from __future__ import annotations

import pytest

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.runtime_checkpoint import AlphaCheckpointStore
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_social_state import (
    METADATA_KEY,
    RELATIONSHIP_CHANGED_EVENT,
    RELATIONSHIP_CREATED_EVENT,
    SocialStateError,
    SocialStateService,
    build_social_state_snapshot,
    validate_social_state,
)


def _stack(seed: str = "30c1-social-state-test", *, count: int = 4, strata: int = 2):
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    brain_descent = BrainDrivenDescentService(persistence)
    ids = [f"descender_{index:03d}" for index in range(count)]
    descent = brain_descent.create(seed=seed, descender_ids=ids, stratum_count=strata)
    social = SocialStateService(persistence)
    social.initialize(descent)
    return persistence, brain_descent, social, descent, ids


def test_absent_relationship_reads_neutral_without_canonical_mutation() -> None:
    _, _, social, descent, ids = _stack()
    before_state = descent.model_dump(mode="json")
    before_history = list(descent.history_event_ids)

    relationship = social.get(descent, ids[0], ids[1])

    assert relationship.source_descender_id == ids[0]
    assert relationship.target_descender_id == ids[1]
    assert relationship.trust == 0.0
    assert relationship.respect == 0.0
    assert relationship.affection == 0.0
    assert relationship.fear == 0.0
    assert relationship.resentment == 0.0
    assert relationship.gratitude == 0.0
    assert relationship.rivalry == 0.0
    assert relationship.familiarity == 0.0
    assert descent.model_dump(mode="json") == before_state
    assert descent.history_event_ids == before_history
    assert descent.modifiers[METADATA_KEY]["relationship_count"] == 0


def test_directed_relationships_are_independent_and_sparse() -> None:
    _, _, social, descent, ids = _stack()

    forward = social.adjust_dimension(
        descent,
        ids[0],
        ids[1],
        "trust",
        0.35,
        reason_code="test.shared_risk",
    )
    reverse = social.adjust_dimension(
        descent,
        ids[1],
        ids[0],
        "trust",
        -0.2,
        reason_code="test.suspicion",
    )

    assert forward.changed and forward.edge_created
    assert reverse.changed and reverse.edge_created
    assert social.get(descent, ids[0], ids[1]).trust == 0.35
    assert social.get(descent, ids[1], ids[0]).trust == -0.2
    assert descent.modifiers[METADATA_KEY]["relationship_count"] == 2
    assert validate_social_state(descent)


def test_ensure_relationship_is_deterministic_and_idempotent() -> None:
    persistence, _, social, descent, ids = _stack()
    before_count = len(descent.history_event_ids)

    first = social.ensure_relationship(
        descent,
        ids[0],
        ids[2],
        reason_code="test.explicit_edge",
    )
    after_first = len(descent.history_event_ids)
    second = social.ensure_relationship(
        descent,
        ids[0],
        ids[2],
        reason_code="test.explicit_edge",
    )

    assert first == second
    assert after_first == before_count + 1
    assert len(descent.history_event_ids) == after_first
    assert descent.modifiers[METADATA_KEY]["relationship_count"] == 1
    events = persistence.list_events(descent.id, event_type=RELATIONSHIP_CREATED_EVENT)
    assert len(events) == 1
    assert events[0].data["source_descender_id"] == ids[0]
    assert events[0].data["target_descender_id"] == ids[2]


def test_relationship_dimension_bounds_clamp_deterministically() -> None:
    _, _, social, descent, ids = _stack()

    social.adjust_dimension(descent, ids[0], ids[1], "trust", 2.0, reason_code="test.max_trust")
    assert social.get(descent, ids[0], ids[1]).trust == 1.0

    social.adjust_dimension(descent, ids[0], ids[1], "trust", -2.0, reason_code="test.min_trust")
    assert social.get(descent, ids[0], ids[1]).trust == -1.0

    social.adjust_dimension(descent, ids[0], ids[1], "familiarity", 2.0, reason_code="test.max_familiarity")
    assert social.get(descent, ids[0], ids[1]).familiarity == 1.0

    social.adjust_dimension(descent, ids[0], ids[1], "familiarity", -2.0, reason_code="test.min_familiarity")
    assert social.get(descent, ids[0], ids[1]).familiarity == 0.0

    before = descent.model_dump(mode="json")
    with pytest.raises(SocialStateError):
        social.adjust_dimension(descent, ids[0], ids[1], "trust", 2.01, reason_code="test.invalid_delta")
    assert descent.model_dump(mode="json") == before


def test_no_change_at_bound_is_side_effect_free() -> None:
    _, _, social, descent, ids = _stack()
    social.adjust_dimension(descent, ids[0], ids[1], "trust", 2.0, reason_code="test.max_trust")
    before_state = descent.model_dump(mode="json")
    before_history = list(descent.history_event_ids)

    result = social.adjust_dimension(
        descent,
        ids[0],
        ids[1],
        "trust",
        0.5,
        reason_code="test.already_clamped",
    )

    assert not result.changed
    assert result.ledger_event_id is None
    assert descent.model_dump(mode="json") == before_state
    assert descent.history_event_ids == before_history


