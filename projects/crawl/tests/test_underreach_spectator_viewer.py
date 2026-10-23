import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from time import time

from fastapi.testclient import TestClient

from livingworld.crawl_domain import CrawlEvent, ParticipationStatus
from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.feed_api import create_feed_app
from livingworld.feed_channel_registry import FeedChannelRegistry
from livingworld.spectator_api import SpectatorRepository
from livingworld.spectator_viewer import VIEWER_PROTOCOL, ViewerStateProjector, build_viewer_state


VIEWER_ID = "viewer_local_alpha"


def runtime(*, empty=False):
    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    descent = service.create_seeded_crawl(
        seed="underreach-viewer-tests",
        crawler_ids=["descender_a", "descender_b", "descender_c"],
        floor_count=2,
        crawl_id="descent_viewer",
    )
    service.start(descent)
    if empty:
        descent.participants = {}
        descent.starting_crawler_count = 0
        descent.surviving_crawler_count = 0
        descent.eliminated_crawler_count = 0
    registry = FeedChannelRegistry(descent.id, default_viewer_id=VIEWER_ID)
    registry.register(descent)
    registry.update(
        descent,
        [],
        presentation_tick=4,
        presentation_seconds=2.5,
        buffered_tick=descent.current_tick,
        frame_id="frame_viewer_004",
        camera_available_ids=("descender_a", "descender_b"),
        camera_state={"active_shot": {"shot_id": "shot_a", "mode": "follow", "target_actor_ids": ["descender_a"]}},
    )
    persistence.save_crawl(descent)
    repository = SpectatorRepository(persistence, descent.id)
    live = lambda: {
        "status": "live",
        "connected_presenter": True,
        "updated_at_unix_ms": int(time() * 1000),
        "presentation_tick": registry.latest_presentation_tick,
    }
    camera = lambda: registry.camera_state or {}
    return persistence, descent, registry, repository, live, camera


def viewer_state(*, empty=False):
    persistence, descent, registry, repository, live, camera = runtime(empty=empty)
    return build_viewer_state(
        descent,
        repository.events(limit=1000),
        registry,
        viewer_id=VIEWER_ID,
        live_status=live(),
        live_camera=camera(),
        generated_at_unix_ms=int(time() * 1000),
    )


def post(client, path, request_id, tick, descender_id=None):
    payload = {"viewer_id": VIEWER_ID, "request_id": request_id, "requested_at_presentation_tick": tick}
    if descender_id is not None:
        payload["descender_id"] = descender_id
    return client.post(path, json=payload)


def test_viewer_aggregate_is_read_only():
    _, descent, registry, repository, live, camera = runtime()
    before = descent.fingerprint()
    result = ViewerStateProjector(repository, registry, live, camera).state(VIEWER_ID)
    assert result["protocol"] == VIEWER_PROTOCOL
    assert descent.fingerprint() == before


def test_viewer_uses_underreach_public_terminology_only():
    text = json.dumps(viewer_state()).lower()
    for legacy in ('"crawl_id"', '"crawler_id"', '"floor_number"', '"crawl"', '"crawler"'):
        assert legacy not in text
    assert "descent" in text and "descender" in text and "stratum" in text and "sector" in text


def test_current_focus_matches_registry():
    _, _, registry, _, _, _ = runtime()
    state = viewer_state()
    assert state["focus"]["active_descender_id"] == registry.active_focus(VIEWER_ID)["active_descender_id"]


def test_current_camera_projects_active_focus():
    state = viewer_state()
    assert state["camera"]["mode"] == "follow"
    assert state["camera"]["focus_descender_id"] == state["focus"]["active_descender_id"]
    assert state["camera"]["focus_confirmed"] is True


def test_recent_ledger_uses_public_projection_and_readable_label():
    persistence, descent, registry, repository, live, camera = runtime()
    event = CrawlEvent(id="event_a", crawl_id=descent.id, floor_number=1, tick=2, event_type="CRAWLER_MOVED", summary="crawler moved floor", actor_ids=["descender_a"], location_id="sector_a")
    persistence.append_event(event)
    result = ViewerStateProjector(repository, registry, live, camera).state(VIEWER_ID)
    assert result["ledger"][0]["event_type"] == "DESCENDER_MOVED"
    assert "Descender" in result["ledger"][0]["label"]
    assert "crawler" not in result["ledger"][0]["label"].lower()


