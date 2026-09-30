# Proposed Branching Diagnostic 20260809-165543

This diagnostic used only the isolated `diagnostics/proposed_branching` tree. No main benchmark artifacts, method outputs, frozen proposed source, or multi-UAS mission planner files were modified.

## Preservation / Integrity

- Protected hashes unchanged: `True`
- Protected file count: `17`

## Equivalence Verification

| environment | max matrix diff | max path coord diff | route identical | route distance diff | targets diff | points diff |
|---|---:|---:|---|---:|---:|---:|
| c_trap_001_t12.json | 0 | 0 | True | 0 | 0 | 0 |
| sequential_staggered_blocking_001_t04.json | 0 | 0 | True | 0 | 0 | 0 |
| sequential_staggered_blocking_001_t08.json | 0 | 0 | True | 0 | 0 | 0 |
| sequential_staggered_blocking_001_t12.json | 0 | 0 | True | 0 | 0 | 0 |
| asymmetric_corridor_001_t12.json | 0 | 0 | True | 0 | 0 | 0 |

## Five-Environment Timing Summary

| environment | directed pairs | matrix s | pair-time s | mean pair s | median pair s | max pair s | top5 share | pairs for 80% | tangents | branches | blocks | reblocks | fallback |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| c_trap_001_t12.json | 156 | 0.289199 | 0.228645 | 0.001466 | 0.000002 | 0.012427 | 0.252 | 19 | 24 | 96 | 2276 | 2252 | 0 |
| sequential_staggered_blocking_001_t04.json | 20 | 23.078816 | 23.076978 | 1.153849 | 0.000003 | 5.814029 | 1.000 | 4 | 0 | 99908 | 89274 | 89270 | 0 |
| sequential_staggered_blocking_001_t08.json | 72 | 58.088997 | 58.086231 | 0.806753 | 0.000003 | 5.916436 | 0.504 | 8 | 0 | 249770 | 223072 | 223062 | 0 |
| sequential_staggered_blocking_001_t12.json | 156 | 93.489657 | 93.485973 | 0.599269 | 0.000002 | 6.028625 | 0.317 | 13 | 0 | 399632 | 357020 | 357004 | 0 |
| asymmetric_corridor_001_t12.json | 156 | 35.546164 | 35.543422 | 0.227842 | 0.000002 | 1.653874 | 0.231 | 18 | 0 | 245872 | 227796 | 227774 | 0 |

## Three-T12 Topology Comparison

| environment | matrix s | mean pair s | median pair s | max pair s | tangents | branches | max depth | blocks | reblocks | fallback | top10 share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| c_trap_001_t12.json | 0.289199 | 0.001466 | 0.000002 | 0.012427 | 24 | 96 | 0 | 2276 | 2252 | 0 | 0.473 |
| sequential_staggered_blocking_001_t12.json | 93.489657 | 0.599269 | 0.000002 | 6.028625 | 0 | 399632 | 0 | 357020 | 357004 | 0 | 0.630 |
| asymmetric_corridor_001_t12.json | 35.546164 | 0.227842 | 0.000002 | 1.653874 | 0 | 245872 | 0 | 227796 | 227774 | 0 | 0.460 |

## Slowest Directed Pairs

### c_trap_001_t12.json

