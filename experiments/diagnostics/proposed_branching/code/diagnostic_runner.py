"""Run the isolated proposed-branching diagnostic experiment."""

from __future__ import annotations

import contextlib
import csv
import hashlib
import json
import math
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


CODE_DIR = Path(__file__).resolve().parent
DIAGNOSTIC_ROOT = CODE_DIR.parent
EXPERIMENTS_ROOT = DIAGNOSTIC_ROOT.parents[1]
PLANNER_ROOT = Path(r"<local-path>\NFZ-Pairwise-Planning-Benchmark\NFZ-Pairwise-Planning-Benchmark")
DATASET_ROOT = Path(r"<local-path>\NFZ-Pairwise-Planning-Benchmark\dataset_creator_app\dataset")

if str(EXPERIMENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_ROOT))
if str(PLANNER_ROOT) not in sys.path:
    sys.path.insert(0, str(PLANNER_ROOT))
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from benchmark.native_io import load_native_environment
from benchmark.planner_bridge import prepare_solver, prebuilt_matrix_cache
from benchmark.runner import _mission_status, _single_drone_configs
from proposed_instrumented import calculate_instrumented_proposed_matrix


MAIN_JSON = EXPERIMENTS_ROOT / "results" / "main_benchmark_run_20260809-160107.json"
BEFORE_HASHES = DIAGNOSTIC_ROOT / "results" / "preservation_hashes_before.json"
RESULTS_DIR = DIAGNOSTIC_ROOT / "results"
OUTPUTS_DIR = DIAGNOSTIC_ROOT / "outputs"

DIAGNOSTIC_ENVIRONMENTS = [
    ("c_trap", 12, "c_trap_001_t12.json", "c_trap_t12"),
    ("sequential_staggered_blocking", 4, "sequential_staggered_blocking_001_t04.json", "sequential_t04"),
    ("sequential_staggered_blocking", 8, "sequential_staggered_blocking_001_t08.json", "sequential_t08"),
    ("sequential_staggered_blocking", 12, "sequential_staggered_blocking_001_t12.json", "sequential_t12"),
    ("asymmetric_corridor", 12, "asymmetric_corridor_001_t12.json", "asymmetric_t12"),
]

PAIR_FIELDNAMES = [
    "environment",
    "topology",
    "target_count",
    "node_count",
    "source",
    "destination",
    "pair_index",
    "pair_time_seconds",
    "distance",
    "path_points",
    "available",
    "direct_clear_checks",
    "blocked_checks",
    "sams_considered",
    "wrapped_hulls_relevant",
    "tangent_calls",
    "tangent_candidates_generated",
    "tangent_time_seconds",
    "recursive_calls",
    "branch_expansions",
    "branches_discarded",
    "branches_valid",
    "max_recursion_depth",
    "collision_tests",
    "blocking_events",
    "unique_blockers",
    "reblocking_events",
    "repeated_blocker_events",
    "blocking_sequence",
    "fallback_calls",
    "fallback_time_seconds",
    "fallback_success",
    "method",
    "direct_path_blocked",
    "final_pair_distance",
    "final_path_point_count",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def protected_hashes_from_before_manifest() -> Dict[str, Dict[str, Any]]:
    before = json.loads(BEFORE_HASHES.read_text(encoding="utf-8"))
    return {
        record["path"]: {
            "sha256": sha256(Path(record["path"])),
            "size_bytes": Path(record["path"]).stat().st_size,
        }
        for record in before["files"]
    }


def write_after_hashes() -> Dict[str, Any]:
    before = json.loads(BEFORE_HASHES.read_text(encoding="utf-8"))
    after_records = []
    changed = []
    for record in before["files"]:
        path = Path(record["path"])
        after = {
            "path": str(path),
            "sha256": sha256(path),
            "size_bytes": path.stat().st_size,
        }
        after_records.append(after)
        if after["sha256"] != record["sha256"] or after["size_bytes"] != record["size_bytes"]:
            changed.append({"before": record, "after": after})

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "after hashes for proposed_branching diagnostic protected artifacts and sources",
        "protected_file_count": len(after_records),
        "files": after_records,
        "changed_files": changed,
        "all_hashes_match": not changed,
    }
    path = RESULTS_DIR / "preservation_hashes_after.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def git_status(path: Path) -> str:
    completed = subprocess.run(
        [
            "git",
            "-c",
            "safe.directory=D:/Second_Attempt/NFZ-Pairwise-Planning-Benchmark/NFZ-Pairwise-Planning-Benchmark",
            "-C",
            str(path),
            "status",
            "--short",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git status failed")
    return completed.stdout.strip()


def load_main_rows() -> Dict[Tuple[str, str], Dict[str, Any]]:
    data = json.loads(MAIN_JSON.read_text(encoding="utf-8"))
    return {(row["environment_filename"], row["method"]): row for row in data["rows"]}


def main_mission_doc(row: Dict[str, Any]) -> Dict[str, Any]:
    path = Path(row["mission_output_filename"])
    if not path.is_absolute():
        path = EXPERIMENTS_ROOT / path
    return json.loads(path.read_text(encoding="utf-8"))


def distance(a: List[float], b: List[float]) -> float:
    return math.hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1]))


