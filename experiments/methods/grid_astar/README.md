# Grid A* Matrix Method

This method is a deterministic grid-based A* shortest-path baseline.

The regular workspace is the fixed `150 km x 150 km` local-kilometer domain from `-75 km` to `75 km` in each axis. Grid spacing is fixed at `1.0 km` for every experiment and is not tuned per environment.

The grid is 8-connected. Orthogonal moves cost `1.0 km`, diagonal moves cost `sqrt(2) km`, and A* uses straight-line Euclidean distance to the destination as its heuristic. Neighbor ordering and heap tie-breaking are deterministic.

The method uses the original circular NFZ geometry directly. It does not polygonize circles, merge overlapping NFZs, wrap them in convex hulls, construct tangents, use visibility-graph routing, invoke proposed-method routing logic, or use APPATT/TIG.

A regular grid vertex is blocked if it lies inside or on the boundary of any circular NFZ. Every candidate grid edge and endpoint connector also receives a continuous segment-versus-circle collision test, and an edge is rejected if it intersects or touches any NFZ.

Mission-node coordinates are not permanently snapped. Each exact source and destination coordinate is retained as a temporary graph node and connected to free regular grid vertices in the local `3x3` lattice neighborhood around the nearest grid index. If no valid connector exists, the search expands one deterministic grid ring at a time until a connector is found or the domain is exhausted.

Pairwise paths are reconstructed as unsmoothed polylines containing the exact source, endpoint connector/grid vertices, regular grid vertices, and exact destination. The method performs no path smoothing, line-of-sight shortcutting, staircase removal, visibility optimization, or path simplification beyond removing exact duplicate consecutive coordinates.

If no A* path exists, the pair receives the common solver-compatible unavailable cost and no usable path is stored.

Grid A* is a spatial discretization. Returned path length depends on the fixed `1.0 km` grid resolution and 8-connected movement model.
