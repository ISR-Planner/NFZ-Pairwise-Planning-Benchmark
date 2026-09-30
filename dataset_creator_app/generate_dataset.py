from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


ALLOWED_RADII = (1, 2, 5, 10, 15)
BLOCKING_RADII = (5, 10, 15)
AREA_SIZE = 150.0
WORKSPACE_HALF_KM = AREA_SIZE / 2.0
EARTH_RADIUS_KM = 6371.0088

# Geographic reference center from the native NFZ-aware mission sample.
MAP_CENTER_LAT = 33.51721451704408
MAP_CENTER_LNG = -90.14909708550584
MAP_CENTER_COS_LAT = math.cos(math.radians(MAP_CENTER_LAT))

TARGET_SPACING = 15.0
TARGET_CIRCLE_CLEARANCE = 2.0
TARGET_HULL_CLEARANCE = 1.0
EPS = 1e-7


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Circle:
    center: Point
    radius: int


@dataclass(frozen=True)
class Layout:
    airport: Point
    circles: tuple[Circle, ...]
    cluster_hulls: tuple[tuple[Point, ...], ...]
    targets: tuple[Point, ...]


def add(a: Point, b: Point) -> Point:
    return Point(a.x + b.x, a.y + b.y)


def sub(a: Point, b: Point) -> Point:
    return Point(a.x - b.x, a.y - b.y)


def mul(a: Point, scale: float) -> Point:
    return Point(a.x * scale, a.y * scale)


def dot(a: Point, b: Point) -> float:
    return a.x * b.x + a.y * b.y


def cross(o: Point, a: Point, b: Point) -> float:
    return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)


def dist(a: Point, b: Point) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def unit_from_angle(angle: float) -> Point:
    return Point(math.cos(angle), math.sin(angle))


def unit(a: Point) -> Point:
    length = math.hypot(a.x, a.y)
    if length <= EPS:
        raise ValueError("zero-length vector")
    return Point(a.x / length, a.y / length)


def left_perp(a: Point) -> Point:
    return Point(-a.y, a.x)


def midpoint(a: Point, b: Point) -> Point:
    return Point((a.x + b.x) / 2.0, (a.y + b.y) / 2.0)


def in_area(point: Point, margin: float = 0.0) -> bool:
    return (
        margin <= point.x <= AREA_SIZE - margin
        and margin <= point.y <= AREA_SIZE - margin
    )


def circle_in_area(circle: Circle) -> bool:
    return in_area(circle.center, circle.radius + 1.0)


def circle_points(circle: Circle, samples: int = 64) -> list[Point]:
    return [
        Point(
            circle.center.x + math.cos(2.0 * math.pi * i / samples) * circle.radius,
            circle.center.y + math.sin(2.0 * math.pi * i / samples) * circle.radius,
        )
        for i in range(samples)
    ]


def convex_hull(points: Iterable[Point]) -> tuple[Point, ...]:
    unique = sorted({(round(p.x, 9), round(p.y, 9)) for p in points})
    pts = [Point(x, y) for x, y in unique]
    if len(pts) <= 1:
        return tuple(pts)

    lower: list[Point] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= EPS:
            lower.pop()
        lower.append(p)

    upper: list[Point] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= EPS:
            upper.pop()
        upper.append(p)

    return tuple(lower[:-1] + upper[:-1])


def cluster_hull(circles: Iterable[Circle]) -> tuple[Point, ...]:
    pts: list[Point] = []
    for circle in circles:
        pts.extend(circle_points(circle))
    return convex_hull(pts)


def bbox(poly: Iterable[Point]) -> tuple[float, float, float, float]:
    pts = list(poly)
    return (
        min(p.x for p in pts),
        min(p.y for p in pts),
        max(p.x for p in pts),
        max(p.y for p in pts),
    )


def point_segment_distance(p: Point, a: Point, b: Point) -> float:
    ab = sub(b, a)
    denom = dot(ab, ab)
    if denom <= EPS:
        return dist(p, a)
    t = max(0.0, min(1.0, dot(sub(p, a), ab) / denom))
    projection = add(a, mul(ab, t))
    return dist(p, projection)


