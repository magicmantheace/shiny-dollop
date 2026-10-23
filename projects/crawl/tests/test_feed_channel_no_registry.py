"""Regression test: descender live channel without a feed-channel registry.

Prior to the fix, ``GET /api/feed/descenders/{id}/channel`` (and
``GET /api/feed/channels/{channel_id}``) returned HTTP 500 when the app was
created without a ``feed_channel_registry``: the route function was called
directly as a Python function, so FastAPI's ``Query`` descriptor leaked into
``build_descender_channel`` as ``recent_event_limit`` and ``max()`` raised
``TypeError``.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.feed_api import create_feed_app
from livingworld.feed_channel_registry import descender_channel_id
from livingworld.spectator_api import SpectatorRepository


def _app_without_registry():
    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    descent = service.create_seeded_crawl(
        seed="underreach-no-registry-channel-tests",
        crawler_ids=["descender_a", "descender_b"],
        floor_count=2,
        crawl_id="descent_no_registry",
    )
    service.start(descent)
    repository = SpectatorRepository(persistence, descent.id)
    # NOTE: no feed_channel_registry passed.
    return TestClient(create_feed_app(repository)), "descender_a"


def test_descender_channel_without_registry_returns_200():
    client, descender_id = _app_without_registry()
    response = client.get(f"/api/feed/descenders/{descender_id}/channel")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["channel_id"] == descender_channel_id(descender_id)


def test_generic_channel_route_without_registry_returns_200():
    client, descender_id = _app_without_registry()
    response = client.get(f"/api/feed/channels/{descender_channel_id(descender_id)}")
    assert response.status_code == 200, response.text
    assert response.json()["channel_id"] == descender_channel_id(descender_id)


def test_descender_channel_without_registry_unknown_descender_404():
    client, _ = _app_without_registry()
    response = client.get("/api/feed/descenders/no_such_descender/channel")
    assert response.status_code == 404
