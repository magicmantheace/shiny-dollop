from __future__ import annotations

from livingworld.continent_generation import generate_continent_world
from livingworld.domain import WorldState
from livingworld.institutions import (
    _FACTION_POLICY_PREFERENCES,
    apply_policy_conflict,
    collect_taxes_with_institutions,
    review_policies,
    run_institution_cycle,
)
from livingworld.world_engine import FinalWorldEngine


def _engine(seed: str) -> FinalWorldEngine:
    return FinalWorldEngine(generate_continent_world(seed, "Eldara"))


def _kingdom(engine: FinalWorldEngine):
    return engine.world.kingdoms[sorted(engine.world.kingdoms)[0]]


def test_institutions_initialize_with_regional_policy_compliance() -> None:
    engine = _engine("institutions-bootstrap")
    kingdom = _kingdom(engine)

    assert kingdom.institutions_initialized
    assert kingdom.laws.tax_rate == kingdom.tax_rate
    assert set(kingdom.policy_compliance) == set(kingdom.settlement_ids)
    assert all(0.15 <= value <= 0.98 for value in kingdom.policy_compliance.values())
    assert 0.0 <= kingdom.institutions.corruption <= 1.0
    assert "tax_rate" in kingdom.effective_policies

    capital = kingdom.policy_compliance[kingdom.capital_settlement_id]
    assert capital >= min(kingdom.policy_compliance.values())


def test_tax_collection_depends_on_capacity_corruption_and_compliance() -> None:
    engine = _engine("institutions-tax")
    kingdom = _kingdom(engine)
    settlements = [engine.world.settlements[sid] for sid in kingdom.settlement_ids]
    starting_wealth = {settlement.id: 2_000.0 for settlement in settlements}
    starting_treasury = 10_000.0
    kingdom.laws.tax_rate = 0.16

    for settlement in settlements:
        settlement.wealth = starting_wealth[settlement.id]
        settlement.infrastructure["roads"] = 1.0
        settlement.stability = 0.9
    kingdom.treasury = starting_treasury
    kingdom.institutions.administrative_reach = 0.92
    kingdom.institutions.tax_efficiency = 0.94
    kingdom.institutions.record_keeping = 0.90
    kingdom.institutions.communication_quality = 0.90
    kingdom.institutions.enforcement_capability = 0.86
    kingdom.institutions.local_autonomy = 0.10
    kingdom.institutions.corruption = 0.05
    collect_taxes_with_institutions(engine)
    strong_revenue = kingdom.institutional_revenue_last_month

    for settlement in settlements:
        settlement.wealth = starting_wealth[settlement.id]
        settlement.infrastructure["roads"] = 0.1
        settlement.stability = 0.4
    kingdom.treasury = starting_treasury
    kingdom.institutions.administrative_reach = 0.25
    kingdom.institutions.tax_efficiency = 0.30
    kingdom.institutions.record_keeping = 0.25
    kingdom.institutions.communication_quality = 0.20
    kingdom.institutions.enforcement_capability = 0.30
    kingdom.institutions.local_autonomy = 0.75
    kingdom.institutions.corruption = 0.55
    collect_taxes_with_institutions(engine)
    weak_revenue = kingdom.institutional_revenue_last_month

    assert strong_revenue > weak_revenue * 2.0
    assert weak_revenue > 0.0


def test_security_and_military_policy_create_second_order_effects() -> None:
    engine = _engine("institutions-effects")
    kingdom = _kingdom(engine)
    settlements = [engine.world.settlements[sid] for sid in kingdom.settlement_ids]
    kingdom.treasury = 100_000.0
    kingdom.laws.anti_bandit_spending = 1.0
    kingdom.laws.military_spending = 1.0
    kingdom.laws.conscription = 0.9
    kingdom.laws.grain_reserve = 0.9
    kingdom.institutions.administrative_reach = 0.9
    kingdom.institutions.enforcement_capability = 0.9
    kingdom.institutions.corruption = 0.05
    kingdom.military_readiness = 0.2
    for settlement in settlements:
        settlement.crime = 0.45
        settlement.food_security = 0.35
        settlement.infrastructure["roads"] = 0.9
        settlement.stability = 0.75

    crime_before = sum(s.crime for s in settlements)
    food_before = sum(s.food_security for s in settlements)
    readiness_before = kingdom.military_readiness
    treasury_before = kingdom.treasury

    run_institution_cycle(engine)

    assert sum(s.crime for s in settlements) < crime_before
    assert sum(s.food_security for s in settlements) > food_before
    assert kingdom.military_readiness > readiness_before
    assert kingdom.treasury < treasury_before
    assert kingdom.institutional_spending_last_month > 0.0


