# Part II Sanity Repetition Summary

These six repetitions use the uninstrumented primary benchmark path. They are a reproducibility sanity check, not a new statistical sample.

## Campaign

- Run: `run_01_20260812-211108`
- Campaign ID: `part2_sanity_repetition_20260812-211108`
- Campaign directory: `experiments\part2\results\sanity\run_01_20260812-211108`
- Expected executions: `6`
- Completed executions: `6`
- Functional mismatches: `0`
- Diagnostics enabled: `NO`
- Manifest CSV: `experiments\part2\manifests\part2_sanity_manifest.csv`
- Manifest JSON: `experiments\part2\manifests\part2_sanity_manifest.json`

## Six-Row Comparison

| topology | method | primary matrix s | repeat matrix s | delta % | primary distance km | repeat distance km | functional match | ordering preserved |
|---|---|---:|---:|---:|---:|---:|---|---|
| C-Trap | proposed | 0.205891 | 0.206023 | 0.06 | 432.655352 | 432.655352 | True | True |
| C-Trap | visibility_graph | 29.620449 | 29.482993 | -0.46 | 432.655352 | 432.655352 | True | True |
| Sequential Staggered Blocking | proposed | 65.476345 | 65.575653 | 0.15 | 443.585470 | 443.585470 | True | True |
| Sequential Staggered Blocking | visibility_graph | 50.647142 | 50.279515 | -0.73 | 443.585470 | 443.585470 | True | True |
| Asymmetric Corridor | proposed | 19.779254 | 19.670925 | -0.55 | 436.913184 | 436.913184 | True | True |
| Asymmetric Corridor | visibility_graph | 16.964069 | 17.132814 | 0.99 | 436.913184 | 436.913184 | True | True |

## Notes

- Timing differences are descriptive only, especially for short C-Trap Proposed runtimes.
- Mission distance, matrix values, path outputs, and route sequence matched the frozen primary outputs within the configured tolerance.
- No diagnostic counters, branch tracing, or `proposed_parallel` executions were used.

## Guardrails

- Part I files modified: `NO`
- Part II datasets modified: `NO`
- Primary results modified: `NO`
- Diagnostic results modified: `NO`
