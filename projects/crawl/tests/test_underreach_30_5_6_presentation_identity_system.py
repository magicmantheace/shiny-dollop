from __future__ import annotations

from sqlalchemy import inspect

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_delver_chronicle_profile import DelverChronicleProfileService
from livingworld.underreach_group_social_orchestration import GroupSocialOrchestrationService
from livingworld.underreach_highlight_story_arc import HighlightStoryArcService
from livingworld.underreach_loot_cache_relic import METADATA_KEY as LOOT_METADATA_KEY, LootCacheRelicService
from livingworld.underreach_media_event_export import CanonicalMediaEventExporter
from livingworld.underreach_media_foundation import MediaPersistence
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_presentation_identity import (
    PROTOCOL,
    ReferenceKind,
    ReferenceStatus,
    PresentationIdentityError,
    PresentationIdentityService,
)
from livingworld.underreach_resources_survival import ResourcesSurvivalService
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService


IDS = [f"descender_{index:03d}" for index in range(8)]


def _stack(seed: str = "30-5-6-identity", *, database_url: str = "sqlite://"):
    canonical = CrawlPersistence("sqlite://")
    canonical.initialize()
    brain = BrainDrivenDescentService(canonical)
    descent = brain.create(seed=seed, descender_ids=IDS, stratum_count=3)
    brain.start(descent)
    memory = SocialMemoryEvolutionService(canonical)
    memory.initialize(descent)
    social = SocialIntentExecutionService(canonical)
    social.initialize(descent)
    parties = PartiesAlliancesLeadershipService(canonical)
    parties.initialize(descent)
    RivalryBetrayalSocialConflictService(canonical).initialize(descent)
    GroupSocialOrchestrationService(canonical, brain=brain).initialize(descent)
    lifecycle = CrawlLifecycleService(canonical)
    exporter = CanonicalMediaEventExporter(canonical)
    media = MediaPersistence(database_url)
    media.initialize()
    detector = HighlightStoryArcService(media)
    detector.initialize()
    chronicle = DelverChronicleProfileService(media, highlights=detector)
    chronicle.initialize()
    identities = PresentationIdentityService(media, chronicle=chronicle)
    identities.initialize()
    return canonical, descent, memory, lifecycle, exporter, media, detector, chronicle, identities


def _event(lifecycle, descent, event_type: str, actors: list[str], *, danger: float = 0.0, data=None):
    payload = {"danger": danger, "state_changes": {"30_5_6_test": event_type}}
    if data:
        payload.update(data)
    return lifecycle.record_event(
        descent,
        event_type,
        f"30.5.6 canonical source {event_type}.",
        actor_ids=actors,
        location_id=descent.participants[actors[0]].current_location_id if actors else None,
        data=payload,
    )


def _register(media, exporter, descent, event):
    envelope = exporter.export_event(descent, event.id)
    media.register_envelope(envelope)
    return envelope


def _betrayal_fact():
    return {
        "social_facts": [
            {
                "observer_descender_id": IDS[1],
                "subject_descender_id": IDS[0],
                "memory_type": "betrayed",
            }
        ]
    }


def _high_profile(seed: str = "30-5-6-high", *, database_url: str = "sqlite://"):
    stack = _stack(seed, database_url=database_url)
    canonical, descent, memory, lifecycle, exporter, media, detector, chronicle, identities = stack
    prior = _event(lifecycle, descent, "BETRAYAL", IDS[:2], danger=0.6)
    assert memory.process_event(descent, prior).processed
    current = _event(
        lifecycle,
        descent,
        "NEAR_DEATH_BETRAYAL_RELIC_COMEBACK",
        IDS[:2],
        danger=1.0,
        data=_betrayal_fact(),
    )
    assert memory.process_event(descent, current).processed
    envelope = _register(media, exporter, descent, current)
    evaluation = detector.evaluate(envelope)
    assert evaluation.selected
    chronicle.process(envelope)
    profile = chronicle.get_profile(descent.id, IDS[0])
    assert profile is not None and profile.chapter_ids
    return (*stack, profile, envelope)


