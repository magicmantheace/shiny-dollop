from copy import deepcopy
import json

from fastapi.testclient import TestClient
import pytest

import livingworld.live_presentation_bridge as live_bridge
from livingworld.crawl_domain import CrawlEvent
from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.feed_api import create_feed_app
from livingworld.live_presentation_bridge import (
    LIVE_PROTOCOL,
    LiveLedgerBuffer,
    LivePresentationConsumer,
    LivePresentationScheduler,
)
from livingworld.spectator_api import SpectatorRepository


def event(index, *, tick=None, event_type="CRAWLER_MOVED", actors=("descender_a",), descent_id="descent_a"):
    return CrawlEvent(
        id=f"ledger_{index:03d}",
        crawl_id=descent_id,
        floor_number=1,
        tick=index if tick is None else tick,
        event_type=event_type,
        summary="authoritative event",
        actor_ids=list(actors),
        location_id="sector_a",
        data={},
    )


def crawl_fixture(*, persistence=None):
    service = CrawlLifecycleService(persistence)
    crawl = service.create_seeded_crawl(
        seed="underreach-live-tests",
        crawler_ids=["descender_a", "descender_b"],
        floor_count=2,
        crawl_id="descent_a",
    )
    service.start(crawl)
    return crawl


def bootstrap(scheduler, crawl):
    return scheduler.bootstrap(crawl, environment={"environment_id": "stone_dungeon_v1", "build_once": True})


def test_buffer_orders_a_page_and_deduplicates_without_mutating_events():
    source = [event(2), event(1), event(1)]
    before = [item.model_dump() for item in source]
    buffer = LiveLedgerBuffer("descent_a", presentation_delay_ticks=0)
    accepted = buffer.push(source)
    assert [item.id for item in accepted] == ["ledger_001", "ledger_002"]
    assert [item.id for item in buffer.consume_ready()] == ["ledger_001", "ledger_002"]
    assert buffer.dropped_duplicate_count == 1
    assert before == [item.model_dump() for item in source]


def test_buffer_rejects_delivery_older_than_its_canonical_cursor():
    buffer = LiveLedgerBuffer("descent_a", presentation_delay_ticks=0)
    buffer.push([event(2)])
    assert buffer.push([event(1)]) == []
    assert buffer.out_of_order_rejection_count == 1


def test_buffer_delay_and_resume_cursor_are_monotonic():
    buffer = LiveLedgerBuffer("descent_a", presentation_delay_ticks=2)
    buffer.push([event(i) for i in range(1, 6)])
    assert [item.tick for item in buffer.consume_ready()] == [1, 2, 3]
    first_cursor = buffer.latest_consumed_event_id
    assert buffer.consume_ready() == []
    buffer.push([event(6)])
    assert [item.tick for item in buffer.consume_ready()] == [4]
    assert buffer.latest_consumed_event_id != first_cursor


def test_scheduler_is_incremental_deterministic_and_spawns_each_actor_once():
    crawl = crawl_fixture()
    events = [
        event(1),
        event(2, event_type="COMBAT_HIT", actors=("descender_a", "enemy_a")),
        event(3, event_type="ENEMY_DEFEATED", actors=("descender_a", "enemy_a")),
    ]
    streams = []
    for _ in range(2):
        scheduler = LivePresentationScheduler("descent_a", presentation_seed="stable", focus_actor_ids=["descender_a"])
        bootstrap(scheduler, crawl)
        frames = [scheduler.schedule([item], authoritative_tick=item.tick + 3) for item in events]
        streams.append((frames, scheduler.diagnostics()["command_stream_digest"]))
        assert scheduler.schedule(events, authoritative_tick=9) is None
        assert sum(command["type"] == "spawn_actor" for frame in frames for command in frame["commands"]) == 1
    assert streams[0] == streams[1]


@pytest.mark.parametrize(
    ("slot", "forward_reach", "lateral_reach"),
    [
        ("humanoid.combat.attack.default", 93.7539, -0.2642),
        ("humanoid.combat.attack.02", 97.7749, 9.3016),
        ("humanoid.combat.attack.03", 124.5260, -2.7440),
        ("humanoid.combat.attack.charged", 98.0318, -9.2859),
    ],
)
def test_live_contact_staging_uses_measured_forward_and_lateral_reach(
    monkeypatch, slot, forward_reach, lateral_reach
):
    crawl = crawl_fixture()
    scheduler = LivePresentationScheduler(
        "descent_a", presentation_seed="stable", focus_actor_ids=["descender_a"]
    )
    bootstrap(scheduler, crawl)
    monkeypatch.setattr(live_bridge, "choose_attack_slot", lambda *args, **kwargs: slot)

    result = scheduler.schedule(
        [event(2, event_type="COMBAT_HIT", actors=("descender_a", "enemy_a"))],
        authoritative_tick=5,
    )
    moves = {
        command["actor_id"]: command["transform"]
        for command in result["commands"]
        if command["type"] == "move_actor"
    }
    attack = next(command for command in result["commands"] if command["type"] == "play_attack")

    assert moves["enemy_a"]["x"] - moves["descender_a"]["x"] == pytest.approx(forward_reach)
    assert moves["descender_a"]["y"] - moves["enemy_a"]["y"] == pytest.approx(lateral_reach)
    assert attack["expected_root_separation_cm"] == pytest.approx(forward_reach)
    assert attack["expected_lateral_reach_cm"] == pytest.approx(lateral_reach)
    assert attack["force_root_lock"] is True


