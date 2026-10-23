from copy import deepcopy

from fastapi.testclient import TestClient
import pytest

from livingworld.crawl_domain import CrawlEvent, ParticipationStatus
from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.feed_api import create_feed_app
from livingworld.feed_channel_registry import (
    AutomaticFeedDirector,
    AutomaticFocusConfig,
    FeedChannelRegistry,
    descender_channel_id,
)
from livingworld.live_camera_director import LiveCameraConfig, LiveCameraDirector
from livingworld.live_presentation_bridge import LivePresentationConsumer, LivePresentationScheduler
from livingworld.spectator_api import SpectatorRepository


def descent_fixture(*, persistence=None):
    service = CrawlLifecycleService(persistence)
    descent = service.create_seeded_crawl(
        seed="underreach-multichannel-tests",
        crawler_ids=["descender_a", "descender_b", "descender_c"],
        floor_count=2,
        crawl_id="descent_a",
    )
    service.start(descent)
    return descent


def event(index, *, actor="descender_a", event_type="CRAWLER_MOVED", tick=None):
    return CrawlEvent(
        id=f"event_{index:03d}", crawl_id="descent_a", floor_number=1,
        tick=index if tick is None else tick, event_type=event_type,
        summary="authoritative Feed test event", actor_ids=[actor],
        location_id="sector_a", data={},
    )


def registry(descent, *, config=None):
    item = FeedChannelRegistry(
        descent.id,
        automatic_director=AutomaticFeedDirector(config),
        default_viewer_id="qa_viewer",
    )
    item.register(descent)
    return item


def update(item, descent, events=(), *, tick=1, seconds=1.0, available=("descender_a", "descender_b", "descender_c")):
    descent.current_tick = max(descent.current_tick, max((e.tick for e in events), default=descent.current_tick))
    return item.update(
        descent, events, presentation_tick=tick, presentation_seconds=seconds,
        buffered_tick=descent.current_tick, frame_id=f"frame_{tick}",
        camera_available_ids=available,
        camera_state={"active_shot": {"target_actor_ids": ["descender_a"]}},
    )


def request(item, descent, request_id, action, tick, descender_id=None):
    value = {
        "viewer_id": "qa_viewer", "action": action, "request_id": request_id,
        "requested_at_presentation_tick": tick,
    }
    if descender_id is not None:
        value["descender_id"] = descender_id
    return item.apply_request(descent, value)


def test_channel_directory_lists_all_descenders_with_deterministic_ids():
    descent = descent_fixture()
    item = registry(descent)
    update(item, descent)
    first = item.directory(descent, viewer_id="qa_viewer")
    second = item.directory(descent, viewer_id="qa_viewer")
    assert [row["channel_id"] for row in first] == [
        "feed:descender:descender_a", "feed:descender:descender_b", "feed:descender:descender_c"
    ]
    assert [row["presentation_digest"] for row in first] == [row["presentation_digest"] for row in second]


def test_multiple_channel_projections_share_truth_and_are_read_only():
    descent = descent_fixture()
    item = registry(descent)
    update(item, descent, [event(1), event(2, actor="descender_b")])
    before = descent.fingerprint()
    left, right = item.channel(descent, "descender_a"), item.channel(descent, "descender_b")
    assert left["descent_id"] == right["descent_id"] == descent.id
    assert left["focus_descender_id"] != right["focus_descender_id"]
    assert descent.fingerprint() == before


def test_channel_freshness_and_public_terminology_are_monotonic():
    descent = descent_fixture()
    item = registry(descent)
    update(item, descent, [event(3, actor="descender_b")], tick=3, seconds=2.0)
    row = item.channel(descent, "descender_b")
    assert row["latest_authoritative_tick"] == row["latest_buffered_tick"] == 3
    assert row["latest_presentation_tick"] == 3 and row["stale"] is False
    text = str(row)
    assert "crawl_id" not in text and "crawler_id" not in text and "floor_number" not in text


