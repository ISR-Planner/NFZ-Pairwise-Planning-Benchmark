# APPATT Cubic B-Spline Matrix Method

`appatt_bspline` starts by invoking the validated raw APPATT builder in `methods/appatt/method.py`. It then applies a cubic B-spline smoothing stage only to raw APPATT detour paths. Direct two-point raw paths remain unchanged, and raw unavailable pairs remain unavailable.

## Source-Derived APPATT Smoothing

The APPATT paper treats the generated APPATT waypoints as B-spline control points and applies cubic B-spline smoothing to produce a smoother flight path. This implementation uses the four published uniform cubic basis functions directly and evaluates each span from four consecutive control points.

## Benchmark Numerical Adaptations

The original circular SAM geometry is retained with no extra margin. Endpoint replication is used so the sampled spline begins at the exact source and ends at the exact destination: each endpoint has three total occurrences in the evaluation control sequence. This endpoint handling is a benchmark implementation choice because the paper does not specify endpoint clamping.

The sampled trajectory uses `APPATT_BSPLINE_SAMPLES_PER_SPAN = 21`, including each span's endpoints. This is a fixed benchmark representation choice, not a published APPATT parameter.

Every accepted sampled spline segment is continuously checked against the original circular SAM/NFZ interiors. If smoothing causes penetration, the pair is recorded as `BSPLINE_COLLISION` with cost `99999.0` and blocking SAM IDs. The method does not repair the curve, adjust control points, fall back to raw APPATT, invoke TIG, invoke the proposed method, invoke Visibility Graph/Grid A*, or use parallelization.