def test_terminal_actor_persists_and_future_motion_cannot_resurrect_it():
    crawl = crawl_fixture()
    scheduler = LivePresentationScheduler("descent_a", presentation_seed="stable", focus_actor_ids=["descender_a"])
    bootstrap(scheduler, crawl)
    terminal = scheduler.schedule(
        [event(1, event_type="CRAWLER_DIED", actors=("descender_a",))], authoritative_tick=4
    )
    future = scheduler.schedule([event(2, actors=("descender_a",))], authoritative_tick=5)
    assert "descender_a" in terminal["terminal_actor_ids"]
    assert all(command["type"] not in {"move_actor", "play_locomotion", "play_attack", "play_reaction"} for command in future["commands"])
    assert scheduler.actors["descender_a"].terminal is True


def test_bootstrap_is_once_and_incremental_frames_never_resend_environment():
    crawl = crawl_fixture()
    scheduler = LivePresentationScheduler("descent_a", presentation_seed="stable", focus_actor_ids=["descender_a"])
    initial = bootstrap(scheduler, crawl)
    assert initial["protocol"] == LIVE_PROTOCOL
    assert initial["environment"]["build_once"] is True
    frame = scheduler.schedule([event(1)], authoritative_tick=4)
    assert "environment" not in frame
    try:
        bootstrap(scheduler, crawl)
    except RuntimeError:
        pass
    else:
        raise AssertionError("second bootstrap should fail")


def test_alpha_procedural_descenders_embed_deterministic_renderer_neutral_identity():
    service = CrawlLifecycleService()
    crawl = service.create_seeded_crawl(
        seed="underreach-live-tests",
        crawler_ids=["live_descender_004", "live_descender_005"],
        floor_count=2,
        crawl_id="descent_a",
    )
    service.start(crawl)
    before = crawl.fingerprint()
    payloads = []
    for _ in range(2):
        scheduler = LivePresentationScheduler(
            "descent_a",
            presentation_seed="stable",
            focus_actor_ids=["live_descender_004", "live_descender_005"],
        )
        payloads.append(bootstrap(scheduler, crawl))
    actors = {item["actor_id"]: item for item in payloads[0]["actors"]}
    assert actors["live_descender_004"]["character_dna"]["species"] == "human"
    assert actors["live_descender_005"]["character_dna"]["species"] == "dwarf"
    for actor in actors.values():
        assert actor["character_dna"]["protocol"] == "underreach.character-dna.v1"
        assert actor["character_renderer_manifest"]["protocol"] == "underreach.character-renderer-manifest.v1"
        assert not any(token in json.dumps(actor["character_dna"]) for token in ("/Game/", "PersistentLevel"))
    assert payloads[0] == payloads[1]
    assert crawl.fingerprint() == before


def test_procedural_contact_profile_is_used_only_for_29a1_descenders():
    service = CrawlLifecycleService()
    crawl = service.create_seeded_crawl(
        seed="underreach-live-tests",
        crawler_ids=["live_descender_004"],
        floor_count=2,
        crawl_id="descent_a",
    )
    service.start(crawl)
    scheduler = LivePresentationScheduler(
        "descent_a", presentation_seed="stable", focus_actor_ids=["live_descender_004"]
    )
    bootstrap(scheduler, crawl)
    result = scheduler.schedule(
        [event(2, event_type="COMBAT_HIT", actors=("live_descender_004", "enemy_a"))],
        authoritative_tick=5,
    )
    attack = next(command for command in result["commands"] if command["type"] == "play_attack")
    assert attack["procedural_species"] == "human"
    assert attack["contact_effector"] == "hand_r"
    assert attack["duration_seconds"] == pytest.approx(1.5)
    assert attack["contact_phase"] == pytest.approx(25 / 45)
    assert attack["measured_effector_reach_cm"] == pytest.approx(51.9084)
    assert attack["target_surface_offset_cm"] == pytest.approx(28.0)
    assert attack["minimum_visual_root_separation_cm"] == pytest.approx(70.0)
    assert attack["expected_root_separation_cm"] == pytest.approx(79.9084)
    moves = {
        command["actor_id"]: command["transform"]
        for command in result["commands"]
        if command["type"] == "move_actor"
    }
    assert moves["enemy_a"]["x"] - moves["live_descender_004"]["x"] == pytest.approx(79.9084)


