from livingworld.continent_generation import generate_continent_world
from livingworld.persistence import Persistence
from livingworld.world_engine import FinalWorldEngine


def test_continent_target_counts_and_regions():
    world = generate_continent_world("continent-test", "Eldara")

    assert world.continent is not None
    assert world.continent.id == "continent_0001"
    assert len(world.regions) == 6
    assert len(world.kingdoms) == 6
    assert len(world.settlements) == 150
    assert world.total_population == 100_000
    assert len(world.alive_npcs()) == 500
    assert len(world.armies) == 6
    assert world.metrics["regions"] == 6

    names = [kingdom.name for kingdom in world.kingdoms.values()]
    assert len(names) == len(set(names))
    settlement_names = [settlement.name for settlement in world.settlements.values()]
    assert len(settlement_names) == len(set(settlement_names))


def test_continent_generation_is_deterministic():
    first = generate_continent_world("same-continent", "Eldara")
    second = generate_continent_world("same-continent", "Eldara")

    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_continent_references_are_valid():
    world = generate_continent_world("reference-test", "Eldara")

    assert set(world.continent.region_ids) == set(world.regions)

    for region in world.regions.values():
        assert region.kingdom_ids
        assert region.settlement_ids
        assert all(kingdom_id in world.kingdoms for kingdom_id in region.kingdom_ids)
        assert all(settlement_id in world.settlements for settlement_id in region.settlement_ids)

    for kingdom in world.kingdoms.values():
        assert kingdom.capital_settlement_id in world.settlements
        assert kingdom.ruler_npc_id in world.npcs
        assert all(settlement_id in world.settlements for settlement_id in kingdom.settlement_ids)
        assert all(army_id in world.armies for army_id in kingdom.army_ids)
        assert set(kingdom.relations) == set(world.kingdoms) - {kingdom.id}

    for settlement in world.settlements.values():
        assert settlement.kingdom_id in world.kingdoms
        assert settlement.region_id in world.regions

    for npc in world.npcs.values():
        assert npc.kingdom_id in world.kingdoms
        assert npc.settlement_id in world.settlements
        if npc.spouse_id:
            assert npc.spouse_id in world.npcs
        assert all(target in world.npcs for target in npc.relationships)

    for route in world.trade_routes.values():
        assert route.origin_settlement_id in world.settlements
        assert route.destination_settlement_id in world.settlements
        assert route.origin_settlement_id != route.destination_settlement_id
        assert route.distance > 0

    for army in world.armies.values():
        assert army.kingdom_id in world.kingdoms
        assert army.location_settlement_id in world.settlements
        assert army.commander_npc_id in world.npcs


def test_continent_persists_and_advances(tmp_path):
    world = generate_continent_world("persist-continent", "Eldara")
    persistence = Persistence(f"sqlite:///{tmp_path / 'continent.db'}")
    persistence.initialize()
    persistence.save_world(world)

    loaded = persistence.load_world()
    assert loaded is not None
    assert loaded.continent is not None
    assert len(loaded.regions) == 6
    assert loaded.total_population == 100_000

    engine = FinalWorldEngine(loaded)
    engine.advance_hours(24 * 30)

    assert loaded.date.month == 2
    assert loaded.total_population > 0
    assert len(loaded.kingdoms) >= 1