def test_manual_follow_and_a_to_b_switch_are_explicit():
    descent = descent_fixture()
    item = registry(descent)
    update(item, descent, tick=2, seconds=2.0)
    first = request(item, descent, "follow_a", "follow", 2, "descender_a")
    second = request(item, descent, "follow_b", "follow", 2, "descender_b")
    assert first["active_descender_id"] == "descender_a"
    assert second["active_descender_id"] == "descender_b"
    assert second["transition"]["reason"] == "manual_switch"
    assert item.active_focus("qa_viewer")["focus_mode"] == "manual"


def test_duplicate_follow_is_idempotent_and_does_not_reset_focus_timer():
    descent = descent_fixture()
    item = registry(descent)
    update(item, descent, tick=2, seconds=2.0)
    first = request(item, descent, "same_request", "follow", 2, "descender_a")
    started = item.viewers["qa_viewer"].focus_started_seconds
    duplicate = request(item, descent, "same_request", "follow", 2, "descender_a")
    assert duplicate["duplicate"] is True
    assert duplicate["transition"] == first["transition"]
    assert item.viewers["qa_viewer"].focus_started_seconds == started
    assert item.duplicate_requests_ignored == 1


def test_same_target_new_follow_is_safe_noop():
    descent = descent_fixture()
    item = registry(descent)
    update(item, descent, tick=2, seconds=2.0)
    request(item, descent, "follow_1", "follow", 2, "descender_a")
    result = request(item, descent, "follow_2", "follow", 2, "descender_a")
    assert result["status"] == "accepted" and result["transition"] is None


def test_release_returns_to_deterministic_automatic_mode():
    descent = descent_fixture()
    item = registry(descent)
    update(item, descent, [event(1, actor="descender_b", event_type="COMBAT_HIT")], tick=2, seconds=2.0)
    request(item, descent, "follow_a", "follow", 2, "descender_a")
    result = request(item, descent, "release_a", "release", 2)
    assert result["focus_mode"] == "automatic"
    assert result["active_descender_id"] == "descender_b"
    assert result["transition"]["reason"] == "manual_release"


@pytest.mark.parametrize("payload,reason", [
    ({"viewer_id": "qa_viewer", "action": "follow", "request_id": "unknown", "requested_at_presentation_tick": 1, "descender_id": "missing"}, "unknown_descender"),
    ({"viewer_id": "bad viewer", "action": "follow", "request_id": "bad_viewer", "requested_at_presentation_tick": 1, "descender_id": "descender_a"}, "invalid_viewer_id"),
    ({"viewer_id": "qa_viewer", "action": "dance", "request_id": "bad_action", "requested_at_presentation_tick": 1}, "unsupported_action"),
])
def test_invalid_requests_rejected_explicitly(payload, reason):
    descent = descent_fixture()
    item = registry(descent)
    update(item, descent)
    result = item.apply_request(descent, payload)
    assert result["status"] == "rejected" and result["reason"] == reason


def test_stale_request_cannot_rewind_manual_follow():
    descent = descent_fixture()
    item = registry(descent)
    update(item, descent, tick=5, seconds=5.0)
    request(item, descent, "current", "follow", 5, "descender_b")
    stale = request(item, descent, "old", "follow", 4, "descender_a")
    assert stale["reason"] == "stale_request"
    assert item.active_focus("qa_viewer")["active_descender_id"] == "descender_b"


def test_automatic_focus_is_deterministic_and_bounded_to_recent_truth():
    descent = descent_fixture()
    results = []
    for _ in range(2):
        item = registry(descent)
        old = event(1, actor="descender_a", event_type="COMBAT_HIT", tick=1)
        recent = event(20, actor="descender_c", event_type="COMBAT_HIT", tick=20)
        update(item, descent, [old, recent], tick=1, seconds=1.0)
        results.append(item.active_focus("qa_viewer")["active_descender_id"])
        assert item.automatic_director.decide(
            descent, [old, recent], presentation_seconds=1.0, current_descender_id=None,
            current_focus_started_seconds=0, last_switch_seconds=0,
            terminal_seen_seconds={}, force=True,
        ).evaluated_event_count == 1
    assert results == ["descender_c", "descender_c"]


