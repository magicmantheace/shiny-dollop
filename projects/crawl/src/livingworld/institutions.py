from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .advanced_simulation import LivingWorldEngine
from .domain import GovernmentType, InstitutionalCapacity, Kingdom, LawPolicy, PoliticalFactionType

if TYPE_CHECKING:
    from .domain import PoliticalFaction


MIN_POLICY_VALUE = 0.0
MAX_POLICY_VALUE = 1.0
MIN_TAX_RATE = 0.04
MAX_TAX_RATE = 0.24


_INSTITUTION_TEMPLATES: dict[GovernmentType, dict[str, float]] = {
    GovernmentType.MONARCHY: {
        "administrative_reach": 0.62,
        "tax_efficiency": 0.66,
        "corruption": 0.22,
        "record_keeping": 0.58,
        "communication_quality": 0.52,
        "local_autonomy": 0.32,
        "enforcement_capability": 0.60,
    },
    GovernmentType.ELECTIVE_MONARCHY: {
        "administrative_reach": 0.60,
        "tax_efficiency": 0.63,
        "corruption": 0.19,
        "record_keeping": 0.61,
        "communication_quality": 0.55,
        "local_autonomy": 0.38,
        "enforcement_capability": 0.57,
    },
    GovernmentType.COUNCIL: {
        "administrative_reach": 0.58,
        "tax_efficiency": 0.61,
        "corruption": 0.14,
        "record_keeping": 0.68,
        "communication_quality": 0.62,
        "local_autonomy": 0.47,
        "enforcement_capability": 0.52,
    },
    GovernmentType.CLAN_CONFEDERACY: {
        "administrative_reach": 0.40,
        "tax_efficiency": 0.45,
        "corruption": 0.16,
        "record_keeping": 0.35,
        "communication_quality": 0.38,
        "local_autonomy": 0.72,
        "enforcement_capability": 0.48,
    },
    GovernmentType.THEOCRACY: {
        "administrative_reach": 0.66,
        "tax_efficiency": 0.65,
        "corruption": 0.17,
        "record_keeping": 0.72,
        "communication_quality": 0.57,
        "local_autonomy": 0.25,
        "enforcement_capability": 0.64,
    },
    GovernmentType.MERCHANT_OLIGARCHY: {
        "administrative_reach": 0.70,
        "tax_efficiency": 0.78,
        "corruption": 0.18,
        "record_keeping": 0.76,
        "communication_quality": 0.72,
        "local_autonomy": 0.34,
        "enforcement_capability": 0.55,
    },
    GovernmentType.MILITARY_REGIME: {
        "administrative_reach": 0.58,
        "tax_efficiency": 0.60,
        "corruption": 0.20,
        "record_keeping": 0.52,
        "communication_quality": 0.58,
        "local_autonomy": 0.22,
        "enforcement_capability": 0.82,
    },
}


