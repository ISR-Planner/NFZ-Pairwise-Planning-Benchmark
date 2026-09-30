# S-TIG With Quadratic Bezier Smoothing Matrix Method

This method reuses the exact raw S-TIG implementation from `methods/tig_raw/method.py` and then applies the source-derived quadratic Bezier smoothing stage. It does not contain an independent TIG search implementation.

## Source-Derived Smoothing Structure

Every interior raw S-TIG waypoint is treated as a turn. For each turn the smoother creates one temporary point before the turn, uses the original raw turn waypoint as the middle control point, creates one temporary point after the turn, and samples the quadratic Bezier curve through those three control points. The final path concatenates the original straight portions outside the smoothing windows with the sampled turn curves.

The method uses the standard quadratic Bezier form `(1-t)^2 B0 + 2(1-t)t B1 + t^2 B2`. It does not use cubic Bezier curves, B-splines, generic spline packages, path fallback, smoothing repair, control-point movement, or automatic window shrinking.

## Benchmark Numerical Adaptations

The temporary-point trim fraction is fixed at `0.25` of the incoming and outgoing raw segments. The sampled representation uses `21` samples per turn, including endpoints. These are fixed benchmark implementation parameters because the paper does not provide reproducible numeric values for temporary-point placement or sampling density.

After smoothing, every consecutive sampled segment is checked continuously against every original circular SAM/NFZ. Tangency is allowed within numerical tolerance, but interior penetration makes the pair `UNAVAILABLE` with `BEZIER_COLLISION` and the blocking SAM IDs recorded. The method never falls back to the raw TIG path when smoothing collides.
