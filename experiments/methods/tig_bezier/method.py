"""Static TIG matrix builder with quadratic Bezier smoothing."""

from __future__ import annotations

from pathlib import Path

from benchmark.matrix_builders import DEFAULT_PLANNER_ROOT
from methods.tig_raw.method import TIGMatrixBuilderBase


class TIGBezierMatrixBuilder(TIGMatrixBuilderBase):
    """Run the shared raw S-TIG planner, then smooth each turn with Bezier arcs."""

    method = "tig_bezier"
    variant = "bezier"

    def __init__(self, *, planner_root: Path = DEFAULT_PLANNER_ROOT) -> None:
        super().__init__(planner_root=planner_root)
