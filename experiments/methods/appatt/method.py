"""APPATT-style static SETG-TG pairwise matrix builder."""

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


APPATT_SAFE_MARGIN_KM = 0.0
MAX_APPATT_ITERATIONS = 1000
UNAVAILABLE_COST = 99999.0
APPATT_NUMERIC_TOLERANCE_KM = 1e-8
POINT_KEY_PRECISION = 8

Point = Tuple[float, float]


@dataclass(frozen=True)
class _Obstacle:
    id: str
    center: Point
    radius: float
    order: int


@dataclass(frozen=True)
class _Candidate:
    side: str
    point: Point
    origin_count: int
    destination_count: int
    previous_obstacle_clear: bool
    length: float


class APPATTMatrixBuilder:
    """Build pairwise paths with the static APPATT SETG-TG heuristic."""

    method = "appatt"

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
        aggregate_rule_counts: Dict[str, int] = {
            "RULE_1": 0,
            "RULE_2": 0,
            "RULE_3": 0,
            "RULE_4": 0,
            "IMPLEMENTATION_TIEBREAK": 0,
        }

        for i in range(n):
            for j in range(i + 1, n):
                start = (float(waypoints[i]["x"]), float(waypoints[i]["y"]))
                end = (float(waypoints[j]["x"]), float(waypoints[j]["y"]))
                direct_distance = _distance(start, end)
                result = self._run_setg_tg(start, end, obstacles)

                for rule in result["rule_decisions"]:
                    aggregate_rule_counts[rule["rule"]] += 1

                if result["path"] is None:
                    matrix[i][j] = UNAVAILABLE_COST
                    matrix[j][i] = UNAVAILABLE_COST
                    pair_results.append(
                        {
                            "pair": [labels[i], labels[j]],
                            "direct_distance": direct_distance,
                            "appatt_distance": UNAVAILABLE_COST,
                            "path_point_count": 0,
                            "iteration_count": result["iteration_count"],
                            "classification": "UNAVAILABLE",
                            "ba_sequence": result["ba_sequence"],
                            "tangent_waypoint_count": 0,
                            "rule_decisions": result["rule_decisions"],
                            "selected_sides": result["selected_sides"],
                            "failure_reason": result["failure_reason"],
                        }
                    )
                    continue

                path = result["path"]
                distance = _path_length(path)
                path_lists = _points_to_lists(path)
                matrix[i][j] = distance
                matrix[j][i] = distance
                paths[f"{labels[i]}->{labels[j]}"] = path_lists
                paths[f"{labels[j]}->{labels[i]}"] = list(reversed(path_lists))
                classification = "DIRECT" if len(path) == 2 else "APPATT_DETOUR"
                pair_results.append(
                    {
                        "pair": [labels[i], labels[j]],
                        "direct_distance": direct_distance,
                        "appatt_distance": distance,
                        "path_point_count": len(path),
                        "iteration_count": result["iteration_count"],
                        "classification": classification,
                        "ba_sequence": result["ba_sequence"],
                        "tangent_waypoint_count": max(0, len(path) - 2),
                        "rule_decisions": result["rule_decisions"],
                        "selected_sides": result["selected_sides"],
                        "failure_reason": None,
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
                "buffer": APPATT_SAFE_MARGIN_KM,
                "wrapped_polygons": [],
                "routing_model": {
                    "method": self.method,
                    "sam_mode": "appatt_static_setg_tg_original_circles",
                    "unavailable_cost": UNAVAILABLE_COST,
                },
                "appatt": {
                    "safe_margin_km": APPATT_SAFE_MARGIN_KM,
                    "max_iterations": MAX_APPATT_ITERATIONS,
                    "numeric_tolerance_km": APPATT_NUMERIC_TOLERANCE_KM,
                    "obstacle_model": "circle_as_ellipse_a_equals_b",
                    "pair_results": pair_results,
                    "aggregate_rule_counts": aggregate_rule_counts,
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

    def _normalize_obstacles(self, env: Dict[str, Any]) -> List[_Obstacle]:
        obstacles: List[_Obstacle] = []
        for index, sam in enumerate(env.get("sams", []), start=1):
            pos = sam.get("pos") or sam.get("position")
            if pos is None and "x" in sam and "y" in sam:
                pos = [sam["x"], sam["y"]]
            if pos is None:
                continue

            radius = float(sam.get("range", sam.get("radius", 0.0)))
            obstacles.append(
                _Obstacle(
                    id=str(sam.get("id") or sam.get("name") or f"SAM{index}"),
                    center=(float(pos[0]), float(pos[1])),
                    radius=radius + APPATT_SAFE_MARGIN_KM,
                    order=index,
                )
            )
        return obstacles

    def _run_setg_tg(
        self,
        start: Point,
        end: Point,
        obstacles: List[_Obstacle],
    ) -> Dict[str, Any]:
        if _point_inside_any_obstacle(start, obstacles) or _point_inside_any_obstacle(
            end, obstacles
        ):
            return _failure_result("invalid endpoint")

        pa: List[Point] = [start]
        ca: List[Point] = [end]
        ba: List[_Obstacle] = []
        rule_decisions: List[Dict[str, Any]] = []
        selected_sides: List[str] = []
        seen_states = set()

        for iteration in range(1, MAX_APPATT_ITERATIONS + 1):
            if not ca:
                return {
                    "path": pa,
                    "iteration_count": iteration - 1,
                    "ba_sequence": [obstacle.id for obstacle in ba],
                    "rule_decisions": rule_decisions,
                    "selected_sides": selected_sides,
                    "failure_reason": None,
                }

            state_key = (
                _point_key(pa[-1]),
                tuple(_point_key(point) for point in ca),
                tuple(obstacle.id for obstacle in ba[-5:]),
            )
            if state_key in seen_states:
                return {
                    "path": None,
                    "iteration_count": iteration - 1,
                    "ba_sequence": [obstacle.id for obstacle in ba],
                    "rule_decisions": rule_decisions,
                    "selected_sides": selected_sides,
                    "failure_reason": "repeated APPATT state",
                }
            seen_states.add(state_key)

            origin = pa[-1]
            destination = ca[-1]
            first_collision = _first_collided_obstacle(origin, destination, obstacles)

            if first_collision is None:
                pa.append(destination)
                ca.pop()
                continue

            candidates = self._build_candidates(
                origin,
                destination,
                first_collision,
                obstacles,
                ba[-1] if ba else None,
            )
            if not candidates:
                return {
                    "path": None,
                    "iteration_count": iteration,
                    "ba_sequence": [obstacle.id for obstacle in ba],
                    "rule_decisions": rule_decisions,
                    "selected_sides": selected_sides,
                    "failure_reason": "no valid tangent candidate",
                }

            selected, rule = _select_candidate(candidates)
            rule_decisions.append(
                {
                    "rule": rule,
                    "side": selected.side,
                    "obstacle": first_collision.id,
                }
            )
            selected_sides.append(selected.side)
            ba.append(first_collision)

            if _points_close(origin, selected.point) or _points_close(
                destination, selected.point
            ):
                return {
                    "path": None,
                    "iteration_count": iteration,
                    "ba_sequence": [obstacle.id for obstacle in ba],
                    "rule_decisions": rule_decisions,
                    "selected_sides": selected_sides,
                    "failure_reason": "other geometric failure",
                }

            if _first_collided_obstacle(origin, selected.point, obstacles) is None:
                pa.append(selected.point)
            else:
                ca.append(selected.point)

        return {
            "path": None,
            "iteration_count": MAX_APPATT_ITERATIONS,
            "ba_sequence": [obstacle.id for obstacle in ba],
            "rule_decisions": rule_decisions,
            "selected_sides": selected_sides,
            "failure_reason": "iteration limit",
        }

    def _build_candidates(
        self,
        origin: Point,
        destination: Point,
        obstacle: _Obstacle,
        obstacles: List[_Obstacle],
        previous_obstacle: Optional[_Obstacle],
    ) -> List[_Candidate]:
        origin_tangents = _classified_tangents(origin, destination, origin, obstacle)
        destination_tangents = _classified_tangents(
            origin, destination, destination, obstacle
        )
        candidates: List[_Candidate] = []

        for side in ("LEFT", "RIGHT"):
            origin_contact = origin_tangents.get(side)
            destination_contact = destination_tangents.get(side)
            if origin_contact is None or destination_contact is None:
                continue

            point = _line_intersection(
                origin,
                origin_contact,
                destination,
                destination_contact,
            )
            if point is None or not _finite_point(point):
                continue
            if _points_close(origin, point) or _points_close(destination, point):
                continue

            origin_count = _collision_count(origin, point, obstacles)
            destination_count = _collision_count(point, destination, obstacles)
            previous_clear = True
            if previous_obstacle is not None:
                previous_clear = not _segment_penetrates_obstacle(
                    origin, point, previous_obstacle
                )

            candidates.append(
                _Candidate(
                    side=side,
                    point=point,
                    origin_count=origin_count,
                    destination_count=destination_count,
                    previous_obstacle_clear=previous_clear,
                    length=_distance(origin, point) + _distance(point, destination),
                )
            )

        return candidates


def _failure_result(reason: str) -> Dict[str, Any]:
    return {
        "path": None,
        "iteration_count": 0,
        "ba_sequence": [],
        "rule_decisions": [],
        "selected_sides": [],
        "failure_reason": reason,
    }


def _classified_tangents(
    origin: Point,
    destination: Point,
    external_point: Point,
    obstacle: _Obstacle,
) -> Dict[str, Point]:
    contacts = _tangent_contact_points(external_point, obstacle)
    if len(contacts) != 2:
        return {}

    axis = (destination[0] - origin[0], destination[1] - origin[1])
    signed = [
        (_cross(axis, (contact[0] - origin[0], contact[1] - origin[1])), contact)
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
    radius = obstacle.radius
    radius_sq = radius * radius
    if dist_sq <= radius_sq + APPATT_NUMERIC_TOLERANCE_KM:
        return []

    base_scale = radius_sq / dist_sq
    height_scale = radius * math.sqrt(max(0.0, dist_sq - radius_sq)) / dist_sq
    base = (cx + base_scale * vx, cy + base_scale * vy)
    perp = (-vy, vx)
    return [
        (base[0] + height_scale * perp[0], base[1] + height_scale * perp[1]),
        (base[0] - height_scale * perp[0], base[1] - height_scale * perp[1]),
    ]


def _select_candidate(candidates: List[_Candidate]) -> Tuple[_Candidate, str]:
    ordered = sorted(candidates, key=lambda candidate: 0 if candidate.side == "LEFT" else 1)

    clear_values = {candidate.previous_obstacle_clear for candidate in ordered}
    if len(clear_values) > 1:
        selected = next(candidate for candidate in ordered if candidate.previous_obstacle_clear)
        return selected, "RULE_1"

    min_origin = min(candidate.origin_count for candidate in ordered)
    origin_best = [candidate for candidate in ordered if candidate.origin_count == min_origin]
    if len(origin_best) == 1:
        return origin_best[0], "RULE_2"

    min_destination = min(candidate.destination_count for candidate in origin_best)
    destination_best = [
        candidate
        for candidate in origin_best
        if candidate.destination_count == min_destination
    ]
    if len(destination_best) == 1:
        return destination_best[0], "RULE_3"

    min_length = min(candidate.length for candidate in destination_best)
    length_best = [
        candidate
        for candidate in destination_best
        if abs(candidate.length - min_length) <= APPATT_NUMERIC_TOLERANCE_KM
    ]
    if len(length_best) != len(destination_best):
        selected = min(destination_best, key=lambda candidate: candidate.length)
        return selected, "RULE_4"

    selected = min(length_best, key=lambda candidate: 0 if candidate.side == "LEFT" else 1)
    return selected, "IMPLEMENTATION_TIEBREAK"


def _first_collided_obstacle(
    start: Point,
    end: Point,
    obstacles: List[_Obstacle],
) -> Optional[_Obstacle]:
    contacts: List[Tuple[float, int, str, _Obstacle]] = []
    for obstacle in obstacles:
        t = _first_interior_contact_parameter(start, end, obstacle)
        if t is not None:
            contacts.append((t, obstacle.order, obstacle.id, obstacle))

    if not contacts:
        return None

    contacts.sort(key=lambda item: (item[0], item[1], item[2]))
    return contacts[0][3]


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
    if length_sq <= APPATT_NUMERIC_TOLERANCE_KM * APPATT_NUMERIC_TOLERANCE_KM:
        return None

    fx = sx - cx
    fy = sy - cy
    radius = obstacle.radius
    a = length_sq
    b = 2.0 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - radius * radius
    discriminant = b * b - 4.0 * a * c

    if c < -APPATT_NUMERIC_TOLERANCE_KM:
        return 0.0
    if discriminant <= APPATT_NUMERIC_TOLERANCE_KM:
        return None

    root = math.sqrt(max(0.0, discriminant))
    t1 = (-b - root) / (2.0 * a)
    t2 = (-b + root) / (2.0 * a)
    interval_start = max(0.0, min(t1, t2))
    interval_end = min(1.0, max(t1, t2))
    if interval_end - interval_start <= APPATT_NUMERIC_TOLERANCE_KM:
        return None

    probe_t = min(1.0, max(0.0, (interval_start + interval_end) / 2.0))
    probe = (sx + dx * probe_t, sy + dy * probe_t)
    if not _point_inside_obstacle(probe, obstacle):
        return None

    return interval_start


def _collision_count(
    start: Point,
    end: Point,
    obstacles: List[_Obstacle],
) -> int:
    return sum(1 for obstacle in obstacles if _segment_penetrates_obstacle(start, end, obstacle))


def _segment_penetrates_obstacle(
    start: Point,
    end: Point,
    obstacle: _Obstacle,
) -> bool:
    return _first_interior_contact_parameter(start, end, obstacle) is not None


def _point_inside_any_obstacle(point: Point, obstacles: List[_Obstacle]) -> bool:
    return any(_point_inside_obstacle(point, obstacle) for obstacle in obstacles)


def _point_inside_obstacle(point: Point, obstacle: _Obstacle) -> bool:
    return (
        _distance(point, obstacle.center)
        < obstacle.radius - APPATT_NUMERIC_TOLERANCE_KM
    )


def _line_intersection(
    a: Point,
    b: Point,
    c: Point,
    d: Point,
) -> Optional[Point]:
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    denominator = _cross(r, s)
    if abs(denominator) <= APPATT_NUMERIC_TOLERANCE_KM:
        return None

    c_minus_a = (c[0] - a[0], c[1] - a[1])
    t = _cross(c_minus_a, s) / denominator
    return (a[0] + t * r[0], a[1] + t * r[1])


def _finite_point(point: Point) -> bool:
    return math.isfinite(point[0]) and math.isfinite(point[1])


def _distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _path_length(path: List[Point]) -> float:
    return sum(_distance(path[i], path[i + 1]) for i in range(len(path) - 1))


def _points_close(a: Point, b: Point) -> bool:
    return _distance(a, b) <= APPATT_NUMERIC_TOLERANCE_KM


def _point_key(point: Point) -> Tuple[float, float]:
    return (round(point[0], POINT_KEY_PRECISION), round(point[1], POINT_KEY_PRECISION))


def _points_to_lists(points: List[Point]) -> List[List[float]]:
    return [[float(point[0]), float(point[1])] for point in points]


def _cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]
