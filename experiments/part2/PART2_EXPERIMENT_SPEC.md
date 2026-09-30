# Part II Experiment Specification

## Status

This document specifies Part II only. It does not authorize dataset generation,
benchmark execution, algorithm edits, commits, merges, or pushes.

Part I is frozen evidence and must remain unchanged.

## Immutable Part I Provenance

- Dataset branch: `dataset-creator-app`
- Dataset commit: `5f26eb8a5119af9854a5d49de3f900821701a689`
- Experiment branch: `benchmark-part1-experiments`
- Experiment commit: `73b9a7b60fa892bbf2220e6a961c1393ab28fbf5`
- Part I base: `b2e312a3877d9dc0b231bf1582c537790013daf1`
- Repository: `NFZ-Pairwise-Planning-Benchmark` public artifact release
- Frozen execution environment: Intel Core i9-13900K, 64 GB RAM, Windows 11 Pro,
  CPython 3.14.0, CPU-only

Part I scope:

- 108 unique method-environment conditions
- 216 executions
- 9 primary methods
- D1 only
- Matrix timing recorded separately from solver timing

## Audit Summary

### Current Repository State

The audit was performed in:

`<local-path>\NFZ-Pairwise-Planning-Benchmark\NFZ-Pairwise-Planning-Benchmark`

Relevant branch state:

- Current branch: `benchmark-part1-experiments`
- Current HEAD: `73b9a7b60fa892bbf2220e6a961c1393ab28fbf5`
- Remote at the time of the private audit: not retained in the public artifact release
- `benchmark-part1-experiments` and `dataset-creator-app` share common ancestor
  `b2e312a3877d9dc0b231bf1582c537790013daf1`
- No local or remote `benchmark-part2-generalization` branch was found during audit

This makes `benchmark-part1-experiments` the safest Part II branch base because it
contains the frozen Part I harness, methods, results, diagnostics, and manifests.

### Dataset Generator

Frozen generator source:

`dataset_creator_app/generate_dataset.py` from commit
`5f26eb8a5119af9854a5d49de3f900821701a689`

Key generator behavior:

- Native NFZ-aware mission JSON schema: `nfz_env_v1`
- Canonical controlled output directory: `dataset/`
- Workspace: 150 km by 150 km
- NFZ radii: `1, 2, 5, 10, 15` km
- Blocking radii subset: `5, 10, 15` km
- Target spacing: 15 km
- Target circle clearance: 2 km
- Target hull clearance: 1 km
- Topologies:
  - `c_trap`
  - `sequential_staggered_blocking`
  - `asymmetric_corridor`
- For each topology family, the generator writes cumulative `t04`, `t08`, and
  `t12` files.

Seed function:

```python
digest = hashlib.sha256(f"{base_seed}:{topology}:{family_index}".encode("ascii")).digest()
return int.from_bytes(digest[:8], "big")
```

The SHA-256-derived 64-bit seed is then passed to `random.Random`, which uses
Python's deterministic Mersenne Twister implementation. The proposed sequential
master seeds are acceptable because adjacent integer master seeds are hashed
together with topology and family index before reaching the PRNG. This decorrelates
the actual per-topology/per-family streams sufficiently for this deterministic
benchmark design.

### Benchmark Harness

Primary benchmark entry points:

- `experiments/run_benchmark.py`
- `experiments/benchmark/runner.py`
- `experiments/benchmark/matrix_builders.py`
- `experiments/benchmark/native_io.py`
- `experiments/benchmark/planner_bridge.py`

Execution flow:

1. `load_native_environment()` parses an `nfz_env_v1` or raw environment JSON.
2. `run_one()` selects a matrix builder by method name.
3. Matrix construction is timed with `time.perf_counter()` around
   `builder.build(native_env.env)` only.
4. The solver is prepared separately and receives the already-built matrix through
   `prebuilt_matrix_cache()`.
5. D1 is forced as the only enabled aircraft by `_single_drone_configs()`.
6. Solver timing is recorded separately.
7. A mission JSON and a `benchmark_summary.jsonl` row are written.
8. Outcome fields include `solver_completed`, `mission_feasible`,
   `mission_success`, `targets_serviced`, `route_distance`, `points`,
   `failure_reason`, and `error`.

The Part II primary campaign should reuse this harness pattern for all nine
primary methods.

### Method Registry

The Part I registry exposes the required primary methods:

