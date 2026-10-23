from livingworld.continent_generation import generate_continent_world
from livingworld.domain import BorderPolicy, RefugeePolicy, War
from livingworld.world_engine import FinalWorldEngine


def _prepare_cross_border_refugee_case(seed: str):
    world = generate_continent_world(seed, "Eldara")
    kingdom_ids = sorted(world.kingdoms)
    source_kingdom_id, war_opponent_id, host_kingdom_id = kingdom_ids[:3]
    source = next(s for s in world.settlements.values() if s.kingdom_id == source_kingdom_id)
    host = next(s for s in world.settlements.values() if s.kingdom_id == host_kingdom_id)

    source.food_security = 0.12
    source.stability = 0.16
    source.housing_capacity = max(source.population, source.housing_capacity)

    for settlement in world.settlements.values():
        if settlement.id in {source.id, host.id}:
            continue
        settlement.food_security = 0.08
        settlement.stability = 0.08
        settlement.housing_capacity = settlement.population

    host.food_security = 0.98
    host.stability = 0.96
    host.health = 0.96
    host.housing_capacity = host.population + 1_000

    war = War(
        id="war_border_policy_test",
        attacker_kingdom_id=source_kingdom_id,
        defender_kingdom_id=war_opponent_id,
        goal="forced displacement test",
        started_at=world.date.model_copy(deep=True),
    )
    world.wars[war.id] = war
    return world, source, host


def test_closed_rejecting_border_creates_camp_without_losing_population() -> None:
    world, source, host = _prepare_cross_border_refugee_case("closed-border")
    host_kingdom = world.kingdoms[host.kingdom_id]
    host_kingdom.border_policy = BorderPolicy.CLOSED
    host_kingdom.refugee_policy = RefugeePolicy.REJECT

    before_total = world.total_population
    before_host_population = host.population
    engine = FinalWorldEngine(world)
    engine._migration_dynamics()

    camps = [camp for camp in world.refugee_camps.values() if camp.host_settlement_id == host.id]
    assert camps
    camp = camps[0]
    assert camp.people > 0
    assert host.population == before_host_population
    assert world.total_population == before_total
    assert sum(camp.ancestry_population.values()) == camp.people
    assert world.metrics["refugees_rejected_last_month"] > 0

    movement = next(event for event in world.recent_events if event.type == "REFUGEE_MOVEMENT")
    assert movement.data["camped_people"] == movement.data["people"]
    assert movement.data["accepted_people"] == 0
    assert movement.data["camp_id"] == camp.id
    assert any(event.type == "BORDER_REJECTION" for event in world.recent_events)

    relation = world.kingdoms[source.kingdom_id].relations[host.kingdom_id]
    assert any("Refugees denied entry" in grievance for grievance in relation.grievances)


def test_open_welcoming_border_admits_refugees_without_camp() -> None:
    world, _, host = _prepare_cross_border_refugee_case("open-border")
    host_kingdom = world.kingdoms[host.kingdom_id]
    host_kingdom.border_policy = BorderPolicy.OPEN
    host_kingdom.refugee_policy = RefugeePolicy.WELCOME

    before_total = world.total_population
    before_host_population = host.population
    engine = FinalWorldEngine(world)
    engine._migration_dynamics()

    assert world.total_population == before_total
    assert host.population > before_host_population
    assert not world.refugee_camps
    assert world.metrics["refugees_accepted_last_month"] > 0
    movement = next(event for event in world.recent_events if event.type == "REFUGEE_MOVEMENT")
    assert movement.data["accepted_people"] == movement.data["people"]
    assert movement.data["camped_people"] == 0
    assert any(event.type == "REFUGEE_ACCEPTED" for event in world.recent_events)


def test_camp_consumes_resources_and_resettles_when_policy_opens() -> None:
    world, _, host = _prepare_cross_border_refugee_case("camp-resettle")
    host_kingdom = world.kingdoms[host.kingdom_id]
    host_kingdom.border_policy = BorderPolicy.CLOSED
    host_kingdom.refugee_policy = RefugeePolicy.REJECT
    engine = FinalWorldEngine(world)
    engine._migration_dynamics()

    camp = next(iter(world.refugee_camps.values()))
    before_total = world.total_population
    before_camp = camp.people
    before_host_population = host.population
    grain = host.resources.get("grain")
    before_grain = grain.quantity if grain else 0.0

    host_kingdom.border_policy = BorderPolicy.OPEN
    host_kingdom.refugee_policy = RefugeePolicy.WELCOME
    engine._refugee_camp_dynamics()

    assert world.total_population == before_total
    assert camp.people < before_camp
    assert host.population > before_host_population
    if grain:
        assert grain.quantity < before_grain
    assert any(event.type == "REFUGEE_RESETTLED" for event in world.recent_events)


def test_policy_natural_commands_parse() -> None:
    from livingworld.commands import parse_basic_command

    border = parse_basic_command("set kingdom_0001 border controlled")
    assert border is not None
    assert border.type == "kingdom.set_border_policy"
    assert border.parameters["policy"] == "controlled"

    refugees = parse_basic_command("set kingdom_0001 refugees welcome")
    assert refugees is not None
    assert refugees.type == "kingdom.set_refugee_policy"
    assert refugees.parameters["policy"] == "welcome"
