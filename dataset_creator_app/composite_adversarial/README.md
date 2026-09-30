# Composite Adversarial NFZ Dataset Family

This directory contains a separate fourth benchmark-topology candidate. It does not modify or replace the existing benchmark datasets.

- Topology name: Composite Adversarial Stress
- File stem: `composite_adversarial`
- Seed: `20260809`
- Workspace: 150 km x 150 km local Cartesian, converted to native lat/lng at JSON output time
- Native NFZ-aware mission schema: `nfz_env_v1`; the literal field `sams` is retained for compatibility
- Outputs: `dataset/composite_adversarial_001_t04.json`, `dataset/composite_adversarial_001_t08.json`, `dataset/composite_adversarial_001_t12.json`

## Motifs

The layout contains 16 total NFZs:

- C-Trap: NFZ01-NFZ05, one connected C-like overlapping chain with an open mouth facing A1.
- Sequential Staggered Blocking: NFZ06-NFZ11, three separate overlapping two-NFZ clusters in a low/high/low mirror of the existing high/low/high motif.
- Asymmetric Corridor: NFZ12-NFZ16, an opposing upper three-NFZ cluster and lower two-NFZ cluster with a traversable asymmetric corridor.

## Coupling Intent

The motifs are not independent samples pasted onto one map. A1 faces the C-Trap opening. The C-Trap geometry makes the lower-side escape comparatively natural, and the first sequential blocker is placed on that lower downstream side. The sequential low/high/low pattern then causes alternating lateral redirection, leaving the route poorly aligned with the asymmetric corridor throat, which sits below the upper three-NFZ cluster.

The motifs remain recognizable and distinct. Cross-motif circles do not overlap, and overlap-cluster wrapping yields multiple wrapped regions rather than one collapsed obstacle.

## Targets

Targets are cumulative:

- t04 contains T1-T4.
- t08 preserves T1-T4 exactly and adds T5-T8.
- t12 preserves T1-T8 exactly and adds T9-T12.

Minimum target spacing is 17.117243 km. Minimum target-to-circle clearance is 3.341664 km. Minimum target-to-wrapped-hull clearance is 3.350685 km.

## Validation

Validation artifacts are under `validation/`:

- `composite_adversarial_validation.json`
- `composite_adversarial_validation.md`
- `original_dataset_hashes_before.json`
- `original_dataset_hashes_after.json`
- `previews/composite_adversarial_001_t04.svg`
- `previews/composite_adversarial_001_t08.svg`
- `previews/composite_adversarial_001_t12.svg`

No benchmark method, planner, route optimizer, method runtime, route length, or branch-count result is used to generate, rank, or validate this dataset. No geometric stress score was used for candidate ranking; the generator emits one deterministic geometric candidate and validates it.

The free-space check is an independent 1 km occupancy-grid connectivity screen. It confirms that every target has a reachable free-space connection from A1 without invoking any benchmark planner.
