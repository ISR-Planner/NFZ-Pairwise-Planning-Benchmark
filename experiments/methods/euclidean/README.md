# Euclidean Straight-Line Matrix Method

This method is the unrestricted direct-distance reference baseline.

For every pair of matrix nodes, it ignores all SAM/NFZ geometry and computes the straight-line Euclidean distance in the same local-kilometer coordinate frame used by the benchmark solver. Every off-diagonal pair stores the direct endpoint path `[start_point, end_point]`; diagonal distances are zero.

It performs no collision checking, clustering, convex wrapping, tangent construction, recursive chaining, or fallback planning.

