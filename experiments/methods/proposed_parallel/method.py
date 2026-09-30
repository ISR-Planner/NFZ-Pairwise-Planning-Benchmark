"""Experimental process-parallel wrapper for Doc's proposed SAM matrix."""

from __future__ import annotations

import copy
import math
import multiprocessing
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmark.matrix_builders import (
    DEFAULT_PLANNER_ROOT,
    MatrixBuild,
    configure_planner_imports,
)


PROPOSED_PARALLEL_WORKERS = 4
UNAVAILABLE_COST = 99999.0


def _calculate_directed_pair(task: Dict[str, Any]) -> Dict[str, Any]:
    """Windows-spawn-compatible worker for one directed matrix entry."""

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    planner_root = Path(task["planner_root"]).resolve()
    if str(planner_root) not in sys.path:
        sys.path.insert(0, str(planner_root))

    from server.solver.sam_distance_matrix import SAMDistanceMatrixCalculator

    calculator = SAMDistanceMatrixCalculator()
    i = int(task["i"])
    j = int(task["j"])
    labels = task["labels"]
    start = task["start"]
    end = task["end"]
    sams = task["sams"]
    buffer = float(task["buffer"])

    path: Optional[List[List[float]]] = None
    method = "direct"
    if calculator._path_blocked(start, end, sams, buffer):
        path, distance, method = calculator._plan_sam_avoiding_path(
            start,
            end,
            sams,
            buffer,
        )
        if path is None or distance == float("inf"):
            distance = UNAVAILABLE_COST
            path = None
    else:
        distance = math.hypot(end[0] - start[0], end[1] - start[1])

    return {
        "i": i,
        "j": j,
        "source_id": labels[i],
        "destination_id": labels[j],
        "distance": float(distance),
        "path": path,
        "method": method,
    }


