from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from livingworld.underreach_equipment_material_wear import build_equipment_material_wear_manifest


ACCEPTED_29E2_SEED = "underreach-29e2-real-equipment-proof"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default=ACCEPTED_29E2_SEED)
    parser.add_argument("--count", type=int, default=24)
    args = parser.parse_args()

    manifest = build_equipment_material_wear_manifest(seed=args.seed, count=args.count)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[29E.3] digest: {manifest['digest']}")
    print(f"[29E.3] population: {manifest['population_count']}")
    print(f"[29E.3] material directives: {manifest['material_directive_count']}")
    print(f"[29E.3] item material templates: {manifest['item_material_template_count']}")
    print(f"[29E.3] source 29E.2 digest: {manifest['source_29e2_digest']}")
    print(f"[29E.3] output: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
