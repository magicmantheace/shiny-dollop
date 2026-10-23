#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from livingworld.crawl_persistence import CrawlPersistence  # noqa: E402
from livingworld.runtime_checkpoint import AlphaCheckpointStore, payload_digest  # noqa: E402
from livingworld.underreach_ai_brain_foundation import (  # noqa: E402
    IMPLEMENTATION_VERSION,
    PROTOCOL,
    AIBrainFoundationService,
)
from livingworld.underreach_full_autonomous_descent import (  # noqa: E402
    FullAutonomousDescentService,
    validate_full_autonomous_descent,
)


PROOF_PROTOCOL = "underreach.ai-brain-foundation-proof.v1"
DEFAULT_SEED = "underreach-30b1-ai-brain-foundation-proof"


def _new_runtime(seed: str, count: int, strata: int):
    ids = [f"descender_{index:03d}" for index in range(count)]
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    runner = FullAutonomousDescentService(persistence)
    descent = runner.create(seed=seed, descender_ids=ids, stratum_count=strata)
    runner.start(descent)
    return ids, persistence, runner, descent


def build_proof(seed: str, count: int, strata: int) -> dict:
    if count < 4:
        raise ValueError("30B.1 proof requires at least four Descenders")
    if strata < 2:
        raise ValueError("30B.1 proof requires at least two Strata")

    ids, persistence, runner, descent = _new_runtime(seed, count, strata)
    brain = AIBrainFoundationService()

    initial_state = descent.model_dump(mode="json")
    initial_history = list(descent.history_event_ids)
    initial_fingerprint = descent.fingerprint()
    bundle_a = brain.proposal_bundle(descent)
    bundle_b = AIBrainFoundationService().proposal_bundle(descent)
    if bundle_a != bundle_b:
        raise RuntimeError("30B.1 same-state proposal bundles diverged")
    if descent.model_dump(mode="json") != initial_state:
        raise RuntimeError("30B.1 proposal generation mutated canonical state")
    if descent.history_event_ids != initial_history:
        raise RuntimeError("30B.1 proposal generation mutated canonical Ledger")
    if descent.fingerprint() != initial_fingerprint:
        raise RuntimeError("30B.1 proposal generation changed canonical fingerprint")

    # Advance the accepted 30A.5 simulation itself.  The next proposal bundle
    # should be bound to new canonical observations rather than internal brain state.
    runner.step(descent)
    validate_full_autonomous_descent(descent)
    post_step_state = descent.model_dump(mode="json")
    post_step_history = list(descent.history_event_ids)
    post_step_fingerprint = descent.fingerprint()
    bundle_after_step = AIBrainFoundationService().proposal_bundle(descent)
    if bundle_after_step["digest"] == bundle_a["digest"]:
        raise RuntimeError("30B.1 proposal bundle did not respond to canonical state change")
    if descent.model_dump(mode="json") != post_step_state:
        raise RuntimeError("30B.1 post-step proposal mutated canonical state")
    if descent.history_event_ids != post_step_history:
        raise RuntimeError("30B.1 post-step proposal mutated Ledger")
    if descent.fingerprint() != post_step_fingerprint:
        raise RuntimeError("30B.1 post-step proposal changed canonical fingerprint")

    # Durable checkpoint proof: restoring the exact authoritative state must
    # reproduce exactly the same advisory proposal bundle.
    events = persistence.replay_events(descent.id)
    with tempfile.TemporaryDirectory(prefix="crawl-30b1-checkpoint-") as directory:
        store = AlphaCheckpointStore(Path(directory) / "checkpoints", retention=4)
        written = store.write(
            "30b1-proof-runtime",
            descent,
            events,
            simulation_config={
                "protocol": PROTOCOL,
                "implementation_version": IMPLEMENTATION_VERSION,
                "seed": seed,
                "descender_ids": sorted(ids),
                "stratum_count": strata,
            },
            reason="30b1-proof",
            created_at_unix_ms=3001001,
        )
        loaded = store.load_latest()
        validate_full_autonomous_descent(loaded.crawl)
        restored_bundle = AIBrainFoundationService().proposal_bundle(loaded.crawl)
        if restored_bundle != bundle_after_step:
            raise RuntimeError("30B.1 checkpoint-restored proposal bundle diverged")
        checkpoint_digest = written.payload["digest"]
        checkpoint_event_count = loaded.payload["canonical"]["ledger_cursor"]["event_count"]

    actions = sorted({proposal["action"] for proposal in bundle_after_step["proposals"]})
    body = {
        "protocol": PROOF_PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "authoritative": False,
        "simulation_remains_authoritative": True,
        "presentation_feedback_allowed": False,
        "seed": seed,
        "descent_id": descent.id,
        "population_count": count,
        "configured_stratum_count": strata,
        "initial_tick": bundle_a["tick"],
        "post_step_tick": bundle_after_step["tick"],
        "initial_bundle_digest": bundle_a["digest"],
        "post_step_bundle_digest": bundle_after_step["digest"],
        "initial_observation_count": len(bundle_a["observations"]),
        "post_step_observation_count": len(bundle_after_step["observations"]),
        "post_step_actions": actions,
        "provider_id": bundle_after_step["provider_id"],
        "canonical_state_unchanged_by_proposals": True,
        "ledger_unchanged_by_proposals": True,
        "fingerprint_unchanged_by_proposals": True,
        "checkpoint_restored_bundle_exact": True,
        "checkpoint_digest": checkpoint_digest,
        "checkpoint_event_count": checkpoint_event_count,
        "canonical_fingerprint": descent.fingerprint(),
        "canonical_history_digest": payload_digest(list(descent.history_event_ids)),
        "authority_contract": {
            "brain_can_observe": True,
            "brain_can_propose": True,
            "brain_can_execute": False,
            "brain_can_mutate_descent": False,
            "brain_can_append_gameplay_ledger": False,
            "simulation_validation_required_before_execution": True,
            "unreal_can_mutate": False,
            "presentation_can_mutate": False,
        },
    }
    return {**body, "digest": payload_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--strata", type=int, default=3)
    args = parser.parse_args()

    proof = build_proof(args.seed, args.count, args.strata)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"[30B.1] output: {output}")
    print(f"[30B.1] digest: {proof['digest']}")
    print(f"[30B.1] descent: {proof['descent_id']}")
    print(f"[30B.1] population: {proof['population_count']}")
    print(f"[30B.1] initial proposals: {proof['initial_observation_count']}")
    print(f"[30B.1] post-step proposals: {proof['post_step_observation_count']}")
    print(f"[30B.1] checkpoint digest: {proof['checkpoint_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
