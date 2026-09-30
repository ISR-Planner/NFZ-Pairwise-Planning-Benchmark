# Clean Composite Replication Run 2 Final Report

Run 2 timestamp: `20260809-222140`
Run 2 directory: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140`

## Decision

- Classification: **COMPOSITE ADVERSARIAL STRESS RUN 2**
- Severe composite timing regime reproduced: True
- Functional mismatches: 0
- Protected hash mismatches before archival cleanup: 0

## Proposed Run 1 vs Run 2

| targets | Run1 s | Run2 s | Run2/Run1 | % diff | Run2 s/pair |
| --- | --- | --- | --- | --- | --- |
| 4 | 410.634 | 416.773 | 1.0150 | 1.495 | 20.839 |
| 8 | 1347.741 | 1343.403 | 0.9968 | -0.322 | 18.658 |
| 12 | 2984.781 | 2971.729 | 0.9956 | -0.437 | 19.050 |

## Visibility Graph Run 1 vs Run 2

| targets | Run1 s | Run2 s | Run2/Run1 | % diff | Run2 s/pair | Clean VG/Proposed |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | 344.511 | 348.086 | 1.0104 | 1.038 | 17.404 | 0.8352 |
| 8 | 1133.771 | 1129.785 | 0.9965 | -0.352 | 15.691 | 0.8410 |
| 12 | 2516.261 | 2500.276 | 0.9936 | -0.635 | 16.027 | 0.8414 |

## Integrity

- Input SHA-256 equivalence: True
- Protected before/after hashes match: True
- Original adversarial geometry remained byte-identical.
- Original nine controlled JSONs remained byte-identical.
- Original 81-run benchmark artifacts remained byte-identical through the post-run integrity gate.
- Method source remained unchanged.
- multi-UAS mission planner solver source remained unchanged.

## Archive / Cleanup

- Run 1 archived: True
- Archive directory: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_01_20260809-183402`
- Archive SHA-256 verification: True
- Run 1 removed from active results area: True

## Run 2 Artifacts

- Results CSV: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140\results\composite_adversarial_run_02_20260809-222140.csv`
- Results JSON: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140\results\composite_adversarial_run_02_20260809-222140.json`
- Log: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140\logs\composite_adversarial_run_02_20260809-222140.log`
- Analysis CSV: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140\analysis\composite_adversarial_run_02_20260809-222140_analysis.csv`
- Analysis Markdown: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140\analysis\composite_adversarial_run_02_20260809-222140_analysis.md`
- Comparison JSON: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140\analysis\composite_adversarial_run_02_20260809-222140_run1_comparison.json`
- Final report: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140\analysis\composite_adversarial_run_02_20260809-222140_final_report.md`
- Integrity files: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140\integrity`
- Mission outputs: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140\outputs`

