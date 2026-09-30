"""Static TIG matrix builder with the shared raw S-TIG engine."""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from benchmark.matrix_builders import (
    DEFAULT_PLANNER_ROOT,
    MatrixBuild,
    configure_planner_imports,
)


TIG_OBSTACLE_SAFE_MARGIN_KM = 0.0
TIG_VIRTUAL_OFFSET_RATIO = 0.05
TIG_OBSTACLE_PENALTY_KM = 1.0
TIG_BEZIER_TRIM_FRACTION = 0.25
TIG_BEZIER_SAMPLES_PER_TURN = 21
MAX_TIG_SEARCH_EXPANSIONS = 10000
MAX_TIG_LOCAL_EXPANSIONS = 10000
UNAVAILABLE_COST = 99999.0
TIG_NUMERIC_TOLERANCE_KM = 1e-8
POINT_KEY_PRECISION = 8

Point = Tuple[float, float]


@dataclass(frozen=True)
class _Obstacle:
    id: str
    center: Point
    radius: float
    virtual_radius: float
    order: int


@dataclass(frozen=True)
class _TIGCandidate:
    side: str
    point: Point
    tangent_contact: Point
    obstacle_penalty_count: int
    heuristic: float
    distance_from_current: float
    distance_to_destination: float
    segment_blocking_sams: Tuple[str, ...]


@dataclass(frozen=True)
class _RawTIGResult:
    path: Optional[List[Point]]
    status: str
    distance: float
    diagnostics: Dict[str, Any]
    failure_reason: Optional[str]


@dataclass(frozen=True)
class _BezierResult:
    path: Optional[List[Point]]
    status: str
    distance: float
    collision_validation: str
    blocking_sam_ids: List[str]
    interior_turn_count: int
    curve_count: int
    sampled_point_count: int
    minimum_clearance_km: Optional[float]


