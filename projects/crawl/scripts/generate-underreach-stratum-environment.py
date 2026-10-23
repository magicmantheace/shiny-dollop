#!/usr/bin/env python
"""Generate a deterministic 29B.1 Stratum environment manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from livingworld.stratum_environment import build_stratum_environment_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", required=True)
    parser.add_argument("--stratum", type=int, default=0)
    parser.add_argument("--sectors", type=int, default=9)
    parser.add_argument("--theme", default="ancient_stoneworks")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_stratum_environment_manifest(
        args.seed,
        args.stratum,
        sector_count=args.sectors,
        theme=args.theme,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"protocol={manifest['protocol']}")
    print(f"sectors={len(manifest['sectors'])}")
    print(f"entry={manifest['entry_sector_id']}")
    print(f"exit={manifest['exit_sector_id']}")
    print(f"refuge={manifest['refuge_sector_id']}")
    print(f"digest={manifest['digest']}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
