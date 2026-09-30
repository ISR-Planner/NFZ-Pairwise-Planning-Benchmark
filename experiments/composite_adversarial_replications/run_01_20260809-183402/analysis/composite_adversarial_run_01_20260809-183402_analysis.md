# Composite Adversarial Stress Benchmark Analysis

Timestamp: `20260809-183402`

This analysis covers only the new Composite Adversarial Stress result set. The original 81-run benchmark files are not merged into these raw results.

## Infrastructure

- Completed rows: 27/27
- Infrastructure failures: 0
- Preservation hashes match: True
- Evidence count: 81 original + 27 composite = 108 method-environment evaluations

## Overall Method Summary

| method | success/3 | feasible/3 | partial | infeasible | mean matrix s | median matrix s | mean solver s | mean service frac | mean successful dist | min matrix s | max matrix s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| proposed | 3/3 | 3/3 | 0 | 0 | 1581.051621 | 1347.740558 | 68.715185 | 1.000 | 427.207065 | 410.633527 | 2984.780778 |
| euclidean | 3/3 | 3/3 | 0 | 0 | 0.000241 | 0.000242 | 68.673543 | 1.000 | 404.759502 | 0.000208 | 0.000273 |
| collision_rejection | 0/3 | 0/3 | 0 | 3 | 0.000494 | 0.000453 | 0.521774 | 0.000 |  | 0.000286 | 0.000742 |
| visibility_graph | 3/3 | 3/3 | 0 | 0 | 1331.514383 | 1133.771289 | 68.437053 | 1.000 | 427.207065 | 344.511180 | 2516.260680 |
| grid_astar | 2/3 | 3/3 | 1 | 0 | 0.715638 | 0.712598 | 58.775159 | 0.944 | 441.734545 | 0.656420 | 0.777896 |
| appatt_raw | 1/3 | 3/3 | 2 | 0 | 0.002701 | 0.002437 | 87.957811 | 0.694 | 485.029145 | 0.000849 | 0.004817 |
| appatt_bspline | 0/3 | 0/3 | 0 | 3 | 0.011835 | 0.010419 | 0.520151 | 0.000 |  | 0.002382 | 0.022705 |
| tig_raw | 0/3 | 1/3 | 1 | 2 | 0.002614 | 0.002216 | 19.858763 | 0.028 |  | 0.000745 | 0.004883 |
| tig_bezier | 0/3 | 0/3 | 0 | 3 | 0.005291 | 0.003801 | 0.522416 | 0.000 |  | 0.001295 | 0.010776 |

## By Target Count

