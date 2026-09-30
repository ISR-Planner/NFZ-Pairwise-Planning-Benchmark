"""Generate Part II t12 controlled instances from the frozen generator.

This wrapper is infrastructure only until dataset generation is explicitly
authorized. It imports the frozen generator under ``dataset_creator_app`` and
renames selected t12 outputs according to the approved Part II seed mapping.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


PART2_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PART2_ROOT / "config" / "part2_instances.json"
FROZEN_GENERATOR_PATH = (
    PART2_ROOT / "generator" / "dataset_creator_app" / "generate_dataset.py"
)
DEFAULT_OUT_DIR = PART2_ROOT / "datasets" / "controlled_t12"
DEFAULT_MANIFEST_PATH = PART2_ROOT / "manifests" / "part2_generated_dataset_manifest.json"
TOPOLOGY_OUTPUT = {
    "c_trap": ("c_trap", "ctrap"),
    "sequential_staggered_blocking": (
        "sequential_staggered_blocking",
        "sequential",
    ),
    "asymmetric_corridor": ("asymmetric_corridor", "asymmetric"),
}


def load_frozen_generator() -> Any:
    spec = importlib.util.spec_from_file_location(
        "part2_frozen_generate_dataset", FROZEN_GENERATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {FROZEN_GENERATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_text_lf(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def load_config(path: Path = CONFIG_PATH) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def planned_outputs(config: Dict[str, Any], out_dir: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for instance in config["instances"]:
        instance_id = instance["instance_id"]
        seed = int(instance["seed"])
        for topology in config["topologies"]:
            subdir, prefix = TOPOLOGY_OUTPUT[topology]
            environment_id = f"{prefix}_{instance_id}_t12"
            rows.append(
                {
                    "topology": topology,
                    "instance_id": instance_id,
                    "seed": seed,
                    "target_count": 12,
                    "environment_id": environment_id,
                    "path": str(out_dir / subdir / f"{environment_id}.json"),
                }
            )
    return rows


def generate(config: Dict[str, Any], out_dir: Path) -> Dict[str, Any]:
    generator_module = load_frozen_generator()
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="part2_generator_") as tmp:
        staging_root = Path(tmp)
        for instance in config["instances"]:
            instance_id = instance["instance_id"]
            seed = int(instance["seed"])
            for topology, topology_generator in generator_module.TOPOLOGIES:
                if topology not in config["topologies"]:
                    continue

                family_index = 1
                derived_seed = generator_module.derived_seed(
                    seed, topology, family_index
                )
                rng = random.Random(derived_seed)
                layout = topology_generator(rng)
                staging_dir = staging_root / f"{topology}_{instance_id}"
                written = generator_module.write_family(
                    staging_dir, topology, family_index, layout
                )
                source_t12 = next(path for path in written if path.name.endswith("_t12.json"))
                subdir, prefix = TOPOLOGY_OUTPUT[topology]
                environment_id = f"{prefix}_{instance_id}_t12"
                final_name = f"{environment_id}.json"
                final_path = out_dir / subdir / final_name
                final_path.parent.mkdir(parents=True, exist_ok=True)
                write_text_lf(final_path, source_t12.read_text(encoding="utf-8"))
                manifest_rows.append(
                    {
                        "topology": topology,
                        "environment_id": environment_id,
                        "instance_id": instance_id,
                        "seed": seed,
                        "family_index": family_index,
                        "derived_seed": derived_seed,
                        "source_filename": source_t12.name,
                        "part2_filename": final_name,
                        "path": str(final_path),
                        "sha256": sha256(final_path),
                    }
                )

    return {
        "schema": "nfz_part2_generated_dataset_manifest_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_generator_commit": config["dataset_generator_commit"],
        "target_count": 12,
        "rows": manifest_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate approved Part II t12 controlled instances."
    )
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned outputs without writing mission JSON files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    if args.dry_run:
        print(json.dumps(planned_outputs(config, args.out), indent=2))
        return 0

    manifest = generate(config, args.out)
    manifest_path = args.manifest_out
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    write_text_lf(manifest_path, json.dumps(manifest, indent=2) + "\n")
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
