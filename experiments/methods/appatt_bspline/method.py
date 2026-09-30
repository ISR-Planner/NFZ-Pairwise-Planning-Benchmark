"""APPATT wrapper with source-basis cubic B-spline smoothing."""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from benchmark.matrix_builders import DEFAULT_PLANNER_ROOT, MatrixBuild
from methods.appatt.method import (
    APPATTMatrixBuilder,
    APPATT_NUMERIC_TOLERANCE_KM,
    APPATT_SAFE_MARGIN_KM,
    MAX_APPATT_ITERATIONS,
    UNAVAILABLE_COST,
)


APPATT_BSPLINE_SAMPLES_PER_SPAN = 21

Point = Tuple[float, float]


class APPATTBSplineMatrixBuilder:
    """Run validated raw APPATT, then smooth detour paths with cubic B-splines."""

    method = "appatt_bspline"

    def __init__(self, *, planner_root: Path = DEFAULT_PLANNER_ROOT) -> None:
        self._raw_builder = APPATTMatrixBuilder(planner_root=planner_root)

    def prepare(self) -> None:
        self._raw_builder.prepare()

    def build(self, env: Dict[str, Any]) -> MatrixBuild:
        raw_build = self._raw_builder.build(env)
        raw_data = raw_build.data
        labels = [str(label) for label in raw_data["labels"]]
        raw_matrix = copy.deepcopy(raw_data["matrix"])
        raw_paths = copy.deepcopy(raw_data.get("paths", {}))
        raw_pair_results = copy.deepcopy(raw_data.get("appatt", {}).get("pair_results", []))
        pair_results_by_id = {
            _pair_id(pair_result["pair"]): pair_result
            for pair_result in raw_pair_results
        }

        n = len(labels)
        matrix: List[List[float]] = [[0.0] * n for _ in range(n)]
        paths: Dict[str, List[List[float]]] = {}
        bspline_pair_results: List[Dict[str, Any]] = []
        aggregate = {
            "raw_available_pairs": 0,
            "raw_unavailable_pairs": 0,
            "raw_detour_pairs": 0,
            "direct_pairs": 0,
            "bspline_valid_detours": 0,
            "bspline_collision_failures": 0,
            "total_cubic_spans": 0,
            "total_sampled_smoothed_points": 0,
        }

        for i in range(n):
            for j in range(i + 1, n):
                start_label = labels[i]
                end_label = labels[j]
                pair = [start_label, end_label]
                pair_id = _pair_id(pair)
                raw_pair = pair_results_by_id[pair_id]
                raw_cost = float(raw_matrix[i][j])
                raw_path_lists = raw_paths.get(f"{start_label}->{end_label}")

                if raw_path_lists is None or raw_cost >= UNAVAILABLE_COST:
                    aggregate["raw_unavailable_pairs"] += 1
                    matrix[i][j] = UNAVAILABLE_COST
                    matrix[j][i] = UNAVAILABLE_COST
                    bspline_pair_results.append(
                        _raw_unavailable_result(pair, pair_id, raw_pair)
                    )
                    continue

                aggregate["raw_available_pairs"] += 1
                raw_path = [_list_to_point(point) for point in raw_path_lists]
                raw_control_count = len(raw_path)
                direct_distance = float(raw_pair.get("direct_distance", raw_cost))

                if raw_control_count == 2:
                    aggregate["direct_pairs"] += 1
                    matrix[i][j] = raw_cost
                    matrix[j][i] = raw_cost
                    paths[f"{start_label}->{end_label}"] = copy.deepcopy(raw_path_lists)
                    paths[f"{end_label}->{start_label}"] = list(reversed(raw_path_lists))
                    bspline_pair_results.append(
                        {
                            "pair": pair,
                            "pair_id": pair_id,
                            "direct_distance": direct_distance,
                            "raw_appatt_status": raw_pair.get("classification", "DIRECT"),
                            "raw_appatt_distance": raw_cost,
                            "raw_control_point_count": raw_control_count,
                            "raw_path": copy.deepcopy(raw_path_lists),
                            "appatt_bspline_status": "DIRECT",
                            "bspline_distance": raw_cost,
                            "sampled_spline_point_count": raw_control_count,
                            "raw_to_spline_distance_difference": 0.0,
                            "collision_validation": "VALID",
                            "blocking_sam_ids": [],
                            "extended_control_point_count": None,
                            "cubic_span_count": 0,
                            "samples_per_span": None,
                            "minimum_clearance_km": _minimum_clearance(
                                raw_path, raw_data.get("sams", [])
                            ),
                            "failure_reason": None,
                        }
                    )
                    continue

                aggregate["raw_detour_pairs"] += 1
                smoothed = _smooth_appatt_detour(raw_path, raw_data.get("sams", []))
                aggregate["total_cubic_spans"] += smoothed["cubic_span_count"]
                aggregate["total_sampled_smoothed_points"] += smoothed[
                    "sampled_spline_point_count"
                ]

                if smoothed["collision_validation"] == "BSPLINE_COLLISION":
                    aggregate["bspline_collision_failures"] += 1
                    matrix[i][j] = UNAVAILABLE_COST
                    matrix[j][i] = UNAVAILABLE_COST
                    bspline_pair_results.append(
                        {
                            "pair": pair,
                            "pair_id": pair_id,
                            "direct_distance": direct_distance,
                            "raw_appatt_status": raw_pair.get(
                                "classification", "APPATT_DETOUR"
                            ),
                            "raw_appatt_distance": raw_cost,
                            "raw_control_point_count": raw_control_count,
                            "raw_path": copy.deepcopy(raw_path_lists),
                            "appatt_bspline_status": "BSPLINE_COLLISION",
                            "bspline_distance": UNAVAILABLE_COST,
                            "sampled_spline_point_count": smoothed[
                                "sampled_spline_point_count"
                            ],
                            "raw_to_spline_distance_difference": None,
                            "collision_validation": "BSPLINE_COLLISION",
                            "blocking_sam_ids": smoothed["blocking_sam_ids"],
                            "extended_control_point_count": smoothed[
                                "extended_control_point_count"
                            ],
                            "cubic_span_count": smoothed["cubic_span_count"],
                            "samples_per_span": APPATT_BSPLINE_SAMPLES_PER_SPAN,
                            "minimum_clearance_km": smoothed["minimum_clearance_km"],
                            "failure_reason": "B-spline path penetrates original NFZ interior",
                        }
                    )
                    continue

                aggregate["bspline_valid_detours"] += 1
                bspline_path_lists = _points_to_lists(smoothed["path"])
                bspline_distance = float(smoothed["distance"])
                matrix[i][j] = bspline_distance
                matrix[j][i] = bspline_distance
                paths[f"{start_label}->{end_label}"] = bspline_path_lists
                paths[f"{end_label}->{start_label}"] = list(reversed(bspline_path_lists))
                bspline_pair_results.append(
                    {
                        "pair": pair,
                        "pair_id": pair_id,
                        "direct_distance": direct_distance,
                        "raw_appatt_status": raw_pair.get(
                            "classification", "APPATT_DETOUR"
                        ),
                        "raw_appatt_distance": raw_cost,
                        "raw_control_point_count": raw_control_count,
                        "raw_path": copy.deepcopy(raw_path_lists),
                        "appatt_bspline_status": "BSPLINE_VALID",
                        "bspline_distance": bspline_distance,
                        "sampled_spline_point_count": len(bspline_path_lists),
                        "raw_to_spline_distance_difference": bspline_distance - raw_cost,
                        "collision_validation": "VALID",
                        "blocking_sam_ids": [],
                        "extended_control_point_count": smoothed[
                            "extended_control_point_count"
                        ],
                        "cubic_span_count": smoothed["cubic_span_count"],
                        "samples_per_span": APPATT_BSPLINE_SAMPLES_PER_SPAN,
                        "minimum_clearance_km": smoothed["minimum_clearance_km"],
                        "failure_reason": None,
                    }
                )

        data = copy.deepcopy(raw_data)
        data["matrix"] = matrix
        data["paths"] = paths
        data["routing_model"] = {
            "method": self.method,
            "sam_mode": "appatt_static_setg_tg_original_circles_cubic_bspline",
            "unavailable_cost": UNAVAILABLE_COST,
        }
        data["appatt_bspline"] = {
            "source_raw_method": raw_build.method,
            "canonical_raw_builder": "methods.appatt.method.APPATTMatrixBuilder",
            "safe_margin_km": APPATT_SAFE_MARGIN_KM,
            "max_appatt_iterations": MAX_APPATT_ITERATIONS,
            "basis": "uniform cubic B-spline",
            "endpoint_handling": "replicate endpoints to three total occurrences",
            "samples_per_span": APPATT_BSPLINE_SAMPLES_PER_SPAN,
            "numeric_tolerance_km": APPATT_NUMERIC_TOLERANCE_KM,
            "unavailable_cost": UNAVAILABLE_COST,
            "pair_results": bspline_pair_results,
            "aggregate": aggregate,
            "raw_matrix": raw_matrix,
            "raw_paths": raw_paths,
            "raw_pair_results": raw_pair_results,
            "no_fallback": True,
            "parallelization": "none",
        }
        data["benchmark_diagnostics"] = {
            "method": self.method,
            "source_raw_method": raw_build.method,
            "canonical_raw_builder": "methods.appatt.method.APPATTMatrixBuilder",
            "unordered_pair_count": n * (n - 1) // 2,
            "directed_task_count": n * (n - 1),
            "parallel_mechanism": "none",
            "worker_count": 1,
            "persistent_process_pool": False,
            "fallback": False,
            "samples_per_span": APPATT_BSPLINE_SAMPLES_PER_SPAN,
        }
        return MatrixBuild(method=self.method, data=data)