1. `proposed`
2. `euclidean`
3. `collision_rejection`
4. `visibility_graph`
5. `grid_astar`
6. `appatt_raw`
7. `appatt_bspline`
8. `tig_raw`
9. `tig_bezier`

`proposed_parallel` exists only as diagnostic/source context and must not be
counted as a Part II primary method.

### Proposed Implementation

Primary proposed wrapper:

`experiments/methods/proposed/method.py`

It calls:

`server.solver.sam_distance_matrix.calculate_sam_aware_matrix(..., use_supabase_cache=False)`

Core proposed matrix behavior:

- Project environment into local kilometers.
- Normalize SAM records.
- Wrap SAMs through `path_planning_core.sam_wrapping.wrap_sams`.
- Exclude targets inside individual SAMs or wrapped hulls.
- Build all directed non-self waypoint distances.
- For each pair, use a circle-intersection screen first.
- If blocked, call `path_planning_core.boundary_navigation.plan_path`.
- Store SAM-avoiding paths and 99999.0 unavailable sentinels.

Boundary navigation branch behavior:

- Direct clear path: `method == "direct"` or a direct variant.
- Single-polygon boundary navigation returns method strings containing
  `CW via ... tangent`, `CCW via ... tangent`, or `FALLBACK ...`.
- Multi-polygon navigation builds a visibility graph and runs Dijkstra, returning
  method strings beginning with `visibility-graph`.
- Failures return `INVALID: ...`, `no_path_found`, or `error: ...`.

### Existing Proposed Diagnostics

Existing diagnostic tree:

- `experiments/diagnostics/proposed_branching/code/proposed_instrumented.py`
- `experiments/diagnostics/proposed_branching/code/diagnostic_runner.py`
- `experiments/diagnostics/proposed_branching/code/README.md`

The diagnostic implementation is suitable as a Part II starting point because it:

- Lives outside `experiments/methods/proposed`.
- Reproduces the frozen serial proposed matrix flow in a diagnostic-only
  calculator.
- Temporarily monkey-patches read-only boundary-navigation helper functions during
  each directed pair, then restores them.
- Records per-pair timing and counters.
- Already performs equivalence checks against frozen Part I proposed outputs in
  the diagnostic runner.

Important limitations:

- It is a reproduction/wrapper, not the primary proposed method itself.
- Monkey-patching must stay serial and diagnostic-only.
- Exact fallback elapsed time is unavailable without rewriting fallback internals.
- The current proposed implementation is not recursive in Python call structure,
  so recursive counters are expected to remain zero unless the algorithm changes.
- `wrap_sams()` returns wrapped polygons and the original SAM list as metadata,
  not explicit cluster assignments. Cluster counts must therefore be computed in
  diagnostic code using the existing read-only clustering helper or an equivalent
  diagnostic-only procedure.

No blocker was found. Instrumentation can be used safely if it remains separated
from primary timing and passes the regression gate defined below.

## Scientific Question

Part II asks:

Do the topology-dependent tradeoffs observed in Part I persist across independently
generated instances of the same topology classes, and can those tradeoffs be
explained by the pairwise planning branches exercised by the geometry?

Part II is a cross-instance generalization experiment, not a full timing-repetition
experiment.

## Campaign Design

### Fixed Variables

Part II must preserve the controlled Part I benchmark rules:

- 150 km by 150 km workspace
- NFZ radius set: `1, 2, 5, 10, 15` km
- Same topology definitions
- Same target spacing rules
- Same target/NFZ clearance rules
- Same convex-hull admissibility rules
- Same airport placement rules
- Same mission solver
- Same algorithm parameters
- Same Visibility Graph implementation and resolution
- Same Grid A* implementation and resolution
- Same APPATT and TIG benchmark adaptations
- One enabled UAS: D1 only
- CPU-only execution
- Same machine/software environment where possible

### Independent Variable

The only intended independent variable in the primary campaign is geometry
realization within each controlled topology family.

### Topologies

1. C-Trap
2. Sequential Staggered Blocking
3. Asymmetric Corridor

### Mission Size

- `t12` only
- 1 airport plus 12 targets
- 13 mission nodes
- 156 directed non-self relationships per environment

### Final Seed List

Use these five deterministic master seeds:

1. `20260813`
2. `20260814`
3. `20260815`
4. `20260816`
5. `20260817`

The same conceptual seed list is shared across the three topology families. The
generator derives topology-specific random streams through SHA-256 using
`base_seed`, `topology`, and `family_index`.

