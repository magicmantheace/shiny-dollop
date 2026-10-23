from __future__ import annotations

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_delver_chronicle_profile import (
    ChapterKind,
    DelverChronicleProfileService,
    ProfileStatus,
)
from livingworld.underreach_group_social_orchestration import GroupSocialOrchestrationService
from livingworld.underreach_highlight_story_arc import HighlightStoryArcService, HighlightTier
from livingworld.underreach_media_event_export import CanonicalMediaEventExporter
from livingworld.underreach_media_foundation import MediaPersistence
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService


def test_archive_only_death_still_creates_terminal_chronicle_chapter() -> None:
    canonical = CrawlPersistence("sqlite://")
    canonical.initialize()
    brain = BrainDrivenDescentService(canonical)
    ids = [f"descender_{index:03d}" for index in range(4)]
    delver_id = ids[0]
    descent = brain.create(
        seed="30-5-4-terminal-archive-only",
        descender_ids=ids,
        stratum_count=3,
    )
    brain.start(descent)

    SocialMemoryEvolutionService(canonical).initialize(descent)
    SocialIntentExecutionService(canonical).initialize(descent)
    PartiesAlliancesLeadershipService(canonical).initialize(descent)
    RivalryBetrayalSocialConflictService(canonical).initialize(descent)
    GroupSocialOrchestrationService(canonical, brain=brain).initialize(descent)

    event = CrawlLifecycleService(canonical).record_event(
        descent,
        "DEATH",
        "30.5.4 archive-only terminal regression source.",
        actor_ids=[delver_id],
        location_id=descent.participants[delver_id].current_location_id,
        data={
            "danger": 1.0,
            "state_changes": {"30_5_4_terminal_archive_only": True},
        },
    )
    envelope = CanonicalMediaEventExporter(canonical).export_event(descent, event.id)

    media = MediaPersistence("sqlite://")
    media.initialize()
    media.register_envelope(envelope)
    detector = HighlightStoryArcService(media)
    detector.initialize()
    evaluation = detector.evaluate(envelope)

    assert evaluation.selected is False
    assert evaluation.output_tier == HighlightTier.ARCHIVE_ONLY
    assert evaluation.highlight_id is None

    chronicle = DelverChronicleProfileService(media, highlights=detector)
    chronicle.initialize()
    profile = chronicle.process(envelope)[0]
    chapters = chronicle.list_chapters(delver_id=delver_id)

    assert profile.status == ProfileStatus.DEAD
    assert profile.chronicle_closed is True
    assert len(chapters) == 1
    assert chapters[0].chapter_kind == ChapterKind.TERMINAL
    assert chapters[0].highlight_id is None
    assert chapters[0].terminal is True
    assert chapters[0].title_code == "TERMINAL_DEATH"
    assert set(chapters[0].source_event_ids) == {event.id}
    assert chapters[0].allowed_fact_ids
