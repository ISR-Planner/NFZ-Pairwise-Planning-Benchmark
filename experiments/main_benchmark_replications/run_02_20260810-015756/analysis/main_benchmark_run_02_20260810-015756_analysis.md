# Controlled Benchmark Run 2 Analysis

Run directory: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\main_benchmark_replications\run_02_20260810-015756`

## Method Summary

| method | success | feasible | partial | infeasible | mean_matrix_s | mean_solver_s | mean_success_distance | mean_service_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| proposed | 9/9 | 9/9 | 0 | 0 | 17.673758 | 2.534189 | 393.791264 | 1.000000 |
| euclidean | 9/9 | 9/9 | 0 | 0 | 0.000163 | 2.545672 | 388.016001 | 1.000000 |
| collision_rejection | 3/9 | 6/9 | 3 | 3 | 0.000262 | 0.536463 | 430.161065 | 0.384259 |
| visibility_graph | 9/9 | 9/9 | 0 | 0 | 22.368026 | 2.530339 | 393.792316 | 1.000000 |
| grid_astar | 9/9 | 9/9 | 0 | 0 | 0.399217 | 2.536103 | 414.041257 | 1.000000 |
| appatt_raw | 9/9 | 9/9 | 0 | 0 | 0.000994 | 2.540489 | 400.800350 | 1.000000 |
| appatt_bspline | 3/9 | 6/9 | 3 | 3 | 0.002564 | 0.531110 | 430.161065 | 0.384259 |
| tig_raw | 8/9 | 9/9 | 1 | 0 | 0.001069 | 1.702013 | 409.579979 | 0.916667 |
| tig_bezier | 3/9 | 6/9 | 3 | 3 | 0.001590 | 0.530442 | 430.161065 | 0.384259 |
