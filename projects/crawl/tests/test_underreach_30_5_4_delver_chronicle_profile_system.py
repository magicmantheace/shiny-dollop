from __future__ import annotations

from sqlalchemy import inspect

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_delver_chronicle_profile import (
    ChapterKind,
    ChroniclePolicy,
    DelverChronicleProfileService,
    ProfileStatus,
)
from livingworld.underreach_group_social_orchestration import GroupSocialOrchestrationService
from livingworld.underreach_highlight_story_arc import HighlightStoryArcService
from livingworld.underreach_media_event_export import CanonicalMediaEventExporter
from livingworld.underreach_media_foundation import MediaPersistence
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService
from livingworld.underreach_social_state import SocialStateService


def _stack(seed: str = "30-5-4-chronicle", *, database_url: str = "sqlite://"):
    canonical = CrawlPersistence("sqlite://")
    canonical.initialize()
    brain = BrainDrivenDescentService(canonical)
    ids = [f"descender_{index:03d}" for index in range(8)]
    descent = brain.create(seed=seed, descender_ids=ids, stratum_count=3)
    brain.start(descent)
    memory = SocialMemoryEvolutionService(canonical)
    memory.initialize(descent)
    social = SocialIntentExecutionService(canonical)
    social.initialize(descent)
    parties = PartiesAlliancesLeadershipService(canonical)
    parties.initialize(descent)
    conflict = RivalryBetrayalSocialConflictService(canonical)
    conflict.initialize(descent)
    orchestration = GroupSocialOrchestrationService(canonical, brain=brain)
    orchestration.initialize(descent)
    lifecycle = CrawlLifecycleService(canonical)
    exporter = CanonicalMediaEventExporter(canonical)
    media = MediaPersistence(database_url)
    media.initialize()
    detector = HighlightStoryArcService(media)
    detector.initialize()
    chronicle = DelverChronicleProfileService(media, highlights=detector)
    chronicle.initialize()
    return canonical, descent, ids, memory, social, parties, lifecycle, exporter, media, detector, chronicle


def _event(lifecycle, descent, event_type: str, actors: list[str], *, danger: float = 0.0, data=None):
    payload = {"danger": danger, "state_changes": {"30_5_4_test": event_type}}
    if data:
        payload.update(data)
    return lifecycle.record_event(
        descent,
        event_type,
        f"30.5.4 canonical source {event_type}.",
        actor_ids=actors,
        location_id=descent.participants[actors[0]].current_location_id if actors else None,
        data=payload,
    )


def _register(media, exporter, descent, event):
    envelope = exporter.export_event(descent, event.id)
    media.register_envelope(envelope)
    return envelope


def _accept_recruitment(social, descent, source: str, target: str) -> str:
    offered = social.execute(descent, social.propose(descent, source, "recruit", target_descender_id=target))
    assert offered.executed and offered.resolved_offer_id is not None
    accepted = social.execute(
        descent,
        social.propose(
            descent,
            target,
            "accept_recruitment",
            target_descender_id=source,
            recruitment_offer_id=offered.resolved_offer_id,
        ),
    )
    assert accepted.executed
    return offered.resolved_offer_id


def _form_pair(social, parties, descent, source: str, target: str) -> str:
    offer_id = _accept_recruitment(social, descent, source, target)
    return parties.form_from_accepted_recruitment(descent, offer_id).party_id


def _high_signal(memory, lifecycle, descent, ids):
    prior = _event(lifecycle, descent, "BETRAYAL", ids[:2], danger=0.6)
    assert memory.process_event(descent, prior).processed
    current = _event(
        lifecycle,
        descent,
        "NEAR_DEATH_BETRAYAL_RELIC_COMEBACK",
        ids[:2],
        danger=1.0,
        data={
            "social_facts": [
                {
                    "observer_descender_id": ids[1],
                    "subject_descender_id": ids[0],
                    "memory_type": "betrayed",
                }
            ]
        },
    )
    assert memory.process_event(descent, current).processed
    return current