def point_on_segment(p: Point, a: Point, b: Point) -> bool:
    return point_segment_distance(p, a, b) <= 1e-6


def point_in_polygon(point: Point, poly: tuple[Point, ...]) -> bool:
    if not poly:
        return False
    for i, a in enumerate(poly):
        if point_on_segment(point, a, poly[(i + 1) % len(poly)]):
            return True

    inside = False
    x, y = point.x, point.y
    j = len(poly) - 1
    for i, pi in enumerate(poly):
        pj = poly[j]
        if (pi.y > y) != (pj.y > y):
            x_intersect = (pj.x - pi.x) * (y - pi.y) / (pj.y - pi.y) + pi.x
            if x < x_intersect:
                inside = not inside
        j = i
    return inside


def polygon_boundary_distance(point: Point, poly: tuple[Point, ...]) -> float:
    return min(
        point_segment_distance(point, poly[i], poly[(i + 1) % len(poly)])
        for i in range(len(poly))
    )


def outside_polygon_with_clearance(
    point: Point, poly: tuple[Point, ...], clearance: float
) -> bool:
    return (
        not point_in_polygon(point, poly)
        and polygon_boundary_distance(point, poly) >= clearance
    )


def ccw(a: Point, b: Point, c: Point) -> int:
    value = cross(a, b, c)
    if abs(value) <= EPS:
        return 0
    return 1 if value > 0 else -1


def segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    o1 = ccw(a, b, c)
    o2 = ccw(a, b, d)
    o3 = ccw(c, d, a)
    o4 = ccw(c, d, b)

    if o1 != o2 and o3 != o4:
        return True
    return (
        (o1 == 0 and point_on_segment(c, a, b))
        or (o2 == 0 and point_on_segment(d, a, b))
        or (o3 == 0 and point_on_segment(a, c, d))
        or (o4 == 0 and point_on_segment(b, c, d))
    )


def segment_intersects_polygon(a: Point, b: Point, poly: tuple[Point, ...]) -> bool:
    if point_in_polygon(a, poly) or point_in_polygon(b, poly):
        return True
    return any(
        segments_intersect(a, b, poly[i], poly[(i + 1) % len(poly)])
        for i in range(len(poly))
    )


def polygons_intersect(a: tuple[Point, ...], b: tuple[Point, ...]) -> bool:
    if any(point_in_polygon(p, b) for p in a):
        return True
    if any(point_in_polygon(p, a) for p in b):
        return True
    return any(
        segments_intersect(a[i], a[(i + 1) % len(a)], b[j], b[(j + 1) % len(b)])
        for i in range(len(a))
        for j in range(len(b))
    )


def polygon_distance(a: tuple[Point, ...], b: tuple[Point, ...]) -> float:
    if polygons_intersect(a, b):
        return 0.0
    distances: list[float] = []
    for p in a:
        distances.append(polygon_boundary_distance(p, b))
    for p in b:
        distances.append(polygon_boundary_distance(p, a))
    return min(distances)


def clear_of_circles(point: Point, circles: Iterable[Circle], clearance: float) -> bool:
    return all(dist(point, circle.center) - circle.radius >= clearance for circle in circles)


def clear_of_hulls(
    point: Point, hulls: Iterable[tuple[Point, ...]], clearance: float
) -> bool:
    return all(outside_polygon_with_clearance(point, hull, clearance) for hull in hulls)


def partial_overlap(a: Circle, b: Circle) -> bool:
    d = dist(a.center, b.center)
    return abs(a.radius - b.radius) + 0.25 < d < a.radius + b.radius - 0.25


def overlap_distance(rng: random.Random, r1: int, r2: int) -> float | None:
    low = abs(r1 - r2) + 0.7
    high = r1 + r2 - 0.7
    if low >= high:
        return None
    return rng.uniform(low, high)


def translated_circles(circles: Iterable[Circle], delta: Point) -> tuple[Circle, ...]:
    return tuple(Circle(add(circle.center, delta), circle.radius) for circle in circles)


