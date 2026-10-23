from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.runtime_checkpoint import AlphaCheckpointStore, canonical_json, payload_digest
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_social_memory_evolution import (
    PROTOCOL,
    SocialMemoryEvolutionService,
    build_social_memory_snapshot,
)
from livingworld.underreach_social_state import SocialStateService, build_social_state_snapshot


PROOF_PROTOCOL = "underreach.social-memory-evolution-proof.v1"


def _stack(seed: str, count: int, strata: int):
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    brain = BrainDrivenDescentService(persistence)
    ids = [f"descender_{index:03d}" for index in range(count)]
    descent = brain.create(seed=seed, descender_ids=ids, stratum_count=strata)
    brain.start(descent)
    memory = SocialMemoryEvolutionService(persistence)
    memory.initialize(descent)
    social = SocialStateService(persistence)
    lifecycle = CrawlLifecycleService(persistence)
    return persistence, brain, memory, social, lifecycle, descent, ids


def _record(lifecycle, descent, event_type: str, actor_ids: list[str], *, social_facts=None):
    data = {}
    if social_facts is not None:
        data["social_facts"] = social_facts
    return lifecycle.record_event(
        descent,
        event_type,
        f"Structured 30C.2 proof source event {event_type}.",
        actor_ids=actor_ids,
        location_id=descent.participants[actor_ids[0]].current_location_id,
        data=data,
    )


def _seed_source_history(lifecycle, descent, ids):
    return [
        _record(lifecycle, descent, "RESCUE", [ids[0], ids[1]]),
        _record(lifecycle, descent, "SHARED_RESOURCE", [ids[0], ids[1]]),
        _record(lifecycle, descent, "BETRAYAL", [ids[2], ids[3]]),
        _record(lifecycle, descent, "FOUGHT_BESIDE", [ids[4], ids[5]]),
        _record(
            lifecycle,
            descent,
            "ENCOUNTER_RESOLVED",
            [ids[6], ids[7]],
            social_facts=[{
                "observer_descender_id": ids[7],
                "subject_descender_id": ids[6],
                "memory_type": "witnessed_bravery",
            }],
        ),
        _record(lifecycle, descent, "SHARED_RESOURCE", [ids[0], ids[1]]),
    ]


def _advance_into_later_stratum(brain, descent, *, max_steps: int = 500) -> int:
    start_floor = descent.current_floor
    steps = 0
    while descent.current_floor == start_floor and steps < max_steps:
        record = brain.step(descent)
        steps += 1
        if record.get("run_outcome") != "running" and descent.current_floor == start_floor:
            break
    if descent.current_floor <= start_floor:
        raise RuntimeError("30C.2 proof did not reach a later Stratum")
    return steps


