from __future__ import annotations

import argparse
import json
from pathlib import Path

from livingworld.underreach_equipment_asset_integration import (
    build_real_equipment_integration_manifest,
    equipment_source_manifest,
    equipment_source_texts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Underreach 29E.2 real equipment sources and integration proof")
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--seed", default="underreach-29e2-real-equipment-proof")
    parser.add_argument("--count", type=int, default=24)
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    source_dir.mkdir(parents=True, exist_ok=True)
    texts = equipment_source_texts()
    for name, text in sorted(texts.items()):
        (source_dir / name).write_text(text, encoding="utf-8", newline="\n")

    source_manifest = equipment_source_manifest()
    source_manifest_path = Path(args.source_manifest)
    source_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    source_manifest_path.write_text(json.dumps(source_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    proof = build_real_equipment_integration_manifest(seed=args.seed, count=args.count)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"[29E.2] digest: {proof['digest']}")
    print(f"[29E.2] population: {proof['population_count']}")
    print(f"[29E.2] replacements: {proof['replacement_count']}")
    print(f"[29E.2] source assets: {proof['unique_real_mesh_asset_count']}")
    print(f"[29E.2] material instances: {proof['unique_material_instance_count']}")
    print(f"[29E.2] output: {output}")
    print(f"[29E.2] source manifest: {source_manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
