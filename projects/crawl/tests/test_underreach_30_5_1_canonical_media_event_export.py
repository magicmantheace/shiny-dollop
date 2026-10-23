from __future__ import annotations

import pytest

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.runtime_checkpoint import payload_digest
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_group_social_orchestration import GroupSocialOrchestrationService
from livingworld.underreach_media_event_export import (
    PHASE,
    PROTOCOL,
    CanonicalMediaEventExporter,
    MediaEventExportError,
    validate_media_envelope,
)
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService
from livingworld.underreach_social_state import SocialStateService


def _stack(seed: str = "30-5-1-media-export", *, count: int = 6, strata: int = 3):
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    brain = BrainDrivenDescentService(persistence)
    ids = [f"descender_{index:03d}" for index in range(count)]
    descent = brain.create(seed=seed, descender_ids=ids, stratum_count=strata)
    brain.start(descent)
    memory = SocialMemoryEvolutionService(persistence)
    memory.initialize(descent)
    social = SocialIntentExecutionService(persistence)
    social.initialize(descent)
    parties = PartiesAlliancesLeadershipService(persistence)
    parties.initialize(descent)
    conflict = RivalryBetrayalSocialConflictService(persistence)
    conflict.initialize(descent)
    orchestration = GroupSocialOrchestrationService(persistence, brain=brain)
    orchestration.initialize(descent)
    exporter = CanonicalMediaEventExporter(persistence)
    return persistence, brain, memory, social, parties, conflict, orchestration, exporter, descent, ids


def _canonical_event(persistence, descent, event_type: str, actors: list[str], marker: str):
    lifecycle = CrawlLifecycleService(persistence)
    return lifecycle.record_event(
        descent,
        event_type,
        f"30.5.1 canonical source event {marker}.",
        actor_ids=actors,
        location_id=descent.participants[actors[0]].current_location_id if actors else None,
        data={
            "danger": 0.81,
            "state_changes": {"proof_marker": marker},
            "media_test": {"marker": marker, "supported": True},
        },
    )


def test_repeat_export_is_deterministic_and_strictly_read_only() -> None:
    persistence, _, _, _, _, _, _, exporter, descent, ids = _stack(seed="30-5-1-repeat")
    event = _canonical_event(persistence, descent, "RESCUE", ids[:2], "repeat")
    before = descent.model_dump(mode="json")
    before_fingerprint = descent.fingerprint()
    before_history = list(descent.history_event_ids)
    before_rows = [item.model_dump(mode="json") for item in persistence.replay_events(descent.id)]

    first = exporter.export_event(descent, event.id)
    second = exporter.export_event(descent, event.id)

    assert first == second
    assert first.digest == second.digest
    assert first.idempotency_key == second.idempotency_key
    assert validate_media_envelope(first)
    assert descent.model_dump(mode="json") == before
    assert descent.fingerprint() == before_fingerprint
    assert descent.history_event_ids == before_history
    assert [item.model_dump(mode="json") for item in persistence.replay_events(descent.id)] == before_rows


def test_requested_source_ids_are_normalized_to_canonical_ledger_order() -> None:
    persistence, _, _, _, _, _, _, exporter, descent, ids = _stack(seed="30-5-1-order")
    first_event = _canonical_event(persistence, descent, "WITNESSED_BRAVERY", ids[:2], "first")
    second_event = _canonical_event(persistence, descent, "NEAR_DEATH", ids[1:3], "second")

    envelope = exporter.export_events(descent, [second_event.id, first_event.id])

    assert envelope.source_event_ids == (first_event.id, second_event.id)
    assert envelope.source_event_types == ("WITNESSED_BRAVERY", "NEAR_DEATH")
    assert envelope.history_prefix_last_event_id == second_event.id
    assert envelope.history_prefix_count == descent.history_event_ids.index(second_event.id) + 1