def all_circles_in_area(circles: Iterable[Circle]) -> bool:
    return all(circle_in_area(circle) for circle in circles)


def make_targets(
    rng: random.Random,
    sampler: Callable[[], Point],
    circles: tuple[Circle, ...],
    hulls: tuple[tuple[Point, ...], ...],
    count: int = 12,
    extra_validator: Callable[[Point, tuple[Point, ...]], bool] | None = None,
) -> tuple[Point, ...] | None:
    targets: list[Point] = []
    for _ in range(12000):
        candidate = sampler()
        if not in_area(candidate, 2.0):
            continue
        if not clear_of_circles(candidate, circles, TARGET_CIRCLE_CLEARANCE):
            continue
        if not clear_of_hulls(candidate, hulls, TARGET_HULL_CLEARANCE):
            continue
        if any(dist(candidate, existing) < TARGET_SPACING for existing in targets):
            continue
        if extra_validator and not extra_validator(candidate, tuple(targets)):
            continue
        targets.append(candidate)
        if len(targets) == count:
            return tuple(targets)
    return None


def choose_c_trap_radii(rng: random.Random) -> list[int]:
    pool = [radius for radius in ALLOWED_RADII for _ in range(2)]
    rng.shuffle(pool)
    return pool[:5]


def validate_c_trap(
    circles: tuple[Circle, ...], route_dir: Point, lateral_dir: Point
) -> bool:
    if len(circles) != 5 or not all_circles_in_area(circles):
        return False

    for i in range(4):
        if not partial_overlap(circles[i], circles[i + 1]):
            return False

    for i in range(5):
        for j in range(i + 2, 5):
            d = dist(circles[i].center, circles[j].center)
            if {i, j} == {0, 4}:
                if d <= circles[i].radius + circles[j].radius + 4.0:
                    return False
            elif d <= circles[i].radius + circles[j].radius + 0.75:
                return False

    projections = [dot(circle.center, route_dir) for circle in circles]
    if projections[2] <= max(projections[0], projections[4]) + 6.0:
        return False
    if abs(dot(sub(circles[0].center, circles[4].center), lateral_dir)) <= 12.0:
        return False

    mouth_mid = midpoint(circles[0].center, circles[4].center)
    cavity = add(mouth_mid, mul(route_dir, max(6.0, projections[2] - dot(mouth_mid, route_dir)) * 0.45))
    if not clear_of_circles(cavity, circles, 0.75):
        return False

    hull = cluster_hull(circles)
    min_x, min_y, max_x, max_y = bbox(hull)
    return (max_x - min_x) >= 24.0 and (max_y - min_y) >= 30.0


def generate_c_trap(rng: random.Random) -> Layout:
    for _ in range(8000):
        route_angle = rng.uniform(math.radians(-15.0), math.radians(15.0))
        route_dir = unit_from_angle(route_angle)
        mouth_dir = mul(route_dir, -1.0)
        lateral_dir = left_perp(route_dir)

        radii = choose_c_trap_radii(rng)
        distances = [overlap_distance(rng, radii[i], radii[i + 1]) for i in range(4)]
        if any(value is None for value in distances):
            continue

        headings = [
            unit(add(mul(route_dir, 0.84), mul(lateral_dir, -0.54))),
            unit(add(mul(route_dir, 0.36), mul(lateral_dir, -0.93))),
            unit(add(mul(route_dir, -0.36), mul(lateral_dir, -0.93))),
            unit(add(mul(route_dir, -0.84), mul(lateral_dir, -0.54))),
        ]

        centers = [Point(0.0, 0.0)]
        for i, step in enumerate(distances):
            assert step is not None
            centers.append(add(centers[-1], mul(headings[i], step)))

        centroid = Point(
            sum(point.x for point in centers) / len(centers),
            sum(point.y for point in centers) / len(centers),
        )
        desired_center = Point(rng.uniform(70.0, 80.0), rng.uniform(68.0, 82.0))
        circles = tuple(
            Circle(add(sub(center, centroid), desired_center), radius)
            for center, radius in zip(centers, radii)
        )

        if not validate_c_trap(circles, route_dir, lateral_dir):
            continue

        hull = cluster_hull(circles)
        airport = add(
            desired_center,
            add(mul(mouth_dir, rng.uniform(48.0, 58.0)), mul(lateral_dir, rng.uniform(-6.0, 6.0))),
        )
        if not in_area(airport, 2.0):
            continue
        if not clear_of_circles(airport, circles, 1.0):
            continue
        if not clear_of_hulls(airport, (hull,), TARGET_HULL_CLEARANCE):
            continue

        def sample_target() -> Point:
            return add(
                desired_center,
                add(
                    mul(route_dir, rng.uniform(38.0, 73.0)),
                    mul(lateral_dir, rng.uniform(-58.0, 58.0)),
                ),
            )

        def c_trap_target_validator(candidate: Point, _: tuple[Point, ...]) -> bool:
            return segment_intersects_polygon(airport, candidate, hull)

        targets = make_targets(
            rng,
            sample_target,
            circles,
            (hull,),
            extra_validator=c_trap_target_validator,
        )
        if targets is None:
            continue

        return Layout(airport, circles, (hull,), targets)

    raise RuntimeError("failed to generate a valid C-Trap layout")