### Dataset Count

- 5 instances per topology
- 3 topologies
- 15 new `t12` environments total

### Dataset Naming Convention

Because Part II uses five explicit master seeds, filenames should encode both
the topology and seed to avoid ambiguity and accidental collisions with the
generator's default `001` family naming.

Required pattern:

```text
{topology}_s{seed}_i{instance_index:02d}_t12.json
```

Examples:

```text
c_trap_s20260813_i01_t12.json
sequential_staggered_blocking_s20260815_i03_t12.json
asymmetric_corridor_s20260817_i05_t12.json
```

Each output file must have a manifest record that maps:

- Part II filename
- Topology
- Master seed
- Instance index
- Generator family index used internally
- Original generator output filename, if the wrapper stages default names first
- SHA-256 of the final JSON file

### Dataset Generation Plan

Do not edit the frozen generator. For Part II implementation, add an independent
wrapper under `experiments/part2/scripts/` that:

1. Uses the exact generator source copied from dataset commit
   `5f26eb8a5119af9854a5d49de3f900821701a689`.
2. Generates the required topology/seed instances in a staging directory.
3. Selects only `t12` outputs.
4. Renames them to the Part II naming convention.
5. Writes a manifest with seeds, hashes, source commit, and generation command.
6. Leaves JSON payloads unchanged after generation.

The generator source should be copied exactly into:

```text
experiments/part2/generator_source/dataset_creator_app/
```

The Part II wrapper code is separate from that exact source copy.

### Primary Methods

1. `proposed`
2. `euclidean`
3. `collision_rejection`
4. `visibility_graph`
5. `grid_astar`
6. `appatt_raw`
7. `appatt_bspline`
8. `tig_raw`
9. `tig_bezier`

### Primary Execution Count

```text
5 instances x 3 topologies x 9 methods = 135 primary executions
```

Do not run two repetitions of all 135 conditions.

### Predefined Sanity-Check Repetition

Run a small predefined repetition subset after the primary run, not selected
based on results:

- Instance index: `i03`
- Master seed: `20260815`
- Topologies: all three
- Methods: `proposed` and `visibility_graph`

Count:

```text
3 topologies x 2 methods = 6 repeat executions
```

Purpose:

- Confirm Part II path/timing stability on a small fixed subset.
- Check that diagnostic additions did not introduce outcome instability.
- Avoid post hoc selection of surprising cases.

Total planned executions:

```text
135 primary + 6 sanity repetitions = 141 executions
```

## Metrics

Retain all Part I metrics:

- `matrix_build_time_seconds`
- `solver_time_seconds`
- `solver_completed`
- `mission_feasible`
- `mission_success`
- `targets_serviced`
- `targets_expected`
- `points`
- `route_distance`
- `failure_reason`
- `error`
- mission output path
- environment filename
- method name
- topology
- target count

For every environment, compute:

- `visibility_graph / proposed` matrix-time ratio

This ratio is descriptive. It must not be preinterpreted as a win/loss score.

## Proposed Diagnostic Schema

Run Proposed diagnostics separately from primary timing. The diagnostic run should
produce one row per directed non-self pair.

Required pair-level fields:

| Field | Description |
|---|---|
| `run_id` | Diagnostic run identifier |
| `environment_filename` | Part II environment JSON filename |
| `topology` | Controlled topology name |
| `seed` | Master seed |
| `instance_index` | 1 through 5 |
| `target_count` | Always 12 for Part II primary environments |
| `node_count` | Expected 13 unless target exclusion changes available nodes |
| `directed_pair_count` | Expected 156 per full 13-node environment |
| `source` | Source waypoint id |
| `destination` | Destination waypoint id |
| `pair_index` | Stable directed-pair index in matrix traversal order |
| `pair_class` | Normalized class described below |
| `raw_method` | Raw method string returned by boundary navigation or `direct` |
| `direct_path_blocked` | Result of the proposed circle-intersection screen |
| `available` | Whether the pair has a finite usable matrix distance |
| `pair_time_seconds` | Instrumented pair elapsed time |
| `path_distance_km` | Final matrix distance for the pair |
| `path_point_count` | Number of path points stored for the pair |
| `native_nfz_count` | Number of original SAM/NFZ circles |
| `overlapping_cluster_count` | Number of overlapping NFZ clusters, diagnostic-only |
| `singleton_region_count` | Number of clusters containing one NFZ |
| `multi_nfz_cluster_count` | Number of clusters containing more than one NFZ |
| `wrapped_region_count` | Number of resulting wrapped planning polygons |
| `relevant_blocking_region_count` | Number of wrapped regions observed to block the pair |
| `visibility_graph_calls` | Count of `_build_visibility_graph` calls for the pair |
| `visibility_edge_clearance_checks` | Count if hookable without behavior changes, otherwise null |
| `tangent_calls` | Count of `_find_tangent_vertices` calls |
| `tangent_candidates_generated` | Candidate tangent count if hookable |
| `tangent_time_seconds` | Diagnostic-only tangent elapsed time |
| `collision_tests` | Segment/circle/polygon test count observed by hooks |
| `branch_expansions` | Boundary/visibility expansion checks observed by hooks |
| `branches_valid` | Path validation successes observed by hooks |
| `branches_discarded` | Path validation failures observed by hooks |
| `blocking_events` | Observed blocker events |
| `unique_blockers` | Number of distinct observed blockers |
| `reblocking_events` | Blocking events after the first blocker event |
| `blocking_sequence` | Ordered blocker labels, stored as a delimited string or JSON array |
| `fallback_calls` | Fallback observed for the pair |
| `fallback_success` | True/false/null according to observable result |

