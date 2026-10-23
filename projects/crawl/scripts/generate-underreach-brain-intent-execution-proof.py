from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.runtime_checkpoint import AlphaCheckpointStore, canonical_json, payload_digest
from livingworld.underreach_ai_brain_foundation import AIBrainFoundationService
from livingworld.underreach_brain_intent_execution import (
    BrainIntentExecutionService,
    PROTOCOL,
)
from livingworld.underreach_full_autonomous_descent import FullAutonomousDescentService


PROOF_PROTOCOL = "underreach.brain-intent-execution-proof.v1"


def _stack(seed: str, ids: list[str], strata: int):
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    autonomous = FullAutonomousDescentService(persistence)
    descent = autonomous.create(seed=seed, descender_ids=ids, stratum_count=strata)
    autonomous.start(descent)
    brain = AIBrainFoundationService()
    executor = BrainIntentExecutionService(brain=brain, survival=autonomous.survival)
    return persistence, autonomous, brain, executor, descent


def _state_digest(descent) -> str:
    return payload_digest(descent.model_dump(mode="json"))


def generate(output: Path, *, seed: str, count: int, strata: int) -> dict:
    ids = [f"descender_{index:03d}" for index in range(count)]

    persistence, autonomous, brain, executor, descent = _stack(seed, ids, strata)
    actor = ids[0]

    before_proposal = _state_digest(descent)
    before_history = list(descent.history_event_ids)
    intent = brain.propose(descent, actor)
    if _state_digest(descent) != before_proposal or descent.history_event_ids != before_history:
        raise RuntimeError("30B.1 proposal mutated canonical state before 30B.2 validation")

    before_validation = _state_digest(descent)
    decision = executor.validate(descent, intent)
    if not decision.accepted:
        raise RuntimeError(f"reference proposal was unexpectedly rejected: {decision.reason_code}")
    if _state_digest(descent) != before_validation:
        raise RuntimeError("30B.2 validation mutated canonical state")

    execution = executor.execute(descent, intent)
    if not execution.executed or not execution.execution_event_id:
        raise RuntimeError("accepted reference proposal did not execute canonically")
    after_execution = _state_digest(descent)
    if after_execution == before_validation:
        raise RuntimeError("canonical execution produced no canonical state change")

    # Independent identical stack must propose, validate, execute, and serialize identically.
    _, _, twin_brain, twin_executor, twin = _stack(seed, ids, strata)
    twin_intent = twin_brain.propose(twin, actor)
    twin_decision = twin_executor.validate(twin, twin_intent)
    twin_execution = twin_executor.execute(twin, twin_intent)
    if intent != twin_intent or decision != twin_decision or execution != twin_execution:
        raise RuntimeError("independent 30B.2 execution was not deterministic")
    independent_state_equal = twin.model_dump(mode="json") == descent.model_dump(mode="json")
    if not independent_state_equal:
        raise RuntimeError("independent canonical state diverged after the same brain execution")

    # A proposal becomes stale when authoritative state that is part of its observation changes.
    stale_actor = ids[1]
    stale_intent = brain.propose(descent, stale_actor)
    autonomous.survival.advance_time(descent, descent.current_tick + 1)
    before_stale_reject = _state_digest(descent)
    before_stale_history = list(descent.history_event_ids)
    stale_result = executor.execute(descent, stale_intent)
    if stale_result.executed or stale_result.reason_code != "stale_observation":
        raise RuntimeError("stale 30B.1 proposal was not deterministically rejected")
    if _state_digest(descent) != before_stale_reject or descent.history_event_ids != before_stale_history:
        raise RuntimeError("stale proposal rejection mutated canonical state")

    # Checkpoint path: after one canonical brain execution, restoring the exact
    # state must produce the same next proposal and canonical execution.
    checkpoint_persistence, checkpoint_auto, checkpoint_brain, checkpoint_executor, checkpoint_descent = _stack(
        seed + "-checkpoint", ids, strata
    )
    first_checkpoint_intent = checkpoint_brain.propose(checkpoint_descent, actor)
    checkpoint_executor.execute(checkpoint_descent, first_checkpoint_intent)
    checkpoint_events = checkpoint_persistence.replay_events(checkpoint_descent.id)

    checkpoint_dir = output.parent / "checkpoint"
    store = AlphaCheckpointStore(checkpoint_dir, retention=4)
    written = store.write(
        "30b2-proof-runtime",
        checkpoint_descent,
        checkpoint_events,
        simulation_config={"protocol": PROTOCOL, "slice": "30B.2"},
        reason="30b2-proof",
        created_at_unix_ms=3002001,
    )
    loaded = store.load_latest().crawl
    if loaded.model_dump(mode="json") != checkpoint_descent.model_dump(mode="json"):
        raise RuntimeError("30B.2 checkpoint restore changed canonical state")

    next_original_intent = checkpoint_brain.propose(checkpoint_descent, actor)
    loaded_brain = AIBrainFoundationService()
    loaded_executor = BrainIntentExecutionService(brain=loaded_brain)
    next_loaded_intent = loaded_brain.propose(loaded, actor)
    if next_loaded_intent != next_original_intent:
        raise RuntimeError("checkpoint restore changed the next brain proposal")

    next_original_result = checkpoint_executor.execute(checkpoint_descent, next_original_intent)
    next_loaded_result = loaded_executor.execute(loaded, next_loaded_intent)
    if next_loaded_result != next_original_result:
        raise RuntimeError("checkpoint restore changed deterministic intent execution result")
    checkpoint_final_state_equal = loaded.model_dump(mode="json") == checkpoint_descent.model_dump(mode="json")
    if not checkpoint_final_state_equal:
        raise RuntimeError("checkpoint-restored canonical execution diverged")

    events = checkpoint_persistence.replay_events(checkpoint_descent.id)
    event_counts = Counter(event.event_type for event in events)

    body = {
        "protocol": PROOF_PROTOCOL,
        "slice_protocol": PROTOCOL,
        "authoritative": True,
        "canonical_owner": "deterministic_simulation",
        "brain_provider_can_mutate": False,
        "validation_can_mutate": False,
        "rejected_intent_can_mutate": False,
        "accepted_execution_can_mutate": True,
        "presentation_feedback_allowed": False,
        "seed": seed,
        "descent_id": descent.id,
        "population_count": count,
        "configured_stratum_count": strata,
        "initial_action": intent.action,
        "initial_proposal_id": intent.proposal_id,
        "initial_observation_digest": intent.observation_digest,
        "initial_decision_digest": decision.decision_digest,
        "initial_execution_result_digest": execution.result_digest,
        "initial_execution_event_id": execution.execution_event_id,
        "initial_source_event_count": len(execution.source_event_ids),
        "canonical_state_digest_before_execution": before_validation,
        "canonical_state_digest_after_execution": after_execution,
        "independent_execution_equal": execution == twin_execution,
        "independent_state_equal": independent_state_equal,
        "stale_rejection_reason": stale_result.reason_code,
        "stale_rejection_mutated_state": False,
        "checkpoint_digest": written.payload["digest"],
        "checkpoint_event_count": len(checkpoint_events),
        "checkpoint_next_proposal_equal": next_loaded_intent == next_original_intent,
        "checkpoint_next_execution_equal": next_loaded_result == next_original_result,
        "checkpoint_final_state_equal": checkpoint_final_state_equal,
        "checkpoint_final_state_digest": _state_digest(checkpoint_descent),
        "event_type_counts": dict(sorted(event_counts.items())),
        "authority_contract": {
            "brain_proposes_only": True,
            "simulation_validates_legality": True,
            "simulation_executes_mutations": True,
            "stale_or_rejected_proposals_are_side_effect_free": True,
            "execution_is_ledger_bound": True,
            "unreal_can_mutate": False,
            "presentation_can_mutate": False,
            "time_cadence_owned_by_later_orchestrator": True,
            "next_slice_must_build_on_execution_membrane": True,
        },
    }
    proof = {**body, "digest": payload_digest(body)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_json(proof) + "\n", encoding="utf-8")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-30b2-intent-execution-proof")
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--strata", type=int, default=3)
    args = parser.parse_args()
    proof = generate(Path(args.output), seed=args.seed, count=args.count, strata=args.strata)
    print(
        f"[30B.2] proof digest={proof['digest']} action={proof['initial_action']} "
        f"checkpoint={proof['checkpoint_digest']}"
    )
    print("[30B.2] Deterministic intent validation/execution proof PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
