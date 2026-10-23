from fastapi.testclient import TestClient

from livingworld.api import create_app
from livingworld.config import Settings


def make_client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'warfare-api.db'}",
        admin_key="secret",
        tick_seconds=3600,
        world_seed="warfare-api-test",
    )
    return TestClient(create_app(settings))


def test_warfare_state_is_visible_through_existing_api_contracts(tmp_path) -> None:
    with make_client(tmp_path) as client:
        generated = client.post(
            "/api/admin/world/generate-continent",
            json={"seed": "warfare-api", "name": "Eldara"},
            headers={"X-Admin-Key": "secret"},
        )
        assert generated.status_code == 200

        runtime = client.app.state.runtime
        with runtime._lock:
            kingdom_ids = sorted(runtime.world.kingdoms)
            attacker_id, defender_id = kingdom_ids[:2]
            war = runtime.engine.declare_war(attacker_id, defender_id, "API warfare test", source="test")
            runtime.engine._resolve_wars()
            runtime.persistence.save_world(runtime.world)

        wars = client.get("/api/wars?active_only=true")
        assert wars.status_code == 200
        payload = wars.json()
        assert payload
        item = next(w for w in payload if w["id"] == war.id)
        assert item["front_settlement_ids"]
        assert "attacker_exhaustion" in item
        assert "defender_exhaustion" in item
        assert "siege_progress" in item
        assert "occupation_by_settlement" in item
        assert "peace_terms" in item

        armies = client.get("/api/armies")
        assert armies.status_code == 200
        assert all("supply_efficiency" in army for army in armies.json())
        assert all("supply_source_settlement_id" in army for army in armies.json())

        state = client.get("/api/world/state")
        assert state.status_code == 200
        saved = state.json()
        assert saved["wars"][war.id]["front_settlement_ids"]
        assert "overlord_kingdom_id" in next(iter(saved["kingdoms"].values()))
        assert "occupied_by_kingdom_id" in next(iter(saved["settlements"].values()))