def _run(seed: str, count: int, strata: int):
    persistence, brain, memory, social, lifecycle, descent, ids = _stack(seed, count, strata)
    sources = _seed_source_history(lifecycle, descent, ids)
    source_ids = [event.id for event in sources]
    results = memory.process_history(descent, sources)
    if len(results) != len(sources) or not all(result.processed for result in results):
        raise RuntimeError("30C.2 did not process the complete qualifying source history")

    initial_memory_snapshot = build_social_memory_snapshot(descent)
    initial_social_snapshot = build_social_state_snapshot(descent)
    rescue_memory = memory.get_memory(descent, ids[1], ids[0], "rescued")
    shared_memory = memory.get_memory(descent, ids[1], ids[0], "shared_resource")
    if rescue_memory is None or shared_memory is None:
        raise RuntimeError("30C.2 source history did not create expected memory threads")
    if shared_memory.reinforcement_count != 2:
        raise RuntimeError("30C.2 repeated source event did not reinforce one memory thread")

    duplicate_before = descent.model_dump(mode="json")
    duplicate_history = list(descent.history_event_ids)
    duplicate = memory.process_event(descent, sources[0])
    duplicate_side_effect_free = (
        duplicate.duplicate
        and not duplicate.processed
        and descent.model_dump(mode="json") == duplicate_before
        and descent.history_event_ids == duplicate_history
    )
    if not duplicate_side_effect_free:
        raise RuntimeError("30C.2 duplicate processing was not side-effect free")

    relationship_before_stratum = social.get(descent, ids[1], ids[0]).model_dump(mode="json")
    rescue_sources_before = tuple(rescue_memory.source_event_ids)
    steps_to_next_stratum = _advance_into_later_stratum(brain, descent)
    later_stratum_number = descent.current_floor
    relationship_after_stratum = social.get(descent, ids[1], ids[0]).model_dump(mode="json")
    rescue_after = memory.get_memory(descent, ids[1], ids[0], "rescued")
    cross_stratum_relationship_equal = relationship_after_stratum == relationship_before_stratum
    cross_stratum_memory_sources_equal = rescue_after is not None and tuple(rescue_after.source_event_ids) == rescue_sources_before
    if not cross_stratum_relationship_equal or not cross_stratum_memory_sources_equal:
        raise RuntimeError("30C.2 social state did not persist across Stratum progression")

    relationship_before_decay = build_social_state_snapshot(descent)["relationship_state_digest"]
    memory_before_decay = memory.get_memory(descent, ids[1], ids[0], "shared_resource")
    if memory_before_decay is None:
        raise RuntimeError("30C.2 reinforcement memory disappeared before decay")
    decay = memory.advance_decay(descent)
    memory_after_decay = memory.get_memory(descent, ids[1], ids[0], "shared_resource")
    if memory_after_decay is None:
        raise RuntimeError("30C.2 decay removed canonical memory identity")
    relationship_after_decay = build_social_state_snapshot(descent)["relationship_state_digest"]
    decay_reduced_salience = (
        memory_after_decay.confidence < memory_before_decay.confidence
        or memory_after_decay.importance < memory_before_decay.importance
    )
    relationship_unchanged_by_decay = relationship_before_decay == relationship_after_decay
    if not decay_reduced_salience or not relationship_unchanged_by_decay:
        raise RuntimeError("30C.2 memory decay violated the relationship authority contract")

    final_memory_snapshot = build_social_memory_snapshot(descent)
    final_social_snapshot = build_social_state_snapshot(descent)
    return {
        "persistence": persistence,
        "brain": brain,
        "memory": memory,
        "social": social,
        "descent": descent,
        "ids": ids,
        "sources": sources,
        "source_ids": source_ids,
        "results": results,
        "initial_memory_snapshot": initial_memory_snapshot,
        "initial_social_snapshot": initial_social_snapshot,
        "final_memory_snapshot": final_memory_snapshot,
        "final_social_snapshot": final_social_snapshot,
        "duplicate_side_effect_free": duplicate_side_effect_free,
        "steps_to_next_stratum": steps_to_next_stratum,
        "later_stratum_number": later_stratum_number,
        "cross_stratum_relationship_equal": cross_stratum_relationship_equal,
        "cross_stratum_memory_sources_equal": cross_stratum_memory_sources_equal,
        "decay": decay,
        "decay_reduced_salience": decay_reduced_salience,
        "relationship_unchanged_by_decay": relationship_unchanged_by_decay,
    }


