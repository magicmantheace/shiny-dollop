from fastapi.testclient import TestClient

from livingworld.api import create_app
from livingworld.config import Settings


def make_client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'institutions-api.db'}",
        admin_key="secret",
        tick_seconds=3600,
        world_seed="institutions-api-test",
    )
    return TestClient(create_app(settings))


def test_world_api_exposes_laws_institutions_and_compliance(tmp_path) -> None:
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/admin/world/generate-continent",
            json={"seed": "institutions-api", "name": "Eldara"},
            headers={"X-Admin-Key": "secret"},
        )
        assert response.status_code == 200

        state = client.get("/api/world/state")
        assert state.status_code == 200
        payload = state.json()
        assert payload["kingdoms"]
        for kingdom in payload["kingdoms"].values():
            assert kingdom["institutions_initialized"] is True
            assert "tax_rate" in kingdom["laws"]
            assert "anti_bandit_spending" in kingdom["laws"]
            assert "administrative_reach" in kingdom["institutions"]
            assert "corruption" in kingdom["institutions"]
            assert set(kingdom["policy_compliance"]) == set(kingdom["settlement_ids"])
            assert "tax_rate" in kingdom["effective_policies"]

        summary = client.get("/api/world")
        assert summary.status_code == 200
        metrics = summary.json()["metrics"]
        assert 0.0 <= metrics["average_administrative_reach"] <= 1.0
        assert 0.0 <= metrics["average_tax_efficiency"] <= 1.0
        assert 0.0 <= metrics["average_institutional_corruption"] <= 1.0
        assert 0.0 <= metrics["average_policy_compliance"] <= 1.0
