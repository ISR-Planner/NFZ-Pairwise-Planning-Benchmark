"""Run the Part II primary benchmark campaign.

This script is intentionally a thin campaign wrapper around the existing
``experiments.benchmark.runner.run_one`` primary benchmark path. It does not use
the Part II Proposed diagnostic instrumentation.
"""

from __future__ import annotations

import csv
import ctypes
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENTS_ROOT = REPO_ROOT / "experiments"
PART2_ROOT = EXPERIMENTS_ROOT / "part2"
DATASET_MANIFEST_PATH = PART2_ROOT / "manifests" / "part2_dataset_manifest.json"
RESULTS_ROOT = PART2_ROOT / "results" / "primary"
ANALYSIS_ROOT = PART2_ROOT / "analysis"
MANIFEST_ROOT = PART2_ROOT / "manifests"
PART1_RESULTS_CSV = (
    EXPERIMENTS_ROOT
    / "main_benchmark_replications"
    / "run_02_20260810-015756"
    / "results"
    / "main_benchmark_run_02_20260810-015756.csv"
)

STARTING_COMMIT = "e6ac98838da7e22582e3f299c73882a1f4300d91"
PART2_INFRASTRUCTURE_COMMIT = "1163ae8164f9ffe7ad60dc8cfd1dd7cebcfca0ba"
PART1_EXPERIMENT_COMMIT = "73b9a7b60fa892bbf2220e6a961c1393ab28fbf5"
DATASET_GENERATOR_COMMIT = "5f26eb8a5119af9854a5d49de3f900821701a689"

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

PART1_T12_ENVIRONMENT = {
    "c_trap": "c_trap_001_t12.json",
    "sequential_staggered_blocking": "sequential_staggered_blocking_001_t12.json",
    "asymmetric_corridor": "asymmetric_corridor_001_t12.json",
}

CSV_FIELDS = [
    "run",
    "campaign_id",
    "execution_index",
    "environment_id",
    "environment_filename",
    "topology",
    "topology_display",
    "instance_id",
    "seed",
    "method",
    "source_mission_file",
    "source_dataset_hash",
    "target_count",
    "node_count",
    "directed_pair_count",
    "matrix_time_sec",
    "matrix_time_seconds",
    "solver_time_sec",
    "solver_time_seconds",
    "solver_completed",
    "mission_feasible",
    "mission_success",
    "targets_serviced",
    "target_count_total",
    "service_fraction",
    "mission_distance_km",
    "mission_distance",
    "mission_point_count",
    "failure_reason",
    "output_mission_file",
    "mission_output_path",
    "active_route_count",
    "route_sequence",
    "mission_trajectory_point_count",
    "matrix_diagnostics_json",
    "error",
    "run_started_at",
    "status",
    "infrastructure_retry_flag",
]


