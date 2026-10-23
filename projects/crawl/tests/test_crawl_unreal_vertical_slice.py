from livingworld.camera_director import AutomatedCameraDirector
from livingworld.crawl_domain import CrawlEvent
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.presentation_staging import PresentationStagingResolver, validate_staging_manifest


def make_crawl(seed="unreal-stage", crawlers=6, floors=2):
    service = CrawlLifecycleService()
    crawl = service.create_seeded_crawl(
        seed=seed,
        crawler_ids=[f"npc_{index:03d}" for index in range(crawlers)],
        floor_count=floors,
    )
    service.start(crawl)
    return crawl


def event(event_id, tick, event_type, actors, *, data=None, summary=None):
    return CrawlEvent(
        id=event_id,
        crawl_id="crawl-test",
        floor_number=1,
        tick=tick,
        event_type=event_type,
        summary=summary or event_type.replace("_", " ").title(),
        actor_ids=list(actors),
        location_id="arena",
        data=data or {},
    )


def test_staging_is_deterministic_and_uses_canonical_history_order():
    crawl = make_crawl()
    events = [
        event("e1", 10, "COMBAT_STARTED", ["npc_000", "npc_001"], data={"encounter_id": "fight"}),
        event("e2", 10, "COMBAT_HIT", ["npc_000", "enemy_a"], data={"encounter_id": "fight"}),
        event("e3", 10, "ENEMY_DEFEATED", ["npc_000", "enemy_a"], data={"encounter_id": "fight"}),
    ]
    crawl.history_event_ids.extend(["e1", "e2", "e3"])
    resolver = PresentationStagingResolver(max_actors=4)

    first = resolver.resolve(crawl, events, focus_actor_ids=["npc_000"], presentation_seed="stable")
    second = resolver.resolve(crawl, reversed(events), focus_actor_ids=["npc_000"], presentation_seed="stable")

    assert first.as_dict() == second.as_dict()
    assert [beat.event_id for beat in first.beats] == ["e1", "e2", "e3"]
    assert first.authoritative is False


def test_floor_wide_combat_can_be_visually_bounded_without_rewriting_source_event():
    crawl = make_crawl(crawlers=20)
    crowd = [f"npc_{index:03d}" for index in range(20)]
    events = [
        event("e1", 20, "COMBAT_STARTED", crowd, data={"encounter_id": "crowd", "enemy_ids": ["enemy_a"]}),
        event("e2", 20, "COMBAT_HIT", ["npc_000", "enemy_a"], data={"encounter_id": "crowd"}),
        event("e3", 20, "CRAWLER_DAMAGED", ["npc_000", "enemy_a"], data={"encounter_id": "crowd"}),
        event("e4", 20, "ENEMY_DEFEATED", ["npc_000", "enemy_a"], data={"encounter_id": "crowd"}),
    ]
    crawl.history_event_ids.extend(["e1", "e2", "e3", "e4"])

    manifest = PresentationStagingResolver(max_actors=4).resolve(
        crawl,
        events,
        focus_actor_ids=["npc_000"],
        presentation_seed="crowd-bounded",
    )

    staged = {actor.actor_id for actor in manifest.actors}
    assert len(staged) <= 4
    assert "npc_000" in staged
    assert "enemy_a" in staged
    start_beat = next(beat for beat in manifest.beats if beat.event_id == "e1")
    assert set(start_beat.actor_ids).issubset(staged)
    assert events[0].actor_ids == crowd


def test_combat_roles_translate_to_animation_intents_without_changing_event_truth():
    crawl = make_crawl(crawlers=2)
    events = [
        event("e1", 3, "COMBAT_HIT", ["npc_000", "enemy_a"]),
        event("e2", 4, "CRAWLER_DAMAGED", ["npc_000", "enemy_a"]),
        event("e3", 5, "CRAWLER_INJURED", ["npc_000", "enemy_a"]),
        event("e4", 6, "CRAWLER_RETREATED", ["npc_000"]),
    ]
    crawl.history_event_ids.extend(["e1", "e2", "e3", "e4"])

    manifest = PresentationStagingResolver(max_actors=3).resolve(crawl, events, focus_actor_ids=["npc_000"])
    beats = {beat.event_id: beat for beat in manifest.beats}

    assert beats["e1"].action == "attack_hit"
    assert beats["e1"].performer_id == "npc_000"
    assert beats["e1"].target_id == "enemy_a"
    assert beats["e2"].performer_id == "enemy_a"
    assert beats["e2"].target_id == "npc_000"
    assert beats["e3"].action == "injury_reaction"
    assert beats["e4"].action == "retreat"


def test_camera_cues_are_translated_to_presentation_seconds_and_clamped_to_staged_cast():
    crawl = make_crawl(crawlers=5)
    events = [
        event("e1", 8, "COMBAT_STARTED", ["npc_000", "npc_001", "npc_002", "npc_003", "npc_004"]),
        event("e2", 8, "COMBAT_HIT", ["npc_000", "enemy_a"]),
        event("e3", 9, "ENEMY_DEFEATED", ["npc_000", "enemy_a"]),
    ]
    crawl.history_event_ids.extend(["e1", "e2", "e3"])
    camera = AutomatedCameraDirector(minimum_score=0.0).plan(
        crawl,
        events,
        start_tick=8,
        end_tick=9,
        focus_actor_id="npc_000",
        max_shots=8,
    )

    manifest = PresentationStagingResolver(max_actors=3).resolve(
        crawl,
        events,
        focus_actor_ids=["npc_000"],
        camera_plan=camera,
    )
    staged = {actor.actor_id for actor in manifest.actors}

    assert manifest.camera_cues
    assert all(cue.end_seconds > cue.start_seconds for cue in manifest.camera_cues)
    assert all(set(cue.target_actor_ids).issubset(staged) for cue in manifest.camera_cues)


def test_staging_validation_rejects_incomplete_authoritative_event_set():
    crawl = make_crawl(crawlers=2)
    events = [event("e1", 1, "COMBAT_HIT", ["npc_000", "enemy_a"])]
    crawl.history_event_ids.append("e1")
    manifest = PresentationStagingResolver().resolve(crawl, events, focus_actor_ids=["npc_000"])

    assert validate_staging_manifest(manifest, {"e1"})
    assert not validate_staging_manifest(manifest, set())