def generate(output: Path, *, seed: str, count: int, strata: int) -> dict:
    if count < 8:
        raise ValueError("30C.2 proof requires at least eight Descenders")
    if strata < 2:
        raise ValueError("30C.2 proof requires at least two Strata")

    first = _run(seed, count, strata)
    second = _run(seed, count, strata)
    descent = first["descent"]
    twin = second["descent"]

    independent_source_ids_equal = first["source_ids"] == second["source_ids"]
    independent_memory_equal = first["final_memory_snapshot"] == second["final_memory_snapshot"]
    independent_social_equal = first["final_social_snapshot"] == second["final_social_snapshot"]
    independent_state_equal = descent.model_dump(mode="json") == twin.model_dump(mode="json")
    if not all((independent_source_ids_equal, independent_memory_equal, independent_social_equal, independent_state_equal)):
        raise RuntimeError("independent 30C.2 replay/reproduction diverged")

    events = first["persistence"].replay_events(descent.id)
    event_counts = Counter(event.event_type for event in events)
    checkpoint_dir = output.parent / "checkpoint"
    store = AlphaCheckpointStore(checkpoint_dir, retention=4)
    written = store.write(
        "30c2-proof-runtime",
        descent,
        events,
        simulation_config={"protocol": PROTOCOL, "slice": "30C.2"},
        reason="30c2-proof",
        created_at_unix_ms=3002002,
    )
    loaded = store.load_latest().crawl
    checkpoint_state_equal = loaded.model_dump(mode="json") == descent.model_dump(mode="json")
    checkpoint_memory_equal = build_social_memory_snapshot(loaded) == first["final_memory_snapshot"]
    checkpoint_social_equal = build_social_state_snapshot(loaded) == first["final_social_snapshot"]
    if not checkpoint_state_equal or not checkpoint_memory_equal or not checkpoint_social_equal:
        raise RuntimeError("30C.2 checkpoint restore changed canonical social state")

    fact_count = sum(result.fact_count for result in first["results"])
    relationship_event_count = sum(len(result.relationship_event_ids) for result in first["results"])
    memory_event_count = sum(len(result.memory_event_ids) for result in first["results"])

    body = {
        "protocol": PROOF_PROTOCOL,
        "slice_protocol": PROTOCOL,
        "authoritative": True,
        "canonical_owner": "deterministic_simulation",
        "social_reasoning_can_mutate": False,
        "narrative_can_create_memory": False,
        "presentation_feedback_allowed": False,
        "relationship_time_decay_enabled": False,
        "seed": seed,
        "descent_id": descent.id,
        "population_count": count,
        "configured_stratum_count": strata,
        "source_event_count": len(first["source_ids"]),
        "source_event_ids": first["source_ids"],
        "source_event_ids_digest": payload_digest(first["source_ids"]),
        "social_fact_count": fact_count,
        "processed_source_event_count": first["final_memory_snapshot"]["memory_count"] and len(descent.modifiers["_social_memory_evolution"]["processed_source_event_ids"]),
        "memory_count": first["final_memory_snapshot"]["memory_count"],
        "memory_event_count": memory_event_count,
        "relationship_count": first["final_social_snapshot"]["relationship_count"],
        "relationship_mutation_event_count": relationship_event_count,
        "initial_memory_state_digest": first["initial_memory_snapshot"]["memory_state_digest"],
        "initial_relationship_state_digest": first["initial_social_snapshot"]["relationship_state_digest"],
        "final_memory_snapshot_digest": first["final_memory_snapshot"]["digest"],
        "final_memory_state_digest": first["final_memory_snapshot"]["memory_state_digest"],
        "final_relationship_snapshot_digest": first["final_social_snapshot"]["digest"],
        "final_relationship_state_digest": first["final_social_snapshot"]["relationship_state_digest"],
        "duplicate_processing_side_effect_free": first["duplicate_side_effect_free"],
        "steps_to_later_stratum": first["steps_to_next_stratum"],
        "later_stratum_number": first["later_stratum_number"],
        "cross_stratum_relationship_equal": first["cross_stratum_relationship_equal"],
        "cross_stratum_memory_sources_equal": first["cross_stratum_memory_sources_equal"],
        "decay_target_tick": first["decay"].target_tick,
        "decay_affected_memory_count": first["decay"].affected_memory_count,
        "decay_changed_memory_count": first["decay"].changed_memory_count,
        "decay_event_id": first["decay"].ledger_event_id,
        "decay_reduced_salience": first["decay_reduced_salience"],
        "relationship_unchanged_by_decay": first["relationship_unchanged_by_decay"],
        "independent_source_ids_equal": independent_source_ids_equal,
        "independent_memory_equal": independent_memory_equal,
        "independent_social_equal": independent_social_equal,
        "independent_state_equal": independent_state_equal,
        "checkpoint_digest": written.payload["digest"],
        "checkpoint_event_count": len(events),
        "checkpoint_state_equal": checkpoint_state_equal,
        "checkpoint_memory_equal": checkpoint_memory_equal,
        "checkpoint_social_equal": checkpoint_social_equal,
        "event_type_counts": dict(sorted(event_counts.items())),
        "authority_contract": {
            "single_canonical_descent_tree": True,
            "memory_requires_real_ledger_event": True,
            "duplicate_source_processing_is_side_effect_free": True,
            "source_events_processed_in_ledger_order": True,
            "relationship_mutation_uses_30c1_service": True,
            "memory_decay_does_not_change_relationship_truth": True,
            "generated_narrative_can_create_memory": False,
            "presentation_can_mutate": False,
            "unreal_can_mutate": False,
            "checkpoint_and_replay_are_deterministic": True,
            "next_slice": "30C.3",
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
    args = parser.parse_args()
    proof = generate(Path(args.output), seed=args.seed, count=args.count, strata=args.strata)
    print(
        f"[30C.2] proof digest={proof['digest']} descent={proof['descent_id']} "
        f"memories={proof['memory_count']} facts={proof['social_fact_count']} "
        f"laterStratum={proof['later_stratum_number']}"
    )
    print("[30C.2] Deterministic social-memory evolution proof PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
