from copy import deepcopy

from fastapi.testclient import TestClient
import pytest

from livingworld.crawl_domain import CrawlEvent
from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.feed_api import create_feed_app
from livingworld.live_camera_director import LiveCameraConfig, LiveCameraDirector
from livingworld.live_presentation_bridge import LivePresentationScheduler
from livingworld.spectator_api import SpectatorRepository


def environment(*, obstacle=None, valid=None):
    obstacles = [] if obstacle is None else [{"id": "block", "bounds": obstacle}]
    return {
        "room_bounds": {"min": {"x": -1300, "y": -1800, "z": 0}, "max": {"x": 1300, "y": 1800, "z": 700}},
        "valid_camera_region": valid or {"min": {"x": -1240, "y": -1740, "z": 80}, "max": {"x": 1240, "y": 1740, "z": 620}},
        "camera_forbidden_volumes": obstacles,
    }


def event(index, event_type="CRAWLER_MOVED", actors=("descender_a",), tick=None):
    return CrawlEvent(
        id=f"event_{index:03d}", crawl_id="descent_a", floor_number=1,
        tick=index if tick is None else tick, event_type=event_type,
        summary="camera truth", actor_ids=list(actors), location_id="sector_a", data={},
    )


def states(*, enemy_terminal=False, descender_terminal=False):
    return {
        "descender_a": {
            "actor_id": "descender_a", "actor_kind": "descender", "terminal": descender_terminal,
            "transform": {"x": -64.526, "y": 0.0, "z": 94.0, "yaw": -90.0},
        },
        "enemy_a": {
            "actor_id": "enemy_a", "actor_kind": "enemy", "terminal": enemy_terminal,
            "transform": {"x": 60.0, "y": 0.0, "z": 94.0, "yaw": 90.0},
        },
    }


def director(config=None, env=None):
    return LiveCameraDirector(
        "descent_a", presentation_seed="camera-seed", environment=env or environment(),
        config=config or LiveCameraConfig(),
    )


def direct(d, sequence, current, commands=(), *, start=0.0, end=0.5, future=(), actor_states=None, authoritative_tick=None):
    return d.direct(
        frame_sequence=sequence, current_events=current, lookahead_events=future,
        commands=list(commands), actor_states=actor_states or states(), from_seconds=start,
        to_seconds=end, authoritative_tick=authoritative_tick if authoritative_tick is not None else max(e.tick for e in current),
    )


def attack_command(seconds=0.5):
    return {
        "type": "play_attack", "actor_id": "descender_a", "target_actor_id": "enemy_a",
        "presentation_seconds": seconds, "source_event_id": "event_002",
    }


def terminal_command(actor="enemy_a", seconds=2.5, source="event_003"):
    return {
        "type": "play_terminal", "actor_id": actor, "presentation_seconds": seconds,
        "source_event_id": source,
    }


def locomotion_command(seconds=6.0):
    return {
        "type": "play_locomotion", "actor_id": "descender_a", "presentation_seconds": seconds,
        "source_event_id": "event_004",
    }


def test_same_input_and_configuration_produce_same_digest_shots_and_ids():
    results = []
    for _ in range(2):
        d = director()
        direct(d, 1, [event(1)], start=0, end=.45)
        direct(d, 2, [event(2, "COMBAT_HIT", ("descender_a", "enemy_a"))], [attack_command()], start=.45, end=2.5)
        results.append(d.diagnostics(6.0))
    assert results[0]["command_digest"] == results[1]["command_digest"]
    assert [s["shot_id"] for s in results[0]["shots"]] == [s["shot_id"] for s in results[1]["shots"]]


def test_camera_rejects_events_beyond_configured_lookahead():
    d = director(LiveCameraConfig(camera_lookahead_ticks=2))
    with pytest.raises(ValueError, match="lookahead"):
        direct(d, 1, [event(1)], future=[event(4)], authoritative_tick=4)


def test_camera_accepts_only_events_inside_configured_lookahead():
    d = director(LiveCameraConfig(camera_lookahead_ticks=2))
    assert direct(d, 1, [event(1)], future=[event(3)], authoritative_tick=3)


def test_minimum_shot_duration_retains_establishing_over_early_attack():
    d = director(LiveCameraConfig(minimum_shot_seconds=.6, cut_cooldown_seconds=.1))
    direct(d, 1, [event(1)], start=0, end=.1)
    assert direct(d, 2, [event(2)], [attack_command(.2)], start=.1, end=.3) == []
    assert d.active_shot["mode"] == "establishing"