def test_hysteresis_prevents_thrashing_but_clear_improvement_switches():
    descent = descent_fixture()
    descent.current_tick = 10
    config = AutomaticFocusConfig(minimum_focus_seconds=2.0, switch_cooldown_seconds=1.0, switch_threshold=.2)
    director = AutomaticFeedDirector(config)
    close = [event(10, actor="descender_b", event_type="CRAWLER_MOVED", tick=10)]
    held = director.decide(
        descent, close, presentation_seconds=1.0, current_descender_id="descender_a",
        current_focus_started_seconds=0.0, last_switch_seconds=0.0,
        terminal_seen_seconds={}, force=False,
    )
    assert held.descender_id == "descender_a" and not held.switched
    strong = [event(11, actor="descender_b", event_type="COMBAT_HIT", tick=10)]
    switched = director.decide(
        descent, strong, presentation_seconds=4.0, current_descender_id="descender_a",
        current_focus_started_seconds=0.0, last_switch_seconds=0.0,
        terminal_seen_seconds={}, force=False,
    )
    assert switched.descender_id == "descender_b" and switched.switched


def test_manual_focus_cannot_be_stolen_by_automatic_updates():
    descent = descent_fixture()
    item = registry(descent)
    update(item, descent, tick=1, seconds=1.0)
    request(item, descent, "follow_a", "follow", 1, "descender_a")
    update(item, descent, [event(8, actor="descender_c", event_type="COMBAT_HIT")], tick=8, seconds=8.0)
    assert item.active_focus("qa_viewer")["active_descender_id"] == "descender_a"
    assert item.active_focus("qa_viewer")["focus_mode"] == "manual"


def test_manual_terminal_focus_stays_until_release():
    descent = descent_fixture()
    item = registry(descent)
    update(item, descent, tick=1, seconds=1.0)
    request(item, descent, "follow_a", "follow", 1, "descender_a")
    descent.participants["descender_a"].status = ParticipationStatus.DEAD
    descent.participants["descender_a"].health = 0.0
    descent.surviving_crawler_count -= 1
    descent.eliminated_crawler_count += 1
    update(item, descent, [event(2, actor="descender_a", event_type="CRAWLER_DIED")], tick=2, seconds=2.0)
    update(item, descent, [event(8, actor="descender_b", event_type="COMBAT_HIT")], tick=8, seconds=8.0)
    assert item.active_focus("qa_viewer")["active_descender_id"] == "descender_a"


def test_automatic_terminal_hold_then_releases_to_living_activity():
    descent = descent_fixture()
    item = registry(descent, config=AutomaticFocusConfig(terminal_hold_seconds=2.5, minimum_focus_seconds=0, switch_cooldown_seconds=0))
    update(item, descent, [event(1, actor="descender_a", event_type="COMBAT_HIT")], tick=1, seconds=1.0)
    assert item.active_focus("qa_viewer")["active_descender_id"] == "descender_a"
    descent.participants["descender_a"].status = ParticipationStatus.DEAD
    descent.participants["descender_a"].health = 0.0
    descent.surviving_crawler_count -= 1
    descent.eliminated_crawler_count += 1
    update(item, descent, [event(2, actor="descender_a", event_type="CRAWLER_DIED")], tick=2, seconds=2.0)
    assert item.active_focus("qa_viewer")["active_descender_id"] == "descender_a"
    transitions = update(item, descent, [event(8, actor="descender_b", event_type="COMBAT_HIT")], tick=8, seconds=5.0)
    assert item.active_focus("qa_viewer")["active_descender_id"] == "descender_b"
    assert transitions[-1].reason == "auto_terminal_release"


