"""Feed notifications: notable canonical events for a followed descender."""
from __future__ import annotations

from fastapi.testclient import TestClient

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.feed_api import create_feed_app
from livingworld.feed_channel_registry import FeedChannelRegistry, descender_channel_id
from livingworld.spectator_api import SpectatorRepository


def _client(tmp_path):
    persistence = CrawlPersistence(f"sqlite:///{tmp_path / 'notif.db'}")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    descent = service.create_seeded_crawl(
        seed="feed-notifications", crawler_ids=["watched_one", "unwatched_two"], floor_count=1
    )
    service.start(descent, tick=5)
    service.record_event(
        descent, "CRAWLER_INJURED", "watched_one was hurt", actor_ids=["watched_one"]
    )
    service.record_event(
        descent, "CRAWLER_MOVED", "unwatched_two moved", actor_ids=["unwatched_two"]
    )
    service.record_event(
        descent, "CRAWLER_INJURED", "unwatched_two was hurt", actor_ids=["unwatched_two"]
    )
    registry = FeedChannelRegistry(descent.id)
    registry.register(descent)
    return (
        TestClient(create_feed_app(SpectatorRepository(persistence, descent.id), feed_channel_registry=registry)),
        "watched_one",
    )


def test_notifications_surface_followed_descender_events(tmp_path):
    client, followed = _client(tmp_path)
    follow = client.post(
        "/api/feed/live/follow",
        json={
            "viewer_id": "notif_viewer",
            "request_id": "follow_1",
            "requested_at_presentation_tick": 1,
            "descender_id": followed,
        },
    )
    assert follow.status_code == 200, follow.text

    response = client.get("/api/feed/notifications", params={"viewer_id": "notif_viewer"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["followed_descender_id"] == followed
    assert payload["items"], "expected the injury event for the followed descender"
    assert all(followed in item["actor_ids"] for item in payload["items"])
    assert all(item["canonical"] for item in payload["items"])
    assert all(item["event_type"] == "DESCENDER_INJURED" for item in payload["items"])


def test_notifications_empty_without_follow(tmp_path):
    client, _ = _client(tmp_path)
    response = client.get("/api/feed/notifications", params={"viewer_id": "nobody_follows"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert payload["followed_descender_id"] is None


def test_notifications_unavailable_without_registry(tmp_path):
    persistence = CrawlPersistence(f"sqlite:///{tmp_path / 'notif2.db'}")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    descent = service.create_seeded_crawl(
        seed="feed-notifications-2", crawler_ids=["solo"], floor_count=1
    )
    service.start(descent)
    client = TestClient(create_feed_app(SpectatorRepository(persistence, descent.id)))
    response = client.get("/api/feed/notifications", params={"viewer_id": "v"})
    assert response.status_code == 503