| targets | method | matrix s | solver s | solver completed | feasible | success | serviced | service frac | distance | points | failure reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | proposed | 410.633527 | 58.358351 | True | True | True | 4/4 | 1.000 | 389.750531 | 20 |  |
| 4 | euclidean | 0.000273 | 58.317648 | True | True | True | 4/4 | 1.000 | 368.046236 | 20 |  |
| 4 | collision_rejection | 0.000286 | 0.005835 | True | False | False | 0/4 | 0.000 | 0.000000 | 0 | airport disconnected from target graph |
| 4 | visibility_graph | 344.511180 | 58.108299 | True | True | True | 4/4 | 1.000 | 389.750531 | 20 |  |
| 4 | grid_astar | 0.656420 | 58.058914 | True | True | True | 4/4 | 1.000 | 415.020920 | 20 |  |
| 4 | appatt_raw | 0.000849 | 58.194689 | True | True | False | 1/4 | 0.250 | 276.467044 | 5 | serviced 1/4 benchmark targets |
| 4 | appatt_bspline | 0.002382 | 0.005810 | True | False | False | 0/4 | 0.000 | 0.000000 | 0 | airport disconnected from target graph |
| 4 | tig_raw | 0.000745 | 0.005995 | True | False | False | 0/4 | 0.000 | 0.000000 | 0 | airport disconnected from target graph |
| 4 | tig_bezier | 0.001295 | 0.006130 | True | False | False | 0/4 | 0.000 | 0.000000 | 0 | airport disconnected from target graph |
| 8 | proposed | 1347.740558 | 58.606291 | True | True | True | 8/8 | 1.000 | 421.800776 | 40 |  |
| 8 | euclidean | 0.000208 | 58.383354 | True | True | True | 8/8 | 1.000 | 394.882784 | 40 |  |
| 8 | collision_rejection | 0.000453 | 0.015030 | True | False | False | 0/8 | 0.000 | 0.000000 | 0 | airport disconnected from target graph |
| 8 | visibility_graph | 1133.771289 | 58.383613 | True | True | True | 8/8 | 1.000 | 421.800776 | 40 |  |
| 8 | grid_astar | 0.712598 | 58.709546 | True | True | True | 8/8 | 1.000 | 468.448169 | 40 |  |
| 8 | appatt_raw | 0.002437 | 87.912210 | True | True | True | 8/8 | 1.000 | 485.029145 | 40 |  |
| 8 | appatt_bspline | 0.010419 | 0.015565 | True | False | False | 0/8 | 0.000 | 0.000000 | 0 | airport disconnected from target graph |
| 8 | tig_raw | 0.002216 | 0.015604 | True | False | False | 0/8 | 0.000 | 0.000000 | 0 | airport disconnected from target graph |
| 8 | tig_bezier | 0.003801 | 0.015309 | True | False | False | 0/8 | 0.000 | 0.000000 | 0 | airport disconnected from target graph |
| 12 | proposed | 2984.780778 | 89.180912 | True | True | True | 12/12 | 1.000 | 470.069887 | 60 |  |
| 12 | euclidean | 0.000242 | 89.319627 | True | True | True | 12/12 | 1.000 | 451.349485 | 60 |  |
| 12 | collision_rejection | 0.000742 | 1.544456 | True | False | False | 0/12 | 0.000 | 0.000000 | 0 | airport disconnected from target graph |
| 12 | visibility_graph | 2516.260680 | 88.819247 | True | True | True | 12/12 | 1.000 | 470.069887 | 60 |  |
| 12 | grid_astar | 0.777896 | 59.557017 | True | True | False | 10/12 | 0.833 | 493.910307 | 50 | serviced 10/12 benchmark targets |
| 12 | appatt_raw | 0.004817 | 117.766534 | True | True | False | 10/12 | 0.833 | 494.672313 | 50 | serviced 10/12 benchmark targets |
| 12 | appatt_bspline | 0.022705 | 1.539079 | True | False | False | 0/12 | 0.000 | 0.000000 | 0 | airport disconnected from target graph |
| 12 | tig_raw | 0.004883 | 59.554689 | True | True | False | 1/12 | 0.083 | 213.487972 | 5 | serviced 1/12 benchmark targets |
| 12 | tig_bezier | 0.010776 | 1.545810 | True | False | False | 0/12 | 0.000 | 0.000000 | 0 | airport disconnected from target graph |

## Proposed Vs Visibility Graph

| targets | proposed matrix s | VG matrix s | VG/proposed | proposed dist | VG dist | abs dist diff | rel dist diff | service diff | comparison |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | 410.633527 | 344.511180 | 0.839 | 389.750531 | 389.750531 | 0.000000 | 0.000000 | 0 | proposed success, visibility_graph success |
| 8 | 1347.740558 | 1133.771289 | 0.841 | 421.800776 | 421.800776 | 0.000000 | 0.000000 | 0 | proposed success, visibility_graph success |
| 12 | 2984.780778 | 2516.260680 | 0.843 | 470.069887 | 470.069887 | 0.000000 | 0.000000 | 0 | proposed success, visibility_graph success |

## Route Quality Vs Proposed

Comparisons are marked invalid when the compared method is partial or infeasible relative to proposed target service. Euclidean is an unrestricted geometric reference, not an NFZ-feasible shortest-path method.

