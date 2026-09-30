"""Validate Part II generated t12 datasets and create static previews.

This script is dataset-only. It does not run benchmark methods, Proposed
diagnostics, or the mission solver.
"""

from __future__ import annotations

import csv
import hashlib
import html
import importlib.util
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENTS_ROOT = REPO_ROOT / "experiments"
PART2_ROOT = EXPERIMENTS_ROOT / "part2"
DATASET_ROOT = PART2_ROOT / "datasets" / "controlled_t12"
PREVIEW_ROOT = PART2_ROOT / "datasets" / "previews"
MANIFEST_ROOT = PART2_ROOT / "manifests"
CONFIG_PATH = PART2_ROOT / "config" / "part2_instances.json"
FROZEN_GENERATOR_PATH = (
    PART2_ROOT / "generator" / "dataset_creator_app" / "generate_dataset.py"
)
GENERATION_MANIFEST = MANIFEST_ROOT / "part2_generated_dataset_manifest.json"
PART1_CONTROLLED_ROOT = (
    EXPERIMENTS_ROOT / "main_benchmark_replications" / "run_02_20260810-015756"
    / "input_snapshot"
)

EXPECTED_INFRASTRUCTURE_COMMIT = "1163ae8164f9ffe7ad60dc8cfd1dd7cebcfca0ba"
FROZEN_GENERATOR_COMMIT = "5f26eb8a5119af9854a5d49de3f900821701a689"
ALLOWED_RADII = {1, 2, 5, 10, 15}
EPS = 1e-6

TOPOLOGY_OUTPUT = {
    "c_trap": {
        "subdir": "c_trap",
        "prefix": "ctrap",
        "display": "C-Trap",
        "part1": "c_trap_001_t12.json",
    },
    "sequential_staggered_blocking": {
        "subdir": "sequential_staggered_blocking",
        "prefix": "sequential",
        "display": "Sequential Staggered Blocking",
        "part1": "sequential_staggered_blocking_001_t12.json",
    },
    "asymmetric_corridor": {
        "subdir": "asymmetric_corridor",
        "prefix": "asymmetric",
        "display": "Asymmetric Corridor",
        "part1": "asymmetric_corridor_001_t12.json",
    },
}


@dataclass(frozen=True)
class NFZ:
    center: Any
    radius: int
    label: str


@dataclass
class EnvironmentGeometry:
    path: Path
    environment_id: str
    topology: str
    instance_id: str
    seed: int
    raw: Dict[str, Any]
    airport: Any
    targets: List[Tuple[str, Any]]
    nfzs: List[NFZ]
    components: List[List[int]]
    component_hulls: List[Tuple[Any, ...]]
    wrapped_regions: List[Tuple[Any, ...]]


