"""Generate Rev E publication figures for the NFZ benchmark manuscript.

This script is intentionally read-only with respect to benchmark inputs. It
creates vector figures and PNG previews under publication_figures_revE/.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Polygon


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from path_planning_core.latlng_utils import latlng_to_local_xy
from path_planning_core.sam_wrapping import _cluster_overlapping_sams, wrap_sams
from server.solver.projection import _project_env_to_local_km


OUTPUT_DIR = REPO_ROOT / "publication_figures_revE"

PART1_CONTROLLED_RUN = (
    REPO_ROOT / "experiments" / "main_benchmark_replications" / "run_02_20260810-015756"
)
PART1_COMPOSITE_RUN = (
    REPO_ROOT / "experiments" / "composite_adversarial_replications" / "run_02_20260809-222140"
)
PART2_DATASETS = REPO_ROOT / "experiments" / "part2" / "datasets" / "controlled_t12"
PART2_PRIMARY_RUN = (
    REPO_ROOT / "experiments" / "part2" / "results" / "primary" / "run_01_20260812-194711"
)

CONTROLLED_T12 = [
    (
        "c_trap_001_t12",
        "C-Trap",
        PART1_CONTROLLED_RUN
        / "input_snapshot"
        / "c_trap_001_t12.json",
        PART1_CONTROLLED_RUN / "outputs" / "proposed" / "missions",
    ),
    (
        "sequential_staggered_blocking_001_t12",
        "Sequential Staggered Blocking",
        PART1_CONTROLLED_RUN
        / "input_snapshot"
        / "sequential_staggered_blocking_001_t12.json",
        PART1_CONTROLLED_RUN / "outputs" / "proposed" / "missions",
    ),
    (
        "asymmetric_corridor_001_t12",
        "Asymmetric Corridor",
        PART1_CONTROLLED_RUN
        / "input_snapshot"
        / "asymmetric_corridor_001_t12.json",
        PART1_CONTROLLED_RUN / "outputs" / "proposed" / "missions",
    ),
]

COMPOSITE_T12 = (
    "composite_adversarial_001_t12",
    PART1_COMPOSITE_RUN / "input_snapshot" / "composite_adversarial_001_t12.json",
)

FIG4_METHODS = [
    ("proposed", "Proposed", True),
    ("visibility_graph", "Visibility Graph", False),
    ("grid_astar", "Grid A*", False),
    ("appatt_raw", "APPATT raw", False),
]

FIG6_METHODS = [
    ("appatt_raw", "APPATT raw"),
    ("appatt_bspline", "APPATT B-spline"),
    ("tig_raw", "TIG raw"),
    ("tig_bezier", "TIG Bezier"),
]

PART2_TOPOLOGIES = [
    ("c_trap", "C-Trap", "ctrap"),
    ("sequential_staggered_blocking", "Sequential Staggered Blocking", "sequential"),
    ("asymmetric_corridor", "Asymmetric Corridor", "asymmetric"),
]

ROUTE_COLORS = [
    "#20639b",
    "#3caea3",
    "#f6a01a",
    "#7b3f98",
    "#d1495b",
    "#4c78a8",
    "#59a14f",
]

NFZ_FILL = "#f5b041"
NFZ_EDGE = "#c87900"
HULL_EDGE = "#8e24aa"
HULL_FILL = "#8e24aa"
AIRPORT_COLOR = "#111111"
TARGET_COLOR = "#1f77b4"
ROUTE_COLOR = "#2f5597"


@dataclass(frozen=True)
class PanelData:
    doc: dict[str, Any]
    env_doc: dict[str, Any]
    projected_env: dict[str, Any]
    ref_lat: float
    ref_lng: float
    source_path: Path
    mission_path: Path | None


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_env(doc: dict[str, Any]) -> dict[str, Any]:
    if isinstance(doc.get("env"), dict):
        return doc["env"]
    return doc


def method_mission_path(run_dir: Path, method: str, stem: str) -> Path:
    matches = sorted((run_dir / "outputs" / method / "missions").glob(f"{stem}__{method}__*.json"))
    if not matches:
        raise FileNotFoundError(f"No mission output found for {method}: {stem}")
    if len(matches) > 1:
        raise RuntimeError(f"Ambiguous mission outputs for {method}: {stem}: {matches}")
    return matches[0]


def controlled_proposed_path(missions_dir: Path, stem: str) -> Path:
    matches = sorted(missions_dir.glob(f"{stem}__proposed__*.json"))
    if not matches:
        raise FileNotFoundError(f"No Proposed controlled mission output found for {stem}")
    if len(matches) > 1:
        raise RuntimeError(f"Ambiguous Proposed controlled mission output for {stem}: {matches}")
    return matches[0]


def part2_proposed_path(dataset_path: Path) -> Path | None:
    stem = dataset_path.stem
    matches = sorted(
        (PART2_PRIMARY_RUN / "outputs" / "proposed" / "missions").glob(f"{stem}__proposed__*.json")
    )
    if not matches:
        return None
    if len(matches) > 1:
        raise RuntimeError(f"Ambiguous Part II Proposed output for {stem}: {matches}")
    return matches[0]


def load_panel(source_path: Path, mission_path: Path | None = None) -> PanelData:
    env_doc = load_json(source_path)
    doc = load_json(mission_path) if mission_path else env_doc
    projected_env, ref_lat, ref_lng = _project_env_to_local_km(extract_env(env_doc))
    return PanelData(doc, env_doc, projected_env, ref_lat, ref_lng, source_path, mission_path)


def display_nfz_label(raw_label: Any, index: int) -> str:
    fallback = f"NFZ{index + 1}"
    if raw_label in (None, ""):
        return fallback
    value = str(raw_label)
    value = re.sub(r"^sam(?=$|[\d_\-])", "NFZ", value, flags=re.IGNORECASE)
    if value.lower().startswith("sam"):
        return fallback
    return value


def as_local_point(point: Any, ref_lat: float, ref_lng: float) -> tuple[float, float] | None:
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        return None
    try:
        a = float(point[0])
        b = float(point[1])
    except (TypeError, ValueError):
        return None
    if -90.0 <= a <= 90.0 and -180.0 <= b <= 180.0 and abs(b) > 20.0:
        x, y = latlng_to_local_xy(a, b, ref_lat, ref_lng)
        return float(x), float(y)
    return a, b


def trajectory_points(route: dict[str, Any], panel: PanelData) -> list[tuple[float, float]]:
    candidates = [
        route.get("trajectory"),
        route.get("path"),
        route.get("points"),
        route.get("waypoints"),
    ]
    for candidate in candidates:
        if isinstance(candidate, list) and candidate:
            points = [
                xy
                for xy in (as_local_point(point, panel.ref_lat, panel.ref_lng) for point in candidate)
                if xy is not None
            ]
            if len(points) >= 2:
                return points
    return []


def solution_routes(doc: dict[str, Any]) -> list[dict[str, Any]]:
    solution = doc.get("solution", {})
    routes = solution.get("routes", [])
    if isinstance(routes, list):
        return [route for route in routes if isinstance(route, dict)]
    if isinstance(routes, dict):
        def sort_key(item: tuple[Any, Any]) -> tuple[int, str]:
            key = str(item[0])
            return (int(key), key) if key.isdigit() else (10_000, key)

        return [
            route
            for _key, route in sorted(routes.items(), key=sort_key)
            if isinstance(route, dict)
        ]
    return []


def normalized_nfz_for_wrap(projected_env: dict[str, Any]) -> list[dict[str, float]]:
    wrapped_inputs: list[dict[str, float]] = []
    for nfz in projected_env.get("sams", []):
        if "x" not in nfz or "y" not in nfz:
            continue
        radius = nfz.get("range", nfz.get("range_km", 0.0))
        wrapped_inputs.append(
            {
                "x": float(nfz["x"]),
                "y": float(nfz["y"]),
                "range": float(radius),
            }
        )
    return wrapped_inputs


def proposed_wrapped_hulls(projected_env: dict[str, Any]) -> tuple[list[list[tuple[float, float]]], list[int]]:
    nfzs = normalized_nfz_for_wrap(projected_env)
    hulls, _stats = wrap_sams(nfzs, min_seg=0.3)
    clusters = _cluster_overlapping_sams(nfzs)
    clean_hulls = [
        [(float(point[0]), float(point[1])) for point in hull]
        for hull in hulls
        if isinstance(hull, list) and len(hull) >= 3
    ]
    cluster_sizes = [len(cluster) for cluster in clusters]
    return clean_hulls, cluster_sizes


def stored_wrapped_hulls(panel: PanelData) -> list[list[tuple[float, float]]]:
    solution = panel.doc.get("solution", {})
    raw_hulls = solution.get("wrapped_polygons", [])
    projected: list[list[tuple[float, float]]] = []
    if not isinstance(raw_hulls, list):
        return projected
    for hull in raw_hulls:
        if not isinstance(hull, list):
            continue
        points = [
            xy
            for xy in (as_local_point(point, panel.ref_lat, panel.ref_lng) for point in hull)
            if xy is not None
        ]
        if len(points) >= 3:
            projected.append(points)
    return projected


def compare_hulls(computed: list[list[tuple[float, float]]], stored: list[list[tuple[float, float]]]) -> dict[str, Any]:
    if not stored:
        return {
            "stored_hulls_present": False,
            "computed_hull_count": len(computed),
            "stored_hull_count": 0,
            "vertex_counts_match": None,
            "max_vertex_delta_km": None,
        }

    vertex_counts_match = len(computed) == len(stored) and all(
        len(c_hull) == len(s_hull) for c_hull, s_hull in zip(computed, stored)
    )
    max_delta = None
    if vertex_counts_match:
        deltas: list[float] = []
        for c_hull, s_hull in zip(computed, stored):
            for c_point, s_point in zip(c_hull, s_hull):
                deltas.append(math.hypot(c_point[0] - s_point[0], c_point[1] - s_point[1]))
        max_delta = max(deltas) if deltas else 0.0

    return {
        "stored_hulls_present": True,
        "computed_hull_count": len(computed),
        "stored_hull_count": len(stored),
        "vertex_counts_match": vertex_counts_match,
        "max_vertex_delta_km": max_delta,
    }


def expand_bounds(bounds: list[float] | None, x: float, y: float) -> list[float]:
    if bounds is None:
        return [x, x, y, y]
    bounds[0] = min(bounds[0], x)
    bounds[1] = max(bounds[1], x)
    bounds[2] = min(bounds[2], y)
    bounds[3] = max(bounds[3], y)
    return bounds


def panel_bounds(panel: PanelData, include_hulls: bool = True, include_routes: bool = True) -> tuple[float, float, float, float]:
    bounds: list[float] | None = None
    env = panel.projected_env

    for node in env.get("airports", []) + env.get("targets", []):
        if "x" in node and "y" in node:
            bounds = expand_bounds(bounds, float(node["x"]), float(node["y"]))

    for nfz in env.get("sams", []):
        if "x" not in nfz or "y" not in nfz:
            continue
        radius = float(nfz.get("range", nfz.get("range_km", 0.0)))
        x = float(nfz["x"])
        y = float(nfz["y"])
        bounds = expand_bounds(bounds, x - radius, y - radius)
        bounds = expand_bounds(bounds, x + radius, y + radius)

    if include_hulls:
        hulls, _cluster_sizes = proposed_wrapped_hulls(env)
        for hull in hulls:
            for x, y in hull:
                bounds = expand_bounds(bounds, x, y)

    if include_routes:
        for route in solution_routes(panel.doc):
            for x, y in trajectory_points(route, panel):
                bounds = expand_bounds(bounds, x, y)

    if bounds is None:
        return (-10.0, 10.0, -10.0, 10.0)

    width = max(bounds[1] - bounds[0], 1.0)
    height = max(bounds[3] - bounds[2], 1.0)
    margin = max(width, height) * 0.06 + 1.0
    return (bounds[0] - margin, bounds[1] + margin, bounds[2] - margin, bounds[3] + margin)


def merge_bounds(bounds_list: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    xs0, xs1, ys0, ys1 = zip(*bounds_list)
    width = max(xs1) - min(xs0)
    height = max(ys1) - min(ys0)
    margin = max(width, height) * 0.02
    return (min(xs0) - margin, max(xs1) + margin, min(ys0) - margin, max(ys1) + margin)


def apply_bounds(ax: plt.Axes, bounds: tuple[float, float, float, float]) -> None:
    ax.set_xlim(bounds[0], bounds[1])
    ax.set_ylim(bounds[2], bounds[3])
    ax.set_aspect("equal", adjustable="box")


def style_axis(ax: plt.Axes, label_size: float = 7.0) -> None:
    ax.grid(False)
    ax.tick_params(axis="both", which="major", labelsize=label_size, length=2.5, width=0.6)
    for spine in ax.spines.values():
        spine.set_linewidth(0.8)
        spine.set_color("#333333")


def draw_environment(
    ax: plt.Axes,
    panel: PanelData,
    title: str,
    show_hulls: bool,
    show_routes: bool,
    bounds: tuple[float, float, float, float] | None = None,
    label_scale: float = 1.0,
) -> dict[str, Any]:
    env = panel.projected_env
    computed_hulls, cluster_sizes = proposed_wrapped_hulls(env)
    hull_validation = compare_hulls(computed_hulls, stored_wrapped_hulls(panel))
    route_records = solution_routes(panel.doc)
    drawable_route_count = 0

    if show_routes:
        for route_idx, route in enumerate(route_records):
            points = trajectory_points(route, panel)
            if len(points) < 2:
                continue
            drawable_route_count += 1
            xs, ys = zip(*points)
            ax.plot(
                xs,
                ys,
                color=ROUTE_COLORS[route_idx % len(ROUTE_COLORS)],
                linewidth=1.2,
                alpha=0.92,
                zorder=3,
            )

    for index, nfz in enumerate(env.get("sams", [])):
        if "x" not in nfz or "y" not in nfz:
            continue
        x = float(nfz["x"])
        y = float(nfz["y"])
        radius = float(nfz.get("range", nfz.get("range_km", 0.0)))
        ax.add_patch(
            Circle(
                (x, y),
                radius,
                facecolor=NFZ_FILL,
                edgecolor=NFZ_EDGE,
                linewidth=0.8,
                alpha=0.23,
                zorder=1,
            )
        )
        ax.scatter([x], [y], marker="x", s=12 * label_scale, color=NFZ_EDGE, linewidth=0.8, zorder=4)
        label = display_nfz_label(nfz.get("id") or nfz.get("name"), index)
        ax.text(
            x,
            y + radius + 0.65,
            label,
            ha="center",
            va="bottom",
            fontsize=5.2 * label_scale,
            color="#6d4100",
            zorder=5,
        )

    if show_hulls:
        for hull in computed_hulls:
            ax.add_patch(
                Polygon(
                    hull,
                    closed=True,
                    facecolor=HULL_FILL,
                    edgecolor=HULL_EDGE,
                    linewidth=1.1,
                    alpha=0.08,
                    zorder=2,
                )
            )
            closed = hull + [hull[0]]
            xs, ys = zip(*closed)
            ax.plot(xs, ys, color=HULL_EDGE, linewidth=1.15, alpha=0.95, zorder=4)

    for airport in env.get("airports", []):
        if "x" not in airport or "y" not in airport:
            continue
        x = float(airport["x"])
        y = float(airport["y"])
        ax.scatter([x], [y], marker="s", s=35 * label_scale, color=AIRPORT_COLOR, zorder=7)
        ax.text(
            x + 0.65,
            y + 0.65,
            str(airport.get("id") or airport.get("name") or "Airport"),
            fontsize=6.2 * label_scale,
            color=AIRPORT_COLOR,
            zorder=8,
        )

    for idx, target in enumerate(env.get("targets", [])):
        if "x" not in target or "y" not in target:
            continue
        x = float(target["x"])
        y = float(target["y"])
        ax.scatter([x], [y], marker="o", s=20 * label_scale, color=TARGET_COLOR, zorder=6)
        label = str(target.get("id") or target.get("name") or f"T{idx + 1}")
        ax.text(
            x + 0.55,
            y + 0.55,
            label,
            fontsize=5.2 * label_scale,
            color="#144a7a",
            zorder=8,
        )

    if bounds is not None:
        apply_bounds(ax, bounds)
    else:
        apply_bounds(ax, panel_bounds(panel, include_hulls=show_hulls, include_routes=show_routes))

    style_axis(ax, label_size=6.3 * label_scale)
    ax.set_title(title, fontsize=8.2 * label_scale, loc="left", pad=3)

    return {
        "source_path": str(panel.source_path.relative_to(REPO_ROOT)),
        "mission_path": str(panel.mission_path.relative_to(REPO_ROOT)) if panel.mission_path else None,
        "hull_overlay": show_hulls,
        "hull_count": len(computed_hulls),
        "cluster_sizes": cluster_sizes,
        "nfz_count": len(env.get("sams", [])),
        "target_count": len(env.get("targets", [])),
        "route_count": len(route_records) if show_routes else 0,
        "drawable_route_count": drawable_route_count if show_routes else 0,
        "stored_hull_check": hull_validation,
    }


def figure_legend(fig: plt.Figure, include_hulls: bool, include_routes: bool) -> None:
    handles: list[Line2D] = [
        Line2D([0], [0], marker="s", color="none", markerfacecolor=AIRPORT_COLOR, markersize=5, label="Airport"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=TARGET_COLOR, markersize=5, label="Target"),
        Line2D([0], [0], marker="o", color=NFZ_EDGE, markerfacecolor=NFZ_FILL, alpha=0.55, markersize=5, label="NFZ circle"),
    ]
    if include_routes:
        handles.append(Line2D([0], [0], color=ROUTE_COLOR, linewidth=1.5, label="Mission route"))
    if include_hulls:
        handles.append(Line2D([0], [0], color=HULL_EDGE, linewidth=1.4, label="Proposed wrapped planning hull"))
    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.03),
        ncol=len(handles),
        fontsize=7,
        frameon=False,
    )


def save_figure(fig: plt.Figure, basename: str, output_dir: Path) -> list[str]:
    fig.tight_layout(rect=(0.0, 0.06, 1.0, 1.0))
    paths = []
    for suffix in ("svg", "pdf", "png"):
        path = output_dir / f"{basename}.{suffix}"
        save_kwargs: dict[str, Any] = {"bbox_inches": "tight", "facecolor": "white"}
        if suffix == "png":
            save_kwargs["dpi"] = 450
        fig.savefig(path, **save_kwargs)
        paths.append(str(path.relative_to(REPO_ROOT)))
    plt.close(fig)
    return paths


def build_fig2(output_dir: Path) -> dict[str, Any]:
    fig, axes = plt.subplots(1, 3, figsize=(7.35, 2.55))
    panels = []
    for idx, (stem, title, source_path, missions_dir) in enumerate(CONTROLLED_T12):
        mission_path = controlled_proposed_path(missions_dir, stem)
        panel = load_panel(source_path, mission_path)
        panels.append(
            draw_environment(
                axes[idx],
                panel,
                f"({chr(97 + idx)}) {title}",
                show_hulls=True,
                show_routes=True,
                label_scale=0.85,
            )
        )
        if idx == 0:
            axes[idx].set_ylabel("North-South local km", fontsize=7)
        axes[idx].set_xlabel("East-West local km", fontsize=7)
    figure_legend(fig, include_hulls=True, include_routes=True)
    return {
        "figure": "fig2_controlled_t12_proposed_environments",
        "outputs": save_figure(fig, "fig2_controlled_t12_proposed_environments", output_dir),
        "panels": panels,
    }


def build_fig4(output_dir: Path) -> dict[str, Any]:
    stem, source_path = COMPOSITE_T12
    panels_data = [
        load_panel(source_path, method_mission_path(PART1_COMPOSITE_RUN, method, stem))
        for method, _label, _show_hulls in FIG4_METHODS
    ]
    shared_bounds = merge_bounds(
        [panel_bounds(panel, include_hulls=True, include_routes=True) for panel in panels_data]
    )

    fig, axes = plt.subplots(2, 2, figsize=(7.35, 5.55))
    panels = []
    for idx, (method, label, show_hulls) in enumerate(FIG4_METHODS):
        panel = panels_data[idx]
        ax = axes.flat[idx]
        panels.append(
            draw_environment(
                ax,
                panel,
                f"({chr(97 + idx)}) {label}",
                show_hulls=show_hulls,
                show_routes=True,
                bounds=shared_bounds,
                label_scale=0.85,
            )
        )
        if idx in (0, 2):
            ax.set_ylabel("North-South local km", fontsize=7)
        if idx in (2, 3):
            ax.set_xlabel("East-West local km", fontsize=7)
        panels[-1]["method"] = method
    figure_legend(fig, include_hulls=True, include_routes=True)
    return {
        "figure": "fig4_composite_t12_method_comparison",
        "outputs": save_figure(fig, "fig4_composite_t12_method_comparison", output_dir),
        "panels": panels,
    }


def build_fig6(output_dir: Path) -> dict[str, Any]:
    stem, source_path = COMPOSITE_T12
    panels_data = [
        load_panel(source_path, method_mission_path(PART1_COMPOSITE_RUN, method, stem))
        for method, _label in FIG6_METHODS
    ]
    shared_bounds = merge_bounds(
        [panel_bounds(panel, include_hulls=False, include_routes=True) for panel in panels_data]
    )

    fig, axes = plt.subplots(2, 2, figsize=(7.35, 5.55))
    panels = []
    for idx, (method, label) in enumerate(FIG6_METHODS):
        ax = axes.flat[idx]
        panel = panels_data[idx]
        panels.append(
            draw_environment(
                ax,
                panel,
                f"({chr(97 + idx)}) {label}",
                show_hulls=False,
                show_routes=True,
                bounds=shared_bounds,
                label_scale=0.85,
            )
        )
        if idx in (0, 2):
            ax.set_ylabel("North-South local km", fontsize=7)
        if idx in (2, 3):
            ax.set_xlabel("East-West local km", fontsize=7)
        panels[-1]["method"] = method
    figure_legend(fig, include_hulls=False, include_routes=True)
    return {
        "figure": "fig6_appatt_tig_raw_vs_smoothed",
        "outputs": save_figure(fig, "fig6_appatt_tig_raw_vs_smoothed", output_dir),
        "panels": panels,
    }


def part2_dataset_paths() -> list[tuple[str, str, str, Path]]:
    paths: list[tuple[str, str, str, Path]] = []
    for topology_dir, topology_label, prefix in PART2_TOPOLOGIES:
        for index in range(1, 6):
            instance_id = f"i{index:02d}"
            path = PART2_DATASETS / topology_dir / f"{prefix}_{instance_id}_t12.json"
            paths.append((topology_dir, topology_label, instance_id, path))
    return paths


def build_fig10_15panel(output_dir: Path) -> dict[str, Any]:
    records = part2_dataset_paths()
    panels_by_key: dict[tuple[str, str], PanelData] = {}
    row_bounds: dict[str, tuple[float, float, float, float]] = {}
    for topology_dir, _topology_label, instance_id, source_path in records:
        panel = load_panel(source_path, part2_proposed_path(source_path))
        panels_by_key[(topology_dir, instance_id)] = panel

    for topology_dir, _topology_label, _prefix in PART2_TOPOLOGIES:
        row_panels = [
            panels_by_key[(topology_dir, f"i{index:02d}")]
            for index in range(1, 6)
        ]
        row_bounds[topology_dir] = merge_bounds(
            [panel_bounds(panel, include_hulls=True, include_routes=False) for panel in row_panels]
        )

    fig, axes = plt.subplots(3, 5, figsize=(7.4, 6.85))
    panels = []
    for row_idx, (topology_dir, topology_label, _prefix) in enumerate(PART2_TOPOLOGIES):
        for col_idx in range(5):
            instance_id = f"i{col_idx + 1:02d}"
            ax = axes[row_idx, col_idx]
            panel = panels_by_key[(topology_dir, instance_id)]
            title = f"{topology_label}\n{instance_id}" if col_idx == 0 else instance_id
            panels.append(
                draw_environment(
                    ax,
                    panel,
                    title,
                    show_hulls=True,
                    show_routes=False,
                    bounds=row_bounds[topology_dir],
                    label_scale=0.62,
                )
            )
            panels[-1]["topology"] = topology_label
            panels[-1]["instance_id"] = instance_id
            if col_idx == 0:
                ax.set_ylabel("North-South km", fontsize=6)
            if row_idx == 2:
                ax.set_xlabel("East-West km", fontsize=6)
    figure_legend(fig, include_hulls=True, include_routes=False)
    return {
        "figure": "fig10_part2_geometry_validation_15panel",
        "outputs": save_figure(fig, "fig10_part2_geometry_validation_15panel", output_dir),
        "panels": panels,
        "readability_note": "Dense contact sheet; representative three-panel figure is also generated.",
    }


def build_fig10_representative(output_dir: Path) -> dict[str, Any]:
    representative_instance = "i03"
    fig, axes = plt.subplots(1, 3, figsize=(7.35, 2.55))
    panels = []
    for idx, (topology_dir, topology_label, prefix) in enumerate(PART2_TOPOLOGIES):
        source_path = PART2_DATASETS / topology_dir / f"{prefix}_{representative_instance}_t12.json"
        panel = load_panel(source_path, part2_proposed_path(source_path))
        panels.append(
            draw_environment(
                axes[idx],
                panel,
                f"({chr(97 + idx)}) {topology_label} {representative_instance}",
                show_hulls=True,
                show_routes=False,
                label_scale=0.85,
            )
        )
        panels[-1]["topology"] = topology_label
        panels[-1]["instance_id"] = representative_instance
        if idx == 0:
            axes[idx].set_ylabel("North-South local km", fontsize=7)
        axes[idx].set_xlabel("East-West local km", fontsize=7)
    figure_legend(fig, include_hulls=True, include_routes=False)
    return {
        "figure": "fig10_part2_geometry_validation_representative_3panel",
        "outputs": save_figure(fig, "fig10_part2_geometry_validation_representative_3panel", output_dir),
        "panels": panels,
    }


def write_report(output_dir: Path, figures: list[dict[str, Any]], input_hashes: dict[str, str]) -> None:
    report = {
        "generated_by": str(Path(__file__).relative_to(REPO_ROOT)),
        "output_directory": str(output_dir.relative_to(REPO_ROOT)),
        "terminology": "Legacy input SAM arrays are displayed as NFZ labels at render time only.",
        "planner_wrapping_source": {
            "module": "path_planning_core.sam_wrapping",
            "functions": ["wrap_sams", "_cluster_overlapping_sams"],
            "min_seg_km": 0.3,
        },
        "projection_source": {
            "module": "server.solver.projection",
            "function": "_project_env_to_local_km",
        },
        "input_hashes_sha256": input_hashes,
        "figures": figures,
    }
    (output_dir / "validation_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    rows: list[dict[str, Any]] = []
    for figure in figures:
        for panel in figure["panels"]:
            rows.append(
                {
                    "figure": figure["figure"],
                    "source_path": panel["source_path"],
                    "mission_path": panel["mission_path"] or "",
                    "method": panel.get("method", ""),
                    "topology": panel.get("topology", ""),
                    "instance_id": panel.get("instance_id", ""),
                    "hull_overlay": panel["hull_overlay"],
                    "hull_count": panel["hull_count"],
                    "cluster_sizes": ";".join(str(size) for size in panel["cluster_sizes"]),
                    "nfz_count": panel["nfz_count"],
                    "target_count": panel["target_count"],
                    "route_count": panel["route_count"],
                    "drawable_route_count": panel["drawable_route_count"],
                }
            )
    with (output_dir / "figure_panel_manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "figure",
                "source_path",
                "mission_path",
                "method",
                "topology",
                "instance_id",
                "hull_overlay",
                "hull_count",
                "cluster_sizes",
                "nfz_count",
                "target_count",
                "route_count",
                "drawable_route_count",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def collect_input_paths() -> list[Path]:
    paths: list[Path] = []
    for stem, _title, source_path, missions_dir in CONTROLLED_T12:
        paths.append(source_path)
        paths.append(controlled_proposed_path(missions_dir, stem))
    stem, composite_source = COMPOSITE_T12
    paths.append(composite_source)
    for method, _label, _show_hulls in FIG4_METHODS:
        paths.append(method_mission_path(PART1_COMPOSITE_RUN, method, stem))
    for method, _label in FIG6_METHODS:
        paths.append(method_mission_path(PART1_COMPOSITE_RUN, method, stem))
    for _topology_dir, _topology_label, _instance_id, source_path in part2_dataset_paths():
        paths.append(source_path)
        proposed_path = part2_proposed_path(source_path)
        if proposed_path:
            paths.append(proposed_path)
    return sorted(set(paths))


def write_readme(output_dir: Path) -> None:
    content = """# Rev E Publication Figures