@dataclass(frozen=True)
class Condition:
    execution_index: int
    environment_id: str
    environment_filename: str
    topology: str
    topology_display: str
    instance_id: str
    seed: int
    method: str
    source_path: Path
    source_dataset_hash: str
    source_file_size_bytes: int

    @property
    def key(self) -> str:
        return f"{self.environment_id}__{self.method}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_text_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, payload: Dict[str, Any] | List[Any]) -> None:
    write_text_lf(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def append_csv(path: Path, row: Dict[str, Any], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        if not exists:
            writer.writeheader()
        writer.writerow({field: row.get(field) for field in fieldnames})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def git_output(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def cpu_name_from_registry() -> Optional[str]:
    if os.name != "nt":
        return None
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
        )
        value, _kind = winreg.QueryValueEx(key, "ProcessorNameString")
        return str(value)
    except OSError:
        return None


def memory_info_gb() -> Dict[str, Optional[float]]:
    if os.name != "nt":
        return {"total_physical_gb": None, "available_physical_gb": None}

    class MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return {"total_physical_gb": None, "available_physical_gb": None}
    return {
        "total_physical_gb": round(status.ullTotalPhys / (1024**3), 2),
        "available_physical_gb": round(status.ullAvailPhys / (1024**3), 2),
    }


def collect_environment_info() -> Dict[str, Any]:
    memory = memory_info_gb()
    return {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "python_version_short": platform.python_version(),
        "platform": platform.platform(),
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "processor": platform.processor(),
        "cpu_name": cpu_name_from_registry(),
        "logical_cpu_count": os.cpu_count(),
        "total_physical_memory_gb": memory["total_physical_gb"],
        "available_physical_memory_gb": memory["available_physical_gb"],
        "cpu_only": True,
    }


def verify_execution_environment(info: Dict[str, Any]) -> None:
    problems: List[str] = []
    if info["python_version_short"] != "3.14.0":
        problems.append(f"Python version differs: {info['python_version_short']}")
    if info["os"] != "Windows":
        problems.append(f"OS differs: {info['os']}")
    cpu_name = str(info.get("cpu_name") or info.get("processor") or "")
    if "i9-13900K" not in cpu_name:
        problems.append(f"CPU identity differs or is unavailable: {cpu_name}")
    total_memory = info.get("total_physical_memory_gb")
    if total_memory is None or total_memory < 60.0:
        problems.append(f"RAM differs or is unavailable: {total_memory} GB")
    if problems:
        raise RuntimeError(
            "Material hardware/software environment mismatch: " + "; ".join(problems)
        )


def load_dataset_manifest() -> List[Dict[str, Any]]:
    manifest = json.loads(DATASET_MANIFEST_PATH.read_text(encoding="utf-8"))
    rows = list(manifest.get("rows", []))
    if len(rows) != 15:
        raise RuntimeError(f"Expected 15 dataset rows, found {len(rows)}")
    return rows


def verify_dataset_rows(rows: List[Dict[str, Any]]) -> None:
    observed = {(row["topology"], row["instance_id"]) for row in rows}
    expected = {
        (topology, f"i{index:02d}")
        for topology in TOPOLOGY_ORDER
        for index in range(1, 6)
    }
    if observed != expected:
        raise RuntimeError(f"Unexpected dataset topology/instance set: {observed}")

    for row in rows:
        path = REPO_ROOT / row["relative_path"]
        if not path.exists():
            raise RuntimeError(f"Dataset is missing: {path}")
        digest = sha256(path)
        if digest != str(row["sha256"]).upper():
            raise RuntimeError(f"Dataset hash mismatch for {path}")
        file_size = path.stat().st_size
        if file_size != int(row["file_size_bytes"]):
            raise RuntimeError(f"Dataset file size mismatch for {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        env = raw["env"] if isinstance(raw.get("env"), dict) else raw
        target_count = len(env.get("targets", []))
        airport_count = len(env.get("airports", []))
        node_count = target_count + airport_count
        if target_count != 12 or airport_count != 1 or node_count != 13:
            raise RuntimeError(f"Unexpected mission node count in {path}")
        if node_count * (node_count - 1) != 156:
            raise RuntimeError(f"Unexpected directed pair count in {path}")


def build_conditions(rows: List[Dict[str, Any]]) -> List[Condition]:
    by_key = {
        (row["topology"], row["instance_id"]): row
        for row in rows
    }
    conditions: List[Condition] = []
    execution_index = 0
    for topology in TOPOLOGY_ORDER:
        for instance_number in range(1, 6):
            instance_id = f"i{instance_number:02d}"
            row = by_key[(topology, instance_id)]
            for method in METHODS:
                execution_index += 1
                path = REPO_ROOT / row["relative_path"]
                conditions.append(
                    Condition(
                        execution_index=execution_index,
                        environment_id=str(row["environment_id"]),
                        environment_filename=Path(row["relative_path"]).name,
                        topology=topology,
                        topology_display=TOPOLOGY_DISPLAY[topology],
                        instance_id=instance_id,
                        seed=int(row["seed"]),
                        method=method,
                        source_path=path,
                        source_dataset_hash=str(row["sha256"]).upper(),
                        source_file_size_bytes=int(row["file_size_bytes"]),
                    )
                )
    if len(conditions) != 135:
        raise RuntimeError(f"Expected 135 conditions, found {len(conditions)}")
    if any(condition.method == "proposed_parallel" for condition in conditions):
        raise RuntimeError("proposed_parallel is not allowed in Part II primary")
    return conditions


def read_last_summary_row(output_dir: Path) -> Dict[str, Any]:
    summary_path = output_dir / "benchmark_summary.jsonl"
    lines = [line for line in summary_path.read_text(encoding="utf-8").splitlines() if line]
    return json.loads(lines[-1])


def mission_details(path: Optional[Path]) -> Dict[str, Any]:
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
    diagnostics = matrix.get("benchmark_diagnostics") or {}
    return {
        "node_count": len(labels),
        "directed_pair_count": len(labels) * (len(labels) - 1),
        "active_route_count": active_route_count,
        "route_sequence": route_sequence,
        "mission_trajectory_point_count": trajectory_points,
        "enabled_drones": enabled,
        "matrix_diagnostics": diagnostics,
    }


def status_label(row: Dict[str, Any]) -> str:
    if row.get("error") or not row.get("solver_completed"):
        return "solver_failed"
    if row.get("mission_success"):
        return "success"
    if row.get("mission_feasible"):
        return "partial"
    return "infeasible"


def mean(values: Iterable[Optional[float]]) -> Optional[float]:
    vals = [float(value) for value in values if value is not None]
    return statistics.fmean(vals) if vals else None


def median(values: Iterable[Optional[float]]) -> Optional[float]:
    vals = sorted(float(value) for value in values if value is not None)
    return statistics.median(vals) if vals else None


def value_range(values: List[float]) -> Optional[float]:
    return max(values) - min(values) if values else None


def as_number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def list_text(values: Iterable[Any]) -> str:
    return ";".join("" if value is None else str(value) for value in values)


def record_from_summary(
    *,
    run_id: str,
    campaign_id: str,
    condition: Condition,
    summary_row: Dict[str, Any],
    mission_path: Optional[Path],
    details: Dict[str, Any],
) -> Dict[str, Any]:
    total_targets = int(summary_row.get("targets_expected") or condition.source_path.exists() and 12 or 0)
    targets_serviced = int(summary_row.get("targets_serviced") or 0)
    service_fraction = targets_serviced / total_targets if total_targets else 0.0
    matrix_time = as_number(summary_row.get("matrix_build_time_seconds"))
    solver_time = as_number(summary_row.get("solver_time_seconds"))
    mission_distance = float(summary_row.get("route_distance") or 0.0)
    diagnostics = summary_row.get("matrix_diagnostics") or details["matrix_diagnostics"]
    return {
        "run": run_id,
        "campaign_id": campaign_id,
        "execution_index": condition.execution_index,
        "environment_id": condition.environment_id,
        "environment_filename": condition.environment_filename,
        "topology": condition.topology,
        "topology_display": condition.topology_display,
        "instance_id": condition.instance_id,
        "seed": condition.seed,
        "method": condition.method,
        "source_mission_file": str(condition.source_path.relative_to(REPO_ROOT)),
        "source_dataset_hash": condition.source_dataset_hash,
        "source_file_size_bytes": condition.source_file_size_bytes,
        "target_count": int(summary_row.get("target_count") or 0),
        "node_count": details["node_count"],
        "directed_pair_count": details["directed_pair_count"],
        "matrix_time_sec": matrix_time,
        "matrix_time_seconds": matrix_time,
        "solver_time_sec": solver_time,
        "solver_time_seconds": solver_time,
        "solver_completed": bool(summary_row.get("solver_completed")),
        "mission_feasible": bool(summary_row.get("mission_feasible")),
        "mission_success": bool(summary_row.get("mission_success")),
        "targets_serviced": targets_serviced,
        "target_count_total": total_targets,
        "service_fraction": service_fraction,
        "mission_distance_km": mission_distance,
        "mission_distance": mission_distance,
        "mission_point_count": int(summary_row.get("points") or 0),
        "failure_reason": summary_row.get("failure_reason"),
        "output_mission_file": (
            str(mission_path.relative_to(REPO_ROOT)) if mission_path else ""
        ),
        "mission_output_path": str(mission_path) if mission_path else "",
        "active_route_count": details["active_route_count"],
        "route_sequence": details["route_sequence"],
        "mission_trajectory_point_count": details["mission_trajectory_point_count"],
        "enabled_drones": details["enabled_drones"],
        "matrix_diagnostics_json": json.dumps(diagnostics or {}, sort_keys=True),
        "error": summary_row.get("error"),
        "run_started_at": summary_row.get("run_started_at"),
        "status": status_label(summary_row),
        "infrastructure_retry_flag": False,
    }


def infrastructure_error_record(
    *,
    run_id: str,
    campaign_id: str,
    condition: Condition,
    error: str,
) -> Dict[str, Any]:
    return {
        "run": run_id,
        "campaign_id": campaign_id,
        "execution_index": condition.execution_index,
        "environment_id": condition.environment_id,
        "environment_filename": condition.environment_filename,
        "topology": condition.topology,
        "topology_display": condition.topology_display,
        "instance_id": condition.instance_id,
        "seed": condition.seed,
        "method": condition.method,
        "source_mission_file": str(condition.source_path.relative_to(REPO_ROOT)),
        "source_dataset_hash": condition.source_dataset_hash,
        "source_file_size_bytes": condition.source_file_size_bytes,
        "target_count": 0,
        "node_count": 0,
        "directed_pair_count": 0,
        "matrix_time_sec": None,
        "matrix_time_seconds": None,
        "solver_time_sec": None,
        "solver_time_seconds": None,
        "solver_completed": False,
        "mission_feasible": False,
        "mission_success": False,
        "targets_serviced": 0,
        "target_count_total": 0,
        "service_fraction": 0.0,
        "mission_distance_km": 0.0,
        "mission_distance": 0.0,
        "mission_point_count": 0,
        "failure_reason": error,
        "output_mission_file": "",
        "mission_output_path": "",
        "active_route_count": 0,
        "route_sequence": "",
        "mission_trajectory_point_count": 0,
        "enabled_drones": [],
        "matrix_diagnostics_json": "{}",
        "error": error,
        "run_started_at": now_iso(),
        "status": "infrastructure_error",
        "infrastructure_retry_flag": False,
    }


def aggregate_by_method(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    aggregates: List[Dict[str, Any]] = []
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
        aggregates.append(
            {
                "method": method,
                "runs": len(method_rows),
                "successes": len(successes),
                "feasible": len(feasible),
                "partial": len(partial),
                "infeasible": len(infeasible),
                "mean_matrix_time": mean(row["matrix_time_sec"] for row in method_rows),
                "mean_solver_time": mean(row["solver_time_sec"] for row in method_rows),
                "mean_successful_mission_distance": mean(
                    row["mission_distance_km"] for row in successes
                ),
                "mean_service_fraction": mean(row["service_fraction"] for row in method_rows),
            }
        )
    return aggregates


def method_result_failure_count(rows: List[Dict[str, Any]]) -> int:
    return sum(
        1
        for row in rows
        if row["status"] in {"partial", "infeasible", "solver_failed"}
        and row["status"] != "infrastructure_error"
    )


def write_progress(
    *,
    path: Path,
    run_id: str,
    campaign_id: str,
    expected_conditions: List[Condition],
    rows: List[Dict[str, Any]],
    infrastructure_failures: List[Dict[str, Any]],
    status: str,
    current: Optional[Condition] = None,
) -> None:
    completed_keys = {f"{row['environment_id']}__{row['method']}" for row in rows}
    expected_keys = [condition.key for condition in expected_conditions]
    pending = [key for key in expected_keys if key not in completed_keys]
    payload = {
        "schema": "nfz_part2_primary_progress_v1",
        "run": run_id,
        "campaign_id": campaign_id,
        "status": status,
        "updated_at": now_iso(),
        "expected_conditions": len(expected_conditions),
        "completed_conditions": len(rows),
        "pending_conditions": len(pending),
        "pending_condition_keys": pending,
        "infrastructure_failures": infrastructure_failures,
        "infrastructure_failure_count": len(infrastructure_failures),
        "method_result_failure_count": method_result_failure_count(rows),
        "current_condition": current.key if current else None,
    }
    write_json(path, payload)


def write_results_json(
    *,
    path: Path,
    run_id: str,
    campaign_id: str,
    run_dir: Path,
    rows: List[Dict[str, Any]],
    infrastructure_failures: List[Dict[str, Any]],
    environment_info: Dict[str, Any],
    dataset_manifest_hash: str,
) -> None:
    payload = {
        "schema": "nfz_part2_primary_results_v1",
        "run": run_id,
        "campaign_id": campaign_id,
        "run_directory": str(run_dir),
        "run_directory_relative": str(run_dir.relative_to(REPO_ROOT)),
        "git_commit": STARTING_COMMIT,
        "part2_infrastructure_commit": PART2_INFRASTRUCTURE_COMMIT,
        "part1_experiment_commit": PART1_EXPERIMENT_COMMIT,
        "dataset_generator_commit": DATASET_GENERATOR_COMMIT,
        "dataset_manifest_hash": dataset_manifest_hash,
        "execution_count": len(rows),
        "expected_execution_count": 135,
        "infrastructure_errors": infrastructure_failures,
        "aggregate_by_method": aggregate_by_method(rows),
        "environment_info": environment_info,
        "rows": rows,
    }
    write_json(path, payload)


def normalize_text_tree(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".json", ".jsonl", ".csv", ".md", ".txt", ".log"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        write_text_lf(path, text)


def validate_completion(rows: List[Dict[str, Any]], conditions: List[Condition]) -> None:
    if len(rows) != len(conditions):
        raise RuntimeError(f"Expected {len(conditions)} records, found {len(rows)}")
    keys = [(row["environment_id"], row["method"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise RuntimeError("Duplicate method/environment condition detected")
    if any(row["method"] == "proposed_parallel" for row in rows):
        raise RuntimeError("proposed_parallel row detected")
    if any("experiments/part2/datasets/controlled_t12" not in row["source_mission_file"].replace("\\", "/") for row in rows):
        raise RuntimeError("Accidental non-Part-II input detected")
    envs = {row["environment_id"] for row in rows}
    if len(envs) != 15:
        raise RuntimeError(f"Expected 15 unique environments, found {len(envs)}")
    for env_id in envs:
        env_methods = {row["method"] for row in rows if row["environment_id"] == env_id}
        if env_methods != set(METHODS):
            raise RuntimeError(f"Missing method for {env_id}: {set(METHODS) - env_methods}")
    for method in METHODS:
        method_envs = {row["environment_id"] for row in rows if row["method"] == method}
        if len(method_envs) != 15:
            raise RuntimeError(f"Method {method} does not cover 15 environments")


def write_primary_manifest(
    *,
    rows: List[Dict[str, Any]],
    run_id: str,
    campaign_id: str,
    run_dir: Path,
    record_paths: Dict[str, Path],
    dataset_manifest_hash: str,
    environment_info: Dict[str, Any],
) -> Tuple[Path, Path, List[Dict[str, Any]]]:
    csv_path = MANIFEST_ROOT / "part2_primary_run01_manifest.csv"
    json_path = MANIFEST_ROOT / "part2_primary_run01_manifest.json"
    if csv_path.exists() or json_path.exists():
        raise FileExistsError("Part II primary run01 manifest already exists")
    manifest_rows: List[Dict[str, Any]] = []
    for row in rows:
        key = f"{row['environment_id']}__{row['method']}"
        result_path = record_paths[key]
        manifest_rows.append(
            {
                "environment_id": row["environment_id"],
                "topology": row["topology"],
                "instance_id": row["instance_id"],
                "seed": row["seed"],
                "method": row["method"],
                "result_path": str(result_path.relative_to(REPO_ROOT)),
                "result_sha256": sha256(result_path),
                "execution_status": row["status"],
                "matrix_time_sec": row["matrix_time_sec"],
                "solver_time_sec": row["solver_time_sec"],
                "mission_success": row["mission_success"],
                "mission_feasible": row["mission_feasible"],
                "targets_serviced": row["targets_serviced"],
                "mission_distance_km": row["mission_distance_km"],
                "infrastructure_retry_flag": row["infrastructure_retry_flag"],
                "git_commit": STARTING_COMMIT,
                "source_dataset_hash": row["source_dataset_hash"],
                "source_mission_file": row["source_mission_file"],
                "output_mission_file": row["output_mission_file"],
            }
        )
    fields = list(manifest_rows[0])
    write_csv(csv_path, manifest_rows, fields)
    write_json(
        json_path,
        {
            "schema": "nfz_part2_primary_run01_manifest_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "run_directory": str(run_dir.relative_to(REPO_ROOT)),
            "created_at": now_iso(),
            "git_commit": STARTING_COMMIT,
            "part2_infrastructure_commit": PART2_INFRASTRUCTURE_COMMIT,
            "part1_experiment_commit": PART1_EXPERIMENT_COMMIT,
            "dataset_generator_commit": DATASET_GENERATOR_COMMIT,
            "dataset_manifest_hash": dataset_manifest_hash,
            "environment_info": environment_info,
            "expected_primary_executions": 135,
            "completed_primary_executions": len(rows),
            "rows": manifest_rows,
        },
    )
    return csv_path, json_path, manifest_rows


def topology_method_summary(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    summary_rows: List[Dict[str, Any]] = []
    for topology in TOPOLOGY_ORDER:
        for method in METHODS:
            subset = [
                row
                for row in rows
                if row["topology"] == topology and row["method"] == method
            ]
            subset = sorted(subset, key=lambda row: row["instance_id"])
            matrix_values = [row["matrix_time_sec"] for row in subset]
            matrix_numbers = [float(value) for value in matrix_values if value is not None]
            feasible_distances = [
                row["mission_distance_km"] for row in subset if row["mission_feasible"]
            ]
            successful_distances = [
                row["mission_distance_km"] for row in subset if row["mission_success"]
            ]
            summary_rows.append(
                {
                    "topology": topology,
                    "topology_display": TOPOLOGY_DISPLAY[topology],
                    "method": method,
                    "condition_count": len(subset),
                    "success_count": sum(1 for row in subset if row["mission_success"]),
                    "feasible_count": sum(1 for row in subset if row["mission_feasible"]),
                    "targets_serviced_values": list_text(row["targets_serviced"] for row in subset),
                    "matrix_time_values_sec": list_text(matrix_values),
                    "matrix_time_mean_sec": mean(matrix_values),
                    "matrix_time_median_sec": median(matrix_values),
                    "matrix_time_min_sec": min(matrix_numbers) if matrix_numbers else None,
                    "matrix_time_max_sec": max(matrix_numbers) if matrix_numbers else None,
                    "matrix_time_range_sec": value_range(matrix_numbers),
                    "feasible_mission_distance_values_km": list_text(feasible_distances),
                    "successful_mission_distance_values_km": list_text(successful_distances),
                }
            )
    return summary_rows


def vg_proposed_ratios(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ratio_rows: List[Dict[str, Any]] = []
    by_condition = {
        (row["topology"], row["instance_id"], row["method"]): row
        for row in rows
    }
    for topology in TOPOLOGY_ORDER:
        ratios: List[float] = []
        ratio_by_instance: Dict[str, Optional[float]] = {}
        for instance_number in range(1, 6):
            instance_id = f"i{instance_number:02d}"
            proposed = by_condition[(topology, instance_id, "proposed")]["matrix_time_sec"]
            vg = by_condition[(topology, instance_id, "visibility_graph")]["matrix_time_sec"]
            ratio = float(vg) / float(proposed) if proposed and vg is not None else None
            ratio_by_instance[instance_id] = ratio
            if ratio is not None:
                ratios.append(ratio)
        ratio_rows.append(
            {
                "topology": topology,
                "topology_display": TOPOLOGY_DISPLAY[topology],
                "i01": ratio_by_instance["i01"],
                "i02": ratio_by_instance["i02"],
                "i03": ratio_by_instance["i03"],
                "i04": ratio_by_instance["i04"],
                "i05": ratio_by_instance["i05"],
                "values": list_text(ratios),
                "mean": mean(ratios),
                "min": min(ratios) if ratios else None,
                "max": max(ratios) if ratios else None,
                "range": value_range(ratios),
            }
        )
    return ratio_rows


def load_part1_t12_rows() -> List[Dict[str, Any]]:
    with PART1_RESULTS_CSV.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    return [
        row
        for row in rows
        if row["environment_filename"] in set(PART1_T12_ENVIRONMENT.values())
        and row["method"] in {"proposed", "visibility_graph"}
    ]


def position_label(value: float, values: List[float]) -> str:
    low = min(values)
    high = max(values)
    span = high - low
    if low <= value <= high:
        if span == 0:
            return "same as Part II values"
        if value - low <= 0.10 * span:
            return "near Part II low end"
        if high - value <= 0.10 * span:
            return "near Part II high end"
        return "within Part II range"
    if value < low:
        return "below Part II range"
    return "above Part II range"


def part1_comparison(rows: List[Dict[str, Any]], ratio_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    part1_rows = load_part1_t12_rows()
    part1_lookup = {
        (row["topology"], row["method"]): row
        for row in part1_rows
    }
    ratio_lookup = {row["topology"]: row for row in ratio_rows}
    comparison_rows: List[Dict[str, Any]] = []
    for topology in TOPOLOGY_ORDER:
        part1_proposed = float(part1_lookup[(topology, "proposed")]["matrix_time_seconds"])
        part1_vg = float(part1_lookup[(topology, "visibility_graph")]["matrix_time_seconds"])
        part1_ratio = part1_vg / part1_proposed
        part2_proposed = [
            float(row["matrix_time_sec"])
            for row in sorted(
                [row for row in rows if row["topology"] == topology and row["method"] == "proposed"],
                key=lambda item: item["instance_id"],
            )
        ]
        part2_vg = [
            float(row["matrix_time_sec"])
            for row in sorted(
                [row for row in rows if row["topology"] == topology and row["method"] == "visibility_graph"],
                key=lambda item: item["instance_id"],
            )
        ]
        part2_ratio_values = [
            float(ratio_lookup[topology][instance_id])
            for instance_id in ("i01", "i02", "i03", "i04", "i05")
        ]
        comparison_rows.append(
            {
                "topology": topology,
                "topology_display": TOPOLOGY_DISPLAY[topology],
                "part1_proposed_matrix_time_sec": part1_proposed,
                "part2_proposed_values_sec": list_text(part2_proposed),
                "part1_vg_matrix_time_sec": part1_vg,
                "part2_vg_values_sec": list_text(part2_vg),
                "part1_vg_proposed_ratio": part1_ratio,
                "part2_ratio_min": min(part2_ratio_values),
                "part2_ratio_mean": statistics.fmean(part2_ratio_values),
                "part2_ratio_max": max(part2_ratio_values),
                "part1_proposed_position": position_label(part1_proposed, part2_proposed),
                "part1_vg_position": position_label(part1_vg, part2_vg),
                "part1_ratio_position": position_label(part1_ratio, part2_ratio_values),
            }
        )
    return comparison_rows


def write_markdown_summary(
    *,
    path: Path,
    rows: List[Dict[str, Any]],
    topology_summary_rows: List[Dict[str, Any]],
    ratio_rows: List[Dict[str, Any]],
    comparison_rows: List[Dict[str, Any]],
    run_id: str,
    campaign_id: str,
    run_dir: Path,
    manifest_csv: Path,
    manifest_json: Path,
) -> None:
    lines: List[str] = [
        "# Part II Primary Run 01 Summary",
        "",
        "This summary is descriptive only. Proposed diagnostic instrumentation and sanity repetitions were not run.",
        "",
        "## Campaign",
        "",
        f"- Run: `{run_id}`",
        f"- Campaign ID: `{campaign_id}`",
        f"- Campaign directory: `{run_dir.relative_to(REPO_ROOT).as_posix()}`",
        f"- Expected primary executions: `{len(rows)}`",
        f"- Primary manifest CSV: `{manifest_csv.relative_to(REPO_ROOT).as_posix()}`",
        f"- Primary manifest JSON: `{manifest_json.relative_to(REPO_ROOT).as_posix()}`",
        "",
        "## Completion",
        "",
        "| method | success / 15 | feasible / 15 |",
        "|---|---:|---:|",
    ]
    method_totals = aggregate_by_method(rows)
    for item in method_totals:
        lines.append(
            f"| {item['method']} | {item['successes']} / 15 | {item['feasible']} / 15 |"
        )
    lines.extend(
        [
            "",
            "## Proposed Matrix Time",
            "",
            "| topology | values sec | mean | min | max |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for topology in TOPOLOGY_ORDER:
        row = next(
            item
            for item in topology_summary_rows
            if item["topology"] == topology and item["method"] == "proposed"
        )
        lines.append(
            f"| {row['topology_display']} | {row['matrix_time_values_sec']} | {row['matrix_time_mean_sec']:.6f} | {row['matrix_time_min_sec']:.6f} | {row['matrix_time_max_sec']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Visibility Graph Matrix Time",
            "",
            "| topology | values sec | mean | min | max |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for topology in TOPOLOGY_ORDER:
        row = next(
            item
            for item in topology_summary_rows
            if item["topology"] == topology and item["method"] == "visibility_graph"
        )
        lines.append(
            f"| {row['topology_display']} | {row['matrix_time_values_sec']} | {row['matrix_time_mean_sec']:.6f} | {row['matrix_time_min_sec']:.6f} | {row['matrix_time_max_sec']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## VG / Proposed Ratios",
            "",
            "| topology | i01 | i02 | i03 | i04 | i05 | mean | min | max | range |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in ratio_rows:
        lines.append(
            "| {topology_display} | {i01:.6f} | {i02:.6f} | {i03:.6f} | {i04:.6f} | {i05:.6f} | {mean:.6f} | {min:.6f} | {max:.6f} | {range:.6f} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Part I T12 Comparison",
            "",
            "| topology | Part I Proposed | Part II Proposed values | Part I VG | Part II VG values | Part I ratio | Part II ratio min/mean/max | Part I position |",
            "|---|---:|---|---:|---|---:|---|---|",
        ]
    )
    for row in comparison_rows:
        lines.append(
            "| {topology_display} | {part1_proposed_matrix_time_sec:.6f} | {part2_proposed_values_sec} | {part1_vg_matrix_time_sec:.6f} | {part2_vg_values_sec} | {part1_vg_proposed_ratio:.6f} | {part2_ratio_min:.6f}/{part2_ratio_mean:.6f}/{part2_ratio_max:.6f} | Proposed: {part1_proposed_position}; VG: {part1_vg_position}; ratio: {part1_ratio_position} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Proposed diagnostic executions: `0`",
            "- Sanity repetitions: `0`",
            "- Datasets modified: `NO`",
            "- Part I files modified: `NO`",
            "",
        ]
    )
    write_text_lf(path, "\n".join(lines))


def write_analysis_outputs(
    *,
    rows: List[Dict[str, Any]],
    run_id: str,
    campaign_id: str,
    run_dir: Path,
    manifest_csv: Path,
    manifest_json: Path,
) -> Dict[str, str]:
    topology_rows = topology_method_summary(rows)
    ratio_rows = vg_proposed_ratios(rows)
    comparison_rows = part1_comparison(rows, ratio_rows)

    execution_summary_csv = ANALYSIS_ROOT / "part2_primary_run01_execution_summary.csv"
    execution_summary_json = ANALYSIS_ROOT / "part2_primary_run01_execution_summary.json"
    topology_csv = ANALYSIS_ROOT / "part2_primary_run01_topology_method_summary.csv"
    topology_json = ANALYSIS_ROOT / "part2_primary_run01_topology_method_summary.json"
    ratio_csv = ANALYSIS_ROOT / "part2_primary_run01_vg_proposed_ratios.csv"
    ratio_json = ANALYSIS_ROOT / "part2_primary_run01_vg_proposed_ratios.json"
    comparison_csv = ANALYSIS_ROOT / "part2_primary_run01_part1_comparison.csv"
    comparison_json = ANALYSIS_ROOT / "part2_primary_run01_part1_comparison.json"
    markdown_path = ANALYSIS_ROOT / "PART2_PRIMARY_RUN01_SUMMARY.md"

    for path in (
        execution_summary_csv,
        execution_summary_json,
        topology_csv,
        topology_json,
        ratio_csv,
        ratio_json,
        comparison_csv,
        comparison_json,
        markdown_path,
    ):
        if path.exists():
            raise FileExistsError(f"Analysis output already exists: {path}")

    method_rows = aggregate_by_method(rows)
    write_csv(execution_summary_csv, method_rows, list(method_rows[0]))
    write_json(
        execution_summary_json,
        {
            "schema": "nfz_part2_primary_run01_execution_summary_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "rows": method_rows,
        },
    )
    write_csv(topology_csv, topology_rows, list(topology_rows[0]))
    write_json(
        topology_json,
        {
            "schema": "nfz_part2_primary_run01_topology_method_summary_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "rows": topology_rows,
        },
    )
    write_csv(ratio_csv, ratio_rows, list(ratio_rows[0]))
    write_json(
        ratio_json,
        {
            "schema": "nfz_part2_primary_run01_vg_proposed_ratios_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "rows": ratio_rows,
        },
    )
    write_csv(comparison_csv, comparison_rows, list(comparison_rows[0]))
    write_json(
        comparison_json,
        {
            "schema": "nfz_part2_primary_run01_part1_comparison_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "rows": comparison_rows,
        },
    )
    write_markdown_summary(
        path=markdown_path,
        rows=rows,
        topology_summary_rows=topology_rows,
        ratio_rows=ratio_rows,
        comparison_rows=comparison_rows,
        run_id=run_id,
        campaign_id=campaign_id,
        run_dir=run_dir,
        manifest_csv=manifest_csv,
        manifest_json=manifest_json,
    )
    return {
        "execution_summary_csv": str(execution_summary_csv.relative_to(REPO_ROOT)),
        "execution_summary_json": str(execution_summary_json.relative_to(REPO_ROOT)),
        "topology_method_summary_csv": str(topology_csv.relative_to(REPO_ROOT)),
        "topology_method_summary_json": str(topology_json.relative_to(REPO_ROOT)),
        "vg_proposed_ratios_csv": str(ratio_csv.relative_to(REPO_ROOT)),
        "vg_proposed_ratios_json": str(ratio_json.relative_to(REPO_ROOT)),
        "part1_comparison_csv": str(comparison_csv.relative_to(REPO_ROOT)),
        "part1_comparison_json": str(comparison_json.relative_to(REPO_ROOT)),
        "markdown_summary": str(markdown_path.relative_to(REPO_ROOT)),
    }


def log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{now_iso()} {message}\n")


def run_campaign() -> int:
    if str(EXPERIMENTS_ROOT) not in sys.path:
        sys.path.insert(0, str(EXPERIMENTS_ROOT))

    from benchmark.runner import run_one

    branch = git_output("branch", "--show-current")
    head = git_output("rev-parse", "HEAD")
    if branch != "benchmark-part2-generalization":
        raise RuntimeError(f"Unexpected branch: {branch}")
    if head != STARTING_COMMIT:
        raise RuntimeError(f"Unexpected HEAD: {head}")

    environment_info = collect_environment_info()
    verify_execution_environment(environment_info)

    dataset_rows = load_dataset_manifest()
    verify_dataset_rows(dataset_rows)
    dataset_manifest_hash = sha256(DATASET_MANIFEST_PATH)
    conditions = build_conditions(dataset_rows)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_id = f"run_01_{timestamp}"
    campaign_id = f"part2_generalization_primary_{timestamp}"
    run_dir = RESULTS_ROOT / run_id
    if run_dir.exists():
        raise FileExistsError(f"Campaign directory already exists: {run_dir}")

    records_dir = run_dir / "records"
    logs_dir = run_dir / "logs"
    outputs_dir = run_dir / "outputs"
    csv_path = run_dir / f"{campaign_id}.csv"
    json_path = run_dir / f"{campaign_id}.json"
    jsonl_path = run_dir / f"{campaign_id}_rows.jsonl"
    progress_path = run_dir / "campaign_status.json"
    execution_order_path = run_dir / "execution_order.json"
    log_path = logs_dir / f"{campaign_id}.log"

    run_dir.mkdir(parents=True, exist_ok=False)
    write_json(
        execution_order_path,
        {
            "schema": "nfz_part2_primary_execution_order_v1",
            "order": "for each topology, for each instance i01-i05, run all nine primary methods",
            "methods": METHODS,
            "topologies": TOPOLOGY_ORDER,
            "conditions": [
                {
                    "execution_index": condition.execution_index,
                    "environment_id": condition.environment_id,
                    "topology": condition.topology,
                    "instance_id": condition.instance_id,
                    "seed": condition.seed,
                    "method": condition.method,
                    "source_mission_file": str(condition.source_path.relative_to(REPO_ROOT)),
                }
                for condition in conditions
            ],
        },
    )
    write_json(
        run_dir / "environment_provenance.json",
        {
            "schema": "nfz_part2_primary_environment_provenance_v1",
            "branch": branch,
            "git_commit": head,
            "part2_infrastructure_commit": PART2_INFRASTRUCTURE_COMMIT,
            "part1_experiment_commit": PART1_EXPERIMENT_COMMIT,
            "dataset_generator_commit": DATASET_GENERATOR_COMMIT,
            "dataset_manifest": str(DATASET_MANIFEST_PATH.relative_to(REPO_ROOT)),
            "dataset_manifest_hash": dataset_manifest_hash,
            "environment_info": environment_info,
            "primary_methods": METHODS,
            "proposed_diagnostic_executions": 0,
            "sanity_repetitions": 0,
        },
    )

    rows: List[Dict[str, Any]] = []
    infrastructure_failures: List[Dict[str, Any]] = []
    record_paths: Dict[str, Path] = {}

    log(log_path, f"START campaign={campaign_id} expected={len(conditions)}")
    write_progress(
        path=progress_path,
        run_id=run_id,
        campaign_id=campaign_id,
        expected_conditions=conditions,
        rows=rows,
        infrastructure_failures=infrastructure_failures,
        status="running",
    )

    for condition in conditions:
        log(
            log_path,
            f"START {condition.execution_index:03d}/{len(conditions)} "
            f"{condition.environment_id} {condition.method}",
        )
        write_progress(
            path=progress_path,
            run_id=run_id,
            campaign_id=campaign_id,
            expected_conditions=conditions,
            rows=rows,
            infrastructure_failures=infrastructure_failures,
            status="running",
            current=condition,
        )
        try:
            output_dir = outputs_dir / condition.method
            result = run_one(
                environment_path=condition.source_path,
                matrix_method=condition.method,
                output_dir=output_dir,
            )
            summary_row = read_last_summary_row(output_dir)
            mission_path = Path(result.output_mission_json) if result.output_mission_json else None
            details = mission_details(mission_path)
            row = record_from_summary(
                run_id=run_id,
                campaign_id=campaign_id,
                condition=condition,
                summary_row=summary_row,
                mission_path=mission_path,
                details=details,
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            infrastructure_failures.append(
                {
                    "environment_id": condition.environment_id,
                    "method": condition.method,
                    "execution_index": condition.execution_index,
                    "error": error,
                    "traceback": traceback.format_exc(),
                    "time": now_iso(),
                    "retry_performed": False,
                }
            )
            row = infrastructure_error_record(
                run_id=run_id,
                campaign_id=campaign_id,
                condition=condition,
                error=error,
            )
            log(log_path, f"INFRASTRUCTURE_ERROR {condition.key} {error}")

        rows.append(row)
        record_path = records_dir / f"{condition.key}.json"
        write_json(record_path, row)
        record_paths[condition.key] = record_path
        append_csv(csv_path, row, CSV_FIELDS)
        append_jsonl(jsonl_path, row)
        write_results_json(
            path=json_path,
            run_id=run_id,
            campaign_id=campaign_id,
            run_dir=run_dir,
            rows=rows,
            infrastructure_failures=infrastructure_failures,
            environment_info=environment_info,
            dataset_manifest_hash=dataset_manifest_hash,
        )
        write_progress(
            path=progress_path,
            run_id=run_id,
            campaign_id=campaign_id,
            expected_conditions=conditions,
            rows=rows,
            infrastructure_failures=infrastructure_failures,
            status="running",
        )
        log(
            log_path,
            "END "
            f"{condition.execution_index:03d}/{len(conditions)} {condition.key} "
            f"status={row['status']} matrix={row['matrix_time_sec']} "
            f"solver={row['solver_time_sec']} distance={row['mission_distance_km']}",
        )

    validate_completion(rows, conditions)
    normalize_text_tree(run_dir)

    manifest_csv, manifest_json, _manifest_rows = write_primary_manifest(
        rows=rows,
        run_id=run_id,
        campaign_id=campaign_id,
        run_dir=run_dir,
        record_paths=record_paths,
        dataset_manifest_hash=dataset_manifest_hash,
        environment_info=environment_info,
    )
    analysis_artifacts = write_analysis_outputs(
        rows=rows,
        run_id=run_id,
        campaign_id=campaign_id,
        run_dir=run_dir,
        manifest_csv=manifest_csv,
        manifest_json=manifest_json,
    )
    write_results_json(
        path=json_path,
        run_id=run_id,
        campaign_id=campaign_id,
        run_dir=run_dir,
        rows=rows,
        infrastructure_failures=infrastructure_failures,
        environment_info=environment_info,
        dataset_manifest_hash=dataset_manifest_hash,
    )
    final_status = "complete" if not infrastructure_failures else "complete_with_errors"
    write_progress(
        path=progress_path,
        run_id=run_id,
        campaign_id=campaign_id,
        expected_conditions=conditions,
        rows=rows,
        infrastructure_failures=infrastructure_failures,
        status=final_status,
    )
    write_json(
        run_dir / "campaign_artifacts.json",
        {
            "schema": "nfz_part2_primary_campaign_artifacts_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "run_directory": str(run_dir.relative_to(REPO_ROOT)),
            "results_csv": str(csv_path.relative_to(REPO_ROOT)),
            "results_json": str(json_path.relative_to(REPO_ROOT)),
            "results_jsonl": str(jsonl_path.relative_to(REPO_ROOT)),
            "progress_manifest": str(progress_path.relative_to(REPO_ROOT)),
            "execution_order": str(execution_order_path.relative_to(REPO_ROOT)),
            "primary_manifest_csv": str(manifest_csv.relative_to(REPO_ROOT)),
            "primary_manifest_json": str(manifest_json.relative_to(REPO_ROOT)),
            "analysis_artifacts": analysis_artifacts,
        },
    )
    log(
        log_path,
        f"COMPLETE status={final_status} completed={len(rows)}/{len(conditions)} "
        f"infrastructure_failures={len(infrastructure_failures)}",
    )
    print(f"run_id={run_id}")
    print(f"campaign_id={campaign_id}")
    print(f"run_dir={run_dir}")
    print(f"completed={len(rows)}")
    print(f"infrastructure_failures={len(infrastructure_failures)}")
    return 0 if not infrastructure_failures else 2


if __name__ == "__main__":
    raise SystemExit(run_campaign())
