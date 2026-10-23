"""Feed search: read-only substring search over descenders and canonical events."""
from __future__ import annotations

from fastapi.testclient import TestClient

from livingworld.crawl_domain import CrawlEvent
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


def test_search_rejects_whitespace_only_query(tmp_path):
    client = _client(tmp_path)
    for whitespace in (" ", "   ", "\t \n "):
        response = client.get("/api/feed/search", params={"q": whitespace})
        assert response.status_code == 422, f"q={whitespace!r} returned {response.status_code}"
    # A query with surrounding whitespace still searches the trimmed needle.
    response = client.get("/api/feed/search", params={"q": "  cache  "})
    assert response.status_code == 200
    assert any("cache" in e["summary"].lower() for e in response.json()["events"])


def _bulk_client(tmp_path, event_count: int):
    persistence = CrawlPersistence(f"sqlite:///{tmp_path / 'search_bulk.db'}")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    descent = service.create_seeded_crawl(
        seed="feed-search-bulk", crawler_ids=["seeker"], floor_count=1
    )
    service.start(descent, tick=1)
    crawl_id = descent.id
    for index in range(event_count):
        summary = (
            "ancient relic xyz buried deep"
            if index == 0
            else f"routine filler event number {index}"
        )
        persistence.append_event(
            CrawlEvent(
                id=f"bulk-{index:05d}",
                crawl_id=crawl_id,
                tick=index + 1,
                event_type="BULK_FILLER",
                summary=summary,
                actor_ids=["seeker"],
            )
        )
    return TestClient(create_feed_app(SpectatorRepository(persistence, crawl_id)))


def test_search_finds_events_beyond_latest_1000(tmp_path):
    # 1,200 events: the only match sits in the oldest events, outside the
    # latest-1,000 window the endpoint used to read.
    client = _bulk_client(tmp_path, 1200)
    response = client.get("/api/feed/search", params={"q": "ancient relic xyz"})
    assert response.status_code == 200
    events = response.json()["events"]
    assert len(events) == 1
    assert events[0]["id"] == "bulk-00000"
    assert "ancient relic xyz" in events[0]["summary"]


def test_search_like_wildcards_match_literally(tmp_path):
    client = _client(tmp_path)
    # "%" and "_" in the needle are escaped: they must not act as wildcards.
    response = client.get("/api/feed/search", params={"q": "seek%"})
    assert response.status_code == 200
    assert response.json()["descenders"] == [] and response.json()["events"] == []
