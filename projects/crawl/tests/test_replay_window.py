"""Replay contract (§37): window selection with its own digest-bearing manifest."""
from __future__ import annotations

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.replay_engine import ReplayArchive


def _archive(tmp_path):
    persistence = CrawlPersistence(f"sqlite:///{tmp_path / 'replay.db'}")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    crawl = service.create_seeded_crawl(
        seed="replay-contract", crawler_ids=["npc_a", "npc_b"], floor_count=2
    )
    service.start(crawl, tick=10)
    service.record_event(crawl, "CRAWLER_MOVED", "a moved", actor_ids=["npc_a"])
    service.record_event(crawl, "CRAWLER_MOVED", "b moved", actor_ids=["npc_b"])
    service.complete_current_floor(crawl, advance_ticks=5)
    service.record_event(crawl, "CRAWLER_DIED", "a died", actor_ids=["npc_a"])
    events = persistence.list_events(crawl.id, limit=10000)
    return ReplayArchive(crawl, events)


def test_window_manifest_records_range_entities_and_digest(tmp_path):
    archive = _archive(tmp_path)
    assert archive.manifest.window_start_tick is None  # whole-archive manifest

    window = archive.select_window(
        start_tick=10, end_tick=14, actor_ids=("npc_a",), checkpoint_id="cp-1"
    )
    manifest = window.manifest
    assert manifest.window_start_tick == 10
    assert manifest.window_end_tick == 14
    assert manifest.required_entity_ids == ("npc_a",)
    assert manifest.checkpoint_id == "cp-1"
    assert all(10 <= e.tick <= 14 for e in window.events)
    assert all("npc_a" in e.actor_ids for e in window.events)
    assert manifest.event_count == len(window.events)
    # The digest is computed over the window's events only, not the archive's.
    assert manifest.authoritative_event_digest != archive.manifest.authoritative_event_digest


def test_window_selection_is_deterministic_and_nondestructive(tmp_path):
    archive = _archive(tmp_path)
    first = archive.select_window(start_tick=10, actor_ids=("npc_a",))
    second = archive.select_window(start_tick=10, actor_ids=("npc_a",))
    assert first.manifest.authoritative_event_digest == second.manifest.authoritative_event_digest
    # The parent archive is untouched.
    assert first.manifest.event_count <= archive.manifest.event_count
    assert archive.manifest.window_start_tick is None


def test_empty_window_is_valid(tmp_path):
    archive = _archive(tmp_path)
    window = archive.select_window(start_tick=10_000, end_tick=20_000)
    assert window.events == ()
    assert window.manifest.event_count == 0