def test_reconnect_restores_manual_and_automatic_focus_without_cursor_rewind():
    descent = descent_fixture()
    original = registry(descent)
    update(original, descent, tick=4, seconds=4.0)
    request(original, descent, "follow_b", "follow", 4, "descender_b")
    snapshot = original.reconnect_snapshot()
    restored = registry(descent)
    restored.restore(snapshot)
    assert restored.active_focus("qa_viewer") == original.active_focus("qa_viewer")
    assert restored.active_focus("qa_viewer")["active_descender_id"] == "descender_b"
    assert restored.active_focus("qa_viewer")["focus_mode"] == "manual"
    assert restored.latest_presentation_tick == 4 and restored.reconnect_restores == 1


def test_scheduler_focus_change_preserves_cursor_bootstrap_and_actor_set():
    descent = descent_fixture()
    scheduler = LivePresentationScheduler(
        descent.id, presentation_seed="stable", focus_actor_ids=["descender_a", "descender_b"],
    )
    scheduler.bootstrap(descent, environment={"environment_id": "stone", "build_once": True})
    first = scheduler.schedule([event(1)], authoritative_tick=1)
    cursor = scheduler.latest_processed_key
    actors = set(scheduler.actors)
    scheduler.queue_focus_transition({
        "transition_id": "focus_manual_b", "viewer_id": "qa_viewer", "presentation_tick": 1,
        "presentation_seconds": scheduler.presentation_seconds, "from_channel": descender_channel_id("descender_a"),
        "to_channel": descender_channel_id("descender_b"), "from_descender_id": "descender_a",
        "to_descender_id": "descender_b", "mode": "manual", "reason": "manual_switch", "request_id": "follow_b",
    })
    second = scheduler.schedule([], authoritative_tick=1)
    assert second["frame_sequence"] == first["frame_sequence"] + 1
    assert scheduler.latest_processed_key == cursor and set(scheduler.actors) == actors
    assert scheduler.bootstrap_count == 1
    assert sum(command["type"] == "focus_change" for command in second["commands"]) == 1
    assert sum(command["type"] == "camera_cut" for command in second["commands"]) <= 1


def test_scheduler_advances_post_roll_while_camera_focus_retry_is_pending():
    descent = descent_fixture()
    scheduler = LivePresentationScheduler(
        descent.id, presentation_seed="stable", focus_actor_ids=["descender_a", "descender_b"],
    )
    scheduler.bootstrap(descent, environment={"environment_id": "stone", "build_once": True})
    scheduler.camera_director.pending_focus_transition = {
        "transition_id": "pending_auto_release", "to_descender_id": "descender_b",
        "mode": "automatic", "reason": "auto_terminal_release", "presentation_seconds": 0.0,
    }
    frame = scheduler.schedule([], authoritative_tick=0)
    assert frame is not None and frame["source"]["ledger_event_ids"] == []
    assert any(command.get("focus_transition_id") == "pending_auto_release" for command in frame["commands"])


def test_duplicate_bridge_delivery_after_focus_switch_is_idempotent():
    descent = descent_fixture()
    scheduler = LivePresentationScheduler(descent.id, presentation_seed="stable", focus_actor_ids=["descender_a", "descender_b"])
    bootstrap = scheduler.bootstrap(descent, environment={"environment_id": "stone", "build_once": True})
    scheduler.queue_focus_transition({
        "transition_id": "focus_b", "to_descender_id": "descender_b", "mode": "manual", "reason": "manual_follow",
    })
    frame = scheduler.schedule([event(1)], authoritative_tick=1)
    consumer = LivePresentationConsumer(descent.id)
    consumer.apply_bootstrap(bootstrap)
    first = consumer.apply_frame(frame)
    assert first and consumer.apply_frame(frame) == [] and consumer.duplicate_frames == 1