class ProposedParallelSAMMatrixBuilder:
    """Run the existing proposed directed pair calculations in processes."""

    method = "proposed_parallel"

    def __init__(
        self,
        *,
        planner_root: Path = DEFAULT_PLANNER_ROOT,
        buffer: float = 0.0,
        workers: int = PROPOSED_PARALLEL_WORKERS,
    ) -> None:
        self.planner_root = planner_root
        self.buffer = buffer
        self.workers = workers
        self._project_env_to_local_km = None
        self._calculator_cls = None
        self._point_in_polygon = None
        self._wrap_sams = None

    def prepare(self) -> None:
        configure_planner_imports(self.planner_root)

        from server.solver.projection import _project_env_to_local_km
        from server.solver.sam_distance_matrix import (
            SAMDistanceMatrixCalculator,
            point_in_polygon,
            wrap_sams,
        )

        self._project_env_to_local_km = _project_env_to_local_km
        self._calculator_cls = SAMDistanceMatrixCalculator
        self._point_in_polygon = point_in_polygon
        self._wrap_sams = wrap_sams

    def build(self, env: Dict[str, Any]) -> MatrixBuild:
        if self._project_env_to_local_km is None:
            self.prepare()

        if self.workers < 1:
            raise ValueError("proposed_parallel requires at least one worker")

        assert self._project_env_to_local_km is not None
        assert self._calculator_cls is not None
        projected_env, _, _ = self._project_env_to_local_km(copy.deepcopy(env))
        airports = list(projected_env.get("airports", []))
        targets = projected_env.get("targets", [])
        sams = projected_env.get("sams", [])

        for checkpoint in projected_env.get("checkpoints", []):
            airports.append(
                {
                    "id": str(checkpoint["id"]),
                    "x": float(checkpoint["x"]),
                    "y": float(checkpoint["y"]),
                    "is_checkpoint": True,
                }
            )

        for node_id, node_data in projected_env.get("synthetic_starts", {}).items():
            airports.append(
                {
                    "id": str(node_id),
                    "x": float(node_data["x"]),
                    "y": float(node_data["y"]),
                    "is_synthetic": True,
                }
            )

        calculator = self._calculator_cls()
        normalized_sams = calculator._normalize_sams(sams)
        valid_targets, excluded_inside_boundary, polygon_boundaries = (
            self._filter_valid_targets(targets, normalized_sams)
        )
        all_waypoints = calculator._build_waypoint_list(airports, valid_targets)
        labels = [wp["id"] for wp in all_waypoints]
        n = len(all_waypoints)

        matrix: List[List[float]] = [[0.0] * n for _ in range(n)]
        paths: Dict[str, List[List[float]]] = {}
        tasks = self._build_directed_tasks(all_waypoints, labels, normalized_sams)

        results: Dict[tuple[int, int], Dict[str, Any]] = {}
        mp_context = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(
            max_workers=self.workers,
            mp_context=mp_context,
        ) as executor:
            futures = [executor.submit(_calculate_directed_pair, task) for task in tasks]
            for future in as_completed(futures):
                result = future.result()
                results[(int(result["i"]), int(result["j"]))] = result

        for i in range(n):
            for j in range(n):
                if i == j:
                    matrix[i][j] = 0.0
                    continue

                result = results[(i, j)]
                distance = float(result["distance"])
                matrix[i][j] = distance
                if distance < UNAVAILABLE_COST and result.get("path") is not None:
                    paths[f"{labels[i]}->{labels[j]}"] = result["path"]

        waypoint_details = self._build_waypoint_details(all_waypoints)
        all_excluded = excluded_inside_boundary + self._unreachable_targets(
            airports=airports,
            valid_targets=valid_targets,
            all_waypoints=all_waypoints,
            matrix=matrix,
        )
        wrapped_polygon_lists = self._wrapped_polygon_lists(polygon_boundaries)

        result = {
            "matrix": matrix,
            "labels": labels,
            "waypoints": waypoint_details,
            "paths": paths,
            "excluded_targets": all_excluded,
            "sams": normalized_sams,
            "buffer": self.buffer,
            "wrapped_polygons": wrapped_polygon_lists,
        }
        self._add_serial_metadata(result, airports, targets, sams)

        diagnostics = {
            "method": self.method,
            "parallel_mechanism": "ProcessPoolExecutor",
            "worker_count": self.workers,
            "directed_task_count": len(tasks),
            "average_directed_tasks_per_worker": (
                len(tasks) / self.workers if self.workers else None
            ),
            "directed_pairs_calculated_independently": True,
            "symmetric_pairs_collapsed": False,
            "use_supabase_cache": False,
            "persistent_process_pool": False,
            "worker_pool_lifetime": "one matrix build",
        }
        result["proposed_parallel"] = diagnostics
        result["benchmark_diagnostics"] = diagnostics

        return MatrixBuild(method=self.method, data=result)

    def _filter_valid_targets(
        self,
        targets: List[Dict[str, Any]],
        normalized_sams: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[str], List[Any]]:
        valid_targets = []
        excluded_inside_boundary = []
        polygon_boundaries = []

        if self._wrap_sams and normalized_sams:
            sams_for_wrapping = [
                {"x": sam["pos"][0], "y": sam["pos"][1], "radius": sam["range"]}
                for sam in normalized_sams
            ]
            polygon_boundaries, _ = self._wrap_sams(sams_for_wrapping)

        for target in targets:
            tx, ty = float(target["x"]), float(target["y"])
            should_exclude = False

            for sam in normalized_sams:
                sam_x, sam_y = sam["pos"]
                sam_range = sam["range"]
                distance = math.sqrt((tx - sam_x) ** 2 + (ty - sam_y) ** 2)
                if distance < sam_range:
                    excluded_inside_boundary.append(target["id"])
                    should_exclude = True
                    break

            if not should_exclude:
                for polygon in polygon_boundaries:
                    if self._point_in_polygon((tx, ty), polygon):
                        excluded_inside_boundary.append(target["id"])
                        should_exclude = True
                        break

            if not should_exclude:
                valid_targets.append(target)

        return valid_targets, excluded_inside_boundary, polygon_boundaries

    def _build_directed_tasks(
        self,
        all_waypoints: List[Dict[str, Any]],
        labels: List[str],
        normalized_sams: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        tasks = []
        for i, start_wp in enumerate(all_waypoints):
            for j, end_wp in enumerate(all_waypoints):
                if i == j:
                    continue
                tasks.append(
                    {
                        "planner_root": str(self.planner_root),
                        "i": i,
                        "j": j,
                        "labels": labels,
                        "start": [start_wp["x"], start_wp["y"]],
                        "end": [end_wp["x"], end_wp["y"]],
                        "sams": normalized_sams,
                        "buffer": self.buffer,
                    }
                )
        return tasks

    def _build_waypoint_details(
        self,
        all_waypoints: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        details = []
        for wp in all_waypoints:
            detail = {
                "id": wp["id"],
                "x": float(wp["x"]),
                "y": float(wp["y"]),
            }
            if str(wp["id"]).startswith("T"):
                detail["priority"] = int(wp.get("priority", 5))
                detail["type"] = wp.get("type", "a")
            details.append(detail)
        return details

    def _unreachable_targets(
        self,
        *,
        airports: List[Dict[str, Any]],
        valid_targets: List[Dict[str, Any]],
        all_waypoints: List[Dict[str, Any]],
        matrix: List[List[float]],
    ) -> List[str]:
        airport_ids = [str(a["id"]) for a in airports]
        target_ids = [str(t["id"]) for t in valid_targets]
        id_to_index = {str(wp["id"]): idx for idx, wp in enumerate(all_waypoints)}
        unreachable_targets = []

        for target_id in target_ids:
            target_index = id_to_index.get(target_id)
            if target_index is None:
                continue

            reachable_from_any_airport = False
            for airport_id in airport_ids:
                airport_index = id_to_index.get(airport_id)
                if airport_index is None:
                    continue
                if matrix[airport_index][target_index] < UNAVAILABLE_COST:
                    reachable_from_any_airport = True
                    break

            if not reachable_from_any_airport:
                unreachable_targets.append(target_id)

        return unreachable_targets

    def _wrapped_polygon_lists(self, polygon_boundaries: List[Any]) -> List[Any]:
        wrapped_polygon_lists = []
        for polygon in polygon_boundaries:
            if hasattr(polygon, "tolist"):
                wrapped_polygon_lists.append(polygon.tolist())
            else:
                wrapped_polygon_lists.append(list(polygon))
        return wrapped_polygon_lists

    def _add_serial_metadata(
        self,
        result: Dict[str, Any],
        airports: List[Dict[str, Any]],
        targets: List[Dict[str, Any]],
        sams: List[Dict[str, Any]],
    ) -> None:
        try:
            from server.database.mission_ledger import compute_env_hash
            from server.database.mission_ledger import compute_routing_model_hash
            from server.database.mission_ledger import get_default_routing_model

            env_hash = compute_env_hash(airports, targets, sams)
            routing_model = get_default_routing_model()
            routing_model["sam_buffer"] = self.buffer
            routing_model_hash = compute_routing_model_hash(routing_model)

            result["env_hash"] = env_hash
            result["routing_model"] = routing_model
            result["routing_model_hash"] = routing_model_hash
            result["cache_hit"] = False
        except ImportError:
            pass
        except Exception as exc:
            print(f"Warning: failed to add proposed_parallel cache metadata: {exc}")
