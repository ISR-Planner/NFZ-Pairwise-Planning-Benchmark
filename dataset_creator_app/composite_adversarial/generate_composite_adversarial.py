from __future__ import annotations

import copy
import hashlib
import heapq
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SEED = 20260809
TOPOLOGY_NAME = "Composite Adversarial Stress"
TOPOLOGY_STEM = "composite_adversarial"
FAMILY_INDEX = 1
AREA_SIZE = 150.0
WORKSPACE_HALF_KM = AREA_SIZE / 2.0
EARTH_RADIUS_KM = 6371.0088
MAP_CENTER_LAT = 33.51721451704408
MAP_CENTER_LNG = -90.14909708550584
MAP_CENTER_COS_LAT = math.cos(math.radians(MAP_CENTER_LAT))
ALLOWED_RADII = {1, 2, 5, 10, 15}
TARGET_SPACING = 15.0
TARGET_CIRCLE_CLEARANCE = 2.0
TARGET_HULL_CLEARANCE = 1.0
EPS = 1e-7

ROOT = Path(__file__).resolve().parent
ORIGINAL_DATASET_DIR = ROOT.parent / "dataset"
DATASET_DIR = ROOT / "dataset"
VALIDATION_DIR = ROOT / "validation"
PREVIEW_DIR = VALIDATION_DIR / "previews"
BEFORE_HASH_PATH = VALIDATION_DIR / "original_dataset_hashes_before.json"
AFTER_HASH_PATH = VALIDATION_DIR / "original_dataset_hashes_after.json"
VALIDATION_JSON_PATH = VALIDATION_DIR / "composite_adversarial_validation.json"
VALIDATION_MD_PATH = VALIDATION_DIR / "composite_adversarial_validation.md"
README_PATH = ROOT / "README.md"


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Circle:
    id: str
    motif: str
    cluster: str
    center: Point
    radius: int


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


def circle_points(circle: Circle, samples: int = 72) -> list[Point]:
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


def segment_intersects_polygon(a: Point, b: Point, poly: tuple[Point, ...]) -> bool:
    if point_in_polygon(a, poly) or point_in_polygon(b, poly):
        return True
    return any(
        segments_intersect(a, b, poly[i], poly[(i + 1) % len(poly)])
        for i in range(len(poly))
    )


def segment_intersects_circle(a: Point, b: Point, circle: Circle) -> bool:
    return point_segment_distance(circle.center, a, b) <= circle.radius


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


def in_area(point: Point, margin: float = 0.0) -> bool:
    return margin <= point.x <= AREA_SIZE - margin and margin <= point.y <= AREA_SIZE - margin


def circle_in_area(circle: Circle) -> bool:
    return in_area(circle.center, circle.radius + 1.0)


def partial_overlap(a: Circle, b: Circle) -> bool:
    d = dist(a.center, b.center)
    return abs(a.radius - b.radius) + 0.25 < d < a.radius + b.radius - 0.25


def no_circle_overlap(a: Circle, b: Circle, margin: float = 0.0) -> bool:
    return dist(a.center, b.center) > a.radius + b.radius + margin


def circle_clearance(point: Point, circles: Iterable[Circle]) -> float:
    return min(dist(point, circle.center) - circle.radius for circle in circles)


def hull_clearance(point: Point, hulls: Iterable[tuple[Point, ...]]) -> float:
    clearances = []
    for hull in hulls:
        if point_in_polygon(point, hull):
            clearances.append(-polygon_boundary_distance(point, hull))
        else:
            clearances.append(polygon_boundary_distance(point, hull))
    return min(clearances)


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


def nfz_record(circle: Circle) -> dict[str, object]:
    return {"center": native_lat_lng(circle.center), "range_km": circle.radius}


def target_record(index: int, point: Point) -> dict[str, object]:
    return {"id": f"T{index}", **native_lat_lng(point), "priority": 5, "type": "a"}


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


