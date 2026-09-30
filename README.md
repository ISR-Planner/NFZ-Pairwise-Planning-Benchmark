# NFZ-Pairwise-Planning-Benchmark

Public benchmark artifacts supporting the paper "Benchmarking No-Fly-Zone-Aware Pairwise Cost Preprocessing for Multi-UAS Orienteering."

## Contents

- 12 Part I datasets: 9 controlled and 3 composite adversarial environments.
- 216 Part I executions: two repetitions of 108 method-environment conditions.
- 15 Part II cross-instance datasets.
- 135 Part II primary executions.
- 15 Proposed diagnostic executions.
- 6 precommitted sanity repetitions.
- Supplemental reviewer-validation records and publication figures.

## Directory Map

- `dataset_creator_app/`: Part I dataset generation, validation, and frozen datasets.
- `experiments/benchmark/`: common benchmark harness.
- `experiments/methods/`: Part I controlled Run 1 outputs and method adapters.
- `experiments/main_benchmark_replications/`: Part I controlled Run 2 outputs.
- `experiments/composite_adversarial_replications/`: both Part I composite runs.
- `experiments/diagnostics/`: Part I diagnostic evidence.
- `experiments/part2/`: Part II datasets, primary results, diagnostics, sanity repetitions, and manifests.
- `experiments/reviewer_validation/`: supplemental validation supporting Paper I claims.
- `publication_figures_revE/`: approved benchmark figure artifacts generated from frozen results.
- `path_planning_core/` and `server/solver/`: supporting planning and mission-solver code.

## Navigation And Reproduction

Start with [REPRODUCING_RESULTS.md](REPRODUCING_RESULTS.md). Frozen benchmark outputs must not be overwritten. Use a separate output directory for any independent rerun.

Public-to-private provenance anchors and sanitation scope are documented in [PROVENANCE.md](PROVENANCE.md). The exact public inventory and omission decisions are documented in [PUBLIC_RELEASE_MANIFEST.md](PUBLIC_RELEASE_MANIFEST.md) and `PUBLIC_RELEASE_MANIFEST.json`. File integrity is recorded in `SHA256SUMS.txt`.

The internal development repositories remain separate provenance anchors. They are not required for ordinary use or inspection of this public release.

## Citation

Citation metadata for this artifact is provided in [CITATION.cff](CITATION.cff). The associated paper is:

Johnny L. Chapman, Sr., Kamal Ali, Brandon Newton, Amaru Nicholson, Brent Thoma, and Kershard Wooten, "Benchmarking No-Fly-Zone-Aware Pairwise Cost Preprocessing for Multi-UAS Orienteering."

Final venue, DOI, and publication metadata are intentionally omitted until verified.

## Distribution

Distribution Statement A. Approved for public release; distribution is unlimited. Approved AFRL-2026-1658 24-09-2026.

## License Status

No public software license has been added. Distribution Statement A authorizes public release but is not a software license. Reuse rights beyond applicable law require authorization from the rights holder.