def test_procedural_contact_targets_torso_surface_without_body_interpenetration():
    for species, profile in live_bridge.PROCEDURAL_ATTACK_PRESENTATION.items():
        assert profile["target_surface_offset_cm"] > 0.0, species
        assert (
            profile["forward_reach_cm"] + profile["target_surface_offset_cm"]
            >= profile["minimum_visual_root_separation_cm"]
        ), species
        assert profile["contact_effector"] in {"hand_l", "hand_r", "foot_l", "foot_r"}


def test_consumer_is_idempotent_rejects_rewind_and_reports_missing_ranges():
    crawl = crawl_fixture()
    scheduler = LivePresentationScheduler("descent_a", presentation_seed="stable", focus_actor_ids=["descender_a"])
    initial = bootstrap(scheduler, crawl)
    first = scheduler.schedule([event(1)], authoritative_tick=4)
    second = scheduler.schedule([event(2)], authoritative_tick=5)
    consumer = LivePresentationConsumer("descent_a")
    assert consumer.apply_bootstrap(initial) is True
    assert consumer.apply_bootstrap(initial) is False
    applied = consumer.apply_frame(first)
    assert applied
    assert consumer.apply_frame(first) == []
    assert consumer.duplicate_frames == 1
    assert consumer.apply_frame(second)
    assert consumer.apply_frame(first) == []
    assert consumer.latest_frame_sequence == 2
    older_scheduler = LivePresentationScheduler("descent_a", presentation_seed="other", focus_actor_ids=["descender_a"])
    bootstrap(older_scheduler, crawl)
    distinct_old = older_scheduler.schedule([event(1)], authoritative_tick=4)
    assert consumer.apply_frame(distinct_old) == []
    assert consumer.rejected_frames == 1

    gap_consumer = LivePresentationConsumer("descent_a")
    gap_consumer.apply_bootstrap(initial)
    assert gap_consumer.apply_frame(second) == []
    assert gap_consumer.missing_ranges == [{"from": 1, "to": 1}]


def test_reconnect_snapshot_restores_cursor_and_terminal_state():
    crawl = crawl_fixture()
    scheduler = LivePresentationScheduler("descent_a", presentation_seed="stable", focus_actor_ids=["descender_a"])
    initial = bootstrap(scheduler, crawl)
    frame = scheduler.schedule(
        [event(1, event_type="CRAWLER_DIED", actors=("descender_a",))], authoritative_tick=4
    )
    consumer = LivePresentationConsumer("descent_a")
    consumer.apply_bootstrap(initial)
    consumer.apply_frame(frame)
    snapshot = scheduler.reconnect_snapshot(crawl, environment_digest=initial["digest"])
    resumed = LivePresentationConsumer("descent_a")
    resumed.apply_resume_snapshot(snapshot)
    assert resumed.latest_frame_sequence == 1
    assert resumed.terminal_actor_ids == {"descender_a"}
    assert resumed.reconnect_count == 1


def test_bad_digest_and_terminal_violation_fail_loudly():
    crawl = crawl_fixture()
    scheduler = LivePresentationScheduler("descent_a", presentation_seed="stable", focus_actor_ids=["descender_a"])
    initial = bootstrap(scheduler, crawl)
    consumer = LivePresentationConsumer("descent_a")
    broken = deepcopy(initial)
    broken["simulation_tick"] = 999
    try:
        consumer.apply_bootstrap(broken)
    except ValueError as exc:
        assert "digest" in str(exc)
    else:
        raise AssertionError("corrupt bootstrap should fail")


def test_feed_live_status_is_read_only_and_uses_underreach_vocabulary():
    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    crawl = crawl_fixture(persistence=persistence)
    fingerprint = crawl.fingerprint()
    payload = {
        "descent_id": crawl.id,
        "simulation_tick": crawl.current_tick,
        "latest_ledger_tick": crawl.current_tick,
        "presentation_tick": 3,
        "connected_presenter": True,
        "bridge_protocol": LIVE_PROTOCOL,
        "status": "streaming",
        "authoritative": False,
    }
    client = TestClient(create_feed_app(SpectatorRepository(persistence, crawl.id), lambda: payload))
    result = client.get("/api/feed/live/status")
    assert result.status_code == 200
    assert result.json() == payload
    assert not any(token in result.text for token in ('"crawl_id"', '"crawler_id"', '"floor_number"'))
    assert crawl.fingerprint() == fingerprint


def test_feed_offline_status_is_a_stable_non_authoritative_projection():
    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    crawl = crawl_fixture(persistence=persistence)
    client = TestClient(create_feed_app(SpectatorRepository(persistence, crawl.id)))
    status = client.get("/api/feed/live/status").json()
    assert status["descent_id"] == crawl.id
    assert status["status"] == "offline"
    assert status["authoritative"] is False
