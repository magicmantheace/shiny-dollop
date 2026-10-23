from livingworld.simulation import WorldEngine


def test_world_clock_advances(world):
    engine = WorldEngine(world)
    engine.advance_days(31)
    assert world.date.month == 2
    assert world.date.day == 2


def test_daily_economy_changes_stock(world):
    engine = WorldEngine(world)
    settlement = next(iter(world.settlements.values()))
    before = settlement.resources["grain"].quantity
    engine.advance_days(1)
    assert settlement.resources["grain"].quantity != before


def test_kingdom_decisions_are_explainable(world):
    engine = WorldEngine(world)
    kingdom = next(iter(world.kingdoms.values()))
    decision = engine._kingdom_decision(kingdom)
    assert decision.action
    assert decision.reasons
    assert decision.score == kingdom.last_decision.score


def test_war_produces_history(world):
    events = []
    engine = WorldEngine(world, events.append)
    kingdoms = list(world.kingdoms)
    war = engine.declare_war(kingdoms[0], kingdoms[1], "test border claim")
    assert war.id in world.wars
    assert any(event.type == "WAR_DECLARED" for event in events)


def test_ruler_death_can_trigger_succession(world):
    events = []
    engine = WorldEngine(world, events.append)
    kingdom = next(iter(world.kingdoms.values()))
    old_ruler = kingdom.ruler_npc_id
    engine.kill_npc(old_ruler, "test")
    engine._succession_checks()
    assert kingdom.ruler_npc_id != old_ruler
    assert world.npcs[kingdom.ruler_npc_id].alive
    assert any(event.type == "RULER_SUCCEEDED" for event in events)
