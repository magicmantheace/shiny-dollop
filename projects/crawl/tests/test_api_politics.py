from fastapi.testclient import TestClient

from livingworld.api import create_app
from livingworld.config import Settings


def make_client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'politics-api.db'}",
        admin_key="secret",
        tick_seconds=3600,
        world_seed="politics-api-test",
    )
    return TestClient(create_app(settings))


def test_continent_api_exposes_persistent_political_society(tmp_path) -> None:
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/admin/world/generate-continent",
            json={"seed": "politics-api", "name": "Eldara"},
            headers={"X-Admin-Key": "secret"},
        )
        assert response.status_code == 200

        state = client.get("/api/world/state")
        assert state.status_code == 200
        payload = state.json()
        assert len(payload["political_factions"]) == 24
        assert all(kingdom["politics_initialized"] for kingdom in payload["kingdoms"].values())
        assert all(len(kingdom["faction_ids"]) == 4 for kingdom in payload["kingdoms"].values())
        assert all("ruler" in kingdom["political_offices"] for kingdom in payload["kingdoms"].values())
        assert all(kingdom["political_crisis_months"] == 0 for kingdom in payload["kingdoms"].values())
        assert all(kingdom["last_political_resolution_year"] is None for kingdom in payload["kingdoms"].values())
        assert all(kingdom["last_political_resolution"] is None for kingdom in payload["kingdoms"].values())

        kingdom_id = sorted(payload["kingdoms"])[0]
        kingdom = client.get(f"/api/kingdoms/{kingdom_id}")
        assert kingdom.status_code == 200
        item = kingdom.json()
        assert item["faction_ids"]
        assert item["political_offices"]["ruler"]["holder_npc_id"] == item["ruler_npc_id"]
        assert item["political_crisis_months"] == 0
        assert item["last_political_resolution"] is None

        summary = client.get("/api/world")
        assert summary.status_code == 200
        metrics = summary.json()["metrics"]
        assert metrics["political_factions"] == 24.0
        assert 0.0 <= metrics["average_legitimacy"] <= 1.0
        assert 0.0 <= metrics["average_faction_loyalty"] <= 1.0