def _route(descent, descender_id: str, target_sector_id: str) -> list[str]:
    participant = descent.participants[descender_id]
    floor = descent.floors[participant.current_floor]
    start = participant.current_location_id
    assert start is not None
    parent: dict[str, str | None] = {start: None}
    queue = [start]
    while queue:
        current = queue.pop(0)
        if current == target_sector_id:
            break
        for neighbor in sorted(floor.locations[current].adjacency):
            if neighbor not in parent:
                parent[neighbor] = current
                queue.append(neighbor)
    assert target_sector_id in parent
    path = []
    current: str | None = target_sector_id
    while current is not None:
        path.append(current)
        current = parent[current]
    return list(reversed(path))


def _claim_relic(canonical, descent, delver_id: str) -> tuple[LootCacheRelicService, str]:
    loot = LootCacheRelicService(canonical)
    survival = ResourcesSurvivalService(canonical)
    cache = next(
        item
        for item in descent.modifiers[LOOT_METADATA_KEY]["caches"]
        if item["stratum_number"] == descent.current_floor
    )
    for sector_id in _route(descent, delver_id, cache["sector_id"])[1:]:
        loot.commit_descender_position(descent, delver_id, sector_id)
    survival.open_cache(descent, cache["cache_id"], delver_id)
    relic_id = next(item["id"] for item in cache["blueprints"] if item["kind"] == "relic")
    loot.claim_ground_item(descent, relic_id, delver_id)
    return loot, relic_id


def test_media_relevant_profile_gets_versioned_identity_with_pending_reference_slots() -> None:
    *_, identities, profile, _ = _high_profile(seed="30-5-6-basic")

    state = identities.ensure_identity(profile)

    assert state.identity.protocol == PROTOCOL
    assert state.identity.identity_version == 1
    assert state.binding.active_identity_id == state.identity.identity_id
    assert state.binding.current_equipment_revision_id == state.equipment_revision.revision_id
    assert state.identity.deterministic_seed >= 0
    assert [slot.kind for slot in state.identity.reference_slots] == [
        ReferenceKind.PORTRAIT,
        ReferenceKind.FACE_REFERENCE,
        ReferenceKind.THREE_QUARTER,
        ReferenceKind.FULL_BODY_FRONT,
        ReferenceKind.FULL_BODY_SIDE,
        ReferenceKind.COMBAT_REFERENCE,
    ]
    assert all(slot.status == ReferenceStatus.PENDING_GENERATION for slot in state.identity.reference_slots)
    assert all(slot.generated is False and slot.artifact_id is None for slot in state.identity.reference_slots)
    assert state.equipment_revision.reference_slot.kind == ReferenceKind.CURRENT_EQUIPMENT
    assert state.equipment_revision.reference_slot.generated is False
    assert state.identity.presentation_traits == {}
    assert state.identity.canonical_identity_fields_added is False
    assert state.identity.provider_invocation_used is False


def test_repeat_identity_sync_is_idempotent() -> None:
    *_, identities, profile, _ = _high_profile(seed="30-5-6-repeat")

    first = identities.ensure_identity(profile)
    first_snapshot = identities.snapshot()
    second = identities.ensure_identity(profile)
    second_snapshot = identities.snapshot()

    assert second == first
    assert second_snapshot == first_snapshot
    assert len(identities.list_identities(profile_id=profile.profile_id)) == 1
    assert len(identities.list_equipment_revisions(identity_id=first.identity.identity_id)) == 1


def test_renderer_profile_change_creates_new_presentation_version_without_changing_canonical_state() -> None:
    canonical, descent, _, _, _, _, _, _, identities, profile, _ = _high_profile(seed="30-5-6-version")
    before_state = descent.model_dump(mode="json")
    before_fingerprint = descent.fingerprint()
    before_ledger = [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)]

    first = identities.ensure_identity(profile, renderer_profile="capability:image_reference_conditioning")
    second = identities.ensure_identity(profile, renderer_profile="capability:image_reference_conditioning_v2")

    assert first.identity.identity_version == 1
    assert second.identity.identity_version == 2
    assert second.identity.identity_id != first.identity.identity_id
    assert second.identity.deterministic_seed != first.identity.deterministic_seed
    assert second.binding.identity_version_count == 2
    assert second.binding.active_identity_id == second.identity.identity_id
    versions = identities.list_identities(profile_id=profile.profile_id)
    assert [item.identity_version for item in versions] == [1, 2]
    assert descent.model_dump(mode="json") == before_state
    assert descent.fingerprint() == before_fingerprint
    assert [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)] == before_ledger


