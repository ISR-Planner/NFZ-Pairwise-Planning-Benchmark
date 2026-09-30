# Clean Composite Replication Run 2 Analysis

Run 2 timestamp: `20260809-222140`
Run directory: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140`

Classification: **COMPOSITE ADVERSARIAL STRESS RUN 2**

## Input Equivalence

- Input snapshot hash verification: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140\integrity\input_hash_verification.json`
- All copied inputs byte-identical: True

## Infrastructure And Integrity

- Infrastructure completion: 27/27
- Infrastructure failures: 0
- Protected hashes before/after match: True
- Protected mismatches: 0

## Functional Reproducibility

- Functional mismatches: 0

All compared functional fields matched Run 1 for every environment-method combination: solver completion, feasibility, success, targets serviced, service fraction, route sequence, mission distance, point count, and failure reason.

## Proposed Timing Focus

| targets | Run1 matrix s | Run2 matrix s | Run2/Run1 | % diff | Run2 s/pair |
| --- | --- | --- | --- | --- | --- |
| 4 | 410.634 | 416.773 | 1.0150 | 1.495 | 20.839 |
| 8 | 1347.741 | 1343.403 | 0.9968 | -0.322 | 18.658 |
| 12 | 2984.781 | 2971.729 | 0.9956 | -0.437 | 19.050 |

## Visibility Graph Timing Focus

| targets | Run1 matrix s | Run2 matrix s | Run2/Run1 | % diff | Run2 s/pair | Clean VG/Proposed |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | 344.511 | 348.086 | 1.0104 | 1.038 | 17.404 | 0.8352 |
| 8 | 1133.771 | 1129.785 | 0.9965 | -0.352 | 15.691 | 0.8410 |
| 12 | 2516.261 | 2500.276 | 0.9936 | -0.635 | 16.027 | 0.8414 |

## All-Method Timing Stability

| method | mean abs % matrix diff | median abs % | max abs % | note |
| --- | --- | --- | --- | --- |
| proposed | 0.751 | 0.437 | 1.495 | long-running material timing |
| euclidean | 13.020 | 3.142 | 33.566 | tiny/fast timing; percent swings may be measurement noise |
| collision_rejection | 6.328 | 4.621 | 11.255 | tiny/fast timing; percent swings may be measurement noise |
| visibility_graph | 0.675 | 0.635 | 1.038 | long-running material timing |
| grid_astar | 0.088 | 0.087 | 0.152 | tiny/fast timing; percent swings may be measurement noise |
| appatt_raw | 0.600 | 0.662 | 0.883 | tiny/fast timing; percent swings may be measurement noise |
| appatt_bspline | 2.455 | 1.977 | 3.781 | tiny/fast timing; percent swings may be measurement noise |
| tig_raw | 0.737 | 0.645 | 1.268 | tiny/fast timing; percent swings may be measurement noise |
| tig_bezier | 3.335 | 3.617 | 5.314 | tiny/fast timing; percent swings may be measurement noise |

## Run 2 Success / Feasibility