def build_environment(airport: Point, circles: tuple[Circle, ...], targets: tuple[Point, ...], target_count: int) -> dict[str, object]:
    configs = drone_configs()
    env = {
        "airports": [airport_record(airport)],
        "sams": [nfz_record(circle) for circle in circles],
        "drone_configs": copy.deepcopy(configs),
        "targets": [target_record(index, point) for index, point in enumerate(targets[:target_count], start=1)],
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


def make_c_trap() -> list[Circle]:
    radii = [10, 15, 10, 15, 5]
    steps = [17.0, 17.0, 17.0, 14.0]
    headings = [Point(0.84, -0.54), Point(0.36, -0.93), Point(-0.36, -0.93), Point(-0.84, -0.54)]
    centers = [Point(0.0, 0.0)]
    for step, heading in zip(steps, headings):
        centers.append(add(centers[-1], mul(heading, step)))
    centroid = Point(sum(p.x for p in centers) / len(centers), sum(p.y for p in centers) / len(centers))
    desired_center = Point(39.0, 80.0)
    circles = []
    for idx, (center, radius) in enumerate(zip(centers, radii), start=1):
        shifted = add(sub(center, centroid), desired_center)
        circles.append(Circle(f"NFZ{idx:02d}", "C-Trap", "c_trap_chain", shifted, radius))
    return circles


def make_sequential() -> list[Circle]:
    circles: list[Circle] = []
    clusters = [(67.0, 54.0), (84.0, 91.0), (101.0, 57.0)]
    idx = 6
    for cluster_index, (x, y) in enumerate(clusters, start=1):
        circles.append(Circle(f"NFZ{idx:02d}", "Sequential Staggered Blocking", f"sequential_pair_{cluster_index}", Point(x, y - 4.0), 5))
        idx += 1
        circles.append(Circle(f"NFZ{idx:02d}", "Sequential Staggered Blocking", f"sequential_pair_{cluster_index}", Point(x, y + 4.0), 5))
        idx += 1
    return circles


def make_asymmetric() -> list[Circle]:
    return [
        Circle("NFZ12", "Asymmetric Corridor", "asymmetric_upper_3", Point(116.0, 94.0), 10),
        Circle("NFZ13", "Asymmetric Corridor", "asymmetric_upper_3", Point(127.0, 96.0), 10),
        Circle("NFZ14", "Asymmetric Corridor", "asymmetric_upper_3", Point(137.0, 94.0), 5),
        Circle("NFZ15", "Asymmetric Corridor", "asymmetric_lower_2", Point(118.0, 55.0), 10),
        Circle("NFZ16", "Asymmetric Corridor", "asymmetric_lower_2", Point(132.0, 58.0), 10),
    ]


def build_layout() -> tuple[Point, tuple[Circle, ...], tuple[Point, ...]]:
    random.Random(SEED)
    airport = Point(10.0, 80.0)
    circles = tuple(make_c_trap() + make_sequential() + make_asymmetric())
    targets = (
        Point(145.0, 105.0),
        Point(145.0, 55.0),
        Point(128.0, 128.0),
        Point(130.0, 28.0),
        Point(112.0, 113.0),
        Point(112.0, 42.0),
        Point(145.0, 83.0),
        Point(145.0, 18.0),
        Point(125.0, 76.0),
        Point(97.0, 125.0),
        Point(98.0, 30.0),
        Point(145.0, 130.0),
    )
    return airport, circles, targets


def circles_by_motif(circles: tuple[Circle, ...]) -> dict[str, tuple[Circle, ...]]:
    motifs = ("C-Trap", "Sequential Staggered Blocking", "Asymmetric Corridor")
    return {motif: tuple(circle for circle in circles if circle.motif == motif) for motif in motifs}


def circles_by_cluster(circles: tuple[Circle, ...]) -> dict[str, tuple[Circle, ...]]:
    clusters: dict[str, list[Circle]] = {}
    for circle in circles:
        clusters.setdefault(circle.cluster, []).append(circle)
    return {key: tuple(value) for key, value in clusters.items()}


def overlap_components(circles: tuple[Circle, ...]) -> list[list[Circle]]:
    parent = list(range(len(circles)))

    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i, a in enumerate(circles):
        for j, b in enumerate(circles[i + 1 :], start=i + 1):
            if dist(a.center, b.center) <= a.radius + b.radius:
                union(i, j)

    groups: dict[int, list[Circle]] = {}
    for index, circle in enumerate(circles):
        groups.setdefault(find(index), []).append(circle)
    return list(groups.values())


def motif_hulls(circles: tuple[Circle, ...]) -> dict[str, list[tuple[Point, ...]]]:
    by_cluster = circles_by_cluster(circles)
    return {
        "C-Trap": [cluster_hull(by_cluster["c_trap_chain"])],
        "Sequential Staggered Blocking": [
            cluster_hull(by_cluster["sequential_pair_1"]),
            cluster_hull(by_cluster["sequential_pair_2"]),
            cluster_hull(by_cluster["sequential_pair_3"]),
        ],
        "Asymmetric Corridor": [
            cluster_hull(by_cluster["asymmetric_upper_3"]),
            cluster_hull(by_cluster["asymmetric_lower_2"]),
        ],
    }


def all_wrapped_hulls(circles: tuple[Circle, ...]) -> list[tuple[Point, ...]]:
    return [cluster_hull(tuple(component)) for component in overlap_components(circles)]


def segment_motif_hits(a: Point, b: Point, circles: tuple[Circle, ...]) -> list[str]:
    hits: list[str] = []
    by_motif = circles_by_motif(circles)
    hulls = motif_hulls(circles)
    for motif in ("C-Trap", "Sequential Staggered Blocking", "Asymmetric Corridor"):
        circle_hit = any(segment_intersects_circle(a, b, circle) for circle in by_motif[motif])
        hull_hit = any(segment_intersects_polygon(a, b, hull) for hull in hulls[motif])
        if circle_hit or hull_hit:
            hits.append(motif)
    return hits


def path_length(points: list[Point]) -> float:
    return sum(dist(points[i], points[i + 1]) for i in range(len(points) - 1))


def polyline_clear_of_circles(points: list[Point], circles: tuple[Circle, ...]) -> bool:
    return not any(
        segment_intersects_circle(points[i], points[i + 1], circle)
        for i in range(len(points) - 1)
        for circle in circles
    )


def independent_connectivity(airport: Point, targets: tuple[Point, ...], circles: tuple[Circle, ...]) -> dict[str, object]:
    grid_step = 1.0
    sample_clearance = 0.05
    grid_size = int(AREA_SIZE / grid_step) + 1

    def free(point: Point, clearance: float = sample_clearance) -> bool:
        return in_area(point, 0.0) and all(dist(point, circle.center) > circle.radius + clearance for circle in circles)

    def edge_free(a: Point, b: Point) -> bool:
        length = dist(a, b)
        samples = max(1, math.ceil(length / 0.4))
        for idx in range(samples + 1):
            t = idx / samples
            point = Point(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)
            if not free(point):
                return False
        return True

    free_grid = [
        [free(Point(x * grid_step, y * grid_step)) for y in range(grid_size)]
        for x in range(grid_size)
    ]

    def nearest_free_node(point: Point) -> tuple[int, int] | None:
        base_x = round(point.x / grid_step)
        base_y = round(point.y / grid_step)
        best: tuple[float, int, int] | None = None
        for radius in range(0, 6):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    x = base_x + dx
                    y = base_y + dy
                    if 0 <= x < grid_size and 0 <= y < grid_size and free_grid[x][y]:
                        candidate = Point(x * grid_step, y * grid_step)
                        value = dist(point, candidate)
                        if best is None or value < best[0]:
                            best = (value, x, y)
            if best is not None:
                return (best[1], best[2])
        return None

    start = nearest_free_node(airport)
    if start is None:
        return {"all_targets_reachable": False, "reason": "airport has no free grid node"}

    directions = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
    queue: list[tuple[float, tuple[int, int]]] = [(0.0, start)]
    distances: dict[tuple[int, int], float] = {start: 0.0}
    while queue:
        cost, node = heapq.heappop(queue)
        if cost != distances[node]:
            continue
        x, y = node
        a = Point(x * grid_step, y * grid_step)
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < grid_size and 0 <= ny < grid_size) or not free_grid[nx][ny]:
                continue
            b = Point(nx * grid_step, ny * grid_step)
            if not edge_free(a, b):
                continue
            next_cost = cost + math.hypot(dx, dy) * grid_step
            next_node = (nx, ny)
            if next_cost < distances.get(next_node, float("inf")):
                distances[next_node] = next_cost
                heapq.heappush(queue, (next_cost, next_node))

    target_results = []
    for index, target in enumerate(targets, start=1):
        node = nearest_free_node(target)
        reachable = node in distances if node is not None else False
        target_results.append(
            {
                "target": f"T{index}",
                "nearest_grid_node": list(node) if node is not None else None,
                "reachable": reachable,
                "grid_path_length_km": round(distances[node], 6) if reachable and node is not None else None,
            }
        )

    return {
        "method": "independent 1 km occupancy-grid Dijkstra connectivity check; not a benchmark method",
        "grid_step_km": grid_step,
        "sample_clearance_km": sample_clearance,
        "visited_free_nodes": len(distances),
        "airport_grid_node": list(start),
        "all_targets_reachable": all(item["reachable"] for item in target_results),
        "targets": target_results,
    }