_FACTION_POLICY_PREFERENCES: dict[PoliticalFactionType, dict[str, float]] = {
    PoliticalFactionType.NOBILITY: {
        "tax_rate": 0.11,
        "conscription": 0.58,
        "religious_tolerance": 0.38,
        "guild_privileges": 0.26,
        "land_rights": 0.24,
        "inheritance_equality": 0.18,
        "trade_tariff": 0.12,
        "anti_bandit_spending": 0.48,
        "military_spending": 0.58,
        "grain_reserve": 0.30,
        "magic_regulation": 0.55,
    },
    PoliticalFactionType.MERCHANTS: {
        "tax_rate": 0.08,
        "conscription": 0.20,
        "religious_tolerance": 0.72,
        "guild_privileges": 0.82,
        "land_rights": 0.65,
        "inheritance_equality": 0.56,
        "trade_tariff": 0.03,
        "anti_bandit_spending": 0.72,
        "military_spending": 0.34,
        "grain_reserve": 0.42,
        "magic_regulation": 0.28,
    },
    PoliticalFactionType.MILITARY: {
        "tax_rate": 0.15,
        "conscription": 0.88,
        "religious_tolerance": 0.42,
        "guild_privileges": 0.32,
        "land_rights": 0.38,
        "inheritance_equality": 0.28,
        "trade_tariff": 0.10,
        "anti_bandit_spending": 0.68,
        "military_spending": 0.92,
        "grain_reserve": 0.48,
        "magic_regulation": 0.62,
    },
    PoliticalFactionType.PRIESTHOOD: {
        "tax_rate": 0.12,
        "conscription": 0.40,
        "religious_tolerance": 0.20,
        "guild_privileges": 0.34,
        "land_rights": 0.38,
        "inheritance_equality": 0.30,
        "trade_tariff": 0.10,
        "anti_bandit_spending": 0.52,
        "military_spending": 0.44,
        "grain_reserve": 0.72,
        "magic_regulation": 0.76,
    },
    PoliticalFactionType.GUILDS: {
        "tax_rate": 0.09,
        "conscription": 0.24,
        "religious_tolerance": 0.66,
        "guild_privileges": 0.90,
        "land_rights": 0.74,
        "inheritance_equality": 0.70,
        "trade_tariff": 0.05,
        "anti_bandit_spending": 0.66,
        "military_spending": 0.32,
        "grain_reserve": 0.56,
        "magic_regulation": 0.34,
    },
    PoliticalFactionType.FRONTIER: {
        "tax_rate": 0.07,
        "conscription": 0.62,
        "religious_tolerance": 0.64,
        "guild_privileges": 0.30,
        "land_rights": 0.82,
        "inheritance_equality": 0.54,
        "trade_tariff": 0.04,
        "anti_bandit_spending": 0.76,
        "military_spending": 0.64,
        "grain_reserve": 0.38,
        "magic_regulation": 0.30,
    },
    PoliticalFactionType.COMMONERS: {
        "tax_rate": 0.06,
        "conscription": 0.16,
        "religious_tolerance": 0.74,
        "guild_privileges": 0.54,
        "land_rights": 0.92,
        "inheritance_equality": 0.92,
        "trade_tariff": 0.05,
        "anti_bandit_spending": 0.82,
        "military_spending": 0.26,
        "grain_reserve": 0.90,
        "magic_regulation": 0.24,
    },
}