class _RawSTIGPlanner:
    """Shared deterministic raw S-TIG planner used by both TIG variants."""

    def plan(
        self,
        start: Point,
        end: Point,
        obstacles: List[_Obstacle],
    ) -> _RawTIGResult:
        diagnostics: Dict[str, Any] = {
            "global_expansions": 0,
            "local_expansions": 0,
            "first_collision_sequence": [],
            "selected_left_right_sequence": [],
            "candidate_decisions": [],
            "treated_set_size": 0,
            "closed_set_size": 0,
            "max_current_set_size": 1,
            "failure_reason": None,
        }
        closed_set = {_point_key(start)}
        treated_set = set()
        path: List[Point] = [start]

        if _point_inside_any_obstacle(start, obstacles):
            return self._failure(
                "source inside original NFZ", diagnostics, treated_set, closed_set
            )
        if _point_inside_any_obstacle(end, obstacles):
            return self._failure(
                "destination inside original NFZ", diagnostics, treated_set, closed_set
            )

        ok = self._solve_segment(
            path=path,
            destination=end,
            obstacles=obstacles,
            diagnostics=diagnostics,
            treated_set=treated_set,
            closed_set=closed_set,
            depth=1,
        )
        diagnostics["treated_set_size"] = len(treated_set)
        diagnostics["closed_set_size"] = len(closed_set)

        if not ok:
            return _RawTIGResult(
                path=None,
                status="UNAVAILABLE",
                distance=UNAVAILABLE_COST,
                diagnostics=diagnostics,
                failure_reason=diagnostics["failure_reason"],
            )

        path = _remove_consecutive_duplicates(path)
        validation = _validate_path_against_obstacles(path, obstacles)
        if validation["blocking_sam_ids"]:
            diagnostics["failure_reason"] = "raw path penetrates original NFZ interior"
            diagnostics["raw_validation_blocking_sams"] = validation["blocking_sam_ids"]
            return _RawTIGResult(
                path=None,
                status="UNAVAILABLE",
                distance=UNAVAILABLE_COST,
                diagnostics=diagnostics,
                failure_reason=diagnostics["failure_reason"],
            )

        status = "DIRECT" if len(path) <= 2 else "TIG_DETOUR"
        return _RawTIGResult(
            path=path,
            status=status,
            distance=_path_length(path),
            diagnostics=diagnostics,
            failure_reason=None,
        )

    def _solve_segment(
        self,
        *,
        path: List[Point],
        destination: Point,
        obstacles: List[_Obstacle],
        diagnostics: Dict[str, Any],
        treated_set: set,
        closed_set: set,
        depth: int,
    ) -> bool:
        diagnostics["max_current_set_size"] = max(
            int(diagnostics["max_current_set_size"]), depth
        )
        diagnostics["global_expansions"] += 1
        if diagnostics["global_expansions"] > MAX_TIG_SEARCH_EXPANSIONS:
            diagnostics["failure_reason"] = "global expansion limit"
            return False
        if diagnostics["local_expansions"] > MAX_TIG_LOCAL_EXPANSIONS:
            diagnostics["failure_reason"] = "local expansion limit"
            return False

        current = path[-1]
        first_collision = _first_collided_obstacle(current, destination, obstacles)
        if first_collision is None:
            self._append_path_point(path, destination, closed_set)
            return True

        diagnostics["first_collision_sequence"].append(first_collision.id)
        state_key = (_point_key(current), _point_key(destination), first_collision.id)
        if state_key in treated_set:
            diagnostics["failure_reason"] = "repeated S-TIG state"
            return False
        treated_set.add(state_key)

        candidates = _build_tig_candidates(
            current=current,
            destination=destination,
            obstacle=first_collision,
            obstacles=obstacles,
        )
        diagnostics["local_expansions"] += len(candidates)
        if diagnostics["local_expansions"] > MAX_TIG_LOCAL_EXPANSIONS:
            diagnostics["failure_reason"] = "local expansion limit"
            return False
        if not candidates:
            diagnostics["failure_reason"] = "no valid TIG tangent candidate"
            return False

        selected = _select_candidate(candidates)
        diagnostics["selected_left_right_sequence"].append(selected.side)
        diagnostics["candidate_decisions"].append(
            {
                "from": _point_to_list(current),
                "to": _point_to_list(destination),
                "obstacle": first_collision.id,
                "selected_side": selected.side,
                "selected_point": _point_to_list(selected.point),
                "selected_tangent_contact": _point_to_list(selected.tangent_contact),
                "selected_heuristic": selected.heuristic,
                "selected_obstacle_penalty_count": selected.obstacle_penalty_count,
                "selected_segment_blocking_sams": list(selected.segment_blocking_sams),
                "candidates": [
                    {
                        "side": candidate.side,
                        "point": _point_to_list(candidate.point),
                        "tangent_contact": _point_to_list(candidate.tangent_contact),
                        "heuristic": candidate.heuristic,
                        "obstacle_penalty_count": candidate.obstacle_penalty_count,
                        "distance_from_current": candidate.distance_from_current,
                        "distance_to_destination": candidate.distance_to_destination,
                        "segment_blocking_sams": list(
                            candidate.segment_blocking_sams
                        ),
                    }
                    for candidate in candidates
                ],
            }
        )

        if _points_close(current, selected.point) or _points_close(
            destination, selected.point
        ):
            diagnostics["failure_reason"] = "degenerate TIG waypoint"
            return False
        if _point_inside_any_obstacle(selected.point, obstacles):
            diagnostics["failure_reason"] = "TIG waypoint inside original NFZ"
            return False

        if _first_collided_obstacle(current, selected.point, obstacles) is None:
            if _point_key(selected.point) in closed_set:
                diagnostics["failure_reason"] = "repeated TIG waypoint"
                return False
            self._append_path_point(path, selected.point, closed_set)
        else:
            if not self._solve_segment(
                path=path,
                destination=selected.point,
                obstacles=obstacles,
                diagnostics=diagnostics,
                treated_set=treated_set,
                closed_set=closed_set,
                depth=depth + 1,
            ):
                return False

        return self._solve_segment(
            path=path,
            destination=destination,
            obstacles=obstacles,
            diagnostics=diagnostics,
            treated_set=treated_set,
            closed_set=closed_set,
            depth=depth,
        )

    def _append_path_point(
        self,
        path: List[Point],
        point: Point,
        closed_set: set,
    ) -> None:
        if not _points_close(path[-1], point):
            path.append(point)
        closed_set.add(_point_key(point))

    def _failure(
        self,
        reason: str,
        diagnostics: Dict[str, Any],
        treated_set: set,
        closed_set: set,
    ) -> _RawTIGResult:
        diagnostics["failure_reason"] = reason
        diagnostics["treated_set_size"] = len(treated_set)
        diagnostics["closed_set_size"] = len(closed_set)
        return _RawTIGResult(
            path=None,
            status="UNAVAILABLE",
            distance=UNAVAILABLE_COST,
            diagnostics=diagnostics,
            failure_reason=reason,
        )