def test_highlight_creates_structured_chronicle_chapter_for_each_delver() -> None:
    _, descent, ids, memory, _, _, lifecycle, exporter, media, detector, chronicle = _stack(seed="30-5-4-highlight")
    event = _high_signal(memory, lifecycle, descent, ids)
    envelope = _register(media, exporter, descent, event)
    evaluation = detector.evaluate(envelope)
    assert evaluation.selected

    profiles = chronicle.process(envelope)

    assert {profile.delver_id for profile in profiles} == set(ids[:2])
    assert len(chronicle.list_chapters()) == 2
    for profile in profiles:
        assert profile.status == ProfileStatus.ACTIVE
        assert profile.chronicle_closed is False
        assert len(profile.chapter_ids) == 1
        chapter = chronicle.list_chapters(delver_id=profile.delver_id)[0]
        assert chapter.chapter_kind == ChapterKind.HIGHLIGHT
        assert chapter.highlight_id == evaluation.highlight_id
        assert chapter.generated_prose_used is False
        assert chapter.structured_only is True
        assert chapter.claim_verification_required is True
        assert set(chapter.source_event_ids) == {event.id}
        assert chapter.allowed_fact_ids


def test_profile_derives_party_alliance_and_directed_relationships_from_media_context() -> None:
    canonical, descent, ids, _, social, parties, lifecycle, exporter, media, detector, chronicle = _stack(seed="30-5-4-profile-context")
    left = _form_pair(social, parties, descent, ids[0], ids[1])
    right = _form_pair(social, parties, descent, ids[2], ids[3])
    alliance = parties.form_alliance(descent, left, right)
    state = SocialStateService(canonical)
    state.adjust_dimension(descent, ids[0], ids[1], "trust", 0.8, reason_code="30_5_4.ally")
    state.adjust_dimension(descent, ids[0], ids[2], "resentment", 0.85, reason_code="30_5_4.rival")
    event = _event(lifecycle, descent, "SOCIAL_PARTY_COORDINATION", ids[:3], danger=0.45)
    envelope = _register(media, exporter, descent, event)
    detector.evaluate(envelope)

    chronicle.process(envelope)
    profile = chronicle.get_profile(descent.id, ids[0])

    assert profile is not None
    assert profile.current_party_id == left
    assert alliance.alliance_id in profile.current_alliance_ids
    assert any(item.delver_id == ids[1] for item in profile.known_allies)
    assert any(item.delver_id == ids[2] for item in profile.known_rivals)
    assert profile.public_name is None
    assert profile.presentation_can_mutate_simulation is False
    assert profile.provider_invocation_used is False


def test_terminal_death_creates_terminal_chapter_and_permanently_closes_chronicle() -> None:
    _, descent, ids, _, _, _, lifecycle, exporter, media, detector, chronicle = _stack(seed="30-5-4-terminal")
    death = _event(lifecycle, descent, "DEATH", ids[:1], danger=1.0)
    envelope = _register(media, exporter, descent, death)
    detector.evaluate(envelope)

    profile = chronicle.process(envelope)[0]
    chapters = chronicle.list_chapters(delver_id=ids[0])

    assert profile.status == ProfileStatus.DEAD
    assert profile.chronicle_closed is True
    assert len(chapters) == 1
    assert chapters[0].chapter_kind == ChapterKind.TERMINAL
    assert chapters[0].terminal is True
    assert chapters[0].title_code == "TERMINAL_DEATH"


