from fastapi.testclient import TestClient

from livingworld.api import create_app
from livingworld.config import Settings


def make_client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'production-api.db'}",
        admin_key="secret",
        tick_seconds=3600,
        world_seed="production-api-test",
    )
    return TestClient(create_app(settings))


def test_continent_api_exposes_production_labor_and_reserves(tmp_path) -> None:
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/admin/world/generate-continent",
            json={"seed": "production-api", "name": "Eldara"},
            headers={"X-Admin-Key": "secret"},
        )
        assert response.status_code == 200

        state = client.get("/api/world/state")
        assert state.status_code == 200
        payload = state.json()
        settlements = list(payload["settlements"].values())
        kingdoms = list(payload["kingdoms"].values())

        assert settlements
        assert all(item["production_initialized"] for item in settlements if item["population"] > 0)
        assert all(item["production_sites"] for item in settlements if item["population"] > 0)
        assert all(item["labor_allocation"] for item in settlements if item["population"] > 0)
        assert all("food" in item["resource_reserves"] for item in kingdoms)

        summary = client.get("/api/world")
        assert summary.status_code == 200
        metrics = summary.json()["metrics"]
        assert metrics["production_sites"] > 0
        assert 0.0 <= metrics["average_labor_utilization"] <= 1.0
        assert metrics["kingdom_food_reserves"] >= 0.0