def test_maximum_shot_duration_forces_a_new_valid_shot():
    d = director(LiveCameraConfig(maximum_shot_seconds=1.0, minimum_shot_seconds=.2))
    direct(d, 1, [event(1)], start=0, end=.2)
    result = direct(d, 2, [event(2)], start=1.0, end=1.2)
    assert result and len(d.shots) == 2


def test_cut_cooldown_blocks_rapid_second_cut():
    d = director(LiveCameraConfig(minimum_shot_seconds=.1, cut_cooldown_seconds=.5))
    direct(d, 1, [event(1)], start=0, end=.1)
    assert not direct(d, 2, [event(2)], [attack_command(.3)], start=.1, end=.35)


def test_duplicate_or_old_frame_cannot_duplicate_or_rewind_a_cut():
    d = director()
    first = direct(d, 1, [event(1)])
    assert first
    assert direct(d, 1, [event(1)]) == []
    assert d.duplicate_frame_count == 1
    assert d.latest_frame_sequence == 1


def test_valid_current_shot_is_retained_over_low_value_follow_cut():
    d = director()
    direct(d, 1, [event(1)], start=0, end=.45)
    assert not direct(d, 2, [event(2)], [locomotion_command(1.0)], start=.45, end=1.2)
    assert d.active_shot["mode"] == "establishing"


def test_combat_event_prefers_valid_combat_pair_with_accepted_occupancy():
    d = director()
    direct(d, 1, [event(1)], start=0, end=.45)
    direct(d, 2, [event(2, "COMBAT_HIT", ("descender_a", "enemy_a"))], [attack_command()], start=.45, end=2.2)
    shot = d.shots[-1]
    assert shot["mode"] == "combat_pair"
    assert shot["occupancy_width"] >= .35 and shot["occupancy_height"] >= .64


def test_combat_cue_uses_upright_envelope_when_later_death_shares_frame():
    d = director()
    direct(d, 1, [event(1)], start=0, end=.45)
    direct(
        d, 2, [event(2, "COMBAT_HIT", ("descender_a", "enemy_a")), event(3, "ENEMY_DEFEATED", ("descender_a", "enemy_a"), tick=2)],
        [attack_command(.45), terminal_command(seconds=2.5)], start=.45, end=3.0,
        actor_states=states(enemy_terminal=True),
    )
    assert [shot["mode"] for shot in d.shots[-2:]] == ["combat_pair", "death_hold"]


def test_terminal_event_triggers_and_locks_death_hold():
    d = director()
    direct(d, 1, [event(1)], start=0, end=.45)
    direct(d, 2, [event(2, "ENEMY_DEFEATED", ("descender_a", "enemy_a"))], [terminal_command()], start=.45, end=3.0, actor_states=states(enemy_terminal=True))
    assert d.active_shot["mode"] == "death_hold"
    assert d.locked_terminal_until == 5.0


def test_camera_releases_death_hold_to_later_activity():
    d = director()
    direct(d, 1, [event(1)], start=0, end=.45)
    direct(d, 2, [event(2)], [terminal_command()], start=.45, end=3.0, actor_states=states(enemy_terminal=True))
    direct(d, 3, [event(3)], [locomotion_command(5.2)], start=5.1, end=5.4, actor_states=states(enemy_terminal=True))
    assert d.active_shot["mode"] == "follow"


def test_second_terminal_event_can_receive_focus_after_first_hold():
    d = director()
    direct(d, 1, [event(1)], start=0, end=.45)
    direct(d, 2, [event(2)], [terminal_command()], start=.45, end=3.0, actor_states=states(enemy_terminal=True))
    direct(d, 3, [event(3)], [locomotion_command(5.2)], start=5.1, end=5.4, actor_states=states(enemy_terminal=True))
    direct(d, 4, [event(4)], [terminal_command("descender_a", 8.0, "event_004")], start=7.9, end=8.5, actor_states=states(enemy_terminal=True, descender_terminal=True))
    assert d.active_shot["mode"] == "death_hold"
    assert d.active_shot["target_actor_ids"] == ["descender_a"]


def test_geometry_invalid_candidate_is_rejected():
    d = director(env=environment(valid={"min": {"x": -20, "y": -20, "z": 80}, "max": {"x": 20, "y": 20, "z": 200}}))
    candidate = d._candidate("follow", ["descender_a"], states(), [], 10)
    assert not candidate["geometry_valid"]
    d._choose([candidate, d._candidate("fallback_static", ["descender_a"], states(), [], 1)])
    assert d.rejections["geometry"] >= 1


