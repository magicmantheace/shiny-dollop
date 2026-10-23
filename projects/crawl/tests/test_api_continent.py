from fastapi.testclient import TestClient

from livingworld.api import create_app
from livingworld.config import Settings


def make_client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'continent-api.db'}",
        admin_key="secret",
        tick_seconds=3600,
        world_seed="continent-api-test",
    )
    return TestClient(create_app(settings))


def test_generate_continent_and_read_region_map_endpoints(tmp_path) -> None:
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/admin/world/generate-continent",
            json={"seed": "continent-api", "name": "Eldara"},
            headers={"X-Admin-Key": "secret"},
        )
        assert response.status_code == 200
        assert response.json()["regions"] == 6

        continent = client.get("/api/continent")
        assert continent.status_code == 200
        assert continent.json()["population"] == 100_000
        assert continent.json()["region_count"] == 6
        assert continent.json()["settlement_count"] == 150

        regions = client.get("/api/regions")
        assert regions.status_code == 200
        assert len(regions.json()) == 6
        assert sum(region["population"] for region in regions.json()) == 100_000

        world_map = client.get("/api/map")
        assert world_map.status_code == 200
        payload = world_map.json()
        assert payload["continent"]["id"] == "continent_0001"
        assert payload["bounds"] == {"min_x": 0.0, "max_x": 200.0, "min_y": 0.0, "max_y": 300.0}
        assert len(payload["regions"]) == 6
        assert len(payload["settlements"]) == 150
        assert all(settlement["region_id"] for settlement in payload["settlements"])


def test_migration_endpoint_returns_structured_events(tmp_path) -> None:
    with make_client(tmp_path) as client:
        client.post(
            "/api/admin/world/generate-continent",
            json={"seed": "migration-api", "name": "Eldara"},
            headers={"X-Admin-Key": "secret"},
        )
        runtime = client.app.state.runtime
        with runtime._lock:
            source = next(iter(runtime.world.settlements.values()))
            source.food_security = 0.05
            source.stability = 0.12
            for destination in runtime.world.settlements.values():
                if destination.id == source.id:
                    continue
                destination.food_security = max(destination.food_security, 0.92)
                destination.stability = max(destination.stability, 0.9)
                destination.housing_capacity = max(destination.housing_capacity, destination.population + 500)
            runtime.engine._migration_dynamics()
            runtime.persistence.save_world(runtime.world)

        migrations = client.get("/api/migrations?limit=20")
        assert migrations.status_code == 200
        payload = migrations.json()
        assert payload
        assert payload[0]["type"] in {"MIGRATION", "REFUGEE_MOVEMENT"}
        assert payload[0]["data"]["people"] > 0
        assert payload[0]["data"]["origin_region_id"]
        assert payload[0]["data"]["destination_region_id"]
