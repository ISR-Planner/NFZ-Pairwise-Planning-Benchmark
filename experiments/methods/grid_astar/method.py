"""Deterministic 8-connected Grid A* matrix builder."""

from __future__ import annotations

import copy
import heapq
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from benchmark.matrix_builders import (
    DEFAULT_PLANNER_ROOT,
    MatrixBuild,
    configure_planner_imports,
)


GRID_SPACING_KM = 1.0
DOMAIN_MIN_KM = -75.0
DOMAIN_MAX_KM = 75.0
UNAVAILABLE_COST = 99999.0
COLLISION_EPSILON_KM = 1e-9
POINT_KEY_PRECISION = 9

NEIGHBOR_OFFSETS: Tuple[Tuple[int, int], ...] = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
)

Point = Tuple[float, float]


class GridAStarMatrixBuilder:
    """Build pairwise shortest paths on a fixed 1 km 8-connected grid."""

    method = "grid_astar"

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
        grid = _Grid(sams)

        labels = [wp["id"] for wp in waypoints]
        n = len(waypoints)
        matrix: List[List[float]] = [[0.0] * n for _ in range(n)]
        paths: Dict[str, List[List[float]]] = {}
        pair_results: List[Dict[str, Any]] = []
        total_expanded_nodes = 0

        for i in range(n):
            for j in range(i + 1, n):
                start = (float(waypoints[i]["x"]), float(waypoints[i]["y"]))
                end = (float(waypoints[j]["x"]), float(waypoints[j]["y"]))
                direct_distance = _distance(start, end)
                path, expanded_nodes = grid.shortest_path(start, end)
                total_expanded_nodes += expanded_nodes

                if path is None:
                    matrix[i][j] = UNAVAILABLE_COST
                    matrix[j][i] = UNAVAILABLE_COST
                    pair_results.append(
                        {
                            "pair": [labels[i], labels[j]],
                            "direct_distance": direct_distance,
                            "grid_astar_distance": UNAVAILABLE_COST,
                            "path_point_count": 0,
                            "expanded_nodes": expanded_nodes,
                            "status": "UNAVAILABLE",
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
                        "pair": [labels[i], labels[j]],
                        "direct_distance": direct_distance,
                        "grid_astar_distance": distance,
                        "path_point_count": len(path),
                        "expanded_nodes": expanded_nodes,
                        "status": "AVAILABLE",
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
                    "sam_mode": "original_circles_grid_astar",
                    "unavailable_cost": UNAVAILABLE_COST,
                },
                "grid_astar": {
                    "grid_spacing_km": GRID_SPACING_KM,
                    "domain_min_km": DOMAIN_MIN_KM,
                    "domain_max_km": DOMAIN_MAX_KM,
                    "grid_width": grid.width,
                    "grid_height": grid.height,
                    "total_regular_grid_vertices": grid.total_vertices,
                    "blocked_regular_grid_vertices": grid.blocked_vertices,
                    "free_regular_grid_vertices": grid.free_vertices,
                    "valid_regular_grid_edges": grid.valid_edges,
                    "total_astar_expanded_nodes": total_expanded_nodes,
                    "neighbor_offsets": [list(offset) for offset in NEIGHBOR_OFFSETS],
                    "pair_results": pair_results,
                    "unavailable_cost": UNAVAILABLE_COST,
                    "collision_epsilon_km": COLLISION_EPSILON_KM,
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


class _Grid:
    def __init__(self, sams: List[Dict[str, Any]]) -> None:
        self.sams = sams
        self.width = int(round((DOMAIN_MAX_KM - DOMAIN_MIN_KM) / GRID_SPACING_KM)) + 1
        self.height = self.width
        self.total_vertices = self.width * self.height
        self._free = [True] * self.total_vertices
        self._adjacency: List[List[Tuple[float, int]]] = [
            [] for _ in range(self.total_vertices)
        ]

        self._classify_vertices()
        self.blocked_vertices = sum(1 for is_free in self._free if not is_free)
        self.free_vertices = self.total_vertices - self.blocked_vertices
        self.valid_edges = self._build_regular_edges()

    def shortest_path(
        self,
        start: Point,
        end: Point,
    ) -> Tuple[Optional[List[Point]], int]:
        start_connectors = self._endpoint_connectors(start)
        end_connectors = self._endpoint_connectors(end)
        if not start_connectors or not end_connectors:
            return None, 0

        start_node = self.total_vertices
        end_node = self.total_vertices + 1
        distances: Dict[int, float] = {start_node: 0.0}
        previous: Dict[int, int] = {}
        expanded_nodes = 0
        tie = 0
        heap: List[Tuple[float, float, int, int]] = [
            (_distance(start, end), 0.0, tie, start_node)
        ]

        while heap:
            _, current_distance, _, current = heapq.heappop(heap)
            if current_distance > distances.get(current, math.inf) + 1e-12:
                continue

            expanded_nodes += 1
            if current == end_node:
                break

            for edge_cost, neighbor in self._neighbors_for_search(
                current,
                start_connectors,
                end_connectors,
            ):
                candidate = current_distance + edge_cost
                if candidate + 1e-12 < distances.get(neighbor, math.inf):
                    distances[neighbor] = candidate
                    previous[neighbor] = current
                    tie += 1
                    priority = candidate + self._heuristic(neighbor, end)
                    heapq.heappush(heap, (priority, candidate, tie, neighbor))

        if end_node not in distances:
            return None, expanded_nodes

        node_path = [end_node]
        current = end_node
        while current != start_node:
            current = previous[current]
            node_path.append(current)
        node_path.reverse()

        points = [
            self._search_node_point(node, start, end)
            for node in node_path
        ]
        return _remove_consecutive_duplicates(points), expanded_nodes

    def _classify_vertices(self) -> None:
        for index in range(self.total_vertices):
            point = self._point(index)
            if _point_blocked_by_sams(point, self.sams):
                self._free[index] = False

    def _build_regular_edges(self) -> int:
        edge_count = 0
        for index in range(self.total_vertices):
            if not self._free[index]:
                continue
            ix, iy = self._index_to_xy(index)
            start = self._point(index)
            for dx, dy in NEIGHBOR_OFFSETS:
                nx = ix + dx
                ny = iy + dy
                if not self._in_bounds(nx, ny):
                    continue
                neighbor = self._xy_to_index(nx, ny)
                if neighbor <= index or not self._free[neighbor]:
                    continue
                end = self._point(neighbor)
                if _segment_blocked_by_sams(start, end, self.sams):
                    continue
                cost = _distance(start, end)
                self._adjacency[index].append((cost, neighbor))
                self._adjacency[neighbor].append((cost, index))
                edge_count += 1

        for neighbors in self._adjacency:
            neighbors.sort(key=lambda item: (item[0], item[1]))
        return edge_count

    def _endpoint_connectors(self, endpoint: Point) -> List[Tuple[float, int]]:
        if _point_blocked_by_sams(endpoint, self.sams):
            return []

        center_ix = self._nearest_grid_index(endpoint[0])
        center_iy = self._nearest_grid_index(endpoint[1])
        max_ring = max(self.width, self.height)

        for ring in range(1, max_ring):
            connectors: List[Tuple[float, int]] = []
            for ix, iy in self._ring_indices(center_ix, center_iy, ring):
                index = self._xy_to_index(ix, iy)
                if not self._free[index]:
                    continue
                grid_point = self._point(index)
                if _segment_blocked_by_sams(endpoint, grid_point, self.sams):
                    continue
                connectors.append((_distance(endpoint, grid_point), index))

            if connectors:
                return sorted(connectors, key=lambda item: (item[0], item[1]))

        return []

    def _ring_indices(
        self,
        center_ix: int,
        center_iy: int,
        ring: int,
    ) -> Iterable[Tuple[int, int]]:
        candidates: List[Tuple[int, int]] = []
        for ix in range(center_ix - ring, center_ix + ring + 1):
            for iy in range(center_iy - ring, center_iy + ring + 1):
                if not self._in_bounds(ix, iy):
                    continue
                if ring > 1 and max(abs(ix - center_ix), abs(iy - center_iy)) != ring:
                    continue
                candidates.append((ix, iy))
        return sorted(candidates)

    def _neighbors_for_search(
        self,
        node: int,
        start_connectors: List[Tuple[float, int]],
        end_connectors: List[Tuple[float, int]],
    ) -> List[Tuple[float, int]]:
        start_node = self.total_vertices
        end_node = self.total_vertices + 1
        if node == start_node:
            return [(cost, index) for cost, index in start_connectors]
        if node == end_node:
            return []

        neighbors = list(self._adjacency[node])
        for cost, index in end_connectors:
            if node == index:
                neighbors.append((cost, end_node))
        return sorted(neighbors, key=lambda item: (item[0], item[1]))

    def _heuristic(self, node: int, end: Point) -> float:
        if node == self.total_vertices + 1:
            return 0.0
        if node == self.total_vertices:
            return 0.0
        return _distance(self._point(node), end)

    def _search_node_point(self, node: int, start: Point, end: Point) -> Point:
        if node == self.total_vertices:
            return start
        if node == self.total_vertices + 1:
            return end
        return self._point(node)

    def _nearest_grid_index(self, value: float) -> int:
        raw = round((value - DOMAIN_MIN_KM) / GRID_SPACING_KM)
        return max(0, min(self.width - 1, int(raw)))

    def _point(self, index: int) -> Point:
        ix, iy = self._index_to_xy(index)
        return (
            DOMAIN_MIN_KM + ix * GRID_SPACING_KM,
            DOMAIN_MIN_KM + iy * GRID_SPACING_KM,
        )

    def _index_to_xy(self, index: int) -> Tuple[int, int]:
        return index // self.height, index % self.height

    def _xy_to_index(self, ix: int, iy: int) -> int:
        return ix * self.height + iy

    def _in_bounds(self, ix: int, iy: int) -> bool:
        return 0 <= ix < self.width and 0 <= iy < self.height


def _point_blocked_by_sams(point: Point, sams: List[Dict[str, Any]]) -> bool:
    return any(
        _distance(point, (float(sam["pos"][0]), float(sam["pos"][1])))
        <= float(sam["range"]) + COLLISION_EPSILON_KM
        for sam in sams
    )


def _segment_blocked_by_sams(
    start: Point,
    end: Point,
    sams: List[Dict[str, Any]],
) -> bool:
    return any(
        _point_to_segment_distance(
            (float(sam["pos"][0]), float(sam["pos"][1])),
            start,
            end,
        )
        <= float(sam["range"]) + COLLISION_EPSILON_KM
        for sam in sams
    )


def _point_to_segment_distance(point: Point, start: Point, end: Point) -> float:
    sx, sy = start
    ex, ey = end
    px, py = point
    dx = ex - sx
    dy = ey - sy
    length_sq = dx * dx + dy * dy
    if length_sq <= COLLISION_EPSILON_KM * COLLISION_EPSILON_KM:
        return _distance(point, start)

    t = ((px - sx) * dx + (py - sy) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    closest = (sx + t * dx, sy + t * dy)
    return _distance(point, closest)


def _distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _path_length(path: List[Point]) -> float:
    return sum(_distance(path[i], path[i + 1]) for i in range(len(path) - 1))


def _remove_consecutive_duplicates(points: List[Point]) -> List[Point]:
    cleaned: List[Point] = []
    previous_key: Optional[Tuple[float, float]] = None
    for point in points:
        key = _point_key(point)
        if key != previous_key:
            cleaned.append(point)
            previous_key = key
    return cleaned


def _point_key(point: Point) -> Tuple[float, float]:
    return (round(point[0], POINT_KEY_PRECISION), round(point[1], POINT_KEY_PRECISION))


def _points_to_lists(points: List[Point]) -> List[List[float]]:
    return [[float(point[0]), float(point[1])] for point in points]