class TIGMatrixBuilderBase:
    """Common serial unordered-pair matrix builder for TIG variants."""

    method = "tig"
    variant = "raw"

    def __init__(self, *, planner_root: Path = DEFAULT_PLANNER_ROOT) -> None:
        self.planner_root = planner_root
        self._project_env_to_local_km = None
        self._raw_planner = _RawSTIGPlanner()

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
        obstacles = self._normalize_obstacles(projected_env)
        sams = [
            {
                "id": obstacle.id,
                "pos": [obstacle.center[0], obstacle.center[1]],
                "range": obstacle.radius,
            }
            for obstacle in obstacles
        ]

        labels = [wp["id"] for wp in waypoints]
        n = len(waypoints)
        matrix: List[List[float]] = [[0.0] * n for _ in range(n)]
        paths: Dict[str, List[List[float]]] = {}
        pair_results: List[Dict[str, Any]] = []
        aggregate = {
            "raw_tig_available_pairs": 0,
            "raw_tig_unavailable_pairs": 0,
            "bezier_valid_pairs": 0,
            "bezier_invalid_collision_pairs": 0,
            "total_curves_generated": 0,
            "total_sampled_smoothed_points": 0,
        }

        for i in range(n):
            for j in range(i + 1, n):
                start = (float(waypoints[i]["x"]), float(waypoints[i]["y"]))
                end = (float(waypoints[j]["x"]), float(waypoints[j]["y"]))
                pair = [labels[i], labels[j]]
                pair_id = f"{labels[i]}-{labels[j]}"
                direct_distance = _distance(start, end)
                raw = self._raw_planner.plan(start, end, obstacles)

                if raw.path is None:
                    aggregate["raw_tig_unavailable_pairs"] += 1
                    matrix[i][j] = UNAVAILABLE_COST
                    matrix[j][i] = UNAVAILABLE_COST
                    pair_results.append(
                        self._unavailable_pair_result(
                            pair=pair,
                            pair_id=pair_id,
                            direct_distance=direct_distance,
                            raw=raw,
                            collision_validation="RAW_UNAVAILABLE",
                            blocking_sam_ids=[],
                        )
                    )
                    continue

                aggregate["raw_tig_available_pairs"] += 1
                raw_validation = _validate_path_against_obstacles(raw.path, obstacles)
                if raw_validation["blocking_sam_ids"]:
                    aggregate["raw_tig_unavailable_pairs"] += 1
                    aggregate["raw_tig_available_pairs"] -= 1
                    matrix[i][j] = UNAVAILABLE_COST
                    matrix[j][i] = UNAVAILABLE_COST
                    pair_results.append(
                        self._unavailable_pair_result(
                            pair=pair,
                            pair_id=pair_id,
                            direct_distance=direct_distance,
                            raw=raw,
                            collision_validation="RAW_COLLISION",
                            blocking_sam_ids=raw_validation["blocking_sam_ids"],
                        )
                    )
                    continue

                final_path = raw.path
                final_distance = raw.distance
                final_status = raw.status
                collision_validation = "VALID"
                blocking_sam_ids: List[str] = []
                bezier: Optional[_BezierResult] = None

                if self.variant == "bezier":
                    bezier = _smooth_raw_path_with_quadratic_bezier(
                        raw.path, obstacles
                    )
                    aggregate["total_curves_generated"] += bezier.curve_count
                    aggregate["total_sampled_smoothed_points"] += (
                        bezier.sampled_point_count
                    )
                    collision_validation = bezier.collision_validation
                    blocking_sam_ids = bezier.blocking_sam_ids

                    if bezier.path is None:
                        if collision_validation == "BEZIER_COLLISION":
                            aggregate["bezier_invalid_collision_pairs"] += 1
                        matrix[i][j] = UNAVAILABLE_COST
                        matrix[j][i] = UNAVAILABLE_COST
                        pair_results.append(
                            self._bezier_unavailable_pair_result(
                                pair=pair,
                                pair_id=pair_id,
                                direct_distance=direct_distance,
                                raw=raw,
                                raw_validation=raw_validation,
                                bezier=bezier,
                            )
                        )
                        continue

                    aggregate["bezier_valid_pairs"] += 1
                    final_path = bezier.path
                    final_distance = bezier.distance
                    final_status = "DIRECT" if len(raw.path) <= 2 else "BEZIER_SMOOTHED"

                path_lists = _points_to_lists(final_path)
                matrix[i][j] = final_distance
                matrix[j][i] = final_distance
                paths[f"{labels[i]}->{labels[j]}"] = path_lists
                paths[f"{labels[j]}->{labels[i]}"] = list(reversed(path_lists))
                pair_results.append(
                    self._available_pair_result(
                        pair=pair,
                        pair_id=pair_id,
                        direct_distance=direct_distance,
                        raw=raw,
                        raw_validation=raw_validation,
                        final_status=final_status,
                        final_distance=final_distance,
                        final_path=final_path,
                        collision_validation=collision_validation,
                        blocking_sam_ids=blocking_sam_ids,
                        bezier=bezier,
                    )
                )

        if self.variant == "raw":
            aggregate["bezier_valid_pairs"] = 0
            aggregate["bezier_invalid_collision_pairs"] = 0

        return MatrixBuild(
            method=self.method,
            data={
                "matrix": matrix,
                "labels": labels,
                "waypoints": waypoints,
                "paths": paths,
                "excluded_targets": [],
                "sams": sams,
                "buffer": TIG_OBSTACLE_SAFE_MARGIN_KM,
                "wrapped_polygons": [],
                "routing_model": {
                    "method": self.method,
                    "sam_mode": "static_s_tig_original_circles",
                    "unavailable_cost": UNAVAILABLE_COST,
                },
                "tig": {
                    "method": self.method,
                    "variant": self.variant,
                    "source_algorithm": "static S-TIG",
                    "obstacle_model": "circle_as_ellipse_a_equals_b_theta_0",
                    "safe_margin_km": TIG_OBSTACLE_SAFE_MARGIN_KM,
                    "virtual_offset_ratio": TIG_VIRTUAL_OFFSET_RATIO,
                    "obstacle_penalty_km": TIG_OBSTACLE_PENALTY_KM,
                    "max_search_expansions": MAX_TIG_SEARCH_EXPANSIONS,
                    "max_local_expansions": MAX_TIG_LOCAL_EXPANSIONS,
                    "bezier_trim_fraction": TIG_BEZIER_TRIM_FRACTION
                    if self.variant == "bezier"
                    else None,
                    "bezier_samples_per_turn": TIG_BEZIER_SAMPLES_PER_TURN
                    if self.variant == "bezier"
                    else None,
                    "numeric_tolerance_km": TIG_NUMERIC_TOLERANCE_KM,
                    "unavailable_cost": UNAVAILABLE_COST,
                    "pair_results": pair_results,
                    "aggregate": aggregate,
                    "no_fallback": True,
                    "parallelization": "none",
                },
                "benchmark_diagnostics": {
                    "method": self.method,
                    "variant": self.variant,
                    "unordered_pair_count": n * (n - 1) // 2,
                    "directed_task_count": n * (n - 1),
                    "raw_engine_shared_with": ["tig_raw", "tig_bezier"],
                    "parallel_mechanism": "none",
                    "worker_count": 1,
                    "persistent_process_pool": False,
                    "fallback": False,
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

    def _normalize_obstacles(self, env: Dict[str, Any]) -> List[_Obstacle]:
        obstacles: List[_Obstacle] = []
        for index, sam in enumerate(env.get("sams", []), start=1):
            pos = sam.get("pos") or sam.get("position")
            if pos is None and "x" in sam and "y" in sam:
                pos = [sam["x"], sam["y"]]
            if pos is None:
                continue

            radius = float(sam.get("range", sam.get("radius", 0.0)))
            radius += TIG_OBSTACLE_SAFE_MARGIN_KM
            obstacles.append(
                _Obstacle(
                    id=str(sam.get("id") or sam.get("name") or f"SAM{index}"),
                    center=(float(pos[0]), float(pos[1])),
                    radius=radius,
                    virtual_radius=radius * (1.0 + TIG_VIRTUAL_OFFSET_RATIO),
                    order=index,
                )
            )
        return obstacles

    def _unavailable_pair_result(
        self,
        *,
        pair: List[str],
        pair_id: str,
        direct_distance: float,
        raw: _RawTIGResult,
        collision_validation: str,
        blocking_sam_ids: List[str],
    ) -> Dict[str, Any]:
        return {
            "pair": pair,
            "pair_id": pair_id,
            "direct_distance": direct_distance,
            "status": "UNAVAILABLE",
            "raw_tig_status": raw.status,
            "raw_tig_distance": UNAVAILABLE_COST,
            "raw_path_point_count": 0,
            "raw_path": [],
            "raw_tig_diagnostics": raw.diagnostics,
            "failure_reason": raw.failure_reason,
            "collision_validation": collision_validation,
            "blocking_sam_ids": blocking_sam_ids,
        }

    def _available_pair_result(
        self,
        *,
        pair: List[str],
        pair_id: str,
        direct_distance: float,
        raw: _RawTIGResult,
        raw_validation: Dict[str, Any],
        final_status: str,
        final_distance: float,
        final_path: List[Point],
        collision_validation: str,
        blocking_sam_ids: List[str],
        bezier: Optional[_BezierResult],
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "pair": pair,
            "pair_id": pair_id,
            "direct_distance": direct_distance,
            "status": final_status,
            "matrix_distance": final_distance,
            "path_point_count": len(final_path),
            "raw_tig_status": raw.status,
            "raw_tig_distance": raw.distance,
            "raw_path_point_count": len(raw.path or []),
            "raw_path": _points_to_lists(raw.path or []),
            "raw_tig_diagnostics": raw.diagnostics,
            "raw_collision_validation": "VALID"
            if not raw_validation["blocking_sam_ids"]
            else "RAW_COLLISION",
            "raw_validation_blocking_sam_ids": raw_validation["blocking_sam_ids"],
            "raw_minimum_clearance_km": raw_validation["minimum_clearance_km"],
            "collision_validation": collision_validation,
            "blocking_sam_ids": blocking_sam_ids,
            "failure_reason": None,
        }

        if self.variant == "bezier" and bezier is not None:
            result.update(
                {
                    "tig_bezier_status": final_status,
                    "smoothed_distance": final_distance,
                    "smoothed_sampled_point_count": len(final_path),
                    "raw_to_smoothed_distance_change": final_distance - raw.distance,
                    "interior_raw_turn_count": bezier.interior_turn_count,
                    "quadratic_curve_count": bezier.curve_count,
                    "bezier_trim_fraction": TIG_BEZIER_TRIM_FRACTION,
                    "bezier_samples_per_turn": TIG_BEZIER_SAMPLES_PER_TURN,
                    "bezier_minimum_clearance_km": bezier.minimum_clearance_km,
                    "bezier_path": _points_to_lists(final_path),
                }
            )

        return result

    def _bezier_unavailable_pair_result(
        self,
        *,
        pair: List[str],
        pair_id: str,
        direct_distance: float,
        raw: _RawTIGResult,
        raw_validation: Dict[str, Any],
        bezier: _BezierResult,
    ) -> Dict[str, Any]:
        return {
            "pair": pair,
            "pair_id": pair_id,
            "direct_distance": direct_distance,
            "status": "UNAVAILABLE",
            "matrix_distance": UNAVAILABLE_COST,
            "path_point_count": 0,
            "raw_tig_status": raw.status,
            "raw_tig_distance": raw.distance,
            "raw_path_point_count": len(raw.path or []),
            "raw_path": _points_to_lists(raw.path or []),
            "raw_tig_diagnostics": raw.diagnostics,
            "raw_collision_validation": "VALID"
            if not raw_validation["blocking_sam_ids"]
            else "RAW_COLLISION",
            "raw_validation_blocking_sam_ids": raw_validation["blocking_sam_ids"],
            "raw_minimum_clearance_km": raw_validation["minimum_clearance_km"],
            "tig_bezier_status": "UNAVAILABLE",
            "smoothed_distance": UNAVAILABLE_COST,
            "smoothed_sampled_point_count": bezier.sampled_point_count,
            "raw_to_smoothed_distance_change": None,
            "interior_raw_turn_count": bezier.interior_turn_count,
            "quadratic_curve_count": bezier.curve_count,
            "bezier_trim_fraction": TIG_BEZIER_TRIM_FRACTION,
            "bezier_samples_per_turn": TIG_BEZIER_SAMPLES_PER_TURN,
            "bezier_minimum_clearance_km": bezier.minimum_clearance_km,
            "collision_validation": bezier.collision_validation,
            "blocking_sam_ids": bezier.blocking_sam_ids,
            "failure_reason": "Bezier-smoothed path penetrates original NFZ interior"
            if bezier.collision_validation == "BEZIER_COLLISION"
            else "Bezier smoothing unavailable",
            "bezier_path": [],
        }


class TIGRawMatrixBuilder(TIGMatrixBuilderBase):
    """Return the raw S-TIG tangent/virtual-waypoint polyline."""

    method = "tig_raw"
    variant = "raw"


def _build_tig_candidates(
    *,
    current: Point,
    destination: Point,
    obstacle: _Obstacle,
    obstacles: List[_Obstacle],
) -> List[_TIGCandidate]:
    contacts = _classified_tangent_contacts(current, destination, obstacle)
    candidates: List[_TIGCandidate] = []

    for side in ("LEFT", "RIGHT"):
        contact = contacts.get(side)
        if contact is None:
            continue
        waypoint = _virtual_circle_waypoint(current, contact, obstacle)
        if waypoint is None:
            continue
        if not _finite_point(waypoint):
            continue
        if _points_close(current, waypoint) or _points_close(destination, waypoint):
            continue

        blockers = tuple(_segment_blocking_obstacle_ids(current, waypoint, obstacles))
        penalty_count = len(blockers)
        distance_from_current = _distance(current, waypoint)
        distance_to_destination = _distance(waypoint, destination)
        heuristic = (
            distance_from_current
            + TIG_OBSTACLE_PENALTY_KM * penalty_count
            + distance_to_destination
        )
        candidates.append(
            _TIGCandidate(
                side=side,
                point=waypoint,
                tangent_contact=contact,
                obstacle_penalty_count=penalty_count,
                heuristic=heuristic,
                distance_from_current=distance_from_current,
                distance_to_destination=distance_to_destination,
                segment_blocking_sams=blockers,
            )
        )

    return candidates


def _classified_tangent_contacts(
    current: Point,
    destination: Point,
    obstacle: _Obstacle,
) -> Dict[str, Point]:
    contacts = _tangent_contact_points(current, obstacle)
    if len(contacts) != 2:
        return {}

    axis = (destination[0] - current[0], destination[1] - current[1])
    signed = [
        (_cross(axis, (contact[0] - current[0], contact[1] - current[1])), contact)
        for contact in contacts
    ]
    signed.sort(key=lambda item: (item[0], item[1][0], item[1][1]))
    return {"RIGHT": signed[0][1], "LEFT": signed[-1][1]}


def _tangent_contact_points(point: Point, obstacle: _Obstacle) -> List[Point]:
    cx, cy = obstacle.center
    px, py = point
    vx = px - cx
    vy = py - cy
    dist_sq = vx * vx + vy * vy
    radius_sq = obstacle.radius * obstacle.radius
    if dist_sq <= radius_sq + TIG_NUMERIC_TOLERANCE_KM:
        return []

    base_scale = radius_sq / dist_sq
    height_scale = (
        obstacle.radius * math.sqrt(max(0.0, dist_sq - radius_sq)) / dist_sq
    )
    base = (cx + base_scale * vx, cy + base_scale * vy)
    perp = (-vy, vx)
    return [
        (base[0] + height_scale * perp[0], base[1] + height_scale * perp[1]),
        (base[0] - height_scale * perp[0], base[1] - height_scale * perp[1]),
    ]


def _virtual_circle_waypoint(
    current: Point,
    tangent_contact: Point,
    obstacle: _Obstacle,
) -> Optional[Point]:
    dx = tangent_contact[0] - current[0]
    dy = tangent_contact[1] - current[1]
    norm = math.hypot(dx, dy)
    if norm <= TIG_NUMERIC_TOLERANCE_KM:
        return None

    ux = dx / norm
    uy = dy / norm
    fx = current[0] - obstacle.center[0]
    fy = current[1] - obstacle.center[1]
    b = 2.0 * (fx * ux + fy * uy)
    c = fx * fx + fy * fy - obstacle.virtual_radius * obstacle.virtual_radius
    discriminant = b * b - 4.0 * c
    if discriminant < -TIG_NUMERIC_TOLERANCE_KM:
        return None

    root = math.sqrt(max(0.0, discriminant))
    candidates = [(-b - root) / 2.0, (-b + root) / 2.0]
    beyond_contact = [
        value
        for value in candidates
        if value > norm + TIG_NUMERIC_TOLERANCE_KM
    ]
    if not beyond_contact:
        positive = [value for value in candidates if value > TIG_NUMERIC_TOLERANCE_KM]
        if not positive:
            return None
        ray_distance = max(positive)
    else:
        ray_distance = max(beyond_contact)

    return (current[0] + ray_distance * ux, current[1] + ray_distance * uy)


def _select_candidate(candidates: List[_TIGCandidate]) -> _TIGCandidate:
    return min(
        candidates,
        key=lambda candidate: (
            candidate.heuristic,
            0 if candidate.side == "LEFT" else 1,
            candidate.point[0],
            candidate.point[1],
        ),
    )


def _smooth_raw_path_with_quadratic_bezier(
    raw_path: List[Point],
    obstacles: List[_Obstacle],
) -> _BezierResult:
    interior_turn_count = max(0, len(raw_path) - 2)
    if interior_turn_count == 0:
        validation = _validate_path_against_obstacles(raw_path, obstacles)
        blockers = validation["blocking_sam_ids"]
        if blockers:
            return _BezierResult(
                path=None,
                status="UNAVAILABLE",
                distance=UNAVAILABLE_COST,
                collision_validation="BEZIER_COLLISION",
                blocking_sam_ids=blockers,
                interior_turn_count=0,
                curve_count=0,
                sampled_point_count=len(raw_path),
                minimum_clearance_km=validation["minimum_clearance_km"],
            )
        return _BezierResult(
            path=list(raw_path),
            status="DIRECT",
            distance=_path_length(raw_path),
            collision_validation="VALID",
            blocking_sam_ids=[],
            interior_turn_count=0,
            curve_count=0,
            sampled_point_count=len(raw_path),
            minimum_clearance_km=validation["minimum_clearance_km"],
        )

    smoothed: List[Point] = [raw_path[0]]
    curve_count = 0
    for index in range(1, len(raw_path) - 1):
        previous = raw_path[index - 1]
        turn = raw_path[index]
        following = raw_path[index + 1]
        before = (
            turn[0] + TIG_BEZIER_TRIM_FRACTION * (previous[0] - turn[0]),
            turn[1] + TIG_BEZIER_TRIM_FRACTION * (previous[1] - turn[1]),
        )
        after = (
            turn[0] + TIG_BEZIER_TRIM_FRACTION * (following[0] - turn[0]),
            turn[1] + TIG_BEZIER_TRIM_FRACTION * (following[1] - turn[1]),
        )

        _append_unique(smoothed, before)
        samples = _quadratic_bezier_samples(
            before,
            turn,
            after,
            TIG_BEZIER_SAMPLES_PER_TURN,
        )
        for sample in samples:
            _append_unique(smoothed, sample)
        curve_count += 1

    _append_unique(smoothed, raw_path[-1])
    smoothed = _remove_consecutive_duplicates(smoothed)
    smoothed[0] = raw_path[0]
    smoothed[-1] = raw_path[-1]

    validation = _validate_path_against_obstacles(smoothed, obstacles)
    blockers = validation["blocking_sam_ids"]
    if blockers:
        return _BezierResult(
            path=None,
            status="UNAVAILABLE",
            distance=UNAVAILABLE_COST,
            collision_validation="BEZIER_COLLISION",
            blocking_sam_ids=blockers,
            interior_turn_count=interior_turn_count,
            curve_count=curve_count,
            sampled_point_count=len(smoothed),
            minimum_clearance_km=validation["minimum_clearance_km"],
        )

    return _BezierResult(
        path=smoothed,
        status="BEZIER_SMOOTHED",
        distance=_path_length(smoothed),
        collision_validation="VALID",
        blocking_sam_ids=[],
        interior_turn_count=interior_turn_count,
        curve_count=curve_count,
        sampled_point_count=len(smoothed),
        minimum_clearance_km=validation["minimum_clearance_km"],
    )


def _quadratic_bezier_samples(
    b0: Point,
    b1: Point,
    b2: Point,
    sample_count: int,
) -> List[Point]:
    if sample_count < 2:
        raise ValueError("quadratic Bezier sampling requires at least two samples")
    samples: List[Point] = []
    for index in range(sample_count):
        t = index / (sample_count - 1)
        mt = 1.0 - t
        samples.append(
            (
                mt * mt * b0[0] + 2.0 * mt * t * b1[0] + t * t * b2[0],
                mt * mt * b0[1] + 2.0 * mt * t * b1[1] + t * t * b2[1],
            )
        )
    return samples


def _validate_path_against_obstacles(
    path: List[Point],
    obstacles: List[_Obstacle],
) -> Dict[str, Any]:
    blockers: List[str] = []
    min_clearance: Optional[float] = None

    for obstacle in obstacles:
        for index in range(len(path) - 1):
            clearance = (
                _point_to_segment_distance(obstacle.center, path[index], path[index + 1])
                - obstacle.radius
            )
            if min_clearance is None or clearance < min_clearance:
                min_clearance = clearance
            if _segment_penetrates_obstacle(path[index], path[index + 1], obstacle):
                blockers.append(obstacle.id)
                break

    return {
        "blocking_sam_ids": sorted(set(blockers)),
        "minimum_clearance_km": min_clearance,
    }


def _first_collided_obstacle(
    start: Point,
    end: Point,
    obstacles: List[_Obstacle],
) -> Optional[_Obstacle]:
    contacts: List[Tuple[float, int, str, _Obstacle]] = []
    for obstacle in obstacles:
        t = _first_interior_contact_parameter(start, end, obstacle)
        if t is not None:
            contacts.append((round(t, 12), obstacle.order, obstacle.id, obstacle))

    if not contacts:
        return None

    contacts.sort(key=lambda item: (item[0], item[1], item[2]))
    return contacts[0][3]


def _segment_blocking_obstacle_ids(
    start: Point,
    end: Point,
    obstacles: List[_Obstacle],
) -> List[str]:
    blockers = [
        obstacle.id
        for obstacle in obstacles
        if _segment_penetrates_obstacle(start, end, obstacle)
    ]
    return sorted(blockers)


def _first_interior_contact_parameter(
    start: Point,
    end: Point,
    obstacle: _Obstacle,
) -> Optional[float]:
    sx, sy = start
    ex, ey = end
    cx, cy = obstacle.center
    dx = ex - sx
    dy = ey - sy
    length_sq = dx * dx + dy * dy
    if length_sq <= TIG_NUMERIC_TOLERANCE_KM * TIG_NUMERIC_TOLERANCE_KM:
        return None

    fx = sx - cx
    fy = sy - cy
    radius = obstacle.radius
    a = length_sq
    b = 2.0 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - radius * radius
    discriminant = b * b - 4.0 * a * c

    if c < -TIG_NUMERIC_TOLERANCE_KM:
        return 0.0
    if discriminant <= TIG_NUMERIC_TOLERANCE_KM:
        return None

    root = math.sqrt(max(0.0, discriminant))
    t1 = (-b - root) / (2.0 * a)
    t2 = (-b + root) / (2.0 * a)
    interval_start = max(0.0, min(t1, t2))
    interval_end = min(1.0, max(t1, t2))
    if interval_end - interval_start <= TIG_NUMERIC_TOLERANCE_KM:
        return None

    probe_t = min(1.0, max(0.0, (interval_start + interval_end) / 2.0))
    probe = (sx + dx * probe_t, sy + dy * probe_t)
    if not _point_inside_obstacle(probe, obstacle):
        return None

    return interval_start


def _segment_penetrates_obstacle(
    start: Point,
    end: Point,
    obstacle: _Obstacle,
) -> bool:
    return _first_interior_contact_parameter(start, end, obstacle) is not None


def _point_inside_any_obstacle(point: Point, obstacles: List[_Obstacle]) -> bool:
    return any(_point_inside_obstacle(point, obstacle) for obstacle in obstacles)


def _point_inside_obstacle(point: Point, obstacle: _Obstacle) -> bool:
    return _distance(point, obstacle.center) < obstacle.radius - TIG_NUMERIC_TOLERANCE_KM


def _point_to_segment_distance(point: Point, start: Point, end: Point) -> float:
    sx, sy = start
    ex, ey = end
    px, py = point
    dx = ex - sx
    dy = ey - sy
    length_sq = dx * dx + dy * dy
    if length_sq <= TIG_NUMERIC_TOLERANCE_KM * TIG_NUMERIC_TOLERANCE_KM:
        return _distance(point, start)

    t = ((px - sx) * dx + (py - sy) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    closest = (sx + t * dx, sy + t * dy)
    return _distance(point, closest)


def _distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _path_length(path: List[Point]) -> float:
    return sum(_distance(path[index], path[index + 1]) for index in range(len(path) - 1))


def _remove_consecutive_duplicates(points: List[Point]) -> List[Point]:
    cleaned: List[Point] = []
    for point in points:
        _append_unique(cleaned, point)
    return cleaned


def _append_unique(points: List[Point], point: Point) -> None:
    if not points or not _points_close(points[-1], point):
        points.append(point)


def _points_close(a: Point, b: Point) -> bool:
    return _distance(a, b) <= TIG_NUMERIC_TOLERANCE_KM


def _point_key(point: Point) -> Tuple[float, float]:
    return (round(point[0], POINT_KEY_PRECISION), round(point[1], POINT_KEY_PRECISION))


def _point_to_list(point: Point) -> List[float]:
    return [float(point[0]), float(point[1])]


def _points_to_lists(points: List[Point]) -> List[List[float]]:
    return [_point_to_list(point) for point in points]


def _finite_point(point: Point) -> bool:
    return math.isfinite(point[0]) and math.isfinite(point[1])


def _cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]
