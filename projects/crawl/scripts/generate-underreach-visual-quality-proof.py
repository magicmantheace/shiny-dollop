from __future__ import annotations

import argparse
import json
from pathlib import Path

from livingworld.underreach_visual_quality import build_visual_quality_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", default="underreach-29e1-visual-quality-proof")
    parser.add_argument("--count", type=int, default=24)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    manifest = build_visual_quality_manifest(args.seed, args.count)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    equipment = [item for entry in manifest["entries"] for item in entry["equipment"]]
    print(f"[29E.1] digest: {manifest['digest']}")
    print(f"[29E.1] population: {manifest['population_count']}")
    print(f"[29E.1] equipment directives: {len(equipment)}")
    print(f"[29E.1] output: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
