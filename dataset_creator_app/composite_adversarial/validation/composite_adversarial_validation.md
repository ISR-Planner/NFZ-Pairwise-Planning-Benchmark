# Composite Adversarial NFZ Validation

Topology: Composite Adversarial Stress (`composite_adversarial`)
Seed: 20260809
Native NFZ-aware mission compatibility preserves the literal JSON field `sams`.
No benchmark planner or matrix method was run.

## Required Checks

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | total NFZ count = 16 | PASS | 16 |
| 2 | C-Trap NFZ count = 5 | PASS | 5 |
| 3 | Sequential NFZ count = 6 | PASS | 6 |
| 4 | Asymmetric Corridor NFZ count = 5 | PASS | 5 |
| 5 | each motif satisfies structural rules | PASS | c_trap=True; sequential=True; asymmetric=True |
| 6 | motifs remain distinct | PASS | min_cross_motif_gap_km=2.117243; wrapped_regions=6 |
| 7 | no cross-motif circle overlap | PASS | min_cross_motif_gap_km=2.117243 |
| 8 | multiple wrapped regions after clustering/wrapping | PASS | wrapped_regions=6 |
| 9 | airport outside NFZs | PASS | circle_clearance=20.955632; hull_clearance=12.299804 |
| 10 | all targets outside NFZs | PASS | circle_clearance=3.341664; hull_clearance=3.350685 |
| 11 | target spacing >= 15 km | PASS | min_spacing=17.117243 |
| 12 | target-circle clearance >= 2 km | PASS | min_clearance=3.341664 |
| 13 | target-hull clearance >= 1 km | PASS | min_clearance=3.350685 |
| 14 | workspace bounds respected | PASS | airport=True; targets=True; circles=True |
| 15 | t04 targets preserved in t08/t12 | PASS | True |
| 16 | t08 targets preserved in t12 | PASS | True |
| 17 | NFZ geometry identical across t04/t08/t12 | PASS | True |
| 18 | airport identical across t04/t08/t12 | PASS | True |
| 19 | some airport-target segments interact with all three motif regions | PASS | all_three_count=2 |
| 20 | target-target mixture low/medium/high obstruction | PASS | {"high_2_or_3_motifs": 2, "low_0_motifs": 27, "medium_1_motif": 37} |
| 21 | no obvious boundary bypass dominates | PASS | min_ratio=1.493452; mean_ratio=2.090341; collision_free=16/24 |
| 22 | geometric free-space connection remains possible | PASS | all_targets_reachable=True; visited_nodes=19381 |

## Motif Membership

| NFZ | Motif | Cluster | Center x km | Center y km | Radius km |
|---|---|---|---:|---:|---:|
| NFZ01 | C-Trap | c_trap_chain | 28.704 | 104.666 | 10 |
| NFZ02 | C-Trap | c_trap_chain | 42.984 | 95.486 | 15 |
| NFZ03 | C-Trap | c_trap_chain | 49.104 | 79.676 | 10 |
| NFZ04 | C-Trap | c_trap_chain | 42.984 | 63.866 | 15 |
| NFZ05 | C-Trap | c_trap_chain | 31.224 | 56.306 | 5 |
| NFZ06 | Sequential Staggered Blocking | sequential_pair_1 | 67.000 | 50.000 | 5 |
| NFZ07 | Sequential Staggered Blocking | sequential_pair_1 | 67.000 | 58.000 | 5 |
| NFZ08 | Sequential Staggered Blocking | sequential_pair_2 | 84.000 | 87.000 | 5 |
| NFZ09 | Sequential Staggered Blocking | sequential_pair_2 | 84.000 | 95.000 | 5 |
| NFZ10 | Sequential Staggered Blocking | sequential_pair_3 | 101.000 | 53.000 | 5 |
| NFZ11 | Sequential Staggered Blocking | sequential_pair_3 | 101.000 | 61.000 | 5 |
| NFZ12 | Asymmetric Corridor | asymmetric_upper_3 | 116.000 | 94.000 | 10 |
| NFZ13 | Asymmetric Corridor | asymmetric_upper_3 | 127.000 | 96.000 | 10 |
| NFZ14 | Asymmetric Corridor | asymmetric_upper_3 | 137.000 | 94.000 | 5 |
| NFZ15 | Asymmetric Corridor | asymmetric_lower_2 | 118.000 | 55.000 | 10 |
| NFZ16 | Asymmetric Corridor | asymmetric_lower_2 | 132.000 | 58.000 | 10 |

## Key Metrics

