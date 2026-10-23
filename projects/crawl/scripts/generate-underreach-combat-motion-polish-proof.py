from __future__ import annotations
import argparse
import json
from pathlib import Path
from livingworld.underreach_combat_motion_polish import build_combat_motion_polish_proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attack-profiles", required=True)
    parser.add_argument("--reaction-profiles", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-29d4-combat-motion-polish-proof")
    args = parser.parse_args()
    attacks = json.loads(Path(args.attack_profiles).read_text(encoding="utf-8"))
    reactions = json.loads(Path(args.reaction_profiles).read_text(encoding="utf-8"))
    proof = build_combat_motion_polish_proof(attacks, reactions, args.seed)
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(proof, indent=2, sort_keys=True), encoding="utf-8")
    polish = proof["motion_polish"]
    kinds = {}
    for d in polish["directives"]:
        kinds[d["presentation_kind"]] = kinds.get(d["presentation_kind"], 0) + 1
    print(f"[29D.4] motion polish digest: {polish['digest']}")
    print(f"[29D.4] directives: {len(polish['directives'])} kinds={json.dumps(kinds, sort_keys=True)}")
    print(f"[29D.4] output: {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