def test_visible_equipment_change_creates_new_equipment_revision_but_not_new_identity() -> None:
    canonical, descent, memory, lifecycle, exporter, media, detector, chronicle, identities = _stack(seed="30-5-6-equipment")
    loot, relic_id = _claim_relic(canonical, descent, IDS[0])
    data = _betrayal_fact()
    data["item_id"] = relic_id
    event = _event(lifecycle, descent, "NEAR_DEATH_BETRAYAL_RELIC_COMEBACK", IDS[:2], danger=1.0, data=data)
    assert memory.process_event(descent, event).processed
    envelope = _register(media, exporter, descent, event)
    assert detector.evaluate(envelope).selected
    chronicle.process(envelope)
    profile = chronicle.get_profile(descent.id, IDS[0])
    assert profile is not None
    assert any(item.item_id == relic_id for item in profile.notable_equipment)

    first = identities.ensure_identity(profile)
    assert any(item.item_id == relic_id for item in first.equipment_revision.equipment)

    loot.drop_owned_item(descent, relic_id, IDS[0])
    update_event = _event(lifecycle, descent, "EQUIPMENT_REFERENCE_UPDATE", IDS[:1], danger=0.0, data={"item_id": relic_id})
    update_envelope = _register(media, exporter, descent, update_event)
    detector.evaluate(update_envelope)
    chronicle.process(update_envelope)
    updated_profile = chronicle.get_profile(descent.id, IDS[0])
    assert updated_profile is not None

    second = identities.ensure_identity(updated_profile)

    assert second.identity.identity_id == first.identity.identity_id
    assert second.identity.identity_version == 1
    assert second.equipment_revision.revision_id != first.equipment_revision.revision_id
    assert second.equipment_revision.revision_index == 2
    assert second.equipment_revision.equipment == ()
    assert second.equipment_revision.source_envelope_id == update_envelope.envelope_id
    assert second.binding.current_equipment_revision_id == second.equipment_revision.revision_id
    assert len(identities.list_equipment_revisions(identity_id=first.identity.identity_id)) == 2


def test_return_to_previous_equipment_digest_reuses_existing_revision() -> None:
    canonical, descent, memory, lifecycle, exporter, media, detector, chronicle, identities = _stack(seed="30-5-6-equipment-reuse")
    loot, relic_id = _claim_relic(canonical, descent, IDS[0])
    data = _betrayal_fact()
    data["item_id"] = relic_id
    event = _event(lifecycle, descent, "NEAR_DEATH_BETRAYAL_RELIC_COMEBACK", IDS[:2], danger=1.0, data=data)
    assert memory.process_event(descent, event).processed
    envelope = _register(media, exporter, descent, event)
    detector.evaluate(envelope)
    chronicle.process(envelope)
    first_profile = chronicle.get_profile(descent.id, IDS[0])
    assert first_profile is not None
    first = identities.ensure_identity(first_profile)

    loot.drop_owned_item(descent, relic_id, IDS[0])
    dropped = _event(lifecycle, descent, "EQUIPMENT_REFERENCE_UPDATE", IDS[:1], data={"item_id": relic_id})
    dropped_envelope = _register(media, exporter, descent, dropped)
    detector.evaluate(dropped_envelope)
    chronicle.process(dropped_envelope)
    dropped_profile = chronicle.get_profile(descent.id, IDS[0])
    assert dropped_profile is not None
    dropped_state = identities.ensure_identity(dropped_profile)
    assert dropped_state.equipment_revision.equipment == ()
    assert dropped_state.equipment_revision.source_envelope_id == dropped_envelope.envelope_id

    relic_sector = descent.items[relic_id].location_id
    assert relic_sector is not None
    for sector_id in _route(descent, IDS[0], relic_sector)[1:]:
        loot.commit_descender_position(descent, IDS[0], sector_id)
    loot.claim_ground_item(descent, relic_id, IDS[0])
    reclaimed = _event(lifecycle, descent, "EQUIPMENT_REFERENCE_UPDATE", IDS[:1], data={"item_id": relic_id})
    reclaimed_envelope = _register(media, exporter, descent, reclaimed)
    detector.evaluate(reclaimed_envelope)
    chronicle.process(reclaimed_envelope)
    reclaimed_profile = chronicle.get_profile(descent.id, IDS[0])
    assert reclaimed_profile is not None
    third = identities.ensure_identity(reclaimed_profile)

    assert third.equipment_revision.revision_id == first.equipment_revision.revision_id
    assert third.binding.current_equipment_revision_id == first.equipment_revision.revision_id
    assert len(identities.list_equipment_revisions(identity_id=first.identity.identity_id)) == 2