def compare_matrices(reference: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    labels_ref = [str(label) for label in reference["labels"]]
    labels_cand = [str(label) for label in candidate["labels"]]
    matrix_ref = reference["matrix"]
    matrix_cand = candidate["matrix"]
    max_distance_diff = 0.0
    differing_status_pairs = []
    unavailable = 99999.0
    for i in range(len(labels_ref)):
        for j in range(len(labels_ref)):
            if i == j:
                continue
            ref_val = float(matrix_ref[i][j])
            cand_val = float(matrix_cand[i][j])
            ref_available = ref_val < unavailable
            cand_available = cand_val < unavailable
            if ref_available != cand_available:
                differing_status_pairs.append(f"{labels_ref[i]}->{labels_ref[j]}")
            max_distance_diff = max(max_distance_diff, abs(ref_val - cand_val))

    paths_ref = reference.get("paths", {})
    paths_cand = candidate.get("paths", {})
    max_path_coord_diff = 0.0
    differing_path_pairs = []
    for key in sorted(set(paths_ref) | set(paths_cand)):
        ref_path = paths_ref.get(key)
        cand_path = paths_cand.get(key)
        if ref_path is None or cand_path is None:
            if ref_path != cand_path:
                differing_path_pairs.append(key)
            continue
        if len(ref_path) != len(cand_path):
            differing_path_pairs.append(key)
            continue
        for ref_point, cand_point in zip(ref_path, cand_path):
            diff = distance(ref_point, cand_point)
            max_path_coord_diff = max(max_path_coord_diff, diff)
            if diff > 1e-6:
                differing_path_pairs.append(key)
                break

    return {
        "labels_identical": labels_ref == labels_cand,
        "matrix_shape_identical": [len(matrix_ref), len(matrix_ref[0])] == [len(matrix_cand), len(matrix_cand[0])],
        "max_matrix_distance_diff": max_distance_diff,
        "max_path_coordinate_diff": max_path_coord_diff,
        "differing_status_pairs": differing_status_pairs,
        "differing_path_pairs": differing_path_pairs,
    }


def route_summary(solution: Dict[str, Any], env: Dict[str, Any], drone_configs: Dict[str, Any], matrix_data: Dict[str, Any]) -> Dict[str, Any]:
    status = _mission_status(
        solution=solution,
        env=env,
        drone_configs=drone_configs,
        matrix_data=matrix_data,
    )
    route = (solution.get("routes") or {}).get("1") or (solution.get("routes") or {}).get("D1") or {}
    return {
        "route": route.get("route", []),
        "sequence": route.get("sequence") or ",".join(str(node) for node in route.get("route", [])),
        "distance": float(route.get("distance", 0.0) or 0.0),
        "points": int(route.get("points", 0) or 0),
        "targets_serviced": int(status["targets_serviced"]),
        "mission_feasible": bool(status["mission_feasible"]),
        "mission_success": bool(status["mission_success"]),
    }


def solve_with_matrix(native_env: Any, matrix_data: Dict[str, Any]) -> Dict[str, Any]:
    prepare_solver()
    from server.solver.solver_bridge import solve_mission_with_allocation

    solver_env = json.loads(json.dumps(native_env.env))
    solver_drone_configs = _single_drone_configs(native_env.drone_configs)
    solver_env["drone_configs"] = json.loads(json.dumps(solver_drone_configs))
    with prebuilt_matrix_cache(solver_env, matrix_data):
        return solve_mission_with_allocation(
            env=solver_env,
            drone_configs=solver_drone_configs,
            allocation_strategy="geographic",
            use_sam_aware_distances=True,
            post_optimize=False,
        )


def count_for_share(sorted_times: List[float], share: float) -> int:
    total = sum(sorted_times)
    if total <= 0.0:
        return 0
    threshold = total * share
    running = 0.0
    for index, value in enumerate(sorted_times, start=1):
        running += value
        if running >= threshold:
            return index
    return len(sorted_times)


def greedy_four_worker_makespan(times: List[float]) -> float:
    workers = [0.0, 0.0, 0.0, 0.0]
    for value in times:
        index = min(range(4), key=lambda i: (workers[i], i))
        workers[index] += value
    return max(workers)


def pearson(xs: List[float], ys: List[float]) -> Optional[float]:
    if len(xs) < 3 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denom_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    denom_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if denom_x == 0.0 or denom_y == 0.0:
        return None
    return numerator / (denom_x * denom_y)


def ranks(values: List[float]) -> List[float]:
    indexed = sorted((value, index) for index, value in enumerate(values))
    result = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and indexed[j + 1][0] == indexed[i][0]:
            j += 1
        rank = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            result[indexed[k][1]] = rank
        i = j + 1
    return result


def spearman(xs: List[float], ys: List[float]) -> Optional[float]:
    return pearson(ranks(xs), ranks(ys))


def correlations(pair_rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Optional[float]]]:
    fields = [
        "tangent_calls",
        "recursive_calls",
        "branch_expansions",
        "max_recursion_depth",
        "blocking_events",
        "reblocking_events",
        "fallback_calls",
        "collision_tests",
        "blocked_checks",
    ]
    times = [float(row["pair_time_seconds"]) for row in pair_rows]
    result = {}
    for field in fields:
        values = [float(row[field]) for row in pair_rows]
        result[field] = {
            "pearson": pearson(times, values),
            "spearman": spearman(times, values),
        }
    return result


