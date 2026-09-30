# Public Release Provenance

This repository is a clean public export. It does not contain the commit history or private URLs of the internal development and release-candidate repositories.

## Provenance Chain

| Artifact group | Internal source commit | Sanitized release-candidate commit | Public location |
|---|---|---|---|
| Dataset generator and Part I datasets | `5f26eb8a5119af9854a5d49de3f900821701a689` | `5bf57f8ae9a3bcc4cbcf07b7a9f4d46474fd3e47` | `dataset_creator_app/` |
| Part I campaign | `73b9a7b60fa892bbf2220e6a961c1393ab28fbf5` | `fa79039cfd93152a8caa5117bd4c4597ecae7d7c` | `experiments/benchmark/`, `experiments/methods/`, `experiments/main_benchmark_replications/`, `experiments/composite_adversarial_replications/`, and `experiments/diagnostics/` |
| Part II completed campaign | `df37f713d0320481dbd50e80ca49e919326a20f8` | `4bc5575f835394c71752b284db631a5456080b51` | `experiments/part2/` |
| Reviewer validation | `4bcace45ebbb4649f79dc978cdf5d380a53562f7` | `782201673d7ceaeb838eb0ddd58dcb9b589e0ede` | `experiments/reviewer_validation/` and `publication_figures_revE/` |

The current internal reviewer-validation HEAD was `9e3552db7452366d6f89589f96972ad0617bab18` when this release was prepared. The changes after the mapped reviewer source commit were confined to private prompt-response provenance; no scientific artifact in this public release changed.

The public Git commit is the commit containing this document. Its full SHA is reported with the release record and should be fixed by the immutable release tag.

## Part II Manifest Hashes

- Private source `experiments/part2/manifests/part2_dataset_manifest.json` SHA-256: `EBDD2A1B86741A266B78371C04C001FD4D2797E91E90C44EB2AA56F6CA053A58`.
- Sanitized/public `experiments/part2/manifests/part2_dataset_manifest.json` SHA-256: `3B5E5B0FF7518154D3A04274378D3DBC593724B5A7609FA29739CA70CECE94E7`.

Sanitation changed path and terminology metadata in the manifest, so those byte hashes are intentionally different. Representative source/public JSON comparisons confirmed identical numeric sequences for datasets, primary results, diagnostic records, and reviewer-validation records.

## Transformations

The release-candidate process replaced private repository names, machine paths, and release-facing internal terminology. This clean export additionally:

- removes private-candidate metadata and internal editorial planning material;
- removes the excluded editorial document from the reviewer-validation script's public precondition list;
- replaces two residual user-specific Python executable paths with `python` and one user-specific temporary-file path with `<temporary-directory>`;
- adds a sanitized copy of the frozen Part I runner with repository-relative defaults;
- expresses the shared benchmark planner root through the equivalent repository-relative `parent.parent.parent` path;
- annotates Part II manifest-hash scope without changing benchmark results;
- creates public documentation and checksums for the released tree.

Scientific numerical values, method identifiers, experiment counts, datasets, routes, and frozen result records were not changed by this public packaging pass.
