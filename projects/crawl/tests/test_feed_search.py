"""Feed search: read-only substring search over descenders and canonical events."""
from __future__ import annotations

from fastapi.testclient import TestClient

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.feed_api import create_feed_app
from livingworld.spectator_api import SpectatorRepository


def _client(tmp_path):
    persistence = CrawlPersistence(f"sqlite:///{tmp_path / 'search.db'}")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    descent = service.create_seeded_crawl(
        seed="feed-search", crawler_ids=["seek_target", "other_one"], floor_count=1
    )
    service.start(descent, tick=5)
    service.record_event(
        descent, "CRAWLER_MOVED", "seek_target found a cache", actor_ids=["seek_target"]
    )
    return TestClient(create_feed_app(SpectatorRepository(persistence, descent.id)))


def test_search_finds_descender_by_id_substring(tmp_path):
    client = _client(tmp_path)
    response = client.get("/api/feed/search", params={"q": "seek_tar"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["query"] == "seek_tar"
    ids = [d["descender_id"] for d in payload["descenders"]]
    assert "seek_target" in ids
    assert "other_one" not in ids


def test_search_finds_event_by_summary_and_actor(tmp_path):
    client = _client(tmp_path)
    response = client.get("/api/feed/search", params={"q": "cache"})
    assert response.status_code == 200
    events = response.json()["events"]
    assert events, "expected the recorded cache event"
    assert all(e["canonical"] for e in events)
    assert any("cache" in e["summary"].lower() for e in events)


def test_search_is_case_insensitive_and_empty_safe(tmp_path):
    client = _client(tmp_path)
    upper = client.get("/api/feed/search", params={"q": "SEEK_TARGET"}).json()
    lower = client.get("/api/feed/search", params={"q": "seek_target"}).json()
    assert upper["descenders"] == lower["descenders"]
    empty = client.get("/api/feed/search", params={"q": "zzz_no_match_zzz"}).json()
    assert empty["descenders"] == [] and empty["events"] == []


def test_search_rejects_blank_query(tmp_path):
    client = _client(tmp_path)
    response = client.get("/api/feed/search", params={"q": ""})
    assert response.status_code == 422
