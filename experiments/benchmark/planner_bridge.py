"""Bridge from the standalone harness into the read-only multi-UAS mission planner."""

from __future__ import annotations

import copy
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator

from .matrix_builders import DEFAULT_PLANNER_ROOT, configure_planner_imports


def configure_stdio() -> None:
    """Avoid Windows cp1252 crashes from planner debug Unicode."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def prepare_solver(planner_root: Path = DEFAULT_PLANNER_ROOT) -> None:
    """Import and initialize the existing solver outside timed windows."""
    configure_stdio()
    configure_planner_imports(planner_root)

    import server.solver.solver_bridge  # noqa: F401
    import server.solver.solve_mission  # noqa: F401
    import server.solver.sam_distance_matrix  # noqa: F401


@contextmanager
def prebuilt_matrix_cache(
    env: Dict[str, Any],
    matrix_data: Dict[str, Any],
) -> Iterator[None]:
    """Make solve_mission_with_allocation reuse the benchmark-built matrix."""

    from server.solver import sam_distance_matrix
    from server.solver import solve_mission as solve_mission_module
    from server.solver.target_allocator import clear_allocator_matrix

    projected_env, _, _ = solve_mission_module._project_env_to_local_km(env)
    env_hash = solve_mission_module._compute_env_hash(projected_env)

    previous_matrix = sam_distance_matrix._calculator._cached_matrix
    previous_cache_hash = sam_distance_matrix._calculator._cache_hash
    previous_solver_hash = solve_mission_module._cached_env_hash

    sam_distance_matrix._calculator._cached_matrix = matrix_data
    sam_distance_matrix._calculator._cache_hash = env_hash
    solve_mission_module._cached_env_hash = env_hash
    clear_allocator_matrix()

    try:
        yield
    finally:
        sam_distance_matrix._calculator._cached_matrix = previous_matrix
        sam_distance_matrix._calculator._cache_hash = previous_cache_hash
        solve_mission_module._cached_env_hash = previous_solver_hash
        clear_allocator_matrix()


def solve_with_prebuilt_matrix(
    *,
    env: Dict[str, Any],
    drone_configs: Dict[str, Any],
    matrix_data: Dict[str, Any],
    planner_root: Path = DEFAULT_PLANNER_ROOT,
    allocation_strategy: str = "geographic",
    post_optimize: bool = False,
) -> Dict[str, Any]:
    """Run the existing mission solver using an already-built matrix."""

    prepare_solver(planner_root)

    from server.solver.solver_bridge import solve_mission_with_allocation

    with prebuilt_matrix_cache(copy.deepcopy(env), matrix_data):
        return solve_mission_with_allocation(
            env=copy.deepcopy(env),
            drone_configs=copy.deepcopy(drone_configs),
            allocation_strategy=allocation_strategy,
            use_sam_aware_distances=True,
            post_optimize=post_optimize,
        )