- Wrapped region count: 6
- Minimum cross-motif circle gap: 2.117243 km
- Minimum wrapped-region gap: 2.0 km
- Minimum target spacing: 17.117243 km
- Minimum target-to-circle clearance: 3.341664 km
- Minimum target-to-wrapped-hull clearance: 3.350685 km
- Airport-target rays hitting all three motifs: 2
- Target-target obstruction mix: {"high_2_or_3_motifs": 2, "low_0_motifs": 27, "medium_1_motif": 37}
- Boundary bypass screen: {"candidates": [{"boundary_y_km": 5.0, "collision_free": true, "length_ratio_vs_direct": 2.257907, "target": "T1"}, {"boundary_y_km": 5.0, "collision_free": true, "length_ratio_vs_direct": 1.893728, "target": "T2"}, {"boundary_y_km": 5.0, "collision_free": false, "length_ratio_vs_direct": 2.480588, "target": "T3"}, {"boundary_y_km": 5.0, "collision_free": true, "length_ratio_vs_direct": 1.666893, "target": "T4"}, {"boundary_y_km": 5.0, "collision_free": false, "length_ratio_vs_direct": 2.658448, "target": "T5"}, {"boundary_y_km": 5.0, "collision_free": true, "length_ratio_vs_direct": 1.966035, "target": "T6"}, {"boundary_y_km": 5.0, "collision_free": true, "length_ratio_vs_direct": 2.132807, "target": "T7"}, {"boundary_y_km": 5.0, "collision_free": true, "length_ratio_vs_direct": 1.501114, "target": "T8"}, {"boundary_y_km": 5.0, "collision_free": false, "length_ratio_vs_direct": 2.268194, "target": "T9"}, {"boundary_y_km": 5.0, "collision_free": false, "length_ratio_vs_direct": 2.87905, "target": "T10"}, {"boundary_y_km": 5.0, "collision_free": true, "length_ratio_vs_direct": 1.857475, "target": "T11"}, {"boundary_y_km": 5.0, "collision_free": true, "length_ratio_vs_direct": 2.327006, "target": "T12"}, {"boundary_y_km": 145.0, "collision_free": true, "length_ratio_vs_direct": 1.748057, "target": "T1"}, {"boundary_y_km": 145.0, "collision_free": true, "length_ratio_vs_direct": 2.112235, "target": "T2"}, {"boundary_y_km": 145.0, "collision_free": true, "length_ratio_vs_direct": 1.569992, "target": "T3"}, {"boundary_y_km": 145.0, "collision_free": false, "length_ratio_vs_direct": 2.309182, "target": "T4"}, {"boundary_y_km": 145.0, "collision_free": true, "length_ratio_vs_direct": 1.85625, "target": "T5"}, {"boundary_y_km": 145.0, "collision_free": false, "length_ratio_vs_direct": 2.480511, "target": "T6"}, {"boundary_y_km": 145.0, "collision_free": true, "length_ratio_vs_direct": 1.940262, "target": "T7"}, {"boundary_y_km": 145.0, "collision_free": true, "length_ratio_vs_direct": 2.201184, "target": "T8"}, {"boundary_y_km": 145.0, "collision_free": false, "length_ratio_vs_direct": 2.163909, "target": "T9"}, {"boundary_y_km": 145.0, "collision_free": true, "length_ratio_vs_direct": 1.756016, "target": "T10"}, {"boundary_y_km": 145.0, "collision_free": false, "length_ratio_vs_direct": 2.64789, "target": "T11"}, {"boundary_y_km": 145.0, "collision_free": true, "length_ratio_vs_direct": 1.493452, "target": "T12"}], "collision_free_boundary_polylines": 16, "mean_length_ratio_vs_direct": 2.090341, "min_length_ratio_vs_direct": 1.493452, "passes_no_obvious_dominating_bypass_screen": true, "tested_boundary_polylines": 24}
- Independent connectivity all targets reachable: True
- Original dataset hash verification: byte-identical

## Coupling Summary

The C-Trap opening faces the airport and has a smaller lower terminal NFZ, making the lower-side escape geometrically attractive. The first sequential pair is placed immediately downstream on that lower side, so the C-Trap escape interacts with the first staggered blocker instead of continuing unobstructed.

The sequential pattern is a low/high/low mirror of the established high/low/high motif. The final low blocker redirects continuation back upward, while the asymmetric corridor's clear throat is centered lower than that exit and under an upper three-NFZ cluster, creating poor alignment at the corridor entrance without sealing it.

The validation uses geometry only: circle and wrapped-hull intersections, clearances, boundary-bypass screening, and an independent occupancy-grid connectivity check.
