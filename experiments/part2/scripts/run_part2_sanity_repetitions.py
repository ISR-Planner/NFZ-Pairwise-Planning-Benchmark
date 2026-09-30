"""Run the final Part II sanity-repetition campaign.

The campaign reruns only the six precommitted i03 conditions using the same
uninstrumented benchmark path as the frozen Part II primary run.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENTS_ROOT = REPO_ROOT / "experiments"
PART2_ROOT = EXPERIMENTS_ROOT / "part2"
SCRIPT_ROOT = PART2_ROOT / "scripts"
RESULTS_ROOT = PART2_ROOT / "results" / "sanity"
ANALYSIS_ROOT = PART2_ROOT / "analysis"
MANIFEST_ROOT = PART2_ROOT / "manifests"
PRIMARY_RUN_DIR = PART2_ROOT / "results" / "primary" / "run_01_20260812-194711"
PRIMARY_RECORDS_DIR = PRIMARY_RUN_DIR / "records"

STARTING_COMMIT = "12a21ecf614d8b261cd27b39665142c6fdbb006b"
FROZEN_PRIMARY_COMMIT = "ff7d3f36d7cbbcfb9cb9d2e1232e3feae33a5d85"
PART2_INFRASTRUCTURE_COMMIT = "1163ae8164f9ffe7ad60dc8cfd1dd7cebcfca0ba"
PART1_EXPERIMENT_COMMIT = "73b9a7b60fa892bbf2220e6a961c1393ab28fbf5"
DATASET_GENERATOR_COMMIT = "5f26eb8a5119af9854a5d49de3f900821701a689"

INSTANCE_ID = "i03"
EXPECTED_EXECUTIONS = 6
TOLERANCE_KM = 1e-6

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

METHODS = [
    "proposed",
    "visibility_graph",
]

CSV_FIELDS = [
    "run",
    "campaign_id",
    "execution_index",
    "environment_id",
    "topology",
    "topology_display",
    "instance_id",
    "seed",
    "method",
    "source_mission_file",
    "source_dataset_hash",
    "primary_record_path",
    "primary_output_mission_file",
    "repeat_output_mission_file",
    "primary_matrix_time_sec",
    "repeat_matrix_time_sec",
    "matrix_time_abs_delta_sec",
    "matrix_time_delta_percent",
    "primary_solver_time_sec",
    "repeat_solver_time_sec",
    "solver_time_abs_delta_sec",
    "solver_time_delta_percent",
    "solver_completed_match",
    "mission_feasible_match",
    "mission_success_match",
    "targets_serviced_match",
    "mission_distance_match",
    "failure_reason_match",
    "matrix_labels_match",
    "matrix_shape_match",
    "matrix_availability_match",
    "matrix_values_match",
    "path_outputs_match",
    "route_sequence_match",
    "functional_match",
    "mission_distance_delta_km",
    "max_matrix_distance_delta",
    "max_path_coordinate_delta",
    "primary_mission_distance_km",
    "repeat_mission_distance_km",
    "primary_failure_reason",
    "repeat_failure_reason",
    "qualitative_ordering_preserved",
    "timing_role",
    "status",
    "infrastructure_retry_flag",
    "error",
]

MANIFEST_FIELDS = [
    "environment_id",
    "topology",
    "instance_id",
    "seed",
    "method",
    "result_path",
    "result_sha256",
    "repeat_output_mission_file",
    "repeat_output_mission_sha256",
    "execution_status",
    "functional_match",
    "primary_matrix_time_sec",
    "repeat_matrix_time_sec",
    "matrix_time_abs_delta_sec",
    "matrix_time_delta_percent",
    "primary_solver_time_sec",
    "repeat_solver_time_sec",
    "solver_time_delta_percent",
    "mission_distance_delta_km",
    "max_matrix_distance_delta",
    "max_path_coordinate_delta",
    "qualitative_ordering_preserved",
    "git_commit",
    "frozen_primary_commit",
    "source_dataset_hash",
]

for path in (REPO_ROOT, EXPERIMENTS_ROOT, SCRIPT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_part2_primary as primary
from benchmark.native_io import load_native_environment
from benchmark.runner import run_one


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


def append_csv(path: Path, row: Dict[str, Any], fields: Sequence[str]) -> None:
    exists = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fields),
            extrasaction="ignore",
            lineterminator="\n",
        )
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def format_path(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def as_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def percent_delta(reference: Optional[float], repeat: Optional[float]) -> Optional[float]:
    if reference is None or repeat is None or reference == 0.0:
        return None
    return (repeat - reference) / reference * 100.0


def list_text(values: Iterable[Any]) -> str:
    return ";".join("" if value is None else str(value) for value in values)


def git_output(*args: str) -> str:
    return primary.git_output(*args)


def verify_preconditions() -> Dict[str, Any]:
    branch = git_output("branch", "--show-current")
    head = git_output("rev-parse", "HEAD")
    if branch != "benchmark-part2-generalization":
        raise RuntimeError(f"Unexpected branch: {branch}")
    if head != STARTING_COMMIT:
        raise RuntimeError(f"Unexpected HEAD: {head}")
    if not PRIMARY_RUN_DIR.exists():
        raise FileNotFoundError(PRIMARY_RUN_DIR)

    for path in (
        MANIFEST_ROOT / "part2_sanity_manifest.csv",
        MANIFEST_ROOT / "part2_sanity_manifest.json",
        ANALYSIS_ROOT / "PART2_SANITY_REPETITION_SUMMARY.md",
        ANALYSIS_ROOT / "part2_sanity_repetition_comparison.csv",
        ANALYSIS_ROOT / "part2_sanity_repetition_comparison.json",
    ):
        if path.exists():
            raise FileExistsError(f"Output already exists: {path}")

    environment_info = primary.collect_environment_info()
    primary.verify_execution_environment(environment_info)
    return {
        "branch": branch,
        "git_commit": head,
        "environment_info": environment_info,
    }


def load_and_verify_dataset_rows() -> List[Dict[str, Any]]:
    rows = primary.load_dataset_manifest()
    primary.verify_dataset_rows(rows)
    return rows


def build_conditions(rows: Sequence[Dict[str, Any]]) -> List[Condition]:
    by_key = {(row["topology"], row["instance_id"]): row for row in rows}
    conditions: List[Condition] = []
    execution_index = 0
    for topology in TOPOLOGY_ORDER:
        row = by_key[(topology, INSTANCE_ID)]
        for method in METHODS:
            execution_index += 1
            source_path = REPO_ROOT / row["relative_path"]
            conditions.append(
                Condition(
                    execution_index=execution_index,
                    environment_id=str(row["environment_id"]),
                    environment_filename=Path(row["relative_path"]).name,
                    topology=topology,
                    topology_display=TOPOLOGY_DISPLAY[topology],
                    instance_id=INSTANCE_ID,
                    seed=int(row["seed"]),
                    method=method,
                    source_path=source_path,
                    source_dataset_hash=str(row["sha256"]).upper(),
                    source_file_size_bytes=int(row["file_size_bytes"]),
                )
            )
    if len(conditions) != EXPECTED_EXECUTIONS:
        raise RuntimeError(f"Expected {EXPECTED_EXECUTIONS} conditions, found {len(conditions)}")
    if any(condition.method == "proposed_parallel" for condition in conditions):
        raise RuntimeError("proposed_parallel is forbidden for sanity repetitions")
    return conditions


def primary_record_path(condition: Condition) -> Path:
    return PRIMARY_RECORDS_DIR / f"{condition.environment_id}__{condition.method}.json"


def load_primary_record(condition: Condition) -> Dict[str, Any]:
    path = primary_record_path(condition)
    row = json.loads(path.read_text(encoding="utf-8"))
    if row["environment_id"] != condition.environment_id or row["method"] != condition.method:
        raise RuntimeError(f"Primary record mismatch for {condition.key}")
    if str(row["source_dataset_hash"]).upper() != condition.source_dataset_hash:
        raise RuntimeError(f"Primary dataset hash mismatch for {condition.key}")
    return row


def load_mission_doc(path_text: str) -> Dict[str, Any]:
    raw_path = Path(path_text)
    path = raw_path if raw_path.is_absolute() else REPO_ROOT / raw_path
    return json.loads(path.read_text(encoding="utf-8"))


def point_distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1]))


def compare_matrices(reference: Dict[str, Any], repeat: Dict[str, Any]) -> Dict[str, Any]:
    labels_ref = [str(label) for label in reference.get("labels", [])]
    labels_repeat = [str(label) for label in repeat.get("labels", [])]
    matrix_ref = reference.get("matrix", [])
    matrix_repeat = repeat.get("matrix", [])
    shape_ref = [len(matrix_ref), len(matrix_ref[0]) if matrix_ref else 0]
    shape_repeat = [len(matrix_repeat), len(matrix_repeat[0]) if matrix_repeat else 0]
    unavailable = 99999.0
    differing_availability: List[str] = []
    differing_values: List[str] = []
    max_delta = 0.0

    if labels_ref == labels_repeat and shape_ref == shape_repeat:
        for i, source in enumerate(labels_ref):
            for j, destination in enumerate(labels_ref):
                if i == j:
                    continue
                ref_val = float(matrix_ref[i][j])
                repeat_val = float(matrix_repeat[i][j])
                key = f"{source}->{destination}"
                delta = abs(ref_val - repeat_val)
                max_delta = max(max_delta, delta)
                if (ref_val < unavailable) != (repeat_val < unavailable):
                    differing_availability.append(key)
                if delta > TOLERANCE_KM:
                    differing_values.append(key)

    return {
        "labels_match": labels_ref == labels_repeat,
        "shape_match": shape_ref == shape_repeat,
        "availability_match": not differing_availability,
        "values_match": not differing_values and labels_ref == labels_repeat and shape_ref == shape_repeat,
        "max_matrix_distance_delta": max_delta,
        "differing_availability": differing_availability,
        "differing_values": differing_values,
    }


def compare_paths(reference: Dict[str, Any], repeat: Dict[str, Any]) -> Dict[str, Any]:
    paths_ref = reference.get("paths", {}) or {}
    paths_repeat = repeat.get("paths", {}) or {}
    keys_match = set(paths_ref) == set(paths_repeat)
    differing_paths: List[str] = []
    max_delta = 0.0
    for key in sorted(set(paths_ref) | set(paths_repeat)):
        ref_path = paths_ref.get(key)
        repeat_path = paths_repeat.get(key)
        if ref_path is None or repeat_path is None:
            differing_paths.append(key)
            continue
        if len(ref_path) != len(repeat_path):
            differing_paths.append(key)
            continue
        for ref_point, repeat_point in zip(ref_path, repeat_path):
            delta = point_distance(ref_point, repeat_point)
            max_delta = max(max_delta, delta)
            if delta > TOLERANCE_KM:
                differing_paths.append(key)
                break
    return {
        "path_outputs_match": keys_match and not differing_paths,
        "path_keys_match": keys_match,
        "max_path_coordinate_delta": max_delta,
        "differing_paths": differing_paths,
    }


def route_sequence(doc: Dict[str, Any]) -> str:
    routes = (doc.get("solution") or {}).get("routes") or {}
    route_data = routes.get("1") or routes.get(1) or routes.get("D1") or {}
    return ",".join(str(node) for node in route_data.get("route", []))


def read_last_summary_row(output_dir: Path) -> Dict[str, Any]:
    summary_path = output_dir / "benchmark_summary.jsonl"
    lines = [line for line in summary_path.read_text(encoding="utf-8").splitlines() if line]
    return json.loads(lines[-1])


def timing_role(row: Dict[str, Any], paired_row: Dict[str, Any]) -> str:
    if float(row["repeat_matrix_time_sec"]) < float(paired_row["repeat_matrix_time_sec"]):
        return "faster"
    if float(row["repeat_matrix_time_sec"]) > float(paired_row["repeat_matrix_time_sec"]):
        return "slower"
    return "tie"


def apply_ordering_preservation(rows: List[Dict[str, Any]]) -> None:
    for topology in TOPOLOGY_ORDER:
        proposed = next(row for row in rows if row["topology"] == topology and row["method"] == "proposed")
        vg = next(row for row in rows if row["topology"] == topology and row["method"] == "visibility_graph")
        primary_proposed_faster = float(proposed["primary_matrix_time_sec"]) < float(vg["primary_matrix_time_sec"])
        repeat_proposed_faster = float(proposed["repeat_matrix_time_sec"]) < float(vg["repeat_matrix_time_sec"])
        preserved = primary_proposed_faster == repeat_proposed_faster
        proposed["qualitative_ordering_preserved"] = preserved
        vg["qualitative_ordering_preserved"] = preserved
        proposed["timing_role"] = timing_role(proposed, vg)
        vg["timing_role"] = timing_role(vg, proposed)


def build_comparison_row(
    *,
    run_id: str,
    campaign_id: str,
    condition: Condition,
    primary_record: Dict[str, Any],
    repeat_summary: Dict[str, Any],
    repeat_mission_path: Path,
    primary_doc: Dict[str, Any],
    repeat_doc: Dict[str, Any],
) -> Dict[str, Any]:
    primary_matrix = primary_doc["solution"]["distance_matrix"]
    repeat_matrix = repeat_doc["solution"]["distance_matrix"]
    matrix_comparison = compare_matrices(primary_matrix, repeat_matrix)
    path_comparison = compare_paths(primary_matrix, repeat_matrix)

    primary_matrix_time = float(primary_record["matrix_time_sec"])
    repeat_matrix_time = as_float(repeat_summary.get("matrix_build_time_seconds"))
    primary_solver_time = float(primary_record["solver_time_sec"])
    repeat_solver_time = as_float(repeat_summary.get("solver_time_seconds"))
    primary_distance = float(primary_record["mission_distance_km"])
    repeat_distance = float(repeat_summary.get("route_distance") or 0.0)
    mission_distance_delta = abs(primary_distance - repeat_distance)

    solver_completed_match = as_bool(primary_record["solver_completed"]) == as_bool(repeat_summary["solver_completed"])
    mission_feasible_match = as_bool(primary_record["mission_feasible"]) == as_bool(repeat_summary["mission_feasible"])
    mission_success_match = as_bool(primary_record["mission_success"]) == as_bool(repeat_summary["mission_success"])
    targets_serviced_match = int(primary_record["targets_serviced"]) == int(repeat_summary["targets_serviced"])
    failure_reason_match = (primary_record.get("failure_reason") or None) == (repeat_summary.get("failure_reason") or None)
    route_match = route_sequence(primary_doc) == route_sequence(repeat_doc)
    functional_match = (
        solver_completed_match
        and mission_feasible_match
        and mission_success_match
        and targets_serviced_match
        and mission_distance_delta <= TOLERANCE_KM
        and failure_reason_match
        and matrix_comparison["labels_match"]
        and matrix_comparison["shape_match"]
        and matrix_comparison["availability_match"]
        and matrix_comparison["values_match"]
        and path_comparison["path_outputs_match"]
        and route_match
    )

    return {
        "run": run_id,
        "campaign_id": campaign_id,
        "execution_index": condition.execution_index,
        "environment_id": condition.environment_id,
        "topology": condition.topology,
        "topology_display": condition.topology_display,
        "instance_id": condition.instance_id,
        "seed": condition.seed,
        "method": condition.method,
        "source_mission_file": format_path(condition.source_path),
        "source_dataset_hash": condition.source_dataset_hash,
        "primary_record_path": format_path(primary_record_path(condition)),
        "primary_output_mission_file": primary_record["output_mission_file"],
        "repeat_output_mission_file": format_path(repeat_mission_path),
        "primary_matrix_time_sec": primary_matrix_time,
        "repeat_matrix_time_sec": repeat_matrix_time,
        "matrix_time_abs_delta_sec": abs(float(repeat_matrix_time) - primary_matrix_time) if repeat_matrix_time is not None else None,
        "matrix_time_delta_percent": percent_delta(primary_matrix_time, repeat_matrix_time),
        "primary_solver_time_sec": primary_solver_time,
        "repeat_solver_time_sec": repeat_solver_time,
        "solver_time_abs_delta_sec": abs(float(repeat_solver_time) - primary_solver_time) if repeat_solver_time is not None else None,
        "solver_time_delta_percent": percent_delta(primary_solver_time, repeat_solver_time),
        "solver_completed_match": solver_completed_match,
        "mission_feasible_match": mission_feasible_match,
        "mission_success_match": mission_success_match,
        "targets_serviced_match": targets_serviced_match,
        "mission_distance_match": mission_distance_delta <= TOLERANCE_KM,
        "failure_reason_match": failure_reason_match,
        "matrix_labels_match": matrix_comparison["labels_match"],
        "matrix_shape_match": matrix_comparison["shape_match"],
        "matrix_availability_match": matrix_comparison["availability_match"],
        "matrix_values_match": matrix_comparison["values_match"],
        "path_outputs_match": path_comparison["path_outputs_match"],
        "route_sequence_match": route_match,
        "functional_match": functional_match,
        "mission_distance_delta_km": mission_distance_delta,
        "max_matrix_distance_delta": matrix_comparison["max_matrix_distance_delta"],
        "max_path_coordinate_delta": path_comparison["max_path_coordinate_delta"],
        "primary_mission_distance_km": primary_distance,
        "repeat_mission_distance_km": repeat_distance,
        "primary_failure_reason": primary_record.get("failure_reason"),
        "repeat_failure_reason": repeat_summary.get("failure_reason"),
        "qualitative_ordering_preserved": None,
        "timing_role": None,
        "status": "success" if functional_match else "functional_mismatch",
        "infrastructure_retry_flag": False,
        "error": repeat_summary.get("error"),
    }


def write_progress(
    *,
    path: Path,
    run_id: str,
    campaign_id: str,
    conditions: Sequence[Condition],
    rows: Sequence[Dict[str, Any]],
    infrastructure_failures: Sequence[Dict[str, Any]],
    functional_mismatches: Sequence[Dict[str, Any]],
    status: str,
    current: Optional[Condition] = None,
) -> None:
    completed = {row["environment_id"] + "__" + row["method"] for row in rows}
    pending = [condition.key for condition in conditions if condition.key not in completed]
    write_json(
        path,
        {
            "schema": "nfz_part2_sanity_progress_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "status": status,
            "updated_at": now_iso(),
            "expected_executions": len(conditions),
            "completed_executions": len(rows),
            "pending_executions": len(pending),
            "pending_condition_keys": pending,
            "current_condition_key": current.key if current else None,
            "infrastructure_failure_count": len(infrastructure_failures),
            "functional_mismatch_count": len(functional_mismatches),
            "infrastructure_failures": list(infrastructure_failures),
            "functional_mismatches": list(functional_mismatches),
            "diagnostics_enabled": False,
            "primary_campaign_rerun": False,
            "sanity_repetitions": len(rows),
        },
    )


def log_message(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{now_iso()} {message}\n")


def validate_completion(rows: Sequence[Dict[str, Any]], conditions: Sequence[Condition]) -> None:
    if len(rows) != EXPECTED_EXECUTIONS:
        raise RuntimeError(f"Expected {EXPECTED_EXECUTIONS} rows, found {len(rows)}")
    expected_keys = {condition.key for condition in conditions}
    observed_keys = {row["environment_id"] + "__" + row["method"] for row in rows}
    if observed_keys != expected_keys:
        raise RuntimeError(f"Unexpected completed key set: {observed_keys}")
    if any(not row["functional_match"] for row in rows):
        raise RuntimeError("Functional mismatch detected")
    if any(row["method"] == "proposed_parallel" for row in rows):
        raise RuntimeError("proposed_parallel appeared in sanity rows")


def write_manifest(
    *,
    run_id: str,
    campaign_id: str,
    run_dir: Path,
    rows: Sequence[Dict[str, Any]],
    record_paths: Dict[str, Path],
    environment_info: Dict[str, Any],
    dataset_manifest_hash: str,
) -> Tuple[Path, Path]:
    manifest_rows: List[Dict[str, Any]] = []
    for row in rows:
        key = row["environment_id"] + "__" + row["method"]
        result_path = record_paths[key]
        mission_path = REPO_ROOT / row["repeat_output_mission_file"]
        manifest_rows.append(
            {
                "environment_id": row["environment_id"],
                "topology": row["topology"],
                "instance_id": row["instance_id"],
                "seed": row["seed"],
                "method": row["method"],
                "result_path": format_path(result_path),
                "result_sha256": sha256(result_path),
                "repeat_output_mission_file": row["repeat_output_mission_file"],
                "repeat_output_mission_sha256": sha256(mission_path),
                "execution_status": row["status"],
                "functional_match": row["functional_match"],
                "primary_matrix_time_sec": row["primary_matrix_time_sec"],
                "repeat_matrix_time_sec": row["repeat_matrix_time_sec"],
                "matrix_time_abs_delta_sec": row["matrix_time_abs_delta_sec"],
                "matrix_time_delta_percent": row["matrix_time_delta_percent"],
                "primary_solver_time_sec": row["primary_solver_time_sec"],
                "repeat_solver_time_sec": row["repeat_solver_time_sec"],
                "solver_time_delta_percent": row["solver_time_delta_percent"],
                "mission_distance_delta_km": row["mission_distance_delta_km"],
                "max_matrix_distance_delta": row["max_matrix_distance_delta"],
                "max_path_coordinate_delta": row["max_path_coordinate_delta"],
                "qualitative_ordering_preserved": row["qualitative_ordering_preserved"],
                "git_commit": STARTING_COMMIT,
                "frozen_primary_commit": FROZEN_PRIMARY_COMMIT,
                "source_dataset_hash": row["source_dataset_hash"],
            }
        )

    manifest_csv = MANIFEST_ROOT / "part2_sanity_manifest.csv"
    manifest_json = MANIFEST_ROOT / "part2_sanity_manifest.json"
    write_csv(manifest_csv, manifest_rows, MANIFEST_FIELDS)
    write_json(
        manifest_json,
        {
            "schema": "nfz_part2_sanity_manifest_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "run_directory": format_path(run_dir),
            "created_at": now_iso(),
            "expected_executions": EXPECTED_EXECUTIONS,
            "completed_executions": len(rows),
            "dataset_manifest": format_path(primary.DATASET_MANIFEST_PATH),
            "dataset_manifest_hash": dataset_manifest_hash,
            "environment_info": environment_info,
            "diagnostics_enabled": False,
            "rows": manifest_rows,
        },
    )
    return manifest_csv, manifest_json


def write_markdown_summary(
    *,
    path: Path,
    run_id: str,
    campaign_id: str,
    run_dir: Path,
    rows: Sequence[Dict[str, Any]],
    manifest_csv: Path,
    manifest_json: Path,
) -> None:
    lines: List[str] = [
        "# Part II Sanity Repetition Summary",
        "",
        "These six repetitions use the uninstrumented primary benchmark path. They are a reproducibility sanity check, not a new statistical sample.",
        "",
        "## Campaign",
        "",
        f"- Run: `{run_id}`",
        f"- Campaign ID: `{campaign_id}`",
        f"- Campaign directory: `{format_path(run_dir)}`",
        f"- Expected executions: `{EXPECTED_EXECUTIONS}`",
        f"- Completed executions: `{len(rows)}`",
        f"- Functional mismatches: `{sum(1 for row in rows if not row['functional_match'])}`",
        f"- Diagnostics enabled: `NO`",
        f"- Manifest CSV: `{format_path(manifest_csv)}`",
        f"- Manifest JSON: `{format_path(manifest_json)}`",
        "",
        "## Six-Row Comparison",
        "",
        "| topology | method | primary matrix s | repeat matrix s | delta % | primary distance km | repeat distance km | functional match | ordering preserved |",
        "|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in sorted(rows, key=lambda item: (TOPOLOGY_ORDER.index(item["topology"]), METHODS.index(item["method"]))):
        delta_pct = row["matrix_time_delta_percent"]
        delta_text = "NA" if delta_pct is None else f"{float(delta_pct):.2f}"
        lines.append(
            "| {topology_display} | {method} | {primary_matrix_time_sec:.6f} | {repeat_matrix_time_sec:.6f} | {delta} | {primary_mission_distance_km:.6f} | {repeat_mission_distance_km:.6f} | {functional_match} | {qualitative_ordering_preserved} |".format(
                delta=delta_text,
                **row,
            )
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Timing differences are descriptive only, especially for short C-Trap Proposed runtimes.",
            "- Mission distance, matrix values, path outputs, and route sequence matched the frozen primary outputs within the configured tolerance.",
            "- No diagnostic counters, branch tracing, or `proposed_parallel` executions were used.",
            "",
            "## Guardrails",
            "",
            "- Part I files modified: `NO`",
            "- Part II datasets modified: `NO`",
            "- Primary results modified: `NO`",
            "- Diagnostic results modified: `NO`",
            "",
        ]
    )
    write_text_lf(path, "\n".join(lines))


def write_analysis_outputs(
    *,
    run_id: str,
    campaign_id: str,
    run_dir: Path,
    rows: Sequence[Dict[str, Any]],
    manifest_csv: Path,
    manifest_json: Path,
) -> Dict[str, str]:
    comparison_csv = ANALYSIS_ROOT / "part2_sanity_repetition_comparison.csv"
    comparison_json = ANALYSIS_ROOT / "part2_sanity_repetition_comparison.json"
    markdown = ANALYSIS_ROOT / "PART2_SANITY_REPETITION_SUMMARY.md"
    write_csv(comparison_csv, rows, CSV_FIELDS)
    write_json(
        comparison_json,
        {
            "schema": "nfz_part2_sanity_repetition_comparison_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "rows": list(rows),
        },
    )
    write_markdown_summary(
        path=markdown,
        run_id=run_id,
        campaign_id=campaign_id,
        run_dir=run_dir,
        rows=rows,
        manifest_csv=manifest_csv,
        manifest_json=manifest_json,
    )
    return {
        "comparison_csv": format_path(comparison_csv),
        "comparison_json": format_path(comparison_json),
        "markdown_summary": format_path(markdown),
    }


def normalize_text_tree(root: Path) -> None:
    for suffix in (".csv", ".json", ".jsonl", ".md", ".log", ".txt"):
        for path in root.rglob(f"*{suffix}"):
            text = path.read_text(encoding="utf-8")
            path.write_text(text, encoding="utf-8", newline="\n")


def run_campaign() -> int:
    preconditions = verify_preconditions()
    dataset_rows = load_and_verify_dataset_rows()
    conditions = build_conditions(dataset_rows)
    dataset_manifest_hash = sha256(primary.DATASET_MANIFEST_PATH)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_id = f"run_01_{timestamp}"
    campaign_id = f"part2_sanity_repetition_{timestamp}"
    run_dir = RESULTS_ROOT / run_id
    if run_dir.exists():
        raise FileExistsError(run_dir)

    records_dir = run_dir / "records"
    outputs_dir = run_dir / "outputs"
    logs_dir = run_dir / "logs"
    log_path = logs_dir / f"{campaign_id}.log"
    progress_path = run_dir / "campaign_status.json"
    csv_path = run_dir / f"{campaign_id}.csv"
    json_path = run_dir / f"{campaign_id}.json"
    jsonl_path = run_dir / f"{campaign_id}_rows.jsonl"

    run_dir.mkdir(parents=True, exist_ok=False)
    write_json(
        run_dir / "execution_order.json",
        {
            "schema": "nfz_part2_sanity_execution_order_v1",
            "order": "for each topology, run proposed then visibility_graph for instance i03",
            "instance_id": INSTANCE_ID,
            "methods": METHODS,
            "conditions": [
                {
                    "execution_index": condition.execution_index,
                    "environment_id": condition.environment_id,
                    "topology": condition.topology,
                    "instance_id": condition.instance_id,
                    "seed": condition.seed,
                    "method": condition.method,
                    "source_mission_file": format_path(condition.source_path),
                }
                for condition in conditions
            ],
        },
    )
    write_json(
        run_dir / "environment_provenance.json",
        {
            "schema": "nfz_part2_sanity_environment_provenance_v1",
            "branch": preconditions["branch"],
            "git_commit": preconditions["git_commit"],
            "frozen_primary_commit": FROZEN_PRIMARY_COMMIT,
            "part2_infrastructure_commit": PART2_INFRASTRUCTURE_COMMIT,
            "part1_experiment_commit": PART1_EXPERIMENT_COMMIT,
            "dataset_generator_commit": DATASET_GENERATOR_COMMIT,
            "dataset_manifest": format_path(primary.DATASET_MANIFEST_PATH),
            "dataset_manifest_hash": dataset_manifest_hash,
            "environment_info": preconditions["environment_info"],
            "execution_mode": "primary_uninstrumented",
            "diagnostics_enabled": False,
            "proposed_parallel_executions": 0,
        },
    )

    rows: List[Dict[str, Any]] = []
    record_paths: Dict[str, Path] = {}
    infrastructure_failures: List[Dict[str, Any]] = []
    functional_mismatches: List[Dict[str, Any]] = []
    write_progress(
        path=progress_path,
        run_id=run_id,
        campaign_id=campaign_id,
        conditions=conditions,
        rows=rows,
        infrastructure_failures=infrastructure_failures,
        functional_mismatches=functional_mismatches,
        status="running",
    )
    log_message(log_path, f"START campaign={campaign_id} expected={len(conditions)}")

    for condition in conditions:
        log_message(log_path, f"START {condition.execution_index:02d}/{len(conditions)} {condition.key}")
        write_progress(
            path=progress_path,
            run_id=run_id,
            campaign_id=campaign_id,
            conditions=conditions,
            rows=rows,
            infrastructure_failures=infrastructure_failures,
            functional_mismatches=functional_mismatches,
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
            repeat_summary = read_last_summary_row(output_dir)
            repeat_mission_path = Path(result.output_mission_json) if result.output_mission_json else None
            if repeat_mission_path is None:
                raise RuntimeError(f"No repeat mission output for {condition.key}")
            primary_record = load_primary_record(condition)
            primary_doc = load_mission_doc(primary_record["output_mission_file"])
            repeat_doc = json.loads(repeat_mission_path.read_text(encoding="utf-8"))
            row = build_comparison_row(
                run_id=run_id,
                campaign_id=campaign_id,
                condition=condition,
                primary_record=primary_record,
                repeat_summary=repeat_summary,
                repeat_mission_path=repeat_mission_path,
                primary_doc=primary_doc,
                repeat_doc=repeat_doc,
            )
            if not row["functional_match"]:
                functional_mismatches.append(row)
                write_progress(
                    path=progress_path,
                    run_id=run_id,
                    campaign_id=campaign_id,
                    conditions=conditions,
                    rows=rows,
                    infrastructure_failures=infrastructure_failures,
                    functional_mismatches=functional_mismatches,
                    status="failed_functional_mismatch",
                    current=condition,
                )
                raise RuntimeError(f"Functional mismatch for {condition.key}: {row}")
        except Exception as exc:
            if functional_mismatches:
                raise
            failure = {
                "condition_key": condition.key,
                "environment_id": condition.environment_id,
                "method": condition.method,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
                "time": now_iso(),
                "retry_performed": False,
            }
            infrastructure_failures.append(failure)
            write_progress(
                path=progress_path,
                run_id=run_id,
                campaign_id=campaign_id,
                conditions=conditions,
                rows=rows,
                infrastructure_failures=infrastructure_failures,
                functional_mismatches=functional_mismatches,
                status="failed_infrastructure",
                current=condition,
            )
            raise

        rows.append(row)
        record_path = records_dir / f"{condition.key}__sanity.json"
        write_json(record_path, row)
        record_paths[condition.key] = record_path
        append_csv(csv_path, row, CSV_FIELDS)
        append_jsonl(jsonl_path, row)
        write_json(
            json_path,
            {
                "schema": "nfz_part2_sanity_results_v1",
                "run": run_id,
                "campaign_id": campaign_id,
                "rows": rows,
                "infrastructure_failures": infrastructure_failures,
                "functional_mismatches": functional_mismatches,
            },
        )
        write_progress(
            path=progress_path,
            run_id=run_id,
            campaign_id=campaign_id,
            conditions=conditions,
            rows=rows,
            infrastructure_failures=infrastructure_failures,
            functional_mismatches=functional_mismatches,
            status="running",
        )
        log_message(
            log_path,
            "END "
            f"{condition.key} primary_matrix={row['primary_matrix_time_sec']} "
            f"repeat_matrix={row['repeat_matrix_time_sec']} "
            f"functional_match={row['functional_match']}",
        )

    apply_ordering_preservation(rows)
    for row in rows:
        record_path = record_paths[row["environment_id"] + "__" + row["method"]]
        write_json(record_path, row)
    write_csv(csv_path, rows, CSV_FIELDS)
    write_text_lf(
        jsonl_path,
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
    )
    write_json(
        json_path,
        {
            "schema": "nfz_part2_sanity_results_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "rows": rows,
            "infrastructure_failures": infrastructure_failures,
            "functional_mismatches": functional_mismatches,
        },
    )
    validate_completion(rows, conditions)
    normalize_text_tree(run_dir)

    manifest_csv, manifest_json = write_manifest(
        run_id=run_id,
        campaign_id=campaign_id,
        run_dir=run_dir,
        rows=rows,
        record_paths=record_paths,
        environment_info=preconditions["environment_info"],
        dataset_manifest_hash=dataset_manifest_hash,
    )
    analysis_artifacts = write_analysis_outputs(
        run_id=run_id,
        campaign_id=campaign_id,
        run_dir=run_dir,
        rows=rows,
        manifest_csv=manifest_csv,
        manifest_json=manifest_json,
    )
    write_json(
        run_dir / "campaign_artifacts.json",
        {
            "schema": "nfz_part2_sanity_campaign_artifacts_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "run_directory": format_path(run_dir),
            "results_csv": format_path(csv_path),
            "results_json": format_path(json_path),
            "results_jsonl": format_path(jsonl_path),
            "progress_manifest": format_path(progress_path),
            "execution_order": format_path(run_dir / "execution_order.json"),
            "sanity_manifest_csv": format_path(manifest_csv),
            "sanity_manifest_json": format_path(manifest_json),
            "analysis_artifacts": analysis_artifacts,
        },
    )
    write_progress(
        path=progress_path,
        run_id=run_id,
        campaign_id=campaign_id,
        conditions=conditions,
        rows=rows,
        infrastructure_failures=infrastructure_failures,
        functional_mismatches=functional_mismatches,
        status="complete",
    )
    log_message(log_path, f"COMPLETE completed={len(rows)} infrastructure_failures={len(infrastructure_failures)}")

    print(f"run_id={run_id}")
    print(f"campaign_id={campaign_id}")
    print(f"run_dir={run_dir}")
    print(f"completed={len(rows)}")
    print(f"infrastructure_failures={len(infrastructure_failures)}")
    print(f"functional_mismatches={len(functional_mismatches)}")
    return 0


def finalize_existing_run(run_dir: Path) -> int:
    """Finish manifests and summaries from already-saved six-row results."""

    json_files = sorted(run_dir.glob("part2_sanity_repetition_*.json"))
    if len(json_files) != 1:
        raise RuntimeError(f"Expected one sanity results JSON in {run_dir}, found {len(json_files)}")
    json_path = json_files[0]
    campaign_id = json_path.stem
    run_id = run_dir.name
    csv_path = run_dir / f"{campaign_id}.csv"
    jsonl_path = run_dir / f"{campaign_id}_rows.jsonl"
    progress_path = run_dir / "campaign_status.json"
    record_paths = {
        path.name.replace("__sanity.json", ""): path
        for path in (run_dir / "records").glob("*__sanity.json")
    }

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    rows = list(payload["rows"])
    if len(rows) != EXPECTED_EXECUTIONS:
        raise RuntimeError(f"Expected {EXPECTED_EXECUTIONS} saved rows, found {len(rows)}")

    conditions = build_conditions(load_and_verify_dataset_rows())
    apply_ordering_preservation(rows)
    validate_completion(rows, conditions)

    for row in rows:
        key = row["environment_id"] + "__" + row["method"]
        write_json(record_paths[key], row)
    write_csv(csv_path, rows, CSV_FIELDS)
    write_text_lf(
        jsonl_path,
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
    )
    write_json(
        json_path,
        {
            "schema": "nfz_part2_sanity_results_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "rows": rows,
            "infrastructure_failures": payload.get("infrastructure_failures", []),
            "functional_mismatches": payload.get("functional_mismatches", []),
        },
    )
    normalize_text_tree(run_dir)

    environment_info = primary.collect_environment_info()
    dataset_manifest_hash = sha256(primary.DATASET_MANIFEST_PATH)
    manifest_csv, manifest_json = write_manifest(
        run_id=run_id,
        campaign_id=campaign_id,
        run_dir=run_dir,
        rows=rows,
        record_paths=record_paths,
        environment_info=environment_info,
        dataset_manifest_hash=dataset_manifest_hash,
    )
    analysis_artifacts = write_analysis_outputs(
        run_id=run_id,
        campaign_id=campaign_id,
        run_dir=run_dir,
        rows=rows,
        manifest_csv=manifest_csv,
        manifest_json=manifest_json,
    )
    write_json(
        run_dir / "campaign_artifacts.json",
        {
            "schema": "nfz_part2_sanity_campaign_artifacts_v1",
            "run": run_id,
            "campaign_id": campaign_id,
            "run_directory": format_path(run_dir),
            "results_csv": format_path(csv_path),
            "results_json": format_path(json_path),
            "results_jsonl": format_path(jsonl_path),
            "progress_manifest": format_path(progress_path),
            "execution_order": format_path(run_dir / "execution_order.json"),
            "sanity_manifest_csv": format_path(manifest_csv),
            "sanity_manifest_json": format_path(manifest_json),
            "analysis_artifacts": analysis_artifacts,
            "finalized_from_saved_rows": True,
        },
    )
    write_progress(
        path=progress_path,
        run_id=run_id,
        campaign_id=campaign_id,
        conditions=conditions,
        rows=rows,
        infrastructure_failures=payload.get("infrastructure_failures", []),
        functional_mismatches=payload.get("functional_mismatches", []),
        status="complete",
    )
    print(f"finalized_run={run_id}")
    print(f"campaign_id={campaign_id}")
    print(f"rows={len(rows)}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--finalize-run":
        raise SystemExit(finalize_existing_run(Path(sys.argv[2]).resolve()))
    raise SystemExit(run_campaign())
