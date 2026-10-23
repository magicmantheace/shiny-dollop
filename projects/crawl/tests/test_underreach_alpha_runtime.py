import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from livingworld.crawl_domain import Crawl
from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.feed_api import create_feed_app
from livingworld.feed_channel_registry import FeedChannelRegistry
from livingworld.headless_mvp_simulation import HeadlessCrawlMVP
from livingworld.live_camera_director import LiveCameraConfig, LiveCameraDirector
from livingworld.live_presentation_bridge import LiveLedgerBuffer, LivePresentationScheduler
from livingworld.runtime_checkpoint import (
    AlphaCheckpointStore,
    CheckpointError,
    CHECKPOINT_PROTOCOL,
    ledger_digest,
    payload_digest,
)
from livingworld.spectator_api import SpectatorRepository
from livingworld.spectator_viewer import build_viewer_state
from livingworld.underreach_alpha_runtime import (
    PROFILES,
    ComponentHealth,
    RuntimeLock,
    RuntimeProfile,
    _atomic_json,
    _directory_size,
    _rss_bytes,
)


def authority(tmp_path: Path, *, floor_count=2):
    persistence = CrawlPersistence(f"sqlite:///{(tmp_path / 'ledger.sqlite3').as_posix()}")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    crawl = service.create_seeded_crawl(
        seed="alpha-runtime-tests",
        crawler_ids=["descender_a", "descender_b", "descender_c"],
        floor_count=floor_count,
        crawl_id="descent_alpha_tests",
    )
    service.start(crawl)
    return persistence, service, crawl


def checkpoint(tmp_path: Path, *, tick=0, retention=4):
    persistence, service, crawl = authority(tmp_path)
    if tick:
        service.set_tick(crawl, tick)
        service.record_event(crawl, "QA_EVENT", "Canonical QA event.", actor_ids=["descender_a"])
    store = AlphaCheckpointStore(tmp_path / "checkpoints", retention=retention)
    loaded = store.write(
        "runtime_test",
        crawl,
        persistence.replay_events(crawl.id),
        simulation_config={"seed": crawl.seed, "floor_count": 2},
        reason="test",
        created_at_unix_ms=1000 + tick,
    )
    return persistence, service, crawl, store, loaded


def test_profile_contract_has_qa_alpha_and_headless():
    assert set(PROFILES) == {"qa", "alpha", "headless"}
    assert PROFILES["alpha"].viewer and PROFILES["alpha"].unreal
    assert not PROFILES["headless"].viewer and not PROFILES["headless"].unreal


def test_alpha_checkpoint_interval_and_retention_are_practical():
    assert PROFILES["alpha"].checkpoint_interval_seconds == 60.0
    assert 10 <= PROFILES["alpha"].checkpoint_retention <= 20


def test_runtime_profile_is_immutable():
    with pytest.raises(Exception):
        PROFILES["qa"].name = "changed"


def test_checkpoint_round_trip_restores_exact_canonical_state(tmp_path):
    _, _, crawl, store, written = checkpoint(tmp_path, tick=7)
    loaded = store.load_latest()
    assert loaded.crawl == crawl
    assert loaded.crawl.fingerprint() == crawl.fingerprint()
    assert loaded.payload["digest"] == written.payload["digest"]


def test_checkpoint_protocol_and_rng_strategy_are_explicit(tmp_path):
    _, _, _, _, loaded = checkpoint(tmp_path)
    assert loaded.payload["protocol"] == CHECKPOINT_PROTOCOL
    assert loaded.payload["canonical"]["rng_state"] == "stateless_sha256_seed_tick"


def test_checkpoint_serialization_is_deterministic_for_same_inputs(tmp_path):
    persistence, _, crawl = authority(tmp_path)
    left = AlphaCheckpointStore(tmp_path / "left")
    right = AlphaCheckpointStore(tmp_path / "right")
    args = dict(
        simulation_config={"floor_count": 2, "seed": crawl.seed},
        reason="determinism", created_at_unix_ms=1234,
    )
    a = left.write("runtime_same", crawl, persistence.replay_events(crawl.id), **args)
    b = right.write("runtime_same", crawl, persistence.replay_events(crawl.id), **args)
    assert a.payload == b.payload


