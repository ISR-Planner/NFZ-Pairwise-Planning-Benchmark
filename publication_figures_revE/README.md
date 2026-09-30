# Rev E Publication Figures

This directory contains generated publication graphics for the NFZ pairwise
preprocessing manuscript. Figures were generated from frozen benchmark JSON
inputs and mission outputs without modifying datasets, routes, or metrics.

Visible labels convert legacy input SAM identifiers to NFZ terminology at
render time only. The underlying JSON files are unchanged.

Wrapped planning hulls are produced with `path_planning_core.sam_wrapping.wrap_sams`
using the same `min_seg=0.3` setting used by the Proposed planner path.
