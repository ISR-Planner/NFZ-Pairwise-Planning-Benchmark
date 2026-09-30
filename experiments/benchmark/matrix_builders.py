"""Matrix-builder interface and registry for Mission benchmark experiments."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Protocol


DEFAULT_PLANNER_ROOT = Path(__file__).resolve().parent.parent.parent


def configure_planner_imports(planner_root: Path = DEFAULT_PLANNER_ROOT) -> None:
    """Make the read-only planner package importable from this standalone app."""
    root = planner_root.resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


@dataclass(frozen=True)
class MatrixBuild:
    """Result from a matrix builder."""

    method: str
    data: Dict[str, Any]


class MatrixBuilder(Protocol):
    """Common interface all benchmark matrix builders implement."""

    method: str

    def build(self, env: Dict[str, Any]) -> MatrixBuild:
        """Build a complete pairwise matrix and associated paths."""


BuilderFactory = Callable[[], MatrixBuilder]


def default_registry(planner_root: Path = DEFAULT_PLANNER_ROOT) -> Mapping[str, BuilderFactory]:
    """Return the simple method registry used by the CLI."""

    from methods.appatt.method import APPATTMatrixBuilder
    from methods.appatt_bspline.method import APPATTBSplineMatrixBuilder
    from methods.appatt_raw.method import APPATTRawMatrixBuilder
    from methods.collision_rejection.method import CollisionRejectionMatrixBuilder
    from methods.euclidean.method import EuclideanMatrixBuilder
    from methods.grid_astar.method import GridAStarMatrixBuilder
    from methods.proposed.method import ProposedSAMMatrixBuilder
    from methods.proposed_parallel.method import ProposedParallelSAMMatrixBuilder
    from methods.tig_bezier.method import TIGBezierMatrixBuilder
    from methods.tig_raw.method import TIGRawMatrixBuilder
    from methods.visibility_graph.method import VisibilityGraphMatrixBuilder

    return {
        "proposed": lambda: ProposedSAMMatrixBuilder(planner_root=planner_root),
        "proposed_parallel": lambda: ProposedParallelSAMMatrixBuilder(
            planner_root=planner_root
        ),
        "appatt": lambda: APPATTMatrixBuilder(planner_root=planner_root),
        "appatt_raw": lambda: APPATTRawMatrixBuilder(planner_root=planner_root),
        "appatt_bspline": lambda: APPATTBSplineMatrixBuilder(
            planner_root=planner_root
        ),
        "euclidean": lambda: EuclideanMatrixBuilder(planner_root=planner_root),
        "collision_rejection": lambda: CollisionRejectionMatrixBuilder(
            planner_root=planner_root
        ),
        "visibility_graph": lambda: VisibilityGraphMatrixBuilder(
            planner_root=planner_root
        ),
        "grid_astar": lambda: GridAStarMatrixBuilder(planner_root=planner_root),
        "tig_raw": lambda: TIGRawMatrixBuilder(planner_root=planner_root),
        "tig_bezier": lambda: TIGBezierMatrixBuilder(planner_root=planner_root),
    }


def get_builder(
    method: str,
    *,
    planner_root: Path = DEFAULT_PLANNER_ROOT,
) -> MatrixBuilder:
    registry = default_registry(planner_root)
    try:
        return registry[method]()
    except KeyError as exc:
        methods = ", ".join(sorted(registry))
        raise ValueError(f"Unknown matrix method '{method}'. Available: {methods}") from exc
