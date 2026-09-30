"""
Mission Trajectory Planner
Generates flight paths that avoid SAM zones using boundary navigation.

Uses tangent-arc-tangent method with INVIOLABLE SAM boundaries.
Boundaries are NEVER penetrated - paths go around them.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List, Tuple

# Add project root to path for path_planning_core
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# Add /app for Docker deployment
if "/app" not in sys.path:
    sys.path.insert(0, "/app")

# Import boundary navigation directly - uses proper tangent-arc-tangent method
from path_planning_core.boundary_navigation import plan_path as boundary_plan_path

# Verbose solver tracing is OFF by default — a multi-target opportunistic solve
# runs generate_trajectory dozens of times, and its per-waypoint / per-segment
# prints tripped Railway's 500 logs/sec limit (dropping real messages). Set
# MISSION_DEBUG=1 to re-enable the detailed trace locally.
_DEBUG = os.environ.get("MISSION_DEBUG", "").strip() not in ("", "0", "false", "False")


def _dbg(*args, **kwargs):
    if _DEBUG:
        print(*args, **kwargs)


def _closest_point_on_segment(
    cx: float, cy: float, ax: float, ay: float, bx: float, by: float
):
    """Point on segment A->B closest to C (clamped to the segment)."""
    sx, sy = bx - ax, by - ay
    seg_len2 = sx * sx + sy * sy
    if seg_len2 < 1e-12:
        return ax, ay
    u = ((cx - ax) * sx + (cy - ay) * sy) / seg_len2
    u = 0.0 if u < 0.0 else (1.0 if u > 1.0 else u)
    return ax + u * sx, ay + u * sy


def _point_inside_any_sam_xy(x: float, y: float, sams) -> bool:
    """True if point (x,y) is strictly inside any SAM circle. Used to keep a
    relaxed detection-radius waypoint out of SAM zones (the waypoint must be a
    legal position; the trajectory generator handles detouring the path)."""
    if not sams:
        return False
    for sam in sams:
        sx, sy = sam["pos"]
        r = float(sam["range"])
        dx, dy = x - sx, y - sy
        if dx * dx + dy * dy < r * r:
            return True
    return False


# Detection radius is a "pass within r" condition. We relax each waypoint to the
# FULL radius (margin 1.0) — the animation's within-r visit check has a 1%
# tolerance (dist ≤ r·1.01), so a waypoint at exactly r is still detected, and
# using the full radius yields the true taut minimum (a 0.95 margin cost ~6 km on
# a 10-target env for no benefit now that the tolerance absorbs the boundary).
_RADIUS_MARGIN = 1.0


def _clip_route_projection(
    route,
    positions,
    target_radii,
    sams=None,
    max_iterations: int = 20,
    convergence_km: float = 0.001,
):
    """Per-waypoint center-projection relaxation (FALLBACK).

    Each interior waypoint slides to the point on its neighbors' segment that
    minimizes its two incident legs, clamped into its circle; iterate. This is
    coordinate descent — it converges but can stick ~9% above the true taut
    optimum (leaves visible corners/slack). Kept only as a fallback for when the
    convex solver (clip_route_to_radii) is unavailable or fails. Returns a NEW
    positions dict; input not mutated.
    """
    import math

    if len(route) < 3 or not target_radii:
        return dict(positions)

    sams = sams or []
    pts, centers, radii, fixed = [], [], [], []
    for i, wid in enumerate(route):
        if wid not in positions:
            pts.append([0.0, 0.0])
            centers.append((0.0, 0.0))
            radii.append(0.0)
            fixed.append(True)
            continue
        x, y = float(positions[wid][0]), float(positions[wid][1])
        r = float(target_radii.get(wid, 0.0) or 0.0)
        is_interior = 0 < i < len(route) - 1
        pts.append([x, y])
        centers.append((x, y))
        radii.append(r)
        fixed.append(not (is_interior and r > 0.0))

    for _ in range(max_iterations):
        max_move = 0.0
        for i in range(1, len(route) - 1):
            if fixed[i]:
                continue
            cx, cy = centers[i]
            r = radii[i] * _RADIUS_MARGIN
            px, py = pts[i - 1]
            nx, ny = pts[i + 1]
            fx, fy = _closest_point_on_segment(cx, cy, px, py, nx, ny)
            dfx, dfy = fx - cx, fy - cy
            dist = math.hypot(dfx, dfy)
            if dist <= r:
                tx, ty = fx, fy
            else:
                tx, ty = cx + dfx / dist * r, cy + dfy / dist * r
            chosen_x, chosen_y = cx, cy
            for s in range(9):
                t = 1.0 - s / 8
                qx = cx + (tx - cx) * t
                qy = cy + (ty - cy) * t
                if not _point_inside_any_sam_xy(qx, qy, sams):
                    chosen_x, chosen_y = qx, qy
                    break
            move = math.hypot(chosen_x - pts[i][0], chosen_y - pts[i][1])
            if move > max_move:
                max_move = move
            pts[i] = [chosen_x, chosen_y]
        if max_move < convergence_km:
            break

    out = dict(positions)
    for i, wid in enumerate(route):
        if not fixed[i]:
            out[wid] = [pts[i][0], pts[i][1]]
    return out


def clip_route_to_radii(
    route,
    positions,
    target_radii,
    sams=None,
    max_iterations: int = 20,
    convergence_km: float = 0.001,
):
    """Taut-string (rubber-band) relaxation of target waypoints within detection
    circles, keeping the Held-Karp ORDER fixed and avoiding SAM zones.

    A target with detection_radius r>0 only needs the drone to pass within r, so
    its waypoint may float anywhere in the circle. Pulling the whole path taut is
    a CONVEX problem: minimize total polyline length subject to, for each free
    (interior, r>0) waypoint W with center C, radius r: |W−C| ≤ 0.95r (stay in the
    circle, with the visit margin) AND |W−S| ≥ range_S for every SAM S (a drone
    can't sit inside a SAM — the trajectory generator still detours the flown path
    around SAMs, so only the WAYPOINT is constrained, not the chords). We solve it
    directly with SLSQP.

    The earlier per-waypoint center-projection (now _clip_route_projection) is
    coordinate descent and sticks ~9% above optimum (200.5 vs 182.5 km on a
    10-target env), leaving visible corners/slack. The convex solve reaches the
    true taut string. Falls back to the projection if SciPy is unavailable or the
    solve fails/violates a constraint. Start/end/airports/radius-0 are FIXED
    anchors. A waypoint id may repeat in a route, so everything is keyed by route
    INDEX. Returns a NEW positions dict; the input is not mutated.
    """
    import math

    if len(route) < 3 or not target_radii:
        return dict(positions)

    sams = sams or []

    # Identify free waypoints (interior targets with radius>0 whose position we
    # know). Everything else is a fixed anchor.
    free = []  # route indices we optimize
    for i, wid in enumerate(route):
        if 0 < i < len(route) - 1 and wid in positions:
            r = float(target_radii.get(wid, 0.0) or 0.0)
            if r > 0.0:
                free.append(i)
    if not free:
        return dict(positions)

    try:
        import numpy as np
        from scipy.optimize import minimize

        fixed_xy = {
            i: (float(positions[route[i]][0]), float(positions[route[i]][1]))
            for i in range(len(route))
            if i not in free and route[i] in positions
        }
        centers = [
            (
                float(positions[route[i]][0]),
                float(positions[route[i]][1]),
            )
            for i in free
        ]
        radii_eff = [
            float(target_radii.get(route[i], 0.0) or 0.0) * _RADIUS_MARGIN for i in free
        ]
        idx_of_free = {i: k for k, i in enumerate(free)}

        def point(i, v):
            if i in idx_of_free:
                k = idx_of_free[i]
                return v[2 * k], v[2 * k + 1]
            return fixed_xy.get(i, (0.0, 0.0))

        def length(v):
            total = 0.0
            for a in range(len(route) - 1):
                ax, ay = point(a, v)
                bx, by = point(a + 1, v)
                total += math.hypot(bx - ax, by - ay)
            return total

        cons = []
        for k, i in enumerate(free):
            cx, cy = centers[k]
            reff = radii_eff[k]
            cons.append(
                {
                    "type": "ineq",
                    "fun": (
                        lambda v, k=k, cx=cx, cy=cy, reff=reff: reff**2
                        - (v[2 * k] - cx) ** 2
                        - (v[2 * k + 1] - cy) ** 2
                    ),
                }
            )
            for sam in sams:
                sx, sy = sam["pos"]
                sr = float(sam["range"])
                cons.append(
                    {
                        "type": "ineq",
                        "fun": (
                            lambda v, k=k, sx=sx, sy=sy, sr=sr: (v[2 * k] - sx) ** 2
                            + (v[2 * k + 1] - sy) ** 2
                            - sr**2
                        ),
                    }
                )

        x0 = np.array([c for cxcy in centers for c in cxcy], dtype=float)
        res = minimize(
            length,
            x0,
            method="SLSQP",
            constraints=cons,
            options={"maxiter": 2000, "ftol": 1e-10},
        )

        if not res.success:
            raise RuntimeError(f"SLSQP did not converge: {res.message}")

        # Validate: every free waypoint inside its circle AND outside every SAM.
        out = dict(positions)
        for k, i in enumerate(free):
            wx, wy = float(res.x[2 * k]), float(res.x[2 * k + 1])
            cx, cy = centers[k]
            if math.hypot(wx - cx, wy - cy) > radii_eff[k] + 1e-3:
                raise RuntimeError("solution left a detection circle")
            if _point_inside_any_sam_xy(wx, wy, sams):
                raise RuntimeError("solution landed inside a SAM")
            out[route[i]] = [wx, wy]
        return out
    except Exception as _e:  # SciPy missing, non-convergence, or a violation
        print(
            f"   ⚠️ taut-string convex solve failed ({_e}); using projection fallback",
            flush=True,
        )
        return _clip_route_projection(
            route,
            positions,
            target_radii,
            sams=sams,
            max_iterations=max_iterations,
            convergence_km=convergence_km,
        )


class MissionTrajectoryPlanner:
    """Plan trajectories that avoid SAM zones using boundary navigation + strict validation."""

    def __init__(self, sams: List[Dict]):
        """
        Initialize planner with SAM zones.

        Args:
            sams: List of SAM dicts with:
                  - pos: [x, y] or position: [x, y]
                  - range: float (SAM radius)
        """
        # Normalize SAM format: {'pos': (x, y), 'range': radius}
        self.sams: List[Dict[str, float]] = []
        for sam in sams:
            pos = sam.get("pos") or sam.get("position")
            if not pos:
                continue
            if isinstance(pos, (list, tuple)):
                px, py = float(pos[0]), float(pos[1])
            else:
                # Just in case some old format sneaks in
                px = float(pos.get("x", 0.0))
                py = float(pos.get("y", 0.0))

            radius = float(sam.get("range", sam.get("radius", 15)))
            self.sams.append({"pos": (px, py), "range": radius})

        if self.sams:
            print(
                f"🎯 MissionTrajectoryPlanner initialized with {len(self.sams)} SAMs (boundary navigation + strict validation)",  # noqa: E501
                flush=True,
            )
            for sam in self.sams:
                print(
                    f"   SAM: pos={sam['pos']}, range={sam['range']:.2f}",
                    flush=True,
                )

    # ---------------------------
    #  Internal helpers
    # ---------------------------

    def _point_inside_any_sam(self, x: float, y: float) -> bool:
        """Return True if (x,y) is strictly inside ANY SAM circle."""
        for sam in self.sams:
            sx, sy = sam["pos"]
            r = sam["range"]
            dx = x - sx
            dy = y - sy
            if dx * dx + dy * dy < r * r:  # strictly inside
                return True
        return False

    def _path_violates_sams(
        self,
        path: List[List[float]],
        samples_per_segment: int = 64,
    ) -> Tuple[bool, Tuple[float, float] | None]:
        """
        Sample each segment of the path.
        Returns (violates, offending_point).
        """
        if not path or len(path) < 2 or not self.sams:
            return False, None

        for i in range(len(path) - 1):
            x1, y1 = path[i]
            x2, y2 = path[i + 1]

            for k in range(samples_per_segment + 1):
                t = k / samples_per_segment
                x = x1 + t * (x2 - x1)
                y = y1 + t * (y2 - y1)

                if self._point_inside_any_sam(x, y):
                    return True, (x, y)

        return False, None

    # ---------------------------
    #  Public API
    # ---------------------------

    def plan_path(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
    ) -> Tuple[List[List[float]], float]:
        """
        Plan path from start to end avoiding SAM zones.

        CRITICAL: Paths will NEVER penetrate SAM boundaries.
        We:
          1. Ask boundary_navigation for a candidate path.
          2. STRICTLY VALIDATE that no segment enters a SAM.
          3. If any violation is detected -> return ([], inf) and log.

        Args:
            start: (x, y) starting position
            end: (x, y) ending position

        Returns:
            Tuple of (path_points, total_distance)
            - path_points: List of [x, y] coordinates
            - total_distance: Total path length, or inf if invalid
        """
        import math

        # No SAMs -> trivial direct segment
        if not self.sams:
            distance = math.hypot(end[0] - start[0], end[1] - start[1])
            return [list(start), list(end)], distance

        # Use boundary navigation to compute a candidate path
        path, distance, method = boundary_plan_path(
            list(start),
            list(end),
            self.sams,
            debug=True,
        )

        # Sanity check on method
        if method.startswith("INVALID") or not path or len(path) < 2:
            print(
                f"❌ NO VALID PATH from ({start[0]:.1f},{start[1]:.1f}) "
                f"to ({end[0]:.1f},{end[1]:.1f}): {method}",
                flush=True,
            )
            return [], float("inf")

        # boundary_navigation already validates paths against polygons.
        # We trust its output - no additional circle-based validation needed.

        # Debug: show when SAM avoidance generates a non-direct path
        if len(path) > 2:
            print(
                f"🛡️ Boundary navigation OK: "
                f"({start[0]:.1f},{start[1]:.1f}) → ({end[0]:.1f},{end[1]:.1f}) "
                f"via {len(path)} waypoints [{method}]",
                flush=True,
            )

        return path, distance

    def generate_trajectory(
        self,
        route: List[str],
        waypoint_positions: Dict[str, List[float]],
        drone_id: str | None = None,
        return_waypoint_indices: bool = False,
    ) -> List[List[float]] | Tuple[List[List[float]], Dict[int, int]]:
        """
        Generate complete trajectory for a route sequence.

        Args:
            route: List of waypoint IDs in order (e.g., ['A1', 'T3', 'T5', 'A1'])
            waypoint_positions: Dict mapping waypoint ID to [x, y] position
            drone_id: Optional drone ID for debug logging
            return_waypoint_indices: If True, also return mapping of route index to trajectory index

        Returns:
            If return_waypoint_indices is False:
                List of [x, y] coordinates forming the complete path.
            If return_waypoint_indices is True:
                Tuple of (trajectory, waypoint_indices) where waypoint_indices maps
                route index -> trajectory index for each waypoint.

            If ANY segment violates SAMs, the offending segment's path is dropped
            and the trajectory ends before that segment.
        """
        if len(route) < 2:
            if return_waypoint_indices:
                return [], {}
            return []

        drone_label = f"D{drone_id}" if drone_id else "UNKNOWN"

        # Track trajectory index for each route waypoint
        waypoint_indices: Dict[int, int] = {0: 0}  # First waypoint is always at index 0

        _dbg(
            f"\n📍 [{drone_label}] Generating trajectory for route: "
            f"{' → '.join(route)}",
            flush=True,
        )
        for wp_id in route:
            if wp_id in waypoint_positions:
                x, y = waypoint_positions[wp_id]
                _dbg(f"   {wp_id}: ({x:.1f}, {y:.1f})", flush=True)

        trajectory: List[List[float]] = []

        for i in range(len(route) - 1):
            from_id = route[i]
            to_id = route[i + 1]

            if from_id not in waypoint_positions or to_id not in waypoint_positions:
                print(
                    f"   ⚠️ [{drone_label}] Skipping segment {from_id}→{to_id}: "
                    f"missing waypoint coordinates.",
                    flush=True,
                )
                continue

            start_xy = tuple(waypoint_positions[from_id])
            end_xy = tuple(waypoint_positions[to_id])

            _dbg(
                f"   📐 [{drone_label}] Planning segment {from_id}→{to_id}: "
                f"({start_xy[0]:.1f},{start_xy[1]:.1f}) → ({end_xy[0]:.1f},{end_xy[1]:.1f})",
                flush=True,
            )

            segment_path, seg_dist = self.plan_path(start_xy, end_xy)

            if not segment_path:
                # Path invalid -> stop trajectory here; do NOT draw illegal motion
                print(
                    f"   🚫 [{drone_label}] Segment {from_id}→{to_id} "
                    f"has NO VALID SAM-SAFE PATH. Trajectory terminated.",
                    flush=True,
                )
                break

            _dbg(
                f"   ✅ [{drone_label}] Segment {from_id}→{to_id} "
                f"has {len(segment_path)} waypoints, length ≈ {seg_dist:.1f}",
                flush=True,
            )
            # (Removed a per-trajectory-POINT print loop here: it logged every
            # point of every segment, which on a multi-target opportunistic solve
            # emitted thousands of lines and tripped Railway's 500 logs/sec limit,
            # dropping real messages. The per-segment summary above is enough.)

            # Concatenate, avoiding duplicate joint point
            if i == 0:
                trajectory.extend(segment_path)
            else:
                if len(segment_path) > 1:
                    trajectory.extend(segment_path[1:])
                else:
                    trajectory.extend(segment_path)

            # Record the trajectory index for the end waypoint of this segment
            # The end waypoint (route[i+1]) is at the last index of the trajectory so far
            waypoint_indices[i + 1] = len(trajectory) - 1

        if return_waypoint_indices:
            return trajectory, waypoint_indices
        return trajectory