def make_pair(
    rng: random.Random, midpoint_point: Point, theta: float, radii: tuple[int, int]
) -> tuple[Circle, ...] | None:
    separation = overlap_distance(rng, radii[0], radii[1])
    if separation is None:
        return None
    axis = unit_from_angle(theta)
    return (
        Circle(add(midpoint_point, mul(axis, -separation / 2.0)), radii[0]),
        Circle(add(midpoint_point, mul(axis, separation / 2.0)), radii[1]),
    )


def relative_pair(rng: random.Random) -> tuple[tuple[Circle, ...], float] | None:
    radii = (rng.choice(BLOCKING_RADII), rng.choice(BLOCKING_RADII))
    theta = math.pi / 2.0 + rng.uniform(math.radians(-15.0), math.radians(15.0))
    pair = make_pair(rng, Point(0.0, 0.0), theta, radii)
    if pair is None:
        return None
    return pair, theta


def validate_sequential(
    clusters: tuple[tuple[Circle, ...], ...],
    hulls: tuple[tuple[Point, ...], ...],
    airport: Point,
    nominal_target: Point,
) -> bool:
    if len(clusters) != 3 or any(len(cluster) != 2 for cluster in clusters):
        return False
    if not all_circles_in_area(circle for cluster in clusters for circle in cluster):
        return False
    if not all(partial_overlap(cluster[0], cluster[1]) for cluster in clusters):
        return False

    for i in range(3):
        for j in range(i + 1, 3):
            for a in clusters[i]:
                for b in clusters[j]:
                    if dist(a.center, b.center) <= a.radius + b.radius + 0.75:
                        return False

    boxes = [bbox(hull) for hull in hulls]
    for i in range(2):
        gap = boxes[i + 1][0] - boxes[i][2]
        if not 6.0 <= gap <= 12.0:
            return False

    return all(segment_intersects_polygon(airport, nominal_target, hull) for hull in hulls)


