from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.runtime_checkpoint import AlphaCheckpointStore, canonical_json, payload_digest
from livingworld.underreach_ai_brain_foundation import AIBrainFoundationService
from livingworld.underreach_brain_driven_descent import (
    METADATA_KEY,
    PROTOCOL,
    BrainDrivenDescentService,
    build_brain_driven_snapshot,
    validate_brain_driven_descent,
)


PROOF_PROTOCOL = "underreach.brain-driven-descent-proof.v1"


class ExplodingProvider:
    provider_id = "proof-exploding-provider-v1"

    def propose(self, observation):
        raise RuntimeError("synthetic proof provider outage")


def _stack(seed: str, ids: list[str], strata: int, *, brain=None):
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    service = BrainDrivenDescentService(persistence, brain=brain)
    descent = service.create(seed=seed, descender_ids=ids, stratum_count=strata)
    return persistence, service, descent


def _state_digest(descent) -> str:
    return payload_digest(descent.model_dump(mode="json"))


def _brain_action_counts(descent) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in descent.modifiers[METADATA_KEY]["step_records"]:
        for decision in record["decisions"]:
            action = decision.get("brain_action")
            if action:
                counts[str(action)] += 1
    return dict(sorted(counts.items()))


def generate(output: Path, *, seed: str, count: int, strata: int, max_steps: int) -> dict:
    ids = [f"descender_{index:03d}" for index in range(count)]

    # Baseline uninterrupted brain-driven run.
    persistence, service, descent = _stack(seed, ids, strata)
    result = service.run(descent, max_steps=max_steps)
    if not result.completed:
        raise RuntimeError(f"baseline brain-driven Descent did not complete: {result}")
    baseline_snapshot = build_brain_driven_snapshot(descent)
    baseline_model = descent.model_dump(mode="json")
    baseline_history = list(descent.history_event_ids)
    baseline_events = persistence.replay_events(descent.id)
    event_counts = Counter(event.event_type for event in baseline_events)

    # Independent reproduction with reversed input order must be bit-identical.
    _, reproduce_service, reproduce = _stack(seed, list(reversed(ids)), strata)
    reproduce_result = reproduce_service.run(reproduce, max_steps=max_steps)
    if reproduce_result != result:
        raise RuntimeError("independent brain-driven run result diverged")
    reproduce_snapshot = build_brain_driven_snapshot(reproduce)
    if reproduce.model_dump(mode="json") != baseline_model:
        raise RuntimeError("independent brain-driven canonical model diverged")
    if reproduce.history_event_ids != baseline_history:
        raise RuntimeError("independent brain-driven Ledger ID sequence diverged")
    if reproduce_snapshot != baseline_snapshot:
        raise RuntimeError("independent brain-driven snapshot diverged")

    # Checkpoint after the first transition, then resume to exact baseline state.
    checkpoint_persistence, checkpoint_service, checkpoint_descent = _stack(seed, ids, strata)
    checkpoint_service.start(checkpoint_descent)
    for _ in range(max_steps):
        if (
            checkpoint_descent.current_floor >= 2
            or checkpoint_descent.modifiers[METADATA_KEY]["run_outcome"] != "running"
        ):
            break
        checkpoint_service.step(checkpoint_descent)
    if checkpoint_descent.current_floor != 2:
        raise RuntimeError("30B.3 checkpoint run did not reach Stratum 2")
    checkpoint_snapshot = build_brain_driven_snapshot(checkpoint_descent)
    checkpoint_events = checkpoint_persistence.replay_events(checkpoint_descent.id)

    checkpoint_dir = output.parent / "checkpoint"
    store = AlphaCheckpointStore(checkpoint_dir, retention=4)
    written = store.write(
        "30b3-proof-runtime",
        checkpoint_descent,
        checkpoint_events,
        simulation_config={"protocol": PROTOCOL, "seed": seed, "strata": strata},
        reason="30b3-proof",
        created_at_unix_ms=3003001,
    )
    loaded = store.load_latest().crawl
    if loaded.model_dump(mode="json") != checkpoint_descent.model_dump(mode="json"):
        raise RuntimeError("30B.3 checkpoint restore changed canonical state")
    if build_brain_driven_snapshot(loaded) != checkpoint_snapshot:
        raise RuntimeError("30B.3 checkpoint restore changed brain-driven trace")
    if not validate_brain_driven_descent(loaded):
        raise RuntimeError("30B.3 checkpoint restore failed validation")

    resumed_result = checkpoint_service.run(loaded, max_steps=max_steps, start_if_planned=False)
    if not resumed_result.completed:
        raise RuntimeError("checkpoint-resumed brain-driven run did not complete")
    resumed_snapshot = build_brain_driven_snapshot(loaded)
    if loaded.model_dump(mode="json") != baseline_model:
        raise RuntimeError("checkpoint-resumed brain-driven canonical model diverged")
    if loaded.history_event_ids != baseline_history:
        raise RuntimeError("checkpoint-resumed brain-driven Ledger sequence diverged")
    if resumed_snapshot != baseline_snapshot:
        raise RuntimeError("checkpoint-resumed brain-driven snapshot diverged")

    # Provider outage probe: no proposal may be required for liveness.
    outage_brain = AIBrainFoundationService(provider=ExplodingProvider())
    _, outage_service, outage_descent = _stack(seed + "-outage", ids, 2, brain=outage_brain)
    outage_service.start(outage_descent)
    outage_before_tick = outage_descent.current_tick
    outage_record = outage_service.step(outage_descent)
    outage_metrics = dict(outage_descent.modifiers[METADATA_KEY]["metrics"])
    if outage_descent.current_tick != outage_before_tick + 1:
        raise RuntimeError("provider outage prevented canonical clock progress")
    if outage_metrics["provider_errors"] < 1 or outage_metrics["fallback_invocations"] < 1:
        raise RuntimeError("provider outage did not exercise deterministic fallback")
    if any(not decision["fallback_used"] for decision in outage_record["decisions"]):
        raise RuntimeError("provider outage left a Descender without fallback")

    metrics = dict(descent.modifiers[METADATA_KEY]["metrics"])
    source_metrics = dict(descent.modifiers["_full_autonomous_descent"]["metrics"])
    body = {
        "protocol": PROOF_PROTOCOL,
        "slice_protocol": PROTOCOL,
        "authoritative": True,
        "canonical_owner": "deterministic_simulation",
        "brain_provider_can_mutate": False,
        "presentation_feedback_allowed": False,
        "seed": seed,
        "descent_id": descent.id,
        "population_count": count,
        "configured_stratum_count": strata,
        "final_status": descent.status.value,
        "final_outcome": descent.modifiers[METADATA_KEY]["run_outcome"],
        "final_current_stratum_index": descent.current_floor - 1,
        "final_tick": descent.current_tick,
        "step_count": descent.modifiers[METADATA_KEY]["step_count"],
        "surviving_descender_count": descent.surviving_crawler_count,
        "eliminated_descender_count": descent.eliminated_crawler_count,
        "provider_id": descent.modifiers[METADATA_KEY]["provider_id"],
        "brain_cadence_steps": descent.modifiers[METADATA_KEY]["brain_cadence_steps"],
        "metrics": metrics,
        "source_autonomous_metrics": source_metrics,
        "brain_action_counts": _brain_action_counts(descent),
        "event_type_counts": dict(sorted(event_counts.items())),
        "final_snapshot_digest": baseline_snapshot["digest"],
        "final_step_trace_digest": baseline_snapshot["step_trace_digest"],
        "final_canonical_fingerprint": descent.fingerprint(),
        "final_canonical_state_digest": _state_digest(descent),
        "reproduction_snapshot_digest": reproduce_snapshot["digest"],
        "reproduction_canonical_fingerprint": reproduce.fingerprint(),
        "checkpoint_digest": written.payload["digest"],
        "checkpoint_event_count": len(checkpoint_events),
        "checkpoint_step_count": checkpoint_descent.modifiers[METADATA_KEY]["step_count"],
        "checkpoint_snapshot_digest": checkpoint_snapshot["digest"],
        "checkpoint_canonical_fingerprint": checkpoint_descent.fingerprint(),
        "resumed_final_snapshot_digest": resumed_snapshot["digest"],
        "resumed_final_canonical_fingerprint": loaded.fingerprint(),
        "outage_probe": {
            "provider_id": outage_descent.modifiers[METADATA_KEY]["provider_id"],
            "tick_advanced": outage_descent.current_tick == outage_before_tick + 1,
            "provider_errors": outage_metrics["provider_errors"],
            "fallback_invocations": outage_metrics["fallback_invocations"],
            "fallback_moves": outage_metrics["fallback_moves"],
            "decision_count": len(outage_record["decisions"]),
        },
        "authority_contract": {
            "brain_proposes_only": True,
            "brain_execution_requires_30b2_membrane": True,
            "simulation_owns_time": True,
            "simulation_owns_encounters": True,
            "simulation_owns_loot_and_survival": True,
            "simulation_owns_stratum_progression": True,
            "provider_failure_uses_deterministic_fallback": True,
            "nonprogress_navigation_uses_deterministic_fallback": True,
            "checkpoint_resume_must_match_uninterrupted": True,
            "unreal_can_mutate": False,
            "presentation_can_mutate": False,
        },
    }
    proof = {**body, "digest": payload_digest(body)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_json(proof) + "\n", encoding="utf-8")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-30b3-brain-driven-descent-proof")
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--strata", type=int, default=4)
    parser.add_argument("--max-steps", type=int, default=2500)
    args = parser.parse_args()
    proof = generate(
        Path(args.output),
        seed=args.seed,
        count=args.count,
        strata=args.strata,
        max_steps=args.max_steps,
    )
    print(
        f"[30B.3] proof digest={proof['digest']} descent={proof['descent_id']} "
        f"steps={proof['step_count']} proposals={proof['metrics']['brain_proposals']} "
        f"fallbacks={proof['metrics']['fallback_invocations']}"
    )
    print("[30B.3] Deterministic brain-driven Descent proof PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
