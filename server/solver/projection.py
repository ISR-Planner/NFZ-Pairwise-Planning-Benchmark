"""Lat/lng to local-km projection helpers for solver boundaries."""

import copy
from typing import Any, Dict, List, Tuple

from path_planning_core.latlng_utils import latlng_to_local_xy, local_xy_to_latlng


def _project_env_to_local_km(
    env: Dict[str, Any],
) -> Tuple[Dict[str, Any], float, float]:
    """
    Project lat/lng environment to local x/y km coordinates.

    This is a boundary shim that converts the new lat/lng schema to the old
    x/y schema expected by solver internals. Internal logic operates in km, and
    results are unprojected back to lat/lng before return.

    Returns:
        (projected_env, ref_lat, ref_lng) where projected_env has x/y in km.
    """
    env = copy.deepcopy(env)

    all_latlngs: List[Tuple[float, float]] = []

    for a in env.get("airports", []):
        if "lat" in a and "lng" in a:
            all_latlngs.append((float(a["lat"]), float(a["lng"])))

    for t in env.get("targets", []):
        if "lat" in t and "lng" in t:
            all_latlngs.append((float(t["lat"]), float(t["lng"])))

    for s in env.get("sams", []):
        center = s.get("center")
        if center and "lat" in center and "lng" in center:
            all_latlngs.append((float(center["lat"]), float(center["lng"])))

    if not all_latlngs:
        ref_lat, ref_lng = 37.775, -122.435
    else:
        ref_lat = sum(ll[0] for ll in all_latlngs) / len(all_latlngs)
        ref_lng = sum(ll[1] for ll in all_latlngs) / len(all_latlngs)

    for a in env.get("airports", []):
        if "lat" in a and "lng" in a:
            x_km, y_km = latlng_to_local_xy(
                float(a["lat"]), float(a["lng"]), ref_lat, ref_lng
            )
            a["x"] = x_km
            a["y"] = y_km

    for t in env.get("targets", []):
        if "lat" in t and "lng" in t:
            x_km, y_km = latlng_to_local_xy(
                float(t["lat"]), float(t["lng"]), ref_lat, ref_lng
            )
            t["x"] = x_km
            t["y"] = y_km

    for s in env.get("sams", []):
        center = s.get("center")
        if center and "lat" in center and "lng" in center:
            x_km, y_km = latlng_to_local_xy(
                float(center["lat"]), float(center["lng"]), ref_lat, ref_lng
            )
            s["pos"] = [x_km, y_km]
            s["x"] = x_km
            s["y"] = y_km
        if "range_km" in s:
            s["range"] = s["range_km"]

    for c in env.get("checkpoints", []):
        if "lat" in c and "lng" in c:
            x_km, y_km = latlng_to_local_xy(
                float(c["lat"]), float(c["lng"]), ref_lat, ref_lng
            )
            c["x"] = x_km
            c["y"] = y_km

    for _node_id, node_data in env.get("synthetic_starts", {}).items():
        if "lat" in node_data and "lng" in node_data:
            x_km, y_km = latlng_to_local_xy(
                float(node_data["lat"]), float(node_data["lng"]), ref_lat, ref_lng
            )
            node_data["x"] = x_km
            node_data["y"] = y_km

    for _did, state in env.get("drone_states", {}).items():
        if "fuel_budget_km" in state and "fuel_budget" not in state:
            state["fuel_budget"] = state["fuel_budget_km"]

    return env, ref_lat, ref_lng


def _project_solution_trajectories(
    solution: Dict[str, Any], ref_lat: float, ref_lng: float
) -> None:
    """
    Convert [lat, lng] trajectory points into [x_km, y_km] in place.

    Used by optimizer endpoints that receive a returned solution in lat/lng and
    need trajectories in km to match the projected environment.
    """
    routes = solution.get("routes", {})
    for _did, route_data in routes.items():
        trajectory = route_data.get("trajectory")
        if trajectory and isinstance(trajectory, list):
            new_trajectory = []
            for point in trajectory:
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    lat, lng = float(point[0]), float(point[1])
                    x_km, y_km = latlng_to_local_xy(lat, lng, ref_lat, ref_lng)
                    new_trajectory.append([x_km, y_km])
                else:
                    new_trajectory.append(point)
            route_data["trajectory"] = new_trajectory


def _unproject_solution_trajectories(
    result: Dict[str, Any], ref_lat: float, ref_lng: float
) -> None:
    """Convert solution trajectory and wrapped polygon points to lat/lng in place."""
    routes = result.get("routes", {})
    for _did, route_data in routes.items():
        trajectory = route_data.get("trajectory")
        if trajectory and isinstance(trajectory, list):
            new_trajectory = []
            for point in trajectory:
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    x_km, y_km = float(point[0]), float(point[1])
                    lat, lng = local_xy_to_latlng(x_km, y_km, ref_lat, ref_lng)
                    new_trajectory.append([lat, lng])
                else:
                    new_trajectory.append(point)
            route_data["trajectory"] = new_trajectory

    wrapped_polygons = result.get("wrapped_polygons", [])
    if wrapped_polygons:
        new_polygons = []
        for poly in wrapped_polygons:
            if isinstance(poly, list):
                new_poly = []
                for point in poly:
                    if isinstance(point, (list, tuple)) and len(point) >= 2:
                        x_km, y_km = float(point[0]), float(point[1])
                        lat, lng = local_xy_to_latlng(x_km, y_km, ref_lat, ref_lng)
                        new_poly.append([lat, lng])
                    else:
                        new_poly.append(point)
                new_polygons.append(new_poly)
            else:
                new_polygons.append(poly)
        result["wrapped_polygons"] = new_polygons