| targets | method | status | serviced | delta vs proposed | relative delta | note |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | euclidean | success | 4 | -21.704295 | -0.055688 | valid; Euclidean is an unrestricted geometric reference, not an NFZ-feasible shortest-path method |
| 4 | visibility_graph | success | 4 | 0.000000 | 0.000000 | valid |
| 4 | grid_astar | success | 4 | 25.270389 | 0.064837 | valid |
| 4 | appatt_raw | partial | 1 |  |  | invalid: method partial or infeasible relative to proposed service set |
| 4 | tig_raw | infeasible | 0 |  |  | invalid: method partial or infeasible relative to proposed service set |
| 8 | euclidean | success | 8 | -26.917991 | -0.063817 | valid; Euclidean is an unrestricted geometric reference, not an NFZ-feasible shortest-path method |
| 8 | visibility_graph | success | 8 | 0.000000 | 0.000000 | valid |
| 8 | grid_astar | success | 8 | 46.647394 | 0.110591 | valid |
| 8 | appatt_raw | success | 8 | 63.228369 | 0.149901 | valid |
| 8 | tig_raw | infeasible | 0 |  |  | invalid: method partial or infeasible relative to proposed service set |
| 12 | euclidean | success | 12 | -18.720402 | -0.039825 | valid; Euclidean is an unrestricted geometric reference, not an NFZ-feasible shortest-path method |
| 12 | visibility_graph | success | 12 | 0.000000 | 0.000000 | valid |
| 12 | grid_astar | partial | 10 |  |  | invalid: method partial or infeasible relative to proposed service set |
| 12 | appatt_raw | partial | 10 |  |  | invalid: method partial or infeasible relative to proposed service set |
| 12 | tig_raw | partial | 1 |  |  | invalid: method partial or infeasible relative to proposed service set |

## Failure And Partial Analysis

APPATT B-spline and TIG Bezier are benchmark zero-margin/source-pipeline variants; these outcomes are not generalized to the published algorithms in all settings.

| method | targets | status | serviced | airport disconnected | smoothing collision counts | failure reason |
| --- | --- | --- | --- | --- | --- | --- |
| collision_rejection | 4 | infeasible | 0 | True | not reported by harness diagnostics | airport disconnected from target graph |
| collision_rejection | 8 | infeasible | 0 | True | not reported by harness diagnostics | airport disconnected from target graph |
| collision_rejection | 12 | infeasible | 0 | True | not reported by harness diagnostics | airport disconnected from target graph |
| appatt_bspline | 4 | infeasible | 0 | True | not reported by harness diagnostics | airport disconnected from target graph |
| appatt_bspline | 8 | infeasible | 0 | True | not reported by harness diagnostics | airport disconnected from target graph |
| appatt_bspline | 12 | infeasible | 0 | True | not reported by harness diagnostics | airport disconnected from target graph |
| tig_raw | 4 | infeasible | 0 | True | not reported by harness diagnostics | airport disconnected from target graph |
| tig_raw | 8 | infeasible | 0 | True | not reported by harness diagnostics | airport disconnected from target graph |
| tig_raw | 12 | partial | 1 | False | not reported by harness diagnostics | serviced 1/12 benchmark targets |
| tig_bezier | 4 | infeasible | 0 | True | not reported by harness diagnostics | airport disconnected from target graph |
| tig_bezier | 8 | infeasible | 0 | True | not reported by harness diagnostics | airport disconnected from target graph |
| tig_bezier | 12 | infeasible | 0 | True | not reported by harness diagnostics | airport disconnected from target graph |

Connectivity loss with target count: collision_rejection, appatt_bspline, and tig_bezier are airport-disconnected at all three target counts. tig_raw is airport-disconnected at t04/t08 and becomes feasible but partial at t12 with 1/12 serviced. appatt_raw is partial at t04, successful at t08, and partial at t12; grid_astar is partial at t12.

## Matrix-Time Scaling

| method | t04->t08 abs | t08->t12 abs | t04->t12 abs | t04->t08 x | t08->t12 x | t04->t12 x |
| --- | --- | --- | --- | --- | --- | --- |
| proposed | 937.107031 | 1637.040220 | 2574.147251 | 3.282 | 2.215 | 7.269 |
| euclidean | -0.000064 | 0.000034 | -0.000031 | 0.764 | 1.161 | 0.887 |
| collision_rejection | 0.000167 | 0.000289 | 0.000456 | 1.585 | 1.637 | 2.594 |
| visibility_graph | 789.260109 | 1382.489391 | 2171.749500 | 3.291 | 2.219 | 7.304 |
| grid_astar | 0.056179 | 0.065297 | 0.121476 | 1.086 | 1.092 | 1.185 |
| appatt_raw | 0.001588 | 0.002380 | 0.003968 | 2.869 | 1.977 | 5.671 |
| appatt_bspline | 0.008037 | 0.012285 | 0.020322 | 4.374 | 2.179 | 9.531 |
| tig_raw | 0.001472 | 0.002667 | 0.004138 | 2.977 | 2.203 | 6.558 |
| tig_bezier | 0.002506 | 0.006974 | 0.009480 | 2.935 | 2.835 | 8.320 |

