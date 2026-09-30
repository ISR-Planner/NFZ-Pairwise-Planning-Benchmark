# Controlled Benchmark Run 1 vs Run 2 Paired Analysis

Paired rows: 81/81.

Functional mismatches: 0.

Timing differences are reported separately and are not counted as functional mismatches.

## Matrix Timing By Method

| method | mean_run1_s | mean_run2_s | mean_abs_pct_diff | median_abs_pct_diff | max_abs_pct_diff | mean_ratio |
| --- | --- | --- | --- | --- | --- | --- |
| proposed | 17.604109 | 17.673758 | 0.905709 | 0.414701 | 4.838395 | 1.007800 |
| euclidean | 0.000167 | 0.000163 | 9.993907 | 4.921465 | 32.098148 | 0.976975 |
| collision_rejection | 0.000280 | 0.000262 | 6.715397 | 3.543084 | 21.655643 | 0.942041 |
| visibility_graph | 22.369133 | 22.368026 | 0.761541 | 0.608114 | 1.446514 | 1.000594 |
| grid_astar | 0.394364 | 0.399217 | 3.036983 | 2.363467 | 6.740517 | 1.011713 |
| appatt_raw | 0.001017 | 0.000994 | 3.121480 | 3.348554 | 7.503382 | 0.977874 |
| appatt_bspline | 0.002574 | 0.002564 | 4.919706 | 4.382404 | 10.287847 | 0.994943 |
| tig_raw | 0.001063 | 0.001069 | 4.066740 | 3.513322 | 12.151137 | 1.001062 |
| tig_bezier | 0.001625 | 0.001590 | 5.693277 | 4.962925 | 14.353185 | 0.990312 |

## Solver Timing By Method

| method | mean_run1_s | mean_run2_s | mean_abs_pct_diff | median_abs_pct_diff | max_abs_pct_diff | mean_ratio |
| --- | --- | --- | --- | --- | --- | --- |
| proposed | 2.529748 | 2.534189 | 4.390361 | 1.237958 | 16.432654 | 1.038741 |
| euclidean | 2.513181 | 2.545672 | 3.616539 | 1.596889 | 14.584675 | 1.035289 |
| collision_rejection | 0.529892 | 0.536463 | 17.819343 | 8.342867 | 72.758312 | 1.178193 |
| visibility_graph | 2.539611 | 2.530339 | 7.386236 | 1.346502 | 36.708668 | 1.060241 |
| grid_astar | 2.528159 | 2.536103 | 8.301103 | 2.175832 | 36.253539 | 1.073080 |
| appatt_raw | 2.518713 | 2.540489 | 5.665740 | 1.530443 | 20.733910 | 1.051437 |
| appatt_bspline | 0.532951 | 0.531110 | 54.663511 | 17.770599 | 333.336378 | 1.540359 |
| tig_raw | 1.684898 | 1.702013 | 10.412801 | 1.256689 | 45.550592 | 1.104128 |
| tig_bezier | 0.527055 | 0.530442 | 30.356388 | 21.892554 | 92.838213 | 1.301156 |

## Proposed Topology Detail

| topology | target_count | run1_matrix_s | run2_matrix_s | run1_s_per_pair | run2_s_per_pair | run2_success | run2_distance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| c_trap | 4 | 0.083541 | 0.083444 | 0.004177 | 0.004172 | true | 354.351874 |
| c_trap | 8 | 0.149666 | 0.149785 | 0.002079 | 0.002080 | true | 394.916626 |
| c_trap | 12 | 0.213604 | 0.223939 | 0.001369 | 0.001436 | true | 425.295286 |
| sequential_staggered_blocking | 4 | 14.811251 | 14.785378 | 0.740563 | 0.739269 | true | 345.903038 |
| sequential_staggered_blocking | 8 | 37.291649 | 37.189310 | 0.517940 | 0.516518 | true | 411.706836 |
| sequential_staggered_blocking | 12 | 59.549678 | 59.967959 | 0.381729 | 0.384410 | true | 446.279350 |
| asymmetric_corridor | 4 | 6.609243 | 6.636651 | 0.330462 | 0.331833 | true | 335.005606 |
| asymmetric_corridor | 8 | 15.405054 | 15.540132 | 0.213959 | 0.215835 | true | 401.939315 |
| asymmetric_corridor | 12 | 24.323296 | 24.487227 | 0.155919 | 0.156969 | true | 428.723440 |

