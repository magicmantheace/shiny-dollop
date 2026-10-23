from fastapi.testclient import TestClient

from livingworld.api import create_app
from livingworld.config import Settings
from livingworld.domain import BorderPolicy, RefugeePolicy, War


def make_client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'border-api.db'}",
        admin_key="secret",
        tick_seconds=3600,
        world_seed="border-api-test",
    )
    return TestClient(create_app(settings))


def test_policy_commands_are_visible_in_map_and_kingdom_api(tmp_path) -> None:
    with make_client(tmp_path) as client:
        client.post(
            "/api/admin/world/generate-continent",
            json={"seed": "border-policy-api", "name": "Eldara"},
            headers={"X-Admin-Key": "secret"},
        )
        kingdom_id = client.get("/api/kingdoms").json()[0]["id"]

        border = client.post(
            "/api/commands",
            json={"type": "kingdom.set_border_policy", "target_id": kingdom_id, "parameters": {"policy": "closed"}},
            headers={"X-Admin-Key": "secret"},
        )
        assert border.status_code == 200

        refugees = client.post(
            "/api/commands/natural",
            json={"text": f"set {kingdom_id} refugees reject", "allow_ai_fallback": False},
            headers={"X-Admin-Key": "secret"},
        )
        assert refugees.status_code == 200

        kingdom = client.get(f"/api/kingdoms/{kingdom_id}").json()
        assert kingdom["border_policy"] == "closed"
        assert kingdom["refugee_policy"] == "reject"

        world_map = client.get("/api/map").json()
        mapped = next(item for item in world_map["kingdoms"] if item["id"] == kingdom_id)
        assert mapped["border_policy"] == "closed"
        assert mapped["refugee_policy"] == "reject"
        assert "refugee_camps" in world_map


def test_refugee_camp_endpoint_exposes_rejected_population(tmp_path) -> None:
    with make_client(tmp_path) as client:
        client.post(
            "/api/admin/world/generate-continent",
            json={"seed": "camp-api", "name": "Eldara"},
            headers={"X-Admin-Key": "secret"},
        )
        runtime = client.app.state.runtime
        with runtime._lock:
            kingdom_ids = sorted(runtime.world.kingdoms)
            source_kingdom_id, opponent_id, host_kingdom_id = kingdom_ids[:3]
            source = next(s for s in runtime.world.settlements.values() if s.kingdom_id == source_kingdom_id)
            host = next(s for s in runtime.world.settlements.values() if s.kingdom_id == host_kingdom_id)

            source.food_security = 0.1
            source.stability = 0.1
            for settlement in runtime.world.settlements.values():
                if settlement.id in {source.id, host.id}:
                    continue
                settlement.food_security = 0.05
                settlement.stability = 0.05
                settlement.housing_capacity = settlement.population
            host.food_security = 0.98
            host.stability = 0.98
            host.housing_capacity = host.population + 1_000
            runtime.world.kingdoms[host_kingdom_id].border_policy = BorderPolicy.CLOSED
            runtime.world.kingdoms[host_kingdom_id].refugee_policy = RefugeePolicy.REJECT
            runtime.world.wars["war_api_camp"] = War(
                id="war_api_camp",
                attacker_kingdom_id=source_kingdom_id,
                defender_kingdom_id=opponent_id,
                goal="camp endpoint test",
                started_at=runtime.world.date.model_copy(deep=True),
            )
            before = runtime.world.total_population
            runtime.engine._migration_dynamics()
            runtime.persistence.save_world(runtime.world)
            assert runtime.world.total_population == before

        camps = client.get("/api/refugee-camps").json()
        assert camps
        matching = next(
            (
                camp for camp in camps
                if camp["host_kingdom_id"] == host_kingdom_id
                and camp["origin_kingdom_id"] == source_kingdom_id
            ),
            None,
        )
        assert matching is not None
        assert matching["people"] > 0

        continent = client.get("/api/continent").json()
        assert continent["refugee_camp_count"] >= 1
        assert continent["refugee_camp_population"] > 0
