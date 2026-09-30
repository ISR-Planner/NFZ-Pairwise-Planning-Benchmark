# Part II Functional Regression Gate

Created at: `2026-08-12T23:25:50.487087+00:00`

This gate compares frozen Part I Proposed outputs against the Part II
instrumented Proposed diagnostic wrapper. Timing overhead is recorded but
does not determine pass/fail.

Tolerance: `1e-06` km

## Overall Result

PART II FUNCTIONAL REGRESSION GATE: PASS

## Cases

| case | pass | reference s | diagnostic s | overhead % | max matrix delta | max path delta | route delta |
|---|---|---:|---:|---:|---:|---:|---:|
| C-Trap t12 | True | 0.223939 | 0.232272 | 3.721 | 0 | 0 | 0 |
| Sequential Staggered Blocking t12 | True | 59.967959 | 90.047385 | 50.159 | 0 | 0 | 0 |
| Asymmetric Corridor t12 | True | 24.487227 | 34.476186 | 40.793 | 0 | 0 | 0 |
| Composite Adversarial t12 | True | 2971.728721 | 5293.733881 | 78.137 | 0 | 0 | 0 |

## Details

### C-Trap t12

- Reference environment: `<local-path>\NFZ-Pairwise-Planning-Benchmark\NFZ-Pairwise-Planning-Benchmark\experiments\main_benchmark_replications\run_02_20260810-015756\input_snapshot\c_trap_001_t12.json`
- Reference frozen result: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\main_benchmark_replications\run_02_20260810-015756\outputs\proposed\missions\c_trap_001_t12__proposed__run_02_20260810-015756__mission_seg_20260810-0200_N1_1.json`
- Instrumented result: `<local-path>\NFZ-Pairwise-Planning-Benchmark\NFZ-Pairwise-Planning-Benchmark\experiments\part2\regression\outputs\part2_regression_gate_20260812-215351\c_trap_t12_environment_summary.json`
- Matrix equality/pass: `True`
- Path equality/pass: `True`
- Route equality/pass: `True`
- Mission outcome equality/pass: `True`
- Distance delta: `0.0`
- Diagnostic overhead percent: `3.7209256836323195`
- Overall: `PASS`

### Sequential Staggered Blocking t12

- Reference environment: `<local-path>\NFZ-Pairwise-Planning-Benchmark\NFZ-Pairwise-Planning-Benchmark\experiments\main_benchmark_replications\run_02_20260810-015756\input_snapshot\sequential_staggered_blocking_001_t12.json`
- Reference frozen result: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\main_benchmark_replications\run_02_20260810-015756\outputs\proposed\missions\sequential_staggered_blocking_001_t12__proposed__run_02_20260810-015756__mission_seg_20260810-0204_N1_1.json`
- Instrumented result: `<local-path>\NFZ-Pairwise-Planning-Benchmark\NFZ-Pairwise-Planning-Benchmark\experiments\part2\regression\outputs\part2_regression_gate_20260812-215351\sequential_staggered_blocking_t12_environment_summary.json`
- Matrix equality/pass: `True`
- Path equality/pass: `True`
- Route equality/pass: `True`
- Mission outcome equality/pass: `True`
- Distance delta: `0.0`
- Diagnostic overhead percent: `50.1591635801108`
- Overall: `PASS`

### Asymmetric Corridor t12

- Reference environment: `<local-path>\NFZ-Pairwise-Planning-Benchmark\NFZ-Pairwise-Planning-Benchmark\experiments\main_benchmark_replications\run_02_20260810-015756\input_snapshot\asymmetric_corridor_001_t12.json`
- Reference frozen result: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\main_benchmark_replications\run_02_20260810-015756\outputs\proposed\missions\asymmetric_corridor_001_t12__proposed__run_02_20260810-015756__mission_seg_20260810-0207_N1_1.json`
- Instrumented result: `<local-path>\NFZ-Pairwise-Planning-Benchmark\NFZ-Pairwise-Planning-Benchmark\experiments\part2\regression\outputs\part2_regression_gate_20260812-215351\asymmetric_corridor_t12_environment_summary.json`
- Matrix equality/pass: `True`
- Path equality/pass: `True`
- Route equality/pass: `True`
- Mission outcome equality/pass: `True`
- Distance delta: `0.0`
- Diagnostic overhead percent: `40.79252590915736`
- Overall: `PASS`

### Composite Adversarial t12

- Reference environment: `<local-path>\NFZ-Pairwise-Planning-Benchmark\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140\input_snapshot\composite_adversarial_001_t12.json`
- Reference frozen result: `<local-path>\NFZ-Pairwise-Planning-Benchmark\experiments\composite_adversarial_replications\run_02_20260809-222140\outputs\proposed\missions\composite_adversarial_001_t12__proposed__mission_seg_20260810-0017_N1_1.json`
- Instrumented result: `<local-path>\NFZ-Pairwise-Planning-Benchmark\NFZ-Pairwise-Planning-Benchmark\experiments\part2\regression\outputs\part2_regression_gate_20260812-215351\composite_adversarial_t12_environment_summary.json`
- Matrix equality/pass: `True`
- Path equality/pass: `True`
- Route equality/pass: `True`
- Mission outcome equality/pass: `True`
- Distance delta: `0.0`
- Diagnostic overhead percent: `78.13651166409221`
- Overall: `PASS`
