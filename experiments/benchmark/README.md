# Common Benchmark Harness

The harness separates solver execution from mission outcome classification.

- `solver_completed`: true when the common solver call returns normally without raising an exception. A normal return can still describe an infeasible or incomplete mission.
- `mission_feasible`: true when the returned result is an operationally usable mission with at least one benchmark target serviced. Airport-only or empty routes, disconnected-airport cases, and no-target-service results are infeasible.
- `mission_success`: true when the feasible mission services all configured benchmark targets for the input environment. Partial service remains measurable but is not a complete benchmark success.
- `targets_serviced`: count of unique configured benchmark targets present in returned routes.
- `failure_reason`: concise explanation when `mission_feasible` or `mission_success` is false, when the harness can determine one.

The solver call, matrix values, routing behavior, timing boundaries, one-drone normalization, and native mission export are common across matrix methods.

