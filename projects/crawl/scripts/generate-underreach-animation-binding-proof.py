#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from livingworld.underreach_animation_binding import build_animation_binding_proof


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic Underreach 29D.2 real-animation binding proof")
    parser.add_argument("--profiles", required=True, help="Measured attack profile JSON from Unreal")
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-29d2-animation-contact-proof")
    args = parser.parse_args()

    profile_path = Path(args.profiles)
    measurements = json.loads(profile_path.read_text(encoding="utf-8"))
    proof = build_animation_binding_proof(measurements, args.seed)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    binding = proof["binding"]
    attacks = [item for item in binding["bindings"] if item["presentation_kind"] == "attack"]
    fallbacks = [item for item in binding["bindings"] if item["binding_status"] == "semantic_fallback"]
    assets = sorted({item["asset_name"] for item in attacks})
    max_alignment = max((float(item["bounded_alignment_request_cm"]) for item in attacks), default=0.0)
    print(f"[29D.2] source canonical digest: {binding['source_canonical_digest']}")
    print(f"[29D.2] source presentation digest: {binding['source_presentation_digest']}")
    print(f"[29D.2] binding digest: {binding['digest']}")
    print(f"[29D.2] real attack bindings: {len(attacks)}")
    print(f"[29D.2] unique real attack assets: {len(assets)} ({', '.join(assets)})")
    print(f"[29D.2] semantic reaction/death fallbacks: {len(fallbacks)}")
    print(f"[29D.2] max bounded alignment request cm: {max_alignment:.3f}")
    print(f"[29D.2] output: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