def original_dataset_hashes() -> dict[str, object]:
    files = []
    for path in sorted(ORIGINAL_DATASET_DIR.glob("*.json")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"file": path.name, "bytes": path.stat().st_size, "sha256": digest})
    return {
        "source_dataset": str(ORIGINAL_DATASET_DIR),
        "file_count": len(files),
        "files": files,
    }


def ensure_before_hashes() -> dict[str, object]:
    if BEFORE_HASH_PATH.exists():
        return json.loads(BEFORE_HASH_PATH.read_text(encoding="utf-8-sig"))
    manifest = original_dataset_hashes()
    BEFORE_HASH_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def compare_hashes(before_manifest: dict[str, object], after_manifest: dict[str, object]) -> tuple[bool, list[dict[str, object]]]:
    before_files = {item["file"]: item for item in before_manifest.get("files", [])}
    after_files = {item["file"]: item for item in after_manifest.get("files", [])}
    names = sorted(set(before_files) | set(after_files))
    comparisons = []
    for name in names:
        before = before_files.get(name)
        after = after_files.get(name)
        comparisons.append(
            {
                "file": name,
                "present_before": before is not None,
                "present_after": after is not None,
                "bytes_before": before.get("bytes") if before else None,
                "bytes_after": after.get("bytes") if after else None,
                "sha256_before": before.get("sha256") if before else None,
                "sha256_after": after.get("sha256") if after else None,
                "byte_identical": before == after,
            }
        )
    return all(item["byte_identical"] for item in comparisons), comparisons


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def target_payload_points(payload: dict[str, object]) -> list[dict[str, object]]:
    return list(payload["env"]["targets"])


def validate_payload_invariants(payloads: dict[int, dict[str, object]]) -> dict[str, object]:
    t04 = target_payload_points(payloads[4])
    t08 = target_payload_points(payloads[8])
    t12 = target_payload_points(payloads[12])
    nfz_04 = payloads[4]["env"]["sams"]
    nfz_08 = payloads[8]["env"]["sams"]
    nfz_12 = payloads[12]["env"]["sams"]
    airport_04 = payloads[4]["env"]["airports"]
    airport_08 = payloads[8]["env"]["airports"]
    airport_12 = payloads[12]["env"]["airports"]
    return {
        "t04_preserved_in_t08_and_t12": t04 == t08[:4] == t12[:4],
        "t08_preserved_in_t12": t08 == t12[:8],
        "nfz_geometry_identical": nfz_04 == nfz_08 == nfz_12,
        "airport_identical": airport_04 == airport_08 == airport_12,
    }