def test_wall_clock_metadata_does_not_change_canonical_fingerprint(tmp_path):
    persistence, _, crawl = authority(tmp_path)
    store = AlphaCheckpointStore(tmp_path / "checkpoints")
    a = store.write("runtime", crawl, persistence.replay_events(crawl.id), simulation_config={}, created_at_unix_ms=1)
    b = store.write("runtime", crawl, persistence.replay_events(crawl.id), simulation_config={}, created_at_unix_ms=2)
    assert a.payload["canonical"]["simulation_fingerprint"] == b.payload["canonical"]["simulation_fingerprint"]
    assert a.payload["digest"] != b.payload["digest"]


def test_checkpoint_digest_rejects_corruption(tmp_path):
    _, _, _, _, loaded = checkpoint(tmp_path)
    payload = json.loads(loaded.path.read_text())
    payload["canonical"]["tick"] += 1
    with pytest.raises(CheckpointError, match="digest"):
        AlphaCheckpointStore.validate(payload)


def test_checkpoint_state_fingerprint_rejects_semantic_tamper_with_rehashed_envelope(tmp_path):
    _, _, _, _, loaded = checkpoint(tmp_path)
    payload = json.loads(loaded.path.read_text())
    payload["canonical"]["state"]["current_tick"] = 1
    body = {key: value for key, value in payload.items() if key != "digest"}
    payload["digest"] = payload_digest(body)
    with pytest.raises(CheckpointError, match="tick|fingerprint"):
        AlphaCheckpointStore.validate(payload)


def test_incomplete_temporary_checkpoint_is_never_latest(tmp_path):
    _, _, _, store, loaded = checkpoint(tmp_path)
    (store.directory / "checkpoint-9999999999-broken.json.tmp").write_text("{")
    assert store.load_latest().path == loaded.path


def test_corrupt_latest_pointer_falls_back_to_valid_checkpoint(tmp_path):
    _, _, _, store, loaded = checkpoint(tmp_path)
    store.latest_path.write_text("not json")
    assert store.load_latest().path == loaded.path


def test_checkpoint_retention_keeps_newest_valid_files(tmp_path):
    persistence, service, crawl = authority(tmp_path)
    store = AlphaCheckpointStore(tmp_path / "checkpoints", retention=3)
    for tick in range(6):
        service.set_tick(crawl, tick)
        store.write("runtime", crawl, persistence.replay_events(crawl.id), simulation_config={}, created_at_unix_ms=tick)
    files = list(store.directory.glob("checkpoint-*.json"))
    assert len(files) == 3
    assert store.load_latest().crawl.current_tick == 5


def test_latest_pointer_is_only_written_after_valid_file(tmp_path):
    _, _, _, store, loaded = checkpoint(tmp_path)
    pointer = json.loads(store.latest_path.read_text())
    assert pointer["path"] == loaded.path.name
    assert (store.directory / pointer["path"]).exists()
    assert not list(store.directory.glob("*.tmp"))


def test_checkpoint_requires_exact_ledger_membership(tmp_path):
    persistence, _, crawl = authority(tmp_path)
    events = persistence.replay_events(crawl.id)[:-1]
    with pytest.raises(CheckpointError, match="Ledger"):
        AlphaCheckpointStore(tmp_path / "checkpoints").write(
            "runtime", crawl, events, simulation_config={}, created_at_unix_ms=1
        )


def test_ledger_digest_is_order_independent_of_database_query_order(tmp_path):
    persistence, _, crawl = authority(tmp_path)
    events = persistence.replay_events(crawl.id)
    assert ledger_digest(events) == ledger_digest(list(reversed(events)))


def test_resume_prunes_only_post_checkpoint_events(tmp_path):
    persistence, service, crawl, store, loaded = checkpoint(tmp_path, tick=2)
    expected_ids = list(crawl.history_event_ids)
    service.set_tick(crawl, 3)
    service.record_event(crawl, "AFTER_CHECKPOINT", "Must be replayed after restore.")
    removed = persistence.restore_checkpoint_state(loaded.crawl)
    assert removed == 1
    assert {item.id for item in persistence.replay_events(crawl.id)} == set(expected_ids)


def test_resume_refuses_missing_canonical_ledger_prefix(tmp_path):
    persistence, _, _, _, loaded = checkpoint(tmp_path)
    persistence.reset_all()
    with pytest.raises(RuntimeError, match="incomplete"):
        persistence.restore_checkpoint_state(loaded.crawl)


