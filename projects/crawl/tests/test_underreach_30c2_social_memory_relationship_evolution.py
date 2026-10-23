from __future__ import annotations

import pytest

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.runtime_checkpoint import AlphaCheckpointStore
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_social_memory_evolution import (
    METADATA_KEY,
    SocialMemoryEvolutionError,
    SocialMemoryEvolutionService,
    build_social_memory_snapshot,
    validate_social_memory_evolution,
)
from livingworld.underreach_social_state import SocialStateService, build_social_state_snapshot


def _stack(seed: str = "30c2-memory-test", *, count: int = 6, strata: int = 3, start: bool = True):
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    brain = BrainDrivenDescentService(persistence)
    ids = [f"descender_{index:03d}" for index in range(count)]
    descent = brain.create(seed=seed, descender_ids=ids, stratum_count=strata)
    if start:
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
        f"Structured test event {event_type}.",
        actor_ids=actor_ids,
        location_id=descent.participants[actor_ids[0]].current_location_id,
        data=data,
    )


def test_rescue_event_creates_memory_and_relationship_changes() -> None:
    persistence, _, memory, social, lifecycle, descent, ids = _stack()
    rescuer, rescued = ids[0], ids[1]
    source = _record(lifecycle, descent, "RESCUE", [rescuer, rescued])

    result = memory.process_event(descent, source)

    assert result.qualifying and result.processed and not result.duplicate
    assert result.fact_count == 1
    assert len(result.memory_ids) == 1
    assert len(result.relationship_event_ids) == 5
    remembered = memory.get_memory(descent, rescued, rescuer, "rescued")
    assert remembered is not None
    assert remembered.source_event_ids == (source.id,)
    assert remembered.reinforcement_count == 1
    assert remembered.importance == 0.9
    assert remembered.confidence == 1.0
    relationship = social.get(descent, rescued, rescuer)
    assert relationship.trust == 0.18
    assert relationship.respect == 0.12
    assert relationship.affection == 0.06
    assert relationship.gratitude == 0.24
    assert relationship.familiarity == 0.08
    assert source.id in descent.modifiers[METADATA_KEY]["processed_source_event_ids"]
    stored = persistence.events_by_ids(list(result.memory_event_ids))[0]
    assert stored.data["source_event_id"] == source.id
    assert stored.data["memory_type"] == "rescued"
    assert validate_social_memory_evolution(descent)


def test_duplicate_source_event_processing_is_side_effect_free() -> None:
    _, _, memory, _, lifecycle, descent, ids = _stack()
    source = _record(lifecycle, descent, "SHARED_RESOURCE", [ids[0], ids[1]])
    first = memory.process_event(descent, source)
    assert first.processed
    before_state = descent.model_dump(mode="json")
    before_history = list(descent.history_event_ids)

    duplicate = memory.process_event(descent, source)

    assert duplicate.qualifying and duplicate.duplicate and not duplicate.processed
    assert descent.model_dump(mode="json") == before_state
    assert descent.history_event_ids == before_history


def test_repeated_event_type_reinforces_one_memory_thread_and_relationship() -> None:
    _, brain, memory, social, lifecycle, descent, ids = _stack()
    giver, receiver = ids[0], ids[1]
    first = _record(lifecycle, descent, "SHARED_RESOURCE", [giver, receiver])
    memory.process_event(descent, first)
    brain.step(descent)
    second = _record(lifecycle, descent, "SHARED_RESOURCE", [giver, receiver])
    result = memory.process_event(descent, second)

    remembered = memory.get_memory(descent, receiver, giver, "shared_resource")
    assert remembered is not None
    assert remembered.source_event_ids == (first.id, second.id)
    assert remembered.reinforcement_count == 2
    assert remembered.last_reinforced_tick == second.tick
    assert len(result.memory_ids) == 1
    relationship = social.get(descent, receiver, giver)
    assert relationship.trust == 0.2
    assert relationship.gratitude == 0.28
    assert relationship.familiarity == 0.12
    assert descent.modifiers[METADATA_KEY]["memory_count"] == 1


