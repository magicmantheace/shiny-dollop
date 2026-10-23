"""Slice 30 acceptance gate: a crawl can conclude, be archived, and a new
seeded crawl can begin without deleting or corrupting historical
queryability.
"""
from __future__ import annotations

from livingworld.crawl_domain import CrawlStatus
from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService


def _make_service(tmp_path):
    persistence = CrawlPersistence(f"sqlite:///{tmp_path / 'crawl.db'}")
    persistence.initialize()
    return CrawlLifecycleService(persistence), persistence


def test_conclude_archive_new_crawl_preserves_history(tmp_path):
    service, persistence = _make_service(tmp_path)

    first = service.create_seeded_crawl(
        seed="season-one", crawler_ids=["npc_a", "npc_b"], floor_count=2, crawl_id="crawl_one"
    )
    service.start(first, tick=10)
    service.record_event(first, "CRAWLER_MOVED", "npc_a moved", actor_ids=["npc_a"])
    service.complete_current_floor(first, advance_ticks=5)
    service.complete_current_floor(first, advance_ticks=5)
    assert first.status == CrawlStatus.COMPLETED

    service.archive(first)
    assert first.status == CrawlStatus.ARCHIVED

    # A new seeded crawl begins cleanly alongside the archived one.
    second = service.create_seeded_crawl(
        seed="season-two", crawler_ids=["npc_c"], floor_count=1, crawl_id="crawl_two"
    )
    service.start(second, tick=3)
    service.record_event(second, "CRAWLER_MOVED", "npc_c moved", actor_ids=["npc_c"])
    assert second.status == CrawlStatus.RUNNING

    # Both crawls remain queryable with intact, separate histories.
    archived = persistence.load_crawl("crawl_one")
    assert archived is not None
    assert archived.status == CrawlStatus.ARCHIVED
    assert archived.seed == "season-one"

    running = persistence.load_crawl("crawl_two")
    assert running is not None
    assert running.status == CrawlStatus.RUNNING

    first_events = persistence.list_events("crawl_one", limit=500)
    assert any(e.event_type == "CRAWL_ARCHIVED" for e in first_events)
    assert all(e.crawl_id == "crawl_one" for e in first_events)

    second_events = persistence.list_events("crawl_two", limit=500)
    assert all(e.crawl_id == "crawl_two" for e in second_events)
    assert {e.crawl_id for e in first_events + second_events} == {"crawl_one", "crawl_two"}

    by_status = {c.id: c.status for c in persistence.list_crawls(status="archived")}
    assert by_status.get("crawl_one") == CrawlStatus.ARCHIVED
    assert "crawl_two" not in by_status