def test_canonical_fingerprint_survives_sorted_json_round_trip(tmp_path):
    _, _, crawl = authority(tmp_path)
    restored = Crawl.model_validate(json.loads(json.dumps(crawl.model_dump(mode="json"), sort_keys=True)))
    assert restored.fingerprint() == crawl.fingerprint()


def test_split_checkpoint_resume_matches_uninterrupted_canonical_run(tmp_path):
    def create_run(directory: Path):
        persistence = CrawlPersistence(f"sqlite:///{(directory / 'ledger.sqlite3').as_posix()}")
        persistence.initialize()
        service = CrawlLifecycleService(persistence)
        crawl = service.create_seeded_crawl(
            seed="alpha-split-resume",
            crawler_ids=[f"descender_{index:02d}" for index in range(8)],
            floor_count=8,
            crawl_id="descent_split_resume",
        )
        service.start(crawl)
        simulation = HeadlessCrawlMVP(service, intermission_ticks=2, director_interval=5)
        simulation.prepare(crawl)
        return persistence, service, crawl, simulation

    uninterrupted = tmp_path / "uninterrupted"
    uninterrupted.mkdir()
    full_persistence, _, full_crawl, full_simulation = create_run(uninterrupted)
    for _ in range(20):
        full_simulation.step(full_crawl)

    split = tmp_path / "split"
    split.mkdir()
    split_persistence, _, split_crawl, split_simulation = create_run(split)
    for _ in range(8):
        split_simulation.step(split_crawl)
    store = AlphaCheckpointStore(split / "checkpoints")
    store.write(
        "runtime_split",
        split_crawl,
        split_persistence.replay_events(split_crawl.id),
        simulation_config={"seed": split_crawl.seed, "floor_count": 8},
        created_at_unix_ms=1234,
    )

    # Reopen both durable state and checkpoint as a new process would.
    resumed_persistence = CrawlPersistence(f"sqlite:///{(split / 'ledger.sqlite3').as_posix()}")
    resumed_persistence.initialize()
    resumed_service = CrawlLifecycleService(resumed_persistence)
    resumed_crawl = store.load_latest().crawl.model_copy(deep=True)
    assert resumed_persistence.restore_checkpoint_state(resumed_crawl) == 0
    resumed_simulation = HeadlessCrawlMVP(
        resumed_service, intermission_ticks=2, director_interval=5
    )
    for _ in range(12):
        resumed_simulation.step(resumed_crawl)

    full_events = full_persistence.replay_events(full_crawl.id)
    resumed_events = resumed_persistence.replay_events(resumed_crawl.id)
    assert resumed_crawl.current_tick == full_crawl.current_tick == 20
    assert resumed_crawl.history_event_ids == full_crawl.history_event_ids
    assert resumed_crawl.fingerprint() == full_crawl.fingerprint()
    assert ledger_digest(resumed_events) == ledger_digest(full_events)


def test_history_event_ids_do_not_affect_simulation_fingerprint(tmp_path):
    _, _, crawl = authority(tmp_path)
    copied = crawl.model_copy(deep=True)
    copied.history_event_ids.append("presentation_never_reads_this_as_state")
    assert copied.fingerprint() == crawl.fingerprint()


def test_incremental_persistence_lookup_preserves_requested_event_order(tmp_path):
    persistence, _, crawl = authority(tmp_path)
    ids = list(reversed(crawl.history_event_ids))
    assert [item.id for item in persistence.events_by_ids(ids)] == ids


def test_incremental_persistence_lookup_rejects_missing_event(tmp_path):
    persistence, _, _ = authority(tmp_path)
    with pytest.raises(KeyError):
        persistence.events_by_ids(["event_missing"])


def test_runtime_health_endpoint_is_read_only(tmp_path):
    persistence, _, crawl = authority(tmp_path)
    registry = FeedChannelRegistry(crawl.id)
    registry.register(crawl)
    before = crawl.fingerprint()
    health = lambda: {"protocol": "underreach.alpha-runtime.v1", "runtime_id": "runtime_x", "overall_status": "healthy"}
    client = TestClient(create_feed_app(SpectatorRepository(persistence, crawl.id), feed_channel_registry=registry, runtime_health_provider=health))
    result = client.get("/api/feed/runtime/health")
    assert result.status_code == 200 and result.json()["overall_status"] == "healthy"
    assert crawl.fingerprint() == before


