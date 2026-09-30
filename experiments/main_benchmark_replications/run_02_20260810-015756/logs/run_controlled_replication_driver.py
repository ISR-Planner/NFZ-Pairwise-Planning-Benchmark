from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ROOT = Path(r"<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments")
RUN_TIMESTAMP = "20260810-015756"
RUN_ID = "run_02"
RUN_DIR = EXPERIMENT_ROOT / "main_benchmark_replications" / f"{RUN_ID}_{RUN_TIMESTAMP}"
INPUT_DIR = RUN_DIR / "input_snapshot"
RESULTS_DIR = RUN_DIR / "results"
OUTPUTS_DIR = RUN_DIR / "outputs"
LOGS_DIR = RUN_DIR / "logs"

ENVIRONMENTS = [
    "c_trap_001_t04.json",
    "c_trap_001_t08.json",
    "c_trap_001_t12.json",
    "sequential_staggered_blocking_001_t04.json",
    "sequential_staggered_blocking_001_t08.json",
    "sequential_staggered_blocking_001_t12.json",
    "asymmetric_corridor_001_t04.json",
    "asymmetric_corridor_001_t08.json",
    "asymmetric_corridor_001_t12.json",
]

METHODS = [
    "proposed",
    "euclidean",
    "collision_rejection",
    "visibility_graph",
    "grid_astar",
    "appatt_raw",
    "appatt_bspline",
    "tig_raw",
    "tig_bezier",
]

