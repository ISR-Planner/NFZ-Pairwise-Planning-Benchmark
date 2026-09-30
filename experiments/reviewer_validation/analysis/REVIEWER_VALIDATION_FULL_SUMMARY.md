# Reviewer-Validation Full Campaign Summary

Campaign directory: `experiments\reviewer_validation\results\run_01_20260813-201359`
Branch: `paper1-reviewer-validation`
Base commit: `3683ea5727a8c2a3b67ddd1ef025e8f3fc6c2bf8`

## Execution Counts

- Cached VG recorded executions: `45`
- Resolution sensitivity recorded executions: `72`
- Conservatism stress environments: `5`
- High-fidelity pair checks: `9`

## Connectivity

Frozen connectivity analysis rows: `351`.
Connectivity is reported at matrix level and is separate from mission success.

## Cached Visibility Graph

- C-Trap: mean total preprocessing `3.533762` s; connectivity agreement with original VG: `True`.
- Sequential Staggered Blocking: mean total preprocessing `4.564846` s; connectivity agreement with original VG: `True`.
- Asymmetric Corridor: mean total preprocessing `2.974798` s; connectivity agreement with original VG: `True`.

## Resolution Sensitivity

### visibility_graph
- 24: n=9, success=9/9, mean matrix=1.539034 s.
- 48: n=9, success=9/9, mean matrix=10.149613 s.
- 72: n=9, success=9/9, mean matrix=32.459654 s.
- 144: n=9, success=9/9, mean matrix=240.995540 s.

### grid_astar
- 0.25: n=9, success=9/9, mean matrix=7.375140 s.
- 0.5: n=9, success=9/9, mean matrix=1.766149 s.
- 1: n=9, success=9/9, mean matrix=0.439467 s.
- 2: n=9, success=9/9, mean matrix=0.117064 s.

## Conservatism Stress

- target_in_concavity_seed_91001: native finite=20, Proposed finite=12, extra area=289.045 km^2, targets inside wrapped hull=`T1`.
- transit_through_concavity_seed_91002: native finite=20, Proposed finite=12, extra area=422.277 km^2, targets inside wrapped hull=`T2`.
- increasing_conservatism_low_seed_91003: native finite=20, Proposed finite=12, extra area=222.338 km^2, targets inside wrapped hull=`T1`.
- increasing_conservatism_medium_seed_91004: native finite=20, Proposed finite=20, extra area=0.000 km^2, targets inside wrapped hull=``.
- increasing_conservatism_high_seed_91005: native finite=20, Proposed finite=20, extra area=0.000 km^2, targets inside wrapped hull=``.

## High-Fidelity Reference

The selected high-fidelity reference is polygonal, not mathematically exact. Max absolute distance difference: `0.005323749` km; max relative error: `0.000040274`.

## Timing Protocol

- Python: `3.13.9` at `python`
- Platform: `Windows-11-10.0.26200-SP0`
- CPU: `13th Gen Intel(R) Core(TM) i9-13900K`
- RAM: `63.75` GB
- Warm-up: cached VG uses one unrecorded matrix warm-up per environment; sensitivity uses zero warm-up; conservatism/high-fidelity are deterministic supplemental checks.
- Order: deterministic by topology, instance, method family, parameter, repetition.

## Frozen-Artifact Integrity

Integrity after campaign: `True`.

## Artifacts

- repeated_timing_summary_csv: `experiments\reviewer_validation\analysis\reviewer_validation_repeated_timing_summary.csv`
- repeated_timing_summary_json: `experiments\reviewer_validation\analysis\reviewer_validation_repeated_timing_summary.json`
- resolution_sensitivity: `experiments\reviewer_validation\figures\resolution_sensitivity_tradeoff.png`
- cached_vg: `experiments\reviewer_validation\figures\cached_vg_preprocessing_time.png`