| targets | method | solver completed | feasible | success | serviced | service fraction | failure reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | proposed | True | True | True | 4/4 | 1.000 |  |
| 4 | euclidean | True | True | True | 4/4 | 1.000 |  |
| 4 | collision_rejection | True | False | False | 0/4 | 0.000 | airport disconnected from target graph |
| 4 | visibility_graph | True | True | True | 4/4 | 1.000 |  |
| 4 | grid_astar | True | True | True | 4/4 | 1.000 |  |
| 4 | appatt_raw | True | True | False | 1/4 | 0.250 | serviced 1/4 benchmark targets |
| 4 | appatt_bspline | True | False | False | 0/4 | 0.000 | airport disconnected from target graph |
| 4 | tig_raw | True | False | False | 0/4 | 0.000 | airport disconnected from target graph |
| 4 | tig_bezier | True | False | False | 0/4 | 0.000 | airport disconnected from target graph |
| 8 | proposed | True | True | True | 8/8 | 1.000 |  |
| 8 | euclidean | True | True | True | 8/8 | 1.000 |  |
| 8 | collision_rejection | True | False | False | 0/8 | 0.000 | airport disconnected from target graph |
| 8 | visibility_graph | True | True | True | 8/8 | 1.000 |  |
| 8 | grid_astar | True | True | True | 8/8 | 1.000 |  |
| 8 | appatt_raw | True | True | True | 8/8 | 1.000 |  |
| 8 | appatt_bspline | True | False | False | 0/8 | 0.000 | airport disconnected from target graph |
| 8 | tig_raw | True | False | False | 0/8 | 0.000 | airport disconnected from target graph |
| 8 | tig_bezier | True | False | False | 0/8 | 0.000 | airport disconnected from target graph |
| 12 | proposed | True | True | True | 12/12 | 1.000 |  |
| 12 | euclidean | True | True | True | 12/12 | 1.000 |  |
| 12 | collision_rejection | True | False | False | 0/12 | 0.000 | airport disconnected from target graph |
| 12 | visibility_graph | True | True | True | 12/12 | 1.000 |  |
| 12 | grid_astar | True | True | False | 10/12 | 0.833 | serviced 10/12 benchmark targets |
| 12 | appatt_raw | True | True | False | 10/12 | 0.833 | serviced 10/12 benchmark targets |
| 12 | appatt_bspline | True | False | False | 0/12 | 0.000 | airport disconnected from target graph |
| 12 | tig_raw | True | True | False | 1/12 | 0.083 | serviced 1/12 benchmark targets |
| 12 | tig_bezier | True | False | False | 0/12 | 0.000 | airport disconnected from target graph |

## Run 2 Distances

| targets | method | distance | points |
| --- | --- | --- | --- |
| 4 | proposed | 389.751 | 20 |
| 4 | euclidean | 368.046 | 20 |
| 4 | collision_rejection | 0.000 | 0 |
| 4 | visibility_graph | 389.751 | 20 |
| 4 | grid_astar | 415.021 | 20 |
| 4 | appatt_raw | 276.467 | 5 |
| 4 | appatt_bspline | 0.000 | 0 |
| 4 | tig_raw | 0.000 | 0 |
| 4 | tig_bezier | 0.000 | 0 |
| 8 | proposed | 421.801 | 40 |
| 8 | euclidean | 394.883 | 40 |
| 8 | collision_rejection | 0.000 | 0 |
| 8 | visibility_graph | 421.801 | 40 |
| 8 | grid_astar | 468.448 | 40 |
| 8 | appatt_raw | 485.029 | 40 |
| 8 | appatt_bspline | 0.000 | 0 |
| 8 | tig_raw | 0.000 | 0 |
| 8 | tig_bezier | 0.000 | 0 |
| 12 | proposed | 470.070 | 60 |
| 12 | euclidean | 451.349 | 60 |
| 12 | collision_rejection | 0.000 | 0 |
| 12 | visibility_graph | 470.070 | 60 |
| 12 | grid_astar | 493.910 | 50 |
| 12 | appatt_raw | 494.672 | 50 |
| 12 | appatt_bspline | 0.000 | 0 |
| 12 | tig_raw | 213.488 | 5 |
| 12 | tig_bezier | 0.000 | 0 |

## Scaling

Proposed Run 2 scaling: t04->t08 3.223x, t08->t12 2.212x, t04->t12 7.130x.
Visibility Graph Run 2 scaling: t04->t08 3.246x, t08->t12 2.213x, t04->t12 7.183x.


## Artifacts

- Run 2 CSV: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140\results\composite_adversarial_run_02_20260809-222140.csv`
- Run 2 JSON: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140\results\composite_adversarial_run_02_20260809-222140.json`
- Analysis CSV: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140\analysis\composite_adversarial_run_02_20260809-222140_analysis.csv`
- Analysis MD: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140\analysis\composite_adversarial_run_02_20260809-222140_analysis.md`
- Comparison JSON: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140\analysis\composite_adversarial_run_02_20260809-222140_run1_comparison.json`
- Protected hashes after: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140\integrity\protected_hashes_after.json`

