# Part II Cross-Instance Generalization

Part II tests whether the topology-dependent tradeoffs observed in frozen Part I
persist across independently generated instances of the controlled topology
families, and whether Proposed behavior can be explained by directed-pair branch
usage.

Part I is immutable. Do not edit Part I datasets, results, manifests, diagnostic
outputs, or primary method behavior for Part II.

## Provenance

- Part I experiment parent: `benchmark-part1-experiments`
  `73b9a7b60fa892bbf2220e6a961c1393ab28fbf5`
- Part I base: `b2e312a3877d9dc0b231bf1582c537790013daf1`
- Frozen dataset-generator source branch: `dataset-creator-app`
- Frozen dataset-generator source commit:
  `5f26eb8a5119af9854a5d49de3f900821701a689`

## Design

- Topologies: C-Trap, Sequential Staggered Blocking, Asymmetric Corridor
- Mission size: `t12` only
- Planned environments: 15 total
- Precommitted seeds: `20260813`, `20260814`, `20260815`, `20260816`,
  `20260817`
- Planned primary executions: 135
- Later predefined sanity repetitions: 6

The seed-to-instance mapping is recorded before generation in
`config/part2_instances.json`.

## Timing Modes

Primary timing uses the existing benchmark harness with uninstrumented method
builders. These timings are the official Part II matrix-construction timings.

Diagnostic timing uses Proposed-only instrumentation to classify branch behavior
for each directed pair. Diagnostic timing is reported separately and must not be
substituted for primary timing in manuscript comparisons.

## Current Status

Part II datasets, validation artifacts, primary Run 01 benchmark results,
Proposed diagnostic branch-usage results, and sanity repetitions exist.

- Part II datasets generated: 15
- Part II primary executions performed: 135
- Part II diagnostic executions performed: 15
- Part II sanity repetitions performed: 6
