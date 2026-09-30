# Proposed NFZ-Aware Matrix Method

This method wraps the existing multi-UAS mission planner implementation:

- `server.solver.sam_distance_matrix.calculate_sam_aware_matrix`
- `path_planning_core.sam_wrapping.wrap_sams`
- `path_planning_core.boundary_navigation.plan_path`

The benchmark wrapper does not alter the algorithm. It calls the existing implementation with Supabase caching disabled so generated directed pairwise paths remain available in the run artifact.

## Active Implementation

The benchmarked implementation is a deterministic NFZ-aware pairwise cost-preprocessing method:

- C1: prepare native NFZ obstacle inputs and cluster overlapping NFZs.
- C2: construct convex-hull wrapped regions for overlapping NFZ clusters.
- C3: classify each directed source-destination pair with a direct-path obstruction test against the native circular NFZ representation.
- C4: construct a local NFZ-avoiding path using geometry-dependent routing:
  - one wrapped NFZ region uses tangent/boundary navigation;
  - multiple wrapped NFZ regions use visibility-graph construction plus Dijkstra shortest-path search.
- C5: store directed pairwise NFZ-aware costs and complete detour paths.
- C6: deliver the reusable matrix and path cache to the common mission optimizer.

Implementation note: recursive tangent chaining is not present in the current active proposed-method call path. Multi-region visibility-graph routing is primary behavior for the multiple-wrapped-region case, not a fallback.
