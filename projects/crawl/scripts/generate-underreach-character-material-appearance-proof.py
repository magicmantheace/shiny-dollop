from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from livingworld.underreach_character_material_appearance import (
    DEFAULT_SEED,
    build_character_material_appearance_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--count", type=int, default=24)
    args = parser.parse_args()

    manifest = build_character_material_appearance_manifest(seed=args.seed, count=args.count)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[29E.4] digest: {manifest['digest']}")
    print(f"[29E.4] population: {manifest['population_count']}")
    print(f"[29E.4] character material directives: {manifest['material_directive_count']}")
    print(f"[29E.4] material templates: {manifest['character_material_template_count']}")
    print(f"[29E.4] source 29E.3 digest: {manifest['source_29e3_digest']}")
    print(f"[29E.4] output: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