def test_viewer_projection_contains_compact_runtime_health(tmp_path):
    persistence, _, crawl = authority(tmp_path)
    registry = FeedChannelRegistry(crawl.id, default_viewer_id="viewer")
    registry.register(crawl)
    registry.update(crawl, [], presentation_tick=0, presentation_seconds=0, buffered_tick=0)
    runtime = {"overall_status": "healthy", "uptime_seconds": 60, "presentation_lag_ticks": 0, "unreal_connected": True, "checkpoint_age_seconds": 2}
    result = build_viewer_state(crawl, persistence.replay_events(crawl.id), registry, viewer_id="viewer", runtime_health=runtime)
    assert result["runtime"] == runtime


def test_runtime_health_fallback_is_safe_offline(tmp_path):
    persistence, _, crawl = authority(tmp_path)
    result = TestClient(create_feed_app(SpectatorRepository(persistence, crawl.id))).get("/api/feed/runtime/health").json()
    assert result["overall_status"] == "offline" and result["authoritative"] is False


def test_component_health_clears_failure_after_recovery():
    component = ComponentHealth("viewer")
    component.fail("down", recovering=True)
    assert component.status == "recovering" and component.consecutive_failures == 1
    component.healthy(9, pid=123)
    assert component.status == "healthy" and component.consecutive_failures == 0 and component.last_healthy_tick == 9


def test_single_instance_lock_rejects_live_owner(tmp_path):
    path = tmp_path / "runtime.lock"
    first = RuntimeLock(path, "runtime_a")
    first.acquire()
    try:
        with pytest.raises(RuntimeError, match="already owned"):
            RuntimeLock(path, "runtime_b").acquire()
    finally:
        first.release()


def test_single_instance_lock_recovers_stale_metadata(tmp_path):
    path = tmp_path / "runtime.lock"
    path.write_text(json.dumps({"pid": 999999999, "runtime_id": "stale"}))
    lock = RuntimeLock(path, "runtime_new")
    lock.acquire()
    assert json.loads(path.read_text())["runtime_id"] == "runtime_new"
    lock.release()


def test_lock_release_never_removes_another_runtime_lock(tmp_path):
    path = tmp_path / "runtime.lock"
    lock = RuntimeLock(path, "runtime_a")
    lock.acquire()
    value = json.loads(path.read_text())
    value["runtime_id"] = "runtime_b"
    path.write_text(json.dumps(value))
    lock.release()
    assert path.exists()


def test_live_buffer_retention_is_bounded(tmp_path):
    persistence, service, crawl = authority(tmp_path)
    buffer = LiveLedgerBuffer(crawl.id, presentation_delay_ticks=0, maximum_events=8)
    for tick in range(1, 15):
        service.set_tick(crawl, tick)
        event = service.record_event(crawl, "QA_EVENT", f"event {tick}")
        buffer.push([event])
        buffer.consume_ready()
    assert buffer.snapshot()["retained_event_count"] <= 8


def test_scheduler_transient_limit_is_explicit(tmp_path):
    _, _, crawl = authority(tmp_path)
    scheduler = LivePresentationScheduler(crawl.id, presentation_seed="test")
    scheduler.bootstrap(crawl, environment={})
    assert scheduler.maximum_transient_history == 4096


def test_camera_transient_limit_is_explicit():
    director = LiveCameraDirector("descent", presentation_seed="test", environment={}, config=LiveCameraConfig())
    assert director.maximum_transient_history == 1024


def test_registry_transient_limit_is_explicit(tmp_path):
    _, _, crawl = authority(tmp_path)
    registry = FeedChannelRegistry(crawl.id)
    registry.register(crawl)
    assert registry.maximum_transient_history == 1024


def test_atomic_runtime_json_leaves_no_partial_file(tmp_path):
    path = tmp_path / "state" / "runtime.json"
    _atomic_json(path, {"status": "healthy"})
    assert json.loads(path.read_text()) == {"status": "healthy"}
    assert not path.with_suffix(".json.tmp").exists()


def test_directory_size_counts_only_files(tmp_path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "a").write_bytes(b"123")
    (tmp_path / "nested" / "b").write_bytes(b"4567")
    assert _directory_size(tmp_path) == 7


def test_process_memory_sampler_is_safe_for_current_process():
    value = _rss_bytes(os.getpid())
    assert value is None or value > 0


def test_qa_fault_schedule_cannot_be_enabled_by_alpha_profile_data():
    assert "fault_injection" not in PROFILES["alpha"].__dict__
