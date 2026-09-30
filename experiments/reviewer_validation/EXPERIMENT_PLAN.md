# Reviewer-Validation Experiment Plan

Branch: `paper1-reviewer-validation`

Base commit: `3683ea5727a8c2a3b67ddd1ef025e8f3fc6c2bf8`

This plan is frozen before generating any new comparative reviewer-validation
results. The existing Part I and Part II primary benchmark artifacts are
treated as immutable evidence. All outputs from this plan are supplemental and
remain under `experiments/reviewer_validation/`.

## A. Frozen Primary Benchmark

The primary benchmark remains unchanged.

- Part I controlled and composite campaigns: 216 executions.
- Part II primary generalization campaign: 135 executions.
- Total frozen primary executions: 351.

No Part I or Part II environments, result files, mission outputs, analysis
tables, manifests, seeds, or method definitions will be overwritten or replaced.
New results are supplementary reviewer validation only.

## B. Connectivity Analysis From Frozen Artifacts

Connectivity analysis will be derived from frozen mission/result artifacts
wherever the stored distance matrix is present. No rerun is permitted merely to
obtain a metric already recoverable from stored files.

For each supported method/environment artifact, record:

- total directed non-self pairs;
- finite directed pairs;
- finite-pair percentage;
- unavailable directed pairs;
- airport-reachable targets from the recorded D1 start airport;
- reverse reachability to the recorded D1 start airport;
- strongly connected component count and largest strongly connected component;
- stored path count where the method records explicit paths;
- excluded targets recorded by the matrix builder;
- method-specific failure reason or mission status;
- path-validation or smoothing-loss evidence when directly supported.

Pair loss will not be attributed to convex wrapping unless the artifact contains
evidence supporting that causal claim.

## C. Cached Visibility Graph Supplement

VG-cached is a supplemental baseline. The original pairwise Visibility Graph
baseline remains unchanged.

Implementation design:

1. polygonize NFZs once per environment;
2. build static obstacle-boundary visibility once per environment;
3. reuse the static graph for every source/destination query;
4. add source/destination visibility per query;
5. solve each query with Dijkstra;
6. perform the same final path validation as the original polygonal VG code.

Scope:

- all 15 Part II t12 environments under `experiments/part2/datasets/controlled_t12/`;
- 3 recorded repetitions per environment;
- one unrecorded warm-up per environment.

Recorded fields:

- static graph construction time;
- matrix-query time;
- total preprocessing time;
- finite-pair percentage;
- solver outcome;
- mission distance;
- route-distance agreement with the original frozen VG record;
- connectivity agreement with the original frozen VG record.

Before campaign execution, the cached VG implementation will be regression
checked against the original VG for every Part II t12 environment.

## D. Resolution Sensitivity

Sensitivity uses only the fixed Part II i03 instances:

- `ctrap_i03_t12`
  (`experiments/part2/datasets/controlled_t12/c_trap/ctrap_i03_t12.json`);
- `sequential_i03_t12`
  (`experiments/part2/datasets/controlled_t12/sequential_staggered_blocking/sequential_i03_t12.json`);
- `asymmetric_i03_t12`
  (`experiments/part2/datasets/controlled_t12/asymmetric_corridor/asymmetric_i03_t12.json`).

Visibility Graph circle resolutions:

- 24 vertices/circle;
- 48 vertices/circle;
- 72 vertices/circle;
- 144 vertices/circle.

Grid A* resolutions:

- 0.25 km;
- 0.5 km;
- 1.0 km;
- 2.0 km.

Original engineered operating points:

- Visibility Graph: 72 vertices/circle.
- Grid A*: 1.0 km.

Repetitions:

- 3 recorded repetitions per topology/parameter/method-family combination.
- Total recorded executions: 3 topologies x 4 parameter values x 2 method
  families x 3 repetitions = 72.

Recorded fields:

- preprocessing time;
- solver time;
- finite-pair percentage;
- complete mission success;
- targets serviced;
- mission distance;
- path-validation failures where supported.

Parameters will not be tuned after seeing results.

## E. Convex-Wrapping Conservatism / Concavity Stress Test

This is an applicability-boundary experiment. It is not a correction to the
primary benchmark and should not be used to protect the Proposed method from
unfavorable cases.

Five deterministic stress environments will be generated and frozen before
comparative results are inspected:

1. `target_in_concavity_seed_91001`;
2. `transit_through_concavity_seed_91002`;
3. `increasing_conservatism_low_seed_91003`;
4. `increasing_conservatism_medium_seed_91004`;
5. `increasing_conservatism_high_seed_91005`.

Each environment intentionally places legally free native-circle space inside a
convex planning hull induced by overlapping circular restricted regions.

Comparisons:

- native-reference planner: high-resolution polygonal VG against original
  circular NFZs, 720 vertices/circle;
- Proposed planner: existing convex-wrapping Proposed matrix builder with zero
  added buffer, unchanged from the primary benchmark.

Recorded fields:

- native NFZ disk area, using deterministic high-resolution polygonal union;
- wrapped obstacle area, using the actual Proposed wrapped polygon output;
- additional area excluded by convex wrapping;
- percentage otherwise usable local free space removed;
- native-reference finite directed pairs;
- Proposed finite directed pairs;
- relationships excluded by the conservative representation;
- targets rendered inaccessible by the conservative representation;
- route inflation where both methods connect.

A pair rejected by Proposed under its declared conservative planning domain is
reported as conservatism, not as an algorithmic failure.

## F. High-Fidelity Reference

The repository will first be inspected for a mathematically exact
circular-obstacle shortest-path implementation. If none is present, the
reference will be a clearly identified very-high-resolution polygonal
Visibility Graph.

Predeclared fallback reference:

- 720 vertices/circle polygonal VG;
- never described as mathematically exact.

Selected comparison subset:

- environments: the three fixed Part II i03 t12 environments listed in section D;
- directed pairs per environment:
  - `A1 -> T1`;
  - `T3 -> T8`;
  - `T6 -> T12`.

Metrics:

- connectivity agreement with 72-vertex VG;
- absolute distance difference;
- relative distance error;
- computation cost.

## G. Timing Protocol

For every new reviewer-validation run, record:

- CPU;
- RAM;
- OS;
- Python executable/version;
- timer function: `time.perf_counter`;
- process reuse: one Python process per campaign phase unless otherwise noted;
- warm-up count;
- recorded repetition count;
- method order;
- whether order is randomized;
- garbage-collection policy;
- caching persistence;
- background-process policy;
- CPU-affinity policy.

Historical Part I timing details that are not stored in the frozen artifacts
will not be reconstructed.

## H. Statistics

For new repeated timing results, report:

- individual repetitions;
- mean;
- sample standard deviation where at least two values exist;
- minimum;
- maximum;
- 95 percent confidence interval where statistically appropriate.

Repeated timings on one environment are treated as repeated measurements of
that environment/method configuration, not as independent mission environments.

## I. Archival Protection

Before any new experiment:

- hash protected Part I and Part II datasets/results;
- record hashes in `experiments/reviewer_validation/validation/`;
- verify no frozen file changes are present.

After every campaign, integrity verification will be repeated.

No frozen result file may be overwritten.