| pair | time s | share | tangents | branches | blocks | reblocks | fallback | method |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| A1->T1 | 0.012427 | 0.054 | 1 | 4 | 88 | 87 | 0 | CW via left tangent, exit at idx 46 |
| A1->T3 | 0.011638 | 0.051 | 1 | 4 | 88 | 87 | 0 | CW via left tangent, exit at idx 50 |
| A1->T7 | 0.011424 | 0.050 | 1 | 4 | 80 | 79 | 0 | CW via left tangent, exit at idx 48 |
| A1->T5 | 0.011308 | 0.049 | 1 | 4 | 82 | 81 | 0 | CW via left tangent, exit at idx 50 |
| T1->A1 | 0.010876 | 0.048 | 1 | 4 | 106 | 105 | 0 | CCW via right tangent, exit at idx 60 |
| T7->A1 | 0.010360 | 0.045 | 1 | 4 | 106 | 105 | 0 | CCW via right tangent, exit at idx 60 |
| A1->T11 | 0.010265 | 0.045 | 1 | 4 | 94 | 93 | 0 | CCW via right tangent, exit at idx 21 |
| T3->A1 | 0.010173 | 0.044 | 1 | 4 | 106 | 105 | 0 | CCW via right tangent, exit at idx 60 |
| T5->A1 | 0.009940 | 0.043 | 1 | 4 | 106 | 105 | 0 | CCW via right tangent, exit at idx 60 |
| A1->T12 | 0.009841 | 0.043 | 1 | 4 | 82 | 81 | 0 | CW via left tangent, exit at idx 53 |

### sequential_staggered_blocking_001_t04.json

| pair | time s | share | tangents | branches | blocks | reblocks | fallback | method |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| T4->A1 | 5.814029 | 0.252 | 0 | 24977 | 22318 | 22317 | 0 | visibility-graph (12 waypoints) |
| A1->T4 | 5.760205 | 0.250 | 0 | 24977 | 22318 | 22317 | 0 | visibility-graph (12 waypoints) |
| T1->A1 | 5.757867 | 0.250 | 0 | 24977 | 22319 | 22318 | 0 | visibility-graph (7 waypoints) |
| A1->T1 | 5.744825 | 0.249 | 0 | 24977 | 22319 | 22318 | 0 | visibility-graph (7 waypoints) |
| T1->T2 | 0.000007 | 0.000 | 0 | 0 | 0 | 0 | 0 | direct |
| A1->T2 | 0.000007 | 0.000 | 0 | 0 | 0 | 0 | 0 | direct |
| T4->T1 | 0.000006 | 0.000 | 0 | 0 | 0 | 0 | 0 | direct |
| T3->T1 | 0.000003 | 0.000 | 0 | 0 | 0 | 0 | 0 | direct |
| T1->T3 | 0.000003 | 0.000 | 0 | 0 | 0 | 0 | 0 | direct |
| T2->T1 | 0.000003 | 0.000 | 0 | 0 | 0 | 0 | 0 | direct |

### sequential_staggered_blocking_001_t08.json

| pair | time s | share | tangents | branches | blocks | reblocks | fallback | method |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| T4->A1 | 5.916436 | 0.102 | 0 | 24977 | 22306 | 22305 | 0 | visibility-graph (12 waypoints) |
| T5->A1 | 5.869160 | 0.101 | 0 | 24977 | 22322 | 22321 | 0 | visibility-graph (18 waypoints) |
| A1->T7 | 5.852149 | 0.101 | 0 | 24977 | 22285 | 22284 | 0 | visibility-graph (8 waypoints) |
| T1->A1 | 5.840884 | 0.101 | 0 | 24977 | 22307 | 22306 | 0 | visibility-graph (7 waypoints) |
| T6->A1 | 5.816151 | 0.100 | 0 | 24977 | 22316 | 22315 | 0 | visibility-graph (9 waypoints) |
| T7->A1 | 5.778030 | 0.099 | 0 | 24977 | 22285 | 22284 | 0 | visibility-graph (8 waypoints) |
| A1->T4 | 5.777566 | 0.099 | 0 | 24977 | 22306 | 22305 | 0 | visibility-graph (12 waypoints) |
| A1->T6 | 5.751695 | 0.099 | 0 | 24977 | 22316 | 22315 | 0 | visibility-graph (9 waypoints) |
| A1->T1 | 5.749796 | 0.099 | 0 | 24977 | 22307 | 22306 | 0 | visibility-graph (7 waypoints) |
| A1->T5 | 5.734169 | 0.099 | 0 | 24977 | 22322 | 22321 | 0 | visibility-graph (18 waypoints) |