def test_terminal_descender_remains_visible_as_fallen():
    persistence, descent, registry, repository, live, camera = runtime()
    descent.participants["descender_b"].status = ParticipationStatus.DEAD
    descent.participants["descender_b"].health = 0.0
    descent.surviving_crawler_count -= 1
    descent.eliminated_crawler_count += 1
    persistence.save_crawl(descent)
    result = ViewerStateProjector(repository, registry, live, camera).state(VIEWER_ID)
    fallen = next(item for item in result["descenders"] if item["descender_id"] == "descender_b")
    assert fallen["terminal"] is True and fallen["status"] == "fallen"
    assert result["summary"]["fallen_descender_count"] == 1


def test_viewer_endpoint_does_not_mutate_simulation_fingerprint():
    _, descent, registry, repository, live, camera = runtime()
    before = descent.fingerprint()
    client = TestClient(create_feed_app(repository, live, camera, registry))
    assert client.get(f"/api/feed/viewer/state?viewer_id={VIEWER_ID}").status_code == 200
    assert descent.fingerprint() == before


def test_viewer_freshness_cursor_is_monotonic():
    _, descent, registry, repository, live, camera = runtime()
    projector = ViewerStateProjector(repository, registry, live, camera)
    first = projector.state(VIEWER_ID)
    registry.latest_authoritative_tick += 1
    registry.latest_buffered_tick += 1
    registry.latest_presentation_tick += 1
    second = projector.state(VIEWER_ID)
    assert second["connection"]["latest_buffered_tick"] >= first["connection"]["latest_buffered_tick"]
    assert second["focus"]["presentation_tick"] >= first["focus"]["presentation_tick"]


def test_follow_request_is_idempotent_and_sink_only_receives_one_transition():
    _, _, registry, repository, live, camera = runtime()
    queued = []
    client = TestClient(create_feed_app(repository, live, camera, registry, lambda item: queued.append(item) is None))
    first = post(client, "/api/feed/live/follow", "follow_a", 4, "descender_b")
    duplicate = post(client, "/api/feed/live/follow", "follow_a", 4, "descender_b")
    assert first.status_code == duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True
    assert len(queued) == 1


def test_release_is_idempotent():
    _, _, registry, repository, live, camera = runtime()
    client = TestClient(create_feed_app(repository, live, camera, registry))
    post(client, "/api/feed/live/follow", "follow_b", 4, "descender_b")
    first = post(client, "/api/feed/live/release", "release_a", 4)
    duplicate = post(client, "/api/feed/live/release", "release_a", 4)
    assert first.status_code == duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True


def test_invalid_follow_returns_an_explicit_error():
    _, _, registry, repository, live, camera = runtime()
    response = post(TestClient(create_feed_app(repository, live, camera, registry)), "/api/feed/live/follow", "bad", 4, "missing")
    assert response.status_code == 404
    assert response.json()["detail"]["reason"] == "unknown_descender"


def test_reconnect_recovers_confirmed_server_focus():
    _, _, registry, repository, live, camera = runtime()
    client = TestClient(create_feed_app(repository, live, camera, registry))
    post(client, "/api/feed/live/follow", "follow_reconnect", 4, "descender_b")
    first = client.get(f"/api/feed/viewer/state?viewer_id={VIEWER_ID}").json()
    reloaded = client.get(f"/api/feed/viewer/state?viewer_id={VIEWER_ID}").json()
    assert reloaded["focus"] == first["focus"]
    assert reloaded["focus"]["mode"] == "manual"


def test_no_active_descent_is_a_safe_product_state():
    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    registry = FeedChannelRegistry("descent_missing", default_viewer_id=VIEWER_ID)
    client = TestClient(create_feed_app(SpectatorRepository(persistence), feed_channel_registry=registry))
    result = client.get(f"/api/feed/viewer/state?viewer_id={VIEWER_ID}")
    assert result.status_code == 200
    assert result.json()["descent"] is None and result.json()["connection"]["state"] == "offline"