## Proposed Topology Means

| topology | run1_mean_matrix_s | run2_mean_matrix_s |
| --- | --- | --- |
| c_trap | 0.148937 | 0.152389 |
| sequential_staggered_blocking | 37.217526 | 37.314215 |
| asymmetric_corridor | 15.445864 | 15.554670 |

## Visibility Graph Topology Detail

| topology | target_count | run1_matrix_s | run2_matrix_s |
| --- | --- | --- | --- |
| c_trap | 4 | 13.684090 | 13.767305 |
| c_trap | 8 | 27.182722 | 27.314186 |
| c_trap | 12 | 41.552625 | 40.951560 |
| sequential_staggered_blocking | 4 | 6.556681 | 6.482420 |
| sequential_staggered_blocking | 8 | 16.388492 | 16.293345 |
| sequential_staggered_blocking | 12 | 26.008731 | 26.252015 |
| asymmetric_corridor | 4 | 10.008895 | 10.103421 |
| asymmetric_corridor | 8 | 23.426781 | 23.526732 |
| asymmetric_corridor | 12 | 36.513183 | 36.621248 |

## Run 2 Visibility Graph / Proposed Ratios

| environment | run1_ratio | run2_ratio |
| --- | --- | --- |
| c_trap_001_t04.json | 163.800302 | 164.988952 |
| c_trap_001_t08.json | 181.621955 | 182.355826 |
| c_trap_001_t12.json | 194.531208 | 182.869347 |
| sequential_staggered_blocking_001_t04.json | 0.442682 | 0.438435 |
| sequential_staggered_blocking_001_t08.json | 0.439468 | 0.438119 |
| sequential_staggered_blocking_001_t12.json | 0.436757 | 0.437767 |
| asymmetric_corridor_001_t04.json | 1.514378 | 1.522367 |
| asymmetric_corridor_001_t08.json | 1.520720 | 1.513934 |
| asymmetric_corridor_001_t12.json | 1.501161 | 1.495524 |

## Run 1 vs Run 2 Method Outcomes

| method | run1_success | run2_success | run1_feasible | run2_feasible | run1_partial | run2_partial | run1_infeasible | run2_infeasible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| proposed | 9/9 | 9/9 | 9/9 | 9/9 | 0 | 0 | 0 | 0 |
| euclidean | 9/9 | 9/9 | 9/9 | 9/9 | 0 | 0 | 0 | 0 |
| collision_rejection | 3/9 | 3/9 | 6/9 | 6/9 | 3 | 3 | 3 | 3 |
| visibility_graph | 9/9 | 9/9 | 9/9 | 9/9 | 0 | 0 | 0 | 0 |
| grid_astar | 9/9 | 9/9 | 9/9 | 9/9 | 0 | 0 | 0 | 0 |
| appatt_raw | 9/9 | 9/9 | 9/9 | 9/9 | 0 | 0 | 0 | 0 |
| appatt_bspline | 3/9 | 3/9 | 6/9 | 6/9 | 3 | 3 | 3 | 3 |
| tig_raw | 8/9 | 8/9 | 9/9 | 9/9 | 1 | 1 | 0 | 0 |
| tig_bezier | 3/9 | 3/9 | 6/9 | 6/9 | 3 | 3 | 3 | 3 |

## Mission Distance Differences

Nonzero mission-distance differences: 0. Maximum absolute difference: 0.000000000000.