def test_feed_api_directory_focus_follow_release_and_errors_are_session_only():
    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    descent = descent_fixture(persistence=persistence)
    item = registry(descent)
    update(item, descent, tick=1, seconds=1.0)
    before = descent.fingerprint()
    client = TestClient(create_feed_app(SpectatorRepository(persistence, descent.id), feed_channel_registry=item))
    assert len(client.get("/api/feed/channels?viewer_id=qa_viewer").json()) == 3
    assert client.get("/api/feed/channels/feed:descender:descender_a?viewer_id=qa_viewer").status_code == 200
    follow = client.post("/api/feed/live/follow", json={
        "viewer_id": "qa_viewer", "request_id": "api_follow", "requested_at_presentation_tick": 1,
        "descender_id": "descender_b",
    })
    assert follow.status_code == 200 and follow.json()["active_descender_id"] == "descender_b"
    assert client.get("/api/feed/live/focus?viewer_id=qa_viewer").json()["focus_mode"] == "manual"
    release = client.post("/api/feed/live/release", json={
        "viewer_id": "qa_viewer", "request_id": "api_release", "requested_at_presentation_tick": 1,
    })
    assert release.status_code == 200 and release.json()["focus_mode"] == "automatic"
    invalid = client.post("/api/feed/live/follow", json={
        "viewer_id": "qa_viewer", "request_id": "api_invalid", "requested_at_presentation_tick": 1,
        "descender_id": "unknown",
    })
    assert invalid.status_code == 404
    assert descent.fingerprint() == before


def test_channel_and_focus_digests_are_deterministic():
    descent = descent_fixture()
    outputs = []
    for _ in range(2):
        item = registry(deepcopy(descent))
        copy_descent = deepcopy(descent)
        update(item, copy_descent, [event(1), event(2, actor="descender_b", event_type="COMBAT_HIT")], tick=2, seconds=2.0)
        request(item, copy_descent, "follow_a", "follow", 2, "descender_a")
        request(item, copy_descent, "follow_b", "follow", 2, "descender_b")
        debug = item.diagnostics()
        outputs.append((debug["channel_digest"], debug["focus_sequence_digest"]))
    assert outputs[0] == outputs[1]


def test_camera_focus_transition_targets_active_channel_and_duplicate_frame_stays_safe():
    environment = {
        "room_bounds": {"min": {"x": -1300, "y": -1800, "z": 0}, "max": {"x": 1300, "y": 1800, "z": 700}},
        "valid_camera_region": {"min": {"x": -1240, "y": -1740, "z": 80}, "max": {"x": 1240, "y": 1740, "z": 620}},
        "camera_forbidden_volumes": [],
    }
    states = {
        "descender_a": {"actor_id": "descender_a", "actor_kind": "descender", "terminal": False, "transform": {"x": -200, "y": 0, "z": 94, "yaw": 0}},
        "descender_b": {"actor_id": "descender_b", "actor_kind": "descender", "terminal": False, "transform": {"x": 200, "y": 0, "z": 94, "yaw": 180}},
    }
    director = LiveCameraDirector("descent_a", presentation_seed="stable", environment=environment, config=LiveCameraConfig(minimum_shot_seconds=.1, cut_cooldown_seconds=.1))
    transition = {
        "transition_id": "focus_b", "to_descender_id": "descender_b", "mode": "manual",
        "reason": "manual_switch", "presentation_seconds": 0.0,
    }
    commands = director.direct(
        frame_sequence=1, current_events=[event(1)], lookahead_events=[], commands=[], actor_states=states,
        from_seconds=0, to_seconds=.5, authoritative_tick=1, focus_transition=transition,
    )
    assert commands[-1]["target_actor_ids"] == ["descender_b"]
    assert commands[-1]["focus_transition_id"] == "focus_b"
    assert director.direct(
        frame_sequence=1, current_events=[event(1)], lookahead_events=[], commands=[], actor_states=states,
        from_seconds=0, to_seconds=.5, authoritative_tick=1, focus_transition=transition,
    ) == []