def make_validation(airport: Point, circles: tuple[Circle, ...], targets: tuple[Point, ...], payloads: dict[int, dict[str, object]]) -> dict[str, object]:
    by_motif = circles_by_motif(circles)
    by_cluster = circles_by_cluster(circles)
    hulls_by_motif = motif_hulls(circles)
    wrapped_hulls = all_wrapped_hulls(circles)
    payload_invariants = validate_payload_invariants(payloads)

    c_trap = by_motif["C-Trap"]
    c_adjacent = [partial_overlap(c_trap[i], c_trap[i + 1]) for i in range(4)]
    c_non_adjacent_clear = all(
        no_circle_overlap(c_trap[i], c_trap[j], 0.75 if {i, j} != {0, 4} else 4.0)
        for i in range(5)
        for j in range(i + 2, 5)
    )
    c_radii_counts = {radius: sum(1 for circle in c_trap if circle.radius == radius) for radius in sorted(ALLOWED_RADII)}
    c_mouth_distance = dist(c_trap[0].center, c_trap[4].center)
    c_hull = hulls_by_motif["C-Trap"][0]
    c_box = bbox(c_hull)
    c_structural = all(c_adjacent) and c_non_adjacent_clear and max(c_radii_counts.values()) <= 2 and c_mouth_distance > c_trap[0].radius + c_trap[4].radius + 4.0 and (c_box[2] - c_box[0]) >= 24.0 and (c_box[3] - c_box[1]) >= 30.0

    sequential_clusters = [by_cluster[f"sequential_pair_{index}"] for index in range(1, 4)]
    sequential_hulls = hulls_by_motif["Sequential Staggered Blocking"]
    sequential_pair_overlap = [partial_overlap(cluster[0], cluster[1]) for cluster in sequential_clusters]
    sequential_orientations = []
    for cluster in sequential_clusters:
        a, b = cluster
        angle = abs(math.degrees(math.atan2(b.center.y - a.center.y, b.center.x - a.center.x)))
        if angle > 180.0:
            angle -= 180.0
        sequential_orientations.append(angle)
    sequential_gaps = [bbox(sequential_hulls[i + 1])[0] - bbox(sequential_hulls[i])[2] for i in range(2)]
    sequential_centers_y = [sum(circle.center.y for circle in cluster) / len(cluster) for cluster in sequential_clusters]
    sequential_staggered = sequential_centers_y[0] < 75.0 and sequential_centers_y[1] > 75.0 and sequential_centers_y[2] < 75.0
    sequential_distinct = all(
        no_circle_overlap(a, b, 0.75)
        for i, left_cluster in enumerate(sequential_clusters)
        for right_cluster in sequential_clusters[i + 1 :]
        for a in left_cluster
        for b in right_cluster
    )
    sequential_structural = all(sequential_pair_overlap) and all(75.0 <= angle <= 105.0 for angle in sequential_orientations) and all(6.0 <= gap <= 12.0 for gap in sequential_gaps) and sequential_staggered and sequential_distinct

    asym_upper = by_cluster["asymmetric_upper_3"]
    asym_lower = by_cluster["asymmetric_lower_2"]
    asym_upper_hull, asym_lower_hull = hulls_by_motif["Asymmetric Corridor"]
    asym_overlaps = [partial_overlap(asym_upper[0], asym_upper[1]), partial_overlap(asym_upper[1], asym_upper[2]), partial_overlap(asym_lower[0], asym_lower[1])]
    asym_corridor_gap = polygon_distance(asym_upper_hull, asym_lower_hull)
    upper_box = bbox(asym_upper_hull)
    lower_box = bbox(asym_lower_hull)
    asym_x_overlap = min(upper_box[2], lower_box[2]) - max(upper_box[0], lower_box[0])
    corridor_probe = not segment_intersects_polygon(Point(104.0, 76.0), Point(146.0, 76.0), asym_upper_hull) and not segment_intersects_polygon(Point(104.0, 76.0), Point(146.0, 76.0), asym_lower_hull)
    asym_structural = all(asym_overlaps) and not polygons_intersect(asym_upper_hull, asym_lower_hull) and 8.0 <= asym_corridor_gap <= 30.0 and asym_x_overlap >= 20.0 and corridor_probe and len(asym_upper) == 3 and len(asym_lower) == 2

    cross_motif_gaps = [
        dist(a.center, b.center) - a.radius - b.radius
        for i, a in enumerate(circles)
        for b in circles[i + 1 :]
        if a.motif != b.motif
    ]
    wrapped_region_distances = [
        polygon_distance(wrapped_hulls[i], wrapped_hulls[j])
        for i in range(len(wrapped_hulls))
        for j in range(i + 1, len(wrapped_hulls))
    ]

    target_spacings = [dist(a, b) for i, a in enumerate(targets) for b in targets[i + 1 :]]
    target_circle_clearances = [circle_clearance(target, circles) for target in targets]
    target_hull_clearances = [hull_clearance(target, wrapped_hulls) for target in targets]
    airport_circle_clearance = circle_clearance(airport, circles)
    airport_hull_clearance = hull_clearance(airport, wrapped_hulls)
    target_bounds_ok = all(in_area(target, 2.0) for target in targets)
    circle_bounds_ok = all(circle_in_area(circle) for circle in circles)

    at_intersections = []
    for index, target in enumerate(targets, start=1):
        hits = segment_motif_hits(airport, target, circles)
        at_intersections.append({"target": f"T{index}", "motifs": hits, "motif_count": len(hits)})
    all_three_at = [item for item in at_intersections if item["motif_count"] == 3]

    tt_counts = {"low_0_motifs": 0, "medium_1_motif": 0, "high_2_or_3_motifs": 0}
    tt_examples: list[dict[str, object]] = []
    for i, a in enumerate(targets, start=1):
        for j, b in enumerate(targets[i:], start=i + 1):
            hits = segment_motif_hits(a, b, circles)
            if len(hits) == 0:
                tt_counts["low_0_motifs"] += 1
            elif len(hits) == 1:
                tt_counts["medium_1_motif"] += 1
            else:
                tt_counts["high_2_or_3_motifs"] += 1
            if len(tt_examples) < 12 and (len(hits) == 0 or len(hits) >= 2):
                tt_examples.append({"pair": [f"T{i}", f"T{j}"], "motifs": hits, "motif_count": len(hits)})

    boundary_candidates = []
    for boundary_y in (5.0, 145.0):
        for index, target in enumerate(targets, start=1):
            path = [airport, Point(airport.x, boundary_y), Point(target.x, boundary_y), target]
            direct = dist(airport, target)
            boundary_candidates.append(
                {
                    "target": f"T{index}",
                    "boundary_y_km": boundary_y,
                    "length_ratio_vs_direct": round(path_length(path) / direct, 6),
                    "collision_free": polyline_clear_of_circles(path, circles),
                }
            )
    boundary_ratios = [item["length_ratio_vs_direct"] for item in boundary_candidates]
    boundary_collision_free = sum(1 for item in boundary_candidates if item["collision_free"])
    boundary_metrics = {
        "tested_boundary_polylines": len(boundary_candidates),
        "collision_free_boundary_polylines": boundary_collision_free,
        "min_length_ratio_vs_direct": round(min(boundary_ratios), 6),
        "mean_length_ratio_vs_direct": round(sum(boundary_ratios) / len(boundary_ratios), 6),
        "passes_no_obvious_dominating_bypass_screen": min(boundary_ratios) >= 1.45 and sum(boundary_ratios) / len(boundary_ratios) >= 1.9 and boundary_collision_free < len(boundary_candidates),
        "candidates": boundary_candidates,
    }

    connectivity = independent_connectivity(airport, targets, circles)

    motif_membership = [
        {
            "nfz_id": circle.id,
            "motif": circle.motif,
            "cluster": circle.cluster,
            "local_center_km": {"x": circle.center.x, "y": circle.center.y},
            "radius_km": circle.radius,
        }
        for circle in circles
    ]

    metrics = {
        "workspace_km": {"width": AREA_SIZE, "height": AREA_SIZE},
        "airport_local_km": {"x": airport.x, "y": airport.y},
        "target_local_km": [{"id": f"T{index}", "x": point.x, "y": point.y} for index, point in enumerate(targets, start=1)],
        "min_cross_motif_circle_gap_km": round(min(cross_motif_gaps), 6),
        "wrapped_region_count": len(wrapped_hulls),
        "min_wrapped_region_gap_km": round(min(wrapped_region_distances), 6),
        "min_target_spacing_km": round(min(target_spacings), 6),
        "min_target_circle_clearance_km": round(min(target_circle_clearances), 6),
        "min_target_wrapped_hull_clearance_km": round(min(target_hull_clearances), 6),
        "airport_circle_clearance_km": round(airport_circle_clearance, 6),
        "airport_wrapped_hull_clearance_km": round(airport_hull_clearance, 6),
        "c_trap": {
            "radii_counts": c_radii_counts,
            "mouth_distance_km": round(c_mouth_distance, 6),
            "bbox_km": [round(value, 6) for value in c_box],
            "adjacent_partial_overlaps": c_adjacent,
        },
        "sequential_staggered_blocking": {
            "pair_orientations_degrees": [round(value, 6) for value in sequential_orientations],
            "wrapped_hull_gaps_km": [round(value, 6) for value in sequential_gaps],
            "cluster_center_y_km": [round(value, 6) for value in sequential_centers_y],
            "pattern": "low/high/low mirror of high/low/high",
        },
        "asymmetric_corridor": {
            "upper_cluster_count": len(asym_upper),
            "lower_cluster_count": len(asym_lower),
            "corridor_gap_km": round(asym_corridor_gap, 6),
            "x_overlap_km": round(asym_x_overlap, 6),
            "corridor_probe_clear": corridor_probe,
        },
        "airport_target_intersections": at_intersections,
        "target_target_obstruction_counts": tt_counts,
        "target_target_examples": tt_examples,
        "boundary_bypass": boundary_metrics,
        "connectivity": connectivity,
    }

    checks = [
        {"id": 1, "name": "total NFZ count = 16", "passed": len(circles) == 16, "detail": str(len(circles))},
        {"id": 2, "name": "C-Trap NFZ count = 5", "passed": len(by_motif["C-Trap"]) == 5, "detail": str(len(by_motif["C-Trap"]))},
        {"id": 3, "name": "Sequential NFZ count = 6", "passed": len(by_motif["Sequential Staggered Blocking"]) == 6, "detail": str(len(by_motif["Sequential Staggered Blocking"]))},
        {"id": 4, "name": "Asymmetric Corridor NFZ count = 5", "passed": len(by_motif["Asymmetric Corridor"]) == 5, "detail": str(len(by_motif["Asymmetric Corridor"]))},
        {"id": 5, "name": "each motif satisfies structural rules", "passed": c_structural and sequential_structural and asym_structural, "detail": f"c_trap={c_structural}; sequential={sequential_structural}; asymmetric={asym_structural}"},
        {"id": 6, "name": "motifs remain distinct", "passed": min(cross_motif_gaps) > 0.0 and len(wrapped_hulls) >= 4, "detail": f"min_cross_motif_gap_km={min(cross_motif_gaps):.6f}; wrapped_regions={len(wrapped_hulls)}"},
        {"id": 7, "name": "no cross-motif circle overlap", "passed": min(cross_motif_gaps) > 0.0, "detail": f"min_cross_motif_gap_km={min(cross_motif_gaps):.6f}"},
        {"id": 8, "name": "multiple wrapped regions after clustering/wrapping", "passed": len(wrapped_hulls) > 1, "detail": f"wrapped_regions={len(wrapped_hulls)}"},
        {"id": 9, "name": "airport outside NFZs", "passed": airport_circle_clearance > 0.0 and airport_hull_clearance > TARGET_HULL_CLEARANCE, "detail": f"circle_clearance={airport_circle_clearance:.6f}; hull_clearance={airport_hull_clearance:.6f}"},
        {"id": 10, "name": "all targets outside NFZs", "passed": min(target_circle_clearances) >= TARGET_CIRCLE_CLEARANCE and min(target_hull_clearances) >= TARGET_HULL_CLEARANCE, "detail": f"circle_clearance={min(target_circle_clearances):.6f}; hull_clearance={min(target_hull_clearances):.6f}"},
        {"id": 11, "name": "target spacing >= 15 km", "passed": min(target_spacings) >= TARGET_SPACING, "detail": f"min_spacing={min(target_spacings):.6f}"},
        {"id": 12, "name": "target-circle clearance >= 2 km", "passed": min(target_circle_clearances) >= TARGET_CIRCLE_CLEARANCE, "detail": f"min_clearance={min(target_circle_clearances):.6f}"},
        {"id": 13, "name": "target-hull clearance >= 1 km", "passed": min(target_hull_clearances) >= TARGET_HULL_CLEARANCE, "detail": f"min_clearance={min(target_hull_clearances):.6f}"},
        {"id": 14, "name": "workspace bounds respected", "passed": in_area(airport, 0.0) and target_bounds_ok and circle_bounds_ok, "detail": f"airport={in_area(airport, 0.0)}; targets={target_bounds_ok}; circles={circle_bounds_ok}"},
        {"id": 15, "name": "t04 targets preserved in t08/t12", "passed": payload_invariants["t04_preserved_in_t08_and_t12"], "detail": str(payload_invariants["t04_preserved_in_t08_and_t12"])},
        {"id": 16, "name": "t08 targets preserved in t12", "passed": payload_invariants["t08_preserved_in_t12"], "detail": str(payload_invariants["t08_preserved_in_t12"])},
        {"id": 17, "name": "NFZ geometry identical across t04/t08/t12", "passed": payload_invariants["nfz_geometry_identical"], "detail": str(payload_invariants["nfz_geometry_identical"])},
        {"id": 18, "name": "airport identical across t04/t08/t12", "passed": payload_invariants["airport_identical"], "detail": str(payload_invariants["airport_identical"])},
        {"id": 19, "name": "some airport-target segments interact with all three motif regions", "passed": len(all_three_at) >= 2, "detail": f"all_three_count={len(all_three_at)}"},
        {"id": 20, "name": "target-target mixture low/medium/high obstruction", "passed": all(value > 0 for value in tt_counts.values()), "detail": json.dumps(tt_counts, sort_keys=True)},
        {"id": 21, "name": "no obvious boundary bypass dominates", "passed": boundary_metrics["passes_no_obvious_dominating_bypass_screen"], "detail": f"min_ratio={boundary_metrics['min_length_ratio_vs_direct']}; mean_ratio={boundary_metrics['mean_length_ratio_vs_direct']}; collision_free={boundary_collision_free}/{len(boundary_candidates)}"},
        {"id": 22, "name": "geometric free-space connection remains possible", "passed": bool(connectivity.get("all_targets_reachable")), "detail": f"all_targets_reachable={connectivity.get('all_targets_reachable')}; visited_nodes={connectivity.get('visited_free_nodes')}"},
    ]

    return {
        "topology_name": TOPOLOGY_NAME,
        "topology_stem": TOPOLOGY_STEM,
        "seed": SEED,
        "dataset_files": [f"{TOPOLOGY_STEM}_{FAMILY_INDEX:03d}_t{target_count:02d}.json" for target_count in (4, 8, 12)],
        "motif_membership": motif_membership,
        "checks": checks,
        "metrics": metrics,
        "overall_passed": all(check["passed"] for check in checks),
        "notes": [
            "NFZ is the conceptual obstacle term used by this dataset family.",
            "The native NFZ-aware mission schema field `sams` is preserved literally for compatibility.",
            "No benchmark planner or matrix method is used for generation or validation.",
            "Connectivity is checked by an independent geometric occupancy-grid search only.",
            "No geometric stress score was used for candidate ranking; this is a single deterministic candidate.",
        ],
    }


