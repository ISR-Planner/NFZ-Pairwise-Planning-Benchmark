#!/usr/bin/env python3
"""Run one NFZ-aware matrix-builder benchmark environment."""

from __future__ import annotations

import argparse
from pathlib import Path

from benchmark.matrix_builders import DEFAULT_PLANNER_ROOT
from benchmark.runner import run_one


DEFAULT_DATASET = Path(__file__).resolve().parent.parent / "dataset_creator_app" / "dataset"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one standalone NFZ-aware matrix-builder benchmark."
    )
    parser.add_argument(
        "environment",
        type=Path,
        help="Path to one native NFZ-aware mission environment JSON.",
    )
    parser.add_argument(
        "--method",
        default="proposed",
        help="Matrix-builder method to use, e.g. proposed, appatt_raw, appatt_bspline.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for mission JSON and benchmark summary. Defaults to methods/<method>/outputs.",
    )
    parser.add_argument(
        "--planner-root",
        type=Path,
        default=DEFAULT_PLANNER_ROOT,
        help="Read-only existing multi-UAS mission-planner root.",
    )
    parser.add_argument(
        "--allocation-strategy",
        default="geographic",
        help="Existing solver allocation strategy.",
    )
    parser.add_argument(
        "--post-optimize",
        action="store_true",
        help="Run the existing post-optimization pipeline after the solver.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_one(
        environment_path=args.environment,
        matrix_method=args.method,
        output_dir=args.output_dir,
        planner_root=args.planner_root,
        allocation_strategy=args.allocation_strategy,
        post_optimize=args.post_optimize,
    )

    status = "success" if result.mission_success else "failure"
    print(f"status: {status}")
    print(f"source_environment: {result.source_environment}")
    print(f"matrix_method: {result.matrix_method}")
    print(f"target_count: {result.target_count}")
    print(f"matrix_build_time_seconds: {result.matrix_build_time_seconds}")
    print(f"solver_time_seconds: {result.solver_time_seconds}")
    print(f"solver_completed: {result.solver_completed}")
    print(f"mission_feasible: {result.mission_feasible}")
    print(f"mission_success: {result.mission_success}")
    print(f"targets_serviced: {result.targets_serviced}")
    print(f"points: {result.points}")
    print(f"route_distance: {result.route_distance}")
    print(f"failure_reason: {result.failure_reason}")
    print(f"output_mission_json: {result.output_mission_json}")
    print(f"summary_jsonl: {result.summary_jsonl}")
    if result.error:
        print(f"error: {result.error}")
    return 0 if result.solver_completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
