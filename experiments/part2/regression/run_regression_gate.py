"""Run the Part II Proposed diagnostic functional regression gate."""

from __future__ import annotations

import contextlib
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENTS_ROOT = REPO_ROOT / "experiments"
PART2_ROOT = EXPERIMENTS_ROOT / "part2"

for path in (REPO_ROOT, EXPERIMENTS_ROOT, PART2_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from benchmark.planner_bridge import prebuilt_matrix_cache, prepare_solver
from benchmark.runner import _mission_status, _single_drone_configs
from diagnostics.proposed_diagnostics import run_diagnostics_for_environment


TOLERANCE_KM = 1e-6

CONTROLLED_RUN2 = (
    EXPERIMENTS_ROOT / "main_benchmark_replications" / "run_02_20260810-015756"
)
COMPOSITE_RUN2 = (
    EXPERIMENTS_ROOT
    / "composite_adversarial_replications"
    / "run_02_20260809-222140"
)

REGRESSION_CASES = [
    {
        "case_id": "c_trap_t12",
        "label": "C-Trap t12",
        "topology": "c_trap",
        "instance_id": "part1_controlled_001",
        "seed": None,
        "environment": CONTROLLED_RUN2 / "input_snapshot" / "c_trap_001_t12.json",
        "summary": CONTROLLED_RUN2 / "outputs" / "proposed" / "benchmark_summary.jsonl",
        "source_environment_id": "c_trap_001_t12",
    },
    {
        "case_id": "sequential_staggered_blocking_t12",
        "label": "Sequential Staggered Blocking t12",
        "topology": "sequential_staggered_blocking",
        "instance_id": "part1_controlled_001",
        "seed": None,
        "environment": CONTROLLED_RUN2
        / "input_snapshot"
        / "sequential_staggered_blocking_001_t12.json",
        "summary": CONTROLLED_RUN2 / "outputs" / "proposed" / "benchmark_summary.jsonl",
        "source_environment_id": "sequential_staggered_blocking_001_t12",
    },
    {
        "case_id": "asymmetric_corridor_t12",
        "label": "Asymmetric Corridor t12",
        "topology": "asymmetric_corridor",
        "instance_id": "part1_controlled_001",
        "seed": None,
        "environment": CONTROLLED_RUN2
        / "input_snapshot"
        / "asymmetric_corridor_001_t12.json",
        "summary": CONTROLLED_RUN2 / "outputs" / "proposed" / "benchmark_summary.jsonl",
        "source_environment_id": "asymmetric_corridor_001_t12",
    },
    {
        "case_id": "composite_adversarial_t12",
        "label": "Composite Adversarial t12",
        "topology": "composite_adversarial",
        "instance_id": "part1_composite_001",
        "seed": None,
        "environment": COMPOSITE_RUN2
        / "input_snapshot"
        / "composite_adversarial_001_t12.json",
        "summary": COMPOSITE_RUN2 / "outputs" / "proposed" / "benchmark_summary.jsonl",
        "source_environment_id": "composite_adversarial_001_t12",
    },
]


def load_summary_row(path: Path, source_environment_id: str) -> Dict[str, Any]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for row in rows:
        if row.get("source_environment_id") == source_environment_id:
            return row
    raise KeyError(f"{source_environment_id} not found in {path}")


def resolve_recorded_path(recorded: str) -> Path:
    path = Path(recorded)
    if path.exists():
        return path
    marker = "experiments"
    parts = list(path.parts)
    if marker in parts:
        idx = parts.index(marker)
        candidate = EXPERIMENTS_ROOT.joinpath(*parts[idx + 1 :])
        if candidate.exists():
            return candidate
    raise FileNotFoundError(recorded)


def route_data(solution: Dict[str, Any]) -> Dict[str, Any]:
    routes = solution.get("routes") or {}
    return routes.get("1") or routes.get("D1") or {}


def route_summary(solution: Dict[str, Any], status: Dict[str, Any]) -> Dict[str, Any]:
    route = route_data(solution)
    route_nodes = [str(node) for node in route.get("route", [])]
    return {
        "route": route_nodes,
        "sequence": ",".join(route_nodes),
        "distance": float(route.get("distance", 0.0) or 0.0),
        "points": int(route.get("points", 0) or 0),
        "targets_serviced": int(status["targets_serviced"]),
        "mission_feasible": bool(status["mission_feasible"]),
        "mission_success": bool(status["mission_success"]),
        "failure_reason": status["failure_reason"],
    }


def compare_matrices(reference: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    labels_ref = [str(label) for label in reference["labels"]]
    labels_candidate = [str(label) for label in candidate["labels"]]
    matrix_ref = reference["matrix"]
    matrix_candidate = candidate["matrix"]
    unavailable = 99999.0
    max_matrix_delta = 0.0
    differing_availability: List[str] = []
    differing_values: List[str] = []

    if labels_ref != labels_candidate:
        return {
            "labels_equal": False,
            "shape_equal": False,
            "availability_equal": False,
            "values_equal": False,
            "max_matrix_delta": None,
            "differing_availability": ["labels differ"],
            "differing_values": [],
        }

    shape_equal = [len(matrix_ref), len(matrix_ref[0])] == [
        len(matrix_candidate),
        len(matrix_candidate[0]),
    ]
    for i, source in enumerate(labels_ref):
        for j, destination in enumerate(labels_ref):
            ref_value = float(matrix_ref[i][j])
            candidate_value = float(matrix_candidate[i][j])
            ref_available = ref_value < unavailable
            candidate_available = candidate_value < unavailable
            pair = f"{source}->{destination}"
            if ref_available != candidate_available:
                differing_availability.append(pair)
            delta = abs(ref_value - candidate_value)
            max_matrix_delta = max(max_matrix_delta, delta)
            if delta > TOLERANCE_KM:
                differing_values.append(pair)

    return {
        "labels_equal": True,
        "shape_equal": shape_equal,
        "availability_equal": not differing_availability,
        "values_equal": not differing_values,
        "max_matrix_delta": max_matrix_delta,
        "differing_availability": differing_availability,
        "differing_values": differing_values,
    }


def point_delta(a: List[float], b: List[float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def compare_paths(reference: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    paths_ref = reference.get("paths", {})
    paths_candidate = candidate.get("paths", {})
    keys_equal = set(paths_ref) == set(paths_candidate)
    differing_paths: List[str] = []
    max_path_delta = 0.0
    for key in sorted(set(paths_ref) | set(paths_candidate)):
        ref_path = paths_ref.get(key)
        candidate_path = paths_candidate.get(key)
        if ref_path is None or candidate_path is None:
            if ref_path != candidate_path:
                differing_paths.append(key)
            continue
        if len(ref_path) != len(candidate_path):
            differing_paths.append(key)
            continue
        for ref_point, candidate_point in zip(ref_path, candidate_path):
            delta = point_delta(ref_point, candidate_point)
            max_path_delta = max(max_path_delta, delta)
            if delta > TOLERANCE_KM:
                differing_paths.append(key)
                break
    return {
        "path_keys_equal": keys_equal,
        "paths_equal": not differing_paths,
        "max_path_delta": max_path_delta,
        "differing_paths": differing_paths,
    }


def solve_with_matrix(native_env: Any, matrix_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    prepare_solver(REPO_ROOT)
    from server.solver.solver_bridge import solve_mission_with_allocation

    solver_env = json.loads(json.dumps(native_env.env))
    solver_drone_configs = _single_drone_configs(native_env.drone_configs)
    solver_env["drone_configs"] = json.loads(json.dumps(solver_drone_configs))
    with prebuilt_matrix_cache(solver_env, matrix_data):
        solution = solve_mission_with_allocation(
            env=solver_env,
            drone_configs=solver_drone_configs,
            allocation_strategy="geographic",
            use_sam_aware_distances=True,
            post_optimize=False,
        )
    status = _mission_status(
        solution=solution,
        env=solver_env,
        drone_configs=solver_drone_configs,
        matrix_data=matrix_data,
    )
    return solution, status


def compare_routes(reference: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    distance_delta = abs(reference["distance"] - candidate["distance"])
    return {
        "route_equal": reference["route"] == candidate["route"],
        "mission_success_equal": reference["mission_success"] == candidate["mission_success"],
        "mission_feasible_equal": reference["mission_feasible"] == candidate["mission_feasible"],
        "targets_serviced_equal": reference["targets_serviced"] == candidate["targets_serviced"],
        "points_equal": reference["points"] == candidate["points"],
        "failure_reason_equal": reference["failure_reason"] == candidate["failure_reason"],
        "route_distance_delta": distance_delta,
        "route_distance_equal": distance_delta <= TOLERANCE_KM,
        "reference_sequence": reference["sequence"],
        "candidate_sequence": candidate["sequence"],
    }


def case_passed(result: Dict[str, Any]) -> bool:
    matrix = result["matrix_comparison"]
    paths = result["path_comparison"]
    route = result["route_comparison"]
    return all(
        [
            matrix["labels_equal"],
            matrix["shape_equal"],
            matrix["availability_equal"],
            matrix["values_equal"],
            paths["path_keys_equal"],
            paths["paths_equal"],
            route["route_equal"],
            route["mission_success_equal"],
            route["mission_feasible_equal"],
            route["targets_serviced_equal"],
            route["points_equal"],
            route["failure_reason_equal"],
            route["route_distance_equal"],
        ]
    )


def run_case(case: Dict[str, Any], output_dir: Path, log_handle: Any) -> Dict[str, Any]:
    summary_row = load_summary_row(case["summary"], case["source_environment_id"])
    reference_doc_path = resolve_recorded_path(summary_row["output_mission_json"])
    reference_doc = json.loads(reference_doc_path.read_text(encoding="utf-8"))
    reference_matrix = reference_doc["solution"]["distance_matrix"]
    reference_status = {
        "targets_serviced": int(summary_row["targets_serviced"]),
        "mission_feasible": bool(summary_row["mission_feasible"]),
        "mission_success": bool(summary_row["mission_success"]),
        "failure_reason": summary_row.get("failure_reason"),
    }
    reference_route = route_summary(reference_doc["solution"], reference_status)

    with contextlib.redirect_stdout(log_handle), contextlib.redirect_stderr(log_handle):
        diagnostic = run_diagnostics_for_environment(
            environment_path=case["environment"],
            environment_id=case["source_environment_id"],
            topology=case["topology"],
            instance_id=case["instance_id"],
            seed=case["seed"],
        )
        candidate_solution, candidate_status = solve_with_matrix(
            diagnostic.native_env,
            diagnostic.matrix_data,
        )

    candidate_route = route_summary(candidate_solution, candidate_status)
    matrix_comparison = compare_matrices(reference_matrix, diagnostic.matrix_data)
    path_comparison = compare_paths(reference_matrix, diagnostic.matrix_data)
    route_comparison = compare_routes(reference_route, candidate_route)
    reference_runtime = float(summary_row["matrix_build_time_seconds"])
    diagnostic_runtime = float(diagnostic.diagnostic_runtime_sec)
    overhead_pct = (
        ((diagnostic_runtime - reference_runtime) / reference_runtime) * 100.0
        if reference_runtime > 0
        else None
    )

    pair_path = output_dir / f"{case['case_id']}_pair_diagnostics.json"
    summary_path = output_dir / f"{case['case_id']}_environment_summary.json"
    pair_path.write_text(
        json.dumps(diagnostic.pair_rows, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(diagnostic.environment_summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    result = {
        "case_id": case["case_id"],
        "label": case["label"],
        "environment": str(case["environment"]),
        "reference_result": str(reference_doc_path),
        "instrumented_pair_diagnostics": str(pair_path),
        "instrumented_environment_summary": str(summary_path),
        "reference_runtime_sec": reference_runtime,
        "diagnostic_runtime_sec": diagnostic_runtime,
        "diagnostic_overhead_pct": overhead_pct,
        "matrix_comparison": matrix_comparison,
        "path_comparison": path_comparison,
        "route_comparison": route_comparison,
    }
    result["passed"] = case_passed(result)
    return result


def write_csv_report(path: Path, results: List[Dict[str, Any]]) -> None:
    fieldnames = [
        "case_id",
        "label",
        "passed",
        "reference_runtime_sec",
        "diagnostic_runtime_sec",
        "diagnostic_overhead_pct",
        "max_matrix_delta",
        "max_path_delta",
        "route_distance_delta",
        "matrix_values_equal",
        "paths_equal",
        "route_equal",
        "mission_success_equal",
        "mission_feasible_equal",
        "targets_serviced_equal",
        "failure_reason_equal",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "case_id": result["case_id"],
                    "label": result["label"],
                    "passed": result["passed"],
                    "reference_runtime_sec": result["reference_runtime_sec"],
                    "diagnostic_runtime_sec": result["diagnostic_runtime_sec"],
                    "diagnostic_overhead_pct": result["diagnostic_overhead_pct"],
                    "max_matrix_delta": result["matrix_comparison"]["max_matrix_delta"],
                    "max_path_delta": result["path_comparison"]["max_path_delta"],
                    "route_distance_delta": result["route_comparison"]["route_distance_delta"],
                    "matrix_values_equal": result["matrix_comparison"]["values_equal"],
                    "paths_equal": result["path_comparison"]["paths_equal"],
                    "route_equal": result["route_comparison"]["route_equal"],
                    "mission_success_equal": result["route_comparison"]["mission_success_equal"],
                    "mission_feasible_equal": result["route_comparison"]["mission_feasible_equal"],
                    "targets_serviced_equal": result["route_comparison"]["targets_serviced_equal"],
                    "failure_reason_equal": result["route_comparison"]["failure_reason_equal"],
                }
            )


def write_markdown(path: Path, payload: Dict[str, Any]) -> None:
    lines = [
        "# Part II Functional Regression Gate",
        "",
        f"Created at: `{payload['created_at']}`",
        "",
        "This gate compares frozen Part I Proposed outputs against the Part II",
        "instrumented Proposed diagnostic wrapper. Timing overhead is recorded but",
        "does not determine pass/fail.",
        "",
        f"Tolerance: `{TOLERANCE_KM}` km",
        "",
        "## Overall Result",
        "",
        f"PART II FUNCTIONAL REGRESSION GATE: {'PASS' if payload['passed'] else 'FAIL'}",
        "",
        "## Cases",
        "",
        "| case | pass | reference s | diagnostic s | overhead % | max matrix delta | max path delta | route delta |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for result in payload["results"]:
        overhead = result["diagnostic_overhead_pct"]
        overhead_text = "NA" if overhead is None else f"{overhead:.3f}"
        lines.append(
            "| {label} | {passed} | {ref:.6f} | {diag:.6f} | {overhead} | {matrix_delta:.12g} | {path_delta:.12g} | {route_delta:.12g} |".format(
                label=result["label"],
                passed=result["passed"],
                ref=result["reference_runtime_sec"],
                diag=result["diagnostic_runtime_sec"],
                overhead=overhead_text,
                matrix_delta=result["matrix_comparison"]["max_matrix_delta"],
                path_delta=result["path_comparison"]["max_path_delta"],
                route_delta=result["route_comparison"]["route_distance_delta"],
            )
        )
    lines.extend(["", "## Details", ""])
    for result in payload["results"]:
        lines.extend(
            [
                f"### {result['label']}",
                "",
                f"- Reference environment: `{result['environment']}`",
                f"- Reference frozen result: `{result['reference_result']}`",
                f"- Instrumented result: `{result['instrumented_environment_summary']}`",
                f"- Matrix equality/pass: `{result['matrix_comparison']['values_equal']}`",
                f"- Path equality/pass: `{result['path_comparison']['paths_equal']}`",
                f"- Route equality/pass: `{result['route_comparison']['route_equal']}`",
                f"- Mission outcome equality/pass: `{result['route_comparison']['mission_success_equal'] and result['route_comparison']['mission_feasible_equal'] and result['route_comparison']['targets_serviced_equal']}`",
                f"- Distance delta: `{result['route_comparison']['route_distance_delta']}`",
                f"- Diagnostic overhead percent: `{result['diagnostic_overhead_pct']}`",
                f"- Overall: `{'PASS' if result['passed'] else 'FAIL'}`",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_dir = PART2_ROOT / "regression" / "outputs" / f"part2_regression_gate_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "part2_regression_gate.log"
    results: List[Dict[str, Any]] = []
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"Part II regression gate {timestamp}\n")
        for case in REGRESSION_CASES:
            log.write(f"\n=== {case['label']} ===\n")
            log.flush()
            results.append(run_case(case, output_dir, log))

    payload = {
        "schema": "nfz_part2_regression_gate_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "part1_experiment_commit": "73b9a7b60fa892bbf2220e6a961c1393ab28fbf5",
        "dataset_generator_commit": "5f26eb8a5119af9854a5d49de3f900821701a689",
        "tolerance_km": TOLERANCE_KM,
        "log": str(log_path),
        "results": results,
    }
    payload["passed"] = all(result["passed"] for result in results)

    json_path = output_dir / "part2_regression_gate.json"
    csv_path = output_dir / "part2_regression_gate.csv"
    md_path = PART2_ROOT / "regression" / "PART2_REGRESSION_GATE.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    write_csv_report(csv_path, results)
    write_markdown(md_path, payload)

    print(f"markdown={md_path}")
    print(f"json={json_path}")
    print(f"csv={csv_path}")
    print(f"log={log_path}")
    print(f"passed={payload['passed']}")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
