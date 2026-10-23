from __future__ import annotations

import argparse
from pathlib import Path
import shutil

from livingworld.runtime_checkpoint import canonical_json
from livingworld.underreach_unattended_promotion_soak import (
    UnattendedPromotionSoakPolicy,
    UnattendedPromotionSoakService,
    validate_soak_result,
)


PROOF_PROTOCOL = "underreach.unattended-promotion-soak-proof.v1"


def build_proof(*, output: Path, seed: str) -> dict:
    runtime_root = output.parent / f"{output.stem}-runtime"
    if runtime_root.exists():
        shutil.rmtree(runtime_root)
    runtime_root.mkdir(parents=True, exist_ok=True)
    media_root = runtime_root / "media"
    canonical_db = runtime_root / "canonical.sqlite3"
    media_db = runtime_root / "media.sqlite3"

    policy = UnattendedPromotionSoakPolicy(
        population_count=20,
        stratum_count=3,
        max_simulation_steps=2000,
        required_social_events=4,
        portrait_width=192,
        portrait_height=192,
        scene_width=270,
        scene_height=480,
        promo_fps=12,
        promo_minimum_seconds=6.0,
        promo_maximum_seconds=24.0,
    )
    service = UnattendedPromotionSoakService(
        canonical_database_url=f"sqlite:///{canonical_db.as_posix()}",
        media_database_url=f"sqlite:///{media_db.as_posix()}",
        media_root=media_root,
        seed=seed,
        policy=policy,
    )
    result = service.run()
    validate_soak_result(result)
    body = result.model_dump(mode="json")
    return {
        "protocol": PROOF_PROTOCOL,
        "slice_protocol": body["protocol"],
        "implementation_version": body["implementation_version"],
        "phase": body["phase"],
        "seed": seed,
        "policy_digest": body["policy_digest"],
        "canonical": body["canonical"],
        "event_provenance": body["event_provenance"],
        "media": body["media"],
        "chronicle": body["chronicle"],
        "verification": body["verification"],
        "presentation": body["presentation"],
        "audio": body["audio"],
        "promotion": body["promotion"],
        "review_queue": body["review_queue"],
        "website": body["website"],
        "restart": body["restart"],
        "idempotency": body["idempotency"],
        "mandatory_zeroes": body["mandatory_zeroes"],
        "authority_contract": body["authority_contract"],
        "digest": body["digest"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the deterministic Underreach 30.5.12 unattended promotion soak proof.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-30-5-12-unattended-promotion-soak-proof")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    proof = build_proof(output=output, seed=args.seed)
    output.write_text(canonical_json(proof) + "\n", encoding="utf-8")

    print(
        canonical_json(
            {
                "digest": proof["digest"],
                "population": proof["canonical"]["population_count"],
                "events": proof["canonical"]["final_event_count"],
                "profiles": proof["media"]["profile_count"],
                "highlights": proof["chronicle"]["highlight_count"],
                "promo": proof["promotion"]["status"],
                "review": proof["review_queue"]["review_status"],
                "website": proof["website"]["status"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