Normalize branch classification as follows:

| `pair_class` | Rule |
|---|---|
| `direct_unobstructed` | The proposed circle-intersection screen says the pair is not blocked. |
| `single_region_tangent_boundary` | The pair is blocked, finite, does not call visibility graph, and raw method contains tangent/boundary navigation such as `CW via`, `CCW via`, or `FALLBACK`. |
| `multi_region_vg_dijkstra` | The pair is finite and raw method starts with `visibility-graph`, or diagnostic hooks observed at least one `_build_visibility_graph` call. |
| `failed` | The pair is unavailable, has distance `99999.0`, or raw method begins with `INVALID`, `no_path_found`, or `error`. |
| `boundary_direct_after_circle_screen` | The circle screen flagged the pair as blocked but wrapped-polygon navigation returned a direct finite path. Report this separately rather than forcing it into `direct_unobstructed`. |
| `other_boundary` | Any finite blocked pair that does not match the categories above. This should be investigated if nonzero. |

Required environment-level Proposed diagnostic summary:

- environment filename
- topology
- seed
- instance index
- total pair count
- pair counts and percentages by `pair_class`
- aggregate pair time by `pair_class`
- mean, median, min, max pair time by `pair_class`
- total and per-class tangent calls
- total and per-class visibility graph calls
- total and per-class collision tests
- wrapped region count
- overlapping cluster count
- singleton and multi-NFZ cluster counts
- slowest 10 directed pairs
- cumulative share of pair time contributed by slowest 1, 5, and 10 pairs

## Regression Gate

Before any Part II experiment run, diagnostic or harness additions must prove
that they do not change algorithm behavior.

Minimum gate:

- Compare uninstrumented frozen proposed behavior against instrumented proposed
  behavior on representative frozen Part I environments:
  - `c_trap_001_t12.json`
  - `sequential_staggered_blocking_001_t12.json`
  - `asymmetric_corridor_001_t12.json`

Preferred gate:

- Run the comparison on all 9 controlled Part I environments.

Required comparisons:

- Matrix labels identical
- Matrix shape identical
- Available/unavailable pair status identical
- Maximum finite matrix-distance difference <= `1e-6` km
- Stored path keys identical
- Stored path point counts identical
- Maximum stored path coordinate difference <= `1e-6` km
- Solver route sequence identical
- Mission success classification identical
- Mission feasible classification identical
- Targets serviced identical
- Mission route distance difference <= `1e-6` km
- Failure reason identical, including null-vs-null

The existing diagnostic runner already performs similar matrix/path/route checks
and should be generalized rather than replaced wholesale.

If the regression gate fails, Part II execution must stop until the cause is
understood.

## Timing Strategy

Use two timing modes.

### Mode 1: Primary Benchmark Timing

- Use the normal Part I harness and uninstrumented method builders.
- Use `proposed` exactly as the primary Part I method wrapper.
- Record matrix timing and solver timing as Part I did.
- Do not include diagnostic monkey-patching, branch counters, or extra geometry
  scans inside primary matrix timing.

### Mode 2: Proposed Diagnostic Branch-Usage Run