This directory contains generated publication graphics for the NFZ pairwise
preprocessing manuscript. Figures were generated from frozen benchmark JSON
inputs and mission outputs without modifying datasets, routes, or metrics.

Visible labels convert legacy input SAM identifiers to NFZ terminology at
render time only. The underlying JSON files are unchanged.

Wrapped planning hulls are produced with `path_planning_core.sam_wrapping.wrap_sams`
using the same `min_seg=0.3` setting used by the Proposed planner path.
"""
    (output_dir / "README.md").write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="replace an existing generated output directory")
    args = parser.parse_args()

    matplotlib.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "axes.linewidth": 0.8,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    if OUTPUT_DIR.exists() and any(OUTPUT_DIR.iterdir()) and not args.force:
        raise SystemExit(f"{OUTPUT_DIR} already contains files; rerun with --force to replace generated outputs")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.force:
        for child in OUTPUT_DIR.iterdir():
            if child.is_file():
                child.unlink()

    input_paths = collect_input_paths()
    input_hashes_before = {str(path.relative_to(REPO_ROOT)): sha256_file(path) for path in input_paths}

    figures = [
        build_fig2(OUTPUT_DIR),
        build_fig4(OUTPUT_DIR),
        build_fig6(OUTPUT_DIR),
        build_fig10_15panel(OUTPUT_DIR),
        build_fig10_representative(OUTPUT_DIR),
    ]

    input_hashes_after = {str(path.relative_to(REPO_ROOT)): sha256_file(path) for path in input_paths}
    if input_hashes_before != input_hashes_after:
        raise RuntimeError("At least one frozen input file changed during figure generation")

    write_report(OUTPUT_DIR, figures, input_hashes_before)
    write_readme(OUTPUT_DIR)

    generated = sorted(str(path.relative_to(REPO_ROOT)) for path in OUTPUT_DIR.iterdir() if path.is_file())
    print(json.dumps({"output_dir": str(OUTPUT_DIR.relative_to(REPO_ROOT)), "generated": generated}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
