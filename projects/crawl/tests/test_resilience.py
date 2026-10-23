from __future__ import annotations

from livingworld.config import Settings
from livingworld.generation import generate_world
from livingworld.runtime import LivingWorldRuntime
from livingworld.world_engine import FinalWorldEngine


def test_comma_separated_cors_origins_are_supported(monkeypatch):
    monkeypatch.setenv("LIVINGWORLD_ALLOW_ORIGINS", "http://one.example,http://two.example")
    settings = Settings(_env_file=None)
    assert settings.allow_origins == ["http://one.example", "http://two.example"]


def test_century_keeps_named_generations_alive():
    world = generate_world("century-resilience", "Century World")
    engine = FinalWorldEngine(world)
    engine.advance_years(100, ignore_pause=True)

    living = world.alive_npcs()
    assert 50 <= len(living) <= 300
    assert len(world.npcs) > 100
    assert all(settlement.kingdom_id in world.kingdoms for settlement in world.settlements.values())
    assert all(npc.kingdom_id in world.kingdoms for npc in living)


def test_conquest_updates_persistent_resident_allegiance():
    world = generate_world("conquest-resilience", "Conquest World")
    engine = FinalWorldEngine(world)
    attacker, defender = list(world.kingdoms.values())[:2]

    war = engine.declare_war(attacker.id, defender.id, "resilience test")
    engine._end_war(war, attacker.id, "resilience test victory")

    for settlement_id in war.occupied_settlement_ids:
        owner_id = world.settlements[settlement_id].kingdom_id
        residents = [npc for npc in world.alive_npcs() if npc.settlement_id == settlement_id]
        assert all(npc.kingdom_id == owner_id for npc in residents)


def test_snapshot_restore_never_reuses_historical_ids(tmp_path):
    runtime = LivingWorldRuntime(Settings(
        database_url=f"sqlite:///{tmp_path / 'snapshot.db'}",
        world_seed="snapshot-resilience",
        tick_seconds=3600,
    ))
    runtime.create_snapshot("early")

    runtime.engine.emit("TEST_EVENT", "An event after the snapshot.")
    runtime.world.new_entity_id("test_entity")
    high_event_sequence = runtime.world.next_event_sequence
    high_entity_sequence = runtime.world.next_entity_sequence

    runtime.restore_snapshot("early")

    assert runtime.world.next_event_sequence >= high_event_sequence
    assert runtime.world.next_entity_sequence >= high_entity_sequence
