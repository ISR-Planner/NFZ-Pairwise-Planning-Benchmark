"""Unrestricted Euclidean straight-line matrix builder."""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any, Dict, List

from benchmark.matrix_builders import (
    DEFAULT_PLANNER_ROOT,
    MatrixBuild,
    configure_planner_imports,
)


class EuclideanMatrixBuilder:
    """Build a direct-distance matrix that ignores all SAM/NFZ geometry."""

    method = "euclidean"

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
        labels = [wp["id"] for wp in waypoints]
        n = len(waypoints)

        matrix: List[List[float]] = [[0.0] * n for _ in range(n)]
        paths: Dict[str, List[List[float]]] = {}

        for i, start in enumerate(waypoints):
            for j, end in enumerate(waypoints):
                if i == j:
                    continue

                start_point = [float(start["x"]), float(start["y"])]
                end_point = [float(end["x"]), float(end["y"])]
                distance = math.hypot(
                    end_point[0] - start_point[0],
                    end_point[1] - start_point[1],
                )
                matrix[i][j] = distance
                paths[f"{labels[i]}->{labels[j]}"] = [start_point, end_point]

        return MatrixBuild(
            method=self.method,
            data={
                "matrix": matrix,
                "labels": labels,
                "waypoints": waypoints,
                "paths": paths,
                "excluded_targets": [],
                "sams": [],
                "buffer": 0.0,
                "wrapped_polygons": [],
                "routing_model": {"method": self.method, "sam_mode": "ignored"},
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
            detail = {
                "id": str(target.get("id", f"T{len(waypoints) + 1}")),
                "x": float(target["x"]),
                "y": float(target["y"]),
                "priority": int(target.get("priority", 5)),
                "type": target.get("type", "a"),
            }
            waypoints.append(detail)

        return waypoints

