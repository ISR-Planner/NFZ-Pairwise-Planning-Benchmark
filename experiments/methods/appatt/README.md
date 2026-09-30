# APPATT-Style Static SETG-TG Matrix Method

This method is an APPATT-style static SETG-TG pairwise implementation based on the static Elliptic Tangent Graph method with Target Guidance from Liu, Li, Fan, Wu, Pedrycz, and Suganthan, "An Autonomous Path Planning Method for Unmanned Aerial Vehicle based on A Tangent Intersection and Target Guidance Strategy."

It is not a byte-for-byte reproduction of the paper's full flight-dynamics pipeline. It implements the raw static SETG-TG waypoint construction needed for this pairwise matrix benchmark.

## Published APPATT / SETG-TG Behavior

APPATT assumes a static known environment and encloses obstacles with ellipses. For a current origin point `O` and destination guidance point `D`, the static SETG-TG process checks whether `O -> D` is obstructed. If it is obstructed, the first-collided obstacle is selected.

For that first-collided obstacle, tangent lines from `O` and from `D` are constructed. Same-side origin and destination tangents form two tangent-intersection subpaths, where each temporary waypoint is the intersection of tangent lines, not the tangent contact point on the obstacle.

The conceptual state is:

- `Pa`: accepted/determined path waypoints
- `Ca`: candidate guidance waypoints
- `Ba`: obstacles avoided or encountered in sequence

The iteration starts from `Pa = [S]`, `Ca = [E]`, and `Ba = []`. If `O -> D` is clear, `D` is accepted into `Pa` and removed from `Ca`. If `O -> D` is obstructed, SETG-TG chooses one of the two tangent-intersection candidates using the published four priority rules in order:

1. Avoid returning toward the previously avoided obstacle.
2. Prefer fewer obstacle collisions along the origin tangent.
3. Prefer fewer obstacle collisions along the destination tangent.
4. Prefer the shorter complete candidate subpath.

The chosen tangent-intersection waypoint is accepted into `Pa` when `O -> T` is clear; otherwise it is added to `Ca` for further target-guided processing.

## Benchmark Adaptations

The source benchmark obstacles are circular SAM/NFZ regions, so each original circle is represented as an ellipse with `a = b = range_km`. No ellipse fitting is performed.

`APPATT_SAFE_MARGIN_KM = 0.0` because the native `range_km` already defines the experimental exclusion zone. Expanding the radius here would change the obstacle geometry relative to the other benchmark methods.

Original SAMs remain independent even when they overlap. The method does not merge overlapping SAMs, cluster SAMs, convex-wrap SAMs, or construct a common enclosing ellipse.

All geometry is computed in the benchmark's local kilometer coordinate system, not in raw latitude/longitude degree space.

APPATT is a start-to-end planner, while this benchmark requires a symmetric pairwise matrix. For each unordered benchmark-node pair, APPATT is run once in the canonical matrix orientation. The same distance is used for both matrix directions, and the reverse path is the exact reversal of the forward path. APPATT is not run in both directions to choose a best-of-two result.

Cubic B-spline smoothing from the paper is omitted. This benchmark compares pairwise geometric preprocessing, so the stored path is the raw SETG-TG waypoint path consumed by the common solver.

Mathematical tangency to the intentionally avoided circular obstacle is permitted. A segment is invalid only when it penetrates an NFZ interior; small numerical tolerance is used to avoid false interior penetration from tangent roundoff.

If all four published priority rules tie, the implementation applies a deterministic `LEFT` before `RIGHT` tie-break. This is an implementation decision, not a fifth APPATT heuristic rule.

Repeated-state detection and `MAX_APPATT_ITERATIONS = 1000` are implementation safety guards. If APPATT fails, the pair receives the common unavailable cost and no fallback planner is invoked.