def test_envelope_contains_event_provenance_semantics_and_social_context() -> None:
    persistence, _, memory, _, _, _, _, exporter, descent, ids = _stack(seed="30-5-1-context")
    state = SocialStateService(persistence)
    state.adjust_dimension(
        descent,
        ids[1],
        ids[0],
        "trust",
        0.42,
        reason_code="30_5_1.test_export_context",
    )
    event = _canonical_event(persistence, descent, "RESCUE", ids[:2], "context")
    processed = memory.process_event(descent, event)
    assert processed.processed

    envelope = exporter.export_event(descent, event.id)

    assert envelope.schema == PROTOCOL
    assert envelope.phase == PHASE == "30.5"
    assert envelope.source_event_ids == (event.id,)
    assert envelope.canonical_fingerprint == descent.fingerprint()
    assert envelope.presentation_can_mutate_simulation is False
    assert envelope.unreal_dependency is False
    assert envelope.cloud_ai_dependency is False
    assert envelope.paid_ai_dependency is False
    assert set(envelope.delver_ids) == set(ids[:2])
    assert envelope.semantic_context[0]["event_id"] == event.id
    assert envelope.semantic_context[0]["semantic"]["danger_level"] == 0.81
    assert envelope.social_context["relationships"]
    assert any(
        record["source_descender_id"] == ids[1]
        and record["target_descender_id"] == ids[0]
        and record["trust"] > 0.42
        for record in envelope.social_context["relationships"]
    )
    assert any(record["source_event_ids"] == [event.id] for record in envelope.social_context["memories"])
    predicates = {fact.predicate for fact in envelope.allowed_facts}
    assert "event_type" in predicates
    assert "canonical_summary" in predicates
    assert "data.state_changes.proof_marker" in predicates
    assert "data.media_test.supported" in predicates
    assert all(set(fact.source_event_ids) <= {event.id} for fact in envelope.allowed_facts)


def test_missing_event_rejected_without_any_canonical_mutation() -> None:
    _, _, _, _, _, _, _, exporter, descent, _ = _stack(seed="30-5-1-missing")
    before = descent.model_dump(mode="json")
    with pytest.raises(MediaEventExportError, match="missing canonical Ledger event"):
        exporter.export_event(descent, "crawl_event_missing")
    assert descent.model_dump(mode="json") == before


def test_duplicate_event_ids_are_rejected_without_mutation() -> None:
    persistence, _, _, _, _, _, _, exporter, descent, ids = _stack(seed="30-5-1-duplicate")
    event = _canonical_event(persistence, descent, "RESCUE", ids[:2], "duplicate")
    before = descent.model_dump(mode="json")
    with pytest.raises(MediaEventExportError, match="must be unique"):
        exporter.export_events(descent, [event.id, event.id])
    assert descent.model_dump(mode="json") == before


def test_export_digest_is_reproducible_across_independent_identical_runs() -> None:
    def run_once():
        persistence, _, _, _, _, _, _, exporter, descent, ids = _stack(seed="30-5-1-independent")
        event = _canonical_event(persistence, descent, "RESCUE", ids[:2], "independent")
        envelope = exporter.export_event(descent, event.id)
        return envelope.model_dump(mode="json"), payload_digest(descent.model_dump(mode="json"))

    first_envelope, first_state = run_once()
    second_envelope, second_state = run_once()
    assert first_envelope == second_envelope
    assert first_state == second_state


def test_30_5_1_has_no_media_provider_or_generation_side_effect_contract() -> None:
    persistence, _, _, _, _, _, _, exporter, descent, ids = _stack(seed="30-5-1-boundary")
    event = _canonical_event(persistence, descent, "RESCUE", ids[:2], "boundary")
    envelope = exporter.export_event(descent, event.id)

    payload = envelope.model_dump(mode="json")
    assert payload["phase"] == "30.5"
    assert payload["visual_identity_refs"] == []
    assert payload["unreal_dependency"] is False
    assert payload["cloud_ai_dependency"] is False
    assert payload["paid_ai_dependency"] is False
    assert "provider" not in payload
    assert "generated_prose" not in payload
    assert "generated_image" not in payload
    assert "generated_video" not in payload
