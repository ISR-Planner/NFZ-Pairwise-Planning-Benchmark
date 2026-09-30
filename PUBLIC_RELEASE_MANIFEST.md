# Public Release Manifest

## Release Scope

This clean export contains the reviewed Paper I datasets, benchmark outputs, supporting source, diagnostics, reviewer-validation evidence, and figure artifacts. It contains no manuscript source or output, private correspondence, PA package, credential, private URL, or inherited Git history.

## Verified Counts

| Artifact | Count |
|---|---:|
| Part I controlled datasets | 9 |
| Part I composite datasets | 3 |
| Part I controlled Run 1 executions | 81 |
| Part I controlled Run 2 executions | 81 |
| Part I composite Run 1 executions | 27 |
| Part I composite Run 2 executions | 27 |
| Part II datasets | 15 |
| Part II primary executions | 135 |
| Part II Proposed diagnostic executions | 15 |
| Part II sanity repetitions | 6 |

## Part I Private-Manifest Reconciliation

The frozen private Part I manifest listed 351 artifacts. Ten transient or derived files were intentionally omitted from the public release, while the required runner was included as a sanitized public copy. The private manifest itself is not published because it does not describe this public tree.

| Previously missing path | Classification | Public action | Rationale |
|---|---|---|---|
| `experiments/composite_adversarial_replications/run_01_20260809-183402/logs/composite_adversarial_run_01_20260809-183402.log` | LOG/TRANSIENT | Omitted | Execution transcript is not needed to inspect the frozen outputs. |
| `experiments/composite_adversarial_replications/run_02_20260809-222140/logs/composite_adversarial_run_02_20260809-222140.log` | LOG/TRANSIENT | Omitted | Execution transcript is not needed to inspect the frozen outputs. |
| `experiments/diagnostics/proposed_branching/results/proposed_branching_diagnostic_20260809-165543.log` | LOG/TRANSIENT | Omitted | Structured diagnostic outputs and analysis are released. |
| `experiments/main_benchmark_replications/run_02_20260810-015756/logs/main_benchmark_run_02_20260810-015756.log` | LOG/TRANSIENT | Omitted | Structured Run 2 outputs are released. |
| `experiments/results/main_benchmark_run_20260809-160107.csv` | OPTIONAL/DERIVED ANALYSIS OUTPUT | Omitted | The public tree contains all 81 Run 1 mission records and per-method summaries. |
| `experiments/results/main_benchmark_run_20260809-160107.json` | OPTIONAL/DERIVED ANALYSIS OUTPUT | Omitted | Duplicates information available from released structured records. |
| `experiments/results/main_benchmark_run_20260809-160107.log` | LOG/TRANSIENT | Omitted | Execution transcript is not required for artifact inspection. |
| `experiments/results/main_benchmark_run_20260809-160107_analysis.csv` | OPTIONAL/DERIVED ANALYSIS OUTPUT | Omitted | Derived from released structured Run 1 outputs. |
| `experiments/results/main_benchmark_run_20260809-160107_analysis.md` | OPTIONAL/DERIVED ANALYSIS OUTPUT | Omitted | Narrative derived analysis is not required to reproduce the manuscript tables. |
| `experiments/results/main_benchmark_run_20260809-160107_rows.jsonl` | OPTIONAL/DERIVED ANALYSIS OUTPUT | Omitted | Per-method summaries and mission records provide the released evidence. |
| `experiments/run_benchmark.py` | REQUIRED FOR REPRODUCTION | Included and sanitized | Frozen campaign entry point; private absolute default path replaced by a repository-relative default. |

## Reviewer-Validation Decision

- PUBLIC AND NECESSARY: experiment plan, analyses, connectivity results, cached-VG results, sensitivity results, conservatism results, high-fidelity checks, campaign status, and validation hashes.
- PUBLIC BUT OPTIONAL: raw supplemental records, mission outputs, and figure-generation source retained for independent inspection.
- SANITIZE BEFORE PUBLICATION: two Python executable fields were generalized to `python`.
- INTERNAL-ONLY: the manuscript revision-planning document was excluded.

One Part I integrity-manifest path into a user-profile temporary directory was generalized to `<temporary-directory>`.

`PUBLIC_RELEASE_MANIFEST.json` records the same machine-readable release decisions. `SHA256SUMS.txt` records every public file except itself.