def generate_sequential_staggered(rng: random.Random) -> Layout:
    route_y = 75.0
    for _ in range(8000):
        mirror = rng.choice((-1.0, 1.0))
        signs = (mirror, -mirror, mirror)
        relative_clusters: list[tuple[Circle, ...]] = []
        relative_hulls: list[tuple[Point, ...]] = []

        for _idx in range(3):
            pair_data = relative_pair(rng)
            if pair_data is None:
                break
            pair, _theta = pair_data
            relative_clusters.append(pair)
            relative_hulls.append(cluster_hull(pair))
        if len(relative_clusters) != 3:
            continue

        clusters: list[tuple[Circle, ...]] = []
        hulls: list[tuple[Point, ...]] = []
        previous_right: float | None = None

        for idx, pair in enumerate(relative_clusters):
            rel_hull = relative_hulls[idx]
            min_x, min_y, max_x, max_y = bbox(rel_hull)
            half_height = max(abs(min_y), abs(max_y))
            y_shift = route_y + signs[idx] * rng.uniform(0.45, 0.65) * half_height
            if previous_right is None:
                left_edge = rng.uniform(33.0, 38.0)
            else:
                left_edge = previous_right + rng.uniform(6.0, 12.0)
            x_shift = left_edge - min_x
            shifted = translated_circles(pair, Point(x_shift, y_shift))
            hull = cluster_hull(shifted)
            clusters.append(shifted)
            hulls.append(hull)
            previous_right = bbox(hull)[2]

        airport = Point(rng.uniform(10.0, 14.0), route_y + rng.uniform(-3.0, 3.0))
        nominal_target = Point(rng.uniform(136.0, 140.0), route_y + rng.uniform(-3.0, 3.0))
        clusters_tuple = tuple(clusters)
        hulls_tuple = tuple(hulls)

        if not validate_sequential(clusters_tuple, hulls_tuple, airport, nominal_target):
            continue
        if not clear_of_circles(airport, tuple(c for cl in clusters for c in cl), 1.0):
            continue
        if not clear_of_hulls(airport, hulls_tuple, TARGET_HULL_CLEARANCE):
            continue

        circles = tuple(circle for cluster in clusters for circle in cluster)
        max_hull_x = max(bbox(hull)[2] for hull in hulls_tuple)
        target_x_min = max(105.0, max_hull_x + 6.0)
        if target_x_min > 142.0:
            continue

        def sample_target() -> Point:
            return Point(rng.uniform(target_x_min, 148.0), rng.uniform(18.0, 132.0))

        targets = make_targets(rng, sample_target, circles, hulls_tuple)
        if targets is None:
            continue

        return Layout(airport, circles, hulls_tuple, targets)

    raise RuntimeError("failed to generate a valid Sequential Staggered Blocking layout")


def make_chain_cluster(
    rng: random.Random, count: int, radii: tuple[int, ...], base_angle: float
) -> tuple[Circle, ...] | None:
    centers = [Point(0.0, 0.0)]
    for i in range(count - 1):
        separation = overlap_distance(rng, radii[i], radii[i + 1])
        if separation is None:
            return None
        angle = base_angle + rng.uniform(math.radians(-24.0), math.radians(24.0))
        centers.append(add(centers[-1], mul(unit_from_angle(angle), separation)))

    centroid = Point(
        sum(point.x for point in centers) / len(centers),
        sum(point.y for point in centers) / len(centers),
    )
    return tuple(
        Circle(sub(center, centroid), radius) for center, radius in zip(centers, radii)
    )


def validate_chain_cluster(circles: tuple[Circle, ...]) -> bool:
    return all(partial_overlap(circles[i], circles[i + 1]) for i in range(len(circles) - 1))


def place_corridor_cluster(
    circles: tuple[Circle, ...],
    center_x: float,
    route_y: float,
    corridor_width: float,
    side: int,
) -> tuple[Circle, ...]:
    hull = cluster_hull(circles)
    min_x, min_y, max_x, max_y = bbox(hull)
    x_shift = center_x - ((min_x + max_x) / 2.0)
    if side > 0:
        y_shift = route_y + corridor_width / 2.0 - min_y
    else:
        y_shift = route_y - corridor_width / 2.0 - max_y
    return translated_circles(circles, Point(x_shift, y_shift))


def validate_asymmetric(
    upper: tuple[Circle, ...],
    lower: tuple[Circle, ...],
    upper_hull: tuple[Point, ...],
    lower_hull: tuple[Point, ...],
    airport: Point,
    nominal_target: Point,
) -> bool:
    if not all_circles_in_area((*upper, *lower)):
        return False
    if not validate_chain_cluster(upper) or not validate_chain_cluster(lower):
        return False
    if polygons_intersect(upper_hull, lower_hull):
        return False

    corridor_gap = polygon_distance(upper_hull, lower_hull)
    if not 8.0 <= corridor_gap <= 30.0:
        return False
    if segment_intersects_polygon(airport, nominal_target, upper_hull):
        return False
    if segment_intersects_polygon(airport, nominal_target, lower_hull):
        return False

    upper_box = bbox(upper_hull)
    lower_box = bbox(lower_hull)
    x_overlap = min(upper_box[2], lower_box[2]) - max(upper_box[0], lower_box[0])
    return x_overlap >= 20.0


