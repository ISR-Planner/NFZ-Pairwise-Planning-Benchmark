"""Native NFZ-aware mission environment/result loading and writing helpers."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class NativeEnvironment:
    source_path: Path
    source_id: str
    raw: Dict[str, Any]
    env: Dict[str, Any]
    drone_configs: Dict[str, Any]

    @property
    def target_count(self) -> int:
        return len(self.env.get("targets", []))

    @property
    def segment_count(self) -> int:
        return int(self.raw.get("segment_count") or 1)


def _safe_identifier(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return value.strip("_") or "environment"


def load_native_environment(path: Path) -> NativeEnvironment:
    raw = json.loads(path.read_text(encoding="utf-8"))

    if raw.get("is_segmented") is True:
        raise ValueError("Segmented Mission JSON is out of scope for this benchmark stage")

    if raw.get("schema") == "nfz_env_v1" and isinstance(raw.get("env"), dict):
        env = copy.deepcopy(raw["env"])
    elif all(key in raw for key in ("airports", "targets", "sams")):
        env = copy.deepcopy(raw)
    else:
        raise ValueError(
            "Unsupported environment JSON. Expected native nfz_env_v1 or raw env."
        )

    drone_configs = copy.deepcopy(raw.get("drone_configs") or env.get("drone_configs") or {})
    if not drone_configs:
        raise ValueError("Environment JSON does not include drone_configs")

    return NativeEnvironment(
        source_path=path,
        source_id=_safe_identifier(path.stem),
        raw=raw,
        env=env,
        drone_configs=drone_configs,
    )


def mission_filename(
    *,
    source_id: str,
    matrix_method: str,
    segment_count: int,
    timestamp: Optional[datetime] = None,
) -> str:
    ts = (timestamp or datetime.now()).strftime("%Y%m%d-%H%M")
    method = _safe_identifier(matrix_method)
    return f"{source_id}__{method}__mission_seg_{ts}_N{segment_count}_1.json"


def build_mission_document(
    native_env: NativeEnvironment,
    *,
    solution: Dict[str, Any],
    env: Optional[Dict[str, Any]] = None,
    drone_configs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Preserve the native environment envelope and attach the solver result."""

    run_env = copy.deepcopy(env if env is not None else native_env.env)
    run_drone_configs = copy.deepcopy(
        drone_configs if drone_configs is not None else native_env.drone_configs
    )

    document = copy.deepcopy(native_env.raw)
    if "env" not in document:
        document = {
            "schema": "nfz_env_v1",
            "is_segmented": False,
            "segment_count": 1,
            "env": run_env,
        }
    else:
        document["env"] = run_env
    document["drone_configs"] = run_drone_configs
    if isinstance(document.get("env"), dict):
        document["env"]["drone_configs"] = copy.deepcopy(run_drone_configs)
    document["solution"] = solution
    return document


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
