from fastapi.testclient import TestClient

from livingworld.api import create_app
from livingworld.config import Settings
from livingworld.frontier import found_frontier_settlement


def make_client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'frontier-api.db'}",
        admin_key="secret",
        tick_seconds=3600,
        world_seed="frontier-api-test",
    )
    return TestClient(create_app(settings))


def test_frontier_state_is_visible_through_existing_api(tmp_path) -> None:
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/admin/world/generate-continent",
            json={"seed": "frontier-api", "name": "Eldara"},
            headers={"X-Admin-Key": "secret"},
        )
        assert response.status_code == 200

        runtime = client.app.state.runtime
        with runtime._lock:
            kingdom_id = sorted(runtime.world.kingdoms)[0]
            settlement = found_frontier_settlement(runtime.engine, kingdom_id, force=True)
            runtime.persistence.save_world(runtime.world)

        state = client.get("/api/world/state")
        assert state.status_code == 200
        payload = state.json()
        assert payload["territory_claims"]
        claim = next(
            item for item in payload["territory_claims"].values()
            if item["settlement_id"] == settlement.id
        )
        assert claim["kingdom_id"] == kingdom_id
        assert claim["control_radius"] > 0

        settlements = client.get(f"/api/settlements?kingdom_id={kingdom_id}")
        assert settlements.status_code == 200
        frontier = next(item for item in settlements.json() if item["id"] == settlement.id)
        assert frontier["frontier"] is True
        assert frontier["origin_settlement_id"]

        kingdoms = client.get("/api/kingdoms")
        assert kingdoms.status_code == 200
        kingdom = next(item for item in kingdoms.json() if item["id"] == kingdom_id)
        assert claim["id"] in kingdom["claims"]