### sequential_staggered_blocking_001_t12.json

| pair | time s | share | tangents | branches | blocks | reblocks | fallback | method |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| T4->A1 | 6.028625 | 0.064 | 0 | 24977 | 22320 | 22319 | 0 | visibility-graph (12 waypoints) |
| T6->A1 | 5.937851 | 0.064 | 0 | 24977 | 22330 | 22329 | 0 | visibility-graph (9 waypoints) |
| A1->T11 | 5.901228 | 0.063 | 0 | 24977 | 22296 | 22295 | 0 | visibility-graph (3 waypoints) |
| T1->A1 | 5.884283 | 0.063 | 0 | 24977 | 22321 | 22320 | 0 | visibility-graph (7 waypoints) |
| T7->A1 | 5.878483 | 0.063 | 0 | 24977 | 22299 | 22298 | 0 | visibility-graph (8 waypoints) |
| A1->T10 | 5.877254 | 0.063 | 0 | 24977 | 22287 | 22286 | 0 | visibility-graph (8 waypoints) |
| T11->A1 | 5.854024 | 0.063 | 0 | 24977 | 22296 | 22295 | 0 | visibility-graph (3 waypoints) |
| T10->A1 | 5.852616 | 0.063 | 0 | 24977 | 22287 | 22286 | 0 | visibility-graph (8 waypoints) |
| A1->T6 | 5.850818 | 0.063 | 0 | 24977 | 22330 | 22329 | 0 | visibility-graph (9 waypoints) |
| T5->A1 | 5.812880 | 0.062 | 0 | 24977 | 22336 | 22335 | 0 | visibility-graph (18 waypoints) |

### asymmetric_corridor_001_t12.json

| pair | time s | share | tangents | branches | blocks | reblocks | fallback | method |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| A1->T5 | 1.653874 | 0.047 | 0 | 11176 | 10347 | 10346 | 0 | visibility-graph (10 waypoints) |
| T12->A1 | 1.646508 | 0.046 | 0 | 11176 | 10360 | 10359 | 0 | visibility-graph (10 waypoints) |
| A1->T6 | 1.644776 | 0.046 | 0 | 11176 | 10358 | 10357 | 0 | visibility-graph (4 waypoints) |
| A1->T12 | 1.644455 | 0.046 | 0 | 11176 | 10360 | 10359 | 0 | visibility-graph (10 waypoints) |
| A1->T7 | 1.635843 | 0.046 | 0 | 11176 | 10349 | 10348 | 0 | visibility-graph (4 waypoints) |
| A1->T10 | 1.631042 | 0.046 | 0 | 11176 | 10358 | 10357 | 0 | visibility-graph (7 waypoints) |
| T10->A1 | 1.629325 | 0.046 | 0 | 11176 | 10358 | 10357 | 0 | visibility-graph (7 waypoints) |
| T7->A1 | 1.625031 | 0.046 | 0 | 11176 | 10349 | 10348 | 0 | visibility-graph (4 waypoints) |
| A1->T11 | 1.622164 | 0.046 | 0 | 11176 | 10348 | 10347 | 0 | visibility-graph (7 waypoints) |
| A1->T4 | 1.619487 | 0.046 | 0 | 11176 | 10364 | 10363 | 0 | visibility-graph (6 waypoints) |

## Descriptive Runtime/Counter Relationships

### c_trap_001_t12.json

| counter | Pearson | Spearman |
|---|---:|---:|
| tangent_calls | 0.988988 | 0.630153 |
| recursive_calls | NA | NA |
| branch_expansions | 0.988988 | 0.630153 |
| max_recursion_depth | NA | NA |
| blocking_events | 0.974367 | 0.626341 |
| reblocking_events | 0.974121 | 0.626341 |
| fallback_calls | NA | NA |
| collision_tests | 0.969158 | 0.628919 |
| blocked_checks | -0.877776 | -0.629742 |