- Run only Proposed diagnostic instrumentation.
- Run serially.
- Do not use diagnostic timing as the primary matrix time.
- Use diagnostic pair timing only to describe mechanism and workload distribution.
- Record instrumentation overhead separately by comparing diagnostic elapsed time
  against primary uninstrumented Proposed time on the same environments.

Report overhead as:

- diagnostic matrix elapsed / primary proposed matrix elapsed
- absolute overhead seconds
- whether outcome equivalence passed

Do not silently compare fully instrumented Part II timing against uninstrumented
Part I timing.

## Result Naming Convention

Primary run:

```text
experiments/part2/results/primary/{run_id}/
```

Where:

```text
run_id = part2_generalization_primary_{YYYYMMDD-HHMMSS}
```

Primary summary artifacts:

```text
experiments/part2/results/primary/{run_id}/part2_generalization_primary_{YYYYMMDD-HHMMSS}.csv
experiments/part2/results/primary/{run_id}/part2_generalization_primary_{YYYYMMDD-HHMMSS}.json
experiments/part2/results/primary/{run_id}/part2_generalization_primary_{YYYYMMDD-HHMMSS}_rows.jsonl
experiments/part2/results/primary/{run_id}/part2_generalization_primary_{YYYYMMDD-HHMMSS}.log
```

Per-method outputs:

```text
experiments/part2/results/primary/{run_id}/outputs/{method}/benchmark_summary.jsonl
experiments/part2/results/primary/{run_id}/outputs/{method}/missions/
```

Sanity repetition run:

```text
experiments/part2/results/sanity_repetition/{run_id}/
```

Diagnostic run:

```text
experiments/part2/diagnostics/proposed_branch_usage/{run_id}/
```

Diagnostic artifacts:

```text
part2_proposed_pair_diagnostics_{YYYYMMDD-HHMMSS}.csv
part2_proposed_branch_usage_summary_{YYYYMMDD-HHMMSS}.csv
part2_proposed_branch_usage_summary_{YYYYMMDD-HHMMSS}.json
part2_proposed_branch_usage_analysis_{YYYYMMDD-HHMMSS}.md
part2_proposed_branch_usage_{YYYYMMDD-HHMMSS}.log
```

Regression gate output:

```text
experiments/part2/diagnostics/regression_gate/{run_id}/
```

## Manifest and Provenance Requirements

Create manifests for:

1. Generator source provenance
2. Generated dataset provenance
3. Primary run provenance
4. Sanity repetition provenance
5. Proposed diagnostic provenance
6. Analysis provenance

Each manifest must record:

- Repository URL
- Part II branch name
- Part II commit at execution time
- Part I experiment source branch and commit
- Dataset generator source branch and commit
- Base commit
- Python version
- OS
- CPU
- RAM
- CPU-only declaration
- Command lines
- Working directory
- Run timestamp
- Seeds
- Topology list
- Method list
- Environment JSON SHA-256 hashes
- Source file SHA-256 hashes for changed/new Part II scripts
- Output artifact paths and hashes
- Regression-gate result
- Whether any diagnostic timing was excluded from primary timing

Part II provenance must identify both:

- Part I experiment commit:
  `73b9a7b60fa892bbf2220e6a961c1393ab28fbf5`
- Dataset generator commit:
  `5f26eb8a5119af9854a5d49de3f900821701a689`

## Analysis Plan

Do not design p-value or significance-test claims. Five instances per topology
are for qualitative persistence and descriptive generalization, not a statistically
powered population sample.

Required tables:

1. Dataset manifest table:
   - filename, topology, seed, instance index, JSON hash, NFZ count, wrapped
     region count, target count
2. Primary execution table:
   - one row per environment-method execution with all retained Part I metrics
3. Topology-method summary:
   - individual values, mean, median, min, max, range
4. Proposed vs Visibility Graph ratio table:
   - all five `VG/proposed` ratios per topology
   - mean, min, max, range
5. Proposed branch composition:
   - pair counts and percentages by class for every environment
6. Proposed branch timing:
   - aggregate and per-pair timing by branch class
7. Geometry/workload table:
   - wrapped regions, overlapping clusters, multi-NFZ clusters, visibility graph
     calls, tangent calls, collision tests
8. Sanity repetition table:
   - paired repeat deltas for Proposed and Visibility Graph on the predefined
     `i03` subset
9. Regression gate table:
   - environment, pass/fail, maximum matrix/path/route differences

Required plots:

1. Matrix construction time by topology and method, showing individual instances
2. Proposed and Visibility Graph matrix time paired by environment
3. `VG/proposed` ratio by topology
4. Proposed branch composition stacked bars
5. Fraction of `multi_region_vg_dijkstra` pairs vs Proposed matrix time
6. Fraction of `multi_region_vg_dijkstra` pairs vs `VG/proposed` ratio
7. Wrapped region count and multi-NFZ cluster count vs Proposed matrix time
8. Slowest-pair contribution plots for Proposed diagnostics
9. Sanity repetition deltas for the predefined subset

Analysis interpretation must allow either:

- Stable topology-dependent crossover behavior; or
- Large within-topology variation showing topology label alone is insufficient.

## Repository Plan

Create a new branch only when implementation begins:

```text
benchmark-part2-generalization
```

Recommended base:

```text
benchmark-part1-experiments @ 73b9a7b60fa892bbf2220e6a961c1393ab28fbf5
```

Rationale:

- Contains frozen Part I experiment code, outputs, diagnostics, and manifests.
- Shares clean base `b2e312a3877d9dc0b231bf1582c537790013daf1` with the dataset
  branch.
- Avoids modifying Part I files.
- Avoids casually merging `dataset-creator-app` into the Part I branch.
- Allows Part II to add only isolated new material under `experiments/part2/`.

Recommended structure:

```text
experiments/
  part1/
    [frozen, do not alter]
  part2/
    PART2_EXPERIMENT_SPEC.md
    README.md
    generator_source/
      dataset_creator_app/
        README.md
        generate_dataset.py
    scripts/
      generate_part2_datasets.py
      run_part2_primary.py
      run_part2_sanity_repetition.py
      run_proposed_branch_usage.py
      run_regression_gate.py
      analyze_part2_results.py
    datasets/
      controlled_t12/
    results/
      primary/
      sanity_repetition/
    diagnostics/
      regression_gate/
      proposed_branch_usage/
    manifests/
    analysis/
```

Only `experiments/part2/` should be modified for Part II unless a future audited
implementation task identifies a specific non-Part-I shared helper that must be
added. Existing Part I files under `experiments/part1/`, `experiments/results/`,
`experiments/methods/`, `experiments/main_benchmark_replications/`, and
`experiments/composite_adversarial_replications/` must not be overwritten or
edited.

## Preconditions Before Running Part II

Before dataset generation or benchmark execution:

1. Create `benchmark-part2-generalization` from
   `73b9a7b60fa892bbf2220e6a961c1393ab28fbf5`.
2. Copy the frozen generator source from
   `5f26eb8a5119af9854a5d49de3f900821701a689` into
   `experiments/part2/generator_source/dataset_creator_app/`.
3. Add Part II wrapper scripts under `experiments/part2/scripts/`.
4. Generate only the 15 `t12` Part II controlled environments.
5. Write dataset and generator manifests.
6. Run the regression gate.
7. Stop if the regression gate fails.
8. Run primary benchmark timing with uninstrumented builders.
9. Run the predefined sanity repetition subset.
10. Run Proposed diagnostic branch-usage mode separately.
11. Run analysis.
12. Write provenance manifests for every generated artifact.

## Blocking Issues

No blocking issue was found during this audit.

Known guardrails:

- Do not modify Part I.
- Do not modify primary algorithm decisions.
- Do not include diagnostic overhead in primary timing.
- Do not rely on topology labels alone if within-topology variation is large.
- Treat branch counters as descriptive diagnostics, not causal proof by themselves.

## Concise Campaign Summary

- Topologies: C-Trap, Sequential Staggered Blocking, Asymmetric Corridor
- Instances per topology: 5
- Mission size: t12 only, 13 mission nodes, 156 directed non-self pairs
- Primary methods: 9
- Primary executions: 135
- Sanity repetitions: 6 predefined repeat executions on seed `20260815` / `i03`
- Total planned executions: 141
- Seed list: `20260813`, `20260814`, `20260815`, `20260816`, `20260817`
- Part I experiment parent: `benchmark-part1-experiments`
  `73b9a7b60fa892bbf2220e6a961c1393ab28fbf5`
- Dataset-generator source: `dataset-creator-app`
  `5f26eb8a5119af9854a5d49de3f900821701a689`
- Instrumentation strategy: separate serial Proposed diagnostic wrapper with
  regression equivalence gate
- Timing strategy: primary uninstrumented timing plus separate diagnostic overhead
  reporting
- Blocking issues: none found
