from fastapi.testclient import TestClient

from livingworld.camera_director import AutomatedCameraDirector
from livingworld.crawl_domain import CrawlEvent
from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.headless_mvp_simulation import HeadlessCrawlMVP
from livingworld.live_channels import ViewerChannelRegistry, build_crawler_channel, build_viewer_channels, channel_focus_plan
from livingworld.spectator_api import SpectatorRepository, create_spectator_app
from livingworld.story_highlights import StoryArcDetector


def make_crawl(seed="batch6", crawlers=4, floors=2):
    service = CrawlLifecycleService()
    crawl = service.create_seeded_crawl(
        seed=seed,
        crawler_ids=[f"npc_{index:03d}" for index in range(crawlers)],
        floor_count=floors,
    )
    service.start(crawl)
    return service, crawl


def event(event_id, tick, event_type, actors, *, location="loc", importance=0.7, danger=0.5, parents=(), relationship=0.0, reversal=False, floor=1):
    return CrawlEvent(
        id=event_id,
        crawl_id="crawl-test",
        floor_number=floor,
        tick=tick,
        event_type=event_type,
        summary=event_type.replace("_", " ").title(),
        actor_ids=list(actors),
        location_id=location,
        data={
            "semantic": {
                "importance_score": importance,
                "rarity_score": 0.7,
                "danger_level": danger,
                "reversal": reversal,
                "relationship_impact": relationship,
                "audience_interest_tags": ["action"] if "COMBAT" in event_type else [],
                "causal_parent_ids": list(parents),
            }
        },
    )


def test_camera_plan_is_deterministic_and_never_mutates_crawl():
    _, crawl = make_crawl(seed="camera-determinism")
    events = [
        event("e1", 2, "COMBAT_STARTED", ["npc_000", "npc_001"], importance=0.6),
        event("e2", 3, "NEAR_DEATH", ["npc_000"], importance=0.82, danger=0.95, parents=("e1",), reversal=True),
        event("e3", 5, "RESCUE", ["npc_000", "npc_002"], importance=0.9, danger=0.85, parents=("e2",), reversal=True),
        event("e4", 7, "COMBAT_ENDED", ["npc_000", "npc_002"], importance=0.68),
    ]
    before = crawl.fingerprint()
    director = AutomatedCameraDirector()
    first = director.plan(crawl, events, start_tick=0, end_tick=12)
    second = director.plan(crawl, reversed(events), start_tick=0, end_tick=12)

    assert first.digest == second.digest
    assert first.as_dict() == second.as_dict()
    assert first.shots
    assert len(first.shots) < len(events) + 1
    assert crawl.fingerprint() == before


def test_camera_director_holds_subject_instead_of_thrashing():
    _, crawl = make_crawl(seed="camera-hold")
    events = [
        event(f"e{tick}", tick, "COMBAT_STARTED", ["npc_000", "npc_001"], importance=0.55 + tick * 0.01)
        for tick in range(1, 10)
    ]
    plan = AutomatedCameraDirector(min_hold_ticks=4).plan(crawl, events, start_tick=1, end_tick=15)
    assert len(plan.shots) <= 3
    assert all(shot.end_tick >= shot.start_tick for shot in plan.shots)


def test_channel_focus_is_pure_and_promotes_watched_context_logically():
    _, crawl = make_crawl(seed="channel-focus", crawlers=5)
    watched = "npc_000"
    neighbor = "npc_001"
    crawl.participants[neighbor].current_location_id = crawl.participants[watched].current_location_id
    before = crawl.fingerprint()

    plan = channel_focus_plan(crawl, [watched])

    assert plan["effective_tiers"][watched] == "A"
    assert neighbor in plan["local_active_ids"]
    assert plan["effective_tiers"][neighbor] == "B"
    assert plan["mutates_authoritative_state"] is False
    assert crawl.fingerprint() == before


def test_multiple_viewers_can_follow_different_channels_without_state_changes():
    _, crawl = make_crawl(seed="multi-viewer", crawlers=4)
    registry = ViewerChannelRegistry()
    registry.follow("viewer-a", "npc_000", crawl)
    registry.follow("viewer-b", "npc_002", crawl)
    events = [event("e1", 1, "COMBAT_STARTED", ["npc_000", "npc_001"])]
    before = crawl.fingerprint()

    channels = build_viewer_channels(crawl, events, registry)

    assert channels["viewer-a"]["crawler"]["npc_id"] == "npc_000"
    assert channels["viewer-b"]["crawler"]["npc_id"] == "npc_002"
    assert registry.focused_ids() == {"npc_000", "npc_002"}
    assert crawl.fingerprint() == before


def test_story_detector_builds_explainable_rescue_comeback_from_event_ids():
    events = [
        event("e1", 10, "COMBAT_STARTED", ["npc_000", "npc_001"], importance=0.5),
        event("e2", 12, "NEAR_DEATH", ["npc_000"], importance=0.82, danger=0.98, parents=("e1",), reversal=True),
        event("e3", 14, "RESCUE", ["npc_000", "npc_002"], importance=0.92, danger=0.88, parents=("e2",), relationship=0.7, reversal=True),
        event("e4", 17, "COMBAT_ENDED", ["npc_000", "npc_002"], importance=0.65, parents=("e3",)),
    ]
    arcs = StoryArcDetector(minimum_score=0.3).analyze(events)

    assert arcs
    rescue = next(arc for arc in arcs if arc.story_type == "rescue_comeback")
    assert {"e2", "e3"}.issubset(set(rescue.event_ids))
    assert "authoritative events" in rescue.explanation
    assert any("RESCUE:e3" == item for item in rescue.evidence)


