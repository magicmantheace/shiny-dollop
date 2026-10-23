#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from livingworld.underreach_character_visual_polish_render import (  # noqa: E402
    DEFAULT_SEED,
    build_character_visual_polish_render_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--count", type=int, default=24)
    args = parser.parse_args()

    manifest = build_character_visual_polish_render_manifest(seed=args.seed, count=args.count)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    print(f"[29E.6] output: {output}")
    print(f"[29E.6] digest: {manifest['digest']}")
    print(f"[29E.6] population: {manifest['population_count']}")
    print(f"[29E.6] shots: {len(manifest['shots'])}")
    print(f"[29E.6] crowd: {manifest['crowd_descender_count']}")
    print(f"[29E.6] source 29E.5 digest: {manifest['source_29e5_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
