from __future__ import annotations

import argparse
import json
from pathlib import Path

from livingworld.underreach_autonomous_encounters import run_autonomous_encounter


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic Underreach 29C.3 autonomous encounter proof")
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-29c3-autonomous-proof")
    parser.add_argument("--theme", default="ancient_stoneworks")
    parser.add_argument("--sectors", type=int, default=12)
    parser.add_argument("--descenders", type=int, default=3)
    args = parser.parse_args()

    proof = run_autonomous_encounter(
        args.seed,
        theme=args.theme,
        sector_count=args.sectors,
        descender_count=args.descenders,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    truth = proof["canonical_truth"]
    print(f"[29C.3] canonical digest: {proof['canonical_digest']}")
    print(f"[29C.3] proof digest: {proof['digest']}")
    print(f"[29C.3] outcome: {truth['outcome']}")
    print(f"[29C.3] frames: {len(truth['frames'])}")
    print(f"[29C.3] Ledger events: {len(truth['ledger_events'])}")
    print(f"[29C.3] output: {output.resolve()}")


if __name__ == "__main__":
    main()
