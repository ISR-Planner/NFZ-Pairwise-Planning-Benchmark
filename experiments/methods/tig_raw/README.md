# Raw S-TIG Matrix Method

This method implements the static TIG pairwise planner as a serial benchmark matrix builder. It returns the raw path as exact source, TIG virtual waypoints, and exact destination. The matrix cost is the raw polyline length.

## Source S-TIG Behavior

The raw search uses circular SAMs as the benchmark's special case of TIG ellipse geometry where `a = b = range_km` and `theta = 0`. For each source-destination pair it finds the first obstacle whose original forbidden interior is intersected, builds LEFT and RIGHT tangent candidates from the current point, extends each tangent ray to the larger virtual circle, and selects a candidate using the TIG heuristic form `D(N,w) + alpha*P + D(w,T)`.

The implementation maintains deterministic `CurrentSet`, `ClosedSet`, and `treatedSet` equivalents through recursive target handling, path-state tracking, and repeated-state protection. It records first-collision and selected-side sequences for every pair.

## Benchmark Adaptations

The SAM safe margin is fixed at `0.0 km`. The virtual-circle offset is fixed at `5%` of the original SAM radius, so waypoint generation uses `virtual_radius = 1.05*r` while collision checking always uses the original radius. The obstacle penalty is fixed at `alpha = 1.0 km`.

The search limits are `MAX_TIG_SEARCH_EXPANSIONS = 10000` and `MAX_TIG_LOCAL_EXPANSIONS = 10000`. No fallback planner, smoothing, shortcutting, path simplification, obstacle clustering, obstacle merging, convex wrapping, APPATT tangent intersection, visibility graph, grid A*, proposed method logic, cache, or parallel worker pool is used.

The paper includes an angle condition, but the available description does not provide a sufficiently reproducible numerical parameterization for this benchmark, so no independent turning-angle threshold is introduced.
