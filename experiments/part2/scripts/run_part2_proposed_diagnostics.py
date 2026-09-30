"""Run the Part II Proposed diagnostic campaign.

This campaign uses the regression-validated instrumented Proposed wrapper for
mechanistic branch-use diagnostics. It does not run the primary nine-method
benchmark and does not replace the frozen primary timing results.
"""

from __future__ import annotations

import contextlib
import copy
import csv
import json
import math
import statistics
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENTS_ROOT = REPO_ROOT / "experiments"
PART2_ROOT = EXPERIMENTS_ROOT / "part2"
SCRIPT_ROOT = PART2_ROOT / "scripts"
RESULTS_ROOT = PART2_ROOT / "results" / "diagnostics" / "proposed_branching"
ANALYSIS_ROOT = PART2_ROOT / "analysis"
MANIFEST_ROOT = PART2_ROOT / "manifests"
PRIMARY_RUN_DIR = PART2_ROOT / "results" / "primary" / "run_01_20260812-194711"
PRIMARY_RECORDS_DIR = PRIMARY_RUN_DIR / "records"
PART1_DIAGNOSTIC_PAIR_CSV = (
    EXPERIMENTS_ROOT
    / "diagnostics"
    / "proposed_branching"
    / "results"
    / "proposed_pair_diagnostics_20260809-165543.csv"
)
PART1_DIAGNOSTIC_SUMMARY_JSON = (
    EXPERIMENTS_ROOT
    / "diagnostics"
    / "proposed_branching"
    / "results"
    / "proposed_branching_summary_20260809-165543.json"
)

STARTING_COMMIT = "ff7d3f36d7cbbcfb9cb9d2e1232e3feae33a5d85"
PRIMARY_RESULTS_COMMIT = STARTING_COMMIT
PART2_INFRASTRUCTURE_COMMIT = "1163ae8164f9ffe7ad60dc8cfd1dd7cebcfca0ba"
PART1_EXPERIMENT_COMMIT = "73b9a7b60fa892bbf2220e6a961c1393ab28fbf5"
DATASET_GENERATOR_COMMIT = "5f26eb8a5119af9854a5d49de3f900821701a689"

METHOD = "proposed_diagnostic"
REFERENCE_METHOD = "proposed"
VISIBILITY_GRAPH_METHOD = "visibility_graph"
TOLERANCE_KM = 1e-6
EXPECTED_ENVIRONMENTS = 15
EXPECTED_DIRECTED_PAIRS_PER_ENVIRONMENT = 156
EXPECTED_PAIR_RECORDS = EXPECTED_ENVIRONMENTS * EXPECTED_DIRECTED_PAIRS_PER_ENVIRONMENT

TOPOLOGY_ORDER = [
    "c_trap",
    "sequential_staggered_blocking",
    "asymmetric_corridor",
]

TOPOLOGY_DISPLAY = {
    "c_trap": "C-Trap",
    "sequential_staggered_blocking": "Sequential Staggered Blocking",
    "asymmetric_corridor": "Asymmetric Corridor",
}

BRANCH_CLASSES = ("direct", "single_region", "multi_region_visibility", "failed")

PAIR_FIELDS = [
    "environment_id",
    "topology",
    "instance_id",
    "seed",
    "source_node",
    "destination_node",
    "branch_class",
    "pair_time_sec",
    "path_distance_km",
    "feasible",
    "raw_method",
    "direct_path_blocked",
    "pair_index",
    "node_count",
    "target_count",
    "native_nfz_count",
    "cluster_count",
    "singleton_region_count",
    "multi_nfz_cluster_count",
    "wrapped_region_count",
    "relevant_blocking_region_count",
    "tangent_call_count",
    "tangent_exit_check_count",
    "visibility_edge_clearance_checks",
    "blocking_checks",
    "reblocking_checks",
    "blocking_sequence",
]

ENVIRONMENT_SUMMARY_FIELDS = [
    "environment_id",
    "topology",
    "topology_display",
    "instance_id",
    "seed",
    "directed_pair_count",
    "direct_count",
    "single_region_count",
    "multi_region_visibility_count",
    "failed_count",
    "direct_percent",
    "single_region_percent",
    "multi_region_visibility_percent",
    "failed_percent",
    "primary_proposed_matrix_time_sec",
    "primary_visibility_graph_matrix_time_sec",
    "vg_proposed_primary_ratio",
    "diagnostic_matrix_time_sec",
    "diagnostic_overhead_percent",
    "total_pair_time_sec",
    "direct_pair_time_sec",
    "single_region_pair_time_sec",
    "multi_region_visibility_pair_time_sec",
    "failed_pair_time_sec",
    "mean_direct_pair_time_sec",
    "mean_single_region_pair_time_sec",
    "mean_multi_region_visibility_pair_time_sec",
    "mean_failed_pair_time_sec",
    "median_direct_pair_time_sec",
    "median_single_region_pair_time_sec",
    "median_multi_region_visibility_pair_time_sec",
    "median_failed_pair_time_sec",
    "max_direct_pair_time_sec",
    "max_single_region_pair_time_sec",
    "max_multi_region_visibility_pair_time_sec",
    "max_failed_pair_time_sec",
    "native_nfz_count",
    "cluster_count",
    "singleton_region_count",
    "multi_nfz_cluster_count",
    "wrapped_region_count",
    "sum_relevant_blocking_region_count",
    "total_tangent_call_count",
    "total_tangent_exit_check_count",
    "total_visibility_edge_clearance_checks",
    "total_blocking_checks",
    "total_reblocking_checks",
    "mission_success",
    "mission_feasible",
    "targets_serviced",
    "mission_distance_km",
    "functional_equivalence_passed",
    "output_mission_file",
    "source_mission_file",
    "source_dataset_hash",
]

CROSSOVER_FIELDS = [
    "environment_id",
    "topology",
    "topology_display",
    "instance_id",
    "seed",
    "primary_proposed_matrix_time_sec",
    "primary_visibility_graph_matrix_time_sec",
    "vg_proposed_primary_ratio",
    "vg_beats_proposed",
    "direct_percent",
    "single_region_percent",
    "multi_region_visibility_percent",
    "failed_percent",
    "wrapped_region_count",
    "total_visibility_edge_clearance_checks",
    "total_blocking_checks",
    "total_reblocking_checks",
    "total_tangent_call_count",
    "sum_relevant_blocking_region_count",
    "diagnostic_matrix_time_sec",
    "diagnostic_overhead_percent",
]

MANIFEST_FIELDS = [
    "environment_id",
    "topology",
    "instance_id",
    "seed",
    "method",
    "result_path",
    "result_sha256",
    "pair_diagnostics_path",
    "pair_diagnostics_sha256",
    "environment_summary_path",
    "environment_summary_sha256",
    "output_mission_file",
    "output_mission_sha256",
    "execution_status",
    "functional_equivalence_passed",
    "directed_pair_count",
    "failed_pair_count",
    "direct_count",
    "single_region_count",
    "multi_region_visibility_count",
    "primary_proposed_matrix_time_sec",
    "diagnostic_matrix_time_sec",
    "diagnostic_overhead_percent",
    "matrix_distance_max_delta",
    "path_coordinate_max_delta",
    "route_distance_delta",
    "git_commit",
    "primary_results_commit",
    "source_dataset_hash",
]

TOPOLOGY_METRICS = [
    ("direct_percent", "Direct pair %"),
    ("single_region_percent", "Single-region pair %"),
    ("multi_region_visibility_percent", "Multi-region Visibility Graph pair %"),
    ("failed_percent", "Failed pair %"),
    ("primary_proposed_matrix_time_sec", "Primary Proposed matrix time sec"),
    ("primary_visibility_graph_matrix_time_sec", "Primary VG matrix time sec"),
    ("vg_proposed_primary_ratio", "VG / Proposed primary ratio"),
    ("diagnostic_matrix_time_sec", "Diagnostic matrix time sec"),
    ("diagnostic_overhead_percent", "Diagnostic overhead %"),
    ("total_tangent_call_count", "Tangent calls"),
    ("total_blocking_checks", "Blocking checks"),
    ("total_reblocking_checks", "Reblocking checks"),
    ("sum_relevant_blocking_region_count", "Relevant blocking region count"),
    ("wrapped_region_count", "Wrapped region count"),
]