def _smooth_appatt_detour(
    raw_path: List[Point],
    sams: List[Dict[str, Any]],
) -> Dict[str, Any]:
    extended = [raw_path[0], raw_path[0], *raw_path, raw_path[-1], raw_path[-1]]
    smoothed: List[Point] = []
    cubic_span_count = max(0, len(extended) - 3)

    for start in range(cubic_span_count):
        p0, p1, p2, p3 = extended[start : start + 4]
        for sample_index in range(APPATT_BSPLINE_SAMPLES_PER_SPAN):
            t = sample_index / (APPATT_BSPLINE_SAMPLES_PER_SPAN - 1)
            _append_unique(smoothed, _cubic_bspline_point(t, p0, p1, p2, p3))

    if not smoothed:
        smoothed = list(raw_path)
    smoothed[0] = raw_path[0]
    smoothed[-1] = raw_path[-1]

    validation = _validate_path(smoothed, sams)
    if validation["blocking_sam_ids"]:
        return {
            "path": None,
            "distance": UNAVAILABLE_COST,
            "collision_validation": "BSPLINE_COLLISION",
            "blocking_sam_ids": validation["blocking_sam_ids"],
            "minimum_clearance_km": validation["minimum_clearance_km"],
            "extended_control_point_count": len(extended),
            "cubic_span_count": cubic_span_count,
            "sampled_spline_point_count": len(smoothed),
        }

    return {
        "path": smoothed,
        "distance": _path_length(smoothed),
        "collision_validation": "VALID",
        "blocking_sam_ids": [],
        "minimum_clearance_km": validation["minimum_clearance_km"],
        "extended_control_point_count": len(extended),
        "cubic_span_count": cubic_span_count,
        "sampled_spline_point_count": len(smoothed),
    }