### sequential_staggered_blocking_001_t04.json

| counter | Pearson | Spearman |
|---|---:|---:|
| tangent_calls | NA | NA |
| recursive_calls | NA | NA |
| branch_expansions | 0.999987 | 0.695521 |
| max_recursion_depth | NA | NA |
| blocking_events | 0.999987 | 0.682574 |
| reblocking_events | 0.999987 | 0.682574 |
| fallback_calls | NA | NA |
| collision_tests | 0.999988 | 0.699854 |
| blocked_checks | -0.999987 | -0.695521 |

### sequential_staggered_blocking_001_t08.json

| counter | Pearson | Spearman |
|---|---:|---:|
| tangent_calls | NA | NA |
| recursive_calls | NA | NA |
| branch_expansions | 0.999944 | 0.600528 |
| max_recursion_depth | NA | NA |
| blocking_events | 0.999943 | 0.597208 |
| reblocking_events | 0.999943 | 0.597208 |
| fallback_calls | NA | NA |
| collision_tests | 0.999946 | 0.599781 |
| blocked_checks | -0.999944 | -0.600528 |

### sequential_staggered_blocking_001_t12.json

| counter | Pearson | Spearman |
|---|---:|---:|
| tangent_calls | NA | NA |
| recursive_calls | NA | NA |
| branch_expansions | 0.999908 | 0.527006 |
| max_recursion_depth | NA | NA |
| blocking_events | 0.999905 | 0.525351 |
| reblocking_events | 0.999905 | 0.525351 |
| fallback_calls | NA | NA |
| collision_tests | 0.999908 | 0.525935 |
| blocked_checks | -0.999908 | -0.527006 |

### asymmetric_corridor_001_t12.json

| counter | Pearson | Spearman |
|---|---:|---:|
| tangent_calls | NA | NA |
| recursive_calls | NA | NA |
| branch_expansions | 0.999906 | 0.611768 |
| max_recursion_depth | NA | NA |
| blocking_events | 0.999907 | 0.610336 |
| reblocking_events | 0.999907 | 0.610336 |
| fallback_calls | NA | NA |
| collision_tests | 0.999900 | 0.608645 |
| blocked_checks | -0.801005 | -0.526053 |

## Trace-Based 4-Worker Scheduling Estimate

THEORETICAL / TRACE-BASED ESTIMATE. This excludes process startup and IPC and is not an actual parallel benchmark.

| environment | serial pair s | ideal lower bound | simulated makespan | speedup |
|---|---:|---:|---:|---:|
| c_trap_001_t12.json | 0.228645 | 0.057161 | 0.057422 | 3.981828 |
| sequential_staggered_blocking_001_t04.json | 23.076978 | 5.769245 | 5.814029 | 3.969189 |
| sequential_staggered_blocking_001_t08.json | 58.086231 | 14.521558 | 17.380896 | 3.341958 |
| sequential_staggered_blocking_001_t12.json | 93.485973 | 23.371493 | 23.411802 | 3.993113 |
| asymmetric_corridor_001_t12.json | 35.543422 | 8.885855 | 9.676672 | 3.673104 |

## Unavailable Metrics

- exact fallback elapsed time
- true recursive-call tree depth, because the current proposed boundary-navigation path is not recursive
- exact branches producing final continuation versus rejected continuation inside Dijkstra without rewriting Dijkstra

## Factual Conclusions

- Sequential Staggered Blocking has the largest observed instrumented pair-time totals among these five cases.
- The diagnostic traces show whether runtime is concentrated by inspecting the top-pair shares and pairs-for-80% columns above.
- Recursive Python calls were not observed in the current proposed boundary-navigation implementation; branch work is represented by visible-exit and visibility-graph candidate checks.
- Fallback elapsed time is unavailable without rewriting fallback internals.