def test_policy_conflict_changes_faction_loyalty_and_creates_grievance() -> None:
    engine = _engine("institutions-conflict")
    kingdom = _kingdom(engine)
    faction = engine.world.political_factions[kingdom.faction_ids[0]]
    faction.loyalty = 0.70

    # Drive every policy to the extreme farthest from this faction's own preference.
    # This keeps the test valid regardless of which government/faction mix the seed
    # generates instead of assuming every kingdom contains a Merchant League.
    preferred = _FACTION_POLICY_PREFERENCES[faction.kind]
    for key, desired in preferred.items():
        if key == "tax_rate":
            choices = (0.04, 0.24)
        elif key == "trade_tariff":
            choices = (0.0, 0.20)
        else:
            choices = (0.0, 1.0)
        setattr(kingdom.laws, key, max(choices, key=lambda value: abs(value - desired)))

    before = faction.loyalty
    apply_policy_conflict(engine, kingdom)

    assert faction.loyalty < before
    assert any(grievance.startswith("Policy conflict: ") for grievance in faction.grievances)


def test_annual_policy_review_responds_to_material_pressure() -> None:
    engine = _engine("institutions-review")
    kingdom = _kingdom(engine)
    engine.world.date.year = kingdom.last_policy_review_year + 1
    engine.world.date.month = 1
    for sid in kingdom.settlement_ids:
        settlement = engine.world.settlements[sid]
        settlement.crime = 0.42
        settlement.food_security = 0.30

    anti_before = kingdom.laws.anti_bandit_spending
    grain_before = kingdom.laws.grain_reserve
    changes = review_policies(engine, kingdom)

    assert changes
    assert kingdom.laws.anti_bandit_spending >= anti_before
    assert kingdom.laws.grain_reserve >= grain_before
    assert kingdom.laws.revision == 1
    assert any(event.type == "LAW_CHANGED" for event in engine.world.recent_events)


def test_institution_state_survives_world_round_trip() -> None:
    engine = _engine("institutions-round-trip")
    kingdom = _kingdom(engine)
    kingdom.laws.trade_tariff = 0.17
    kingdom.laws.revision = 3
    kingdom.institutions.corruption = 0.37
    kingdom.institutions.record_keeping = 0.73
    kingdom.policy_compliance[kingdom.capital_settlement_id] = 0.91

    restored = WorldState.model_validate(engine.world.model_dump(mode="json"))
    loaded = restored.kingdoms[kingdom.id]

    assert loaded.laws.trade_tariff == 0.17
    assert loaded.laws.revision == 3
    assert loaded.institutions.corruption == 0.37
    assert loaded.institutions.record_keeping == 0.73
    assert loaded.policy_compliance[kingdom.capital_settlement_id] == 0.91


def test_installed_engine_cadence_runs_institutions_and_annual_review() -> None:
    engine = _engine("institutions-installed-cadence")
    kingdom = _kingdom(engine)
    initial_revision = kingdom.laws.revision
    for sid in kingdom.settlement_ids:
        settlement = engine.world.settlements[sid]
        settlement.crime = 0.42
        settlement.food_security = 0.32

    engine.advance_years(2, ignore_pause=True)

    assert kingdom.laws.revision > initial_revision
    assert kingdom.institutional_revenue_last_month >= 0.0
    assert kingdom.institutional_spending_last_month >= 0.0
    assert set(kingdom.policy_compliance) == set(kingdom.settlement_ids)
    assert all(0.0 <= value <= 1.0 for value in kingdom.policy_compliance.values())
    assert 0.0 <= kingdom.institutions.administrative_reach <= 1.0
    assert 0.0 <= kingdom.institutions.tax_efficiency <= 1.0
    assert 0.0 <= kingdom.institutions.corruption <= 1.0
    assert 0.0 <= engine.world.metrics["average_policy_compliance"] <= 1.0
    assert any(event.type == "LAW_CHANGED" for event in engine.world.recent_events)
