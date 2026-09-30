# Proposed Branching Diagnostic

This directory contains an isolated diagnostic experiment for the frozen serial proposed method. It does not modify `methods/proposed`, any method output directory, the completed main benchmark artifacts, or the read-only multi-UAS mission planner.

`proposed_instrumented.py` reproduces the proposed matrix-building flow in a diagnostic-only calculator. It calls the same read-only planner functions used by the frozen method and temporarily wraps selected helper functions during each directed pair calculation to collect timing and counter data.

## Re-Blocking Metric

The diagnostic records an ordered `blocking_sequence` whenever an observed direct circle or wrapped-hull segment test reports an obstruction. `blocking_events` is the total count of those observed obstructions. `unique_blockers` is the number of distinct blocker IDs seen. `reblocking_events` is defined as observed blocking events after the first blocking event for the same directed pair. `repeated_blocker_events` counts repeated observations of blocker IDs already seen.

This metric is observational. It does not alter planner behavior or force additional checks.

## Counter Availability

The current proposed implementation delegates obstacle avoidance to boundary navigation. It is not recursive in the Python call structure used here, so `recursive_calls` and `max_recursion_depth` are reported as zero. Exact fallback elapsed time is not exposed without rewriting fallback internals, so `fallback_time_seconds` is reported as `UNAVAILABLE`.

Counters are descriptive diagnostics only. They should not be interpreted as causal evidence or statistical significance.
