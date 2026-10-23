from __future__ import annotations

import argparse
import json
from pathlib import Path

from livingworld.underreach_live_encounters import build_live_encounter_proof, validate_live_encounter_proof


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the Underreach 29C.2 canonical live encounter proof")
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-29c2-live-proof")
    parser.add_argument("--theme", default="ancient_stoneworks")
    parser.add_argument("--sectors", type=int, default=12)
    parser.add_argument("--descenders", type=int, default=3)
    args = parser.parse_args()

    proof = build_live_encounter_proof(
        args.seed,
        theme=args.theme,
        sector_count=args.sectors,
        descender_count=args.descenders,
    )
    validate_live_encounter_proof(proof)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    truth = proof["canonical_truth"]
    resolution = truth["resolution"]
    print(f"[29C.2] canonical digest: {proof['canonical_digest']}")
    print(f"[29C.2] proof digest: {proof['digest']}")
    print(f"[29C.2] outcome: {resolution['outcome']}")
    print(f"[29C.2] rounds: {resolution['rounds']}")
    print(f"[29C.2] Ledger events: {len(truth['ledger_events'])}")
    print(f"[29C.2] output: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
