from __future__ import annotations

from sqlalchemy import inspect

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_group_social_orchestration import GroupSocialOrchestrationService
from livingworld.underreach_highlight_story_arc import (
    HighlightPolicy,
    HighlightStoryArcService,
    HighlightTier,
    StoryArcStatus,
    StoryArcType,
    score_envelope,
    tier_for_score,
)
from livingworld.underreach_media_event_export import CanonicalMediaEventExporter
from livingworld.underreach_media_foundation import MediaPersistence
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService


def _stack(seed: str = "30-5-3-highlight"):
    canonical = CrawlPersistence("sqlite://")
    canonical.initialize()
    brain = BrainDrivenDescentService(canonical)
    ids = [f"descender_{index:03d}" for index in range(6)]
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
    media = MediaPersistence("sqlite://")
    media.initialize()
    detector = HighlightStoryArcService(media)
    detector.initialize()
    return canonical, descent, ids, memory, lifecycle, exporter, media, detector


def _event(lifecycle, descent, event_type: str, actors: list[str], *, danger: float = 0.0, data=None):
    payload = {"danger": danger, "state_changes": {"30_5_3_test": event_type}}
    if data:
        payload.update(data)
    return lifecycle.record_event(
        descent,
        event_type,
        f"30.5.3 canonical source {event_type}.",
        actor_ids=actors,
        location_id=descent.participants[actors[0]].current_location_id if actors else None,
        data=payload,
    )


def _register(media, exporter, descent, event):
    envelope = exporter.export_event(descent, event.id)
    media.register_envelope(envelope)
    return envelope


def test_roadmap_tier_boundaries_are_exact() -> None:
    policy = HighlightPolicy()
    assert tier_for_score(49, policy) == HighlightTier.ARCHIVE_ONLY
    assert tier_for_score(50, policy) == HighlightTier.CHRONICLE
    assert tier_for_score(69, policy) == HighlightTier.CHRONICLE
    assert tier_for_score(70, policy) == HighlightTier.MOTION_STORY
    assert tier_for_score(79, policy) == HighlightTier.MOTION_STORY
    assert tier_for_score(80, policy) == HighlightTier.ENHANCED_STILLS
    assert tier_for_score(89, policy) == HighlightTier.ENHANCED_STILLS
    assert tier_for_score(90, policy) == HighlightTier.LOCAL_ANIMATION
    assert tier_for_score(94, policy) == HighlightTier.LOCAL_ANIMATION
    assert tier_for_score(95, policy) == HighlightTier.CINEMATIC
    assert tier_for_score(100, policy) == HighlightTier.CINEMATIC


def test_low_signal_envelope_is_archive_only_and_not_persisted_as_highlight() -> None:
    _, descent, ids, _, lifecycle, exporter, media, detector = _stack(seed="30-5-3-low")
    event = _event(lifecycle, descent, "CAMP_NOTE", ids[:1], danger=0.0)
    envelope = _register(media, exporter, descent, event)

    evaluation = detector.evaluate(envelope)

    assert evaluation.selected is False
    assert evaluation.output_tier == HighlightTier.ARCHIVE_ONLY
    assert evaluation.score.total < 50
    assert evaluation.highlight_id is None
    assert detector.list_highlights() == ()


def test_high_signal_envelope_scores_deterministically_without_llm_or_provider() -> None:
    _, descent, ids, memory, lifecycle, exporter, media, detector = _stack(seed="30-5-3-high")
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
    envelope = _register(media, exporter, descent, current)

    first_score, first_reasons = score_envelope(envelope)
    second_score, second_reasons = score_envelope(envelope)
    evaluation = detector.evaluate(envelope)
    highlight = detector.get_highlight(evaluation.highlight_id)

    assert first_score == second_score == evaluation.score
    assert first_reasons == second_reasons == evaluation.reason_codes
    assert evaluation.selected is True
    assert evaluation.score.danger >= 18
    assert evaluation.score.rarity == 15
    assert evaluation.score.social_stakes == 20
    assert evaluation.score.outcome_reversal == 10
    assert evaluation.score.continuity == 15
    assert evaluation.score.visual_potential >= 4
    assert evaluation.score.total >= 80
    assert evaluation.output_tier in {HighlightTier.ENHANCED_STILLS, HighlightTier.LOCAL_ANIMATION, HighlightTier.CINEMATIC}
    assert highlight is not None
    assert highlight.llm_decision_used is False
    assert highlight.provider_invocation_used is False
    assert highlight.unreal_dependency is False
    assert highlight.presentation_can_mutate_simulation is False


