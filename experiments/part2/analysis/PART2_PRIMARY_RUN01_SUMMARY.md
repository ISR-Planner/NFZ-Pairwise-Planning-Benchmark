# Part II Primary Run 01 Summary

This summary is descriptive only. Proposed diagnostic instrumentation and sanity repetitions were not run.

## Campaign

- Run: `run_01_20260812-194711`
- Campaign ID: `part2_generalization_primary_20260812-194711`
- Campaign directory: `experiments/part2/results/primary/run_01_20260812-194711`
- Expected primary executions: `135`
- Primary manifest CSV: `experiments/part2/manifests/part2_primary_run01_manifest.csv`
- Primary manifest JSON: `experiments/part2/manifests/part2_primary_run01_manifest.json`

## Completion

| method | success / 15 | feasible / 15 |
|---|---:|---:|
| proposed | 15 / 15 | 15 / 15 |
| euclidean | 15 / 15 | 15 / 15 |
| collision_rejection | 8 / 15 | 10 / 15 |
| visibility_graph | 15 / 15 | 15 / 15 |
| grid_astar | 15 / 15 | 15 / 15 |
| appatt_raw | 15 / 15 | 15 / 15 |
| appatt_bspline | 8 / 15 | 10 / 15 |
| tig_raw | 15 / 15 | 15 / 15 |
| tig_bezier | 8 / 15 | 10 / 15 |

## Proposed Matrix Time

| topology | values sec | mean | min | max |
|---|---|---:|---:|---:|
| C-Trap | 0.2507547000423074;0.18069790001027286;0.20589070004643872;0.23989119997713715;0.24553840002045035 | 0.224555 | 0.180698 | 0.250755 |
| Sequential Staggered Blocking | 60.347027399984654;50.67146909999428;65.47634520003339;70.66605119995074;66.9036238999688 | 62.812903 | 50.671469 | 70.666051 |
| Asymmetric Corridor | 17.97579409996979;18.297066600003745;19.779253599990625;14.405557799967937;19.15830680000363 | 17.923196 | 14.405558 | 19.779254 |

## Visibility Graph Matrix Time

| topology | values sec | mean | min | max |
|---|---|---:|---:|---:|
| C-Trap | 36.08962809998775;34.22309189999942;29.62044899998;39.30350380000891;36.33938620000845 | 35.115212 | 29.620449 | 39.303504 |
| Sequential Staggered Blocking | 36.92624200001592;26.629931000003126;50.64714210003149;33.527622399968095;26.962237400002778 | 34.938635 | 26.629931 | 50.647142 |
| Asymmetric Corridor | 26.60008220002055;15.305814100021962;16.964069499983452;22.06175940000685;27.2508079999825 | 21.636507 | 15.305814 | 27.250808 |

## VG / Proposed Ratios

| topology | i01 | i02 | i03 | i04 | i05 | mean | min | max | range |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C-Trap | 143.924035 | 189.393966 | 143.864920 | 163.838873 | 147.998790 | 157.804117 | 143.864920 | 189.393966 | 45.529046 |
| Sequential Staggered Blocking | 0.611898 | 0.525541 | 0.773518 | 0.474452 | 0.403001 | 0.557682 | 0.403001 | 0.773518 | 0.370517 |
| Asymmetric Corridor | 1.479772 | 0.836517 | 0.857670 | 1.531476 | 1.422402 | 1.225567 | 0.836517 | 1.531476 | 0.694958 |

## Part I T12 Comparison

| topology | Part I Proposed | Part II Proposed values | Part I VG | Part II VG values | Part I ratio | Part II ratio min/mean/max | Part I position |
|---|---:|---|---:|---|---:|---|---|
| C-Trap | 0.223939 | 0.2507547000423074;0.18069790001027286;0.20589070004643872;0.23989119997713715;0.24553840002045035 | 40.951560 | 36.08962809998775;34.22309189999942;29.62044899998;39.30350380000891;36.33938620000845 | 182.869347 | 143.864920/157.804117/189.393966 | Proposed: within Part II range; VG: above Part II range; ratio: within Part II range |
| Sequential Staggered Blocking | 59.967959 | 60.347027399984654;50.67146909999428;65.47634520003339;70.66605119995074;66.9036238999688 | 26.252015 | 36.92624200001592;26.629931000003126;50.64714210003149;33.527622399968095;26.962237400002778 | 0.437767 | 0.403001/0.557682/0.773518 | Proposed: within Part II range; VG: below Part II range; ratio: near Part II low end |
| Asymmetric Corridor | 24.487227 | 17.97579409996979;18.297066600003745;19.779253599990625;14.405557799967937;19.15830680000363 | 36.621248 | 26.60008220002055;15.305814100021962;16.964069499983452;22.06175940000685;27.2508079999825 | 1.495524 | 0.836517/1.225567/1.531476 | Proposed: above Part II range; VG: above Part II range; ratio: near Part II high end |

## Guardrails

- Proposed diagnostic executions: `0`
- Sanity repetitions: `0`
- Datasets modified: `NO`
- Part I files modified: `NO`
