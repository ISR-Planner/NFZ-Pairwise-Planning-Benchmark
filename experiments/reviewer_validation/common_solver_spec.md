# Common Mission-Solver Specification

This specification is based on the active frozen benchmark harness and solver
code at branch base `3683ea5727a8c2a3b67ddd1ef025e8f3fc6c2bf8`.

## Benchmark Entry Point

The common benchmark entry point is `experiments.benchmark.runner.run_one`.
Each benchmark condition:

1. loads one native NFZ environment JSON with
   `experiments.benchmark.native_io.load_native_environment`;
2. builds a pairwise distance matrix through the selected matrix builder;
3. injects that prebuilt matrix with
   `experiments.benchmark.planner_bridge.prebuilt_matrix_cache`;
4. solves through `server.solver.solver_bridge.solve_mission_with_allocation`;
5. writes the native mission JSON and one benchmark summary row.

Supplemental reviewer-validation runners use the same matrix-injection and
solver-status semantics unless explicitly documented.

## Objective

The active solver constructs a route for the enabled UAS using the supplied
pairwise matrix and the existing Mission mission-allocation/orienteering pipeline.
The benchmark reports mission completion, feasible partial service, target
service count, and mission distance rather than claiming a globally optimal
continuous vehicle trajectory.

## Fuel / Budget Model

The frozen benchmark enables only D1 through `_single_drone_configs`.
All other configured drones are disabled. D1 uses the fuel budget stored in the
environment's `drone_configs` after the active solver normalizes fuel-budget
keys. Matrix costs are interpreted in the same kilometer distance units used by
the frozen benchmark methods.

## Start And Recovery Assumptions

D1 starts from the configured `start_airport`; for the controlled benchmark
environments this is the single airport `A1`. The route returns according to
the solver's existing route construction and mission-export logic. Supplemental
stress environments use the same one-airport, one-enabled-UAS convention.

## Target Selection And Ordering

The solver may choose target order based on the supplied method-specific
matrix. Therefore, target order may change by method. The benchmark records the
sequence, serviced-target count, route distance, and mission status produced by
the common solver for each matrix.

## Exact Versus Heuristic Status

The pairwise matrix builders are deterministic implementations of their stated
geometric approximations or method adaptations. The downstream mission solver is
the repository's active mission-planning implementation, not an independent
proof of globally optimal continuous multi-UAS behavior. The manuscript should
describe returned paths as geometric paths unless vehicle dynamics are
explicitly modeled.

## Stopping Rule

Each condition is executed once for primary frozen benchmark rows and the
predeclared number of repetitions for reviewer-validation timing experiments.
Supplemental scripts save each record immediately. A condition is retried only
for infrastructure failure, not for infeasible or partial mission results.

## Infinite Matrix Entries

Matrix builders use the large sentinel cost `99999.0` through the
`routing_model.unavailable_cost` field where present. The allocator and solver
treat such entries as unavailable. Connectivity summaries define a finite pair
as a directed non-self matrix entry whose value is below the unavailable-cost
sentinel.

## Mission Feasibility And Success

The frozen harness classifies:

- `mission_feasible`: at least one benchmark target is serviced;
- `mission_success`: all benchmark targets are serviced;
- `targets_serviced`: unique benchmark targets in the returned route;
- `failure_reason`: recorded explanation for infeasible or partial missions.

## Mission Distance

The benchmark mission distance is the sum of route distances reported by the
solver route data. Pairwise preprocessing time and solver time remain separate.

## Tie-Breaking

Tie-breaking follows the active solver and method implementations. Visibility
Graph and Grid A* methods sort candidate graph edges deterministically by cost
and index where their implementations expose explicit tie ordering. No
additional tie-breaking is introduced in reviewer-validation scripts.