for path in (REPO_ROOT, EXPERIMENTS_ROOT, SCRIPT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_part2_primary as primary
from benchmark.native_io import build_mission_document, load_native_environment, mission_filename
from benchmark.planner_bridge import prebuilt_matrix_cache, prepare_solver
from benchmark.runner import _mission_status, _single_drone_configs
from experiments.part2.diagnostics.proposed_diagnostics import (
    run_diagnostics_for_environment,
)


@dataclass(frozen=True)
class Condition:
    execution_index: int
    environment_id: str
    environment_filename: str
    topology: str
    topology_display: str
    instance_id: str
    seed: int
    source_path: Path
    source_dataset_hash: str
    source_file_size_bytes: int


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_text_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, payload: Any) -> None:
    write_text_lf(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_csv(path: Path, rows: Sequence[Dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fields),
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def sha256(path: Path) -> str:
    return primary.sha256(path)


def git_output(*args: str) -> str:
    return primary.git_output(*args)


def format_path(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def as_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def list_text(values: Iterable[Any]) -> str:
    return ";".join("" if value is None else str(value) for value in values)


def percentage(count: int, total: int) -> float:
    return (count / total * 100.0) if total else 0.0


def value_stats(values: Sequence[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {"mean": None, "min": None, "max": None, "range": None}
    return {
        "mean": statistics.fmean(values),
        "min": min(values),
        "max": max(values),
        "range": max(values) - min(values),
    }


def pearson(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
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


def ranks(values: Sequence[float]) -> List[float]:
    indexed = sorted((value, index) for index, value in enumerate(values))
    result = [0.0] * len(indexed)
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


def spearman(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    return pearson(ranks(xs), ranks(ys))


def verify_preconditions() -> Dict[str, Any]:
    branch = git_output("branch", "--show-current")
    head = git_output("rev-parse", "HEAD")
    if branch != "benchmark-part2-generalization":
        raise RuntimeError(f"Unexpected branch: {branch}")
    if head != STARTING_COMMIT:
        raise RuntimeError(f"Unexpected HEAD: {head}")

    environment_info = primary.collect_environment_info()
    primary.verify_execution_environment(environment_info)

    if not PRIMARY_RUN_DIR.exists():
        raise FileNotFoundError(PRIMARY_RUN_DIR)
    if not PART1_DIAGNOSTIC_PAIR_CSV.exists():
        raise FileNotFoundError(PART1_DIAGNOSTIC_PAIR_CSV)
    if not PART1_DIAGNOSTIC_SUMMARY_JSON.exists():
        raise FileNotFoundError(PART1_DIAGNOSTIC_SUMMARY_JSON)

    for path in (
        MANIFEST_ROOT / "part2_proposed_diagnostic_manifest.csv",
        MANIFEST_ROOT / "part2_proposed_diagnostic_manifest.json",
        ANALYSIS_ROOT / "PART2_PROPOSED_DIAGNOSTIC_SUMMARY.md",
        ANALYSIS_ROOT / "part2_proposed_diagnostic_environment_summary.csv",
        ANALYSIS_ROOT / "part2_proposed_diagnostic_environment_summary.json",
        ANALYSIS_ROOT / "part2_proposed_diagnostic_topology_summary.csv",
        ANALYSIS_ROOT / "part2_proposed_diagnostic_topology_summary.json",
        ANALYSIS_ROOT / "part2_proposed_diagnostic_crossover_analysis.csv",
        ANALYSIS_ROOT / "part2_proposed_diagnostic_crossover_analysis.json",
        ANALYSIS_ROOT / "part2_proposed_diagnostic_exploratory_associations.csv",
        ANALYSIS_ROOT / "part2_proposed_diagnostic_exploratory_associations.json",
        ANALYSIS_ROOT / "part2_proposed_diagnostic_part1_context.csv",
        ANALYSIS_ROOT / "part2_proposed_diagnostic_part1_context.json",
    ):
        if path.exists():
            raise FileExistsError(f"Output already exists: {path}")

    return {
        "branch": branch,
        "git_commit": head,
        "environment_info": environment_info,
    }


def load_and_verify_dataset_rows() -> List[Dict[str, Any]]:
    rows = primary.load_dataset_manifest()
    primary.verify_dataset_rows(rows)
    return rows


def build_conditions(rows: List[Dict[str, Any]]) -> List[Condition]:
    by_key = {(row["topology"], row["instance_id"]): row for row in rows}
    conditions: List[Condition] = []
    execution_index = 0
    for topology in TOPOLOGY_ORDER:
        for instance_number in range(1, 6):
            instance_id = f"i{instance_number:02d}"
            row = by_key[(topology, instance_id)]
            execution_index += 1
            source_path = REPO_ROOT / row["relative_path"]
            conditions.append(
                Condition(
                    execution_index=execution_index,
                    environment_id=str(row["environment_id"]),
                    environment_filename=Path(row["relative_path"]).name,
                    topology=topology,
                    topology_display=TOPOLOGY_DISPLAY[topology],
                    instance_id=instance_id,
                    seed=int(row["seed"]),
                    source_path=source_path,
                    source_dataset_hash=str(row["sha256"]).upper(),
                    source_file_size_bytes=int(row["file_size_bytes"]),
                )
            )
    if len(conditions) != EXPECTED_ENVIRONMENTS:
        raise RuntimeError(f"Expected {EXPECTED_ENVIRONMENTS} environments, found {len(conditions)}")
    return conditions


def load_primary_records(method: str) -> Dict[str, Dict[str, Any]]:
    records: Dict[str, Dict[str, Any]] = {}
    for path in sorted(PRIMARY_RECORDS_DIR.glob(f"*__{method}.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        records[str(row["environment_id"])] = row
    if len(records) != EXPECTED_ENVIRONMENTS:
        raise RuntimeError(f"Expected {EXPECTED_ENVIRONMENTS} {method} primary records, found {len(records)}")
    return records


def validate_primary_record_alignment(
    conditions: Sequence[Condition],
    proposed_records: Dict[str, Dict[str, Any]],
    vg_records: Dict[str, Dict[str, Any]],
) -> None:
    expected = {condition.environment_id for condition in conditions}
    if set(proposed_records) != expected:
        raise RuntimeError("Primary Proposed record set does not match Part II environments")
    if set(vg_records) != expected:
        raise RuntimeError("Primary Visibility Graph record set does not match Part II environments")
    for condition in conditions:
        proposed = proposed_records[condition.environment_id]
        vg = vg_records[condition.environment_id]
        if proposed["method"] != REFERENCE_METHOD:
            raise RuntimeError(f"Unexpected Proposed method in {condition.environment_id}")
        if vg["method"] != VISIBILITY_GRAPH_METHOD:
            raise RuntimeError(f"Unexpected VG method in {condition.environment_id}")
        if proposed["source_dataset_hash"].upper() != condition.source_dataset_hash:
            raise RuntimeError(f"Primary Proposed dataset hash mismatch for {condition.environment_id}")
        if vg["source_dataset_hash"].upper() != condition.source_dataset_hash:
            raise RuntimeError(f"Primary VG dataset hash mismatch for {condition.environment_id}")


def load_reference_mission(record: Dict[str, Any]) -> Dict[str, Any]:
    raw_path = Path(record["output_mission_file"])
    path = raw_path if raw_path.is_absolute() else REPO_ROOT / raw_path
    return json.loads(path.read_text(encoding="utf-8"))


def point_distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1]))


def compare_matrices(reference: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    labels_ref = [str(label) for label in reference.get("labels", [])]
    labels_cand = [str(label) for label in candidate.get("labels", [])]
    matrix_ref = reference.get("matrix", [])
    matrix_cand = candidate.get("matrix", [])
    shape_ref = [len(matrix_ref), len(matrix_ref[0]) if matrix_ref else 0]
    shape_cand = [len(matrix_cand), len(matrix_cand[0]) if matrix_cand else 0]
    unavailable = 99999.0
    differing_availability: List[str] = []
    differing_values: List[str] = []
    max_delta = 0.0

    if labels_ref == labels_cand and shape_ref == shape_cand:
        for i, source in enumerate(labels_ref):
            for j, destination in enumerate(labels_ref):
                if i == j:
                    continue
                ref_val = float(matrix_ref[i][j])
                cand_val = float(matrix_cand[i][j])
                ref_available = ref_val < unavailable
                cand_available = cand_val < unavailable
                key = f"{source}->{destination}"
                delta = abs(ref_val - cand_val)
                max_delta = max(max_delta, delta)
                if ref_available != cand_available:
                    differing_availability.append(key)
                if delta > TOLERANCE_KM:
                    differing_values.append(key)

    return {
        "labels_equal": labels_ref == labels_cand,
        "shape_equal": shape_ref == shape_cand,
        "availability_equal": not differing_availability,
        "values_equal": not differing_values and labels_ref == labels_cand and shape_ref == shape_cand,
        "max_matrix_delta": max_delta,
        "differing_availability": differing_availability,
        "differing_values": differing_values,
    }


def compare_paths(reference: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    paths_ref = reference.get("paths", {}) or {}
    paths_cand = candidate.get("paths", {}) or {}
    differing_paths: List[str] = []
    max_delta = 0.0
    keys_equal = set(paths_ref) == set(paths_cand)
    for key in sorted(set(paths_ref) | set(paths_cand)):
        ref_path = paths_ref.get(key)
        cand_path = paths_cand.get(key)
        if ref_path is None or cand_path is None:
            differing_paths.append(key)
            continue
        if len(ref_path) != len(cand_path):
            differing_paths.append(key)
            continue
        for ref_point, cand_point in zip(ref_path, cand_path):
            delta = point_distance(ref_point, cand_point)
            max_delta = max(max_delta, delta)
            if delta > TOLERANCE_KM:
                differing_paths.append(key)
                break
    return {
        "path_keys_equal": keys_equal,
        "paths_equal": keys_equal and not differing_paths,
        "max_path_delta": max_delta,
        "differing_paths": differing_paths,
    }


def route_summary(
    *,
    solution: Dict[str, Any],
    env: Dict[str, Any],
    drone_configs: Dict[str, Any],
    matrix_data: Dict[str, Any],
) -> Dict[str, Any]:
    status = _mission_status(
        solution=solution,
        env=env,
        drone_configs=drone_configs,
        matrix_data=matrix_data,
    )
    routes = solution.get("routes") or {}
    route_data = routes.get("1") or routes.get(1) or routes.get("D1") or {}
    route = [str(node) for node in route_data.get("route", [])]
    return {
        "route": route,
        "sequence": ",".join(route),
        "distance": float(route_data.get("distance", 0.0) or 0.0),
        "points": int(route_data.get("points", 0) or 0),
        "mission_feasible": bool(status["mission_feasible"]),
        "mission_success": bool(status["mission_success"]),
        "targets_serviced": int(status["targets_serviced"]),
        "failure_reason": status["failure_reason"],
    }


def solve_with_diagnostic_matrix(
    native_env: Any,
    matrix_data: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    prepare_solver(REPO_ROOT)
    from server.solver.solver_bridge import solve_mission_with_allocation

    solver_env = copy.deepcopy(native_env.env)
    solver_drone_configs = _single_drone_configs(native_env.drone_configs)
    solver_env["drone_configs"] = copy.deepcopy(solver_drone_configs)
    with prebuilt_matrix_cache(solver_env, matrix_data):
        solution = solve_mission_with_allocation(
            env=solver_env,
            drone_configs=solver_drone_configs,
            allocation_strategy="geographic",
            use_sam_aware_distances=True,
            post_optimize=False,
        )
    return solution, solver_env, solver_drone_configs


def functional_equivalence(
    *,
    condition: Condition,
    matrix_data: Dict[str, Any],
    solution: Dict[str, Any],
    solver_env: Dict[str, Any],
    solver_drone_configs: Dict[str, Any],
    primary_record: Dict[str, Any],
    reference_doc: Dict[str, Any],
) -> Dict[str, Any]:
    reference_matrix = reference_doc["solution"]["distance_matrix"]
    matrix_comparison = compare_matrices(reference_matrix, matrix_data)
    path_comparison = compare_paths(reference_matrix, matrix_data)
    candidate_route = route_summary(
        solution=solution,
        env=solver_env,
        drone_configs=solver_drone_configs,
        matrix_data=matrix_data,
    )
    reference_route = route_summary(
        solution=reference_doc["solution"],
        env=reference_doc["env"],
        drone_configs=reference_doc["drone_configs"],
        matrix_data=reference_matrix,
    )
    route_distance_delta = abs(candidate_route["distance"] - reference_route["distance"])
    primary_distance_delta = abs(candidate_route["distance"] - float(primary_record["mission_distance_km"]))
    result = {
        "environment_id": condition.environment_id,
        "topology": condition.topology,
        "instance_id": condition.instance_id,
        "matrix_comparison": matrix_comparison,
        "path_comparison": path_comparison,
        "route_comparison": {
            "route_equal": candidate_route["route"] == reference_route["route"],
            "candidate_sequence": candidate_route["sequence"],
            "reference_sequence": reference_route["sequence"],
            "route_distance_delta": route_distance_delta,
            "primary_record_distance_delta": primary_distance_delta,
            "mission_success_equal": candidate_route["mission_success"] == reference_route["mission_success"] == as_bool(primary_record["mission_success"]),
            "mission_feasible_equal": candidate_route["mission_feasible"] == reference_route["mission_feasible"] == as_bool(primary_record["mission_feasible"]),
            "targets_serviced_equal": candidate_route["targets_serviced"] == reference_route["targets_serviced"] == int(primary_record["targets_serviced"]),
            "points_equal": candidate_route["points"] == reference_route["points"],
            "failure_reason_equal": candidate_route["failure_reason"] == reference_route["failure_reason"],
        },
    }
    passed = (
        matrix_comparison["labels_equal"]
        and matrix_comparison["shape_equal"]
        and matrix_comparison["availability_equal"]
        and matrix_comparison["values_equal"]
        and path_comparison["paths_equal"]
        and result["route_comparison"]["route_equal"]
        and result["route_comparison"]["route_distance_delta"] <= TOLERANCE_KM
        and result["route_comparison"]["primary_record_distance_delta"] <= TOLERANCE_KM
        and result["route_comparison"]["mission_success_equal"]
        and result["route_comparison"]["mission_feasible_equal"]
        and result["route_comparison"]["targets_serviced_equal"]
        and result["route_comparison"]["points_equal"]
        and result["route_comparison"]["failure_reason_equal"]
    )
    result["passed"] = passed
    return result


def branch_time(summary: Dict[str, Any], branch: str, stat: str) -> Optional[float]:
    return summary.get("branch_time_stats", {}).get(branch, {}).get(stat)


def sum_optional_int(rows: Iterable[Dict[str, Any]], field: str) -> Optional[int]:
    values = [row.get(field) for row in rows if row.get(field) is not None]
    if not values:
        return None
    return sum(int(value) for value in values)


def summarize_environment(
    *,
    condition: Condition,
    diagnostic_summary: Dict[str, Any],
    pair_rows: List[Dict[str, Any]],
    primary_record: Dict[str, Any],
    vg_record: Dict[str, Any],
    equivalence: Dict[str, Any],
    mission_path: Path,
) -> Dict[str, Any]:
    counts = diagnostic_summary["branch_counts"]
    total_pairs = int(diagnostic_summary["directed_pair_count"])
    primary_time = float(primary_record["matrix_time_sec"])
    vg_time = float(vg_record["matrix_time_sec"])
    diagnostic_time = float(diagnostic_summary["diagnostic_runtime_sec"])
    overhead = ((diagnostic_time - primary_time) / primary_time * 100.0) if primary_time else None
    route = equivalence["route_comparison"]
    aggregate_time = diagnostic_summary["branch_time_aggregate_sec"]
    return {
        "environment_id": condition.environment_id,
        "topology": condition.topology,
        "topology_display": condition.topology_display,
        "instance_id": condition.instance_id,
        "seed": condition.seed,
        "directed_pair_count": total_pairs,
        "direct_count": int(counts["direct"]),
        "single_region_count": int(counts["single_region"]),
        "multi_region_visibility_count": int(counts["multi_region_visibility"]),
        "failed_count": int(counts["failed"]),
        "direct_percent": percentage(int(counts["direct"]), total_pairs),
        "single_region_percent": percentage(int(counts["single_region"]), total_pairs),
        "multi_region_visibility_percent": percentage(int(counts["multi_region_visibility"]), total_pairs),
        "failed_percent": percentage(int(counts["failed"]), total_pairs),
        "primary_proposed_matrix_time_sec": primary_time,
        "primary_visibility_graph_matrix_time_sec": vg_time,
        "vg_proposed_primary_ratio": vg_time / primary_time if primary_time else None,
        "diagnostic_matrix_time_sec": diagnostic_time,
        "diagnostic_overhead_percent": overhead,
        "total_pair_time_sec": sum(float(row["pair_time_sec"] or 0.0) for row in pair_rows),
        "direct_pair_time_sec": aggregate_time["direct"],
        "single_region_pair_time_sec": aggregate_time["single_region"],
        "multi_region_visibility_pair_time_sec": aggregate_time["multi_region_visibility"],
        "failed_pair_time_sec": aggregate_time["failed"],
        "mean_direct_pair_time_sec": branch_time(diagnostic_summary, "direct", "mean_sec"),
        "mean_single_region_pair_time_sec": branch_time(diagnostic_summary, "single_region", "mean_sec"),
        "mean_multi_region_visibility_pair_time_sec": branch_time(diagnostic_summary, "multi_region_visibility", "mean_sec"),
        "mean_failed_pair_time_sec": branch_time(diagnostic_summary, "failed", "mean_sec"),
        "median_direct_pair_time_sec": branch_time(diagnostic_summary, "direct", "median_sec"),
        "median_single_region_pair_time_sec": branch_time(diagnostic_summary, "single_region", "median_sec"),
        "median_multi_region_visibility_pair_time_sec": branch_time(diagnostic_summary, "multi_region_visibility", "median_sec"),
        "median_failed_pair_time_sec": branch_time(diagnostic_summary, "failed", "median_sec"),
        "max_direct_pair_time_sec": branch_time(diagnostic_summary, "direct", "max_sec"),
        "max_single_region_pair_time_sec": branch_time(diagnostic_summary, "single_region", "max_sec"),
        "max_multi_region_visibility_pair_time_sec": branch_time(diagnostic_summary, "multi_region_visibility", "max_sec"),
        "max_failed_pair_time_sec": branch_time(diagnostic_summary, "failed", "max_sec"),
        "native_nfz_count": diagnostic_summary["native_nfz_count"],
        "cluster_count": diagnostic_summary["cluster_count"],
        "singleton_region_count": diagnostic_summary["singleton_region_count"],
        "multi_nfz_cluster_count": diagnostic_summary["multi_nfz_cluster_count"],
        "wrapped_region_count": diagnostic_summary["wrapped_region_count"],
        "sum_relevant_blocking_region_count": sum(int(row["relevant_blocking_region_count"] or 0) for row in pair_rows),
        "total_tangent_call_count": sum_optional_int(pair_rows, "tangent_call_count"),
        "total_tangent_exit_check_count": sum_optional_int(pair_rows, "tangent_exit_check_count"),
        "total_visibility_edge_clearance_checks": sum_optional_int(pair_rows, "visibility_edge_clearance_checks"),
        "total_blocking_checks": sum_optional_int(pair_rows, "blocking_checks"),
        "total_reblocking_checks": sum_optional_int(pair_rows, "reblocking_checks"),
        "mission_success": as_bool(primary_record["mission_success"]),
        "mission_feasible": as_bool(primary_record["mission_feasible"]),
        "targets_serviced": int(primary_record["targets_serviced"]),
        "mission_distance_km": float(primary_record["mission_distance_km"]),
        "functional_equivalence_passed": bool(equivalence["passed"]),
        "output_mission_file": format_path(mission_path),
        "source_mission_file": format_path(condition.source_path),
        "source_dataset_hash": condition.source_dataset_hash,
    }


def validate_pair_rows(condition: Condition, pair_rows: Sequence[Dict[str, Any]]) -> None:
    if len(pair_rows) != EXPECTED_DIRECTED_PAIRS_PER_ENVIRONMENT:
        raise RuntimeError(f"{condition.environment_id} has {len(pair_rows)} pair rows")
    keys = set()
    for row in pair_rows:
        branch = row["branch_class"]
        if branch not in BRANCH_CLASSES:
            raise RuntimeError(f"Unexpected branch class in {condition.environment_id}: {branch}")
        if row["source_node"] == row["destination_node"]:
            raise RuntimeError(f"Self-pair emitted in {condition.environment_id}")
        key = (row["source_node"], row["destination_node"])
        if key in keys:
            raise RuntimeError(f"Duplicate pair in {condition.environment_id}: {key}")
        keys.add(key)


def write_progress(
    *,
    path: Path,
    run_id: str,
    campaign_id: str,
    conditions: Sequence[Condition],
    completed: Sequence[Dict[str, Any]],
    infrastructure_failures: Sequence[Dict[str, Any]],
    functional_discrepancies: Sequence[Dict[str, Any]],
    status: str,
    current: Optional[Condition] = None,
) -> None:
    completed_ids = {row["environment_id"] for row in completed}
    pending = [condition.environment_id for condition in conditions if condition.environment_id not in completed_ids]
    write_json(
        path,
        {
            "schema": "nfz_part2_proposed_diagnostic_progress_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "status": status,
            "updated_at": now_iso(),
            "expected_diagnostic_environments": len(conditions),
            "completed_diagnostic_environments": len(completed),
            "pending_diagnostic_environments": len(pending),
            "pending_environment_ids": pending,
            "current_environment_id": current.environment_id if current else None,
            "expected_pair_records": EXPECTED_PAIR_RECORDS,
            "completed_pair_records": sum(int(row["directed_pair_count"]) for row in completed),
            "infrastructure_failure_count": len(infrastructure_failures),
            "functional_discrepancy_count": len(functional_discrepancies),
            "infrastructure_failures": list(infrastructure_failures),
            "functional_discrepancies": list(functional_discrepancies),
            "primary_executions_added": 0,
            "sanity_repetitions": 0,
        },
    )


def load_part1_context() -> List[Dict[str, Any]]:
    wanted = {
        "c_trap_001_t12.json": "c_trap",
        "sequential_staggered_blocking_001_t12.json": "sequential_staggered_blocking",
        "asymmetric_corridor_001_t12.json": "asymmetric_corridor",
    }
    branch_counts = {
        filename: {branch: 0 for branch in BRANCH_CLASSES}
        for filename in wanted
    }
    pair_counts = {filename: 0 for filename in wanted}
    with PART1_DIAGNOSTIC_PAIR_CSV.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            filename = row.get("environment")
            if filename not in wanted:
                continue
            pair_counts[filename] += 1
            method = str(row.get("method") or "")
            available = as_bool(row.get("available"))
            if not available or method.startswith(("INVALID", "no_path_found", "error")):
                branch = "failed"
            elif method.startswith("visibility-graph"):
                branch = "multi_region_visibility"
            elif method.startswith("direct"):
                branch = "direct"
            else:
                branch = "single_region"
            branch_counts[filename][branch] += 1

    payload = json.loads(PART1_DIAGNOSTIC_SUMMARY_JSON.read_text(encoding="utf-8"))
    summary_by_filename = {
        row["environment"]: row
        for row in payload.get("environment_summaries", [])
        if row.get("environment") in wanted
    }
    rows: List[Dict[str, Any]] = []
    for filename, topology in wanted.items():
        total = pair_counts[filename]
        counts = branch_counts[filename]
        summary = summary_by_filename.get(filename, {})
        rows.append(
            {
                "part1_environment": filename,
                "topology": topology,
                "topology_display": TOPOLOGY_DISPLAY[topology],
                "directed_pair_count": total,
                "direct_count": counts["direct"],
                "single_region_count": counts["single_region"],
                "multi_region_visibility_count": counts["multi_region_visibility"],
                "failed_count": counts["failed"],
                "direct_percent": percentage(counts["direct"], total),
                "single_region_percent": percentage(counts["single_region"], total),
                "multi_region_visibility_percent": percentage(counts["multi_region_visibility"], total),
                "failed_percent": percentage(counts["failed"], total),
                "diagnostic_matrix_time_sec": summary.get("total_instrumented_matrix_time_seconds"),
                "total_tangent_call_count": summary.get("total_tangent_calls"),
                "total_blocking_checks": summary.get("total_blocking_events"),
                "total_reblocking_checks": summary.get("total_reblocking_events"),
                "source_summary": format_path(PART1_DIAGNOSTIC_SUMMARY_JSON),
                "source_pair_csv": format_path(PART1_DIAGNOSTIC_PAIR_CSV),
            }
        )
    return rows


def topology_summary_rows(environment_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for topology in TOPOLOGY_ORDER:
        group = [
            row for row in sorted(environment_rows, key=lambda item: item["instance_id"])
            if row["topology"] == topology
        ]
        for metric, label in TOPOLOGY_METRICS:
            values = [float(row[metric]) for row in group if row.get(metric) is not None]
            stats = value_stats(values)
            rows.append(
                {
                    "topology": topology,
                    "topology_display": TOPOLOGY_DISPLAY[topology],
                    "metric": metric,
                    "metric_label": label,
                    "i01": group[0].get(metric),
                    "i02": group[1].get(metric),
                    "i03": group[2].get(metric),
                    "i04": group[3].get(metric),
                    "i05": group[4].get(metric),
                    "values": list_text(row.get(metric) for row in group),
                    **stats,
                }
            )
    return rows


def crossover_rows(environment_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in sorted(environment_rows, key=lambda item: (TOPOLOGY_ORDER.index(item["topology"]), item["instance_id"])):
        crossover = {field: row.get(field) for field in CROSSOVER_FIELDS if field in row}
        crossover["vg_beats_proposed"] = float(row["vg_proposed_primary_ratio"]) < 1.0
        rows.append(crossover)
    return rows


def association_rows(environment_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    metrics = [
        ("multi_region_visibility_percent", "multi-region pair %"),
        ("total_blocking_checks", "blocking checks"),
        ("total_reblocking_checks", "reblocking checks"),
        ("wrapped_region_count", "wrapped region count"),
        ("total_tangent_call_count", "tangent calls"),
        ("sum_relevant_blocking_region_count", "relevant blocking region count"),
    ]
    rows: List[Dict[str, Any]] = []
    primary_times = [float(row["primary_proposed_matrix_time_sec"]) for row in environment_rows]
    for metric, label in metrics:
        metric_rows = [row for row in environment_rows if row.get(metric) is not None]
        xs = [float(row[metric]) for row in metric_rows]
        ys = [float(row["primary_proposed_matrix_time_sec"]) for row in metric_rows]
        rows.append(
            {
                "scope": "all_topologies",
                "metric": metric,
                "metric_label": label,
                "n": len(metric_rows),
                "pearson": pearson(xs, ys),
                "spearman": spearman(xs, ys),
                "primary_time_values_sec": list_text(primary_times),
                "metric_values": list_text(xs),
                "interpretation": "descriptive/exploratory only; n=15",
            }
        )
    return rows


def compare_asymmetric_groups(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    asym = [row for row in rows if row["topology"] == "asymmetric_corridor"]
    vg_faster = [row for row in asym if float(row["vg_proposed_primary_ratio"]) < 1.0]
    proposed_faster = [row for row in asym if float(row["vg_proposed_primary_ratio"]) >= 1.0]

    def group_summary(group: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "instances": [row["instance_id"] for row in group],
            "mean_multi_region_percent": statistics.fmean(float(row["multi_region_visibility_percent"]) for row in group) if group else None,
            "mean_blocking_checks": statistics.fmean(float(row["total_blocking_checks"]) for row in group) if group else None,
            "mean_reblocking_checks": statistics.fmean(float(row["total_reblocking_checks"]) for row in group) if group else None,
            "mean_primary_proposed_matrix_time_sec": statistics.fmean(float(row["primary_proposed_matrix_time_sec"]) for row in group) if group else None,
            "mean_primary_vg_matrix_time_sec": statistics.fmean(float(row["primary_visibility_graph_matrix_time_sec"]) for row in group) if group else None,
            "mean_ratio": statistics.fmean(float(row["vg_proposed_primary_ratio"]) for row in group) if group else None,
        }

    return {
        "vg_faster_than_proposed": group_summary(vg_faster),
        "proposed_faster_than_or_equal_vg": group_summary(proposed_faster),
    }


def branch_pattern_status(rows: Sequence[Dict[str, Any]], topology: str) -> str:
    group = [row for row in rows if row["topology"] == topology]
    patterns = {
        (
            int(row["direct_count"]),
            int(row["single_region_count"]),
            int(row["multi_region_visibility_count"]),
            int(row["failed_count"]),
        )
        for row in group
    }
    return "same branch-count pattern across all five instances" if len(patterns) == 1 else "branch-count pattern varies across instances"


def write_markdown_summary(
    *,
    path: Path,
    run_id: str,
    campaign_id: str,
    run_dir: Path,
    environment_rows: Sequence[Dict[str, Any]],
    topology_rows: Sequence[Dict[str, Any]],
    crossover: Sequence[Dict[str, Any]],
    associations: Sequence[Dict[str, Any]],
    part1_rows: Sequence[Dict[str, Any]],
    manifest_csv: Path,
    manifest_json: Path,
) -> None:
    failed_pairs = sum(int(row["failed_count"]) for row in environment_rows)
    asym_groups = compare_asymmetric_groups(environment_rows)
    lines: List[str] = [
        "# Part II Proposed Diagnostic Summary",
        "",
        "This summary is diagnostic and descriptive only. It must not replace the frozen uninstrumented primary timing results.",
        "",
        "## Campaign",
        "",
        f"- Run: `{run_id}`",
        f"- Campaign ID: `{campaign_id}`",
        f"- Campaign directory: `{format_path(run_dir)}`",
        f"- Diagnostic environments: `{len(environment_rows)}`",
        f"- Pair records: `{sum(int(row['directed_pair_count']) for row in environment_rows)}`",
        f"- Failed Proposed pairs: `{failed_pairs}`",
        f"- Functional equivalence: `{'PASS' if all(row['functional_equivalence_passed'] for row in environment_rows) else 'FAIL'}`",
        f"- Manifest CSV: `{format_path(manifest_csv)}`",
        f"- Manifest JSON: `{format_path(manifest_json)}`",
        "",
        "## Environment Summary",
        "",
        "| topology | instance | Proposed primary s | VG primary s | VG/Proposed | direct % | single-region % | multi-region % | failed | block checks | reblocks | diagnostic s | overhead % |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in environment_rows:
        lines.append(
            "| {topology_display} | {instance_id} | {primary_proposed_matrix_time_sec:.6f} | {primary_visibility_graph_matrix_time_sec:.6f} | {vg_proposed_primary_ratio:.6f} | {direct_percent:.2f} | {single_region_percent:.2f} | {multi_region_visibility_percent:.2f} | {failed_count} | {total_blocking_checks} | {total_reblocking_checks} | {diagnostic_matrix_time_sec:.6f} | {diagnostic_overhead_percent:.2f} |".format(
                **row
            )
        )

    lines.extend(["", "## Topology Patterns", ""])
    for topology in TOPOLOGY_ORDER:
        group = [row for row in environment_rows if row["topology"] == topology]
        direct_values = list_text(f"{row['direct_percent']:.2f}" for row in group)
        single_values = list_text(f"{row['single_region_percent']:.2f}" for row in group)
        multi_values = list_text(f"{row['multi_region_visibility_percent']:.2f}" for row in group)
        ratio_values = list_text(f"{row['vg_proposed_primary_ratio']:.3f}" for row in group)
        lines.append(f"### {TOPOLOGY_DISPLAY[topology]}")
        lines.append("")
        lines.append(f"- Branch pattern: {branch_pattern_status(environment_rows, topology)}.")
        lines.append(f"- Direct % by instance: `{direct_values}`.")
        lines.append(f"- Single-region % by instance: `{single_values}`.")
        lines.append(f"- Multi-region % by instance: `{multi_values}`.")
        lines.append(f"- Primary VG/Proposed ratios by instance: `{ratio_values}`.")
        lines.append("")

    lines.extend(
        [
            "## Asymmetric Crossover",
            "",
            f"- VG faster than Proposed instances: `{list_text(asym_groups['vg_faster_than_proposed']['instances'])}`.",
            f"- Proposed faster than or equal to VG instances: `{list_text(asym_groups['proposed_faster_than_or_equal_vg']['instances'])}`.",
            f"- Mean multi-region %, VG-faster group: `{asym_groups['vg_faster_than_proposed']['mean_multi_region_percent']}`.",
            f"- Mean multi-region %, Proposed-faster group: `{asym_groups['proposed_faster_than_or_equal_vg']['mean_multi_region_percent']}`.",
            f"- Mean blocking checks, VG-faster group: `{asym_groups['vg_faster_than_proposed']['mean_blocking_checks']}`.",
            f"- Mean blocking checks, Proposed-faster group: `{asym_groups['proposed_faster_than_or_equal_vg']['mean_blocking_checks']}`.",
            "",
            "## Exploratory Associations",
            "",
            "These are descriptive associations across 15 environments only; no significance tests were run.",
            "",
            "| metric | n | Pearson | Spearman |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in associations:
        pearson_value = "NA" if row["pearson"] is None else f"{row['pearson']:.6f}"
        spearman_value = "NA" if row["spearman"] is None else f"{row['spearman']:.6f}"
        lines.append(f"| {row['metric_label']} | {row['n']} | {pearson_value} | {spearman_value} |")

    lines.extend(
        [
            "",
            "## Part I Diagnostic Context",
            "",
            "| topology | direct % | single-region % | multi-region % | failed | diagnostic s | block checks | reblocks |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in part1_rows:
        lines.append(
            "| {topology_display} | {direct_percent:.2f} | {single_region_percent:.2f} | {multi_region_visibility_percent:.2f} | {failed_count} | {diagnostic_matrix_time_sec} | {total_blocking_checks} | {total_reblocking_checks} |".format(
                **row
            )
        )

    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Primary executions added: `0`",
            "- Proposed diagnostic executions: `15`",
            "- Sanity repetitions: `0`",
            "- `proposed_parallel` executions: `0`",
            "- Dataset files modified: `NO`",
            "- Part I files modified: `NO`",
            "",
            "## Unavailable Counters",
            "",
            "- `visibility_edge_clearance_checks` and `tangent_exit_check_count` are recorded as unavailable by the validated wrapper because collecting them would require algorithm changes.",
            "",
        ]
    )
    write_text_lf(path, "\n".join(lines))


def write_analysis_outputs(
    *,
    run_id: str,
    campaign_id: str,
    run_dir: Path,
    environment_rows: List[Dict[str, Any]],
    pair_rows: List[Dict[str, Any]],
    manifest_csv: Path,
    manifest_json: Path,
) -> Dict[str, str]:
    topology_rows = topology_summary_rows(environment_rows)
    crossover = crossover_rows(environment_rows)
    associations = association_rows(environment_rows)
    part1_rows = load_part1_context()

    env_csv = ANALYSIS_ROOT / "part2_proposed_diagnostic_environment_summary.csv"
    env_json = ANALYSIS_ROOT / "part2_proposed_diagnostic_environment_summary.json"
    topology_csv = ANALYSIS_ROOT / "part2_proposed_diagnostic_topology_summary.csv"
    topology_json = ANALYSIS_ROOT / "part2_proposed_diagnostic_topology_summary.json"
    crossover_csv = ANALYSIS_ROOT / "part2_proposed_diagnostic_crossover_analysis.csv"
    crossover_json = ANALYSIS_ROOT / "part2_proposed_diagnostic_crossover_analysis.json"
    association_csv = ANALYSIS_ROOT / "part2_proposed_diagnostic_exploratory_associations.csv"
    association_json = ANALYSIS_ROOT / "part2_proposed_diagnostic_exploratory_associations.json"
    part1_csv = ANALYSIS_ROOT / "part2_proposed_diagnostic_part1_context.csv"
    part1_json = ANALYSIS_ROOT / "part2_proposed_diagnostic_part1_context.json"
    markdown = ANALYSIS_ROOT / "PART2_PROPOSED_DIAGNOSTIC_SUMMARY.md"

    write_csv(env_csv, environment_rows, ENVIRONMENT_SUMMARY_FIELDS)
    write_json(
        env_json,
        {
            "schema": "nfz_part2_proposed_diagnostic_environment_summary_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "rows": environment_rows,
        },
    )
    write_csv(topology_csv, topology_rows, list(topology_rows[0]))
    write_json(
        topology_json,
        {
            "schema": "nfz_part2_proposed_diagnostic_topology_summary_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "rows": topology_rows,
        },
    )
    write_csv(crossover_csv, crossover, CROSSOVER_FIELDS)
    write_json(
        crossover_json,
        {
            "schema": "nfz_part2_proposed_diagnostic_crossover_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "rows": crossover,
        },
    )
    write_csv(association_csv, associations, list(associations[0]))
    write_json(
        association_json,
        {
            "schema": "nfz_part2_proposed_diagnostic_exploratory_associations_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "rows": associations,
        },
    )
    write_csv(part1_csv, part1_rows, list(part1_rows[0]))
    write_json(
        part1_json,
        {
            "schema": "nfz_part2_proposed_diagnostic_part1_context_v1",
            "source_pair_csv": format_path(PART1_DIAGNOSTIC_PAIR_CSV),
            "source_summary_json": format_path(PART1_DIAGNOSTIC_SUMMARY_JSON),
            "rows": part1_rows,
        },
    )
    write_markdown_summary(
        path=markdown,
        run_id=run_id,
        campaign_id=campaign_id,
        run_dir=run_dir,
        environment_rows=environment_rows,
        topology_rows=topology_rows,
        crossover=crossover,
        associations=associations,
        part1_rows=part1_rows,
        manifest_csv=manifest_csv,
        manifest_json=manifest_json,
    )
    return {
        "environment_summary_csv": format_path(env_csv),
        "environment_summary_json": format_path(env_json),
        "topology_summary_csv": format_path(topology_csv),
        "topology_summary_json": format_path(topology_json),
        "crossover_analysis_csv": format_path(crossover_csv),
        "crossover_analysis_json": format_path(crossover_json),
        "exploratory_associations_csv": format_path(association_csv),
        "exploratory_associations_json": format_path(association_json),
        "part1_context_csv": format_path(part1_csv),
        "part1_context_json": format_path(part1_json),
        "markdown_summary": format_path(markdown),
        "pair_diagnostics_csv": format_path(run_dir / f"{campaign_id}_pair_records.csv"),
        "pair_diagnostics_jsonl": format_path(run_dir / f"{campaign_id}_pair_records.jsonl"),
    }


def validate_completion(
    *,
    conditions: Sequence[Condition],
    environment_rows: Sequence[Dict[str, Any]],
    pair_rows: Sequence[Dict[str, Any]],
    functional_equivalence_rows: Sequence[Dict[str, Any]],
) -> None:
    if len(environment_rows) != EXPECTED_ENVIRONMENTS:
        raise RuntimeError(f"Expected {EXPECTED_ENVIRONMENTS} environment rows")
    if len(pair_rows) != EXPECTED_PAIR_RECORDS:
        raise RuntimeError(f"Expected {EXPECTED_PAIR_RECORDS} pair records, found {len(pair_rows)}")
    if any(not row["passed"] for row in functional_equivalence_rows):
        raise RuntimeError("Functional equivalence did not pass for every environment")
    condition_ids = {condition.environment_id for condition in conditions}
    if {row["environment_id"] for row in environment_rows} != condition_ids:
        raise RuntimeError("Environment summary set does not match conditions")
    pair_keys = set()
    for row in pair_rows:
        if row["branch_class"] not in BRANCH_CLASSES:
            raise RuntimeError(f"Unexpected branch class: {row['branch_class']}")
        key = (row["environment_id"], row["source_node"], row["destination_node"])
        if key in pair_keys:
            raise RuntimeError(f"Duplicate pair record: {key}")
        pair_keys.add(key)
    for condition in conditions:
        count = sum(1 for row in pair_rows if row["environment_id"] == condition.environment_id)
        if count != EXPECTED_DIRECTED_PAIRS_PER_ENVIRONMENT:
            raise RuntimeError(f"{condition.environment_id} has {count} pair records")


def write_manifest(
    *,
    run_id: str,
    campaign_id: str,
    run_dir: Path,
    manifest_rows: List[Dict[str, Any]],
    environment_info: Dict[str, Any],
    dataset_manifest_hash: str,
) -> Tuple[Path, Path]:
    manifest_csv = MANIFEST_ROOT / "part2_proposed_diagnostic_manifest.csv"
    manifest_json = MANIFEST_ROOT / "part2_proposed_diagnostic_manifest.json"
    write_csv(manifest_csv, manifest_rows, MANIFEST_FIELDS)
    write_json(
        manifest_json,
        {
            "schema": "nfz_part2_proposed_diagnostic_manifest_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "run_directory": format_path(run_dir),
            "created_at": now_iso(),
            "diagnostic_environment_count": len(manifest_rows),
            "expected_pair_records": EXPECTED_PAIR_RECORDS,
            "dataset_manifest": format_path(primary.DATASET_MANIFEST_PATH),
            "dataset_manifest_hash": dataset_manifest_hash,
            "environment_info": environment_info,
            "rows": manifest_rows,
        },
    )
    return manifest_csv, manifest_json


def normalize_text_tree(root: Path) -> None:
    for suffix in (".csv", ".json", ".jsonl", ".md", ".log", ".txt"):
        for path in root.rglob(f"*{suffix}"):
            text = path.read_text(encoding="utf-8")
            path.write_text(text, encoding="utf-8", newline="\n")


def log_message(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{now_iso()} {message}\n")


def run_campaign() -> int:
    preconditions = verify_preconditions()
    dataset_rows = load_and_verify_dataset_rows()
    conditions = build_conditions(dataset_rows)
    proposed_records = load_primary_records(REFERENCE_METHOD)
    vg_records = load_primary_records(VISIBILITY_GRAPH_METHOD)
    validate_primary_record_alignment(conditions, proposed_records, vg_records)
    dataset_manifest_hash = sha256(primary.DATASET_MANIFEST_PATH)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_id = f"run_01_{timestamp}"
    campaign_id = f"part2_proposed_diagnostic_{timestamp}"
    run_dir = RESULTS_ROOT / run_id
    if run_dir.exists():
        raise FileExistsError(run_dir)

    records_dir = run_dir / "records"
    pairs_dir = run_dir / "pairs"
    summaries_dir = run_dir / "summaries"
    missions_dir = run_dir / "outputs" / METHOD / "missions"
    logs_dir = run_dir / "logs"
    log_path = logs_dir / f"{campaign_id}.log"
    progress_path = run_dir / "campaign_status.json"
    pair_csv = run_dir / f"{campaign_id}_pair_records.csv"
    pair_jsonl = run_dir / f"{campaign_id}_pair_records.jsonl"
    equivalence_path = run_dir / "functional_equivalence.json"

    run_dir.mkdir(parents=True, exist_ok=False)
    write_json(
        run_dir / "execution_order.json",
        {
            "schema": "nfz_part2_proposed_diagnostic_execution_order_v1",
            "order": "for each topology, for each instance i01-i05, run Proposed diagnostic mode",
            "method": METHOD,
            "topologies": TOPOLOGY_ORDER,
            "conditions": [
                {
                    "execution_index": condition.execution_index,
                    "environment_id": condition.environment_id,
                    "topology": condition.topology,
                    "instance_id": condition.instance_id,
                    "seed": condition.seed,
                    "source_mission_file": format_path(condition.source_path),
                }
                for condition in conditions
            ],
        },
    )
    write_json(
        run_dir / "environment_provenance.json",
        {
            "schema": "nfz_part2_proposed_diagnostic_environment_provenance_v1",
            "branch": preconditions["branch"],
            "git_commit": preconditions["git_commit"],
            "primary_results_commit": PRIMARY_RESULTS_COMMIT,
            "part2_infrastructure_commit": PART2_INFRASTRUCTURE_COMMIT,
            "part1_experiment_commit": PART1_EXPERIMENT_COMMIT,
            "dataset_generator_commit": DATASET_GENERATOR_COMMIT,
            "dataset_manifest": format_path(primary.DATASET_MANIFEST_PATH),
            "dataset_manifest_hash": dataset_manifest_hash,
            "environment_info": preconditions["environment_info"],
            "diagnostic_method": METHOD,
            "primary_executions_added": 0,
            "sanity_repetitions": 0,
            "proposed_parallel_executions": 0,
        },
    )

    completed_environment_rows: List[Dict[str, Any]] = []
    all_pair_rows: List[Dict[str, Any]] = []
    equivalence_rows: List[Dict[str, Any]] = []
    manifest_rows: List[Dict[str, Any]] = []
    infrastructure_failures: List[Dict[str, Any]] = []
    functional_discrepancies: List[Dict[str, Any]] = []

    write_progress(
        path=progress_path,
        run_id=run_id,
        campaign_id=campaign_id,
        conditions=conditions,
        completed=completed_environment_rows,
        infrastructure_failures=infrastructure_failures,
        functional_discrepancies=functional_discrepancies,
        status="running",
    )
    log_message(log_path, f"START campaign={campaign_id} expected_environments={len(conditions)}")

    for condition in conditions:
        log_message(
            log_path,
            f"START {condition.execution_index:02d}/{len(conditions)} {condition.environment_id}",
        )
        write_progress(
            path=progress_path,
            run_id=run_id,
            campaign_id=campaign_id,
            conditions=conditions,
            completed=completed_environment_rows,
            infrastructure_failures=infrastructure_failures,
            functional_discrepancies=functional_discrepancies,
            status="running",
            current=condition,
        )
        try:
            with log_path.open("a", encoding="utf-8", newline="\n") as log_handle:
                with contextlib.redirect_stdout(log_handle), contextlib.redirect_stderr(log_handle):
                    diagnostic = run_diagnostics_for_environment(
                        environment_path=condition.source_path,
                        environment_id=condition.environment_id,
                        topology=condition.topology,
                        instance_id=condition.instance_id,
                        seed=condition.seed,
                    )
                    solution, solver_env, solver_drone_configs = solve_with_diagnostic_matrix(
                        diagnostic.native_env,
                        diagnostic.matrix_data,
                    )

            reference_record = proposed_records[condition.environment_id]
            vg_record = vg_records[condition.environment_id]
            reference_doc = load_reference_mission(reference_record)
            equivalence = functional_equivalence(
                condition=condition,
                matrix_data=diagnostic.matrix_data,
                solution=solution,
                solver_env=solver_env,
                solver_drone_configs=solver_drone_configs,
                primary_record=reference_record,
                reference_doc=reference_doc,
            )
            equivalence_rows.append(equivalence)
            write_json(equivalence_path, {"schema": "nfz_part2_proposed_functional_equivalence_v1", "rows": equivalence_rows})
            if not equivalence["passed"]:
                functional_discrepancies.append(equivalence)
                write_progress(
                    path=progress_path,
                    run_id=run_id,
                    campaign_id=campaign_id,
                    conditions=conditions,
                    completed=completed_environment_rows,
                    infrastructure_failures=infrastructure_failures,
                    functional_discrepancies=functional_discrepancies,
                    status="failed_functional_equivalence",
                    current=condition,
                )
                raise RuntimeError(f"Functional equivalence failed for {condition.environment_id}: {equivalence}")

            validate_pair_rows(condition, diagnostic.pair_rows)
            mission_doc = build_mission_document(
                diagnostic.native_env,
                solution=solution,
                env=solver_env,
                drone_configs=solver_drone_configs,
            )
            mission_path = missions_dir / mission_filename(
                source_id=condition.environment_id,
                matrix_method=METHOD,
                segment_count=diagnostic.native_env.segment_count,
            )
            write_json(mission_path, mission_doc)

            env_summary = summarize_environment(
                condition=condition,
                diagnostic_summary=diagnostic.environment_summary,
                pair_rows=diagnostic.pair_rows,
                primary_record=reference_record,
                vg_record=vg_record,
                equivalence=equivalence,
                mission_path=mission_path,
            )
            record = {
                "schema": "nfz_part2_proposed_diagnostic_environment_record_v1",
                "run": run_id,
                "campaign_id": campaign_id,
                "condition": {
                    "execution_index": condition.execution_index,
                    "environment_id": condition.environment_id,
                    "topology": condition.topology,
                    "instance_id": condition.instance_id,
                    "seed": condition.seed,
                    "source_mission_file": format_path(condition.source_path),
                    "source_dataset_hash": condition.source_dataset_hash,
                },
                "environment_summary": env_summary,
                "functional_equivalence": equivalence,
                "counter_availability": diagnostic.environment_summary.get("counter_availability", {}),
            }
            record_path = records_dir / f"{condition.environment_id}__{METHOD}.json"
            pair_path = pairs_dir / f"{condition.environment_id}__pair_diagnostics.json"
            summary_path = summaries_dir / f"{condition.environment_id}__environment_summary.json"
            write_json(record_path, record)
            write_json(pair_path, diagnostic.pair_rows)
            write_json(summary_path, env_summary)

            if not pair_csv.exists():
                write_csv(pair_csv, [], PAIR_FIELDS)
            with pair_csv.open("a", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=PAIR_FIELDS,
                    extrasaction="ignore",
                    lineterminator="\n",
                )
                writer.writerows(diagnostic.pair_rows)
            for row in diagnostic.pair_rows:
                append_jsonl(pair_jsonl, row)

            completed_environment_rows.append(env_summary)
            all_pair_rows.extend(diagnostic.pair_rows)
            manifest_rows.append(
                {
                    "environment_id": condition.environment_id,
                    "topology": condition.topology,
                    "instance_id": condition.instance_id,
                    "seed": condition.seed,
                    "method": METHOD,
                    "result_path": format_path(record_path),
                    "result_sha256": sha256(record_path),
                    "pair_diagnostics_path": format_path(pair_path),
                    "pair_diagnostics_sha256": sha256(pair_path),
                    "environment_summary_path": format_path(summary_path),
                    "environment_summary_sha256": sha256(summary_path),
                    "output_mission_file": format_path(mission_path),
                    "output_mission_sha256": sha256(mission_path),
                    "execution_status": "success",
                    "functional_equivalence_passed": True,
                    "directed_pair_count": env_summary["directed_pair_count"],
                    "failed_pair_count": env_summary["failed_count"],
                    "direct_count": env_summary["direct_count"],
                    "single_region_count": env_summary["single_region_count"],
                    "multi_region_visibility_count": env_summary["multi_region_visibility_count"],
                    "primary_proposed_matrix_time_sec": env_summary["primary_proposed_matrix_time_sec"],
                    "diagnostic_matrix_time_sec": env_summary["diagnostic_matrix_time_sec"],
                    "diagnostic_overhead_percent": env_summary["diagnostic_overhead_percent"],
                    "matrix_distance_max_delta": equivalence["matrix_comparison"]["max_matrix_delta"],
                    "path_coordinate_max_delta": equivalence["path_comparison"]["max_path_delta"],
                    "route_distance_delta": equivalence["route_comparison"]["route_distance_delta"],
                    "git_commit": preconditions["git_commit"],
                    "primary_results_commit": PRIMARY_RESULTS_COMMIT,
                    "source_dataset_hash": condition.source_dataset_hash,
                }
            )
            log_message(
                log_path,
                f"END {condition.environment_id} pairs={env_summary['directed_pair_count']} "
                f"direct={env_summary['direct_count']} single={env_summary['single_region_count']} "
                f"multi={env_summary['multi_region_visibility_count']} "
                f"failed={env_summary['failed_count']} diag={env_summary['diagnostic_matrix_time_sec']}",
            )
            write_progress(
                path=progress_path,
                run_id=run_id,
                campaign_id=campaign_id,
                conditions=conditions,
                completed=completed_environment_rows,
                infrastructure_failures=infrastructure_failures,
                functional_discrepancies=functional_discrepancies,
                status="running",
            )
        except Exception as exc:
            if functional_discrepancies:
                raise
            failure = {
                "environment_id": condition.environment_id,
                "topology": condition.topology,
                "instance_id": condition.instance_id,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
                "time": now_iso(),
            }
            infrastructure_failures.append(failure)
            write_progress(
                path=progress_path,
                run_id=run_id,
                campaign_id=campaign_id,
                conditions=conditions,
                completed=completed_environment_rows,
                infrastructure_failures=infrastructure_failures,
                functional_discrepancies=functional_discrepancies,
                status="failed_infrastructure",
                current=condition,
            )
            log_message(log_path, f"INFRASTRUCTURE_ERROR {condition.environment_id} {failure['error']}")
            raise

    validate_completion(
        conditions=conditions,
        environment_rows=completed_environment_rows,
        pair_rows=all_pair_rows,
        functional_equivalence_rows=equivalence_rows,
    )

    manifest_csv, manifest_json = write_manifest(
        run_id=run_id,
        campaign_id=campaign_id,
        run_dir=run_dir,
        manifest_rows=manifest_rows,
        environment_info=preconditions["environment_info"],
        dataset_manifest_hash=dataset_manifest_hash,
    )
    analysis_artifacts = write_analysis_outputs(
        run_id=run_id,
        campaign_id=campaign_id,
        run_dir=run_dir,
        environment_rows=completed_environment_rows,
        pair_rows=all_pair_rows,
        manifest_csv=manifest_csv,
        manifest_json=manifest_json,
    )
    write_json(
        run_dir / "campaign_artifacts.json",
        {
            "schema": "nfz_part2_proposed_diagnostic_campaign_artifacts_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "run_directory": format_path(run_dir),
            "progress_manifest": format_path(progress_path),
            "execution_order": format_path(run_dir / "execution_order.json"),
            "functional_equivalence": format_path(equivalence_path),
            "pair_diagnostics_csv": format_path(pair_csv),
            "pair_diagnostics_jsonl": format_path(pair_jsonl),
            "diagnostic_manifest_csv": format_path(manifest_csv),
            "diagnostic_manifest_json": format_path(manifest_json),
            "analysis_artifacts": analysis_artifacts,
        },
    )
    write_progress(
        path=progress_path,
        run_id=run_id,
        campaign_id=campaign_id,
        conditions=conditions,
        completed=completed_environment_rows,
        infrastructure_failures=infrastructure_failures,
        functional_discrepancies=functional_discrepancies,
        status="complete",
    )
    normalize_text_tree(run_dir)
    log_message(log_path, f"COMPLETE completed={len(completed_environment_rows)} pair_records={len(all_pair_rows)}")

    print(f"run_id={run_id}")
    print(f"campaign_id={campaign_id}")
    print(f"run_dir={run_dir}")
    print(f"diagnostic_environments={len(completed_environment_rows)}")
    print(f"pair_records={len(all_pair_rows)}")
    print(f"failed_pairs={sum(int(row['failed_count']) for row in completed_environment_rows)}")
    print(f"manifest_csv={manifest_csv}")
    print(f"manifest_json={manifest_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_campaign())