def test_non_media_relevant_profile_cannot_allocate_identity() -> None:
    _, descent, _, lifecycle, exporter, media, detector, chronicle, identities = _stack(seed="30-5-6-not-relevant")
    event = _event(lifecycle, descent, "CAMP_NOTE", IDS[:1], danger=0.0)
    envelope = _register(media, exporter, descent, event)
    evaluation = detector.evaluate(envelope)
    assert evaluation.selected is False and not evaluation.arc_ids
    chronicle.process(envelope)
    profile = chronicle.get_profile(descent.id, IDS[0])
    assert profile is not None and not profile.chapter_ids and not profile.chronicle_closed

    try:
        identities.ensure_identity(profile)
    except PresentationIdentityError as exc:
        assert "not media-relevant" in str(exc)
    else:
        raise AssertionError("non-media-relevant profile unexpectedly received presentation identity")


def test_identity_tables_are_media_only() -> None:
    canonical, _, _, _, _, media, _, _, identities, profile, _ = _high_profile(seed="30-5-6-separation")
    identities.ensure_identity(profile)

    canonical_tables = set(inspect(canonical.engine).get_table_names())
    media_tables = set(inspect(media.engine).get_table_names())
    assert canonical_tables.isdisjoint(media_tables)
    assert "media_presentation_identities" in media_tables
    assert "media_presentation_equipment_revisions" in media_tables
    assert "media_presentation_identity_bindings" in media_tables


def test_file_backed_restart_preserves_identity_and_reference_state(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'media.sqlite3').as_posix()}"
    canonical, descent, memory, lifecycle, exporter, media, detector, chronicle, identities = _stack(
        seed="30-5-6-restart", database_url=database_url
    )
    event = _event(
        lifecycle,
        descent,
        "NEAR_DEATH_BETRAYAL_RELIC_COMEBACK",
        IDS[:2],
        danger=1.0,
        data=_betrayal_fact(),
    )
    assert memory.process_event(descent, event).processed
    envelope = _register(media, exporter, descent, event)
    detector.evaluate(envelope)
    chronicle.process(envelope)
    profile = chronicle.get_profile(descent.id, IDS[0])
    assert profile is not None
    first = identities.ensure_identity(profile)
    first_snapshot = identities.snapshot()

    reopened_media = MediaPersistence(database_url)
    reopened_media.initialize()
    reopened_detector = HighlightStoryArcService(reopened_media)
    reopened_detector.initialize()
    reopened_chronicle = DelverChronicleProfileService(reopened_media, highlights=reopened_detector)
    reopened_chronicle.initialize()
    reopened_identities = PresentationIdentityService(reopened_media, chronicle=reopened_chronicle)
    reopened_identities.initialize()
    reopened_profile = reopened_chronicle.get_profile(descent.id, IDS[0])
    assert reopened_profile is not None
    repeated = reopened_identities.ensure_identity(reopened_profile)

    assert repeated == first
    assert reopened_identities.snapshot() == first_snapshot