def test_explicit_focus_switch_is_not_treated_as_low_value_locomotion_follow():
    environment = {
        "room_bounds": {"min": {"x": -1300, "y": -1800, "z": 0}, "max": {"x": 1300, "y": 1800, "z": 700}},
        "valid_camera_region": {"min": {"x": -1240, "y": -1740, "z": 80}, "max": {"x": 1240, "y": 1740, "z": 620}},
        "camera_forbidden_volumes": [],
    }
    actor_states = {
        "descender_a": {"actor_id": "descender_a", "actor_kind": "descender", "terminal": False, "transform": {"x": -200, "y": 0, "z": 94, "yaw": 0}},
        "descender_b": {"actor_id": "descender_b", "actor_kind": "descender", "terminal": False, "transform": {"x": 200, "y": 0, "z": 94, "yaw": 180}},
    }
    director = LiveCameraDirector("descent_a", presentation_seed="stable", environment=environment)
    director.direct(
        frame_sequence=1, current_events=[event(1)], lookahead_events=[], commands=[], actor_states=actor_states,
        from_seconds=0, to_seconds=.5, authoritative_tick=1,
        focus_transition={"transition_id": "focus_a", "to_descender_id": "descender_a", "mode": "automatic", "reason": "initial_auto_focus", "presentation_seconds": 0},
    )
    commands = director.direct(
        frame_sequence=2, current_events=[event(2)], lookahead_events=[], commands=[], actor_states=actor_states,
        from_seconds=1.0, to_seconds=1.5, authoritative_tick=2,
        focus_transition={"transition_id": "focus_b", "to_descender_id": "descender_b", "mode": "manual", "reason": "manual_switch", "presentation_seconds": 1.0},
    )
    assert commands and commands[-1]["target_actor_ids"] == ["descender_b"]
    assert commands[-1]["focus_reason"] == "manual_switch"


def test_focus_transition_blocked_by_death_hold_is_applied_after_hold():
    environment = {
        "room_bounds": {"min": {"x": -1300, "y": -1800, "z": 0}, "max": {"x": 1300, "y": 1800, "z": 700}},
        "valid_camera_region": {"min": {"x": -1240, "y": -1740, "z": 80}, "max": {"x": 1240, "y": 1740, "z": 620}},
        "camera_forbidden_volumes": [],
    }
    actor_states = {
        "descender_a": {"actor_id": "descender_a", "actor_kind": "descender", "terminal": True, "transform": {"x": -64, "y": 0, "z": 48, "yaw": 0}},
        "descender_b": {"actor_id": "descender_b", "actor_kind": "descender", "terminal": False, "transform": {"x": 60, "y": 0, "z": 94, "yaw": 180}},
    }
    director = LiveCameraDirector("descent_a", presentation_seed="stable", environment=environment)
    director.direct(
        frame_sequence=1, current_events=[event(1)], lookahead_events=[],
        commands=[{"type": "play_terminal", "actor_id": "descender_a", "presentation_seconds": 1.0, "source_event_id": "event_001"}],
        actor_states={"descender_a": actor_states["descender_a"]}, from_seconds=0, to_seconds=1.2, authoritative_tick=1,
    )
    transition = {"transition_id": "terminal_release", "to_descender_id": "descender_b", "mode": "automatic", "reason": "auto_terminal_release", "presentation_seconds": 2.0}
    assert director.direct(
        frame_sequence=2, current_events=[event(2)], lookahead_events=[], commands=[], actor_states=actor_states,
        from_seconds=2.0, to_seconds=2.4, authoritative_tick=2, focus_transition=transition,
    ) == []
    assert director.pending_focus_transition["transition_id"] == "terminal_release"
    commands = director.direct(
        frame_sequence=3, current_events=[event(3)], lookahead_events=[], commands=[], actor_states=actor_states,
        from_seconds=3.6, to_seconds=4.0, authoritative_tick=3,
    )
    assert commands[-1]["target_actor_ids"] == ["descender_b"]
    assert commands[-1]["focus_reason"] == "auto_terminal_release"
    assert director.pending_focus_transition is None
