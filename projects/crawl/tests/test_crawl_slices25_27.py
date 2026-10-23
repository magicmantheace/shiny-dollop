from livingworld.ai_dramatization import DramatizationPlanner, validate_dramatization_job
from livingworld.commentary_system import CommentaryMode, GroundedCommentaryGenerator, validate_commentary_grounding
from livingworld.crawl_domain import CrawlEvent
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.highlight_reels import HighlightReelAssembler, validate_highlight_package
from livingworld.story_highlights import StoryArc


def make_crawl(seed="batch7", crawlers=4, floors=2):
    service = CrawlLifecycleService()
    crawl = service.create_seeded_crawl(
        seed=seed,
        crawler_ids=[f"npc_{index:03d}" for index in range(crawlers)],
        floor_count=floors,
    )
    service.start(crawl)
    return crawl


def event(event_id, tick, event_type, actors, *, summary=None, floor=1, importance=0.8):
    return CrawlEvent(
        id=event_id,
        crawl_id="crawl-test",
        floor_number=floor,
        tick=tick,
        event_type=event_type,
        summary=summary or event_type.replace("_", " ").title(),
        actor_ids=list(actors),
        location_id="loc",
        data={
            "semantic": {
                "importance_score": importance,
                "danger_level": 0.8,
                "rarity_score": 0.7,
                "reversal": event_type in {"NEAR_DEATH", "RESCUE"},
                "relationship_impact": 0.7 if event_type == "RESCUE" else 0.0,
                "audience_interest_tags": [],
                "causal_parent_ids": [],
            }
        },
    )


def rescue_story():
    return StoryArc(
        id="story_rescue",
        story_type="rescue_comeback",
        score=0.94,
        start_tick=10,
        end_tick=14,
        floor_numbers=(1,),
        participant_ids=("npc_000", "npc_001"),
        event_ids=("e1", "e2", "e3"),
        explanation="Rescue comeback fixture.",
        evidence=("COMBAT_STARTED:e1", "NEAR_DEATH:e2", "RESCUE:e3"),
    )


def rescue_events():
    return [
        event("e1", 10, "COMBAT_STARTED", ["npc_000", "npc_002"], importance=0.55),
        event("e2", 12, "NEAR_DEATH", ["npc_000"], importance=0.9),
        event("e3", 14, "RESCUE", ["npc_000", "npc_001"], importance=0.95),
    ]


def test_commentary_is_deterministic_and_every_line_has_canonical_citations():
    events = rescue_events()
    generator = GroundedCommentaryGenerator()
    first = generator.generate(events, story=rescue_story(), mode=CommentaryMode.DOCUMENTARY)
    second = generator.generate(reversed(events), story=rescue_story(), mode=CommentaryMode.DOCUMENTARY)

    assert first.as_dict() == second.as_dict()
    assert validate_commentary_grounding(first, {event.id for event in events})
    assert all(line.source_event_ids for line in first.lines)
    assert all(line.factual for line in first.lines)


def test_crawler_recap_filters_to_requested_crawler_only():
    events = rescue_events() + [event("e4", 16, "ITEM_ACQUIRED", ["npc_003"])]
    script = GroundedCommentaryGenerator().generate(
        events,
        actor_id="npc_000",
        mode=CommentaryMode.CRAWLER_RECAP,
    )

    assert script.lines
    assert "e4" not in script.source_event_ids
    assert set(script.source_event_ids) == {"e1", "e2", "e3"}


def test_highlight_package_connects_story_replay_camera_commentary_and_outputs_without_mutating_crawl():
    crawl = make_crawl(seed="highlight-package")
    events = rescue_events()
    before = crawl.fingerprint()

    first = HighlightReelAssembler().assemble(crawl, events, rescue_story())
    second = HighlightReelAssembler().assemble(crawl, reversed(events), rescue_story())

    assert first.as_dict() == second.as_dict()
    assert first.replay_window.start_tick <= rescue_story().start_tick
    assert first.replay_window.end_tick >= rescue_story().end_tick
    assert first.camera_plan.shots
    assert first.commentary.lines
    assert first.timeline
    assert {output.value for output in first.outputs} == {"short_vertical", "standard_horizontal"}
    assert validate_highlight_package(first, {event.id for event in events})
    assert crawl.fingerprint() == before


def test_highlight_camera_targets_stay_with_story_participants_during_broad_context_events():
    crawl = make_crawl(seed="highlight-camera-scope", crawlers=25)
    crowd = [f"npc_{index:03d}" for index in range(25)]
    events = [
        event("wide", 8, "COMBAT_STARTED", crowd, importance=0.8),
        event("unrelated", 9, "CRAWLER_ADVANCED", ["npc_017"], importance=0.9),
        event("e1", 10, "COMBAT_STARTED", crowd, importance=0.7),
        event("e2", 12, "NEAR_DEATH", ["npc_000"], importance=0.95),
        event("e3", 14, "RESCUE", ["npc_000", "npc_001"], importance=0.99),
    ]

    package = HighlightReelAssembler().assemble(crawl, events, rescue_story())
    participants = set(rescue_story().participant_ids)

    assert package.camera_plan.shots
    assert all(set(shot.target_actor_ids).issubset(participants) for shot in package.camera_plan.shots)
    assert all("npc_017" not in shot.target_actor_ids for shot in package.camera_plan.shots)


def test_highlight_package_rejects_story_with_missing_event():
    crawl = make_crawl(seed="highlight-missing")
    broken = rescue_story().__class__(
        id="broken",
        story_type="rescue",
        score=0.8,
        start_tick=10,
        end_tick=14,
        floor_numbers=(1,),
        participant_ids=("npc_000",),
        event_ids=("e1", "missing"),
        explanation="broken",
        evidence=("COMBAT_STARTED:e1",),
    )
    try:
        HighlightReelAssembler().assemble(crawl, rescue_events(), broken)
    except ValueError as exc:
        assert "missing authoritative events" in str(exc)
    else:
        raise AssertionError("missing event reference should be rejected")


def test_dramatization_job_is_explicitly_noncanonical_and_fully_traceable():
    crawl = make_crawl(seed="drama-trace")
    events = rescue_events()
    package = HighlightReelAssembler().assemble(crawl, events, rescue_story())
    job = DramatizationPlanner().build_job(package, events, provider="test-provider", model="test-model")

    assert job.canonical is False
    assert job.relationship_to_canonical_replay == "optional_stylized_interpretation"
    assert set(job.source_event_ids) == set(package.authoritative_event_ids)
    assert all(scene.canonical is False for scene in job.scenes)
    assert all("non-canonical visualization" in scene.prompt for scene in job.scenes)
    assert validate_dramatization_job(job, {event.id for event in events})


def test_dramatization_validation_rejects_unknown_source_event():
    crawl = make_crawl(seed="drama-invalid")
    events = rescue_events()
    package = HighlightReelAssembler().assemble(crawl, events, rescue_story())
    job = DramatizationPlanner().build_job(package, events)

    assert not validate_dramatization_job(job, {"e1", "e2"})


def test_commentary_grounding_rejects_incomplete_authoritative_event_set():
    script = GroundedCommentaryGenerator().generate(rescue_events(), story=rescue_story())
    assert not validate_commentary_grounding(script, {"e1", "e2"})
