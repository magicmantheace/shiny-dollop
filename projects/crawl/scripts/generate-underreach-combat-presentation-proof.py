from __future__ import annotations

import argparse
import json
from pathlib import Path

from livingworld.underreach_combat_presentation import build_combat_presentation_proof


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic Underreach 29D.1 combat presentation proof")
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-29d1-combat-presentation-proof")
    args = parser.parse_args()

    proof = build_combat_presentation_proof(args.seed)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    source = proof["source"]
    presentation = proof["presentation"]
    kinds: dict[str, int] = {}
    for window in presentation["windows"]:
        kinds[window["presentation_kind"]] = kinds.get(window["presentation_kind"], 0) + 1
    print(f"[29D.1] source canonical digest: {source['canonical_digest']}")
    print(f"[29D.1] presentation digest: {presentation['digest']}")
    print(f"[29D.1] outcome: {source['canonical_truth']['outcome']}")
    print(f"[29D.1] canonical frames: {len(source['canonical_truth']['frames'])}")
    print(f"[29D.1] presentation windows: {len(presentation['windows'])}")
    print(f"[29D.1] presentation kinds: {json.dumps(kinds, sort_keys=True)}")
    print(f"[29D.1] duration seconds: {presentation['presentation_duration_seconds']}")
    print(f"[29D.1] output: {output.resolve()}")


if __name__ == "__main__":
    main()