def test_los_blocked_candidate_is_rejected():
    block = {"min": {"x": -100, "y": -600, "z": 0}, "max": {"x": 100, "y": -300, "z": 500}}
    d = director(env=environment(obstacle=block))
    candidate = d._candidate("combat_pair", ["descender_a", "enemy_a"], states(), [], 10)
    assert not candidate["los_valid"]


def test_occupancy_invalid_combat_candidate_is_rejected():
    d = director()
    target = {"x": 0.0, "y": 0.0, "z": 125.0}
    result = d._validate("combat_pair", {"x": 0.0, "y": -1700.0, "z": 300.0}, target, d._targets(["descender_a", "enemy_a"], states()))
    assert not result["occupancy_valid"]


def test_deterministic_static_fallback_exists_if_candidates_fail():
    d = director(env=environment(valid={"min": {"x": -1, "y": -1, "z": 80}, "max": {"x": 1, "y": 1, "z": 100}}))
    candidates = [
        d._candidate("follow", ["descender_a"], states(), [], 10),
        d._candidate("fallback_static", ["descender_a"], states(), [], 1),
    ]
    assert d._choose(candidates)["mode"] == "fallback_static"
    assert d.fallback_count == 1


def test_population_edge_pair_gets_a_valid_deterministic_static_fit():
    actor_states = states()
    actor_states["descender_a"]["transform"].update({"x": -50.0, "y": -500.0})
    actor_states["enemy_a"]["transform"].update({"x": 90.0, "y": 136.0})
    first_director = director()
    targets = first_director._targets(["descender_a", "enemy_a"], actor_states)
    original_camera, original_target = first_director._placement("fallback_static", targets)
    assert not first_director._validate("fallback_static", original_camera, original_target, targets)["occupancy_valid"]
    first = first_director._candidate("fallback_static", ["descender_a", "enemy_a"], actor_states, [], 1)
    second = director()._candidate("fallback_static", ["descender_a", "enemy_a"], actor_states, [], 1)
    assert first == second
    assert first["geometry_valid"]
    assert first["los_valid"]
    assert first["occupancy_valid"]
    assert first["camera_position"] != original_camera


def test_reconnect_snapshot_restores_active_camera_without_replaying_cuts():
    original = director()
    direct(original, 1, [event(1)])
    snapshot = original.snapshot()
    resumed = director()
    resumed.restore(snapshot)
    assert resumed.active_shot == original.active_shot
    assert resumed.latest_frame_sequence == 1
    assert resumed.reconnect_restore_count == 1


def test_terminal_actor_state_remains_terminal_after_camera_leaves():
    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    crawl = service.create_seeded_crawl(seed="camera-terminal", crawler_ids=["descender_a"], floor_count=2, crawl_id="descent_a")
    service.start(crawl)
    scheduler = LivePresentationScheduler("descent_a", presentation_seed="stable", focus_actor_ids=["descender_a"])
    scheduler.bootstrap(crawl, environment=environment())
    scheduler.schedule([event(1, "CRAWLER_DIED")], authoritative_tick=4)
    scheduler.schedule([event(2)], authoritative_tick=5)
    assert scheduler.actors["descender_a"].terminal
    assert scheduler.camera_director is not None


def test_feed_live_camera_projection_is_read_only_and_underreach_named():
    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    crawl = service.create_seeded_crawl(seed="feed-camera", crawler_ids=["descender_a"], floor_count=2, crawl_id="descent_a")
    service.start(crawl)
    before = crawl.fingerprint()
    payload = {
        "descent_id": crawl.id, "presentation_tick": 4, "shot_id": "shot_1",
        "camera_mode": "combat_pair", "target_descender_ids": ["descender_a"],
        "director_digest": "abc",
    }
    client = TestClient(create_feed_app(SpectatorRepository(persistence, crawl.id), live_camera_provider=lambda: payload))
    response = client.get("/api/feed/live/camera")
    assert response.status_code == 200 and response.json()["authoritative"] is False
    assert crawl.fingerprint() == before
    assert "crawl_id" not in response.text and "crawler_id" not in response.text


def test_feed_live_camera_offline_fallback_is_stable():
    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    crawl = service.create_seeded_crawl(seed="feed-offline", crawler_ids=["descender_a"], floor_count=2, crawl_id="descent_a")
    service.start(crawl)
    response = TestClient(create_feed_app(SpectatorRepository(persistence, crawl.id))).get("/api/feed/live/camera").json()
    assert response["status"] == "offline"
    assert response["camera_protocol"] == "underreach.live-camera.v1"
