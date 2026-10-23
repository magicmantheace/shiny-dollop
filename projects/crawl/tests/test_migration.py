from livingworld.continent_generation import generate_continent_world
from livingworld.domain import War
from livingworld.world_engine import FinalWorldEngine


def _make_destination_capacity(world, source_id: str) -> None:
    for settlement in world.settlements.values():
        if settlement.id == source_id:
            continue
        settlement.food_security = max(0.92, settlement.food_security)
        settlement.stability = max(0.9, settlement.stability)
        settlement.health = max(0.9, settlement.health)
        settlement.housing_capacity = max(settlement.housing_capacity, settlement.population + 800)


def test_migration_conserves_population_and_ancestry() -> None:
    world = generate_continent_world("migration-test", "Eldara")
    source = next(iter(world.settlements.values()))
    source.food_security = 0.08
    source.stability = 0.18
    _make_destination_capacity(world, source.id)

    before_total = world.total_population
    before_source = source.population
    engine = FinalWorldEngine(world)
    engine._migration_dynamics()

    assert world.total_population == before_total
    assert source.population < before_source
    assert world.metrics["migration_last_month"] > 0
    assert any(event.type == "MIGRATION" for event in world.recent_events)
    for settlement in world.settlements.values():
        assert sum(settlement.ancestry_population.values()) == settlement.population


def test_war_creates_refugee_movements_with_structured_route_data() -> None:
    world = generate_continent_world("refugee-test", "Eldara")
    kingdom_ids = sorted(world.kingdoms)
    attacker_id, defender_id = kingdom_ids[:2]
    source = next(
        settlement for settlement in world.settlements.values()
        if settlement.kingdom_id == attacker_id
    )
    source.food_security = 0.42
    source.stability = 0.42
    _make_destination_capacity(world, source.id)

    war = War(
        id="war_refugee_test",
        attacker_kingdom_id=attacker_id,
        defender_kingdom_id=defender_id,
        goal="border dispute",
        started_at=world.date.model_copy(deep=True),
    )
    world.wars[war.id] = war

    before_total = world.total_population
    engine = FinalWorldEngine(world)
    engine._migration_dynamics()

    refugees = [event for event in world.recent_events if event.type == "REFUGEE_MOVEMENT"]
    assert refugees
    assert world.total_population == before_total
    assert world.metrics["refugees_last_month"] > 0

    event = refugees[0]
    assert event.data["refugee"] is True
    assert event.data["reason"] == "war"
    assert event.data["people"] > 0
    assert event.data["origin_region_id"] in world.regions
    assert event.data["destination_region_id"] in world.regions
    assert event.data["origin_settlement_id"] in world.settlements
    assert event.data["destination_settlement_id"] in world.settlements

    for npc_id in event.data["persistent_npc_ids"]:
        npc = world.npcs[npc_id]
        destination = world.settlements[event.data["destination_settlement_id"]]
        assert npc.settlement_id == destination.id
        assert npc.kingdom_id == destination.kingdom_id


def test_monthly_cycle_records_migration_metrics() -> None:
    world = generate_continent_world("monthly-migration", "Eldara")
    source = next(iter(world.settlements.values()))
    source.food_security = 0.05
    source.stability = 0.12
    _make_destination_capacity(world, source.id)

    engine = FinalWorldEngine(world)
    engine.advance_months(1)

    assert "migration_last_month" in world.metrics
    assert "refugees_last_month" in world.metrics
    assert "migration_flows_last_month" in world.metrics