def test_empty_channel_directory_is_safe():
    result = viewer_state(empty=True)
    assert result["descenders"] == []
    assert result["summary"]["logical_channel_count"] == 1


def test_backend_stale_status_is_computed_from_freshness():
    _, descent, registry, repository, _, camera = runtime()
    registry.latest_authoritative_tick = 20
    registry.latest_buffered_tick = 4
    status = {"status": "live", "connected_presenter": True, "updated_at_unix_ms": 1000}
    result = build_viewer_state(descent, repository.events(), registry, viewer_id=VIEWER_ID, live_status=status, live_camera=camera(), generated_at_unix_ms=1200)
    assert result["connection"]["state"] == "stale" and result["connection"]["stale"] is True


def test_offline_presenter_is_not_reported_live():
    _, descent, registry, repository, _, camera = runtime()
    result = build_viewer_state(descent, repository.events(), registry, viewer_id=VIEWER_ID, live_status={"status": "offline", "connected_presenter": False}, live_camera=camera())
    assert result["connection"]["state"] == "offline"


def test_manual_a_to_b_switch_is_confirmed_in_aggregate_state():
    _, _, registry, repository, live, camera = runtime()
    client = TestClient(create_feed_app(repository, live, camera, registry))
    post(client, "/api/feed/live/follow", "switch_a", 4, "descender_a")
    post(client, "/api/feed/live/follow", "switch_b", 4, "descender_b")
    result = client.get(f"/api/feed/viewer/state?viewer_id={VIEWER_ID}").json()
    assert result["focus"]["mode"] == "manual"
    assert result["focus"]["active_descender_id"] == "descender_b"


def test_auto_release_is_confirmed_in_aggregate_state():
    _, _, registry, repository, live, camera = runtime()
    client = TestClient(create_feed_app(repository, live, camera, registry))
    post(client, "/api/feed/live/follow", "manual", 4, "descender_b")
    post(client, "/api/feed/live/release", "auto", 4)
    assert client.get(f"/api/feed/viewer/state?viewer_id={VIEWER_ID}").json()["focus"]["mode"] == "automatic"


def test_viewer_diagnostics_measure_latency_and_payload_size():
    _, _, registry, repository, live, camera = runtime()
    app = create_feed_app(repository, live, camera, registry)
    client = TestClient(app)
    client.get(f"/api/feed/viewer/state?viewer_id={VIEWER_ID}")
    result = client.get("/api/feed/viewer/diagnostics").json()
    assert result["request_count"] == 1
    assert result["average_viewer_state_latency_ms"] >= 0
    assert result["average_viewer_state_payload_bytes"] > 100


def test_directory_sorting_is_deterministic_with_active_focus_first():
    first = viewer_state()["descenders"]
    second = viewer_state()["descenders"]
    assert [item["descender_id"] for item in first] == [item["descender_id"] for item in second]
    assert first[0]["currently_auto_focused"] is True


def test_controls_are_explicitly_non_authoritative():
    _, _, registry, repository, live, camera = runtime()
    result = post(TestClient(create_feed_app(repository, live, camera, registry)), "/api/feed/live/follow", "presentation_only", 4, "descender_b").json()
    assert result["authoritative"] is False


def test_in_memory_persistence_serializes_live_writer_and_viewer_reader():
    persistence, descent, registry, repository, live, camera = runtime()
    projector = ViewerStateProjector(repository, registry, live, camera)
    gate = Barrier(2)

    def write_events():
        gate.wait()
        for index in range(40):
            persistence.append_event(CrawlEvent(
                id=f"concurrent_event_{index:03d}", crawl_id=descent.id,
                floor_number=1, tick=index + 2, event_type="CRAWLER_MOVED",
                summary="concurrent viewer proof", actor_ids=["descender_a"],
                location_id="sector_a",
            ))

    def read_states():
        gate.wait()
        return [projector.state(VIEWER_ID)["protocol"] for _ in range(40)]

    with ThreadPoolExecutor(max_workers=2) as workers:
        writer = workers.submit(write_events)
        reader = workers.submit(read_states)
        writer.result()
        assert reader.result() == [VIEWER_PROTOCOL] * 40
