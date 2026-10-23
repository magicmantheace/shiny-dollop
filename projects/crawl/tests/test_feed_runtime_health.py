"""Runtime health endpoint: provider data flows end-to-end; offline fallback works."""
from __future__ import annotations

from fastapi.testclient import TestClient

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.feed_api import create_feed_app
from livingworld.spectator_api import SpectatorRepository


def _client(tmp_path, **kwargs):
    persistence = CrawlPersistence(f"sqlite:///{tmp_path / 'health.db'}")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    descent = service.create_seeded_crawl(
        seed="runtime-health", crawler_ids=["npc_a"], floor_count=1
    )
    service.start(descent, tick=7)
    return TestClient(
        create_feed_app(SpectatorRepository(persistence, descent.id), **kwargs)
    )


def test_runtime_health_with_provider(tmp_path):
    provider_payload = {
        "protocol": "underreach.alpha-runtime.v1",
        "runtime_id": "runtime_test",
        "overall_status": "healthy",
        "simulation_tick": 42,
        "recovery_count": 1,
    }
    client = _client(tmp_path, runtime_health_provider=lambda: provider_payload)
    response = client.get("/api/feed/runtime/health")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["runtime_id"] == "runtime_test"
    assert payload["overall_status"] == "healthy"
    assert payload["simulation_tick"] == 42
    assert payload["recovery_count"] == 1


def test_runtime_health_offline_fallback(tmp_path):
    client = _client(tmp_path)
    response = client.get("/api/feed/runtime/health")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["overall_status"] == "offline"
    assert payload["authoritative"] is False
    assert payload["simulation_tick"] == 7
