"""Polygonal visibility-graph matrix builder for original circular SAM/NFZs."""

from __future__ import annotations

import copy
import heapq
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from benchmark.matrix_builders import (
    DEFAULT_PLANNER_ROOT,
    MatrixBuild,
    configure_planner_imports,
)


CIRCLE_VERTEX_COUNT = 72
UNAVAILABLE_COST = 99999.0
GEOMETRY_EPSILON_KM = 1e-9
POINT_KEY_PRECISION = 9

Point = Tuple[float, float]


class VisibilityGraphMatrixBuilder:
    """Build shortest paths through a polygonal visibility graph."""

    method = "visibility_graph"

    def __init__(self, *, planner_root: Path = DEFAULT_PLANNER_ROOT) -> None:
        self.planner_root = planner_root
        self._project_env_to_local_km = None

    def prepare(self) -> None:
        configure_planner_imports(self.planner_root)

        from server.solver.projection import _project_env_to_local_km

        self._project_env_to_local_km = _project_env_to_local_km

    def build(self, env: Dict[str, Any]) -> MatrixBuild:
        if self._project_env_to_local_km is None:
            self.prepare()

        assert self._project_env_to_local_km is not None
        projected_env, _, _ = self._project_env_to_local_km(copy.deepcopy(env))
        waypoints = self._build_waypoints(projected_env)
        sams = self._normalize_sams(projected_env)
        obstacles = self._build_obstacle_polygons(sams)
        boundary_vertices = self._union_boundary_vertices(obstacles)

        labels = [wp["id"] for wp in waypoints]
        n = len(waypoints)
        matrix: List[List[float]] = [[0.0] * n for _ in range(n)]
        paths: Dict[str, List[List[float]]] = {}
        pair_results: List[Dict[str, Any]] = []

        for i in range(n):
            for j in range(i + 1, n):
                start = (float(waypoints[i]["x"]), float(waypoints[i]["y"]))
                end = (float(waypoints[j]["x"]), float(waypoints[j]["y"]))
                pair = [labels[i], labels[j]]
                direct_distance = _distance(start, end)

                path = self._shortest_path(start, end, boundary_vertices, obstacles)
                if path is None:
                    matrix[i][j] = UNAVAILABLE_COST
                    matrix[j][i] = UNAVAILABLE_COST
                    pair_results.append(
                        {
                            "pair": pair,
                            "direct_distance": direct_distance,
                            "visibility_distance": UNAVAILABLE_COST,
                            "path_point_count": 0,
                            "classification": "UNAVAILABLE",
                        }
                    )
                    continue

                distance = _path_length(path)
                path_lists = _points_to_lists(path)
                matrix[i][j] = distance
                matrix[j][i] = distance
                paths[f"{labels[i]}->{labels[j]}"] = path_lists
                paths[f"{labels[j]}->{labels[i]}"] = list(reversed(path_lists))
                pair_results.append(
                    {
                        "pair": pair,
                        "direct_distance": direct_distance,
                        "visibility_distance": distance,
                        "path_point_count": len(path),
                        "classification": "DIRECT" if len(path) == 2 else "DETOUR",
                    }
                )

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
                    "sam_mode": "original_circles_visibility_graph",
                    "unavailable_cost": UNAVAILABLE_COST,
                },
                "visibility_graph": {
                    "circle_vertex_count": CIRCLE_VERTEX_COUNT,
                    "polygonal_obstacle_count": len(obstacles),
                    "obstacle_union_boundary_vertex_count": len(boundary_vertices),
                    "boundary_vertices": _points_to_lists(boundary_vertices),
                    "pair_results": pair_results,
                    "unavailable_cost": UNAVAILABLE_COST,
                    "geometry_epsilon_km": GEOMETRY_EPSILON_KM,
                },
            },
        )

    def _build_waypoints(self, env: Dict[str, Any]) -> List[Dict[str, Any]]:
        waypoints: List[Dict[str, Any]] = []

        for airport in env.get("airports", []):
            waypoints.append(
                {
                    "id": str(airport.get("id", f"A{len(waypoints) + 1}")),
                    "x": float(airport["x"]),
                    "y": float(airport["y"]),
                }
            )

        for checkpoint in env.get("checkpoints", []):
            waypoints.append(
                {
                    "id": str(checkpoint["id"]),
                    "x": float(checkpoint["x"]),
                    "y": float(checkpoint["y"]),
                    "is_checkpoint": True,
                }
            )

        for node_id, node_data in (env.get("synthetic_starts") or {}).items():
            waypoints.append(
                {
                    "id": str(node_id),
                    "x": float(node_data["x"]),
                    "y": float(node_data["y"]),
                    "is_synthetic": True,
                }
            )

        for target in env.get("targets", []):
            waypoints.append(
                {
                    "id": str(target.get("id", f"T{len(waypoints) + 1}")),
                    "x": float(target["x"]),
                    "y": float(target["y"]),
                    "priority": int(target.get("priority", 5)),
                    "type": target.get("type", "a"),
                }
            )

        return waypoints

    def _normalize_sams(self, env: Dict[str, Any]) -> List[Dict[str, Any]]:
        sams: List[Dict[str, Any]] = []
        for index, sam in enumerate(env.get("sams", []), start=1):
            pos = sam.get("pos") or sam.get("position")
            if pos is None and "x" in sam and "y" in sam:
                pos = [sam["x"], sam["y"]]
            if pos is None:
                continue

            sams.append(
                {
                    "id": str(sam.get("id") or sam.get("name") or f"SAM{index}"),
                    "pos": [float(pos[0]), float(pos[1])],
                    "range": float(sam.get("range", sam.get("radius", 0.0))),
                }
            )
        return sams

    def _build_obstacle_polygons(self, sams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        obstacles: List[Dict[str, Any]] = []
        step = 2.0 * math.pi / CIRCLE_VERTEX_COUNT
        for sam in sams:
            cx, cy = float(sam["pos"][0]), float(sam["pos"][1])
            radius = float(sam["range"])
            vertices = [
                (cx + radius * math.cos(k * step), cy + radius * math.sin(k * step))
                for k in range(CIRCLE_VERTEX_COUNT)
            ]
            obstacles.append({"id": sam["id"], "vertices": vertices})
        return obstacles

    def _union_boundary_vertices(
        self, obstacles: List[Dict[str, Any]]
    ) -> List[Point]:
        points: List[Point] = []

        for poly_index, obstacle in enumerate(obstacles):
            for vertex in obstacle["vertices"]:
                if not self._strictly_inside_any_other_polygon(
                    vertex, obstacles, poly_index
                ):
                    points.append(vertex)

        for i in range(len(obstacles)):
            vertices_a = obstacles[i]["vertices"]
            for j in range(i + 1, len(obstacles)):
                vertices_b = obstacles[j]["vertices"]
                for edge_a in _polygon_edges(vertices_a):
                    for edge_b in _polygon_edges(vertices_b):
                        for point in _segment_intersection_points(edge_a, edge_b):
                            if not self._strictly_inside_any_polygon(point, obstacles):
                                points.append(point)

        return _dedupe_points(points)

    def _strictly_inside_any_other_polygon(
        self,
        point: Point,
        obstacles: List[Dict[str, Any]],
        current_index: int,
    ) -> bool:
        for index, obstacle in enumerate(obstacles):
            if index == current_index:
                continue
            if _point_strictly_inside_convex_polygon(point, obstacle["vertices"]):
                return True
        return False

    def _strictly_inside_any_polygon(
        self, point: Point, obstacles: List[Dict[str, Any]]
    ) -> bool:
        return any(
            _point_strictly_inside_convex_polygon(point, obstacle["vertices"])
            for obstacle in obstacles
        )

    def _shortest_path(
        self,
        start: Point,
        end: Point,
        boundary_vertices: List[Point],
        obstacles: List[Dict[str, Any]],
    ) -> Optional[List[Point]]:
        if _points_close(start, end):
            return [start]
        if not self._segment_blocked_by_union(start, end, obstacles):
            return [start, end]
        if self._strictly_inside_any_polygon(start, obstacles):
            return None
        if self._strictly_inside_any_polygon(end, obstacles):
            return None

        graph_points = _dedupe_points([start, end, *boundary_vertices])
        start_index = _index_of_point(graph_points, start)
        end_index = _index_of_point(graph_points, end)
        adjacency: List[List[Tuple[float, int]]] = [[] for _ in graph_points]

        for i in range(len(graph_points)):
            for j in range(i + 1, len(graph_points)):
                a = graph_points[i]
                b = graph_points[j]
                if _points_close(a, b):
                    continue
                if self._segment_blocked_by_union(a, b, obstacles):
                    continue
                cost = _distance(a, b)
                adjacency[i].append((cost, j))
                adjacency[j].append((cost, i))

        for neighbors in adjacency:
            neighbors.sort(key=lambda item: (item[0], item[1]))

        distances = [math.inf] * len(graph_points)
        previous: List[Optional[int]] = [None] * len(graph_points)
        distances[start_index] = 0.0
        heap: List[Tuple[float, int]] = [(0.0, start_index)]

        while heap:
            current_distance, current = heapq.heappop(heap)
            if current_distance > distances[current] + GEOMETRY_EPSILON_KM:
                continue
            if current == end_index:
                break

            for edge_cost, neighbor in adjacency[current]:
                candidate = current_distance + edge_cost
                if candidate + GEOMETRY_EPSILON_KM < distances[neighbor]:
                    distances[neighbor] = candidate
                    previous[neighbor] = current
                    heapq.heappush(heap, (candidate, neighbor))

        if math.isinf(distances[end_index]):
            return None

        indices: List[int] = []
        current: Optional[int] = end_index
        while current is not None:
            indices.append(current)
            current = previous[current]
        indices.reverse()
        return [graph_points[index] for index in indices]

    def _segment_blocked_by_union(
        self,
        start: Point,
        end: Point,
        obstacles: List[Dict[str, Any]],
    ) -> bool:
        return any(
            _segment_intersects_polygon_interior(start, end, obstacle["vertices"])
            for obstacle in obstacles
        )


def _polygon_edges(vertices: List[Point]) -> List[Tuple[Point, Point]]:
    return [
        (vertices[i], vertices[(i + 1) % len(vertices)])
        for i in range(len(vertices))
    ]


def _segment_intersects_polygon_interior(
    start: Point,
    end: Point,
    vertices: List[Point],
) -> bool:
    if _point_strictly_inside_convex_polygon(start, vertices):
        return True
    if _point_strictly_inside_convex_polygon(end, vertices):
        return True

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    if dx * dx + dy * dy <= GEOMETRY_EPSILON_KM * GEOMETRY_EPSILON_KM:
        return False

    low = 0.0
    high = 1.0
    for a, b in _polygon_edges(vertices):
        edge_x = b[0] - a[0]
        edge_y = b[1] - a[1]
        c0 = _cross((edge_x, edge_y), (start[0] - a[0], start[1] - a[1]))
        c1 = _cross((edge_x, edge_y), (end[0] - a[0], end[1] - a[1]))
        delta = c1 - c0

        if abs(delta) <= GEOMETRY_EPSILON_KM:
            if c0 < -GEOMETRY_EPSILON_KM:
                return False
            continue

        t = -c0 / delta
        if delta > 0.0:
            low = max(low, t)
        else:
            high = min(high, t)

        if low - high > GEOMETRY_EPSILON_KM:
            return False

    if high - low <= GEOMETRY_EPSILON_KM:
        return False

    mid_t = (max(0.0, low) + min(1.0, high)) / 2.0
    mid = (start[0] + dx * mid_t, start[1] + dy * mid_t)
    return _point_strictly_inside_convex_polygon(mid, vertices)


def _point_strictly_inside_convex_polygon(point: Point, vertices: List[Point]) -> bool:
    for a, b in _polygon_edges(vertices):
        edge_x = b[0] - a[0]
        edge_y = b[1] - a[1]
        rel_x = point[0] - a[0]
        rel_y = point[1] - a[1]
        if _cross((edge_x, edge_y), (rel_x, rel_y)) <= GEOMETRY_EPSILON_KM:
            return False
    return True


def _segment_intersection_points(
    edge_a: Tuple[Point, Point],
    edge_b: Tuple[Point, Point],
) -> List[Point]:
    a, b = edge_a
    c, d = edge_b
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    denominator = _cross(r, s)
    c_minus_a = (c[0] - a[0], c[1] - a[1])

    if abs(denominator) <= GEOMETRY_EPSILON_KM:
        if abs(_cross(c_minus_a, r)) > GEOMETRY_EPSILON_KM:
            return []

        points = []
        for point in (a, b, c, d):
            if _point_on_segment(point, a, b) and _point_on_segment(point, c, d):
                points.append(point)
        return _dedupe_points(points)

    t = _cross(c_minus_a, s) / denominator
    u = _cross(c_minus_a, r) / denominator
    if (
        -GEOMETRY_EPSILON_KM <= t <= 1.0 + GEOMETRY_EPSILON_KM
        and -GEOMETRY_EPSILON_KM <= u <= 1.0 + GEOMETRY_EPSILON_KM
    ):
        t = min(1.0, max(0.0, t))
        return [(a[0] + t * r[0], a[1] + t * r[1])]
    return []


def _point_on_segment(point: Point, start: Point, end: Point) -> bool:
    if abs(_cross((end[0] - start[0], end[1] - start[1]), (point[0] - start[0], point[1] - start[1]))) > GEOMETRY_EPSILON_KM:
        return False
    return (
        min(start[0], end[0]) - GEOMETRY_EPSILON_KM
        <= point[0]
        <= max(start[0], end[0]) + GEOMETRY_EPSILON_KM
        and min(start[1], end[1]) - GEOMETRY_EPSILON_KM
        <= point[1]
        <= max(start[1], end[1]) + GEOMETRY_EPSILON_KM
    )


def _distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _path_length(path: List[Point]) -> float:
    return sum(_distance(path[i], path[i + 1]) for i in range(len(path) - 1))


def _points_close(a: Point, b: Point) -> bool:
    return _distance(a, b) <= GEOMETRY_EPSILON_KM


def _point_key(point: Point) -> Tuple[float, float]:
    return (round(point[0], POINT_KEY_PRECISION), round(point[1], POINT_KEY_PRECISION))


def _dedupe_points(points: List[Point]) -> List[Point]:
    deduped: Dict[Tuple[float, float], Point] = {}
    for point in points:
        deduped.setdefault(_point_key(point), (float(point[0]), float(point[1])))
    return [deduped[key] for key in sorted(deduped)]


def _index_of_point(points: List[Point], point: Point) -> int:
    key = _point_key(point)
    for index, candidate in enumerate(points):
        if _point_key(candidate) == key:
            return index
    raise ValueError(f"point not present in graph: {point}")


def _points_to_lists(points: List[Point]) -> List[List[float]]:
    return [[float(point[0]), float(point[1])] for point in points]


def _cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]