def test_story_arc_upsert_is_idempotent_and_accumulates_canonical_provenance() -> None:
    _, descent, ids, memory, lifecycle, exporter, media, detector = _stack(seed="30-5-3-arc")
    first = _event(lifecycle, descent, "BETRAYAL", ids[:2], danger=0.75)
    assert memory.process_event(descent, first).processed
    first_envelope = _register(media, exporter, descent, first)
    detector.evaluate(first_envelope)

    second = _event(lifecycle, descent, "PROMISE_VIOLATED", ids[:2], danger=0.55)
    assert memory.process_event(descent, second).processed
    second_envelope = _register(media, exporter, descent, second)
    detector.evaluate(second_envelope)
    snapshot_before_repeat = detector.snapshot()
    repeated = detector.evaluate(second_envelope)
    snapshot_after_repeat = detector.snapshot()

    conflict_arcs = [arc for arc in detector.list_story_arcs() if arc.arc_type == StoryArcType.SOCIAL_CONFLICT]
    assert len(conflict_arcs) == 1
    arc = conflict_arcs[0]
    assert arc.subject_ids == tuple(sorted(ids[:2]))
    assert set(arc.envelope_ids) == {first_envelope.envelope_id, second_envelope.envelope_id}
    assert set(arc.source_event_ids) == {first.id, second.id}
    assert arc.occurrence_count == 2
    assert arc.status == StoryArcStatus.ACTIVE
    assert repeated.arc_ids == tuple(sorted(repeated.arc_ids))
    assert snapshot_after_repeat == snapshot_before_repeat


def test_terminal_death_closes_survival_arc() -> None:
    _, descent, ids, _, lifecycle, exporter, media, detector = _stack(seed="30-5-3-terminal")
    near = _event(lifecycle, descent, "NEAR_DEATH", ids[:1], danger=0.95)
    near_envelope = _register(media, exporter, descent, near)
    detector.evaluate(near_envelope)
    death = _event(lifecycle, descent, "DEATH", ids[:1], danger=1.0)
    death_envelope = _register(media, exporter, descent, death)
    detector.evaluate(death_envelope)

    arcs = [arc for arc in detector.list_story_arcs() if arc.arc_type == StoryArcType.SURVIVAL]
    assert len(arcs) == 1
    assert arcs[0].status == StoryArcStatus.CLOSED
    assert arcs[0].occurrence_count == 2
    assert set(arcs[0].source_event_ids) == {near.id, death.id}


def test_highlight_analysis_never_touches_canonical_database() -> None:
    canonical, descent, ids, _, lifecycle, exporter, media, detector = _stack(seed="30-5-3-separation")
    event = _event(lifecycle, descent, "RESCUE", ids[:2], danger=0.9)
    envelope = _register(media, exporter, descent, event)
    before_state = descent.model_dump(mode="json")
    before_rows = [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)]
    before_fingerprint = descent.fingerprint()

    detector.evaluate(envelope)

    assert descent.model_dump(mode="json") == before_state
    assert descent.fingerprint() == before_fingerprint
    assert [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)] == before_rows
    canonical_tables = set(inspect(canonical.engine).get_table_names())
    media_tables = set(inspect(media.engine).get_table_names())
    assert canonical_tables.isdisjoint(media_tables)
    assert "media_highlights" in media_tables
    assert "media_story_arcs" in media_tables


def test_evaluate_many_normalizes_input_order_and_final_snapshot_is_reproducible() -> None:
    def run(reverse: bool):
        _, descent, ids, memory, lifecycle, exporter, media, detector = _stack(seed="30-5-3-order")
        first = _event(lifecycle, descent, "BETRAYAL", ids[:2], danger=0.8)
        assert memory.process_event(descent, first).processed
        first_envelope = _register(media, exporter, descent, first)
        second = _event(lifecycle, descent, "PROMISE_VIOLATED", ids[:2], danger=0.6)
        assert memory.process_event(descent, second).processed
        second_envelope = _register(media, exporter, descent, second)
        values = [first_envelope, second_envelope]
        if reverse:
            values.reverse()
        evaluations = detector.evaluate_many(values)
        return evaluations, detector.snapshot()

    first_eval, first_snapshot = run(False)
    second_eval, second_snapshot = run(True)
    assert first_eval == second_eval
    assert first_snapshot == second_snapshot


def test_restart_reopens_same_highlights_and_arcs_without_duplication(tmp_path) -> None:
    canonical, descent, ids, memory, lifecycle, exporter, _, _ = _stack(seed="30-5-3-reopen")
    event = _event(lifecycle, descent, "BETRAYAL", ids[:2], danger=0.95)
    assert memory.process_event(descent, event).processed
    envelope = exporter.export_event(descent, event.id)
    database_url = f"sqlite:///{(tmp_path / 'media.sqlite3').as_posix()}"

    media = MediaPersistence(database_url)
    media.initialize()
    media.register_envelope(envelope)
    detector = HighlightStoryArcService(media)
    detector.initialize()
    first = detector.evaluate(envelope)
    first_snapshot = detector.snapshot()

    reopened = MediaPersistence(database_url)
    reopened.initialize()
    reopened_detector = HighlightStoryArcService(reopened)
    reopened_detector.initialize()
    repeated = reopened_detector.evaluate(envelope)
    second_snapshot = reopened_detector.snapshot()

    assert repeated == first
    assert second_snapshot == first_snapshot
    assert len(reopened_detector.list_highlights()) == len(detector.list_highlights())
    assert len(reopened_detector.list_story_arcs()) == len(detector.list_story_arcs())