def test_invalid_relationship_requests_reject_without_mutation() -> None:
    _, _, social, descent, ids = _stack()

    cases = [
        lambda: social.get(descent, ids[0], ids[0]),
        lambda: social.get(descent, ids[0], "missing_descender"),
        lambda: social.adjust_dimension(
            descent, ids[0], ids[1], "unknown", 0.1, reason_code="test.invalid_dimension"
        ),
        lambda: social.adjust_dimension(
            descent, ids[0], ids[1], "trust", 0.1, reason_code="Narrative prose is invalid"
        ),
        lambda: social.adjust_dimension(
            descent,
            ids[0],
            ids[1],
            "trust",
            0.1,
            reason_code="test.bad_source",
            source_event_id="missing_event",
        ),
    ]

    for operation in cases:
        before = descent.model_dump(mode="json")
        before_history = list(descent.history_event_ids)
        with pytest.raises(SocialStateError):
            operation()
        assert descent.model_dump(mode="json") == before
        assert descent.history_event_ids == before_history


def test_relationship_change_is_bound_to_structured_ledger_provenance() -> None:
    persistence, _, social, descent, ids = _stack()
    source_event_id = descent.modifiers[METADATA_KEY]["initialized_event_id"]

    result = social.adjust_dimension(
        descent,
        ids[0],
        ids[1],
        "gratitude",
        0.4,
        reason_code="test.authoritative_help",
        source_event_id=source_event_id,
    )

    assert result.changed
    assert result.ledger_event_id is not None
    event = persistence.events_by_ids([result.ledger_event_id])[0]
    assert event.event_type == RELATIONSHIP_CHANGED_EVENT
    assert event.actor_ids == [ids[0], ids[1]]
    assert event.data["source_descender_id"] == ids[0]
    assert event.data["target_descender_id"] == ids[1]
    assert event.data["dimension"] == "gratitude"
    assert event.data["previous_value"] == 0.0
    assert event.data["requested_delta"] == 0.4
    assert event.data["resulting_value"] == 0.4
    assert event.data["edge_created"] is True
    assert event.data["reason_code"] == "test.authoritative_help"
    assert event.data["source_event_id"] == source_event_id
    assert result.ledger_event_id in descent.modifiers[METADATA_KEY]["mutation_event_ids"]


def test_persistence_and_checkpoint_restore_social_state_exactly(tmp_path) -> None:
    persistence, _, social, descent, ids = _stack(seed="30c1-checkpoint")
    social.adjust_dimension(descent, ids[0], ids[1], "trust", 0.3, reason_code="test.trust")
    social.adjust_dimension(descent, ids[1], ids[0], "respect", 0.55, reason_code="test.respect")
    social.ensure_relationship(descent, ids[2], ids[3], reason_code="test.neutral_edge")

    expected_state = descent.model_dump(mode="json")
    expected_snapshot = build_social_state_snapshot(descent)

    saved = persistence.load_crawl(descent.id)
    assert saved is not None
    assert saved.model_dump(mode="json") == expected_state
    assert build_social_state_snapshot(saved) == expected_snapshot

    events = persistence.replay_events(descent.id)
    store = AlphaCheckpointStore(tmp_path / "checkpoint", retention=4)
    written = store.write(
        "30c1-test-runtime",
        descent,
        events,
        simulation_config={"slice": "30C.1"},
        reason="30c1-test",
        created_at_unix_ms=3001001,
    )
    loaded = store.load_latest().crawl

    assert loaded.model_dump(mode="json") == expected_state
    assert build_social_state_snapshot(loaded) == expected_snapshot
    assert written.payload["canonical"]["state"]["modifiers"][METADATA_KEY] == descent.modifiers[METADATA_KEY]


def test_independent_identical_social_sequences_produce_identical_digests() -> None:
    def run_once():
        _, _, social, descent, ids = _stack(seed="30c1-determinism", count=5, strata=3)
        social.adjust_dimension(descent, ids[0], ids[1], "trust", 0.25, reason_code="proof.trust")
        social.adjust_dimension(descent, ids[1], ids[0], "respect", 0.4, reason_code="proof.respect")
        social.adjust_dimension(descent, ids[0], ids[2], "fear", 0.15, reason_code="proof.fear")
        social.adjust_dimension(descent, ids[2], ids[0], "resentment", 0.2, reason_code="proof.resentment")
        social.ensure_relationship(descent, ids[3], ids[4], reason_code="proof.neutral_contact")
        return descent.model_dump(mode="json"), build_social_state_snapshot(descent)

    first_state, first_snapshot = run_once()
    second_state, second_snapshot = run_once()

    assert first_state == second_state
    assert first_snapshot == second_snapshot
    assert first_snapshot["digest"] == second_snapshot["digest"]
