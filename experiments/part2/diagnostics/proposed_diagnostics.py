"""Part II wrapper for non-invasive Proposed directed-pair diagnostics."""

from __future__ import annotations

import copy
import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENTS_ROOT = REPO_ROOT / "experiments"
LEGACY_DIAGNOSTIC_CODE = (
    EXPERIMENTS_ROOT / "diagnostics" / "proposed_branching" / "code"
)

for path in (REPO_ROOT, EXPERIMENTS_ROOT, LEGACY_DIAGNOSTIC_CODE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from benchmark.matrix_builders import configure_planner_imports
from benchmark.native_io import NativeEnvironment, load_native_environment
from proposed_instrumented import calculate_instrumented_proposed_matrix


BRANCH_CLASSES = ("direct", "single_region", "multi_region_visibility", "failed")
UNAVAILABLE_COUNTERS = (
    "tangent_exit_check_count",
    "visibility_edge_clearance_checks",
)


@dataclass(frozen=True)
class Part2DiagnosticResult:
    native_env: NativeEnvironment
    matrix_data: Dict[str, Any]
    pair_rows: List[Dict[str, Any]]
    environment_summary: Dict[str, Any]
    diagnostic_runtime_sec: float


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def branch_class(raw_pair: Dict[str, Any]) -> str:
    method = str(raw_pair.get("method") or "")
    available = bool(raw_pair.get("available"))
    if not available or method.startswith(("INVALID", "no_path_found", "error")):
        return "failed"
    if method.startswith("visibility-graph"):
        return "multi_region_visibility"
    if method.startswith("direct"):
        return "direct"
    return "single_region"


def distinct_wrapped_blockers(blocking_sequence: str) -> int:
    labels = {
        value
        for value in blocking_sequence.split(";")
        if value and value.startswith("H")
    }
    return len(labels)


def geometry_context(env: Dict[str, Any]) -> Dict[str, Any]:
    configure_planner_imports(REPO_ROOT)
    from path_planning_core import sam_wrapping
    from server.solver import sam_distance_matrix
    from server.solver.projection import _project_env_to_local_km

    projected_env, _, _ = _project_env_to_local_km(copy.deepcopy(env))
    normalized_sams = sam_distance_matrix._calculator._normalize_sams(
        projected_env.get("sams", [])
    )
    sams_for_wrapping = [
        {
            "x": sam["pos"][0],
            "y": sam["pos"][1],
            "range": sam["range"],
            "id": sam.get("id"),
        }
        for sam in normalized_sams
    ]
    clusters = sam_wrapping._cluster_overlapping_sams(sams_for_wrapping)
    wrapped_polygons, _ = sam_wrapping.wrap_sams(sams_for_wrapping)
    return {
        "native_nfz_count": len(normalized_sams),
        "cluster_count": len(clusters),
        "singleton_region_count": sum(1 for cluster in clusters if len(cluster) == 1),
        "multi_nfz_cluster_count": sum(1 for cluster in clusters if len(cluster) > 1),
        "wrapped_region_count": len(wrapped_polygons),
    }


def normalize_pair_row(
    *,
    raw_pair: Dict[str, Any],
    environment_id: str,
    topology: str,
    instance_id: str,
    seed: Optional[int],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    raw_method = str(raw_pair.get("method") or "")
    blocking_sequence = str(raw_pair.get("blocking_sequence") or "")
    return {
        "environment_id": environment_id,
        "topology": topology,
        "instance_id": instance_id,
        "seed": seed,
        "source_node": str(raw_pair.get("source")),
        "destination_node": str(raw_pair.get("destination")),
        "branch_class": branch_class(raw_pair),
        "pair_time_sec": _as_float(raw_pair.get("pair_time_seconds")),
        "path_distance_km": _as_float(raw_pair.get("final_pair_distance")),
        "feasible": bool(raw_pair.get("available")),
        "raw_method": raw_method,
        "direct_path_blocked": bool(raw_pair.get("direct_path_blocked")),
        "pair_index": _as_int(raw_pair.get("pair_index")),
        "node_count": _as_int(raw_pair.get("node_count")),
        "target_count": _as_int(raw_pair.get("target_count")),
        "native_nfz_count": context["native_nfz_count"],
        "cluster_count": context["cluster_count"],
        "singleton_region_count": context["singleton_region_count"],
        "multi_nfz_cluster_count": context["multi_nfz_cluster_count"],
        "wrapped_region_count": context["wrapped_region_count"],
        "relevant_blocking_region_count": distinct_wrapped_blockers(blocking_sequence),
        "tangent_call_count": _as_int(raw_pair.get("tangent_calls")),
        "tangent_exit_check_count": None,
        "visibility_edge_clearance_checks": None,
        "blocking_checks": _as_int(raw_pair.get("blocked_checks")),
        "reblocking_checks": _as_int(raw_pair.get("reblocking_events")),
        "blocking_sequence": blocking_sequence,
    }


def summarize_pair_rows(
    *,
    environment_id: str,
    topology: str,
    instance_id: str,
    seed: Optional[int],
    pair_rows: List[Dict[str, Any]],
    context: Dict[str, Any],
    diagnostic_runtime_sec: float,
) -> Dict[str, Any]:
    total_pairs = len(pair_rows)
    counts = {branch: 0 for branch in BRANCH_CLASSES}
    aggregate_time = {branch: 0.0 for branch in BRANCH_CLASSES}
    pair_times: Dict[str, List[float]] = {branch: [] for branch in BRANCH_CLASSES}
    for row in pair_rows:
        branch = row["branch_class"]
        pair_time = float(row["pair_time_sec"] or 0.0)
        counts[branch] += 1
        aggregate_time[branch] += pair_time
        pair_times[branch].append(pair_time)

    percentages = {
        branch: (counts[branch] / total_pairs if total_pairs else 0.0)
        for branch in BRANCH_CLASSES
    }
    time_stats = {}
    for branch, values in pair_times.items():
        time_stats[branch] = {
            "count": len(values),
            "mean_sec": statistics.fmean(values) if values else None,
            "median_sec": statistics.median(values) if values else None,
            "min_sec": min(values) if values else None,
            "max_sec": max(values) if values else None,
        }

    return {
        "schema": "nfz_part2_proposed_environment_summary_v1",
        "environment_id": environment_id,
        "topology": topology,
        "instance_id": instance_id,
        "seed": seed,
        "target_count": pair_rows[0]["target_count"] if pair_rows else None,
        "node_count": pair_rows[0]["node_count"] if pair_rows else None,
        "directed_pair_count": total_pairs,
        "branch_counts": counts,
        "branch_percentages": percentages,
        "branch_time_aggregate_sec": aggregate_time,
        "branch_time_stats": time_stats,
        "diagnostic_runtime_sec": diagnostic_runtime_sec,
        "counter_availability": {
            "available": [
                "native_nfz_count",
                "cluster_count",
                "singleton_region_count",
                "multi_nfz_cluster_count",
                "wrapped_region_count",
                "relevant_blocking_region_count",
                "tangent_call_count",
                "blocking_checks",
                "reblocking_checks",
            ],
            "unavailable_without_algorithm_changes": list(UNAVAILABLE_COUNTERS),
        },
        **context,
    }


def run_diagnostics_for_environment(
    *,
    environment_path: Path,
    environment_id: Optional[str] = None,
    topology: str,
    instance_id: str,
    seed: Optional[int],
) -> Part2DiagnosticResult:
    native_env = load_native_environment(environment_path)
    env_id = environment_id or native_env.source_id
    context = geometry_context(native_env.env)
    start = time.perf_counter()
    instrumented = calculate_instrumented_proposed_matrix(
        native_env.env,
        environment=env_id,
        topology=topology,
        target_count=native_env.target_count,
        buffer=0.0,
    )
    diagnostic_runtime_sec = time.perf_counter() - start
    matrix_data = dict(instrumented)
    raw_pair_rows = matrix_data.pop("diagnostic_pair_rows")
    matrix_data.pop("diagnostic_summary", None)
    pair_rows = [
        normalize_pair_row(
            raw_pair=row,
            environment_id=env_id,
            topology=topology,
            instance_id=instance_id,
            seed=seed,
            context=context,
        )
        for row in raw_pair_rows
    ]
    summary = summarize_pair_rows(
        environment_id=env_id,
        topology=topology,
        instance_id=instance_id,
        seed=seed,
        pair_rows=pair_rows,
        context=context,
        diagnostic_runtime_sec=diagnostic_runtime_sec,
    )
    return Part2DiagnosticResult(
        native_env=native_env,
        matrix_data=matrix_data,
        pair_rows=pair_rows,
        environment_summary=summary,
        diagnostic_runtime_sec=diagnostic_runtime_sec,
    )


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def iter_csv_rows(rows: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for row in rows:
        yield dict(row)
