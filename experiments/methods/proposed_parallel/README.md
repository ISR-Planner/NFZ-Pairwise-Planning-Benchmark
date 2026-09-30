# Proposed Parallel Matrix Method

This is an experimental parallel execution wrapper for Doc's existing proposed NFZ-aware pairwise matrix algorithm.

The serial `methods/proposed` implementation remains the authoritative reference. This method does not redesign or optimize the routing algorithm. It preserves the existing directed workload: every off-diagonal `i -> j` pair is calculated independently, and `j -> i` is calculated independently as its own task. Symmetric pairs are not collapsed or reversed.

The worker process reuses the read-only planner's `SAMDistanceMatrixCalculator` pairwise helpers:

- `_path_blocked(...)`
- `_plan_sam_avoiding_path(...)`

NFZ preparation, target exclusion, wrapped-polygon diagnostics, buffer handling, path representation, distance calculation, and unavailable-edge behavior are kept aligned with `calculate_sam_aware_matrix(..., use_supabase_cache=False)`.

The parallel method mirrors the current serial proposed implementation's geometry-dependent routing behavior: one wrapped NFZ region uses tangent/boundary navigation, while multiple wrapped NFZ regions use visibility-graph construction plus Dijkstra shortest-path search.

Parallel execution uses `concurrent.futures.ProcessPoolExecutor`, because the pairwise routing work is CPU-bound. The worker function is module-level for Windows spawn compatibility; no lambdas or nested process targets are used.

Initial worker count is fixed by `PROPOSED_PARALLEL_WORKERS = 4`. The count is explicit and reproducible, and can be changed later for scaling tests.

Each matrix build creates and tears down its own process pool. Worker startup, task submission, pair calculations, result transfer, collection, matrix assembly, and pool shutdown are inside the common matrix-build timing boundary. No persistent process pool or persistent cache survives between CLI benchmark runs.

Supabase caching is disabled. The method is intended only as a proof-of-equivalence and performance experiment against the frozen serial proposed method.
