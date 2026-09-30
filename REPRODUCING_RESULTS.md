# Reproducing And Inspecting Results

## Scope

The repository primarily publishes frozen evidence. Inspection and checksum verification do not require rerunning experiments. Exact wall-clock timing reproduction is not promised because timing depends on the operating system, Python runtime, hardware, and background load recorded with each campaign.

## Environment

The frozen Part I campaign records CPython 3.14.0 on Windows 11 with an Intel Core i9-13900K and 64 GB RAM. Reviewer-validation records used Python 3.13.9. Python dependencies available to the public tree are listed in `requirements.txt` and `pyproject.toml`.

Create an isolated environment and install dependencies according to local policy. No credential or external model service is required to inspect the released JSON, CSV, Markdown, SVG, PNG, or PDF artifacts.

## Campaign Entry Points

- `dataset_creator_app/generate_dataset.py`: controlled Part I dataset generator.
- `dataset_creator_app/composite_adversarial/generate_composite_adversarial.py`: composite dataset generator.
- `experiments/run_benchmark.py`: one Part I method/environment execution.
- `experiments/part2/generator/generate_part2_instances.py`: Part II instance generation wrapper.
- `experiments/part2/scripts/run_part2_primary.py`: Part II primary campaign.
- `experiments/part2/scripts/run_part2_proposed_diagnostics.py`: Proposed diagnostic campaign.
- `experiments/part2/scripts/run_part2_sanity_repetitions.py`: precommitted sanity repetitions.
- `experiments/reviewer_validation/scripts/run_reviewer_validation.py`: supplemental reviewer-validation campaign.
- `scripts/analysis/generate_publication_figures_revE.py`: publication-figure generation from frozen artifacts.

Read each campaign README and manifest before running a script. Some scripts represent complete campaign orchestration and can be computationally expensive.

## Safe Independent Runs

Do not overwrite files under the frozen result directories. For a single Part I check, provide a separate output directory, for example:

```powershell
python experiments/run_benchmark.py dataset_creator_app/dataset/c_trap_001_t04.json --method proposed --output-dir scratch/proposed_check
```

The new output is an independent run and must not be represented as part of the frozen campaign.

## Artifact Navigation

- Part I design and counts: `experiments/part1/README.md`.
- Part II design and counts: `experiments/part2/README.md`.
- Reviewer-validation design: `experiments/reviewer_validation/EXPERIMENT_PLAN.md`.
- Reviewer-validation summary: `experiments/reviewer_validation/analysis/REVIEWER_VALIDATION_FULL_SUMMARY.md`.
- Public provenance: `PROVENANCE.md`.
- Public release decisions: `PUBLIC_RELEASE_MANIFEST.md`.

## Checksum Verification

On PowerShell, compare each entry in `SHA256SUMS.txt` with `Get-FileHash -Algorithm SHA256`. On systems with GNU coreutils, run:

```sh
sha256sum --check SHA256SUMS.txt
```

The checksum file excludes itself. `.gitattributes` disables text normalization so committed bytes remain stable across platforms.