CSV_FIELDS = [
    "run",
    "environment",
    "environment_filename",
    "topology",
    "target_count",
    "method",
    "node_count",
    "directed_pair_count",
    "matrix_time_seconds",
    "solver_time_seconds",
    "solver_completed",
    "mission_feasible",
    "mission_success",
    "targets_serviced",
    "target_count_total",
    "service_fraction",
    "mission_distance",
    "mission_point_count",
    "failure_reason",
    "mission_output_path",
    "active_route_count",
    "route_sequence",
    "mission_trajectory_point_count",
    "matrix_diagnostics_json",
    "error",
    "run_started_at",
    "status",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_status(**updates: Any) -> None:
    path = LOGS_DIR / "run_status.json"
    status: dict[str, Any] = {}
    if path.exists():
        status = json.loads(path.read_text(encoding="utf-8"))
    status.update(updates)
    status["updated_at"] = now_iso()
    path.write_text(json.dumps(status, indent=2, sort_keys=True), encoding="utf-8")


def log(message: str) -> None:
    with (LOGS_DIR / f"main_benchmark_run_02_{RUN_TIMESTAMP}.log").open(
        "a", encoding="utf-8"
    ) as handle:
        handle.write(f"{now_iso()} {message}\n")


def topology_for(environment_filename: str) -> str:
    if environment_filename.startswith("c_trap"):
        return "c_trap"
    if environment_filename.startswith("sequential_staggered_blocking"):
        return "sequential_staggered_blocking"
    if environment_filename.startswith("asymmetric_corridor"):
        return "asymmetric_corridor"
    return "unknown"


def read_last_summary_row(method: str) -> dict[str, Any]:
    summary_path = OUTPUTS_DIR / method / "benchmark_summary.jsonl"
    lines = [line for line in summary_path.read_text(encoding="utf-8").splitlines() if line]
    return json.loads(lines[-1])


def rewrite_last_summary_row(method: str, row: dict[str, Any]) -> None:
    summary_path = OUTPUTS_DIR / method / "benchmark_summary.jsonl"
    lines = [line for line in summary_path.read_text(encoding="utf-8").splitlines() if line]
    rows = [json.loads(line) for line in lines]
    rows[-1] = row
    summary_path.write_text(
        "\n".join(json.dumps(item, sort_keys=True) for item in rows) + "\n",
        encoding="utf-8",
    )


def unique_run2_mission_path(path: Path, environment_id: str, method: str) -> Path:
    marker = f"{environment_id}__{method}__"
    if marker in path.name:
        name = path.name.replace(marker, f"{marker}{RUN_ID}_{RUN_TIMESTAMP}__", 1)
    else:
        name = f"{environment_id}__{method}__{RUN_ID}_{RUN_TIMESTAMP}__{path.name}"
    candidate = path.with_name(name)
    if not candidate.exists():
        return candidate
    for index in range(2, 100):
        alt = candidate.with_name(candidate.stem + f"_{index}" + candidate.suffix)
        if not alt.exists():
            return alt
    raise FileExistsError(candidate)


def mission_details(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {
            "node_count": 0,
            "directed_pair_count": 0,
            "active_route_count": 0,
            "route_sequence": "",
            "mission_trajectory_point_count": 0,
            "enabled_drones": [],
            "matrix_diagnostics": {},
        }
    doc = json.loads(path.read_text(encoding="utf-8"))
    configs = doc.get("drone_configs") or (doc.get("env") or {}).get("drone_configs") or {}
    enabled = [
        f"D{drone_id}"
        for drone_id, cfg in sorted(configs.items(), key=lambda item: str(item[0]))
        if isinstance(cfg, dict) and bool(cfg.get("enabled"))
    ]
    solution = doc.get("solution") or {}
    routes = solution.get("routes") or {}
    target_ids = {str(t.get("id")) for t in (doc.get("env") or {}).get("targets", [])}
    active_route_count = 0
    route_sequence = ""
    trajectory_points = 0
    d1 = routes.get("1") or {}
    if d1:
        route = [str(node) for node in d1.get("route", [])]
        if route:
            route_sequence = ",".join(route)
        trajectory_points = len(d1.get("trajectory") or [])
    for route_data in routes.values():
        route = [str(node) for node in route_data.get("route", [])]
        if any(node in target_ids for node in route):
            active_route_count += 1
    matrix = solution.get("distance_matrix") or {}
    labels = matrix.get("labels") or []
    node_count = len(labels)
    diagnostics = matrix.get("benchmark_diagnostics") or {}
    return {
        "node_count": node_count,
        "directed_pair_count": node_count * (node_count - 1),
        "active_route_count": active_route_count,
        "route_sequence": route_sequence,
        "mission_trajectory_point_count": trajectory_points,
        "enabled_drones": enabled,
        "matrix_diagnostics": diagnostics,
    }


def status_label(row: dict[str, Any]) -> str:
    if row.get("error") or not row.get("solver_completed"):
        return "solver_failed"
    if row.get("mission_success"):
        return "success"
    if row.get("mission_feasible"):
        return "partial"
    return "infeasible"


def append_csv(row: dict[str, Any]) -> None:
    csv_path = RESULTS_DIR / f"main_benchmark_run_02_{RUN_TIMESTAMP}.csv"
    exists = csv_path.exists()
    with csv_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({field: row.get(field) for field in CSV_FIELDS})


def write_results_json(rows: list[dict[str, Any]], infrastructure_errors: list[dict[str, Any]]) -> None:
    by_method: dict[str, dict[str, Any]] = {}
    for method in METHODS:
        method_rows = [row for row in rows if row["method"] == method]
        successes = [row for row in method_rows if row["mission_success"]]
        feasible = [row for row in method_rows if row["mission_feasible"]]
        partial = [
            row
            for row in method_rows
            if row["mission_feasible"] and not row["mission_success"]
        ]
        infeasible = [row for row in method_rows if not row["mission_feasible"]]
        by_method[method] = {
            "runs": len(method_rows),
            "successful_missions": len(successes),
            "feasible_missions": len(feasible),
            "partial_missions": len(partial),
            "failed_infeasible_missions": len(infeasible),
            "mean_matrix_time": mean(row["matrix_time_seconds"] for row in method_rows),
            "mean_solver_time": mean(row["solver_time_seconds"] for row in method_rows),
            "mean_successful_mission_distance": mean(
                row["mission_distance"] for row in successes
            ),
            "mean_target_service_fraction": mean(
                row["service_fraction"] for row in method_rows
            ),
        }
    payload = {
        "run": RUN_ID,
        "run_timestamp": RUN_TIMESTAMP,
        "run_directory": str(RUN_DIR),
        "execution_count": len(rows),
        "expected_execution_count": len(ENVIRONMENTS) * len(METHODS),
        "infrastructure_errors": infrastructure_errors,
        "aggregate_by_method": list(by_method.values()),
        "rows": rows,
    }
    (RESULTS_DIR / f"main_benchmark_run_02_{RUN_TIMESTAMP}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def mean(values: Any) -> float | None:
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def run() -> int:
    if str(EXPERIMENT_ROOT) not in sys.path:
        sys.path.insert(0, str(EXPERIMENT_ROOT))

    from benchmark.runner import run_one

    rows: list[dict[str, Any]] = []
    infrastructure_errors: list[dict[str, Any]] = []
    total = len(ENVIRONMENTS) * len(METHODS)
    completed = 0
    log(f"Controlled Benchmark Run 2 timestamp: {RUN_TIMESTAMP}")
    log("Execution order: 9 controlled environments x 9 methods, sequential.")
    write_status(status="running", completed=0, total=total)

    for env_name in ENVIRONMENTS:
        env_path = INPUT_DIR / env_name
        environment_id = env_path.stem
        topology = topology_for(env_name)
        for method in METHODS:
            completed += 1
            write_status(
                status="running",
                completed=completed - 1,
                total=total,
                current_environment=env_name,
                current_method=method,
            )
            log(f"START {completed:02d}/{total} {env_name} {method}")
            result = None
            try:
                result = run_one(
                    environment_path=env_path,
                    matrix_method=method,
                    output_dir=OUTPUTS_DIR / method,
                )
                summary_row = read_last_summary_row(method)
                mission_path = (
                    Path(result.output_mission_json)
                    if result.output_mission_json
                    else None
                )
                if mission_path and mission_path.exists():
                    new_mission_path = unique_run2_mission_path(
                        mission_path, environment_id, method
                    )
                    mission_path.rename(new_mission_path)
                    mission_path = new_mission_path
                    summary_row["output_mission_json"] = str(new_mission_path)
                details = mission_details(mission_path)
                diagnostics = summary_row.get("matrix_diagnostics") or details[
                    "matrix_diagnostics"
                ]
                summary_row.update(
                    {
                        "run": RUN_ID,
                        "run_timestamp": RUN_TIMESTAMP,
                        "node_count": details["node_count"],
                        "directed_pair_count": details["directed_pair_count"],
                        "active_route_count": details["active_route_count"],
                        "route_sequence": details["route_sequence"],
                        "mission_trajectory_point_count": details[
                            "mission_trajectory_point_count"
                        ],
                        "enabled_drones": details["enabled_drones"],
                    }
                )
                rewrite_last_summary_row(method, summary_row)
                total_targets = int(summary_row.get("targets_expected") or 0)
                targets_serviced = int(summary_row.get("targets_serviced") or 0)
                service_fraction = (
                    targets_serviced / total_targets if total_targets else 0.0
                )
                row = {
                    "run": RUN_ID,
                    "environment": environment_id,
                    "environment_filename": env_name,
                    "topology": topology,
                    "target_count": int(summary_row.get("target_count") or 0),
                    "method": method,
                    "node_count": details["node_count"],
                    "directed_pair_count": details["directed_pair_count"],
                    "matrix_time_seconds": summary_row.get(
                        "matrix_build_time_seconds"
                    ),
                    "solver_time_seconds": summary_row.get("solver_time_seconds"),
                    "solver_completed": bool(summary_row.get("solver_completed")),
                    "mission_feasible": bool(summary_row.get("mission_feasible")),
                    "mission_success": bool(summary_row.get("mission_success")),
                    "targets_serviced": targets_serviced,
                    "target_count_total": total_targets,
                    "service_fraction": service_fraction,
                    "mission_distance": float(summary_row.get("route_distance") or 0.0),
                    "mission_point_count": int(summary_row.get("points") or 0),
                    "failure_reason": summary_row.get("failure_reason"),
                    "mission_output_path": str(mission_path) if mission_path else "",
                    "active_route_count": details["active_route_count"],
                    "route_sequence": details["route_sequence"],
                    "mission_trajectory_point_count": details[
                        "mission_trajectory_point_count"
                    ],
                    "matrix_diagnostics_json": json.dumps(
                        diagnostics or {}, sort_keys=True
                    ),
                    "error": summary_row.get("error"),
                    "run_started_at": summary_row.get("run_started_at"),
                    "status": status_label(summary_row),
                }
            except Exception as exc:
                error = {
                    "environment": env_name,
                    "method": method,
                    "error": f"{type(exc).__name__}: {exc}",
                    "time": now_iso(),
                }
                infrastructure_errors.append(error)
                log(f"INFRASTRUCTURE_ERROR {env_name} {method} {error['error']}")
                row = {
                    "run": RUN_ID,
                    "environment": environment_id,
                    "environment_filename": env_name,
                    "topology": topology,
                    "target_count": 0,
                    "method": method,
                    "node_count": 0,
                    "directed_pair_count": 0,
                    "matrix_time_seconds": None,
                    "solver_time_seconds": None,
                    "solver_completed": False,
                    "mission_feasible": False,
                    "mission_success": False,
                    "targets_serviced": 0,
                    "target_count_total": 0,
                    "service_fraction": 0.0,
                    "mission_distance": 0.0,
                    "mission_point_count": 0,
                    "failure_reason": error["error"],
                    "mission_output_path": "",
                    "active_route_count": 0,
                    "route_sequence": "",
                    "mission_trajectory_point_count": 0,
                    "matrix_diagnostics_json": "{}",
                    "error": error["error"],
                    "run_started_at": now_iso(),
                    "status": "infrastructure_error",
                }
            rows.append(row)
            append_csv(row)
            write_results_json(rows, infrastructure_errors)
            log(
                "END "
                f"{completed:02d}/{total} {env_name} {method} "
                f"status={row['status']} matrix={row['matrix_time_seconds']} "
                f"solver={row['solver_time_seconds']} distance={row['mission_distance']}"
            )
            write_status(
                status="running",
                completed=completed,
                total=total,
                current_environment=env_name,
                current_method=method,
                last_status=row["status"],
            )

    final_status = "complete" if not infrastructure_errors else "complete_with_errors"
    write_status(
        status=final_status,
        completed=completed,
        total=total,
        current_environment=None,
        current_method=None,
        infrastructure_error_count=len(infrastructure_errors),
    )
    log(f"COMPLETE status={final_status} completed={completed}/{total}")
    return 0 if not infrastructure_errors else 2


if __name__ == "__main__":
    raise SystemExit(run())
