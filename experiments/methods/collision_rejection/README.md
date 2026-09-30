# Collision-Rejection Matrix Method

This method is a direct-edge feasibility baseline.

For every unordered pair of matrix nodes, it builds the same straight-line candidate edge used by the Euclidean method, then tests that segment against the original circular NFZ regions from the native environment in local kilometers.

If the segment intersects or touches any circular NFZ, both matrix directions are removed by assigning the solver's unavailable-edge sentinel cost. No usable path is stored for that pair. Touching the NFZ boundary is treated as collision.

If the segment is clear, both matrix directions receive the direct Euclidean distance and the stored path is exactly `[start_point, end_point]`.

This method performs no obstacle avoidance or rerouting. It does not cluster NFZs, construct convex hulls, wrap overlapping NFZs, build tangents, invoke the proposed NFZ-aware routing method, or otherwise reuse proposed-method logic. As a result, it may produce a disconnected graph or an infeasible mission. That outcome is intentional and is the purpose of this baseline.
