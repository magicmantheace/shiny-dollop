from fastapi.testclient import TestClient

from livingworld.api import create_app
from livingworld.config import Settings


def make_client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        admin_key="secret",
        tick_seconds=3600,
        world_seed="api-test",
    )
    return TestClient(create_app(settings))


def test_world_and_map_are_observable(tmp_path):
    with make_client(tmp_path) as client:
        world = client.get("/api/world")
        assert world.status_code == 200
        assert world.json()["metrics"]["population"] == 10_000
        world_map = client.get("/api/map")
        assert world_map.status_code == 200
        assert len(world_map.json()["settlements"]) == 25


def test_admin_commands_require_key(tmp_path):
    with make_client(tmp_path) as client:
        command = {"type": "world.advance", "parameters": {"amount": 1, "unit": "day"}, "issuer": "test"}
        assert client.post("/api/commands", json=command).status_code == 401
        response = client.post("/api/commands", json=command, headers={"X-Admin-Key": "secret"})
        assert response.status_code == 200
        assert response.json()["status"] == "completed"


def test_natural_command_endpoint(tmp_path):
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/commands/natural",
            json={"text": "advance 1 month", "allow_ai_fallback": False},
            headers={"X-Admin-Key": "secret"},
        )
        assert response.status_code == 200
        assert response.json()["parser"] == "deterministic"
