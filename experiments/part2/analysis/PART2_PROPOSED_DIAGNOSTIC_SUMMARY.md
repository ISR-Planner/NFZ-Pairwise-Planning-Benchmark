# Part II Proposed Diagnostic Summary

This summary is diagnostic and descriptive only. It must not replace the frozen uninstrumented primary timing results.

## Campaign

- Run: `run_01_20260812-204803`
- Campaign ID: `part2_proposed_diagnostic_20260812-204803`
- Campaign directory: `experiments\part2\results\diagnostics\proposed_branching\run_01_20260812-204803`
- Diagnostic environments: `15`
- Pair records: `2340`
- Failed Proposed pairs: `0`
- Functional equivalence: `PASS`
- Manifest CSV: `experiments\part2\manifests\part2_proposed_diagnostic_manifest.csv`
- Manifest JSON: `experiments\part2\manifests\part2_proposed_diagnostic_manifest.json`

## Environment Summary

| topology | instance | Proposed primary s | VG primary s | VG/Proposed | direct % | single-region % | multi-region % | failed | block checks | reblocks | diagnostic s | overhead % |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C-Trap | i01 | 0.250755 | 36.089628 | 143.924035 | 84.62 | 15.38 | 0.00 | 0 | 732 | 2338 | 0.267330 | 6.61 |
| C-Trap | i02 | 0.180698 | 34.223092 | 189.393966 | 84.62 | 15.38 | 0.00 | 0 | 730 | 2072 | 0.198886 | 10.07 |
| C-Trap | i03 | 0.205891 | 29.620449 | 143.864920 | 84.62 | 15.38 | 0.00 | 0 | 724 | 2257 | 0.227531 | 10.51 |
| C-Trap | i04 | 0.239891 | 39.303504 | 163.838873 | 84.62 | 15.38 | 0.00 | 0 | 726 | 2376 | 0.261671 | 9.08 |
| C-Trap | i05 | 0.245538 | 36.339386 | 147.998790 | 84.62 | 15.38 | 0.00 | 0 | 732 | 2404 | 0.266890 | 8.70 |
| Sequential Staggered Blocking | i01 | 60.347027 | 36.926242 | 0.611898 | 89.74 | 0.00 | 10.26 | 0 | 872 | 357754 | 92.708662 | 53.63 |
| Sequential Staggered Blocking | i02 | 50.671469 | 26.629931 | 0.525541 | 91.03 | 0.00 | 8.97 | 0 | 868 | 319204 | 80.364394 | 58.60 |
| Sequential Staggered Blocking | i03 | 65.476345 | 50.647142 | 0.773518 | 88.46 | 0.00 | 11.54 | 0 | 864 | 412142 | 103.354444 | 57.85 |
| Sequential Staggered Blocking | i04 | 70.666051 | 33.527622 | 0.474452 | 87.18 | 0.00 | 12.82 | 0 | 852 | 458546 | 112.977712 | 59.88 |
| Sequential Staggered Blocking | i05 | 66.903624 | 26.962237 | 0.403001 | 88.46 | 0.00 | 11.54 | 0 | 870 | 407734 | 103.911403 | 55.32 |
| Asymmetric Corridor | i01 | 17.975794 | 26.600082 | 1.479772 | 89.74 | 0.00 | 10.26 | 0 | 744 | 165346 | 25.510712 | 41.92 |
| Asymmetric Corridor | i02 | 18.297067 | 15.305814 | 0.836517 | 89.74 | 0.00 | 10.26 | 0 | 736 | 168692 | 26.265496 | 43.55 |
| Asymmetric Corridor | i03 | 19.779254 | 16.964069 | 0.857670 | 88.46 | 0.00 | 11.54 | 0 | 744 | 185012 | 28.658124 | 44.89 |
| Asymmetric Corridor | i04 | 14.405558 | 22.061759 | 1.531476 | 89.74 | 0.00 | 10.26 | 0 | 748 | 140530 | 20.456468 | 42.00 |
| Asymmetric Corridor | i05 | 19.158307 | 27.250808 | 1.422402 | 88.46 | 0.00 | 11.54 | 0 | 750 | 190848 | 28.158869 | 46.98 |

## Topology Patterns

### C-Trap

- Branch pattern: same branch-count pattern across all five instances.
- Direct % by instance: `84.62;84.62;84.62;84.62;84.62`.
- Single-region % by instance: `15.38;15.38;15.38;15.38;15.38`.
- Multi-region % by instance: `0.00;0.00;0.00;0.00;0.00`.
- Primary VG/Proposed ratios by instance: `143.924;189.394;143.865;163.839;147.999`.

### Sequential Staggered Blocking

- Branch pattern: branch-count pattern varies across instances.
- Direct % by instance: `89.74;91.03;88.46;87.18;88.46`.
- Single-region % by instance: `0.00;0.00;0.00;0.00;0.00`.
- Multi-region % by instance: `10.26;8.97;11.54;12.82;11.54`.
- Primary VG/Proposed ratios by instance: `0.612;0.526;0.774;0.474;0.403`.

### Asymmetric Corridor

- Branch pattern: branch-count pattern varies across instances.
- Direct % by instance: `89.74;89.74;88.46;89.74;88.46`.
- Single-region % by instance: `0.00;0.00;0.00;0.00;0.00`.
- Multi-region % by instance: `10.26;10.26;11.54;10.26;11.54`.
- Primary VG/Proposed ratios by instance: `1.480;0.837;0.858;1.531;1.422`.

## Asymmetric Crossover

- VG faster than Proposed instances: `i02;i03`.
- Proposed faster than or equal to VG instances: `i01;i04;i05`.
- Mean multi-region %, VG-faster group: `10.897435897435898`.
- Mean multi-region %, Proposed-faster group: `10.683760683760683`.
- Mean blocking checks, VG-faster group: `740.0`.
- Mean blocking checks, Proposed-faster group: `747.3333333333334`.

## Exploratory Associations

These are descriptive associations across 15 environments only; no significance tests were run.

| metric | n | Pearson | Spearman |
|---|---:|---:|---:|
| multi-region pair % | 15 | 0.737309 | 0.857996 |
| blocking checks | 15 | 0.963448 | 0.898034 |
| reblocking checks | 15 | 0.985067 | 0.982143 |
| wrapped region count | 15 | 0.958220 | 0.944911 |
| tangent calls | 15 | -0.709670 | -0.818317 |
| relevant blocking region count | 15 | 0.983044 | 0.976510 |

## Part I Diagnostic Context

| topology | direct % | single-region % | multi-region % | failed | diagnostic s | block checks | reblocks |
|---|---:|---:|---:|---:|---:|---:|---:|
| C-Trap | 84.62 | 15.38 | 0.00 | 0 | 0.28919889999815496 | 2276 | 2252 |
| Sequential Staggered Blocking | 89.74 | 0.00 | 10.26 | 0 | 93.48965719999978 | 357020 | 357004 |
| Asymmetric Corridor | 85.90 | 0.00 | 14.10 | 0 | 35.54616449999594 | 227796 | 227774 |

## Guardrails

- Primary executions added: `0`
- Proposed diagnostic executions: `15`
- Sanity repetitions: `0`
- `proposed_parallel` executions: `0`
- Dataset files modified: `NO`
- Part I files modified: `NO`

## Unavailable Counters

- `visibility_edge_clearance_checks` and `tangent_exit_check_count` are recorded as unavailable by the validated wrapper because collecting them would require algorithm changes.