def _cubic_bspline_point(t: float, p0: Point, p1: Point, p2: Point, p3: Point) -> Point:
    t2 = t * t
    t3 = t2 * t
    g0 = (-t3 + 3.0 * t2 - 3.0 * t + 1.0) / 6.0
    g1 = (3.0 * t3 - 6.0 * t2 + 4.0) / 6.0
    g2 = (-3.0 * t3 + 3.0 * t2 + 3.0 * t + 1.0) / 6.0
    g3 = t3 / 6.0
    return (
        g0 * p0[0] + g1 * p1[0] + g2 * p2[0] + g3 * p3[0],
        g0 * p0[1] + g1 * p1[1] + g2 * p2[1] + g3 * p3[1],
    )


def _validate_path(path: List[Point], sams: List[Dict[str, Any]]) -> Dict[str, Any]:
    blockers: List[str] = []
    minimum_clearance: Optional[float] = None
    for sam in sams:
        center = _list_to_point(sam["pos"])
        radius = float(sam["range"])
        sam_blocked = False
        for index in range(len(path) - 1):
            clearance = _point_to_segment_distance(center, path[index], path[index + 1]) - radius
            if minimum_clearance is None or clearance < minimum_clearance:
                minimum_clearance = clearance
            if clearance < -APPATT_NUMERIC_TOLERANCE_KM:
                sam_blocked = True
        if sam_blocked:
            blockers.append(str(sam["id"]))
    return {
        "blocking_sam_ids": sorted(set(blockers)),
        "minimum_clearance_km": minimum_clearance,
    }