def write_dataset(payloads: dict[int, dict[str, object]]) -> list[Path]:
    paths = []
    for target_count, payload in payloads.items():
        path = DATASET_DIR / f"{TOPOLOGY_STEM}_{FAMILY_INDEX:03d}_t{target_count:02d}.json"
        write_json(path, payload)
        paths.append(path)
    return paths


def write_previews(airport: Point, circles: tuple[Circle, ...], targets: tuple[Point, ...]) -> list[Path]:
    colors = {
        "C-Trap": "#d95f02",
        "Sequential Staggered Blocking": "#1b9e77",
        "Asymmetric Corridor": "#7570b3",
    }
    paths: list[Path] = []
    scale = 4.0
    size = int(AREA_SIZE * scale)

    def sx(x: float) -> float:
        return x * scale

    def sy(y: float) -> float:
        return (AREA_SIZE - y) * scale

    for target_count in (4, 8, 12):
        target_subset = targets[:target_count]
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">',
            '<rect width="100%" height="100%" fill="#f8fafc"/>',
            f'<rect x="0" y="0" width="{size}" height="{size}" fill="none" stroke="#334155" stroke-width="2"/>',
        ]
        for value in range(0, 151, 25):
            parts.append(f'<line x1="{sx(value):.2f}" y1="0" x2="{sx(value):.2f}" y2="{size}" stroke="#d8dee9" stroke-width="1"/>')
            parts.append(f'<line x1="0" y1="{sy(value):.2f}" x2="{size}" y2="{sy(value):.2f}" stroke="#d8dee9" stroke-width="1"/>')
        for circle in circles:
            color = colors[circle.motif]
            parts.append(f'<circle cx="{sx(circle.center.x):.2f}" cy="{sy(circle.center.y):.2f}" r="{circle.radius * scale:.2f}" fill="{color}" fill-opacity="0.25" stroke="{color}" stroke-width="2"/>')
            parts.append(f'<text x="{sx(circle.center.x):.2f}" y="{sy(circle.center.y):.2f}" text-anchor="middle" dominant-baseline="central" font-family="Arial" font-size="10" fill="#0f172a">{circle.id}</text>')
        parts.append(f'<rect x="{sx(airport.x) - 5:.2f}" y="{sy(airport.y) - 5:.2f}" width="10" height="10" fill="#111827"/>')
        parts.append(f'<text x="{sx(airport.x) + 7:.2f}" y="{sy(airport.y) - 7:.2f}" font-family="Arial" font-size="12" fill="#111827">A1</text>')
        for index, target in enumerate(target_subset, start=1):
            parts.append(f'<circle cx="{sx(target.x):.2f}" cy="{sy(target.y):.2f}" r="4.5" fill="#0ea5e9" stroke="#0369a1" stroke-width="1.5"/>')
            parts.append(f'<text x="{sx(target.x) + 6:.2f}" y="{sy(target.y) - 6:.2f}" font-family="Arial" font-size="12" fill="#075985">T{index}</text>')
        parts.append('<text x="12" y="22" font-family="Arial" font-size="16" fill="#0f172a">Composite Adversarial NFZ family</text>')
        parts.append(f'<text x="12" y="42" font-family="Arial" font-size="13" fill="#334155">t{target_count:02d}: {target_count} cumulative targets, 16 NFZs</text>')
        parts.append("</svg>")
        path = PREVIEW_DIR / f"{TOPOLOGY_STEM}_{FAMILY_INDEX:03d}_t{target_count:02d}.svg"
        path.write_text("\n".join(parts) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def write_validation_markdown(validation: dict[str, object], hash_ok: bool) -> None:
    checks = validation["checks"]
    metrics = validation["metrics"]
    lines = [
        "# Composite Adversarial NFZ Validation",
        "",
        f"Topology: {validation['topology_name']} (`{validation['topology_stem']}`)",
        f"Seed: {validation['seed']}",
        "Native NFZ-aware mission compatibility preserves the literal JSON field `sams`.",
        "No benchmark planner or matrix method was run.",
        "",
        "## Required Checks",
        "",
        "| # | Check | Result | Detail |",
        "|---|---|---|---|",
    ]
    for check in checks:
        result = "PASS" if check["passed"] else "FAIL"
        lines.append(f"| {check['id']} | {check['name']} | {result} | {check['detail']} |")

    lines.extend([
        "",
        "## Motif Membership",
        "",
        "| NFZ | Motif | Cluster | Center x km | Center y km | Radius km |",
        "|---|---|---|---:|---:|---:|",
    ])
    for item in validation["motif_membership"]:
        center = item["local_center_km"]
        lines.append(f"| {item['nfz_id']} | {item['motif']} | {item['cluster']} | {center['x']:.3f} | {center['y']:.3f} | {item['radius_km']} |")

    lines.extend([
        "",
        "## Key Metrics",
        "",
        f"- Wrapped region count: {metrics['wrapped_region_count']}",
        f"- Minimum cross-motif circle gap: {metrics['min_cross_motif_circle_gap_km']} km",
        f"- Minimum wrapped-region gap: {metrics['min_wrapped_region_gap_km']} km",
        f"- Minimum target spacing: {metrics['min_target_spacing_km']} km",
        f"- Minimum target-to-circle clearance: {metrics['min_target_circle_clearance_km']} km",
        f"- Minimum target-to-wrapped-hull clearance: {metrics['min_target_wrapped_hull_clearance_km']} km",
        f"- Airport-target rays hitting all three motifs: {sum(1 for item in metrics['airport_target_intersections'] if item['motif_count'] == 3)}",
        f"- Target-target obstruction mix: {json.dumps(metrics['target_target_obstruction_counts'], sort_keys=True)}",
        f"- Boundary bypass screen: {json.dumps(metrics['boundary_bypass'], sort_keys=True)}",
        f"- Independent connectivity all targets reachable: {metrics['connectivity']['all_targets_reachable']}",
        f"- Original dataset hash verification: {'byte-identical' if hash_ok else 'MISMATCH'}",
        "",
        "## Coupling Summary",
        "",
        "The C-Trap opening faces the airport and has a smaller lower terminal NFZ, making the lower-side escape geometrically attractive. The first sequential pair is placed immediately downstream on that lower side, so the C-Trap escape interacts with the first staggered blocker instead of continuing unobstructed.",
        "",
        "The sequential pattern is a low/high/low mirror of the established high/low/high motif. The final low blocker redirects continuation back upward, while the asymmetric corridor's clear throat is centered lower than that exit and under an upper three-NFZ cluster, creating poor alignment at the corridor entrance without sealing it.",
        "",
        "The validation uses geometry only: circle and wrapped-hull intersections, clearances, boundary-bypass screening, and an independent occupancy-grid connectivity check.",
    ])
    VALIDATION_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_readme(validation: dict[str, object]) -> None:
    metrics = validation["metrics"]
    lines = [
        "# Composite Adversarial NFZ Dataset Family",
        "",
        "This directory contains a separate fourth benchmark-topology candidate. It does not modify or replace the existing benchmark datasets.",
        "",
        f"- Topology name: {TOPOLOGY_NAME}",
        f"- File stem: `{TOPOLOGY_STEM}`",
        f"- Seed: `{SEED}`",
        f"- Workspace: {AREA_SIZE:.0f} km x {AREA_SIZE:.0f} km local Cartesian, converted to native lat/lng at JSON output time",
        "- Native NFZ-aware mission schema: `nfz_env_v1`; the literal field `sams` is retained for compatibility",
        "- Outputs: `dataset/composite_adversarial_001_t04.json`, `dataset/composite_adversarial_001_t08.json`, `dataset/composite_adversarial_001_t12.json`",
        "",
        "## Motifs",
        "",
        "The layout contains 16 total NFZs:",
        "",
        "- C-Trap: NFZ01-NFZ05, one connected C-like overlapping chain with an open mouth facing A1.",
        "- Sequential Staggered Blocking: NFZ06-NFZ11, three separate overlapping two-NFZ clusters in a low/high/low mirror of the existing high/low/high motif.",
        "- Asymmetric Corridor: NFZ12-NFZ16, an opposing upper three-NFZ cluster and lower two-NFZ cluster with a traversable asymmetric corridor.",
        "",
        "## Coupling Intent",
        "",
        "The motifs are not independent samples pasted onto one map. A1 faces the C-Trap opening. The C-Trap geometry makes the lower-side escape comparatively natural, and the first sequential blocker is placed on that lower downstream side. The sequential low/high/low pattern then causes alternating lateral redirection, leaving the route poorly aligned with the asymmetric corridor throat, which sits below the upper three-NFZ cluster.",
        "",
        "The motifs remain recognizable and distinct. Cross-motif circles do not overlap, and overlap-cluster wrapping yields multiple wrapped regions rather than one collapsed obstacle.",
        "",
        "## Targets",
        "",
        "Targets are cumulative:",
        "",
        "- t04 contains T1-T4.",
        "- t08 preserves T1-T4 exactly and adds T5-T8.",
        "- t12 preserves T1-T8 exactly and adds T9-T12.",
        "",
        f"Minimum target spacing is {metrics['min_target_spacing_km']} km. Minimum target-to-circle clearance is {metrics['min_target_circle_clearance_km']} km. Minimum target-to-wrapped-hull clearance is {metrics['min_target_wrapped_hull_clearance_km']} km.",
        "",
        "## Validation",
        "",
        "Validation artifacts are under `validation/`:",
        "",
        "- `composite_adversarial_validation.json`",
        "- `composite_adversarial_validation.md`",
        "- `original_dataset_hashes_before.json`",
        "- `original_dataset_hashes_after.json`",
        "- `previews/composite_adversarial_001_t04.svg`",
        "- `previews/composite_adversarial_001_t08.svg`",
        "- `previews/composite_adversarial_001_t12.svg`",
        "",
        "No benchmark method, planner, route optimizer, method runtime, route length, or branch-count result is used to generate, rank, or validate this dataset. No geometric stress score was used for candidate ranking; the generator emits one deterministic geometric candidate and validates it.",
        "",
        "The free-space check is an independent 1 km occupancy-grid connectivity screen. It confirms that every target has a reachable free-space connection from A1 without invoking any benchmark planner.",
    ]
    README_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    before_hashes = ensure_before_hashes()
    airport, circles, targets = build_layout()
    payloads = {target_count: build_environment(airport, circles, targets, target_count) for target_count in (4, 8, 12)}
    validation = make_validation(airport, circles, targets, payloads)
    if not validation["overall_passed"]:
        failed = [check for check in validation["checks"] if not check["passed"]]
        write_json(VALIDATION_JSON_PATH, validation)
        raise SystemExit(f"validation failed: {failed}")

    dataset_paths = write_dataset(payloads)
    preview_paths = write_previews(airport, circles, targets)

    after_hashes = original_dataset_hashes()
    hash_ok, hash_comparisons = compare_hashes(before_hashes, after_hashes)
    after_hashes["matches_before"] = hash_ok
    after_hashes["comparisons"] = hash_comparisons
    write_json(AFTER_HASH_PATH, after_hashes)
    validation["original_dataset_hash_verification"] = {
        "byte_identical": hash_ok,
        "before_manifest": str(BEFORE_HASH_PATH),
        "after_manifest": str(AFTER_HASH_PATH),
        "comparisons": hash_comparisons,
    }
    validation["created_files"] = [str(path.relative_to(ROOT)) for path in dataset_paths + preview_paths] + [
        str(VALIDATION_JSON_PATH.relative_to(ROOT)),
        str(VALIDATION_MD_PATH.relative_to(ROOT)),
        str(AFTER_HASH_PATH.relative_to(ROOT)),
        str(README_PATH.relative_to(ROOT)),
    ]
    write_json(VALIDATION_JSON_PATH, validation)
    write_validation_markdown(validation, hash_ok)
    write_readme(validation)

    if not hash_ok:
        raise SystemExit("original dataset hash mismatch detected")

    print(f"Wrote {len(dataset_paths)} dataset files")
    print(f"Wrote {len(preview_paths)} SVG previews")
    print(f"Validation passed: {validation['overall_passed']}")
    print(f"Original dataset byte-identical: {hash_ok}")
    for path in dataset_paths:
        print(path)


if __name__ == "__main__":
    main()