def load_frozen_generator() -> Any:
    spec = importlib.util.spec_from_file_location(
        "part2_validation_frozen_generate_dataset", FROZEN_GENERATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {FROZEN_GENERATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


GEN = load_frozen_generator()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_text_lf(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def git_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def load_config() -> Dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def expected_environments(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for instance in config["instances"]:
        instance_id = str(instance["instance_id"])
        seed = int(instance["seed"])
        for topology in config["topologies"]:
            info = TOPOLOGY_OUTPUT[topology]
            environment_id = f"{info['prefix']}_{instance_id}_t12"
            rows.append(
                {
                    "topology": topology,
                    "display_topology": info["display"],
                    "instance_id": instance_id,
                    "seed": seed,
                    "environment_id": environment_id,
                    "path": DATASET_ROOT / info["subdir"] / f"{environment_id}.json",
                }
            )
    return rows


def native_point(record: Dict[str, Any]) -> Any:
    if "lat" in record and "lng" in record:
        return GEN.native_point({"lat": float(record["lat"]), "lng": float(record["lng"])})
    if "x" in record and "y" in record:
        return GEN.Point(float(record["x"]), float(record["y"]))
    raise ValueError(f"Unsupported point record: {record}")


def nfz_center(record: Dict[str, Any]) -> Any:
    center = record.get("center") or record.get("pos") or record.get("position")
    if isinstance(center, dict):
        return native_point(center)
    if isinstance(center, list) and len(center) >= 2:
        return GEN.Point(float(center[0]), float(center[1]))
    if "x" in record and "y" in record:
        return GEN.Point(float(record["x"]), float(record["y"]))
    raise ValueError(f"Unsupported NFZ record: {record}")


def nfz_radius(record: Dict[str, Any]) -> int:
    return int(record.get("range_km", record.get("range", record.get("radius"))))


def components_for_nfzs(nfzs: List[NFZ]) -> List[List[int]]:
    parent = list(range(len(nfzs)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i, j in combinations(range(len(nfzs)), 2):
        if GEN.dist(nfzs[i].center, nfzs[j].center) <= nfzs[i].radius + nfzs[j].radius + EPS:
            union(i, j)

    groups: Dict[int, List[int]] = {}
    for index in range(len(nfzs)):
        groups.setdefault(find(index), []).append(index)
    return sorted((sorted(value) for value in groups.values()), key=lambda item: item[0])


def hull_for_component(component: List[int], nfzs: List[NFZ]) -> Tuple[Any, ...]:
    circles = tuple(GEN.Circle(nfzs[index].center, nfzs[index].radius) for index in component)
    return GEN.cluster_hull(circles)


def wrapped_regions(nfzs: List[NFZ]) -> List[Tuple[Any, ...]]:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from path_planning_core import sam_wrapping

    wrapped, _ = sam_wrapping.wrap_sams(
        [
            {
                "x": nfz.center.x,
                "y": nfz.center.y,
                "range": nfz.radius,
                "id": nfz.label,
            }
            for nfz in nfzs
        ]
    )
    return [tuple(GEN.Point(float(x), float(y)) for x, y in region) for region in wrapped]


def load_environment(row: Dict[str, Any]) -> EnvironmentGeometry:
    path = row["path"]
    raw = json.loads(path.read_text(encoding="utf-8"))
    env = raw.get("env") if isinstance(raw.get("env"), dict) else raw
    airport_records = env.get("airports", [])
    target_records = env.get("targets", [])
    nfz_records = env.get("sams", [])
    airport = native_point(airport_records[0])
    targets = [
        (str(target.get("id", f"T{index}")), native_point(target))
        for index, target in enumerate(target_records, start=1)
    ]
    nfzs = [
        NFZ(
            center=nfz_center(nfz),
            radius=nfz_radius(nfz),
            label=str(nfz.get("id") or f"NFZ{index:02d}"),
        )
        for index, nfz in enumerate(nfz_records, start=1)
    ]
    components = components_for_nfzs(nfzs)
    component_hulls = [hull_for_component(component, nfzs) for component in components]
    return EnvironmentGeometry(
        path=path,
        environment_id=row["environment_id"],
        topology=row["topology"],
        instance_id=row["instance_id"],
        seed=row["seed"],
        raw=raw,
        airport=airport,
        targets=targets,
        nfzs=nfzs,
        components=components,
        component_hulls=component_hulls,
        wrapped_regions=wrapped_regions(nfzs),
    )


def min_pairwise_distance(points: Iterable[Any]) -> Optional[float]:
    values = [GEN.dist(a, b) for a, b in combinations(list(points), 2)]
    return min(values) if values else None


def point_to_nfz_clearance(point: Any, nfzs: List[NFZ]) -> float:
    return min(GEN.dist(point, nfz.center) - nfz.radius for nfz in nfzs)


def point_to_polygon_clearance(point: Any, polygons: List[Tuple[Any, ...]]) -> Optional[float]:
    if not polygons:
        return None
    clearances: List[float] = []
    for polygon in polygons:
        distance = GEN.polygon_boundary_distance(point, polygon)
        clearances.append(-distance if GEN.point_in_polygon(point, polygon) else distance)
    return min(clearances)


def polygon_gap(a: Tuple[Any, ...], b: Tuple[Any, ...]) -> float:
    return GEN.polygon_distance(a, b)


def min_region_separation(regions: List[Tuple[Any, ...]]) -> Optional[float]:
    if len(regions) < 2:
        return None
    return min(polygon_gap(a, b) for a, b in combinations(regions, 2))


def component_distribution(components: List[List[int]]) -> str:
    return "+".join(str(len(component)) for component in components)


def bbox_width_overlap(a: Tuple[Any, ...], b: Tuple[Any, ...]) -> float:
    a_box = GEN.bbox(a)
    b_box = GEN.bbox(b)
    return min(a_box[2], b_box[2]) - max(a_box[0], b_box[0])


def hull_gap_metrics(hulls: List[Tuple[Any, ...]]) -> Tuple[List[float], List[Tuple[Any, ...]]]:
    ordered = sorted(hulls, key=lambda hull: GEN.bbox(hull)[0])
    gaps = [
        GEN.bbox(ordered[index + 1])[0] - GEN.bbox(ordered[index])[2]
        for index in range(len(ordered) - 1)
    ]
    return gaps, ordered


def common_validation(geometry: EnvironmentGeometry) -> List[str]:
    errors: List[str] = []
    raw = geometry.raw
    env = raw.get("env") if isinstance(raw.get("env"), dict) else raw
    target_ids = [target_id for target_id, _ in geometry.targets]
    nfz_labels = [nfz.label for nfz in geometry.nfzs]

    if raw.get("schema") != "nfz_env_v1":
        errors.append("schema is not nfz_env_v1")
    if len(env.get("airports", [])) != 1:
        errors.append("airport count is not 1")
    if len(geometry.targets) != 12:
        errors.append("target count is not 12")
    if len(set(target_ids)) != len(target_ids):
        errors.append("target IDs are not unique")
    if len(set(nfz_labels)) != len(nfz_labels):
        errors.append("NFZ labels are not unique")
    if any(nfz.radius not in ALLOWED_RADII for nfz in geometry.nfzs):
        errors.append("NFZ radius outside approved set")
    if len(geometry.targets) + 1 != 13:
        errors.append("mission node count is not 13")
    if not GEN.in_area(geometry.airport, 2.0):
        errors.append("airport outside workspace margin")
    if not all(GEN.in_area(point, 2.0) for _, point in geometry.targets):
        errors.append("target outside workspace margin")
    if not all(
        GEN.circle_in_area(GEN.Circle(nfz.center, nfz.radius)) for nfz in geometry.nfzs
    ):
        errors.append("NFZ outside workspace bounds")

    min_spacing = min_pairwise_distance(point for _, point in geometry.targets)
    if min_spacing is None or min_spacing + EPS < GEN.TARGET_SPACING:
        errors.append("target spacing below 15 km")

    target_native_clearances = [
        point_to_nfz_clearance(point, geometry.nfzs) for _, point in geometry.targets
    ]
    if min(target_native_clearances) + EPS < GEN.TARGET_CIRCLE_CLEARANCE:
        errors.append("target-to-native-NFZ clearance below 2 km")

    target_generator_hull_clearances = [
        point_to_polygon_clearance(point, geometry.component_hulls)
        for _, point in geometry.targets
    ]
    if min(value for value in target_generator_hull_clearances if value is not None) + EPS < GEN.TARGET_HULL_CLEARANCE:
        errors.append("target-to-generator-hull clearance below 1 km")

    target_wrapped_clearances = [
        point_to_polygon_clearance(point, geometry.wrapped_regions)
        for _, point in geometry.targets
    ]
    if min(value for value in target_wrapped_clearances if value is not None) < -EPS:
        errors.append("target inside Proposed wrapped planning region")

    if point_to_nfz_clearance(geometry.airport, geometry.nfzs) + EPS < 1.0:
        errors.append("airport-to-native-NFZ clearance below 1 km")
    airport_hull_clearance = point_to_polygon_clearance(
        geometry.airport, geometry.component_hulls
    )
    if airport_hull_clearance is not None and airport_hull_clearance + EPS < GEN.TARGET_HULL_CLEARANCE:
        errors.append("airport-to-generator-hull clearance below 1 km")
    airport_wrapped_clearance = point_to_polygon_clearance(
        geometry.airport, geometry.wrapped_regions
    )
    if airport_wrapped_clearance is not None and airport_wrapped_clearance < -EPS:
        errors.append("airport inside Proposed wrapped planning region")

    return errors


def validate_c_trap(geometry: EnvironmentGeometry) -> Tuple[List[str], Dict[str, Any]]:
    errors: List[str] = []
    nfzs = geometry.nfzs
    metrics: Dict[str, Any] = {}
    if len(nfzs) != 5:
        errors.append("C-Trap NFZ count is not 5")
        return errors, metrics
    if sorted(len(component) for component in geometry.components) != [5]:
        errors.append("C-Trap components are not one connected five-NFZ structure")
    for index in range(4):
        if not GEN.partial_overlap(
            GEN.Circle(nfzs[index].center, nfzs[index].radius),
            GEN.Circle(nfzs[index + 1].center, nfzs[index + 1].radius),
        ):
            errors.append(f"C-Trap adjacent NFZ {index + 1}-{index + 2} does not partially overlap")
    for i, j in combinations(range(5), 2):
        if abs(i - j) <= 1:
            continue
        clearance = GEN.dist(nfzs[i].center, nfzs[j].center) - nfzs[i].radius - nfzs[j].radius
        if {i, j} == {0, 4}:
            metrics["opening_width_km"] = clearance
            if clearance <= 4.0 + EPS:
                errors.append("C-Trap mouth opening is not sufficiently open")
        elif clearance <= 0.75 + EPS:
            errors.append(f"C-Trap non-adjacent NFZ {i + 1}-{j + 1} spacing too small")
    mouth_mid = GEN.midpoint(nfzs[0].center, nfzs[4].center)
    airport_to_mouth = GEN.dist(geometry.airport, mouth_mid)
    airport_to_nose = GEN.dist(geometry.airport, nfzs[2].center)
    metrics["airport_to_mouth_mid_km"] = airport_to_mouth
    metrics["airport_to_c_trap_nose_km"] = airport_to_nose
    metrics["airport_faces_mouth"] = airport_to_mouth < airport_to_nose
    if airport_to_mouth >= airport_to_nose:
        errors.append("C-Trap airport does not face mouth side")
    return errors, metrics


def validate_sequential(geometry: EnvironmentGeometry) -> Tuple[List[str], Dict[str, Any]]:
    errors: List[str] = []
    nfzs = geometry.nfzs
    metrics: Dict[str, Any] = {}
    if len(nfzs) != 6:
        errors.append("Sequential NFZ count is not 6")
        return errors, metrics
    if sorted(len(component) for component in geometry.components) != [2, 2, 2]:
        errors.append("Sequential components are not three separate two-NFZ clusters")
    pair_hulls = []
    pair_center_ys = []
    for pair_index in range(3):
        left = pair_index * 2
        pair = nfzs[left : left + 2]
        if not GEN.partial_overlap(
            GEN.Circle(pair[0].center, pair[0].radius),
            GEN.Circle(pair[1].center, pair[1].radius),
        ):
            errors.append(f"Sequential pair {pair_index + 1} does not partially overlap")
        pair_hulls.append(hull_for_component([left, left + 1], nfzs))
        pair_center_ys.append((pair[0].center.y + pair[1].center.y) / 2.0)
    gaps, _ordered = hull_gap_metrics(pair_hulls)
    metrics["inter_cluster_gap_km"] = ";".join(f"{value:.6f}" for value in gaps)
    if len(gaps) != 2 or any(value < 6.0 - EPS or value > 12.0 + EPS for value in gaps):
        errors.append("Sequential inter-hull gap outside 6-12 km")
    signs = [1 if value > 75.0 else -1 for value in pair_center_ys]
    metrics["alternating_stagger_pattern"] = ",".join("high" if sign > 0 else "low" for sign in signs)
    if not (signs[0] == signs[2] and signs[0] == -signs[1]):
        errors.append("Sequential alternating stagger pattern not preserved")
    return errors, metrics


def validate_asymmetric(geometry: EnvironmentGeometry) -> Tuple[List[str], Dict[str, Any]]:
    errors: List[str] = []
    metrics: Dict[str, Any] = {}
    if len(geometry.nfzs) != 5:
        errors.append("Asymmetric Corridor NFZ count is not 5")
        return errors, metrics
    component_sizes = sorted(len(component) for component in geometry.components)
    if component_sizes != [2, 3]:
        errors.append("Asymmetric Corridor components are not opposing 2-NFZ and 3-NFZ groups")
    if len(geometry.component_hulls) == 2:
        gap = polygon_gap(geometry.component_hulls[0], geometry.component_hulls[1])
        x_overlap = bbox_width_overlap(geometry.component_hulls[0], geometry.component_hulls[1])
        metrics["corridor_gap_km"] = gap
        metrics["opposing_group_x_overlap_km"] = x_overlap
        if gap < 8.0 - EPS or gap > 30.0 + EPS:
            errors.append("Asymmetric Corridor gap outside 8-30 km")
        if x_overlap < 20.0 - EPS:
            errors.append("Asymmetric Corridor opposing groups lack required x-overlap")
    return errors, metrics


def topology_validation(geometry: EnvironmentGeometry) -> Tuple[List[str], Dict[str, Any]]:
    if geometry.topology == "c_trap":
        return validate_c_trap(geometry)
    if geometry.topology == "sequential_staggered_blocking":
        return validate_sequential(geometry)
    if geometry.topology == "asymmetric_corridor":
        return validate_asymmetric(geometry)
    return [f"Unsupported topology {geometry.topology}"], {}


def geometry_signature(geometry: EnvironmentGeometry) -> Tuple[Any, ...]:
    airport = (round(geometry.airport.x, 9), round(geometry.airport.y, 9))
    nfzs = tuple(
        (round(nfz.center.x, 9), round(nfz.center.y, 9), nfz.radius)
        for nfz in geometry.nfzs
    )
    targets = tuple(
        (target_id, round(point.x, 9), round(point.y, 9))
        for target_id, point in geometry.targets
    )
    return airport, nfzs, targets


def part1_signature(topology: str) -> Optional[Tuple[Any, ...]]:
    path = PART1_CONTROLLED_ROOT / TOPOLOGY_OUTPUT[topology]["part1"]
    if not path.exists():
        return None
    row = {
        "topology": topology,
        "instance_id": "part1",
        "seed": 20260808,
        "environment_id": path.stem,
        "path": path,
    }
    return geometry_signature(load_environment(row))


def metric_row(geometry: EnvironmentGeometry) -> Dict[str, Any]:
    target_points = [point for _, point in geometry.targets]
    target_to_native = [point_to_nfz_clearance(point, geometry.nfzs) for point in target_points]
    target_to_wrapped = [
        point_to_polygon_clearance(point, geometry.wrapped_regions) for point in target_points
    ]
    airport_coords = f"{geometry.airport.x:.6f},{geometry.airport.y:.6f}"
    return {
        "environment_id": geometry.environment_id,
        "topology": geometry.topology,
        "instance_id": geometry.instance_id,
        "seed": geometry.seed,
        "target_count": len(geometry.targets),
        "nfz_count": len(geometry.nfzs),
        "airport_coordinates_km": airport_coords,
        "native_component_count": len(geometry.components),
        "component_size_distribution": component_distribution(geometry.components),
        "singleton_component_count": sum(1 for component in geometry.components if len(component) == 1),
        "multi_nfz_component_count": sum(1 for component in geometry.components if len(component) > 1),
        "wrapped_region_count": len(geometry.wrapped_regions),
        "min_target_target_spacing_km": min_pairwise_distance(target_points),
        "min_target_to_native_nfz_clearance_km": min(target_to_native),
        "min_target_to_wrapped_hull_clearance_km": min(
            value for value in target_to_wrapped if value is not None
        ),
        "min_separation_between_wrapped_regions_km": min_region_separation(geometry.wrapped_regions),
    }


def draw_environment_svg(
    geometry: EnvironmentGeometry,
    path: Path,
    *,
    show_wrapped_regions: bool,
    width: int = 900,
    height: int = 920,
) -> None:
    panel = svg_panel(
        geometry,
        x0=40,
        y0=60,
        size=800,
        show_wrapped_regions=show_wrapped_regions,
        title=f"{geometry.environment_id} validation preview",
    )
    legend = [
        '<text x="40" y="890" font-size="16">Blue triangle: airport. Green circles: targets. Red rings: native NFZ boundaries. Orange dashed polygons: wrapped regions.</text>'
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_lf(
        path,
        "\n".join(
            [
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
                '<rect width="100%" height="100%" fill="white"/>',
                *panel,
                *legend,
                "</svg>",
            ]
        )
        + "\n",
    )


def svg_panel(
    geometry: EnvironmentGeometry,
    *,
    x0: float,
    y0: float,
    size: float,
    show_wrapped_regions: bool,
    title: str,
) -> List[str]:
    scale = size / GEN.AREA_SIZE

    def tx(point: Any) -> float:
        return x0 + point.x * scale

    def ty(point: Any) -> float:
        return y0 + size - point.y * scale

    lines: List[str] = []
    lines.append(
        f'<text x="{x0}" y="{y0 - 22}" font-size="16" font-weight="bold">{html.escape(title)}</text>'
    )
    lines.append(
        f'<rect x="{x0}" y="{y0}" width="{size}" height="{size}" fill="#fbfbfb" stroke="#111" stroke-width="1.5"/>'
    )
    if show_wrapped_regions:
        for index, region in enumerate(geometry.wrapped_regions, start=1):
            points = " ".join(f"{tx(point):.3f},{ty(point):.3f}" for point in region)
            lines.append(
                f'<polygon points="{points}" fill="#f59e0b22" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="6 4"/>'
            )
            centroid_x = sum(point.x for point in region) / len(region)
            centroid_y = sum(point.y for point in region) / len(region)
            lines.append(
                f'<text x="{x0 + centroid_x * scale:.3f}" y="{y0 + size - centroid_y * scale:.3f}" font-size="11" fill="#9a3412">WR{index}</text>'
            )
    for index, nfz in enumerate(geometry.nfzs, start=1):
        lines.append(
            f'<circle cx="{tx(nfz.center):.3f}" cy="{ty(nfz.center):.3f}" r="{nfz.radius * scale:.3f}" fill="#dc262611" stroke="#dc2626" stroke-width="1.5"/>'
        )
        lines.append(
            f'<text x="{tx(nfz.center) + 4:.3f}" y="{ty(nfz.center) - 4:.3f}" font-size="11" fill="#991b1b">NFZ{index}</text>'
        )
    airport = geometry.airport
    ax = tx(airport)
    ay = ty(airport)
    lines.append(
        f'<polygon points="{ax:.3f},{ay - 8:.3f} {ax - 8:.3f},{ay + 8:.3f} {ax + 8:.3f},{ay + 8:.3f}" fill="#2563eb" stroke="#1e3a8a" stroke-width="1"/>'
    )
    lines.append(
        f'<text x="{ax + 10:.3f}" y="{ay:.3f}" font-size="11" fill="#1e3a8a">A1</text>'
    )
    for target_id, point in geometry.targets:
        x = tx(point)
        y = ty(point)
        lines.append(
            f'<circle cx="{x:.3f}" cy="{y:.3f}" r="4.5" fill="#16a34a" stroke="#14532d" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{x + 5:.3f}" y="{y - 5:.3f}" font-size="10" fill="#14532d">{html.escape(target_id)}</text>'
        )
    return lines


def write_contact_sheet(
    topology: str,
    geometries: List[EnvironmentGeometry],
    path: Path,
) -> None:
    panel_size = 250
    gap = 24
    width = gap + len(geometries) * (panel_size + gap)
    height = panel_size + 110
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{gap}" y="30" font-size="20" font-weight="bold">{html.escape(TOPOLOGY_OUTPUT[topology]["display"])} Part II contact sheet</text>',
    ]
    for index, geometry in enumerate(geometries):
        x0 = gap + index * (panel_size + gap)
        lines.extend(
            svg_panel(
                geometry,
                x0=x0,
                y0=62,
                size=panel_size,
                show_wrapped_regions=True,
                title=f"{geometry.instance_id} seed {geometry.seed}",
            )
        )
    lines.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_lf(path, "\n".join(lines) + "\n")


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def validation_report(rows: List[Dict[str, Any]], path: Path) -> None:
    lines = [
        "# Part II Dataset Validation",
        "",
        "This report covers dataset generation and geometry validation only. No benchmark methods, Proposed diagnostics, or mission solver executions were run.",
        "",
        "| topology | instance | seed | NFZs | components | targets | min target spacing km | min NFZ clearance km | min wrapped-hull clearance km | topology | admissibility | independence |",
        "|---|---|---:|---:|---|---:|---:|---:|---:|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {topology_display} | {instance_id} | {seed} | {nfz_count} | {component_size_distribution} | {target_count} | {min_target_target_spacing_km:.6f} | {min_target_to_native_nfz_clearance_km:.6f} | {min_target_to_wrapped_hull_clearance_km:.6f} | {topology_validation} | {admissibility_validation} | {geometric_independence} |".format(
                **row
            )
        )
    topology_failures = [row for row in rows if row["topology_validation"] != "PASS"]
    admissibility_failures = [row for row in rows if row["admissibility_validation"] != "PASS"]
    duplicates = [row for row in rows if row["duplicate_geometry"]]
    part1_duplicates = [row for row in rows if row["part1_duplicate"]]
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Instances generated: `{len(rows)}`",
            f"- Topology failures: `{len(topology_failures)}`",
            f"- Admissibility failures: `{len(admissibility_failures)}`",
            f"- Duplicate Part II geometries: `{len(duplicates)}`",
            f"- Duplicates of Part I controlled geometry: `{len(part1_duplicates)}`",
            "- Topology degeneration observed: `NO`" if not topology_failures else "- Topology degeneration observed: `YES`",
            "- Seed failures: `NONE`" if not topology_failures and not admissibility_failures else "- Seed failures: `SEE TABLE`",
            "- Seed replacements performed: `NONE`",
            "",
            "## Preview Artifacts",
            "",
            "- Per-environment previews: `experiments/part2/datasets/previews/`",
            "- Contact sheets: `experiments/part2/datasets/previews/contact_sheet_*.svg`",
            "",
        ]
    )
    write_text_lf(path, "\n".join(lines))


def validate_all() -> int:
    config = load_config()
    generation_manifest = json.loads(GENERATION_MANIFEST.read_text(encoding="utf-8"))
    current_head = git_head()
    generated_at = generation_manifest.get("created_at")
    expected_rows = expected_environments(config)
    geometries = [load_environment(row) for row in expected_rows]

    part1_signatures = {
        topology: part1_signature(topology) for topology in TOPOLOGY_OUTPUT
    }
    signatures_by_topology: Dict[str, Dict[Tuple[Any, ...], List[str]]] = {}
    for geometry in geometries:
        signatures_by_topology.setdefault(geometry.topology, {}).setdefault(
            geometry_signature(geometry), []
        ).append(geometry.environment_id)

    summary_rows: List[Dict[str, Any]] = []
    manifest_rows: List[Dict[str, Any]] = []
    failures: List[str] = []

    for geometry in geometries:
        common_errors = common_validation(geometry)
        topology_errors, topology_metrics = topology_validation(geometry)
        signature = geometry_signature(geometry)
        duplicate_ids = [
            item
            for item in signatures_by_topology[geometry.topology][signature]
            if item != geometry.environment_id
        ]
        part1_duplicate = signature == part1_signatures.get(geometry.topology)

        row = metric_row(geometry)
        row.update(topology_metrics)
        row.update(
            {
                "topology_display": TOPOLOGY_OUTPUT[geometry.topology]["display"],
                "topology_validation": "PASS" if not topology_errors else "FAIL",
                "admissibility_validation": "PASS" if not common_errors else "FAIL",
                "topology_errors": "; ".join(topology_errors),
                "admissibility_errors": "; ".join(common_errors),
                "duplicate_geometry": ";".join(duplicate_ids),
                "part1_duplicate": part1_duplicate,
                "geometric_independence": "PASS" if not duplicate_ids and not part1_duplicate else "FAIL",
                "relative_path": geometry.path.relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256(geometry.path),
                "file_size_bytes": geometry.path.stat().st_size,
                "generation_timestamp": generated_at,
                "frozen_generator_source_commit": FROZEN_GENERATOR_COMMIT,
                "part2_infrastructure_commit": EXPECTED_INFRASTRUCTURE_COMMIT,
            }
        )
        summary_rows.append(row)
        manifest_rows.append(
            {
                "relative_path": row["relative_path"],
                "environment_id": row["environment_id"],
                "topology": row["topology"],
                "instance_id": row["instance_id"],
                "seed": row["seed"],
                "sha256": row["sha256"],
                "file_size_bytes": row["file_size_bytes"],
                "target_count": row["target_count"],
                "nfz_count": row["nfz_count"],
                "generation_timestamp": generated_at,
                "frozen_generator_source_commit": FROZEN_GENERATOR_COMMIT,
                "part2_infrastructure_commit": EXPECTED_INFRASTRUCTURE_COMMIT,
                "dataset_stage": "pre-benchmark Part II dataset",
            }
        )
        if topology_errors or common_errors or duplicate_ids or part1_duplicate:
            failures.append(geometry.environment_id)

        preview_dir = PREVIEW_ROOT / TOPOLOGY_OUTPUT[geometry.topology]["subdir"]
        draw_environment_svg(
            geometry,
            preview_dir / f"{geometry.environment_id}.svg",
            show_wrapped_regions=False,
        )
        draw_environment_svg(
            geometry,
            preview_dir / f"{geometry.environment_id}_wrapped.svg",
            show_wrapped_regions=True,
        )

    for topology in TOPOLOGY_OUTPUT:
        topology_geometries = [
            geometry for geometry in geometries if geometry.topology == topology
        ]
        write_contact_sheet(
            topology,
            topology_geometries,
            PREVIEW_ROOT / f"contact_sheet_{TOPOLOGY_OUTPUT[topology]['subdir']}.svg",
        )

    summary_fields = sorted(summary_rows[0])
    manifest_fields = [
        "relative_path",
        "environment_id",
        "topology",
        "instance_id",
        "seed",
        "sha256",
        "file_size_bytes",
        "target_count",
        "nfz_count",
        "generation_timestamp",
        "frozen_generator_source_commit",
        "part2_infrastructure_commit",
        "dataset_stage",
    ]
    write_csv(MANIFEST_ROOT / "part2_geometry_summary.csv", summary_rows, summary_fields)
    write_text_lf(
        MANIFEST_ROOT / "part2_geometry_summary.json",
        json.dumps(
            {
                "schema": "nfz_part2_geometry_summary_v1",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "part2_infrastructure_commit": EXPECTED_INFRASTRUCTURE_COMMIT,
                "validation_head": current_head,
                "rows": summary_rows,
            },
            indent=2,
            sort_keys=True,
        ),
    )
    write_csv(MANIFEST_ROOT / "part2_dataset_manifest.csv", manifest_rows, manifest_fields)
    write_text_lf(
        MANIFEST_ROOT / "part2_dataset_manifest.json",
        json.dumps(
            {
                "schema": "nfz_part2_dataset_manifest_v1",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "dataset_stage": "pre-benchmark Part II datasets",
                "frozen_generator_source_commit": FROZEN_GENERATOR_COMMIT,
                "part2_infrastructure_commit": EXPECTED_INFRASTRUCTURE_COMMIT,
                "mission_environment_count": len(manifest_rows),
                "rows": manifest_rows,
            },
            indent=2,
            sort_keys=True,
        ),
    )
    validation_report(summary_rows, PART2_ROOT / "datasets" / "PART2_DATASET_VALIDATION.md")

    print(f"validated_environment_count={len(summary_rows)}")
    print(f"failed_environment_count={len(failures)}")
    if failures:
        print("failed_environments=" + ",".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(validate_all())