def generate_asymmetric_corridor(rng: random.Random) -> Layout:
    for _ in range(8000):
        route_y = rng.uniform(70.0, 80.0)
        corridor_width = rng.uniform(11.0, 24.0)
        three_on_top = rng.choice((True, False))

        triple_radii = tuple(rng.choice((5, 10, 10, 15)) for _ in range(3))
        pair_radii = tuple(rng.choice((2, 5, 10, 15)) for _ in range(2))
        triple = make_chain_cluster(
            rng, 3, triple_radii, rng.uniform(math.radians(-15.0), math.radians(15.0))
        )
        pair = make_chain_cluster(
            rng, 2, pair_radii, rng.uniform(math.radians(-25.0), math.radians(25.0))
        )
        if triple is None or pair is None:
            continue

        top_source = triple if three_on_top else pair
        bottom_source = pair if three_on_top else triple
        upper = place_corridor_cluster(
            top_source, rng.uniform(70.0, 83.0), route_y, corridor_width, 1
        )
        lower = place_corridor_cluster(
            bottom_source, rng.uniform(67.0, 80.0), route_y, corridor_width, -1
        )
        upper_hull = cluster_hull(upper)
        lower_hull = cluster_hull(lower)

        airport = Point(rng.uniform(10.0, 15.0), route_y + rng.uniform(-3.0, 3.0))
        nominal_target = Point(rng.uniform(135.0, 141.0), route_y + rng.uniform(-3.0, 3.0))

        if not validate_asymmetric(upper, lower, upper_hull, lower_hull, airport, nominal_target):
            continue

        circles = (*upper, *lower)
        hulls = (upper_hull, lower_hull)
        if not clear_of_circles(airport, circles, 1.0):
            continue
        if not clear_of_hulls(airport, hulls, TARGET_HULL_CLEARANCE):
            continue

        max_hull_x = max(bbox(upper_hull)[2], bbox(lower_hull)[2])
        target_x_min = max(106.0, max_hull_x + 6.0)
        if target_x_min > 142.0:
            continue

        def sample_target() -> Point:
            return Point(
                rng.uniform(target_x_min, 148.0),
                route_y + rng.uniform(-55.0, 55.0),
            )

        targets = make_targets(rng, sample_target, circles, hulls)
        if targets is None:
            continue

        return Layout(airport, circles, hulls, targets)

    raise RuntimeError("failed to generate a valid Asymmetric Corridor layout")


TOPOLOGIES: tuple[tuple[str, Callable[[random.Random], Layout]], ...] = (
    ("c_trap", generate_c_trap),
    ("sequential_staggered_blocking", generate_sequential_staggered),
    ("asymmetric_corridor", generate_asymmetric_corridor),
)


def native_lat_lng(point: Point) -> dict[str, float]:
    dx_km = point.x - WORKSPACE_HALF_KM
    dy_km = point.y - WORKSPACE_HALF_KM
    return {
        "lat": round(MAP_CENTER_LAT + math.degrees(dy_km / EARTH_RADIUS_KM), 12),
        "lng": round(
            MAP_CENTER_LNG
            + math.degrees(dx_km / (EARTH_RADIUS_KM * MAP_CENTER_COS_LAT)),
            12,
        ),
    }


def native_point(lat_lng: dict[str, float]) -> Point:
    dx_km = (
        math.radians(lat_lng["lng"] - MAP_CENTER_LNG)
        * EARTH_RADIUS_KM
        * MAP_CENTER_COS_LAT
    )
    dy_km = math.radians(lat_lng["lat"] - MAP_CENTER_LAT) * EARTH_RADIUS_KM
    return Point(WORKSPACE_HALF_KM + dx_km, WORKSPACE_HALF_KM + dy_km)


