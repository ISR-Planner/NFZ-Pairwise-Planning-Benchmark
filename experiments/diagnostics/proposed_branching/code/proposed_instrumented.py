"""Instrumented proposed-method matrix builder for isolated diagnostics.

This module intentionally lives outside ``methods/proposed``. It reproduces the
frozen serial proposed matrix-building flow while wrapping read-only planner
functions to collect per-directed-pair timing and search counters.
"""

from __future__ import annotations

import copy
import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


EXPERIMENTS_ROOT = Path(__file__).resolve().parents[3]
PLANNER_ROOT = Path(r"<local-path>\NFZ-Pairwise-Planning-Benchmark\NFZ-Pairwise-Planning-Benchmark")

if str(EXPERIMENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_ROOT))
if str(PLANNER_ROOT) not in sys.path:
    sys.path.insert(0, str(PLANNER_ROOT))

from benchmark.matrix_builders import configure_planner_imports


Point = Tuple[float, float]
Polygon = List[Point]


@dataclass
class PairDiagnostics:
    environment: str
    topology: str
    target_count: int
    node_count: int
    source: str
    destination: str
    pair_index: int
    pair_time_seconds: float = 0.0
    distance: float = 0.0
    path_points: int = 0
    available: bool = True
    direct_clear_checks: int = 0
    blocked_checks: int = 0
    sams_considered: int = 0
    wrapped_hulls_relevant: int = 0
    tangent_calls: int = 0
    tangent_candidates_generated: int = 0
    tangent_time_seconds: float = 0.0
    recursive_calls: int = 0
    branch_expansions: int = 0
    branches_discarded: int = 0
    branches_valid: int = 0
    max_recursion_depth: int = 0
    collision_tests: int = 0
    blocking_events: int = 0
    unique_blockers: int = 0
    reblocking_events: int = 0
    repeated_blocker_events: int = 0
    blocking_sequence: List[str] = field(default_factory=list)
    fallback_calls: int = 0
    fallback_time_seconds: str = "UNAVAILABLE"
    fallback_success: str = "UNAVAILABLE"
    method: str = ""
    direct_path_blocked: bool = False
    final_pair_distance: float = 0.0
    final_path_point_count: int = 0

    def record_blocker(self, blocker_id: str) -> None:
        self.blocking_sequence.append(blocker_id)
        self.blocking_events += 1
        self.unique_blockers = len(set(self.blocking_sequence))
        self.reblocking_events = max(0, self.blocking_events - 1)
        self.repeated_blocker_events = self.blocking_events - self.unique_blockers

    def as_row(self) -> Dict[str, Any]:
        row = {
            "environment": self.environment,
            "topology": self.topology,
            "target_count": self.target_count,
            "node_count": self.node_count,
            "source": self.source,
            "destination": self.destination,
            "pair_index": self.pair_index,
            "pair_time_seconds": self.pair_time_seconds,
            "distance": self.distance,
            "path_points": self.path_points,
            "available": self.available,
            "direct_clear_checks": self.direct_clear_checks,
            "blocked_checks": self.blocked_checks,
            "sams_considered": self.sams_considered,
            "wrapped_hulls_relevant": self.wrapped_hulls_relevant,
            "tangent_calls": self.tangent_calls,
            "tangent_candidates_generated": self.tangent_candidates_generated,
            "tangent_time_seconds": self.tangent_time_seconds,
            "recursive_calls": self.recursive_calls,
            "branch_expansions": self.branch_expansions,
            "branches_discarded": self.branches_discarded,
            "branches_valid": self.branches_valid,
            "max_recursion_depth": self.max_recursion_depth,
            "collision_tests": self.collision_tests,
            "blocking_events": self.blocking_events,
            "unique_blockers": self.unique_blockers,
            "reblocking_events": self.reblocking_events,
            "repeated_blocker_events": self.repeated_blocker_events,
            "blocking_sequence": ";".join(self.blocking_sequence),
            "fallback_calls": self.fallback_calls,
            "fallback_time_seconds": self.fallback_time_seconds,
            "fallback_success": self.fallback_success,
            "method": self.method,
            "direct_path_blocked": self.direct_path_blocked,
            "final_pair_distance": self.final_pair_distance,
            "final_path_point_count": self.final_path_point_count,
        }
        return row