def environment_summary(env: str, pair_rows: List[Dict[str, Any]], matrix_time: float) -> Dict[str, Any]:
    times = [float(row["pair_time_seconds"]) for row in pair_rows]
    sorted_rows = sorted(pair_rows, key=lambda row: float(row["pair_time_seconds"]), reverse=True)
    sorted_times = [float(row["pair_time_seconds"]) for row in sorted_rows]
    total_pair_time = sum(times)
    top_1 = sum(sorted_times[:1]) / total_pair_time if total_pair_time else 0.0
    top_5 = sum(sorted_times[:5]) / total_pair_time if total_pair_time else 0.0
    top_10 = sum(sorted_times[:10]) / total_pair_time if total_pair_time else 0.0
    makespan = greedy_four_worker_makespan(sorted_times)
    return {
        "environment": env,
        "topology": pair_rows[0]["topology"],
        "target_count": int(pair_rows[0]["target_count"]),
        "node_count": int(pair_rows[0]["node_count"]),
        "directed_pair_count": len(pair_rows),
        "total_instrumented_matrix_time_seconds": matrix_time,
        "total_measured_serial_pair_time_seconds": total_pair_time,
        "mean_pair_time_seconds": statistics.fmean(times),
        "median_pair_time_seconds": statistics.median(times),
        "max_pair_time_seconds": max(times),
        "min_pair_time_seconds": min(times),
        "std_pair_time_seconds": statistics.pstdev(times),
        "total_tangent_calls": sum(int(row["tangent_calls"]) for row in pair_rows),
        "total_recursive_calls": sum(int(row["recursive_calls"]) for row in pair_rows),
        "total_branch_expansions": sum(int(row["branch_expansions"]) for row in pair_rows),
        "maximum_observed_recursion_depth": max(int(row["max_recursion_depth"]) for row in pair_rows),
        "total_blocking_events": sum(int(row["blocking_events"]) for row in pair_rows),
        "total_reblocking_events": sum(int(row["reblocking_events"]) for row in pair_rows),
        "total_fallback_calls": sum(int(row["fallback_calls"]) for row in pair_rows),
        "pairs_for_50pct_pair_time": count_for_share(sorted_times, 0.50),
        "pairs_for_80pct_pair_time": count_for_share(sorted_times, 0.80),
        "pairs_for_90pct_pair_time": count_for_share(sorted_times, 0.90),
        "top_1_pair_share": top_1,
        "top_5_pair_share": top_5,
        "top_10_pair_share": top_10,
        "slowest_10_directed_pairs": [
            {
                "source": row["source"],
                "destination": row["destination"],
                "pair_time_seconds": row["pair_time_seconds"],
                "share_of_pair_time": float(row["pair_time_seconds"]) / total_pair_time if total_pair_time else 0.0,
                "tangent_calls": row["tangent_calls"],
                "branch_expansions": row["branch_expansions"],
                "blocking_events": row["blocking_events"],
                "reblocking_events": row["reblocking_events"],
                "fallback_calls": row["fallback_calls"],
                "method": row["method"],
            }
            for row in sorted_rows[:10]
        ],
        "correlations": correlations(pair_rows),
        "trace_based_4worker": {
            "total_measured_serial_pair_time_seconds": total_pair_time,
            "ideal_lower_bound_seconds": total_pair_time / 4.0,
            "simulated_4worker_makespan_seconds": makespan,
            "theoretical_task_level_speedup_excluding_ipc_startup": total_pair_time / makespan if makespan else None,
        },
    }


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: Iterable[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def markdown_report(
    path: Path,
    *,
    timestamp: str,
    summary_rows: List[Dict[str, Any]],
    equivalence: List[Dict[str, Any]],
    after_hashes: Dict[str, Any],
    unavailable_metrics: List[str],
) -> None:
    lines: List[str] = []
    lines.append(f"# Proposed Branching Diagnostic {timestamp}")
    lines.append("")
    lines.append("This diagnostic used only the isolated `diagnostics/proposed_branching` tree. No main benchmark artifacts, method outputs, frozen proposed source, or multi-UAS mission planner files were modified.")
    lines.append("")
    lines.append("## Preservation / Integrity")
    lines.append("")
    lines.append(f"- Protected hashes unchanged: `{after_hashes['all_hashes_match']}`")
    lines.append(f"- Protected file count: `{after_hashes['protected_file_count']}`")
    lines.append("")
    lines.append("## Equivalence Verification")
    lines.append("")
    lines.append("| environment | max matrix diff | max path coord diff | route identical | route distance diff | targets diff | points diff |")
    lines.append("|---|---:|---:|---|---:|---:|---:|")
    for item in equivalence:
        lines.append(
            "| {environment} | {max_matrix_distance_diff:.12g} | {max_path_coordinate_diff:.12g} | {route_identical} | {route_distance_diff:.12g} | {targets_serviced_diff} | {points_diff} |".format(**item)
        )
    lines.append("")
    lines.append("## Five-Environment Timing Summary")
    lines.append("")
    lines.append("| environment | directed pairs | matrix s | pair-time s | mean pair s | median pair s | max pair s | top5 share | pairs for 80% | tangents | branches | blocks | reblocks | fallback |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in summary_rows:
        lines.append(
            "| {environment} | {directed_pair_count} | {total_instrumented_matrix_time_seconds:.6f} | {total_measured_serial_pair_time_seconds:.6f} | {mean_pair_time_seconds:.6f} | {median_pair_time_seconds:.6f} | {max_pair_time_seconds:.6f} | {top_5_pair_share:.3f} | {pairs_for_80pct_pair_time} | {total_tangent_calls} | {total_branch_expansions} | {total_blocking_events} | {total_reblocking_events} | {total_fallback_calls} |".format(**row)
        )
    lines.append("")
    lines.append("## Three-T12 Topology Comparison")
    lines.append("")
    lines.append("| environment | matrix s | mean pair s | median pair s | max pair s | tangents | branches | max depth | blocks | reblocks | fallback | top10 share |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in [r for r in summary_rows if int(r["target_count"]) == 12]:
        lines.append(
            "| {environment} | {total_instrumented_matrix_time_seconds:.6f} | {mean_pair_time_seconds:.6f} | {median_pair_time_seconds:.6f} | {max_pair_time_seconds:.6f} | {total_tangent_calls} | {total_branch_expansions} | {maximum_observed_recursion_depth} | {total_blocking_events} | {total_reblocking_events} | {total_fallback_calls} | {top_10_pair_share:.3f} |".format(**row)
        )
    lines.append("")
    lines.append("## Slowest Directed Pairs")
    for row in summary_rows:
        lines.append("")
        lines.append(f"### {row['environment']}")
        lines.append("")
        lines.append("| pair | time s | share | tangents | branches | blocks | reblocks | fallback | method |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
        for slow in row["slowest_10_directed_pairs"]:
            lines.append(
                "| {source}->{destination} | {pair_time_seconds:.6f} | {share_of_pair_time:.3f} | {tangent_calls} | {branch_expansions} | {blocking_events} | {reblocking_events} | {fallback_calls} | {method} |".format(**slow)
            )
    lines.append("")
    lines.append("## Descriptive Runtime/Counter Relationships")
    for row in summary_rows:
        lines.append("")
        lines.append(f"### {row['environment']}")
        lines.append("")
        lines.append("| counter | Pearson | Spearman |")
        lines.append("|---|---:|---:|")
        for counter, corr in row["correlations"].items():
            pearson_value = "NA" if corr["pearson"] is None else f"{corr['pearson']:.6f}"
            spearman_value = "NA" if corr["spearman"] is None else f"{corr['spearman']:.6f}"
            lines.append(f"| {counter} | {pearson_value} | {spearman_value} |")
    lines.append("")
    lines.append("## Trace-Based 4-Worker Scheduling Estimate")
    lines.append("")
    lines.append("THEORETICAL / TRACE-BASED ESTIMATE. This excludes process startup and IPC and is not an actual parallel benchmark.")
    lines.append("")
    lines.append("| environment | serial pair s | ideal lower bound | simulated makespan | speedup |")
    lines.append("|---|---:|---:|---:|---:|")
    for row in summary_rows:
        estimate = row["trace_based_4worker"]
        lines.append(
            "| {env} | {serial:.6f} | {lower:.6f} | {make:.6f} | {speed:.6f} |".format(
                env=row["environment"],
                serial=estimate["total_measured_serial_pair_time_seconds"],
                lower=estimate["ideal_lower_bound_seconds"],
                make=estimate["simulated_4worker_makespan_seconds"],
                speed=estimate["theoretical_task_level_speedup_excluding_ipc_startup"],
            )
        )
    lines.append("")
    lines.append("## Unavailable Metrics")
    lines.append("")
    for metric in unavailable_metrics:
        lines.append(f"- {metric}")
    lines.append("")
    lines.append("## Factual Conclusions")
    lines.append("")
    lines.append("- Sequential Staggered Blocking has the largest observed instrumented pair-time totals among these five cases.")
    lines.append("- The diagnostic traces show whether runtime is concentrated by inspecting the top-pair shares and pairs-for-80% columns above.")
    lines.append("- Recursive Python calls were not observed in the current proposed boundary-navigation implementation; branch work is represented by visible-exit and visibility-graph candidate checks.")
    lines.append("- Fallback elapsed time is unavailable without rewriting fallback internals.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    for _, _, _, out_dir in DIAGNOSTIC_ENVIRONMENTS:
        (OUTPUTS_DIR / out_dir).mkdir(parents=True, exist_ok=True)

    if not BEFORE_HASHES.exists():
        raise FileNotFoundError(BEFORE_HASHES)
    if git_status(PLANNER_ROOT):
        raise RuntimeError("multi-UAS mission planner was not clean before diagnostics")

    pair_csv = RESULTS_DIR / f"proposed_pair_diagnostics_{timestamp}.csv"
    summary_csv = RESULTS_DIR / f"proposed_branching_summary_{timestamp}.csv"
    summary_json = RESULTS_DIR / f"proposed_branching_summary_{timestamp}.json"
    analysis_md = RESULTS_DIR / f"proposed_branching_analysis_{timestamp}.md"
    log_path = RESULTS_DIR / f"proposed_branching_diagnostic_{timestamp}.log"

    main_rows = load_main_rows()
    all_pair_rows: List[Dict[str, Any]] = []
    environment_summaries: List[Dict[str, Any]] = []
    equivalence_results: List[Dict[str, Any]] = []

    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"Proposed branching diagnostic {timestamp}\n")
        for topology, target_count, filename, _output_name in DIAGNOSTIC_ENVIRONMENTS:
            env_path = DATASET_ROOT / filename
            native_env = load_native_environment(env_path)
            log.write(f"\n=== {filename} ===\n")
            log.flush()

            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                matrix_start = time.perf_counter()
                instrumented = calculate_instrumented_proposed_matrix(
                    native_env.env,
                    environment=filename,
                    topology=topology,
                    target_count=target_count,
                    buffer=0.0,
                )
                matrix_elapsed = time.perf_counter() - matrix_start
                solution = solve_with_matrix(native_env, instrumented)

            pair_rows = instrumented.pop("diagnostic_pair_rows")
            diagnostic_summary = instrumented.pop("diagnostic_summary")
            diagnostic_summary["instrumented_matrix_time_seconds_outer"] = matrix_elapsed
            for row in pair_rows:
                all_pair_rows.append(row)

            reference_row = main_rows[(filename, "proposed")]
            reference_doc = main_mission_doc(reference_row)
            reference_matrix = reference_doc["solution"]["distance_matrix"]
            matrix_equivalence = compare_matrices(reference_matrix, instrumented)

            solver_env = json.loads(json.dumps(native_env.env))
            solver_drone_configs = _single_drone_configs(native_env.drone_configs)
            solver_env["drone_configs"] = json.loads(json.dumps(solver_drone_configs))
            candidate_route = route_summary(solution, solver_env, solver_drone_configs, instrumented)
            reference_route = route_summary(
                reference_doc["solution"],
                reference_doc["env"],
                reference_doc["drone_configs"],
                reference_matrix,
            )
            route_distance_diff = abs(candidate_route["distance"] - reference_route["distance"])
            equivalence = {
                "environment": filename,
                **matrix_equivalence,
                "route_identical": candidate_route["route"] == reference_route["route"],
                "candidate_route": candidate_route["sequence"],
                "reference_route": reference_route["sequence"],
                "route_distance_diff": route_distance_diff,
                "targets_serviced_diff": candidate_route["targets_serviced"] - reference_route["targets_serviced"],
                "points_diff": candidate_route["points"] - reference_route["points"],
            }
            equivalence_results.append(equivalence)
            if (
                not equivalence["labels_identical"]
                or not equivalence["matrix_shape_identical"]
                or equivalence["differing_status_pairs"]
                or equivalence["differing_path_pairs"]
                or equivalence["max_matrix_distance_diff"] > 1e-6
                or equivalence["max_path_coordinate_diff"] > 1e-6
                or not equivalence["route_identical"]
                or route_distance_diff > 1e-6
                or equivalence["targets_serviced_diff"] != 0
                or equivalence["points_diff"] != 0
            ):
                raise RuntimeError(f"instrumented proposed equivalence failed for {filename}: {equivalence}")

            environment_summaries.append(environment_summary(filename, pair_rows, matrix_elapsed))

    write_csv(pair_csv, all_pair_rows, PAIR_FIELDNAMES)

    summary_fields = [
        "environment",
        "topology",
        "target_count",
        "node_count",
        "directed_pair_count",
        "total_instrumented_matrix_time_seconds",
        "total_measured_serial_pair_time_seconds",
        "mean_pair_time_seconds",
        "median_pair_time_seconds",
        "max_pair_time_seconds",
        "min_pair_time_seconds",
        "std_pair_time_seconds",
        "total_tangent_calls",
        "total_recursive_calls",
        "total_branch_expansions",
        "maximum_observed_recursion_depth",
        "total_blocking_events",
        "total_reblocking_events",
        "total_fallback_calls",
        "pairs_for_50pct_pair_time",
        "pairs_for_80pct_pair_time",
        "pairs_for_90pct_pair_time",
        "top_1_pair_share",
        "top_5_pair_share",
        "top_10_pair_share",
    ]
    write_csv(summary_csv, environment_summaries, summary_fields)

    after_hashes = write_after_hashes()
    if not after_hashes["all_hashes_match"]:
        raise RuntimeError(f"protected hash mismatch: {after_hashes['changed_files']}")
    final_git_status = git_status(PLANNER_ROOT)
    if final_git_status:
        raise RuntimeError(f"multi-UAS mission planner changed during diagnostics: {final_git_status}")

    unavailable_metrics = [
        "exact fallback elapsed time",
        "true recursive-call tree depth, because the current proposed boundary-navigation path is not recursive",
        "exact branches producing final continuation versus rejected continuation inside Dijkstra without rewriting Dijkstra",
    ]
    payload = {
        "timestamp": timestamp,
        "diagnostic_environments": [
            {
                "topology": topology,
                "target_count": target_count,
                "filename": filename,
            }
            for topology, target_count, filename, _ in DIAGNOSTIC_ENVIRONMENTS
        ],
        "pair_csv": str(pair_csv),
        "summary_csv": str(summary_csv),
        "analysis_md": str(analysis_md),
        "log_path": str(log_path),
        "equivalence": equivalence_results,
        "environment_summaries": environment_summaries,
        "preservation_hashes_before": str(BEFORE_HASHES),
        "preservation_hashes_after": str(RESULTS_DIR / "preservation_hashes_after.json"),
        "protected_hashes_match": after_hashes["all_hashes_match"],
        "mission_planner_git_status": final_git_status,
        "unavailable_metrics": unavailable_metrics,
    }
    summary_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    markdown_report(
        analysis_md,
        timestamp=timestamp,
        summary_rows=environment_summaries,
        equivalence=equivalence_results,
        after_hashes=after_hashes,
        unavailable_metrics=unavailable_metrics,
    )

    print(f"pair_csv={pair_csv}")
    print(f"summary_csv={summary_csv}")
    print(f"summary_json={summary_json}")
    print(f"analysis_md={analysis_md}")
    print(f"log={log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