def test_story_detector_can_connect_cross_floor_relationship_reversal():
    events = [
        event("b1", 20, "BETRAYAL", ["npc_000", "npc_001"], importance=0.9, relationship=-0.9, floor=2),
        event("b2", 45, "NEAR_DEATH", ["npc_000"], importance=0.78, danger=0.9, floor=3),
        event("b3", 47, "RESCUE", ["npc_000", "npc_001"], importance=0.94, relationship=0.85, reversal=True, floor=3),
    ]
    arcs = StoryArcDetector(lookback_ticks=40, minimum_score=0.3).analyze(events)

    assert arcs
    assert any(set(arc.floor_numbers) == {2, 3} for arc in arcs)
    assert any("b1" in arc.event_ids and "b3" in arc.event_ids for arc in arcs)


def test_story_detector_keeps_personal_highlights_bounded_when_combat_events_are_broad():
    crowd = [f"npc_{index:03d}" for index in range(25)]
    events = [
        event("g1", 30, "COMBAT_STARTED", crowd, importance=0.62),
        event("g2", 31, "COMBAT_HIT", crowd, importance=0.48, parents=("g1",)),
        event("g3", 32, "NEAR_DEATH", ["npc_000"], importance=0.84, danger=0.97, parents=("g2",), reversal=True),
        event("g4", 34, "RESCUE", ["npc_000", "npc_001"], importance=0.94, danger=0.88, parents=("g3",), relationship=0.8, reversal=True),
        event("g5", 36, "COMBAT_ENDED", crowd, importance=0.66, parents=("g4",)),
    ]
    arcs = StoryArcDetector(minimum_score=0.3, max_anchor_events=8).analyze(events)

    rescue = next(arc for arc in arcs if arc.story_type == "rescue_comeback")
    assert set(rescue.participant_ids) <= {"npc_000", "npc_001"}
    assert len(rescue.event_ids) <= 8
    assert {"g3", "g4"}.issubset(set(rescue.event_ids))


def test_story_detector_deduplicates_signature_rescue_from_generic_battle_anchors():
    crowd = [f"npc_{index:03d}" for index in range(25)]
    events = [
        event("d1", 20, "COMBAT_STARTED", crowd, importance=0.82),
        event("d2", 21, "COMBAT_HIT", crowd, importance=0.80, parents=("d1",)),
        event("d3", 22, "NEAR_DEATH", ["npc_000"], importance=0.90, danger=0.99, parents=("d2",), reversal=True),
        event("d4", 24, "RESCUE", ["npc_000", "npc_001"], importance=0.96, danger=0.9, parents=("d3",), relationship=0.8, reversal=True),
        event("d5", 25, "COMBAT_ENDED", crowd, importance=0.84, parents=("d4",)),
    ]
    arcs = StoryArcDetector(minimum_score=0.3).analyze(events)

    rescue_arcs = [arc for arc in arcs if arc.story_type in {"rescue", "rescue_comeback"}]
    assert len(rescue_arcs) == 1
    assert {"d3", "d4"}.issubset(set(rescue_arcs[0].event_ids))
    assert set(rescue_arcs[0].participant_ids) <= {"npc_000", "npc_001"}
    assert len(rescue_arcs[0].event_ids) <= 16


def test_batch6_spectator_endpoints_are_read_only_and_renderable(tmp_path):
    persistence = CrawlPersistence(f"sqlite:///{tmp_path / 'batch6.db'}")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    crawl = service.create_seeded_crawl(
        seed="batch6-api",
        crawler_ids=[f"npc_{index:03d}" for index in range(12)],
        floor_count=2,
    )
    service.start(crawl)
    HeadlessCrawlMVP(service, intermission_ticks=2, director_interval=4).run(crawl, max_steps=5000)
    service.record_event(crawl, "NEAR_DEATH", "A crawler barely survived.", actor_ids=["npc_000"], data={"danger": 0.95})
    service.record_event(crawl, "RESCUE", "An ally returned to help.", actor_ids=["npc_000", "npc_001"], data={"relationship_impact": 0.75, "reversal": True})

    client = TestClient(create_spectator_app(SpectatorRepository(persistence, crawl.id)))
    before = crawl.fingerprint()
    channel = client.get("/api/spectator/channels/npc_000")
    camera = client.get("/api/spectator/camera/plan", params={"focus_actor_id": "npc_000"})
    highlights = client.get("/api/spectator/highlights", params={"minimum_score": 0.3})

    assert channel.status_code == 200
    assert channel.json()["channel_id"] == "crawler:npc_000"
    assert "knowledge" not in str(channel.json())
    assert camera.status_code == 200
    assert camera.json()["shots"]
    assert highlights.status_code == 200
    assert highlights.json()
    assert any("event_ids" in arc and "explanation" in arc for arc in highlights.json())
    reloaded = persistence.load_crawl(crawl.id)
    assert reloaded is not None
    assert reloaded.fingerprint() == before
