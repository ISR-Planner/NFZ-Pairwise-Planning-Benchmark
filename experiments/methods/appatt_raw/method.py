"""Preserved raw APPATT wrapper."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict

from benchmark.matrix_builders import DEFAULT_PLANNER_ROOT, MatrixBuild
from methods.appatt.method import APPATTMatrixBuilder


class APPATTRawMatrixBuilder:
    """Delegate to the validated APPATT builder under an explicit raw method name."""

    method = "appatt_raw"

    def __init__(self, *, planner_root: Path = DEFAULT_PLANNER_ROOT) -> None:
        self._raw_builder = APPATTMatrixBuilder(planner_root=planner_root)

    def prepare(self) -> None:
        self._raw_builder.prepare()

    def build(self, env: Dict[str, Any]) -> MatrixBuild:
        raw = self._raw_builder.build(env)
        data = copy.deepcopy(raw.data)
        routing_model = data.setdefault("routing_model", {})
        routing_model["method"] = self.method
        data["benchmark_diagnostics"] = {
            "method": self.method,
            "source_raw_method": raw.method,
            "canonical_raw_builder": "methods.appatt.method.APPATTMatrixBuilder",
            "wrapper_only": True,
            "smoothing": "none",
            "parallel_mechanism": "none",
            "worker_count": 1,
            "persistent_process_pool": False,
            "fallback": False,
        }
        return MatrixBuild(method=self.method, data=data)