_NEUTRAL_IMPLEMENTATION_FIELDS = {
    "religious_tolerance",
    "guild_privileges",
    "land_rights",
    "inheritance_equality",
    "magic_regulation",
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _lerp(current: float, target: float, rate: float) -> float:
    return current + (target - current) * rate


def _kingdom_settlements(engine: LivingWorldEngine, kingdom: Kingdom):
    return [
        engine.world.settlements[sid]
        for sid in kingdom.settlement_ids
        if sid in engine.world.settlements
    ]


def initialize_kingdom_institutions(engine: LivingWorldEngine, kingdom: Kingdom) -> None:
    if kingdom.institutions_initialized:
        refresh_policy_compliance(engine, kingdom)
        return

    template = _INSTITUTION_TEMPLATES.get(
        kingdom.government,
        _INSTITUTION_TEMPLATES[GovernmentType.MONARCHY],
    )
    kingdom.institutions = InstitutionalCapacity(**template)
    culture = engine.world.cultures.get(kingdom.culture_id)
    militarism = culture.militarism if culture else 0.5
    tolerance = culture.tolerance if culture else 0.5
    trade = culture.trade_orientation if culture else 0.5
    collectivism = culture.collectivism if culture else 0.5
    magic_acceptance = culture.magic_acceptance if culture else 0.5

    conscription = _clamp(0.18 + militarism * 0.55)
    military_spending = _clamp(0.25 + militarism * 0.52)
    if kingdom.government == GovernmentType.MILITARY_REGIME:
        conscription = max(conscription, 0.72)
        military_spending = max(military_spending, 0.78)

    religious_tolerance = _clamp(0.20 + tolerance * 0.68)
    if kingdom.government == GovernmentType.THEOCRACY:
        religious_tolerance = min(religious_tolerance, 0.32)

    guild_privileges = _clamp(0.20 + trade * 0.62)
    if kingdom.government == GovernmentType.MERCHANT_OLIGARCHY:
        guild_privileges = max(guild_privileges, 0.72)

    kingdom.laws = LawPolicy(
        tax_rate=_clamp(kingdom.tax_rate, MIN_TAX_RATE, MAX_TAX_RATE),
        conscription=conscription,
        religious_tolerance=religious_tolerance,
        guild_privileges=guild_privileges,
        land_rights=_clamp(0.35 + (1.0 - collectivism) * 0.35),
        inheritance_equality=_clamp(0.28 + tolerance * 0.42),
        trade_tariff=_clamp(0.14 - trade * 0.10, 0.01, 0.18),
        anti_bandit_spending=_clamp(0.28 + kingdom.goals.get("security", 0.5) * 0.45),
        military_spending=military_spending,
        grain_reserve=_clamp(0.30 + collectivism * 0.50),
        magic_regulation=_clamp(0.78 - magic_acceptance * 0.58),
    )
    kingdom.tax_rate = kingdom.laws.tax_rate
    kingdom.institutions_initialized = True
    kingdom.last_policy_review_year = engine.world.date.year
    refresh_policy_compliance(engine, kingdom)


def ensure_institutional_society(engine: LivingWorldEngine) -> None:
    for kingdom in list(engine.world.kingdoms.values()):
        initialize_kingdom_institutions(engine, kingdom)
    refresh_institution_metrics(engine)


def settlement_policy_compliance(
    engine: LivingWorldEngine,
    kingdom: Kingdom,
    settlement_id: str,
) -> float:
    settlement = engine.world.settlements.get(settlement_id)
    capital = engine.world.settlements.get(kingdom.capital_settlement_id)
    if not settlement:
        return 0.0

    settlements = _kingdom_settlements(engine, kingdom)
    distance = 0.0
    max_distance = 1.0
    if capital:
        distance = math.hypot(
            settlement.position.x - capital.position.x,
            settlement.position.y - capital.position.y,
        )
        max_distance = max(
            1.0,
            max(
                (
                    math.hypot(
                        item.position.x - capital.position.x,
                        item.position.y - capital.position.y,
                    )
                    for item in settlements
                ),
                default=1.0,
            ),
        )
    distance_penalty = distance / max_distance
    roads = _clamp(settlement.infrastructure.get("roads", 0.5))
    inst = kingdom.institutions
    compliance = 0.12
    compliance += inst.administrative_reach * 0.23
    compliance += inst.record_keeping * 0.10
    compliance += inst.communication_quality * 0.14
    compliance += inst.enforcement_capability * 0.10
    compliance += roads * 0.13
    compliance += settlement.stability * 0.13
    compliance += (1.0 - inst.corruption) * 0.08
    compliance -= inst.local_autonomy * 0.11
    compliance -= distance_penalty * 0.16
    if settlement.id == kingdom.capital_settlement_id:
        compliance += 0.08
    return _clamp(compliance, 0.15, 0.98)


def refresh_policy_compliance(engine: LivingWorldEngine, kingdom: Kingdom) -> None:
    kingdom.policy_compliance = {
        settlement.id: settlement_policy_compliance(engine, kingdom, settlement.id)
        for settlement in _kingdom_settlements(engine, kingdom)
    }
    values = list(kingdom.policy_compliance.values())
    average = sum(values) / max(1, len(values))
    effective: dict[str, float] = {}
    for key, value in kingdom.laws.model_dump().items():
        if key == "revision":
            continue
        if key == "tax_rate":
            effective[key] = value * average
        elif key in _NEUTRAL_IMPLEMENTATION_FIELDS:
            effective[key] = 0.5 + (value - 0.5) * average
        else:
            effective[key] = value * average
    kingdom.effective_policies = effective


def collect_taxes_with_institutions(engine: LivingWorldEngine) -> None:
    for kingdom in engine.world.kingdoms.values():
        initialize_kingdom_institutions(engine, kingdom)
        refresh_policy_compliance(engine, kingdom)
        revenue = 0.0
        inst = kingdom.institutions
        collection_quality = _clamp(
            0.20
            + inst.tax_efficiency * 0.42
            + inst.record_keeping * 0.18
            + inst.administrative_reach * 0.16
            - inst.corruption * 0.18,
            0.10,
            0.98,
        )
        for sid in kingdom.settlement_ids:
            settlement = engine.world.settlements.get(sid)
            if not settlement:
                continue
            nominal = max(0.0, settlement.wealth * kingdom.laws.tax_rate * 0.025)
            compliance = kingdom.policy_compliance.get(sid, 0.5)
            collected = nominal * compliance * collection_quality
            settlement.wealth = max(0.0, settlement.wealth - collected)
            revenue += collected
        kingdom.treasury += revenue
        kingdom.institutional_revenue_last_month = revenue
        kingdom.tax_rate = kingdom.laws.tax_rate


def _evolve_institutions(engine: LivingWorldEngine, kingdom: Kingdom) -> None:
    settlements = _kingdom_settlements(engine, kingdom)
    if not settlements:
        return
    inst = kingdom.institutions
    avg_roads = sum(_clamp(s.infrastructure.get("roads", 0.5)) for s in settlements) / len(settlements)
    avg_stability = sum(s.stability for s in settlements) / len(settlements)
    treasury_per_capita = kingdom.treasury / max(1, sum(max(0, s.population) for s in settlements))

    corruption_target = _clamp(
        0.34
        - inst.record_keeping * 0.14
        - inst.enforcement_capability * 0.10
        + inst.local_autonomy * 0.06
        + (0.05 if treasury_per_capita < 0.08 else 0.0),
        0.05,
        0.62,
    )
    communication_target = _clamp(0.22 + avg_roads * 0.52 + avg_stability * 0.18)
    administration_target = _clamp(
        0.16
        + inst.record_keeping * 0.22
        + communication_target * 0.22
        + avg_stability * 0.18
        + (1.0 - corruption_target) * 0.14
        - inst.local_autonomy * 0.08
    )
    tax_target = _clamp(
        administration_target * 0.34
        + inst.record_keeping * 0.22
        + communication_target * 0.16
        + inst.enforcement_capability * 0.10
        + (1.0 - corruption_target) * 0.18
    )
    enforcement_target = _clamp(
        0.24
        + kingdom.laws.anti_bandit_spending * 0.28
        + kingdom.laws.military_spending * 0.16
        + administration_target * 0.18
        + avg_stability * 0.10
    )
    record_target = _clamp(0.28 + administration_target * 0.34 + communication_target * 0.20)

    inst.corruption = _clamp(_lerp(inst.corruption, corruption_target, 0.018))
    inst.communication_quality = _clamp(_lerp(inst.communication_quality, communication_target, 0.020))
    inst.administrative_reach = _clamp(_lerp(inst.administrative_reach, administration_target, 0.018))
    inst.tax_efficiency = _clamp(_lerp(inst.tax_efficiency, tax_target, 0.020))
    inst.enforcement_capability = _clamp(_lerp(inst.enforcement_capability, enforcement_target, 0.020))
    inst.record_keeping = _clamp(_lerp(inst.record_keeping, record_target, 0.012))


def _policy_budget(engine: LivingWorldEngine, kingdom: Kingdom) -> tuple[float, float]:
    population = sum(
        max(0, engine.world.settlements[sid].population)
        for sid in kingdom.settlement_ids
        if sid in engine.world.settlements
    )
    average_compliance = sum(kingdom.policy_compliance.values()) / max(1, len(kingdom.policy_compliance))
    anti = kingdom.laws.anti_bandit_spending * average_compliance
    military = kingdom.laws.military_spending * average_compliance
    grain = kingdom.laws.grain_reserve * average_compliance
    requested = population * (anti * 0.0015 + military * 0.0024 + grain * 0.0012)
    spent = min(kingdom.treasury, requested)
    if spent > 0:
        kingdom.treasury -= spent
    kingdom.institutional_spending_last_month = spent
    return requested, 0.0 if requested <= 0 else spent / requested


def _apply_policy_effects(engine: LivingWorldEngine, kingdom: Kingdom) -> None:
    settlements = _kingdom_settlements(engine, kingdom)
    if not settlements:
        kingdom.institutional_spending_last_month = 0.0
        return
    refresh_policy_compliance(engine, kingdom)
    _, budget_scale = _policy_budget(engine, kingdom)
    inst = kingdom.institutions

    for settlement in settlements:
        compliance = kingdom.policy_compliance.get(settlement.id, 0.5)
        anti = kingdom.laws.anti_bandit_spending * compliance * budget_scale
        crime_reduction = anti * inst.enforcement_capability * 0.012
        settlement.crime = _clamp(settlement.crime - crime_reduction)

        if settlement.food_security < 0.55 and kingdom.treasury > 0:
            reserve = kingdom.laws.grain_reserve * compliance * budget_scale
            relief = reserve * inst.administrative_reach * 0.014
            settlement.food_security = _clamp(settlement.food_security + relief)

        governance_quality = compliance * (1.0 - inst.corruption)
        stability_target = _clamp(0.48 + governance_quality * 0.32 - settlement.crime * 0.22)
        settlement.stability = _clamp(_lerp(settlement.stability, stability_target, 0.006))

    average_compliance = sum(kingdom.policy_compliance.values()) / max(1, len(kingdom.policy_compliance))
    military_effect = kingdom.laws.military_spending * average_compliance * budget_scale
    conscription_effect = kingdom.laws.conscription * average_compliance
    readiness_target = _clamp(
        0.22
        + military_effect * 0.42
        + conscription_effect * 0.27
        + inst.enforcement_capability * 0.11
    )
    kingdom.military_readiness = _clamp(_lerp(kingdom.military_readiness, readiness_target, 0.045))
    for army_id in kingdom.army_ids:
        army = engine.world.armies.get(army_id)
        if army and army.active:
            army.readiness = _clamp(_lerp(army.readiness, readiness_target, 0.018), 0.1, 1.0)

    trade_safety_target = _clamp(
        0.48
        + kingdom.laws.anti_bandit_spending * inst.enforcement_capability * 0.27
        + kingdom.laws.guild_privileges * 0.10
        - inst.corruption * 0.08
    )
    tariff_revenue = 0.0
    for route in engine.world.trade_routes.values():
        origin = engine.world.settlements.get(route.origin_settlement_id)
        destination = engine.world.settlements.get(route.destination_settlement_id)
        if not origin or not destination:
            continue
        if kingdom.id not in {origin.kingdom_id, destination.kingdom_id}:
            continue
        route.safety = _clamp(_lerp(route.safety, trade_safety_target, 0.012))
        tariff_revenue += (
            route.volume_last_day
            * kingdom.laws.trade_tariff
            * average_compliance
            * inst.tax_efficiency
            * 0.06
        )
    kingdom.treasury += tariff_revenue

    avg_food = sum(s.food_security * max(1, s.population) for s in settlements) / max(
        1, sum(max(1, s.population) for s in settlements)
    )
    reserve_support = kingdom.laws.grain_reserve * average_compliance * 0.12
    kingdom.food_reserve = _clamp(_lerp(kingdom.food_reserve, _clamp(avg_food + reserve_support), 0.035))


def _active_factions(engine: LivingWorldEngine, kingdom: Kingdom) -> list[PoliticalFaction]:
    return [
        engine.world.political_factions[faction_id]
        for faction_id in kingdom.faction_ids
        if faction_id in engine.world.political_factions
        and engine.world.political_factions[faction_id].active
    ]


def faction_policy_alignment(kingdom: Kingdom, faction: PoliticalFaction) -> tuple[float, str]:
    preferred = _FACTION_POLICY_PREFERENCES[faction.kind]
    distances: dict[str, float] = {}
    for key, desired in preferred.items():
        actual = getattr(kingdom.laws, key)
        scale = 0.16 if key in {"tax_rate", "trade_tariff"} else 1.0
        distances[key] = min(1.0, abs(actual - desired) / scale)
    worst = max(distances, key=lambda key: (distances[key], key))
    alignment = 1.0 - sum(distances.values()) / max(1, len(distances))
    return _clamp(alignment), worst


def apply_policy_conflict(engine: LivingWorldEngine, kingdom: Kingdom) -> None:
    for faction in _active_factions(engine, kingdom):
        alignment, worst = faction_policy_alignment(kingdom, faction)
        delta = (alignment - 0.55) * 0.012
        if kingdom.institutions.corruption > 0.42:
            delta -= (kingdom.institutions.corruption - 0.42) * 0.012
        faction.loyalty = _clamp(faction.loyalty + delta, 0.03, 0.94)
        prefix = "Policy conflict: "
        faction.grievances = [g for g in faction.grievances if not g.startswith(prefix)]
        if alignment < 0.48:
            faction.grievances.append(f"{prefix}{worst.replace('_', ' ')}")


def _weighted_policy_target(engine: LivingWorldEngine, kingdom: Kingdom, key: str) -> float:
    factions = _active_factions(engine, kingdom)
    total = sum(f.influence for f in factions)
    if total <= 0:
        return getattr(kingdom.laws, key)
    return sum(
        faction.influence * _FACTION_POLICY_PREFERENCES[faction.kind][key]
        for faction in factions
    ) / total


def review_policies(engine: LivingWorldEngine, kingdom: Kingdom) -> dict[str, tuple[float, float]]:
    if engine.world.date.month != 1 or engine.world.date.year <= kingdom.last_policy_review_year:
        return {}

    settlements = _kingdom_settlements(engine, kingdom)
    if not settlements:
        kingdom.last_policy_review_year = engine.world.date.year
        return {}
    avg_crime = sum(s.crime for s in settlements) / len(settlements)
    avg_food = sum(s.food_security for s in settlements) / len(settlements)
    population = sum(max(1, s.population) for s in settlements)
    treasury_per_capita = kingdom.treasury / max(1, population)
    at_war = engine._war_for_kingdom(kingdom.id) is not None

    targets = {
        key: _weighted_policy_target(engine, kingdom, key)
        for key in _FACTION_POLICY_PREFERENCES[PoliticalFactionType.NOBILITY]
    }
    targets["anti_bandit_spending"] = max(targets["anti_bandit_spending"], _clamp(0.30 + avg_crime * 1.45))
    if avg_food < 0.52:
        targets["grain_reserve"] = max(targets["grain_reserve"], _clamp(0.68 + (0.52 - avg_food)))
    if at_war:
        targets["conscription"] = max(targets["conscription"], 0.68)
        targets["military_spending"] = max(targets["military_spending"], 0.72)
    if treasury_per_capita < 0.08:
        targets["tax_rate"] = min(MAX_TAX_RATE, targets["tax_rate"] + 0.012)
        targets["military_spending"] = max(0.18, targets["military_spending"] - 0.06)

    changes: dict[str, tuple[float, float]] = {}
    for key, target in targets.items():
        old = getattr(kingdom.laws, key)
        if key == "tax_rate":
            target = _clamp(target, MIN_TAX_RATE, MAX_TAX_RATE)
            step = 0.010
        elif key == "trade_tariff":
            target = _clamp(target, 0.0, 0.20)
            step = 0.018
        else:
            target = _clamp(target)
            step = 0.055
        delta = _clamp(target - old, -step, step)
        new = old + delta
        if abs(new - old) >= 0.002:
            setattr(kingdom.laws, key, new)
            changes[key] = (old, new)

    kingdom.tax_rate = kingdom.laws.tax_rate
    kingdom.last_policy_review_year = engine.world.date.year
    if changes:
        kingdom.laws.revision += 1
        engine.emit(
            "LAW_CHANGED",
            f"The government of {kingdom.name} revised {len(changes)} standing policies after political and material pressure.",
            [kingdom.id],
            kingdom.capital_settlement_id,
            data={
                "revision": kingdom.laws.revision,
                "changes": {
                    key: {"old": round(old, 4), "new": round(new, 4)}
                    for key, (old, new) in changes.items()
                },
            },
            importance=0.48,
        )
    return changes


def run_institution_cycle(engine: LivingWorldEngine) -> None:
    ensure_institutional_society(engine)
    for kingdom in list(engine.world.kingdoms.values()):
        if kingdom.id not in engine.world.kingdoms:
            continue
        _evolve_institutions(engine, kingdom)
        refresh_policy_compliance(engine, kingdom)
        _apply_policy_effects(engine, kingdom)
        review_policies(engine, kingdom)
        refresh_policy_compliance(engine, kingdom)
        apply_policy_conflict(engine, kingdom)
    refresh_institution_metrics(engine)


def refresh_institution_metrics(engine: LivingWorldEngine) -> None:
    kingdoms = list(engine.world.kingdoms.values())
    if not kingdoms:
        return
    initialized = [k for k in kingdoms if k.institutions_initialized]
    if not initialized:
        return
    compliance_values = [
        value
        for kingdom in initialized
        for value in kingdom.policy_compliance.values()
    ]
    policy_conflict_factions = sum(
        1
        for faction in engine.world.political_factions.values()
        if faction.active
        and any(grievance.startswith("Policy conflict: ") for grievance in faction.grievances)
    )
    engine.world.metrics["average_administrative_reach"] = sum(
        k.institutions.administrative_reach for k in initialized
    ) / len(initialized)
    engine.world.metrics["average_tax_efficiency"] = sum(
        k.institutions.tax_efficiency for k in initialized
    ) / len(initialized)
    engine.world.metrics["average_institutional_corruption"] = sum(
        k.institutions.corruption for k in initialized
    ) / len(initialized)
    engine.world.metrics["average_policy_compliance"] = sum(compliance_values) / max(1, len(compliance_values))
    engine.world.metrics["policy_conflict_factions"] = float(policy_conflict_factions)
    engine.world.metrics["institutional_tax_revenue"] = sum(
        k.institutional_revenue_last_month for k in initialized
    )
    engine.world.metrics["institutional_policy_spending"] = sum(
        k.institutional_spending_last_month for k in initialized
    )


_ORIGINAL_INIT = LivingWorldEngine.__init__
_ORIGINAL_MONTHLY = LivingWorldEngine._monthly
_ORIGINAL_ADVANCE_HOURS = LivingWorldEngine.advance_hours
_INSTALLED = False


def _init_with_institutions(self: LivingWorldEngine, *args, **kwargs) -> None:
    _ORIGINAL_INIT(self, *args, **kwargs)
    ensure_institutional_society(self)


def _monthly_with_institutions(self: LivingWorldEngine) -> None:
    _ORIGINAL_MONTHLY(self)
    run_institution_cycle(self)


def _advance_hours_with_institutions(self: LivingWorldEngine, hours: int, *, ignore_pause: bool = False):
    world = _ORIGINAL_ADVANCE_HOURS(self, hours, ignore_pause=ignore_pause)
    refresh_institution_metrics(self)
    return world


def install_institution_model() -> None:
    """Install Slice 2 without replacing the deterministic political authority layer."""
    global _INSTALLED
    if _INSTALLED:
        return
    LivingWorldEngine.__init__ = _init_with_institutions
    LivingWorldEngine._collect_taxes = collect_taxes_with_institutions
    LivingWorldEngine._monthly = _monthly_with_institutions
    LivingWorldEngine.advance_hours = _advance_hours_with_institutions
    _INSTALLED = True
