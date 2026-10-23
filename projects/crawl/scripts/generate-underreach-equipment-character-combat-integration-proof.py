from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from livingworld.underreach_equipment_character_combat_integration import (
    DEFAULT_SEED,
    build_equipment_character_combat_integration_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--count", type=int, default=24)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    manifest = build_equipment_character_combat_integration_manifest(
        seed=args.seed,
        count=args.count,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[29E.5] output: {output}")
    print(f"[29E.5] digest: {manifest['digest']}")
    print(f"[29E.5] population: {manifest['population_count']}")
    print(f"[29E.5] equipment integrations: {manifest['equipment_integration_directive_count']}")
    print(f"[29E.5] source 29E.4 digest: {manifest['source_29e4_digest']}")
    print(f"[29E.5] source 29E.3 digest: {manifest['source_29e3_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