## Proposed Scaling Detail

| targets | nodes | directed pairs | matrix s | s per directed pair |
| --- | --- | --- | --- | --- |
| 4 | 5 | 20 | 410.633527 | 20.531676 |
| 8 | 9 | 72 | 1347.740558 | 18.718619 |
| 12 | 13 | 156 | 2984.780778 | 19.133210 |

Composite proposed matrix time rises from 410.633527 s at t04 to 2984.780778 s at t12. This exceeds the previous proposed worst cases at every matching target count, so the composite creates a new observed timing regime in this single 27-run experiment.

## Composite Vs Original Topologies

### proposed

| targets | topology | matrix s | s per directed pair | mission success | mission distance |
| --- | --- | --- | --- | --- | --- |
| 4 | c_trap | 0.083541 | 0.004177 | True | 354.351874 |
| 4 | sequential_staggered_blocking | 14.811251 | 0.740563 | True | 345.903038 |
| 4 | asymmetric_corridor | 6.609243 | 0.330462 | True | 335.005606 |
| 4 | composite_adversarial | 410.633527 | 20.531676 | True | 389.750531 |
| 8 | c_trap | 0.149666 | 0.002079 | True | 394.916626 |
| 8 | sequential_staggered_blocking | 37.291649 | 0.517940 | True | 411.706836 |
| 8 | asymmetric_corridor | 15.405054 | 0.213959 | True | 401.939315 |
| 8 | composite_adversarial | 1347.740558 | 18.718619 | True | 421.800776 |
| 12 | c_trap | 0.213604 | 0.001369 | True | 425.295286 |
| 12 | sequential_staggered_blocking | 59.549678 | 0.381729 | True | 446.279350 |
| 12 | asymmetric_corridor | 24.323296 | 0.155919 | True | 428.723440 |
| 12 | composite_adversarial | 2984.780778 | 19.133210 | True | 470.069887 |

### visibility_graph

| targets | topology | matrix s | s per directed pair | mission success | mission distance |
| --- | --- | --- | --- | --- | --- |
| 4 | c_trap | 13.684090 | 0.684205 | True | 354.355375 |
| 4 | sequential_staggered_blocking | 6.556681 | 0.327834 | True | 345.903038 |
| 4 | asymmetric_corridor | 10.008895 | 0.500445 | True | 335.005606 |
| 4 | composite_adversarial | 344.511180 | 17.225559 | True | 389.750531 |
| 8 | c_trap | 27.182722 | 0.377538 | True | 394.920128 |
| 8 | sequential_staggered_blocking | 16.388492 | 0.227618 | True | 411.706836 |
| 8 | asymmetric_corridor | 23.426781 | 0.325372 | True | 401.939315 |
| 8 | composite_adversarial | 1133.771289 | 15.746823 | True | 421.800776 |
| 12 | c_trap | 41.552625 | 0.266363 | True | 425.297755 |
| 12 | sequential_staggered_blocking | 26.008731 | 0.166723 | True | 446.279350 |
| 12 | asymmetric_corridor | 36.513183 | 0.234059 | True | 428.723440 |
| 12 | composite_adversarial | 2516.260680 | 16.129876 | True | 470.069887 |

## Previous Proposed Worst Case

| targets | previous worst topology | previous worst s | composite s | composite / previous worst |
| --- | --- | --- | --- | --- |
| 4 | sequential_staggered_blocking | 14.811251 | 410.633527 | 27.724 |
| 8 | sequential_staggered_blocking | 37.291649 | 1347.740558 | 36.141 |
| 12 | sequential_staggered_blocking | 59.549678 | 2984.780778 | 50.123 |

## Files

- Raw CSV: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\results\composite_adversarial_run_01_20260809-183402.csv`
- Raw JSON: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\results\composite_adversarial_run_01_20260809-183402.json`
- Log: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\results\composite_adversarial_run_01_20260809-183402.log`
- Analysis CSV: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\results\composite_adversarial_run_01_20260809-183402_analysis.csv`
- Analysis Markdown: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\results\composite_adversarial_run_01_20260809-183402_analysis.md`
- Preservation before: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\results\protected_hashes_before.json`
- Preservation after: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\results\protected_hashes_after.json`

