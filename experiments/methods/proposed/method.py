"""Proposed SAM-aware matrix-builder wrapper."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from benchmark.matrix_builders import (
    DEFAULT_PLANNER_ROOT,
    MatrixBuild,
    configure_planner_imports,
)


class ProposedSAMMatrixBuilder:
    """Reference builder that wraps the existing Mission SAM-aware matrix method."""

    method = "proposed"

    def __init__(
        self,
        *,
        planner_root: Path = DEFAULT_PLANNER_ROOT,
        buffer: float = 0.0,
    ) -> None:
        self.planner_root = planner_root
        self.buffer = buffer
        self._calculator: Optional[Callable[..., Dict[str, Any]]] = None

    def prepare(self) -> None:
        configure_planner_imports(self.planner_root)

        from server.solver.sam_distance_matrix import calculate_sam_aware_matrix

        self._calculator = calculate_sam_aware_matrix

    def build(self, env: Dict[str, Any]) -> MatrixBuild:
        if self._calculator is None:
            self.prepare()

        assert self._calculator is not None
        matrix = self._calculator(
            env,
            buffer=self.buffer,
            use_supabase_cache=False,
        )
        return MatrixBuild(method=self.method, data=matrix)

