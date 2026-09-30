# Visibility-Graph Matrix Method

This method is a conventional polygonal visibility-graph shortest-path baseline.

Each original circular NFZ is approximated independently with `72` polygon boundary vertices, equivalent to fixed 5-degree angular spacing. The fixed resolution is used for every experiment and is not tuned per environment.

Overlapping polygonal circle approximations are treated as a blocked union. The method does not merge NFZs into convex hulls, does not cluster NFZs, and does not create traversable space inside overlapping obstacle regions.

For each pairwise benchmark-node query, the graph consists of the source endpoint, destination endpoint, and polygonal obstacle-boundary vertices from the blocked union. Collision-free visible vertices are connected, with boundary-touching or boundary-following edges permitted. Edges that pass through obstacle interiors are rejected.

Shortest paths are computed with deterministic graph search. If a direct line of sight is unobstructed, the stored path is exactly `[start, end]`. If a detour is needed, the reconstructed intermediate visibility vertices are retained in the pairwise path. If no visibility-graph path exists, the pair is assigned the common unavailable-edge sentinel and no fallback routing is invoked.

This is a polygonal approximation to circular NFZ geometry, not an exact continuous-circle shortest-path solver. It does not use the proposed method's NFZ clustering or convex-hull wrapping pipeline, APPATT, TIG, or Grid A*.

The distinction from the proposed method is at the obstacle-preprocessing level and at when visibility-graph search is used. The proposed method begins with native NFZ inputs, clusters overlapping NFZs, wraps clusters with convex hulls, accepts unobstructed direct pairs, uses tangent/boundary navigation for one wrapped region, and uses visibility graph plus Dijkstra for multiple wrapped regions. This baseline independently approximates the original circular NFZs with a fixed polygonal discretization and applies its own visibility-graph shortest-path construction to those approximations.
