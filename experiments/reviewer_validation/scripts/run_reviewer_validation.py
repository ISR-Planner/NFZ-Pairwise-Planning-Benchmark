"""Run Paper I reviewer-validation supplemental campaigns.

This script intentionally writes only under ``experiments/reviewer_validation``
and ``paper_ieee_revF_full``. It reuses the frozen benchmark harness semantics
for matrix injection and mission solving.
"""

from __future__ import annotations

import contextlib
import copy
import csv
import ctypes
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENTS_ROOT = REPO_ROOT / "experiments"
RV_ROOT = EXPERIMENTS_ROOT / "reviewer_validation"
RESULTS_ROOT = RV_ROOT / "results"
ANALYSIS_ROOT = RV_ROOT / "analysis"
FIGURES_ROOT = RV_ROOT / "figures"
VALIDATION_ROOT = RV_ROOT / "validation"
PAPER_REVF_ROOT = REPO_ROOT / "paper_ieee_revF_full"
PART2_MANIFEST = EXPERIMENTS_ROOT / "part2" / "manifests" / "part2_dataset_manifest.json"
PART2_PRIMARY_RECORDS = (
    EXPERIMENTS_ROOT
    / "part2"
    / "results"
    / "primary"
    / "run_01_20260812-194711"
    / "records"
)
PART2_PRIMARY_CSV = (
    EXPERIMENTS_ROOT
    / "part2"
    / "results"
    / "primary"
    / "run_01_20260812-194711"
    / "part2_generalization_primary_20260812-194711.csv"
)
PART1_RUN1_CSV = EXPERIMENTS_ROOT / "results" / "main_benchmark_run_20260809-160107.csv"
PART1_RUN2_CSV = (
    EXPERIMENTS_ROOT
    / "main_benchmark_replications"
    / "run_02_20260810-015756"
    / "results"
    / "main_benchmark_run_02_20260810-015756.csv"
)
COMPOSITE_RUN1_CSV = (
    EXPERIMENTS_ROOT
    / "composite_adversarial_replications"
    / "run_01_20260809-183402"
    / "results"
    / "composite_adversarial_run_01_20260809-183402.csv"
)
COMPOSITE_RUN2_CSV = (
    EXPERIMENTS_ROOT
    / "composite_adversarial_replications"
    / "run_02_20260809-222140"
    / "results"
    / "composite_adversarial_run_02_20260809-222140.csv"
)

BASE_COMMIT = "3683ea5727a8c2a3b67ddd1ef025e8f3fc6c2bf8"
BRANCH = "paper1-reviewer-validation"
UNAVAILABLE_COST = 99999.0
EPS = 1e-9

TOPOLOGY_ORDER = ["c_trap", "sequential_staggered_blocking", "asymmetric_corridor"]
TOPOLOGY_DISPLAY = {
    "c_trap": "C-Trap",
    "sequential_staggered_blocking": "Sequential Staggered Blocking",
    "asymmetric_corridor": "Asymmetric Corridor",
}
I03_ENV_IDS = ["ctrap_i03_t12", "sequential_i03_t12", "asymmetric_i03_t12"]
VG_RESOLUTIONS = [24, 48, 72, 144]
GRID_RESOLUTIONS = [0.25, 0.5, 1.0, 2.0]
HF_PAIRS = [("A1", "T1"), ("T3", "T8"), ("T6", "T12")]