def test_explicit_social_facts_support_witness_memory_without_narrative_inference() -> None:
    _, _, memory, social, lifecycle, descent, ids = _stack()
    event = _record(
        lifecycle,
        descent,
        "ENCOUNTER_RESOLVED",
        [ids[0], ids[1], ids[2]],
        social_facts=[
            {
                "observer_descender_id": ids[2],
                "subject_descender_id": ids[0],
                "memory_type": "witnessed_bravery",
            }
        ],
    )

    result = memory.process_event(descent, event)

    assert result.fact_count == 1
    remembered = memory.get_memory(descent, ids[2], ids[0], "witnessed_bravery")
    assert remembered is not None
    assert remembered.source_event_ids == (event.id,)
    relationship = social.get(descent, ids[2], ids[0])
    assert relationship.respect == 0.14
    assert relationship.familiarity == 0.03


def test_fought_beside_event_creates_symmetric_memories_but_directed_edges() -> None:
    _, _, memory, social, lifecycle, descent, ids = _stack()
    event = _record(lifecycle, descent, "FOUGHT_BESIDE", [ids[0], ids[1]])

    result = memory.process_event(descent, event)

    assert result.fact_count == 2
    assert memory.get_memory(descent, ids[0], ids[1], "fought_beside") is not None
    assert memory.get_memory(descent, ids[1], ids[0], "fought_beside") is not None
    assert social.get(descent, ids[0], ids[1]).respect == 0.1
    assert social.get(descent, ids[1], ids[0]).respect == 0.1
    assert descent.modifiers[METADATA_KEY]["memory_count"] == 2


def test_memory_decay_reduces_salience_without_changing_relationship_truth() -> None:
    _, brain, memory, social, lifecycle, descent, ids = _stack()
    source = _record(lifecycle, descent, "SHARED_RESOURCE", [ids[0], ids[1]])
    memory.process_event(descent, source)
    relationship_before = social.get(descent, ids[1], ids[0])
    memory_before = memory.get_memory(descent, ids[1], ids[0], "shared_resource")
    assert memory_before is not None

    for _ in range(4):
        brain.step(descent)
    result = memory.advance_decay(descent)

    memory_after = memory.get_memory(descent, ids[1], ids[0], "shared_resource")
    assert memory_after is not None
    assert result.affected_memory_count >= 1
    assert result.changed_memory_count >= 1
    assert memory_after.confidence < memory_before.confidence
    assert memory_after.importance < memory_before.importance
    assert social.get(descent, ids[1], ids[0]) == relationship_before
    assert result.ledger_event_id is not None


def test_nonqualifying_event_is_side_effect_free() -> None:
    _, _, memory, _, lifecycle, descent, ids = _stack()
    event = _record(lifecycle, descent, "DESCENDER_LOOKED_AROUND", [ids[0]])
    before_state = descent.model_dump(mode="json")
    before_history = list(descent.history_event_ids)

    result = memory.process_event(descent, event)

    assert not result.qualifying and not result.processed and not result.duplicate
    assert descent.model_dump(mode="json") == before_state
    assert descent.history_event_ids == before_history


def test_invalid_social_fact_rejects_without_memory_or_relationship_mutation() -> None:
    _, _, memory, _, lifecycle, descent, ids = _stack()
    event = _record(
        lifecycle,
        descent,
        "ENCOUNTER_RESOLVED",
        [ids[0], ids[1]],
        social_facts=[
            {
                "observer_descender_id": ids[0],
                "subject_descender_id": ids[1],
                "memory_type": "invented_by_narrator",
            }
        ],
    )
    before = descent.model_dump(mode="json")
    before_history = list(descent.history_event_ids)

    with pytest.raises(SocialMemoryEvolutionError):
        memory.process_event(descent, event)

    assert descent.model_dump(mode="json") == before
    assert descent.history_event_ids == before_history