def _minimum_clearance(path: List[Point], sams: List[Dict[str, Any]]) -> Optional[float]:
    return _validate_path(path, sams)["minimum_clearance_km"]


def _point_to_segment_distance(point: Point, start: Point, end: Point) -> float:
    sx, sy = start
    ex, ey = end
    px, py = point
    dx = ex - sx
    dy = ey - sy
    length_sq = dx * dx + dy * dy
    if length_sq <= APPATT_NUMERIC_TOLERANCE_KM * APPATT_NUMERIC_TOLERANCE_KM:
        return _distance(point, start)

    t = ((px - sx) * dx + (py - sy) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    closest = (sx + t * dx, sy + t * dy)
    return _distance(point, closest)


def _raw_unavailable_result(
    pair: List[str],
    pair_id: str,
    raw_pair: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "pair": pair,
        "pair_id": pair_id,
        "direct_distance": float(raw_pair.get("direct_distance", UNAVAILABLE_COST)),
        "raw_appatt_status": raw_pair.get("classification", "UNAVAILABLE"),
        "raw_appatt_distance": UNAVAILABLE_COST,
        "raw_control_point_count": 0,
        "raw_path": [],
        "appatt_bspline_status": "RAW_UNAVAILABLE",
        "bspline_distance": UNAVAILABLE_COST,
        "sampled_spline_point_count": 0,
        "raw_to_spline_distance_difference": None,
        "collision_validation": "RAW_UNAVAILABLE",
        "blocking_sam_ids": [],
        "extended_control_point_count": None,
        "cubic_span_count": 0,
        "samples_per_span": None,
        "minimum_clearance_km": None,
        "failure_reason": raw_pair.get("failure_reason"),
    }


def _pair_id(pair: List[str]) -> str:
    return f"{pair[0]}-{pair[1]}"


def _list_to_point(point: List[float]) -> Point:
    return (float(point[0]), float(point[1]))


def _points_to_lists(points: List[Point]) -> List[List[float]]:
    return [[float(point[0]), float(point[1])] for point in points]


def _append_unique(points: List[Point], point: Point) -> None:
    if not points or _distance(points[-1], point) > APPATT_NUMERIC_TOLERANCE_KM:
        points.append(point)


def _distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _path_length(path: List[Point]) -> float:
    return sum(_distance(path[index], path[index + 1]) for index in range(len(path) - 1))