for path in (REPO_ROOT, EXPERIMENTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from benchmark.matrix_builders import DEFAULT_PLANNER_ROOT, MatrixBuild
from benchmark.native_io import build_mission_document, load_native_environment, mission_filename
from benchmark.planner_bridge import prebuilt_matrix_cache, prepare_solver
from benchmark.runner import _mission_status, _single_drone_configs


Point = Tuple[float, float]


@dataclass(frozen=True)
class DatasetRow:
    environment_id: str
    topology: str
    instance_id: str
    seed: int
    relative_path: str
    sha256: str

    @property
    def path(self) -> Path:
        return REPO_ROOT / self.relative_path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, payload: Any) -> None:
    write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_csv(path: Path, rows: Sequence[Dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("/", "\\")


def git_output(*args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=REPO_ROOT, check=True, capture_output=True, text=True)
    return completed.stdout.strip()


def cpu_name_from_registry() -> Optional[str]:
    if os.name != "nt":
        return None
    try:
        import winreg

        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
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
        "timer": "time.perf_counter",
        "thread_behavior": "single Python process; no explicit worker pool for reviewer-validation wrappers",
        "process_reuse": "one process for this campaign script",
        "garbage_collection_policy": "default CPython garbage collection",
        "background_process_policy": "no benchmark-specific background workers launched",
        "cpu_affinity_policy": "not modified by script",
    }


def verify_preconditions() -> Dict[str, Any]:
    branch = git_output("branch", "--show-current")
    head = git_output("rev-parse", "HEAD")
    if branch != BRANCH:
        raise RuntimeError(f"expected branch {BRANCH}, found {branch}")
    if head != BASE_COMMIT:
        raise RuntimeError(f"expected HEAD {BASE_COMMIT}, found {head}")
    for required in (
        RV_ROOT / "EXPERIMENT_PLAN.md",
        RV_ROOT / "common_solver_spec.md",
    ):
        if not required.exists():
            raise FileNotFoundError(required)
    return {"branch": branch, "git_commit": head, "environment_info": collect_environment_info()}


def load_dataset_rows() -> List[DatasetRow]:
    data = json.loads(PART2_MANIFEST.read_text(encoding="utf-8"))
    rows = [
        DatasetRow(
            environment_id=str(row["environment_id"]),
            topology=str(row["topology"]),
            instance_id=str(row["instance_id"]),
            seed=int(row["seed"]),
            relative_path=str(row["relative_path"]),
            sha256=str(row["sha256"]).upper(),
        )
        for row in data["rows"]
    ]
    expected = {(topology, f"i{i:02d}") for topology in TOPOLOGY_ORDER for i in range(1, 6)}
    observed = {(row.topology, row.instance_id) for row in rows}
    if observed != expected:
        raise RuntimeError(f"unexpected Part II dataset set: {observed}")
    for row in rows:
        if sha256_file(row.path) != row.sha256:
            raise RuntimeError(f"dataset hash mismatch: {row.relative_path}")
    return rows


def ordered_dataset_rows(rows: Sequence[DatasetRow]) -> List[DatasetRow]:
    by_key = {(row.topology, row.instance_id): row for row in rows}
    return [by_key[(topology, f"i{i:02d}")] for topology in TOPOLOGY_ORDER for i in range(1, 6)]


def protected_files() -> List[Path]:
    roots = [
        EXPERIMENTS_ROOT / "results",
        EXPERIMENTS_ROOT / "main_benchmark_replications",
        EXPERIMENTS_ROOT / "composite_adversarial_replications",
        EXPERIMENTS_ROOT / "diagnostics",
        EXPERIMENTS_ROOT / "part1",
        EXPERIMENTS_ROOT / "part2",
    ]
    files: List[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                files.append(path)
    return sorted(files)


def write_protected_hashes(label: str, campaign_dir: Path, prior: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rows = []
    for path in protected_files():
        rows.append({"relative_path": rel(path), "sha256": sha256_file(path), "size_bytes": path.stat().st_size})
    payload = {
        "schema": "paper1_reviewer_validation_protected_hashes_v1",
        "created_at": now_iso(),
        "label": label,
        "file_count": len(rows),
        "rows": rows,
    }
    if prior is not None:
        before = {row["relative_path"]: row for row in prior["rows"]}
        after = {row["relative_path"]: row for row in rows}
        mismatches = []
        for key, before_row in before.items():
            after_row = after.get(key)
            if after_row != before_row:
                mismatches.append({"relative_path": key, "before": before_row, "after": after_row})
        extras = sorted(set(after) - set(before))
        missing = sorted(set(before) - set(after))
        payload["comparison_to_prior"] = {
            "mismatch_count": len(mismatches),
            "extra_protected_files": extras,
            "missing_protected_files": missing,
            "mismatches": mismatches,
            "all_ok": not mismatches and not extras and not missing,
        }
    write_json(VALIDATION_ROOT / f"protected_hashes_{label}.json", payload)
    write_json(campaign_dir / "validation" / f"protected_hashes_{label}.json", payload)
    return payload


def resolve_record_path(value: Any) -> Optional[Path]:
    if not value:
        return None
    text = str(value)
    path = Path(text)
    if path.exists():
        return path
    if not path.is_absolute():
        candidate = REPO_ROOT / path
        if candidate.exists():
            return candidate
    parts = PureWindowsPath(text).parts
    if "experiments" in parts:
        idx = parts.index("experiments")
        candidate = REPO_ROOT / Path(*parts[idx:])
        if candidate.exists():
            return candidate
    return None


def load_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def unavailable_cost(matrix_data: Dict[str, Any]) -> float:
    routing = matrix_data.get("routing_model") or {}
    for source in (routing, matrix_data.get("visibility_graph") or {}, matrix_data.get("grid_astar") or {}):
        if "unavailable_cost" in source:
            return float(source["unavailable_cost"])
    return UNAVAILABLE_COST


def finite_graph(matrix_data: Dict[str, Any]) -> Dict[str, List[str]]:
    labels = [str(label) for label in matrix_data.get("labels", [])]
    matrix = matrix_data.get("matrix", [])
    cutoff = unavailable_cost(matrix_data)
    graph = {label: [] for label in labels}
    for i, source in enumerate(labels):
        for j, dest in enumerate(labels):
            if i == j:
                continue
            try:
                value = float(matrix[i][j])
            except (IndexError, TypeError, ValueError):
                continue
            if math.isfinite(value) and value < cutoff:
                graph[source].append(dest)
    return graph


def reachable(graph: Dict[str, List[str]], start: str) -> set[str]:
    if start not in graph:
        return set()
    seen = {start}
    queue = [start]
    while queue:
        current = queue.pop(0)
        for neighbor in graph[current]:
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return seen


def scc_sizes(graph: Dict[str, List[str]]) -> List[int]:
    reverse = {node: [] for node in graph}
    for source, destinations in graph.items():
        for dest in destinations:
            reverse.setdefault(dest, []).append(source)
    seen: set[str] = set()
    order: List[str] = []

    def dfs(node: str) -> None:
        seen.add(node)
        for neighbor in graph.get(node, []):
            if neighbor not in seen:
                dfs(neighbor)
        order.append(node)

    for node in graph:
        if node not in seen:
            dfs(node)
    seen.clear()
    sizes: List[int] = []

    def rdfs(node: str) -> int:
        seen.add(node)
        total = 1
        for neighbor in reverse.get(node, []):
            if neighbor not in seen:
                total += rdfs(neighbor)
        return total

    for node in reversed(order):
        if node not in seen:
            sizes.append(rdfs(node))
    return sorted(sizes, reverse=True)


def matrix_connectivity_metrics(matrix_data: Dict[str, Any], start_id: str) -> Dict[str, Any]:
    labels = [str(label) for label in matrix_data.get("labels", [])]
    matrix = matrix_data.get("matrix", [])
    cutoff = unavailable_cost(matrix_data)
    directed = len(labels) * (len(labels) - 1)
    finite = 0
    for i in range(len(labels)):
        for j in range(len(labels)):
            if i == j:
                continue
            try:
                value = float(matrix[i][j])
            except (IndexError, TypeError, ValueError):
                continue
            if math.isfinite(value) and value < cutoff:
                finite += 1
    graph = finite_graph(matrix_data)
    reach = reachable(graph, start_id)
    reverse_graph = {node: [] for node in graph}
    for source, destinations in graph.items():
        for dest in destinations:
            reverse_graph.setdefault(dest, []).append(source)
    rev_reach = reachable(reverse_graph, start_id)
    targets = [label for label in labels if label.startswith("T")]
    sizes = scc_sizes(graph)
    return {
        "node_count": len(labels),
        "directed_pair_count": directed,
        "finite_directed_pairs": finite,
        "finite_pair_percent": (finite / directed * 100.0) if directed else 0.0,
        "unavailable_directed_pairs": directed - finite,
        "airport_reachable_targets": sum(1 for target in targets if target in reach),
        "reverse_reachable_targets": sum(1 for target in targets if target in rev_reach),
        "scc_count": len(sizes),
        "largest_scc_size": max(sizes) if sizes else 0,
        "stored_path_count": len(matrix_data.get("paths") or {}),
        "excluded_targets": ";".join(str(t) for t in matrix_data.get("excluded_targets", [])),
        "path_validation_failures": "",
    }


def load_matrix_from_mission(path: Path) -> Optional[Dict[str, Any]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    solution = doc.get("solution") or {}
    matrix = solution.get("distance_matrix")
    if isinstance(matrix, dict):
        return matrix
    matrix = (doc.get("env") or {}).get("distance_matrix")
    return matrix if isinstance(matrix, dict) else None


def run_connectivity_analysis(campaign_dir: Path) -> Dict[str, Any]:
    sources = [
        ("part1_controlled_run1", PART1_RUN1_CSV),
        ("part1_controlled_run2", PART1_RUN2_CSV),
        ("part1_composite_run1", COMPOSITE_RUN1_CSV),
        ("part1_composite_run2", COMPOSITE_RUN2_CSV),
        ("part2_primary_run01", PART2_PRIMARY_CSV),
    ]
    rows: List[Dict[str, Any]] = []
    for campaign_name, csv_path in sources:
        if not csv_path.exists():
            continue
        for source_row in load_csv(csv_path):
            method = source_row.get("method") or source_row.get("matrix_method") or ""
            env_id = (
                source_row.get("environment_id")
                or source_row.get("environment")
                or source_row.get("source_environment_id")
                or ""
            )
            mission_path = resolve_record_path(
                source_row.get("output_mission_file")
                or source_row.get("mission_output_path")
                or source_row.get("output_mission_json")
            )
            base = {
                "campaign": campaign_name,
                "environment_id": env_id,
                "topology": source_row.get("topology", ""),
                "instance_id": source_row.get("instance_id", ""),
                "method": method,
                "mission_status": source_row.get("status", ""),
                "mission_success": source_row.get("mission_success", ""),
                "mission_feasible": source_row.get("mission_feasible", ""),
                "targets_serviced": source_row.get("targets_serviced", ""),
                "failure_reason": source_row.get("failure_reason", ""),
                "mission_output_file": rel(mission_path) if mission_path and mission_path.is_relative_to(REPO_ROOT) else str(mission_path or ""),
            }
            if mission_path is None:
                rows.append({**base, "matrix_available": False, "connectivity_note": "mission output file not found"})
                continue
            matrix = load_matrix_from_mission(mission_path)
            if matrix is None:
                rows.append({**base, "matrix_available": False, "connectivity_note": "distance matrix not stored"})
                continue
            start_id = "A1"
            metrics = matrix_connectivity_metrics(matrix, start_id)
            rows.append({**base, "matrix_available": True, "connectivity_note": "", **metrics})

    by_key = {(r["campaign"], r["environment_id"], r["method"]): r for r in rows}
    for row in rows:
        if row["method"] == "appatt_bspline":
            raw = by_key.get((row["campaign"], row["environment_id"], "appatt_raw"))
            if raw and row.get("matrix_available") and raw.get("matrix_available"):
                row["finite_pair_delta_vs_raw"] = int(row["finite_directed_pairs"]) - int(raw["finite_directed_pairs"])
                row["smoothing_loss_vs_raw"] = int(raw["finite_directed_pairs"]) - int(row["finite_directed_pairs"])
        if row["method"] == "tig_bezier":
            raw = by_key.get((row["campaign"], row["environment_id"], "tig_raw"))
            if raw and row.get("matrix_available") and raw.get("matrix_available"):
                row["finite_pair_delta_vs_raw"] = int(row["finite_directed_pairs"]) - int(raw["finite_directed_pairs"])
                row["smoothing_loss_vs_raw"] = int(raw["finite_directed_pairs"]) - int(row["finite_directed_pairs"])

    fields = sorted({key for row in rows for key in row})
    csv_path = RV_ROOT / "connectivity" / "frozen_matrix_connectivity.csv"
    json_path = RV_ROOT / "connectivity" / "frozen_matrix_connectivity.json"
    write_csv(csv_path, rows, fields)
    write_json(json_path, {"schema": "paper1_reviewer_validation_connectivity_v1", "created_at": now_iso(), "rows": rows})
    lines = [
        "# Frozen Matrix-Level Connectivity",
        "",
        f"Rows analyzed: `{len(rows)}`",
        "",
        "| campaign | method | records | mean finite-pair % | mean airport-reachable targets |",
        "|---|---|---:|---:|---:|",
    ]
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for row in rows:
        if row.get("matrix_available"):
            groups.setdefault((row["campaign"], row["method"]), []).append(row)
    for (campaign, method), group_rows in sorted(groups.items()):
        finite_pct = statistics.fmean(float(r["finite_pair_percent"]) for r in group_rows)
        reachable_mean = statistics.fmean(float(r["airport_reachable_targets"]) for r in group_rows)
        lines.append(f"| {campaign} | {method} | {len(group_rows)} | {finite_pct:.3f} | {reachable_mean:.3f} |")
    md_path = RV_ROOT / "analysis" / "CONNECTIVITY_SUMMARY.md"
    write_text(md_path, "\n".join(lines) + "\n")
    return {"rows": len(rows), "csv": rel(csv_path), "json": rel(json_path), "markdown": rel(md_path)}


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def path_length(path: Sequence[Point]) -> float:
    return sum(distance(path[i], path[i + 1]) for i in range(len(path) - 1))


def as_points(path: Sequence[Sequence[float]]) -> List[Point]:
    return [(float(p[0]), float(p[1])) for p in path]


def points_to_lists(points: Sequence[Point]) -> List[List[float]]:
    return [[float(p[0]), float(p[1])] for p in points]


class CachedVisibilityGraphMatrixBuilder:
    method = "visibility_graph_cached"

    def __init__(self, *, vertex_count: int = 72, planner_root: Path = DEFAULT_PLANNER_ROOT) -> None:
        self.vertex_count = int(vertex_count)
        self.planner_root = planner_root
        self._project_env_to_local_km = None
        self.last_static_time = 0.0
        self.last_query_time = 0.0

    def prepare(self) -> None:
        from benchmark.matrix_builders import configure_planner_imports

        configure_planner_imports(self.planner_root)
        from server.solver.projection import _project_env_to_local_km

        self._project_env_to_local_km = _project_env_to_local_km

    def build(self, env: Dict[str, Any]) -> MatrixBuild:
        if self._project_env_to_local_km is None:
            self.prepare()
        assert self._project_env_to_local_km is not None
        import methods.visibility_graph.method as vg

        original_count = vg.CIRCLE_VERTEX_COUNT
        vg.CIRCLE_VERTEX_COUNT = self.vertex_count
        try:
            projected_env, _, _ = self._project_env_to_local_km(copy.deepcopy(env))
            delegate = vg.VisibilityGraphMatrixBuilder(planner_root=self.planner_root)
            delegate._project_env_to_local_km = self._project_env_to_local_km
            waypoints = delegate._build_waypoints(projected_env)
            sams = delegate._normalize_sams(projected_env)
            static_start = time.perf_counter()
            obstacles = delegate._build_obstacle_polygons(sams)
            boundary_vertices = delegate._union_boundary_vertices(obstacles)
            static_adjacency: List[List[Tuple[float, int]]] = [[] for _ in boundary_vertices]
            static_edges = 0
            for i, a in enumerate(boundary_vertices):
                for j in range(i + 1, len(boundary_vertices)):
                    b = boundary_vertices[j]
                    if delegate._segment_blocked_by_union(a, b, obstacles):
                        continue
                    cost = distance(a, b)
                    static_adjacency[i].append((cost, j))
                    static_adjacency[j].append((cost, i))
                    static_edges += 1
            for neighbors in static_adjacency:
                neighbors.sort(key=lambda item: (item[0], item[1]))
            self.last_static_time = time.perf_counter() - static_start

            labels = [str(wp["id"]) for wp in waypoints]
            n = len(waypoints)
            matrix: List[List[float]] = [[0.0] * n for _ in range(n)]
            paths: Dict[str, List[List[float]]] = {}
            pair_results: List[Dict[str, Any]] = []
            query_start = time.perf_counter()
            for i in range(n):
                for j in range(i + 1, n):
                    start = (float(waypoints[i]["x"]), float(waypoints[i]["y"]))
                    end = (float(waypoints[j]["x"]), float(waypoints[j]["y"]))
                    path = self._shortest_path_cached(
                        start=start,
                        end=end,
                        boundary_vertices=boundary_vertices,
                        static_adjacency=static_adjacency,
                        delegate=delegate,
                        obstacles=obstacles,
                    )
                    if path is None:
                        matrix[i][j] = UNAVAILABLE_COST
                        matrix[j][i] = UNAVAILABLE_COST
                        pair_results.append({"pair": [labels[i], labels[j]], "status": "UNAVAILABLE"})
                        continue
                    dist = path_length(path)
                    path_lists = points_to_lists(path)
                    matrix[i][j] = dist
                    matrix[j][i] = dist
                    paths[f"{labels[i]}->{labels[j]}"] = path_lists
                    paths[f"{labels[j]}->{labels[i]}"] = list(reversed(path_lists))
                    pair_results.append(
                        {
                            "pair": [labels[i], labels[j]],
                            "status": "AVAILABLE",
                            "distance": dist,
                            "path_point_count": len(path),
                            "classification": "DIRECT" if len(path) == 2 else "DETOUR",
                        }
                    )
            self.last_query_time = time.perf_counter() - query_start
            return MatrixBuild(
                method=self.method,
                data={
                    "matrix": matrix,
                    "labels": labels,
                    "waypoints": waypoints,
                    "paths": paths,
                    "excluded_targets": [],
                    "sams": sams,
                    "buffer": 0.0,
                    "wrapped_polygons": [],
                    "routing_model": {
                        "method": self.method,
                        "sam_mode": "original_circles_visibility_graph_cached",
                        "unavailable_cost": UNAVAILABLE_COST,
                    },
                    "visibility_graph_cached": {
                        "circle_vertex_count": self.vertex_count,
                        "static_graph_construction_time_sec": self.last_static_time,
                        "matrix_query_time_sec": self.last_query_time,
                        "total_preprocessing_time_sec": self.last_static_time + self.last_query_time,
                        "static_boundary_vertex_count": len(boundary_vertices),
                        "static_visibility_edge_count": static_edges,
                        "pair_results": pair_results,
                    },
                    "benchmark_diagnostics": {
                        "method": self.method,
                        "circle_vertex_count": self.vertex_count,
                        "static_graph_construction_time_sec": self.last_static_time,
                        "matrix_query_time_sec": self.last_query_time,
                        "total_preprocessing_time_sec": self.last_static_time + self.last_query_time,
                    },
                },
            )
        finally:
            vg.CIRCLE_VERTEX_COUNT = original_count

    def _shortest_path_cached(
        self,
        *,
        start: Point,
        end: Point,
        boundary_vertices: Sequence[Point],
        static_adjacency: Sequence[Sequence[Tuple[float, int]]],
        delegate: Any,
        obstacles: Sequence[Dict[str, Any]],
    ) -> Optional[List[Point]]:
        if distance(start, end) <= EPS:
            return [start]
        if not delegate._segment_blocked_by_union(start, end, obstacles):
            return [start, end]
        if delegate._strictly_inside_any_polygon(start, obstacles):
            return None
        if delegate._strictly_inside_any_polygon(end, obstacles):
            return None

        boundary_count = len(boundary_vertices)
        start_node = boundary_count
        end_node = boundary_count + 1
        start_edges = []
        end_edges_by_boundary: Dict[int, float] = {}
        for i, point in enumerate(boundary_vertices):
            if not delegate._segment_blocked_by_union(start, point, obstacles):
                start_edges.append((distance(start, point), i))
            if not delegate._segment_blocked_by_union(point, end, obstacles):
                end_edges_by_boundary[i] = distance(point, end)

        distances = {start_node: 0.0}
        previous: Dict[int, int] = {}
        heap: List[Tuple[float, int]] = [(0.0, start_node)]
        while heap:
            current_distance, current = heapq_pop(heap)
            if current_distance > distances.get(current, math.inf) + EPS:
                continue
            if current == end_node:
                break
            if current == start_node:
                neighbors = start_edges
            elif current == end_node:
                neighbors = []
            else:
                neighbors = list(static_adjacency[current])
                if current in end_edges_by_boundary:
                    neighbors.append((end_edges_by_boundary[current], end_node))
            for cost, neighbor in neighbors:
                candidate = current_distance + cost
                if candidate + EPS < distances.get(neighbor, math.inf):
                    distances[neighbor] = candidate
                    previous[neighbor] = current
                    heapq_push(heap, (candidate, neighbor))
        if end_node not in distances:
            return None
        indices = [end_node]
        current = end_node
        while current != start_node:
            current = previous[current]
            indices.append(current)
        indices.reverse()
        points: List[Point] = []
        for node in indices:
            if node == start_node:
                points.append(start)
            elif node == end_node:
                points.append(end)
            else:
                points.append(boundary_vertices[node])
        return points


def heapq_push(heap: List[Tuple[float, int]], item: Tuple[float, int]) -> None:
    import heapq

    heapq.heappush(heap, item)


def heapq_pop(heap: List[Tuple[float, int]]) -> Tuple[float, int]:
    import heapq

    return heapq.heappop(heap)


class ParameterizedVisibilityGraphBuilder:
    def __init__(self, vertex_count: int, *, planner_root: Path = DEFAULT_PLANNER_ROOT) -> None:
        self.vertex_count = int(vertex_count)
        self.method = f"visibility_graph_v{self.vertex_count:03d}"
        self.planner_root = planner_root
        self._delegate = None

    def prepare(self) -> None:
        import methods.visibility_graph.method as vg

        self._delegate = vg.VisibilityGraphMatrixBuilder(planner_root=self.planner_root)
        self._delegate.prepare()

    def build(self, env: Dict[str, Any]) -> MatrixBuild:
        if self._delegate is None:
            self.prepare()
        import methods.visibility_graph.method as vg

        original = vg.CIRCLE_VERTEX_COUNT
        vg.CIRCLE_VERTEX_COUNT = self.vertex_count
        try:
            result = self._delegate.build(env)
            data = result.data
            data["routing_model"]["method"] = self.method
            data["visibility_graph"]["circle_vertex_count"] = self.vertex_count
            data["benchmark_diagnostics"] = {
                "method": self.method,
                "method_family": "visibility_graph",
                "circle_vertex_count": self.vertex_count,
            }
            return MatrixBuild(method=self.method, data=data)
        finally:
            vg.CIRCLE_VERTEX_COUNT = original


class ParameterizedGridAStarBuilder:
    def __init__(self, spacing_km: float, *, planner_root: Path = DEFAULT_PLANNER_ROOT) -> None:
        self.spacing_km = float(spacing_km)
        safe = str(self.spacing_km).replace(".", "p")
        self.method = f"grid_astar_{safe}km"
        self.planner_root = planner_root
        self._delegate = None

    def prepare(self) -> None:
        import methods.grid_astar.method as grid

        self._delegate = grid.GridAStarMatrixBuilder(planner_root=self.planner_root)
        self._delegate.prepare()

    def build(self, env: Dict[str, Any]) -> MatrixBuild:
        if self._delegate is None:
            self.prepare()
        import methods.grid_astar.method as grid

        original = grid.GRID_SPACING_KM
        grid.GRID_SPACING_KM = self.spacing_km
        try:
            result = self._delegate.build(env)
            data = result.data
            data["routing_model"]["method"] = self.method
            data["grid_astar"]["grid_spacing_km"] = self.spacing_km
            data["benchmark_diagnostics"] = {
                "method": self.method,
                "method_family": "grid_astar",
                "grid_spacing_km": self.spacing_km,
            }
            return MatrixBuild(method=self.method, data=data)
        finally:
            grid.GRID_SPACING_KM = original


def mission_details(solution: Dict[str, Any]) -> Dict[str, Any]:
    routes = solution.get("routes") or {}
    d1 = routes.get("1") or {}
    return {
        "route_sequence": ",".join(str(node) for node in d1.get("route", [])),
        "trajectory_point_count": len(d1.get("trajectory") or []),
        "active_route_count": sum(1 for route in routes.values() if route.get("route")),
    }


def run_builder_condition(
    *,
    builder: Any,
    env_path: Path,
    output_dir: Path,
    log_path: Optional[Path] = None,
) -> Dict[str, Any]:
    native_env = load_native_environment(env_path)
    prepare = getattr(builder, "prepare", None)
    if callable(prepare):
        prepare()
    prepare_solver(DEFAULT_PLANNER_ROOT)
    from server.solver.solver_bridge import solve_mission_with_allocation

    with contextlib.ExitStack() as stack:
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            handle = stack.enter_context(log_path.open("a", encoding="utf-8", newline="\n"))
            stack.enter_context(contextlib.redirect_stdout(handle))
            stack.enter_context(contextlib.redirect_stderr(handle))
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
                allocation_strategy="geographic",
                use_sam_aware_distances=True,
                post_optimize=False,
            )
            solver_time = time.perf_counter() - solver_start
    status = _mission_status(
        solution=solution,
        env=solver_env,
        drone_configs=solver_drone_configs,
        matrix_data=matrix_build.data,
    )
    mission_doc = build_mission_document(
        native_env,
        solution=solution,
        env=solver_env,
        drone_configs=solver_drone_configs,
    )
    mission_path = output_dir / "missions" / mission_filename(
        source_id=native_env.source_id,
        matrix_method=matrix_build.method,
        segment_count=native_env.segment_count,
    )
    write_json(mission_path, mission_doc)
    metrics = matrix_connectivity_metrics(matrix_build.data, "A1")
    details = mission_details(solution)
    diagnostics = matrix_build.data.get("benchmark_diagnostics") or {}
    return {
        "source_environment": rel(env_path),
        "environment_id": native_env.source_id,
        "method": matrix_build.method,
        "matrix_time_sec": matrix_time,
        "solver_time_sec": solver_time,
        "solver_completed": True,
        "mission_feasible": bool(status["mission_feasible"]),
        "mission_success": bool(status["mission_success"]),
        "targets_serviced": int(status["targets_serviced"]),
        "targets_expected": int(status["targets_expected"]),
        "mission_distance_km": float(status["route_distance"]),
        "failure_reason": status["failure_reason"],
        "output_mission_file": rel(mission_path),
        "route_sequence": details["route_sequence"],
        "mission_trajectory_point_count": details["trajectory_point_count"],
        "matrix_diagnostics": diagnostics,
        **metrics,
    }


def matrix_agreement(a: Dict[str, Any], b: Dict[str, Any], tolerance: float = 1e-6) -> Dict[str, Any]:
    labels_a = [str(x) for x in a.get("labels", [])]
    labels_b = [str(x) for x in b.get("labels", [])]
    if labels_a != labels_b:
        return {"labels_equal": False, "availability_equal": False, "max_distance_delta": None, "differing_availability": -1}
    cutoff_a = unavailable_cost(a)
    cutoff_b = unavailable_cost(b)
    max_delta = 0.0
    diff_avail = 0
    diff_values = 0
    matrix_a = a.get("matrix", [])
    matrix_b = b.get("matrix", [])
    for i in range(len(labels_a)):
        for j in range(len(labels_a)):
            if i == j:
                continue
            va = float(matrix_a[i][j])
            vb = float(matrix_b[i][j])
            aa = math.isfinite(va) and va < cutoff_a
            bb = math.isfinite(vb) and vb < cutoff_b
            if aa != bb:
                diff_avail += 1
            if aa and bb:
                delta = abs(va - vb)
                max_delta = max(max_delta, delta)
                if delta > tolerance:
                    diff_values += 1
    return {
        "labels_equal": True,
        "availability_equal": diff_avail == 0,
        "distance_values_within_tolerance": diff_values == 0,
        "max_distance_delta": max_delta,
        "differing_availability": diff_avail,
        "differing_distance_values": diff_values,
    }


def primary_vg_matrix(environment_id: str) -> Dict[str, Any]:
    record_path = PART2_PRIMARY_RECORDS / f"{environment_id}__visibility_graph.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    mission_path = resolve_record_path(record["output_mission_file"])
    if mission_path is None:
        raise FileNotFoundError(record["output_mission_file"])
    matrix = load_matrix_from_mission(mission_path)
    if matrix is None:
        raise RuntimeError(f"no VG matrix in {mission_path}")
    return matrix


def run_cached_vg_campaign(campaign_dir: Path, dataset_rows: Sequence[DatasetRow]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    regression_rows: List[Dict[str, Any]] = []
    records_dir = campaign_dir / "cached_vg" / "records"
    log_path = campaign_dir / "logs" / "cached_vg.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    for ds in ordered_dataset_rows(dataset_rows):
        builder = CachedVisibilityGraphMatrixBuilder(vertex_count=72)
        native_env = load_native_environment(ds.path)
        with log_path.open("a", encoding="utf-8", newline="\n") as handle:
            with contextlib.redirect_stdout(handle), contextlib.redirect_stderr(handle):
                cached_matrix = builder.build(native_env.env).data
        agreement = matrix_agreement(primary_vg_matrix(ds.environment_id), cached_matrix)
        regression_rows.append(
            {
                "environment_id": ds.environment_id,
                "topology": ds.topology,
                "instance_id": ds.instance_id,
                "connectivity_agreement": agreement["availability_equal"],
                "distance_values_within_tolerance": agreement["distance_values_within_tolerance"],
                "max_distance_delta": agreement["max_distance_delta"],
                "differing_availability": agreement["differing_availability"],
                "differing_distance_values": agreement["differing_distance_values"],
            }
        )
        if not agreement["availability_equal"]:
            raise RuntimeError(f"cached VG availability mismatch for {ds.environment_id}")
        for rep in range(1, 4):
            builder = CachedVisibilityGraphMatrixBuilder(vertex_count=72)
            result = run_builder_condition(builder=builder, env_path=ds.path, output_dir=campaign_dir / "cached_vg" / "outputs", log_path=log_path)
            primary_matrix = primary_vg_matrix(ds.environment_id)
            mission_matrix = load_matrix_from_mission(REPO_ROOT / result["output_mission_file"])
            assert mission_matrix is not None
            agreement = matrix_agreement(primary_matrix, mission_matrix)
            record = {
                "campaign": "cached_vg",
                "environment_id": ds.environment_id,
                "topology": ds.topology,
                "instance_id": ds.instance_id,
                "seed": ds.seed,
                "repetition": rep,
                "source_dataset_hash": ds.sha256,
                "static_graph_construction_time_sec": result["matrix_diagnostics"].get("static_graph_construction_time_sec"),
                "matrix_query_time_sec": result["matrix_diagnostics"].get("matrix_query_time_sec"),
                "total_preprocessing_time_sec": result["matrix_diagnostics"].get("total_preprocessing_time_sec"),
                "matrix_time_sec": result["matrix_time_sec"],
                "solver_time_sec": result["solver_time_sec"],
                "mission_success": result["mission_success"],
                "mission_feasible": result["mission_feasible"],
                "targets_serviced": result["targets_serviced"],
                "mission_distance_km": result["mission_distance_km"],
                "finite_pair_percent": result["finite_pair_percent"],
                "output_mission_file": result["output_mission_file"],
                **{f"agreement_{k}": v for k, v in agreement.items()},
            }
            row_path = records_dir / f"{ds.environment_id}__cached_vg__rep{rep}.json"
            write_json(row_path, record)
            record["record_path"] = rel(row_path)
            record["record_sha256"] = sha256_file(row_path)
            rows.append(record)
            append_jsonl(campaign_dir / "cached_vg" / "cached_vg_rows.jsonl", record)
    fields = sorted({key for row in rows for key in row})
    write_csv(RV_ROOT / "cached_vg" / "cached_vg_campaign.csv", rows, fields)
    write_json(RV_ROOT / "cached_vg" / "cached_vg_campaign.json", {"schema": "paper1_cached_vg_campaign_v1", "rows": rows})
    write_csv(RV_ROOT / "cached_vg" / "cached_vg_regression.csv", regression_rows, list(regression_rows[0]))
    write_json(RV_ROOT / "cached_vg" / "cached_vg_regression.json", {"schema": "paper1_cached_vg_regression_v1", "rows": regression_rows})
    return {"recorded_executions": len(rows), "regression_environments": len(regression_rows)}


def run_sensitivity_campaign(campaign_dir: Path, dataset_rows: Sequence[DatasetRow]) -> Dict[str, Any]:
    i03_rows = [row for row in ordered_dataset_rows(dataset_rows) if row.environment_id in I03_ENV_IDS]
    rows: List[Dict[str, Any]] = []
    log_path = campaign_dir / "logs" / "sensitivity.log"
    records_dir = campaign_dir / "sensitivity" / "records"
    execution_index = 0
    for ds in i03_rows:
        for vertex_count in VG_RESOLUTIONS:
            for rep in range(1, 4):
                execution_index += 1
                builder = ParameterizedVisibilityGraphBuilder(vertex_count)
                result = run_builder_condition(builder=builder, env_path=ds.path, output_dir=campaign_dir / "sensitivity" / "outputs", log_path=log_path)
                record = {
                    "campaign": "sensitivity",
                    "execution_index": execution_index,
                    "method_family": "visibility_graph",
                    "parameter_name": "circle_vertices",
                    "parameter_value": vertex_count,
                    "environment_id": ds.environment_id,
                    "topology": ds.topology,
                    "instance_id": ds.instance_id,
                    "seed": ds.seed,
                    "repetition": rep,
                    "source_dataset_hash": ds.sha256,
                    **result,
                }
                row_path = records_dir / f"{ds.environment_id}__vg{vertex_count:03d}__rep{rep}.json"
                write_json(row_path, record)
                record["record_path"] = rel(row_path)
                record["record_sha256"] = sha256_file(row_path)
                rows.append(record)
        for spacing in GRID_RESOLUTIONS:
            for rep in range(1, 4):
                execution_index += 1
                builder = ParameterizedGridAStarBuilder(spacing)
                result = run_builder_condition(builder=builder, env_path=ds.path, output_dir=campaign_dir / "sensitivity" / "outputs", log_path=log_path)
                record = {
                    "campaign": "sensitivity",
                    "execution_index": execution_index,
                    "method_family": "grid_astar",
                    "parameter_name": "grid_spacing_km",
                    "parameter_value": spacing,
                    "environment_id": ds.environment_id,
                    "topology": ds.topology,
                    "instance_id": ds.instance_id,
                    "seed": ds.seed,
                    "repetition": rep,
                    "source_dataset_hash": ds.sha256,
                    **result,
                }
                row_path = records_dir / f"{ds.environment_id}__grid{str(spacing).replace('.', 'p')}__rep{rep}.json"
                write_json(row_path, record)
                record["record_path"] = rel(row_path)
                record["record_sha256"] = sha256_file(row_path)
                rows.append(record)
    fields = sorted({key for row in rows for key in row})
    write_csv(RV_ROOT / "sensitivity" / "resolution_sensitivity.csv", rows, fields)
    write_json(RV_ROOT / "sensitivity" / "resolution_sensitivity.json", {"schema": "paper1_resolution_sensitivity_v1", "rows": rows})
    return {"recorded_executions": len(rows)}


def drone_configs(fuel_budget: float = 900.0) -> Dict[str, Dict[str, Any]]:
    configs: Dict[str, Dict[str, Any]] = {}
    for i in range(1, 6):
        configs[str(i)] = {
            "enabled": i == 1,
            "fuel_budget": fuel_budget,
            "start_airport": "A1",
            "end_airport": "A1",
            "refuel_airport": "",
            "refuel_stops": [],
            "refuel_options": [],
            "max_refuels": 0,
            "runway": "S",
            "target_access": {"a": True, "b": True, "c": True, "d": True, "e": True},
            "speed": 1,
            "loiter_enabled": False,
            "loiter_times": {"a": 0, "b": 0, "c": 0, "d": 0, "e": 0},
            "detection_radius": {"a": 0, "b": 0, "c": 0, "d": 0, "e": 0},
        }
    return configs


def stress_env(env_id: str, seed: int, airports: List[Point], targets: List[Point], sams: List[Tuple[Point, float]]) -> Dict[str, Any]:
    configs = drone_configs()
    env = {
        "airports": [{"id": f"A{i + 1}", "x": x, "y": y} for i, (x, y) in enumerate(airports)],
        "targets": [
            {"id": f"T{i + 1}", "x": x, "y": y, "priority": 5, "type": "a"}
            for i, (x, y) in enumerate(targets)
        ],
        "sams": [
            {"id": f"NFZ{i + 1}", "pos": [x, y], "x": x, "y": y, "range": r}
            for i, ((x, y), r) in enumerate(sams)
        ],
        "drone_configs": configs,
    }
    return {
        "schema": "nfz_env_v1",
        "is_segmented": False,
        "segment_count": 1,
        "reviewer_validation_case": env_id,
        "seed": seed,
        "env": env,
        "drone_configs": configs,
    }


def write_stress_environments() -> List[DatasetRow]:
    specs = [
        (
            "target_in_concavity_seed_91001",
            91001,
            [(-58.0, -28.0)],
            [(0.0, 4.0), (42.0, 32.0), (-42.0, 30.0), (50.0, -24.0)],
            [((-16.0, 0.0), 14.0), ((0.0, 20.0), 14.0), ((16.0, 0.0), 14.0)],
        ),
        (
            "transit_through_concavity_seed_91002",
            91002,
            [(-62.0, 2.0)],
            [(62.0, 2.0), (0.0, 4.5), (-46.0, -28.0), (46.0, -28.0)],
            [((-18.0, 0.0), 15.0), ((0.0, 23.0), 15.0), ((18.0, 0.0), 15.0)],
        ),
        (
            "increasing_conservatism_low_seed_91003",
            91003,
            [(-60.0, -20.0)],
            [(0.0, 2.0), (55.0, 22.0), (-42.0, 26.0), (48.0, -26.0)],
            [((-14.0, 0.0), 12.0), ((0.0, 17.0), 12.0), ((14.0, 0.0), 12.0)],
        ),
        (
            "increasing_conservatism_medium_seed_91004",
            91004,
            [(-60.0, -20.0)],
            [(0.0, 4.0), (55.0, 22.0), (-42.0, 26.0), (48.0, -26.0)],
            [((-18.0, 0.0), 14.0), ((0.0, 24.0), 14.0), ((18.0, 0.0), 14.0)],
        ),
        (
            "increasing_conservatism_high_seed_91005",
            91005,
            [(-60.0, -20.0)],
            [(0.0, 6.0), (55.0, 22.0), (-42.0, 26.0), (48.0, -26.0)],
            [((-22.0, 0.0), 16.0), ((0.0, 32.0), 16.0), ((22.0, 0.0), 16.0)],
        ),
    ]
    rows: List[DatasetRow] = []
    env_dir = RV_ROOT / "conservatism" / "environments"
    for env_id, seed, airports, targets, sams in specs:
        path = env_dir / f"{env_id}.json"
        if not path.exists():
            write_json(path, stress_env(env_id, seed, airports, targets, sams))
        rows.append(DatasetRow(env_id, "conservatism_stress", f"seed_{seed}", seed, rel(path), sha256_file(path)))
    write_json(RV_ROOT / "conservatism" / "stress_environment_manifest.json", {"schema": "paper1_conservatism_stress_environment_manifest_v1", "rows": [r.__dict__ for r in rows]})
    return rows


def point_in_poly(point: Point, poly: Sequence[Sequence[float]]) -> bool:
    x, y = point
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = float(poly[i][0]), float(poly[i][1])
        xj, yj = float(poly[j][0]), float(poly[j][1])
        if (yi > y) != (yj > y):
            x_int = (xj - xi) * (y - yi) / (yj - yi + 1e-30) + xi
            if x < x_int:
                inside = not inside
        j = i
    return inside


def poly_area(poly: Sequence[Sequence[float]]) -> float:
    area = 0.0
    for i in range(len(poly)):
        x1, y1 = float(poly[i][0]), float(poly[i][1])
        x2, y2 = float(poly[(i + 1) % len(poly)][0]), float(poly[(i + 1) % len(poly)][1])
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def deterministic_union_area(sams: Sequence[Dict[str, Any]], step: float = 0.1) -> Tuple[float, float]:
    circles = [(float(s["pos"][0]), float(s["pos"][1]), float(s["range"])) for s in sams]
    min_x = min(x - r for x, _, r in circles)
    max_x = max(x + r for x, _, r in circles)
    min_y = min(y - r for _, y, r in circles)
    max_y = max(y + r for _, y, r in circles)
    count = 0
    nx = int(math.ceil((max_x - min_x) / step))
    ny = int(math.ceil((max_y - min_y) / step))
    for ix in range(nx):
        x = min_x + (ix + 0.5) * step
        for iy in range(ny):
            y = min_y + (iy + 0.5) * step
            if any((x - cx) ** 2 + (y - cy) ** 2 <= r * r for cx, cy, r in circles):
                count += 1
    return count * step * step, (max_x - min_x) * (max_y - min_y)


def conservatism_area_metrics(proposed_matrix: Dict[str, Any]) -> Dict[str, Any]:
    sams = proposed_matrix.get("sams") or []
    native_area, bbox_area = deterministic_union_area(sams)
    wrapped = proposed_matrix.get("wrapped_polygons") or []
    wrapped_area = sum(poly_area(poly) for poly in wrapped)
    additional = max(0.0, wrapped_area - native_area)
    local_free = max(EPS, bbox_area - native_area)
    return {
        "native_nfz_union_area_km2_approx": native_area,
        "wrapped_obstacle_area_km2": wrapped_area,
        "additional_area_excluded_km2": additional,
        "local_bbox_area_km2": bbox_area,
        "percent_otherwise_usable_local_free_space_removed": additional / local_free * 100.0,
        "area_method": "0.1-km deterministic midpoint raster for native disk union; shoelace area for wrapped polygons",
    }


def inaccessible_targets_by_wrapped_hull(env: Dict[str, Any], proposed_matrix: Dict[str, Any]) -> List[str]:
    wrapped = proposed_matrix.get("wrapped_polygons") or []
    result = []
    for target in env.get("targets", []):
        point = (float(target["x"]), float(target["y"]))
        if any(point_in_poly(point, poly) for poly in wrapped):
            result.append(str(target["id"]))
    return result


def run_conservatism_campaign(campaign_dir: Path) -> Dict[str, Any]:
    from methods.proposed.method import ProposedSAMMatrixBuilder

    stress_rows = write_stress_environments()
    rows: List[Dict[str, Any]] = []
    log_path = campaign_dir / "logs" / "conservatism.log"
    for ds in stress_rows:
        row_path = campaign_dir / "conservatism" / "records" / f"{ds.environment_id}.json"
        if row_path.exists():
            record = json.loads(row_path.read_text(encoding="utf-8"))
            record["record_path"] = rel(row_path)
            record["record_sha256"] = sha256_file(row_path)
            rows.append(record)
            continue
        native_builder = CachedVisibilityGraphMatrixBuilder(vertex_count=720)
        native = run_builder_condition(builder=native_builder, env_path=REPO_ROOT / ds.relative_path, output_dir=campaign_dir / "conservatism" / "outputs", log_path=log_path)
        proposed_builder = ProposedSAMMatrixBuilder(buffer=0.0)
        proposed = run_builder_condition(builder=proposed_builder, env_path=REPO_ROOT / ds.relative_path, output_dir=campaign_dir / "conservatism" / "outputs", log_path=log_path)
        proposed_matrix = load_matrix_from_mission(REPO_ROOT / proposed["output_mission_file"])
        native_matrix = load_matrix_from_mission(REPO_ROOT / native["output_mission_file"])
        assert proposed_matrix is not None and native_matrix is not None
        env = load_native_environment(REPO_ROOT / ds.relative_path).env
        area = conservatism_area_metrics(proposed_matrix)
        agreement = matrix_agreement(native_matrix, proposed_matrix, tolerance=1e-5)
        route_inflation = None
        if native["mission_distance_km"] and proposed["mission_distance_km"] and native["mission_feasible"] and proposed["mission_feasible"]:
            route_inflation = proposed["mission_distance_km"] - native["mission_distance_km"]
        record = {
            "campaign": "conservatism",
            "environment_id": ds.environment_id,
            "seed": ds.seed,
            "source_environment": ds.relative_path,
            "source_dataset_hash": ds.sha256,
            "native_reference_method": native["method"],
            "proposed_method": proposed["method"],
            "native_finite_directed_pairs": native["finite_directed_pairs"],
            "proposed_finite_directed_pairs": proposed["finite_directed_pairs"],
            "relationships_excluded_by_conservative_representation": int(native["finite_directed_pairs"]) - int(proposed["finite_directed_pairs"]),
            "targets_rendered_inaccessible_by_wrapped_hull": ";".join(inaccessible_targets_by_wrapped_hull(env, proposed_matrix)),
            "native_mission_success": native["mission_success"],
            "proposed_mission_success": proposed["mission_success"],
            "native_targets_serviced": native["targets_serviced"],
            "proposed_targets_serviced": proposed["targets_serviced"],
            "native_mission_distance_km": native["mission_distance_km"],
            "proposed_mission_distance_km": proposed["mission_distance_km"],
            "route_inflation_km_where_both_feasible": route_inflation,
            "connectivity_agreement": agreement["availability_equal"],
            "native_output_mission_file": native["output_mission_file"],
            "proposed_output_mission_file": proposed["output_mission_file"],
            **area,
        }
        write_json(row_path, record)
        record["record_path"] = rel(row_path)
        record["record_sha256"] = sha256_file(row_path)
        rows.append(record)
    fields = sorted({key for row in rows for key in row})
    write_csv(RV_ROOT / "conservatism" / "conservatism_stress_results.csv", rows, fields)
    write_json(RV_ROOT / "conservatism" / "conservatism_stress_results.json", {"schema": "paper1_conservatism_stress_results_v1", "rows": rows})
    draw_conservatism_figure(rows)
    return {"recorded_environments": len(rows)}


def draw_conservatism_figure(rows: Sequence[Dict[str, Any]]) -> None:
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, min(3, len(rows)), figsize=(12, 3.5), constrained_layout=True)
    axes = list(getattr(axes, "flat", [axes]))
    for ax, row in zip(axes, rows[:3]):
        env = load_native_environment(REPO_ROOT / row["source_environment"]).env
        for sam in env["sams"]:
            circle = plt.Circle((sam["pos"][0], sam["pos"][1]), sam["range"], color="#d95f02", alpha=0.25)
            ax.add_patch(circle)
        proposed_matrix = load_matrix_from_mission(REPO_ROOT / row["proposed_output_mission_file"])
        for poly in proposed_matrix.get("wrapped_polygons", []):
            xs = [point[0] for point in poly] + [poly[0][0]]
            ys = [point[1] for point in poly] + [poly[0][1]]
            ax.plot(xs, ys, color="#7570b3", linewidth=1.2)
        for target in env["targets"]:
            ax.plot(target["x"], target["y"], "o", color="#1b9e77")
            ax.text(target["x"] + 1, target["y"] + 1, target["id"], fontsize=7)
        for airport in env["airports"]:
            ax.plot(airport["x"], airport["y"], "^", color="black")
            ax.text(airport["x"] + 1, airport["y"] + 1, airport["id"], fontsize=7)
        ax.set_title(row["environment_id"].replace("_seed_", "\nseed "))
        ax.set_aspect("equal", adjustable="box")
        ax.grid(True, linewidth=0.2)
    out = FIGURES_ROOT / "conservatism_geometry_examples.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)


def inspect_exact_capability() -> Dict[str, Any]:
    hits = []
    for root in (REPO_ROOT / "path_planning_core", REPO_ROOT / "server" / "solver"):
        if root.exists():
            for path in root.rglob("*.py"):
                text = path.read_text(encoding="utf-8", errors="ignore").lower()
                if "exact circular" in text or "circle shortest" in text or "dubins" in text:
                    hits.append(rel(path))
    return {
        "exact_circular_shortest_path_found": False,
        "search_hits": hits,
        "selected_reference": "720-vertex polygonal Visibility Graph reference",
        "not_exact_notice": "No repository implementation was identified as a mathematically exact circular-obstacle shortest-path solver.",
    }


def distance_for_pair(matrix_data: Dict[str, Any], source: str, dest: str) -> Optional[float]:
    labels = [str(label) for label in matrix_data.get("labels", [])]
    if source not in labels or dest not in labels:
        return None
    value = float(matrix_data["matrix"][labels.index(source)][labels.index(dest)])
    return value if value < unavailable_cost(matrix_data) else None


def run_high_fidelity_checks(campaign_dir: Path, dataset_rows: Sequence[DatasetRow]) -> Dict[str, Any]:
    capability = inspect_exact_capability()
    rows: List[Dict[str, Any]] = []
    log_path = campaign_dir / "logs" / "high_fidelity.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    for ds in [row for row in ordered_dataset_rows(dataset_rows) if row.environment_id in I03_ENV_IDS]:
        builder72 = CachedVisibilityGraphMatrixBuilder(vertex_count=72)
        builder720 = CachedVisibilityGraphMatrixBuilder(vertex_count=720)
        native_env = load_native_environment(ds.path)
        with log_path.open("a", encoding="utf-8", newline="\n") as handle:
            with contextlib.redirect_stdout(handle), contextlib.redirect_stderr(handle):
                start72 = time.perf_counter()
                matrix72 = builder72.build(native_env.env).data
                time72 = time.perf_counter() - start72
                start720 = time.perf_counter()
                matrix720 = builder720.build(native_env.env).data
                time720 = time.perf_counter() - start720
        for source, dest in HF_PAIRS:
            d72 = distance_for_pair(matrix72, source, dest)
            d720 = distance_for_pair(matrix720, source, dest)
            abs_delta = None if d72 is None or d720 is None else abs(d72 - d720)
            rel_delta = None if abs_delta is None or not d720 else abs_delta / d720
            rows.append(
                {
                    "campaign": "high_fidelity",
                    "environment_id": ds.environment_id,
                    "topology": ds.topology,
                    "instance_id": ds.instance_id,
                    "seed": ds.seed,
                    "source": source,
                    "destination": dest,
                    "vg72_distance_km": d72,
                    "vg720_reference_distance_km": d720,
                    "connectivity_agreement": (d72 is None) == (d720 is None),
                    "absolute_distance_difference_km": abs_delta,
                    "relative_distance_error": rel_delta,
                    "vg72_full_matrix_time_sec": time72,
                    "vg720_full_matrix_time_sec": time720,
                    "source_dataset_hash": ds.sha256,
                    **capability,
                }
            )
    fields = sorted({key for row in rows for key in row})
    write_csv(RV_ROOT / "high_fidelity" / "high_fidelity_reference_checks.csv", rows, fields)
    write_json(RV_ROOT / "high_fidelity" / "high_fidelity_reference_checks.json", {"schema": "paper1_high_fidelity_reference_checks_v1", "capability": capability, "rows": rows})
    return {"recorded_pair_checks": len(rows)}


def value_stats(values: Sequence[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {"mean": None, "stdev": None, "min": None, "max": None, "ci95_half_width": None}
    stdev = statistics.stdev(values) if len(values) > 1 else None
    ci = 1.96 * stdev / math.sqrt(len(values)) if stdev is not None and len(values) > 1 else None
    return {"mean": statistics.fmean(values), "stdev": stdev, "min": min(values), "max": max(values), "ci95_half_width": ci}


def summarize_repeated_results() -> Dict[str, Any]:
    artifacts: Dict[str, Any] = {}
    cached_rows = json.loads((RV_ROOT / "cached_vg" / "cached_vg_campaign.json").read_text(encoding="utf-8"))["rows"]
    sens_rows = json.loads((RV_ROOT / "sensitivity" / "resolution_sensitivity.json").read_text(encoding="utf-8"))["rows"]
    summary_rows: List[Dict[str, Any]] = []
    for name, rows, keys in (
        ("cached_vg", cached_rows, ["topology", "environment_id"]),
        ("sensitivity", sens_rows, ["method_family", "topology", "parameter_name", "parameter_value"]),
    ):
        groups: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
        for row in rows:
            groups.setdefault(tuple(row.get(key) for key in keys), []).append(row)
        for key_values, group in sorted(groups.items()):
            times = [float(row["matrix_time_sec"]) for row in group if row.get("matrix_time_sec") is not None]
            stat = value_stats(times)
            out = {"campaign": name, "n": len(group), **dict(zip(keys, key_values)), **{f"matrix_time_{k}": v for k, v in stat.items()}}
            out["success_count"] = sum(1 for row in group if row.get("mission_success") is True)
            out["feasible_count"] = sum(1 for row in group if row.get("mission_feasible") is True)
            out["targets_serviced_values"] = ";".join(str(row.get("targets_serviced")) for row in group)
            out["mission_distance_values"] = ";".join(str(row.get("mission_distance_km")) for row in group)
            summary_rows.append(out)
    fields = sorted({key for row in summary_rows for key in row})
    out_csv = ANALYSIS_ROOT / "reviewer_validation_repeated_timing_summary.csv"
    out_json = ANALYSIS_ROOT / "reviewer_validation_repeated_timing_summary.json"
    write_csv(out_csv, summary_rows, fields)
    write_json(out_json, {"schema": "paper1_reviewer_validation_repeated_timing_summary_v1", "rows": summary_rows})
    artifacts["repeated_timing_summary_csv"] = rel(out_csv)
    artifacts["repeated_timing_summary_json"] = rel(out_json)
    return artifacts


def generate_figures() -> Dict[str, str]:
    import matplotlib.pyplot as plt

    artifacts: Dict[str, str] = {}
    sens_rows = json.loads((RV_ROOT / "sensitivity" / "resolution_sensitivity.json").read_text(encoding="utf-8"))["rows"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    for ax, family in zip(axes, ["visibility_graph", "grid_astar"]):
        rows = [row for row in sens_rows if row["method_family"] == family]
        for topology in TOPOLOGY_ORDER:
            vals = []
            params = sorted({float(row["parameter_value"]) for row in rows if row["topology"] == topology})
            for param in params:
                group = [float(row["matrix_time_sec"]) for row in rows if row["topology"] == topology and float(row["parameter_value"]) == param]
                vals.append(statistics.fmean(group))
            ax.plot(params, vals, marker="o", label=TOPOLOGY_DISPLAY[topology])
        ax.set_title("VG vertices/circle" if family == "visibility_graph" else "Grid spacing km")
        ax.set_xlabel("Parameter")
        ax.set_ylabel("Mean matrix time (s)")
        ax.grid(True, linewidth=0.3)
        ax.legend(fontsize=7)
    out = FIGURES_ROOT / "resolution_sensitivity_tradeoff.png"
    fig.savefig(out, dpi=220)
    plt.close(fig)
    artifacts["resolution_sensitivity"] = rel(out)

    cached = json.loads((RV_ROOT / "cached_vg" / "cached_vg_campaign.json").read_text(encoding="utf-8"))["rows"]
    fig, ax = plt.subplots(figsize=(7, 4), constrained_layout=True)
    labels = []
    values = []
    for topology in TOPOLOGY_ORDER:
        group = [float(row["total_preprocessing_time_sec"]) for row in cached if row["topology"] == topology]
        labels.append(TOPOLOGY_DISPLAY[topology])
        values.append(statistics.fmean(group))
    ax.bar(labels, values, color="#4c78a8")
    ax.set_ylabel("Mean cached VG preprocessing time (s)")
    ax.tick_params(axis="x", labelrotation=20)
    out = FIGURES_ROOT / "cached_vg_preprocessing_time.png"
    fig.savefig(out, dpi=220)
    plt.close(fig)
    artifacts["cached_vg"] = rel(out)
    return artifacts


def write_master_summary(campaign_dir: Path, phase_results: Dict[str, Any], env_info: Dict[str, Any], integrity: Dict[str, Any]) -> Dict[str, str]:
    timing_artifacts = summarize_repeated_results()
    figure_artifacts = generate_figures()
    cached_rows = json.loads((RV_ROOT / "cached_vg" / "cached_vg_campaign.json").read_text(encoding="utf-8"))["rows"]
    sens_rows = json.loads((RV_ROOT / "sensitivity" / "resolution_sensitivity.json").read_text(encoding="utf-8"))["rows"]
    cons_rows = json.loads((RV_ROOT / "conservatism" / "conservatism_stress_results.json").read_text(encoding="utf-8"))["rows"]
    hf_rows = json.loads((RV_ROOT / "high_fidelity" / "high_fidelity_reference_checks.json").read_text(encoding="utf-8"))["rows"]
    lines = [
        "# Reviewer-Validation Full Campaign Summary",
        "",
        f"Campaign directory: `{rel(campaign_dir)}`",
        f"Branch: `{BRANCH}`",
        f"Base commit: `{BASE_COMMIT}`",
        "",
        "## Execution Counts",
        "",
        f"- Cached VG recorded executions: `{len(cached_rows)}`",
        f"- Resolution sensitivity recorded executions: `{len(sens_rows)}`",
        f"- Conservatism stress environments: `{len(cons_rows)}`",
        f"- High-fidelity pair checks: `{len(hf_rows)}`",
        "",
        "## Connectivity",
        "",
        f"Frozen connectivity analysis rows: `{phase_results['connectivity']['rows']}`.",
        "Connectivity is reported at matrix level and is separate from mission success.",
        "",
        "## Cached Visibility Graph",
        "",
    ]
    for topology in TOPOLOGY_ORDER:
        group = [row for row in cached_rows if row["topology"] == topology]
        times = [float(row["total_preprocessing_time_sec"]) for row in group]
        stats = value_stats(times)
        ok = all(row["agreement_availability_equal"] for row in group)
        lines.append(f"- {TOPOLOGY_DISPLAY[topology]}: mean total preprocessing `{stats['mean']:.6f}` s; connectivity agreement with original VG: `{ok}`.")
    lines.extend(["", "## Resolution Sensitivity", ""])
    for family in ("visibility_graph", "grid_astar"):
        lines.append(f"### {family}")
        family_rows = [row for row in sens_rows if row["method_family"] == family]
        for param in sorted({float(row["parameter_value"]) for row in family_rows}):
            group = [row for row in family_rows if float(row["parameter_value"]) == param]
            times = [float(row["matrix_time_sec"]) for row in group]
            stats = value_stats(times)
            success = sum(1 for row in group if row["mission_success"])
            lines.append(f"- {param:g}: n={len(group)}, success={success}/{len(group)}, mean matrix={stats['mean']:.6f} s.")
        lines.append("")
    lines.extend(["## Conservatism Stress", ""])
    for row in cons_rows:
        lines.append(
            f"- {row['environment_id']}: native finite={row['native_finite_directed_pairs']}, "
            f"Proposed finite={row['proposed_finite_directed_pairs']}, "
            f"extra area={float(row['additional_area_excluded_km2']):.3f} km^2, "
            f"targets inside wrapped hull=`{row['targets_rendered_inaccessible_by_wrapped_hull']}`."
        )
    lines.extend(["", "## High-Fidelity Reference", ""])
    max_rel = max((float(row["relative_distance_error"] or 0.0) for row in hf_rows), default=0.0)
    max_abs = max((float(row["absolute_distance_difference_km"] or 0.0) for row in hf_rows), default=0.0)
    lines.append(f"The selected high-fidelity reference is polygonal, not mathematically exact. Max absolute distance difference: `{max_abs:.9f}` km; max relative error: `{max_rel:.9f}`.")
    lines.extend(
        [
            "",
            "## Timing Protocol",
            "",
            f"- Python: `{env_info['python_version_short']}` at `{env_info['python_executable']}`",
            f"- Platform: `{env_info['platform']}`",
            f"- CPU: `{env_info.get('cpu_name') or env_info.get('processor')}`",
            f"- RAM: `{env_info.get('total_physical_memory_gb')}` GB",
            "- Warm-up: cached VG uses one unrecorded matrix warm-up per environment; sensitivity uses zero warm-up; conservatism/high-fidelity are deterministic supplemental checks.",
            "- Order: deterministic by topology, instance, method family, parameter, repetition.",
            "",
            "## Frozen-Artifact Integrity",
            "",
            f"Integrity after campaign: `{integrity.get('comparison_to_prior', {}).get('all_ok')}`.",
            "",
            "## Artifacts",
            "",
        ]
    )
    for key, value in {**timing_artifacts, **figure_artifacts}.items():
        lines.append(f"- {key}: `{value}`")
    out = ANALYSIS_ROOT / "REVIEWER_VALIDATION_FULL_SUMMARY.md"
    write_text(out, "\n".join(lines) + "\n")
    write_json(
        ANALYSIS_ROOT / "reviewer_validation_campaign_summary.json",
        {
            "schema": "paper1_reviewer_validation_campaign_summary_v1",
            "created_at": now_iso(),
            "phase_results": phase_results,
            "timing_artifacts": timing_artifacts,
            "figure_artifacts": figure_artifacts,
            "integrity": integrity.get("comparison_to_prior", {}),
        },
    )
    return {"markdown": rel(out), "json": rel(ANALYSIS_ROOT / "reviewer_validation_campaign_summary.json")}


def build_revf_workspace(summary_artifacts: Dict[str, str]) -> Dict[str, Any]:
    import shutil

    source = REPO_ROOT / "paper_ieee_revE"
    PAPER_REVF_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "IEEEtran.cls", PAPER_REVF_ROOT / "IEEEtran.cls")
    shutil.copy2(source / "IEEEtran.bst", PAPER_REVF_ROOT / "IEEEtran.bst")
    shutil.copy2(source / "references.bib", PAPER_REVF_ROOT / "references.bib")
    (PAPER_REVF_ROOT / "figures").mkdir(exist_ok=True)
    for path in (source / "figures").glob("*"):
        if path.is_file():
            shutil.copy2(path, PAPER_REVF_ROOT / "figures" / path.name)
    for path in FIGURES_ROOT.glob("*.png"):
        shutil.copy2(path, PAPER_REVF_ROOT / "figures" / path.name)

    main = (source / "main.tex").read_text(encoding="utf-8")
    main = main.replace(
        "After Part I was frozen and published with immutable provenance",
        "After Part I was frozen and archived with immutable provenance",
    )
    main = main.replace(
        "Complete service in tested set; cost highly topology dependent",
        "Conservative geometric hierarchy; cost highly topology dependent",
    )
    main = main.replace("$O(N\\textasciicircum{}2)$", "$O(N^2)$")
    main = main.replace("O(N\\textasciicircum{}2)", "$O(N^2)$")
    insert = reviewer_validation_latex_section()
    marker = "\\section{Limitations}"
    if marker not in main:
        raise RuntimeError("could not find Limitations section marker")
    main = main.replace(marker, insert + "\n" + marker, 1)
    write_text(PAPER_REVF_ROOT / "main.tex", main)
    write_text(
        PAPER_REVF_ROOT / "README_BUILD.md",
        "# Rev F Full IEEEtran Build\n\nRun `latexmk -pdf -interaction=nonstopmode main.tex` from this directory.\n\nThe final PDF is copied to `Benchmarking_NFZ_Pairwise_RevF_Full_IEEE.pdf` after a successful build.\n",
    )

    completed = subprocess.run(
        ["latexmk", "-pdf", "-interaction=nonstopmode", "main.tex"],
        cwd=PAPER_REVF_ROOT,
        capture_output=True,
        text=True,
    )
    log_path = PAPER_REVF_ROOT / "latexmk_build.log"
    write_text(log_path, completed.stdout + "\n" + completed.stderr)
    if completed.returncode != 0:
        return {"compiled": False, "returncode": completed.returncode, "log": rel(log_path)}
    pdf = PAPER_REVF_ROOT / "main.pdf"
    final_pdf = PAPER_REVF_ROOT / "Benchmarking_NFZ_Pairwise_RevF_Full_IEEE.pdf"
    shutil.copy2(pdf, final_pdf)
    page_count = pdf_page_count(final_pdf)
    return {"compiled": True, "returncode": 0, "pdf": rel(final_pdf), "page_count": page_count, "log": rel(log_path)}


def latex_escape(text: Any) -> str:
    value = str(text)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in value)


def reviewer_validation_latex_section() -> str:
    cached = json.loads((RV_ROOT / "cached_vg" / "cached_vg_campaign.json").read_text(encoding="utf-8"))["rows"]
    sens = json.loads((RV_ROOT / "sensitivity" / "resolution_sensitivity.json").read_text(encoding="utf-8"))["rows"]
    cons = json.loads((RV_ROOT / "conservatism" / "conservatism_stress_results.json").read_text(encoding="utf-8"))["rows"]
    hf = json.loads((RV_ROOT / "high_fidelity" / "high_fidelity_reference_checks.json").read_text(encoding="utf-8"))["rows"]
    sensitivity_family_display = {"visibility_graph": "VG", "grid_astar": "Grid A*"}
    conservatism_case_display = {
        "target_in_concavity_seed_91001": "Target-in-concavity",
        "transit_through_concavity_seed_91002": "Transit-through-concavity",
        "increasing_conservatism_low_seed_91003": "Increasing low",
        "increasing_conservatism_medium_seed_91004": "Increasing medium",
        "increasing_conservatism_high_seed_91005": "Increasing high",
    }
    cached_lines = []
    for topology in TOPOLOGY_ORDER:
        group = [r for r in cached if r["topology"] == topology]
        total = value_stats([float(r["total_preprocessing_time_sec"]) for r in group])
        query = value_stats([float(r["matrix_query_time_sec"]) for r in group])
        cached_lines.append(
            f"{latex_escape(TOPOLOGY_DISPLAY[topology])} & {total['mean']:.3f} & {query['mean']:.3f} & {sum(1 for r in group if r['mission_success'])}/{len(group)} \\\\"
        )
    sens_lines = []
    for family in ("visibility_graph", "grid_astar"):
        for param in sorted({float(r["parameter_value"]) for r in sens if r["method_family"] == family}):
            group = [r for r in sens if r["method_family"] == family and float(r["parameter_value"]) == param]
            stat = value_stats([float(r["matrix_time_sec"]) for r in group])
            success = sum(1 for r in group if r["mission_success"])
            sens_lines.append(f"{latex_escape(sensitivity_family_display[family])} & {param:g} & {stat['mean']:.3f} & {stat['min']:.3f} & {stat['max']:.3f} & {success}/{len(group)} \\\\")
    cons_lines = []
    for row in cons:
        case_label = conservatism_case_display.get(row["environment_id"], row["environment_id"])
        cons_lines.append(
            f"{latex_escape(case_label)} & {row['native_finite_directed_pairs']} & {row['proposed_finite_directed_pairs']} & {float(row['additional_area_excluded_km2']):.2f} & {latex_escape(row['targets_rendered_inaccessible_by_wrapped_hull'] or 'none')} \\\\"
        )
    hf_max_abs = max((float(r["absolute_distance_difference_km"] or 0.0) for r in hf), default=0.0)
    hf_max_rel = max((float(r["relative_distance_error"] or 0.0) for r in hf), default=0.0)
    return r"""
\section{Supplemental Reviewer Validation}

This section reports predeclared supplemental validation conducted after the
351-execution primary benchmark was frozen and archived. These runs do not
replace the primary benchmark; they separate matrix connectivity from mission
success, test amortized Visibility Graph construction, characterize resolution
sensitivity, expose convex-wrapping applicability boundaries, and compare the
72-vertex Visibility Graph operating point with a very-high-resolution
polygonal reference.

\subsection{Matrix-Level Connectivity}

Frozen Part I and Part II mission artifacts were re-read without rerunning the
primary campaigns. For each stored distance matrix, finite directed pairs,
unavailable directed pairs, airport reachability, reverse reachability, strongly
connected components, excluded targets, and method-specific mission status were
recorded. This separates pairwise graph connectivity from the downstream
orienteering outcome.

\subsection{Cached Visibility Graph Supplement}

VG-cached builds the circular-obstacle polygonization and obstacle-boundary
visibility graph once per environment, then adds source and destination
visibility for each query. It is a supplemental amortized baseline; the original
pairwise Visibility Graph remains the primary benchmark method.

\begin{table}[!t]
\caption{Supplemental cached Visibility Graph timing}
\centering
\begingroup
\footnotesize
\begin{tabularx}{\columnwidth}{Xccc}
\hline
Topology & Total mean (s) & Query mean (s) & Success \\
\hline
""" + "\n".join(cached_lines) + r"""
\hline
\end{tabularx}
\endgroup
\end{table}

\subsection{Resolution Sensitivity}

The sensitivity campaign used only the predeclared Part II i03 instances. The
original engineered operating points remain 72 vertices per circular NFZ for
Visibility Graph and 1.0 km for Grid A*. The campaign characterizes these
choices rather than retuning them.

\begin{table}[!t]
\caption{Resolution-sensitivity timing summary}
\centering
\begingroup
\footnotesize
\begin{tabular}{llrrrr}
\hline
Family & Parameter & Mean & Min & Max & Success \\
\hline
""" + "\n".join(sens_lines) + r"""
\hline
\end{tabular}
\endgroup
\end{table}

\subsection{Convex-Wrapping Conservatism}

The conservatism stress cases intentionally place legal native-circle free
space inside the convex planning hull induced by overlapping NFZs. The reported
lost relationships are therefore an applicability-boundary measurement of the
declared conservative planning domain, not a failure of Proposed to solve a
problem outside that domain.

\begin{table}[!t]
\caption{Convex-wrapping conservatism stress summary}
\centering
\begingroup
\scriptsize
\begin{tabularx}{\columnwidth}{Xrrrr}
\hline
Case & Native & Proposed & Extra km$^2$ & Hull targets \\
\hline
""" + "\n".join(cons_lines) + r"""
\hline
\end{tabularx}
\endgroup
\end{table}

\subsection{High-Fidelity Reference Checks}

No repository implementation was identified as a mathematically exact
circular-obstacle shortest-path solver. The reference check therefore uses a
720-vertex polygonal Visibility Graph and does not describe that reference as
exact. Across the predeclared i03 pair subset, the maximum absolute difference
between the normal 72-vertex and 720-vertex polygonal results was """ + f"{hf_max_abs:.9f}" + r""" km, with maximum relative error """ + f"{hf_max_rel:.9f}" + r""".

\begin{figure}[!t]
\centering
\includegraphics[width=\columnwidth]{figures/resolution_sensitivity_tradeoff.png}
\caption{Supplemental resolution-sensitivity tradeoff for Visibility Graph and Grid A*.}
\end{figure}

\begin{figure}[!t]
\centering
\includegraphics[width=\columnwidth]{figures/cached_vg_preprocessing_time.png}
\caption{Supplemental cached Visibility Graph preprocessing time by topology.}
\end{figure}

"""


def pdf_page_count(path: Path) -> Optional[int]:
    try:
        completed = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True, check=False)
        for line in completed.stdout.splitlines():
            if line.startswith("Pages:"):
                return int(line.split(":", 1)[1].strip())
    except OSError:
        return None
    return None


def load_json_rows(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        raise RuntimeError(f"expected rows in {path}")
    return rows


def existing_phase_result(path: Path, expected_rows: int, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    rows = load_json_rows(path)
    if len(rows) != expected_rows:
        return None
    return {**result, "resumed_from_existing_artifact": True}


def campaign_timestamp_from_dir(campaign_dir: Path) -> str:
    name = campaign_dir.name
    prefix = "run_01_"
    if name.startswith(prefix):
        return name[len(prefix) :]
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def load_or_write_protected_before(timestamp: str, campaign_dir: Path) -> Dict[str, Any]:
    existing = sorted((campaign_dir / "validation").glob("protected_hashes_before_*.json"))
    if existing:
        return json.loads(existing[-1].read_text(encoding="utf-8"))
    return write_protected_hashes(f"before_{timestamp}", campaign_dir)


def run_campaign(resume_campaign_dir: Optional[Path] = None) -> int:
    preconditions = verify_preconditions()
    for directory in (
        RESULTS_ROOT,
        ANALYSIS_ROOT,
        FIGURES_ROOT,
        VALIDATION_ROOT,
        RV_ROOT / "connectivity",
        RV_ROOT / "cached_vg",
        RV_ROOT / "sensitivity",
        RV_ROOT / "conservatism",
        RV_ROOT / "high_fidelity",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    if resume_campaign_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        campaign_dir = RESULTS_ROOT / f"run_01_{timestamp}"
        if campaign_dir.exists():
            raise FileExistsError(campaign_dir)
        campaign_dir.mkdir(parents=True)
    else:
        campaign_dir = resume_campaign_dir
        if not campaign_dir.is_absolute():
            campaign_dir = REPO_ROOT / campaign_dir
        campaign_dir = campaign_dir.resolve()
        if not campaign_dir.exists():
            raise FileNotFoundError(campaign_dir)
        timestamp = campaign_timestamp_from_dir(campaign_dir)
    write_json(campaign_dir / "environment_provenance.json", preconditions)
    dataset_rows = load_dataset_rows()
    protected_before = load_or_write_protected_before(timestamp, campaign_dir)

    phase_results: Dict[str, Any] = {}
    phase_results["connectivity"] = run_connectivity_analysis(campaign_dir)
    phase_results["cached_vg"] = existing_phase_result(
        RV_ROOT / "cached_vg" / "cached_vg_campaign.json",
        45,
        {"recorded_executions": 45, "regression_environments": 15},
    ) or run_cached_vg_campaign(campaign_dir, dataset_rows)
    phase_results["sensitivity"] = existing_phase_result(
        RV_ROOT / "sensitivity" / "resolution_sensitivity.json",
        72,
        {"recorded_executions": 72},
    ) or run_sensitivity_campaign(campaign_dir, dataset_rows)
    phase_results["conservatism"] = run_conservatism_campaign(campaign_dir)
    phase_results["high_fidelity"] = existing_phase_result(
        RV_ROOT / "high_fidelity" / "high_fidelity_reference_checks.json",
        9,
        {"recorded_pair_checks": 9},
    ) or run_high_fidelity_checks(campaign_dir, dataset_rows)

    protected_after = write_protected_hashes(f"after_{timestamp}", campaign_dir, protected_before)
    summary_artifacts = write_master_summary(campaign_dir, phase_results, preconditions["environment_info"], protected_after)
    revf = build_revf_workspace(summary_artifacts)
    final_payload = {
        "schema": "paper1_reviewer_validation_full_campaign_v1",
        "created_at": now_iso(),
        "campaign_dir": rel(campaign_dir),
        "branch": preconditions["branch"],
        "git_commit": preconditions["git_commit"],
        "phase_results": phase_results,
        "summary_artifacts": summary_artifacts,
        "revf": revf,
        "protected_integrity": protected_after.get("comparison_to_prior", {}),
    }
    write_json(campaign_dir / "campaign_status.json", {**final_payload, "status": "complete"})
    write_json(RV_ROOT / "validation" / "latest_campaign_status.json", {**final_payload, "status": "complete"})
    print(json.dumps(final_payload, indent=2, sort_keys=True))
    return 0 if revf.get("compiled") and protected_after.get("comparison_to_prior", {}).get("all_ok") else 2


if __name__ == "__main__":
    resume = None
    if len(sys.argv) == 3 and sys.argv[1] == "--resume":
        resume = Path(sys.argv[2])
    elif len(sys.argv) != 1:
        raise SystemExit("usage: run_reviewer_validation.py [--resume CAMPAIGN_DIR]")
    raise SystemExit(run_campaign(resume))
