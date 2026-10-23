from livingworld.continent_generation import generate_continent_world
from livingworld.domain import SettlementType
from livingworld.frontier import (
    abandon_frontier_settlement,
    found_frontier_settlement,
    refresh_frontier_metrics,
    territory_summary,
    update_frontiers,
)
from livingworld.world_engine import FinalWorldEngine


def _first_kingdom(world):
    return world.kingdoms[sorted(world.kingdoms)[0]]


def test_frontier_founding_conserves_population_and_creates_claim() -> None:
    world = generate_continent_world("frontier-founding", "Eldara")
    engine = FinalWorldEngine(world)
    kingdom = _first_kingdom(world)
    before_population = world.total_population
    before_settlements = len(world.settlements)
    before_source_population = {
        sid: world.settlements[sid].population for sid in kingdom.settlement_ids
    }

    settlement = found_frontier_settlement(
        engine,
        kingdom.id,
        preferred_type=SettlementType.HAMLET,
        force=True,
    )

    assert world.total_population == before_population
    assert len(world.settlements) == before_settlements + 1
    assert settlement.frontier is True
    assert settlement.type == SettlementType.HAMLET
    assert settlement.origin_settlement_id in before_source_population
    assert world.settlements[settlement.origin_settlement_id].population < before_source_population[settlement.origin_settlement_id]
    assert sum(settlement.ancestry_population.values()) == settlement.population
    assert settlement.id in world.kingdoms[kingdom.id].settlement_ids
    assert settlement.id in world.regions[settlement.region_id].settlement_ids
    claims = [claim for claim in world.territory_claims.values() if claim.get("settlement_id") == settlement.id]
    assert len(claims) == 1
    assert claims[0]["status"] in {"active", "contested"}
    assert claims[0]["control_radius"] > 0
    assert any(
        settlement.id in {route.origin_settlement_id, route.destination_settlement_id}
        for route in world.trade_routes.values()
    )
    assert any(event.type == "SETTLEMENT_FOUNDED" and settlement.id in event.subject_ids for event in world.recent_events)


def test_neighbor_pressure_contests_and_fortifies_frontier() -> None:
    world = generate_continent_world("frontier-contest", "Eldara")
    engine = FinalWorldEngine(world)
    kingdom = _first_kingdom(world)
    settlement = found_frontier_settlement(
        engine,
        kingdom.id,
        preferred_type=SettlementType.HAMLET,
        force=True,
    )
    other = next(
        item for item in world.settlements.values()
        if item.kingdom_id != kingdom.id and item.population > 0
    )
    other.position.x = settlement.position.x + 4.0
    other.position.y = settlement.position.y + 4.0
    kingdom.treasury = max(kingdom.treasury, 20_000)

    for _ in range(12):
        update_frontiers(engine)

    claim = next(claim for claim in world.territory_claims.values() if claim.get("settlement_id") == settlement.id)
    assert claim["status"] == "contested"
    assert other.kingdom_id in claim["contested_by_kingdom_ids"]
    assert settlement.infrastructure["defenses"] > 0.3
    assert settlement.type == SettlementType.FORT
    assert any(event.type == "FRONTIER_CLAIM_CONTESTED" for event in world.recent_events)
    assert any(event.type == "FRONTIER_FORTIFIED" for event in world.recent_events)


def test_frontier_abandonment_creates_ruin_without_losing_population() -> None:
    world = generate_continent_world("frontier-abandonment", "Eldara")
    engine = FinalWorldEngine(world)
    kingdom = _first_kingdom(world)
    settlement = found_frontier_settlement(engine, kingdom.id, force=True)
    before_population = world.total_population
    origin_id = settlement.origin_settlement_id
    assert origin_id is not None

    abandoned = abandon_frontier_settlement(engine, settlement.id, "validation collapse")

    assert abandoned is True
    assert world.total_population == before_population
    assert settlement.type == SettlementType.RUIN
    assert settlement.population == 0
    assert settlement.abandoned_year == world.date.year
    assert settlement.id not in world.kingdoms[kingdom.id].settlement_ids
    assert world.settlements[origin_id].population > 0
    claim = next(claim for claim in world.territory_claims.values() if claim.get("settlement_id") == settlement.id)
    assert claim["status"] == "abandoned"
    assert claim["strength"] == 0.0
    assert all(
        not route.active
        for route in world.trade_routes.values()
        if settlement.id in {route.origin_settlement_id, route.destination_settlement_id}
    )
    assert any(event.type == "SETTLEMENT_ABANDONED" and settlement.id in event.subject_ids for event in world.recent_events)


def test_frontier_metrics_and_territory_summary() -> None:
    world = generate_continent_world("frontier-summary", "Eldara")
    engine = FinalWorldEngine(world)
    kingdom = _first_kingdom(world)
    found_frontier_settlement(engine, kingdom.id, preferred_type=SettlementType.FORT, force=True)
    refresh_frontier_metrics(world)
    summary = territory_summary(world)
    kingdom_summary = next(item for item in summary if item["kingdom_id"] == kingdom.id)

    assert world.metrics["active_frontier_claims"] >= 1
    assert world.metrics["frontier_settlements"] >= 1
    assert world.metrics["frontier_forts"] >= 1
    assert kingdom_summary["active_claims"] >= 1
    assert kingdom_summary["estimated_control_area"] > 0