def test_qualifying_events_must_be_processed_in_canonical_ledger_order() -> None:
    _, _, memory, _, lifecycle, descent, ids = _stack()
    first = _record(lifecycle, descent, "SHARED_RESOURCE", [ids[0], ids[1]])
    second = _record(lifecycle, descent, "PROTECTED", [ids[0], ids[1]])
    memory.process_event(descent, second)
    before = descent.model_dump(mode="json")

    with pytest.raises(SocialMemoryEvolutionError):
        memory.process_event(descent, first)

    assert descent.model_dump(mode="json") == before


def test_relationship_and_memory_survive_actual_stratum_progression() -> None:
    _, brain, memory, social, lifecycle, descent, ids = _stack(seed="30c2-cross-stratum", count=10, strata=3)
    source = _record(lifecycle, descent, "RESCUE", [ids[0], ids[1]])
    memory.process_event(descent, source)
    expected_relationship = social.get(descent, ids[1], ids[0])
    expected_memory = memory.get_memory(descent, ids[1], ids[0], "rescued")
    assert expected_memory is not None

    for _ in range(500):
        if descent.current_floor >= 2:
            break
        brain.step(descent)
    assert descent.current_floor >= 2

    assert social.get(descent, ids[1], ids[0]) == expected_relationship
    later_memory = memory.get_memory(descent, ids[1], ids[0], "rescued")
    assert later_memory is not None
    assert later_memory.source_event_ids == expected_memory.source_event_ids
    assert later_memory.created_tick == expected_memory.created_tick
    assert validate_social_memory_evolution(descent)


def test_persistence_and_checkpoint_round_trip_memory_state_exactly(tmp_path) -> None:
    persistence, _, memory, _, lifecycle, descent, ids = _stack(seed="30c2-checkpoint")
    one = _record(lifecycle, descent, "RESCUE", [ids[0], ids[1]])
    two = _record(lifecycle, descent, "ABANDONED", [ids[2], ids[3]])
    memory.process_event(descent, one)
    memory.process_event(descent, two)
    expected_state = descent.model_dump(mode="json")
    expected_memory = build_social_memory_snapshot(descent)
    expected_social = build_social_state_snapshot(descent)

    saved = persistence.load_crawl(descent.id)
    assert saved is not None
    assert saved.model_dump(mode="json") == expected_state
    assert build_social_memory_snapshot(saved) == expected_memory
    assert build_social_state_snapshot(saved) == expected_social

    events = persistence.replay_events(descent.id)
    store = AlphaCheckpointStore(tmp_path / "checkpoint", retention=4)
    store.write(
        "30c2-test-runtime",
        descent,
        events,
        simulation_config={"slice": "30C.2"},
        reason="30c2-test",
        created_at_unix_ms=3002002,
    )
    loaded = store.load_latest().crawl
    assert loaded.model_dump(mode="json") == expected_state
    assert build_social_memory_snapshot(loaded) == expected_memory
    assert build_social_state_snapshot(loaded) == expected_social


def test_same_canonical_source_history_reconstructs_identical_social_outcome() -> None:
    def run_once():
        _, brain, memory, _, lifecycle, descent, ids = _stack(seed="30c2-replay", count=6, strata=3)
        events = [
            _record(lifecycle, descent, "RESCUE", [ids[0], ids[1]]),
            _record(lifecycle, descent, "SHARED_RESOURCE", [ids[0], ids[1]]),
            _record(lifecycle, descent, "BETRAYAL", [ids[2], ids[3]]),
            _record(
                lifecycle,
                descent,
                "ENCOUNTER_RESOLVED",
                [ids[4], ids[5]],
                social_facts=[{
                    "observer_descender_id": ids[5],
                    "subject_descender_id": ids[4],
                    "memory_type": "witnessed_sacrifice",
                }],
            ),
        ]
        results = memory.process_history(descent, events)
        assert all(result.processed for result in results)
        brain.step(descent)
        memory.advance_decay(descent)
        return (
            build_social_memory_snapshot(descent),
            build_social_state_snapshot(descent),
            descent.modifiers[METADATA_KEY]["processed_source_event_ids"],
        )

    first_memory, first_social, first_sources = run_once()
    second_memory, second_social, second_sources = run_once()
    assert first_memory == second_memory
    assert first_social == second_social
    assert first_sources == second_sources