def test_quiet_meaningful_history_batches_into_configurable_recap() -> None:
    _, descent, ids, _, _, _, lifecycle, exporter, media, detector, _ = _stack(seed="30-5-4-quiet")
    policy = ChroniclePolicy(quiet_recap_min_envelopes=3)
    chronicle = DelverChronicleProfileService(media, policy=policy, highlights=detector)
    chronicle.initialize()
    envelopes = []
    for index in range(3):
        event = _event(lifecycle, descent, f"STRATUM_NOTE_{index}", ids[:1], danger=0.0)
        envelope = _register(media, exporter, descent, event)
        evaluation = detector.evaluate(envelope)
        assert evaluation.selected is False
        assert evaluation.arc_ids
        envelopes.append(envelope)
        chronicle.process(envelope)

    profile = chronicle.get_profile(descent.id, ids[0])
    chapters = chronicle.list_chapters(delver_id=ids[0])

    assert profile is not None
    assert profile.pending_quiet_envelope_ids == ()
    assert len(chapters) == 1
    assert chapters[0].chapter_kind == ChapterKind.QUIET_RECAP
    assert set(chapters[0].source_envelope_ids) == {item.envelope_id for item in envelopes}
    assert chapters[0].highlight_id is None


def test_repeat_processing_is_idempotent() -> None:
    _, descent, ids, memory, _, _, lifecycle, exporter, media, detector, chronicle = _stack(seed="30-5-4-repeat")
    event = _high_signal(memory, lifecycle, descent, ids)
    envelope = _register(media, exporter, descent, event)
    detector.evaluate(envelope)

    first = chronicle.process(envelope)
    first_snapshot = chronicle.snapshot()
    second = chronicle.process(envelope)
    second_snapshot = chronicle.snapshot()

    assert first == second
    assert first_snapshot == second_snapshot
    assert len(chronicle.list_profiles()) == 2
    assert len(chronicle.list_chapters()) == 2


def test_process_many_normalizes_input_order() -> None:
    def run(reverse: bool):
        _, descent, ids, _, _, _, lifecycle, exporter, media, detector, chronicle = _stack(seed="30-5-4-order")
        envelopes = []
        for index in range(3):
            event = _event(lifecycle, descent, f"STRATUM_NOTE_{index}", ids[:1], danger=0.0)
            envelope = _register(media, exporter, descent, event)
            detector.evaluate(envelope)
            envelopes.append(envelope)
        if reverse:
            envelopes.reverse()
        chronicle.process_many(envelopes)
        return chronicle.snapshot()

    assert run(False) == run(True)


def test_chronicle_tables_are_media_only_and_canonical_state_is_unchanged() -> None:
    canonical, descent, ids, memory, _, _, lifecycle, exporter, media, detector, chronicle = _stack(seed="30-5-4-separation")
    event = _high_signal(memory, lifecycle, descent, ids)
    envelope = _register(media, exporter, descent, event)
    detector.evaluate(envelope)
    before_state = descent.model_dump(mode="json")
    before_fingerprint = descent.fingerprint()
    before_rows = [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)]

    chronicle.process(envelope)

    assert descent.model_dump(mode="json") == before_state
    assert descent.fingerprint() == before_fingerprint
    assert [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)] == before_rows
    canonical_tables = set(inspect(canonical.engine).get_table_names())
    media_tables = set(inspect(media.engine).get_table_names())
    assert canonical_tables.isdisjoint(media_tables)
    assert "media_delver_profiles" in media_tables
    assert "media_chronicle_chapters" in media_tables


def test_file_backed_restart_preserves_profiles_and_chapters_without_duplication(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'media.sqlite3').as_posix()}"
    canonical, descent, ids, memory, _, _, lifecycle, exporter, media, detector, chronicle = _stack(
        seed="30-5-4-restart", database_url=database_url
    )
    event = _high_signal(memory, lifecycle, descent, ids)
    envelope = _register(media, exporter, descent, event)
    detector.evaluate(envelope)
    chronicle.process(envelope)
    first_snapshot = chronicle.snapshot()

    reopened_media = MediaPersistence(database_url)
    reopened_media.initialize()
    reopened_detector = HighlightStoryArcService(reopened_media)
    reopened_detector.initialize()
    reopened = DelverChronicleProfileService(reopened_media, highlights=reopened_detector)
    reopened.initialize()
    before_repeat = reopened.snapshot()
    reopened.process(envelope)
    after_repeat = reopened.snapshot()

    assert before_repeat == first_snapshot
    assert after_repeat == first_snapshot
    assert len(reopened.list_profiles()) == 2
    assert len(reopened.list_chapters()) == 2