def map_bounds() -> dict[str, float]:
    southwest = native_lat_lng(Point(0.0, 0.0))
    northeast = native_lat_lng(Point(AREA_SIZE, AREA_SIZE))
    return {
        "south": southwest["lat"],
        "north": northeast["lat"],
        "west": southwest["lng"],
        "east": northeast["lng"],
    }


def airport_record(point: Point) -> dict[str, object]:
    return {"id": "A1", **native_lat_lng(point), "runway": "L"}


def sam_record(circle: Circle) -> dict[str, object]:
    return {"center": native_lat_lng(circle.center), "range_km": circle.radius}


def target_record(index: int, point: Point) -> dict[str, object]:
    return {
        "id": f"T{index}",
        **native_lat_lng(point),
        "priority": 5,
        "type": "a",
    }


def drone_configs() -> dict[str, dict[str, object]]:
    template: dict[str, object] = {
        "enabled": True,
        "fuel_budget": 500,
        "start_airport": "A1",
        "end_airport": "A1",
        "refuel_airport": "",
        "refuel_stops": [],
        "refuel_options": [],
        "max_refuels": 4,
        "runway": "S",
        "target_access": {"a": True, "b": True, "c": True, "d": True, "e": True},
        "speed": 1,
        "loiter_enabled": False,
        "loiter_times": {"a": 0, "b": 0, "c": 0, "d": 0, "e": 0},
        "detection_radius": {"a": 0, "b": 0, "c": 0, "d": 0, "e": 0},
    }
    return {str(index): copy.deepcopy(template) for index in range(1, 6)}


def build_environment(layout: Layout, target_count: int) -> dict[str, object]:
    configs = drone_configs()
    env = {
        "airports": [airport_record(layout.airport)],
        "sams": [sam_record(circle) for circle in layout.circles],
        "drone_configs": copy.deepcopy(configs),
        "targets": [
            target_record(index, point)
            for index, point in enumerate(layout.targets[:target_count], start=1)
        ],
    }
    return {
        "schema": "nfz_env_v1",
        "is_segmented": False,
        "segment_count": 1,
        "env": env,
        "drone_configs": copy.deepcopy(configs),
        "time_sync": {
            "enabled": False,
            "mode": "first_target_arrival",
            "wait_strategy": "launch_delay",
            "tolerance": 1,
        },
        "map_view": {
            "bounds": map_bounds(),
            "center": {"lat": MAP_CENTER_LAT, "lng": MAP_CENTER_LNG},
            "zoom": 8,
        },
    }


def derived_seed(base_seed: int, topology: str, family_index: int) -> int:
    digest = hashlib.sha256(f"{base_seed}:{topology}:{family_index}".encode("ascii")).digest()
    return int.from_bytes(digest[:8], "big")


def write_family(
    out_dir: Path,
    topology: str,
    family_index: int,
    layout: Layout,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for target_count in (4, 8, 12):
        payload = build_environment(layout, target_count)
        path = out_dir / f"{topology}_{family_index:03d}_t{target_count:02d}.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
        paths.append(path)
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate native NFZ environment JSON benchmark families."
    )
    parser.add_argument("--out", default="dataset", help="Output directory.")
    parser.add_argument("--seed", type=int, default=20260808, help="Base random seed.")
    parser.add_argument(
        "--families",
        type=int,
        default=1,
        help="Independent families per topology.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.families < 1:
        raise SystemExit("--families must be at least 1")

    out_dir = Path(args.out)
    written: list[Path] = []
    for topology, generator in TOPOLOGIES:
        for family_index in range(1, args.families + 1):
            rng = random.Random(derived_seed(args.seed, topology, family_index))
            layout = generator(rng)
            written.extend(write_family(out_dir, topology, family_index, layout))

    for path in written:
        print(path.as_posix())


if __name__ == "__main__":
    main()