class BoundaryFunctionInstrumentation:
    """Temporarily wrap boundary-navigation helpers for one pair calculation."""

    def __init__(self, pair: PairDiagnostics) -> None:
        configure_planner_imports(PLANNER_ROOT)
        import path_planning_core.boundary_navigation as boundary_navigation

        self.boundary_navigation = boundary_navigation
        self.pair = pair
        self._originals: Dict[str, Callable[..., Any]] = {}
        self._polygon_ids: Dict[int, str] = {}

    def __enter__(self) -> "BoundaryFunctionInstrumentation":
        bn = self.boundary_navigation
        self._patch("wrap_sams", self._wrap_sams)
        self._patch("_find_tangent_vertices", self._find_tangent_vertices)
        self._patch("_segment_intersects_segment", self._segment_intersects_segment)
        self._patch("_segment_crosses_polygon", self._segment_crosses_polygon)
        self._patch("_find_blocking_polygon", self._find_blocking_polygon)
        self._patch("_find_first_visible_exit", self._find_first_visible_exit)
        self._patch("_segment_clear_of_all_polygons", self._segment_clear_of_all_polygons)
        self._patch("_validate_path", self._validate_path)
        self._patch("_build_visibility_graph", self._build_visibility_graph)
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        for name, original in self._originals.items():
            setattr(self.boundary_navigation, name, original)

    def _patch(self, name: str, replacement: Callable[..., Any]) -> None:
        self._originals[name] = getattr(self.boundary_navigation, name)
        setattr(self.boundary_navigation, name, replacement)

    def _polygon_id(self, polygon: Polygon) -> str:
        key = id(polygon)
        if key in self._polygon_ids:
            return self._polygon_ids[key]
        for existing_id, label in self._polygon_ids.items():
            _ = existing_id
            if label:
                continue
        return "H?"

    def _refresh_polygon_ids(self, polygons: List[Polygon]) -> None:
        self._polygon_ids = {id(poly): f"H{idx}" for idx, poly in enumerate(polygons)}
        self.pair.wrapped_hulls_relevant = len(polygons)

    def _wrap_sams(self, *args: Any, **kwargs: Any) -> Any:
        polygons, metadata = self._originals["wrap_sams"](*args, **kwargs)
        self._refresh_polygon_ids(polygons)
        return polygons, metadata

    def _find_tangent_vertices(self, *args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = self._originals["_find_tangent_vertices"](*args, **kwargs)
        elapsed = time.perf_counter() - start
        self.pair.tangent_calls += 1
        self.pair.tangent_candidates_generated += 2
        self.pair.tangent_time_seconds += elapsed
        return result

    def _segment_intersects_segment(self, *args: Any, **kwargs: Any) -> Any:
        self.pair.collision_tests += 1
        return self._originals["_segment_intersects_segment"](*args, **kwargs)

    def _segment_crosses_polygon(self, a: Point, b: Point, polygon: Polygon) -> Any:
        self.pair.collision_tests += 1
        result = self._originals["_segment_crosses_polygon"](a, b, polygon)
        if result:
            self.pair.record_blocker(self._polygon_id(polygon))
        return result

    def _find_blocking_polygon(self, *args: Any, **kwargs: Any) -> Any:
        return self._originals["_find_blocking_polygon"](*args, **kwargs)

    def _find_first_visible_exit(self, *args: Any, **kwargs: Any) -> Any:
        self.pair.branch_expansions += 1
        return self._originals["_find_first_visible_exit"](*args, **kwargs)

    def _segment_clear_of_all_polygons(self, *args: Any, **kwargs: Any) -> Any:
        self.pair.branch_expansions += 1
        return self._originals["_segment_clear_of_all_polygons"](*args, **kwargs)

    def _validate_path(self, *args: Any, **kwargs: Any) -> Any:
        result = self._originals["_validate_path"](*args, **kwargs)
        if result:
            self.pair.branches_valid += 1
        else:
            self.pair.branches_discarded += 1
        return result

    def _build_visibility_graph(self, start: Point, goal: Point, polygons: List[Polygon], debug: bool = False) -> Any:
        self._refresh_polygon_ids(polygons)
        return self._originals["_build_visibility_graph"](start, goal, polygons, debug)


class InstrumentedProposedCalculator:
    """Diagnostic reproduction of the proposed serial matrix calculator."""

    def __init__(self, environment: str, topology: str, target_count: int) -> None:
        configure_planner_imports(PLANNER_ROOT)
        import server.solver.sam_distance_matrix as sam_distance_matrix
        from server.solver.projection import _project_env_to_local_km

        self.sdm = sam_distance_matrix
        self._project_env_to_local_km = _project_env_to_local_km
        self.environment = environment
        self.topology = topology
        self.target_count = target_count
        self.pair_rows: List[Dict[str, Any]] = []

    def calculate(self, env: Dict[str, Any], buffer: float = 0.0) -> Dict[str, Any]:
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

        matrix_start = time.perf_counter()
        result = self._calculate_matrix(airports, targets, sams, buffer)
        matrix_elapsed = time.perf_counter() - matrix_start
        result["diagnostic_pair_rows"] = self.pair_rows
        result["diagnostic_summary"] = {
            "environment": self.environment,
            "topology": self.topology,
            "target_count": self.target_count,
            "instrumented_matrix_time_seconds": matrix_elapsed,
            "serial_pair_time_seconds": sum(
                float(row["pair_time_seconds"]) for row in self.pair_rows
            ),
            "pair_count": len(self.pair_rows),
            "source": "diagnostics/proposed_branching/code/proposed_instrumented.py",
        }
        return result

    def _calculate_matrix(
        self,
        airports: List[Dict[str, Any]],
        targets: List[Dict[str, Any]],
        sams: List[Dict[str, Any]],
        buffer: float,
    ) -> Dict[str, Any]:
        normalized_sams = self.sdm._calculator._normalize_sams(sams)
        excluded_inside_boundary: List[str] = []
        valid_targets: List[Dict[str, Any]] = []

        polygon_boundaries: List[Any] = []
        if self.sdm.wrap_sams and normalized_sams:
            sams_for_wrapping = [
                {"x": sam["pos"][0], "y": sam["pos"][1], "radius": sam["range"]}
                for sam in normalized_sams
            ]
            wrapped_polygons, _ = self.sdm.wrap_sams(sams_for_wrapping)
            polygon_boundaries = wrapped_polygons

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
                    if self.sdm.point_in_polygon((tx, ty), polygon):
                        excluded_inside_boundary.append(target["id"])
                        should_exclude = True
                        break

            if not should_exclude:
                valid_targets.append(target)

        all_waypoints = self.sdm._calculator._build_waypoint_list(airports, valid_targets)
        labels = [waypoint["id"] for waypoint in all_waypoints]
        node_count = len(all_waypoints)
        matrix: List[List[float]] = [[0.0] * node_count for _ in range(node_count)]
        paths: Dict[str, List[List[float]]] = {}

        pair_index = 0
        for i in range(node_count):
            for j in range(node_count):
                if i == j:
                    matrix[i][j] = 0.0
                    continue

                pair_index += 1
                start_point = [all_waypoints[i]["x"], all_waypoints[i]["y"]]
                end_point = [all_waypoints[j]["x"], all_waypoints[j]["y"]]
                pair = PairDiagnostics(
                    environment=self.environment,
                    topology=self.topology,
                    target_count=self.target_count,
                    node_count=node_count,
                    source=labels[i],
                    destination=labels[j],
                    pair_index=pair_index,
                )

                pair_start = time.perf_counter()
                blocked = self._path_blocked(start_point, end_point, normalized_sams, buffer, pair)
                pair.direct_path_blocked = blocked
                if blocked:
                    path, distance, method = self._plan_sam_avoiding_path(
                        start_point, end_point, normalized_sams, buffer, pair
                    )
                    pair.method = method
                    if path is None or distance == float("inf"):
                        matrix[i][j] = 99999.0
                        pair.distance = 99999.0
                        pair.path_points = 0
                        pair.available = False
                    else:
                        matrix[i][j] = distance
                        key = f"{labels[i]}->{labels[j]}"
                        paths[key] = path
                        pair.distance = distance
                        pair.path_points = len(path)
                        pair.available = True
                else:
                    distance = math.hypot(
                        end_point[0] - start_point[0],
                        end_point[1] - start_point[1],
                    )
                    matrix[i][j] = distance
                    pair.distance = distance
                    pair.path_points = 2
                    pair.available = True
                    pair.method = "direct"
                pair.pair_time_seconds = time.perf_counter() - pair_start
                pair.final_pair_distance = pair.distance
                pair.final_path_point_count = pair.path_points
                self.pair_rows.append(pair.as_row())

        waypoint_details = []
        for waypoint in all_waypoints:
            detail = {
                "id": waypoint["id"],
                "x": float(waypoint["x"]),
                "y": float(waypoint["y"]),
            }
            if str(waypoint["id"]).startswith("T"):
                detail["priority"] = int(waypoint.get("priority", 5))
                detail["type"] = waypoint.get("type", "a")
            waypoint_details.append(detail)

        airport_ids = [str(airport["id"]) for airport in airports]
        target_ids = [str(target["id"]) for target in valid_targets]
        id_to_index = {str(waypoint["id"]): idx for idx, waypoint in enumerate(all_waypoints)}
        unreachable_targets: List[str] = []
        for target_id in target_ids:
            target_idx = id_to_index.get(target_id)
            if target_idx is None:
                continue
            reachable = False
            for airport_id in airport_ids:
                airport_idx = id_to_index.get(airport_id)
                if airport_idx is None:
                    continue
                if matrix[airport_idx][target_idx] < 99999.0:
                    reachable = True
                    break
            if not reachable:
                unreachable_targets.append(target_id)

        wrapped_polygon_lists = []
        for polygon in polygon_boundaries:
            if hasattr(polygon, "tolist"):
                wrapped_polygon_lists.append(polygon.tolist())
            else:
                wrapped_polygon_lists.append(list(polygon))

        return {
            "matrix": matrix,
            "labels": labels,
            "waypoints": waypoint_details,
            "paths": paths,
            "excluded_targets": excluded_inside_boundary + unreachable_targets,
            "sams": normalized_sams,
            "buffer": buffer,
            "wrapped_polygons": wrapped_polygon_lists,
        }

    def _path_blocked(
        self,
        start: List[float],
        end: List[float],
        sams: List[Dict[str, Any]],
        buffer: float,
        pair: PairDiagnostics,
    ) -> bool:
        pair.direct_clear_checks += 1
        pair.sams_considered = len(sams)
        if not sams:
            return False

        for sam_index, sam in enumerate(sams, start=1):
            pair.blocked_checks += 1
            pair.collision_tests += 1
            pos = sam["pos"]
            radius = sam["range"] + buffer
            if self.sdm._calculator._line_intersects_circle(start, end, pos, radius):
                pair.record_blocker(str(sam.get("id") or f"SAM{sam_index}"))
                return True

        return False

    def _plan_sam_avoiding_path(
        self,
        start: List[float],
        end: List[float],
        sams: List[Dict[str, Any]],
        buffer: float,
        pair: PairDiagnostics,
    ) -> Tuple[Optional[List[List[float]]], float, str]:
        _ = buffer
        if not self.sdm.HAS_SAM_NAVIGATION:
            distance = math.hypot(end[0] - start[0], end[1] - start[1])
            return [start, end], distance, "direct (no SAM avoidance)"

        import path_planning_core.boundary_navigation as boundary_navigation

        try:
            with BoundaryFunctionInstrumentation(pair):
                path, distance, method = boundary_navigation.plan_path(start, end, sams)

            if str(method).startswith("FALLBACK"):
                pair.fallback_calls = 1
                pair.fallback_success = "true"
            elif str(method).startswith("INVALID"):
                pair.fallback_calls = 1 if "polygon" in str(method) else 0
                pair.fallback_success = "false" if pair.fallback_calls else "UNAVAILABLE"
            else:
                pair.fallback_calls = 0
                pair.fallback_success = "false"

            if path is not None and len(path) >= 2:
                return path, distance, method
            return None, float("inf"), "no_path_found"
        except Exception as exc:
            return None, float("inf"), f"error: {exc}"


def calculate_instrumented_proposed_matrix(
    env: Dict[str, Any],
    *,
    environment: str,
    topology: str,
    target_count: int,
    buffer: float = 0.0,
) -> Dict[str, Any]:
    calculator = InstrumentedProposedCalculator(
        environment=environment,
        topology=topology,
        target_count=target_count,
    )
    return calculator.calculate(env, buffer=buffer)
