# NFZ Benchmark Dataset Creator

Standalone generator for native NFZ environment JSON benchmark families. It writes
ordinary `nfz_env_v1` files and keeps benchmark identity in filenames and this
codebase, not in the JSON payload.

## Native Schema

The generator follows the representative native JSON shape from:

`<local-path>\outputs\environments\mission_env_20260807-2322_N1_1.json`

Generated files include:

- top-level `schema`, `is_segmented`, `segment_count`, `env`,
  duplicated `drone_configs`, `time_sync`, and `map_view`
- `env.airports`
- `env.sams`
- `env.drone_configs`
- `env.targets`

No benchmark-specific metadata is added to generated environment JSON.

## Usage

```powershell
python .\generate_dataset.py --seed 20260808 --families 1 --out dataset
```

This writes three cumulative target-count files for each topology:

```text
dataset/
  c_trap_001_t04.json
  c_trap_001_t08.json
  c_trap_001_t12.json
  sequential_staggered_blocking_001_t04.json
  sequential_staggered_blocking_001_t08.json
  sequential_staggered_blocking_001_t12.json
  asymmetric_corridor_001_t04.json
  asymmetric_corridor_001_t08.json
  asymmetric_corridor_001_t12.json
```

Target sets are cumulative within a family: T1-T4 are identical in the 4-, 8-,
and 12-target versions, and T1-T8 are identical in the 8- and 12-target
versions.

## Coordinate Model

Generation happens in a deterministic 150 by 150 local plane, then points are
encoded as native lat/lng positions around the geographic reference center from
the NFZ benchmark sample. The local plane is kilometers: circular NFZ radii are emitted
unchanged as native `range_km` values selected from `{1, 2, 5, 10, 15}`.

## Topologies

The generator currently creates:

- `c_trap`: 5 circular NFZs in one partial-overlap C-shaped chain with an open
  mouth and targets beyond the wrapped hull.
- `sequential_staggered_blocking`: 6 circular NFZs as 3 separated overlapping
  pairs, alternating high/low/high or low/high/low across the nominal route.
- `asymmetric_corridor`: 5 circular NFZs as opposing asymmetric 3-circle and
  2-circle clusters forming a traversable corridor.

Invalid random candidates are rejected by topology-specific validators and
regenerated from the same derived seed stream.
