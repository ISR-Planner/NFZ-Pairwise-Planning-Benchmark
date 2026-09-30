# Part II Dataset Validation

This report covers dataset generation and geometry validation only. No benchmark methods, Proposed diagnostics, or mission solver executions were run.

| topology | instance | seed | NFZs | components | targets | min target spacing km | min NFZ clearance km | min wrapped-hull clearance km | topology | admissibility | independence |
|---|---|---:|---:|---|---:|---:|---:|---:|---|---|---|
| C-Trap | i01 | 20260813 | 5 | 5 | 12 | 15.315778 | 28.213260 | 27.029476 | PASS | PASS | PASS |
| Sequential Staggered Blocking | i01 | 20260813 | 6 | 2+2+2 | 12 | 15.563206 | 18.852563 | 18.852892 | PASS | PASS | PASS |
| Asymmetric Corridor | i01 | 20260813 | 5 | 3+2 | 12 | 15.777428 | 23.288284 | 23.291717 | PASS | PASS | PASS |
| C-Trap | i02 | 20260814 | 5 | 5 | 12 | 15.593519 | 27.301148 | 27.306379 | PASS | PASS | PASS |
| Sequential Staggered Blocking | i02 | 20260814 | 6 | 2+2+2 | 12 | 15.348038 | 11.436447 | 11.436483 | PASS | PASS | PASS |
| Asymmetric Corridor | i02 | 20260814 | 5 | 2+3 | 12 | 16.306601 | 12.683196 | 12.689581 | PASS | PASS | PASS |
| C-Trap | i03 | 20260815 | 5 | 5 | 12 | 15.194092 | 31.173556 | 31.172800 | PASS | PASS | PASS |
| Sequential Staggered Blocking | i03 | 20260815 | 6 | 2+2+2 | 12 | 15.025653 | 10.520519 | 10.279726 | PASS | PASS | PASS |
| Asymmetric Corridor | i03 | 20260815 | 5 | 3+2 | 12 | 15.267249 | 15.101944 | 15.109484 | PASS | PASS | PASS |
| C-Trap | i04 | 20260816 | 5 | 5 | 12 | 15.420232 | 19.223316 | 19.062683 | PASS | PASS | PASS |
| Sequential Staggered Blocking | i04 | 20260816 | 6 | 2+2+2 | 12 | 15.109336 | 10.734540 | 10.737997 | PASS | PASS | PASS |
| Asymmetric Corridor | i04 | 20260816 | 5 | 3+2 | 12 | 15.855101 | 12.102669 | 12.106978 | PASS | PASS | PASS |
| C-Trap | i05 | 20260817 | 5 | 5 | 12 | 15.147920 | 18.725175 | 18.692841 | PASS | PASS | PASS |
| Sequential Staggered Blocking | i05 | 20260817 | 6 | 2+2+2 | 12 | 15.278115 | 9.331300 | 9.333049 | PASS | PASS | PASS |
| Asymmetric Corridor | i05 | 20260817 | 5 | 3+2 | 12 | 15.315913 | 11.364035 | 11.374676 | PASS | PASS | PASS |

## Summary

- Instances generated: `15`
- Topology failures: `0`
- Admissibility failures: `0`
- Duplicate Part II geometries: `0`
- Duplicates of Part I controlled geometry: `0`
- Topology degeneration observed: `NO`
- Seed failures: `NONE`
- Seed replacements performed: `NONE`

## Preview Artifacts

- Per-environment previews: `experiments/part2/datasets/previews/`
- Contact sheets: `experiments/part2/datasets/previews/contact_sheet_*.svg`
