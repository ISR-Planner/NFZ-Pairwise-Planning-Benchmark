"""Direct-edge collision-rejection matrix builder."""

from __future__ import annotations

import copy
import math
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Tuple

from benchmark.matrix_builders import (
    DEFAULT_PLANNER_ROOT,
    MatrixBuild,
    configure_planner_imports,
)


UNAVAILABLE_COST = 99999.0
TOUCH_EPSILON_KM = 1e-9


class CollisionRejectionMatrixBuilder:
    """Build direct edges and reject any segment touching circular NFZs."""

    method = "collision_rejection"

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
        labels = [wp["id"] for wp in waypoints]
        n = len(waypoints)

        matrix: List[List[float]] = [[0.0] * n for _ in range(n)]
        paths: Dict[str, List[List[float]]] = {}
        accepted_pairs: List[Dict[str, Any]] = []
        rejected_pairs: List[Dict[str, Any]] = []

        adjacency = {label: set() for label in labels}

        for i in range(n):
            for j in range(i + 1, n):
                start = waypoints[i]
                end = waypoints[j]
                start_point = [float(start["x"]), float(start["y"])]
                end_point = [float(end["x"]), float(end["y"])]
                pair = [labels[i], labels[j]]

                blockers = [
                    sam["id"]
                    for sam in sams
                    if self._segment_touches_circle(start_point, end_point, sam)
                ]

                if blockers:
                    matrix[i][j] = UNAVAILABLE_COST
                    matrix[j][i] = UNAVAILABLE_COST
                    rejected_pairs.append({"pair": pair, "blocking_sams": blockers})
                    continue

                distance = math.hypot(
                    end_point[0] - start_point[0],
                    end_point[1] - start_point[1],
                )
                matrix[i][j] = distance
                matrix[j][i] = distance
                paths[f"{labels[i]}->{labels[j]}"] = [start_point, end_point]
                paths[f"{labels[j]}->{labels[i]}"] = [end_point, start_point]
                accepted_pairs.append({"pair": pair, "distance": distance})
                adjacency[labels[i]].add(labels[j])
                adjacency[labels[j]].add(labels[i])

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
                    "sam_mode": "original_circles_reject_only",
                    "unavailable_cost": UNAVAILABLE_COST,
                },
                "collision_rejection": {
                    "accepted_pairs": accepted_pairs,
                    "rejected_pairs": rejected_pairs,
                    "connected": self._is_connected(labels, adjacency),
                    "unavailable_cost": UNAVAILABLE_COST,
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

    def _segment_touches_circle(
        self,
        start: List[float],
        end: List[float],
        sam: Dict[str, Any],
    ) -> bool:
        center = sam["pos"]
        radius = float(sam["range"])
        distance = self._point_to_segment_distance(
            (float(center[0]), float(center[1])),
            (float(start[0]), float(start[1])),
            (float(end[0]), float(end[1])),
        )
        return distance <= radius + TOUCH_EPSILON_KM

    def _point_to_segment_distance(
        self,
        point: Tuple[float, float],
        start: Tuple[float, float],
        end: Tuple[float, float],
    ) -> float:
        sx, sy = start
        ex, ey = end
        px, py = point
        dx = ex - sx
        dy = ey - sy
        length_sq = dx * dx + dy * dy
        if length_sq == 0.0:
            return math.hypot(px - sx, py - sy)

        t = ((px - sx) * dx + (py - sy) * dy) / length_sq
        t = max(0.0, min(1.0, t))
        closest_x = sx + t * dx
        closest_y = sy + t * dy
        return math.hypot(px - closest_x, py - closest_y)

    def _is_connected(self, labels: List[str], adjacency: Dict[str, set]) -> bool:
        if not labels:
            return True

        seen = {labels[0]}
        queue = deque([labels[0]])
        while queue:
            node = queue.popleft()
            for neighbor in adjacency[node]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)

        return len(seen) == len(labels)

