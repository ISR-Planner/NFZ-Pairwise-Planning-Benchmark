"""Experiment harness for one Mission matrix-builder benchmark run."""

from __future__ import annotations

import json
import copy
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .matrix_builders import DEFAULT_PLANNER_ROOT, get_builder
from .native_io import (
    build_mission_document,
    load_native_environment,
    mission_filename,
    write_json,
)
from .planner_bridge import configure_stdio, prebuilt_matrix_cache, prepare_solver


@dataclass(frozen=True)
class BenchmarkRunResult:
    source_environment: str
    matrix_method: str
    target_count: int
    matrix_build_time_seconds: Optional[float]
    solver_time_seconds: Optional[float]
    solver_completed: bool
    mission_feasible: bool
    mission_success: bool
    targets_serviced: int
    points: int
    route_distance: float
    output_mission_json: Optional[str]
    error: Optional[str]
    failure_reason: Optional[str]
    summary_jsonl: str


def _append_summary(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def _single_drone_configs(drone_configs: Dict[str, Any]) -> Dict[str, Any]:
    configs = copy.deepcopy(drone_configs)
    if "1" not in configs:
        raise ValueError("Benchmark requires D1 drone config")

    for drone_id, cfg in configs.items():
        if isinstance(cfg, dict):
            cfg["enabled"] = str(drone_id) == "1"

    for drone_id in ("2", "3", "4", "5"):
        cfg = configs.setdefault(drone_id, {})
        if isinstance(cfg, dict):
            cfg["enabled"] = False

    return configs


def _mission_status(
    *,
    solution: Dict[str, Any],
    env: Dict[str, Any],
    drone_configs: Dict[str, Any],
    matrix_data: Dict[str, Any],
) -> Dict[str, Any]:
    target_ids = {str(t.get("id")) for t in env.get("targets", [])}
    expected_targets = len(target_ids)
    routes = solution.get("routes", {}) if isinstance(solution, dict) else {}

    serviced = {
        str(node)
        for route_data in routes.values()
        for node in route_data.get("route", [])
        if str(node) in target_ids
    }
    points = sum(int(route_data.get("points", 0) or 0) for route_data in routes.values())
    route_distance = sum(
        float(route_data.get("distance", 0.0) or 0.0)
        for route_data in routes.values()
    )

    targets_serviced = len(serviced)
    mission_feasible = targets_serviced > 0
    mission_success = mission_feasible and targets_serviced == expected_targets

    failure_reason = None
    if not mission_feasible:
        if _airport_disconnected_from_targets(
            matrix_data=matrix_data,
            env=env,
            drone_configs=drone_configs,
        ):
            failure_reason = "airport disconnected from target graph"
        elif expected_targets > 0:
            failure_reason = "no benchmark targets serviced"
        else:
            failure_reason = "no benchmark targets configured"
    elif not mission_success:
        failure_reason = f"serviced {targets_serviced}/{expected_targets} benchmark targets"

    return {
        "mission_feasible": mission_feasible,
        "mission_success": mission_success,
        "targets_serviced": targets_serviced,
        "targets_expected": expected_targets,
        "points": points,
        "route_distance": route_distance,
        "failure_reason": failure_reason,
    }


def _airport_disconnected_from_targets(
    *,
    matrix_data: Dict[str, Any],
    env: Dict[str, Any],
    drone_configs: Dict[str, Any],
) -> bool:
    labels = [str(label) for label in matrix_data.get("labels", [])]
    matrix = matrix_data.get("matrix", [])
    target_ids = {str(t.get("id")) for t in env.get("targets", [])}
    start_id = str((drone_configs.get("1") or {}).get("start_airport") or "")
    if not start_id or start_id not in labels or not target_ids:
        return False

    unavailable_cost = float(
        (matrix_data.get("routing_model") or {}).get(
            "unavailable_cost",
            matrix_data.get("collision_rejection", {}).get("unavailable_cost", 99999.0),
        )
    )
    index = {label: i for i, label in enumerate(labels)}
    seen = {start_id}
    queue = [start_id]
    while queue:
        current = queue.pop(0)
        row = matrix[index[current]]
        for neighbor, j in index.items():
            if neighbor in seen:
                continue
            if float(row[j]) < unavailable_cost:
                seen.add(neighbor)
                queue.append(neighbor)

    return not any(target_id in seen for target_id in target_ids)


def run_one(
    *,
    environment_path: Path,
    matrix_method: str = "proposed",
    output_dir: Optional[Path] = None,
    planner_root: Path = DEFAULT_PLANNER_ROOT,
    allocation_strategy: str = "geographic",
    post_optimize: bool = False,
) -> BenchmarkRunResult:
    configure_stdio()

    native_env = load_native_environment(environment_path)
    output_dir = output_dir or Path("methods") / matrix_method / "outputs"
    builder = get_builder(matrix_method, planner_root=planner_root)
    prepare = getattr(builder, "prepare", None)
    if callable(prepare):
        prepare()
    prepare_solver(planner_root)

    from server.solver.solver_bridge import solve_mission_with_allocation

    summary_path = output_dir / "benchmark_summary.jsonl"
    run_started_at = datetime.now(timezone.utc).isoformat()
    mission_path: Optional[Path] = None
    matrix_time: Optional[float] = None
    solver_time: Optional[float] = None
    solver_completed = False
    mission_feasible = False
    mission_success = False
    targets_serviced = 0
    targets_expected = native_env.target_count
    points = 0
    route_distance = 0.0
    failure_reason: Optional[str] = None
    error: Optional[str] = None

    try:
        matrix_start = time.perf_counter()
        matrix_build = builder.build(native_env.env)
        matrix_time = time.perf_counter() - matrix_start

        solver_env = copy.deepcopy(native_env.env)
        solver_drone_configs = _single_drone_configs(native_env.drone_configs)
        solver_env["drone_configs"] = copy.deepcopy(solver_drone_configs)
        with prebuilt_matrix_cache(solver_env, matrix_build.data):
            solver_start = time.perf_counter()
            solution = solve_mission_with_allocation(
                env=solver_env,
                drone_configs=solver_drone_configs,
                allocation_strategy=allocation_strategy,
                use_sam_aware_distances=True,
                post_optimize=post_optimize,
            )
            solver_time = time.perf_counter() - solver_start
            solver_completed = True

        status = _mission_status(
            solution=solution,
            env=solver_env,
            drone_configs=solver_drone_configs,
            matrix_data=matrix_build.data,
        )
        mission_feasible = bool(status["mission_feasible"])
        mission_success = bool(status["mission_success"])
        targets_serviced = int(status["targets_serviced"])
        targets_expected = int(status["targets_expected"])
        points = int(status["points"])
        route_distance = float(status["route_distance"])
        failure_reason = status["failure_reason"]

        mission_doc = build_mission_document(
            native_env,
            solution=solution,
            env=solver_env,
            drone_configs=solver_drone_configs,
        )
        filename = mission_filename(
            source_id=native_env.source_id,
            matrix_method=matrix_build.method,
            segment_count=native_env.segment_count,
        )
        mission_path = output_dir / "missions" / filename
        write_json(mission_path, mission_doc)
    except Exception as exc:  # pragma: no cover - exercised by CLI failure paths
        error = f"{type(exc).__name__}: {exc}"
        failure_reason = error
        trace_path = output_dir / "failures" / f"{native_env.source_id}__{matrix_method}__trace.txt"
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(traceback.format_exc(), encoding="utf-8")

    row: Dict[str, Any] = {
        "run_started_at": run_started_at,
        "source_environment": str(native_env.source_path),
        "source_environment_id": native_env.source_id,
        "matrix_method": matrix_method,
        "target_count": native_env.target_count,
        "matrix_build_time_seconds": matrix_time,
        "solver_time_seconds": solver_time,
        "solver_completed": solver_completed,
        "mission_feasible": mission_feasible,
        "mission_success": mission_success,
        "success": mission_success,
        "targets_serviced": targets_serviced,
        "targets_expected": targets_expected,
        "points": points,
        "route_distance": route_distance,
        "failure_reason": failure_reason,
        "output_mission_json": str(mission_path) if mission_path else None,
        "error": error,
    }
    if "matrix_build" in locals():
        diagnostics = matrix_build.data.get("benchmark_diagnostics")
        if diagnostics:
            row["matrix_diagnostics"] = diagnostics
    _append_summary(summary_path, row)

    return BenchmarkRunResult(
        source_environment=str(native_env.source_path),
        matrix_method=matrix_method,
        target_count=native_env.target_count,
        matrix_build_time_seconds=matrix_time,
        solver_time_seconds=solver_time,
        solver_completed=solver_completed,
        mission_feasible=mission_feasible,
        mission_success=mission_success,
        targets_serviced=targets_serviced,
        points=points,
        route_distance=route_distance,
        output_mission_json=str(mission_path) if mission_path else None,
        error=error,
        failure_reason=failure_reason,
        summary_jsonl=str(summary_path),
    )
