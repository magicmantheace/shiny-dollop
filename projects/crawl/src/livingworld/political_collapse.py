from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .advanced_simulation import LivingWorldEngine
from .domain import GovernmentType, Kingdom, NPC, PoliticalFaction, PoliticalFactionType
from .politics import initialize_kingdom_politics, install_ruler, refresh_offices

if TYPE_CHECKING:
    from .domain import WorldState


CollapseOutcome = Literal["none", "regime_overthrow", "regional_secession", "civil_war"]

CRISIS_LEGITIMACY_THRESHOLD = 0.30
CRISIS_FACTION_LOYALTY_THRESHOLD = 0.46
CRISIS_MONTHS_REQUIRED = 12
FORCED_RESOLUTION_MONTHS = 36
RESOLUTION_COOLDOWN_YEARS = 4


@dataclass(frozen=True)
class PoliticalCollapseAssessment:
    kingdom_id: str
    outcome: CollapseOutcome
    eligible: bool
    pressure: float
    crisis_months: int
    faction_id: str | None = None
    settlement_id: str | None = None
    trigger_chance: float = 0.0
    forced: bool = False
    blockers: tuple[str, ...] = ()


def _active_factions(world: WorldState, kingdom: Kingdom) -> list[PoliticalFaction]:
    return [
        world.political_factions[faction_id]
        for faction_id in kingdom.faction_ids
        if faction_id in world.political_factions
        and world.political_factions[faction_id].active
    ]


def _opposition_faction(world: WorldState, kingdom: Kingdom) -> PoliticalFaction | None:
    factions = _active_factions(world, kingdom)
    if not factions:
        return None
    return max(
        factions,
        key=lambda faction: (
            faction.influence * (1.0 - faction.loyalty)
            + min(0.20, len(faction.grievances) * 0.04),
            faction.id,
        ),
    )


def _collapse_pressure(kingdom: Kingdom, faction: PoliticalFaction | None) -> float:
    if not faction:
        return 0.0
    pressure = (1.0 - kingdom.legitimacy) * 0.50
    pressure += (1.0 - kingdom.stability) * 0.20
    pressure += (1.0 - faction.loyalty) * 0.20
    pressure += min(0.10, len(faction.grievances) * 0.025)
    return max(0.0, min(1.0, pressure))


def _regional_candidate(world: WorldState, kingdom: Kingdom, faction: PoliticalFaction) -> str | None:
    base_id = faction.regional_base_settlement_id
    if (
        base_id
        and base_id in kingdom.settlement_ids
        and base_id != kingdom.capital_settlement_id
        and base_id in world.settlements
    ):
        return base_id

    candidates = [
        world.settlements[settlement_id]
        for settlement_id in kingdom.settlement_ids
        if settlement_id in world.settlements
        and settlement_id != kingdom.capital_settlement_id
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda settlement: (
            settlement.stability,
            settlement.food_security,
            settlement.id,
        ),
    ).id


def _kingdom_in_active_war(world: WorldState, kingdom_id: str) -> bool:
    return any(
        kingdom_id in {war.attacker_kingdom_id, war.defender_kingdom_id}
        for war in world.active_wars()
    )


def update_political_crisis_state(engine: LivingWorldEngine, kingdom: Kingdom) -> None:
    faction = _opposition_faction(engine.world, kingdom)
    prior = kingdom.political_crisis_months
    crisis_now = bool(
        faction
        and kingdom.legitimacy < CRISIS_LEGITIMACY_THRESHOLD
        and (
            faction.loyalty < CRISIS_FACTION_LOYALTY_THRESHOLD
            or len(faction.grievances) >= 2
        )
    )

    if crisis_now:
        kingdom.political_crisis_months = min(240, prior + 1)
        if kingdom.political_crisis_months == CRISIS_MONTHS_REQUIRED:
            engine.emit(
                "POLITICAL_CRISIS",
                f"A sustained crisis of legitimacy took hold in {kingdom.name}.",
                [kingdom.id] + ([faction.id] if faction else []),
                kingdom.capital_settlement_id,
                data={
                    "legitimacy": kingdom.legitimacy,
                    "faction_loyalty": faction.loyalty if faction else None,
                    "grievances": list(faction.grievances) if faction else [],
                    "crisis_months": kingdom.political_crisis_months,
                },
                importance=0.82,
            )
        return

    decay = 2 if kingdom.legitimacy >= 0.45 else 1
    kingdom.political_crisis_months = max(0, prior - decay)
    if prior >= CRISIS_MONTHS_REQUIRED and kingdom.political_crisis_months == 0:
        engine.emit(
            "POLITICAL_CRISIS_EASED",
            f"The political crisis in {kingdom.name} finally eased.",
            [kingdom.id],
            kingdom.capital_settlement_id,
            importance=0.58,
        )


def assess_political_collapse(world: WorldState, kingdom: Kingdom) -> PoliticalCollapseAssessment:
    faction = _opposition_faction(world, kingdom)
    pressure = _collapse_pressure(kingdom, faction)
    blockers: list[str] = []

    if not faction:
        blockers.append("no_active_faction")
    if kingdom.political_crisis_months < CRISIS_MONTHS_REQUIRED:
        blockers.append("crisis_not_sustained")
    if pressure < 0.62 and kingdom.legitimacy > 0.10:
        blockers.append("pressure_below_threshold")
    if (
        kingdom.last_political_resolution_year is not None
        and world.date.year - kingdom.last_political_resolution_year < RESOLUTION_COOLDOWN_YEARS
    ):
        blockers.append("resolution_cooldown")

    if blockers or not faction:
        return PoliticalCollapseAssessment(
            kingdom_id=kingdom.id,
            outcome="none",
            eligible=False,
            pressure=pressure,
            crisis_months=kingdom.political_crisis_months,
            faction_id=faction.id if faction else None,
            blockers=tuple(blockers),
        )

    settlement_id = _regional_candidate(world, kingdom, faction)
    forced = bool(
        kingdom.political_crisis_months >= FORCED_RESOLUTION_MONTHS
        or kingdom.legitimacy <= 0.04
    )

    regional_base_is_real = bool(
        faction.regional_base_settlement_id
        and faction.regional_base_settlement_id in kingdom.settlement_ids
        and faction.regional_base_settlement_id != kingdom.capital_settlement_id
    )
    regional_bloc = bool(
        regional_base_is_real
        or faction.kind in {
            PoliticalFactionType.FRONTIER,
            PoliticalFactionType.MERCHANTS,
            PoliticalFactionType.GUILDS,
        }
    )
    national_overthrow_bloc = faction.kind in {
        PoliticalFactionType.MILITARY,
        PoliticalFactionType.PRIESTHOOD,
        PoliticalFactionType.NOBILITY,
        PoliticalFactionType.COMMONERS,
    }

    if len(kingdom.settlement_ids) <= 1 or settlement_id is None:
        outcome: CollapseOutcome = "regime_overthrow"
    elif national_overthrow_bloc and not regional_base_is_real:
        outcome = "regime_overthrow"
    elif not regional_bloc and (
        kingdom.legitimacy <= 0.16 or kingdom.political_crisis_months >= 24
    ):
        outcome = "regime_overthrow"
    elif (
        not _kingdom_in_active_war(world, kingdom.id)
        and (
            pressure >= 0.80
            or kingdom.legitimacy <= 0.08
            or kingdom.political_crisis_months >= 30
        )
    ):
        outcome = "civil_war"
    else:
        outcome = "regional_secession"

    chance = 0.05
    chance += max(0.0, pressure - 0.62) * 0.65
    chance += max(0, kingdom.political_crisis_months - CRISIS_MONTHS_REQUIRED) * 0.003
    chance = max(0.05, min(0.40, chance))

    return PoliticalCollapseAssessment(
        kingdom_id=kingdom.id,
        outcome=outcome,
        eligible=True,
        pressure=pressure,
        crisis_months=kingdom.political_crisis_months,
        faction_id=faction.id,
        settlement_id=settlement_id if outcome != "regime_overthrow" else None,
        trigger_chance=chance,
        forced=forced,
    )


def _opposition_successor(
    engine: LivingWorldEngine,
    kingdom: Kingdom,
    faction: PoliticalFaction,
) -> NPC | None:
    current_id = kingdom.ruler_npc_id
    preferred_ids = [faction.leader_npc_id, *faction.member_npc_ids]
    preferred: list[NPC] = []
    seen: set[str] = set()
    for npc_id in preferred_ids:
        if not npc_id or npc_id in seen:
            continue
        seen.add(npc_id)
        npc = engine.world.npcs.get(npc_id)
        if (
            npc
            and npc.alive
            and npc.age >= 18
            and npc.kingdom_id == kingdom.id
            and npc.id != current_id
        ):
            preferred.append(npc)

    candidates = preferred or [
        npc
        for npc in engine.world.npcs.values()
        if npc.alive
        and npc.age >= 18
        and npc.kingdom_id == kingdom.id
        and npc.id != current_id
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda npc: (
            npc.traits.get("ambition", 0.5) * 0.45
            + npc.values.get("status", 0.5) * 0.25
            + npc.traits.get("courage", 0.5) * 0.15
            + npc.traits.get("empathy", 0.5) * 0.15,
            npc.id,
        ),
    )


def _government_after_overthrow(
    current: GovernmentType,
    faction: PoliticalFaction,
) -> GovernmentType:
    preferred = {
        PoliticalFactionType.MILITARY: GovernmentType.MILITARY_REGIME,
        PoliticalFactionType.PRIESTHOOD: GovernmentType.THEOCRACY,
        PoliticalFactionType.MERCHANTS: GovernmentType.MERCHANT_OLIGARCHY,
        PoliticalFactionType.GUILDS: GovernmentType.COUNCIL,
        PoliticalFactionType.COMMONERS: GovernmentType.COUNCIL,
        PoliticalFactionType.FRONTIER: GovernmentType.CLAN_CONFEDERACY,
        PoliticalFactionType.NOBILITY: GovernmentType.ELECTIVE_MONARCHY,
    }[faction.kind]
    return current if current == preferred else preferred


def _resolve_regime_overthrow(
    engine: LivingWorldEngine,
    kingdom: Kingdom,
    faction: PoliticalFaction,
    assessment: PoliticalCollapseAssessment,
) -> bool:
    prior_ruler = engine.world.npcs.get(kingdom.ruler_npc_id or "")
    successor = _opposition_successor(engine, kingdom, faction)
    if not successor:
        return False

    old_government = kingdom.government
    new_government = _government_after_overthrow(old_government, faction)
    kingdom.government = new_government
    method = {
        PoliticalFactionType.MILITARY: "officer revolt",
        PoliticalFactionType.PRIESTHOOD: "clerical overthrow",
        PoliticalFactionType.MERCHANTS: "oligarchic revolt",
        PoliticalFactionType.GUILDS: "guild uprising",
        PoliticalFactionType.COMMONERS: "popular uprising",
        PoliticalFactionType.FRONTIER: "clan revolt",
        PoliticalFactionType.NOBILITY: "palace revolt",
    }[faction.kind]

    install_ruler(
        engine,
        kingdom,
        successor,
        prior_ruler,
        method=method,
        succession=False,
    )
    refresh_offices(engine, kingdom, emit_changes=False)
    kingdom.stability = max(0.28, kingdom.stability - 0.06)

    engine.emit(
        "REGIME_OVERTHROWN",
        f"The {faction.name} overthrew the old regime of {kingdom.name} after a prolonged legitimacy crisis.",
        [kingdom.id, faction.id, successor.id]
        + ([prior_ruler.id] if prior_ruler else []),
        kingdom.capital_settlement_id,
        data={
            "pressure": assessment.pressure,
            "crisis_months": assessment.crisis_months,
            "old_government": old_government.value,
            "new_government": new_government.value,
            "successor_id": successor.id,
        },
        importance=0.96,
    )
    if new_government != old_government:
        engine.emit(
            "GOVERNMENT_REFORMED",
            f"{kingdom.name} reorganized as a {new_government.value.replace('_', ' ')} after the overthrow.",
            [kingdom.id, faction.id],
            kingdom.capital_settlement_id,
            data={
                "old_government": old_government.value,
                "new_government": new_government.value,
            },
            importance=0.88,
        )
    return True


def _resolve_breakaway(
    engine: LivingWorldEngine,
    kingdom: Kingdom,
    faction: PoliticalFaction,
    assessment: PoliticalCollapseAssessment,
) -> bool:
    settlement_id = assessment.settlement_id
    if not settlement_id or settlement_id not in kingdom.settlement_ids:
        return False

    new = engine._found_breakaway_kingdom(
        kingdom,
        settlement_id,
        engine._rng(f"collapse-breakaway:{kingdom.id}:{faction.id}"),
    )
    engine._reconcile_parent_factions_after_secession(kingdom, settlement_id)
    initialize_kingdom_politics(engine, new)
    settlement_name = engine.world.settlements[settlement_id].name

    event_type = "CIVIL_WAR_STARTED" if assessment.outcome == "civil_war" else "REGIONAL_SECESSION"
    summary = (
        f"The {faction.name} broke {settlement_name} from {kingdom.name}, beginning an independence civil war."
        if assessment.outcome == "civil_war"
        else f"The {faction.name} broke {settlement_name} away from {kingdom.name} after a prolonged political crisis."
    )
    engine.emit(
        event_type,
        summary,
        [kingdom.id, new.id, faction.id, settlement_id],
        settlement_id,
        data={
            "pressure": assessment.pressure,
            "crisis_months": assessment.crisis_months,
            "parent_kingdom_id": kingdom.id,
            "new_kingdom_id": new.id,
            "faction_id": faction.id,
        },
        importance=0.98 if assessment.outcome == "civil_war" else 0.94,
    )
    engine.emit(
        "FACTION_REBELLION",
        f"The {faction.name} turned its grievances into open rebellion against {kingdom.name}.",
        [kingdom.id, new.id, faction.id, settlement_id],
        settlement_id,
        data={
            "faction_id": faction.id,
            "parent_kingdom_id": kingdom.id,
            "new_kingdom_id": new.id,
            "grievances": list(faction.grievances),
            "resolution": assessment.outcome,
        },
        importance=0.94,
    )

    if assessment.outcome == "civil_war":
        engine.declare_war(
            new.id,
            kingdom.id,
            "war of independence",
            source="political_crisis",
        )
    return True


def resolve_political_collapse(
    engine: LivingWorldEngine,
    kingdom: Kingdom,
    assessment: PoliticalCollapseAssessment,
) -> bool:
    if not assessment.eligible or assessment.outcome == "none" or not assessment.faction_id:
        return False
    faction = engine.world.political_factions.get(assessment.faction_id)
    if not faction or not faction.active or faction.kingdom_id != kingdom.id:
        return False

    resolved = False
    if assessment.outcome == "regime_overthrow":
        resolved = _resolve_regime_overthrow(engine, kingdom, faction, assessment)
    elif assessment.outcome in {"regional_secession", "civil_war"}:
        resolved = _resolve_breakaway(engine, kingdom, faction, assessment)

    if resolved:
        kingdom.political_crisis_months = 0
        kingdom.last_political_resolution_year = engine.world.date.year
        kingdom.last_political_resolution = assessment.outcome
    return resolved


def _political_fragility_with_collapse(self: LivingWorldEngine) -> None:
    for kingdom in list(self.world.kingdoms.values()):
        if kingdom.id not in self.world.kingdoms:
            continue
        update_political_crisis_state(self, kingdom)
        assessment = assess_political_collapse(self.world, kingdom)
        if not assessment.eligible:
            continue

        should_resolve = assessment.forced
        if not should_resolve:
            rng = self._rng(
                f"political-collapse:{kingdom.id}:{assessment.faction_id}:{assessment.outcome}"
            )
            should_resolve = rng.random() < assessment.trigger_chance
        if not should_resolve:
            continue
        resolve_political_collapse(self, kingdom, assessment)


def collapse_diagnostics(world: WorldState) -> dict[str, float | int]:
    assessments = [assess_political_collapse(world, kingdom) for kingdom in world.kingdoms.values()]
    return {
        "political_crisis_kingdoms": sum(
            1 for kingdom in world.kingdoms.values()
            if kingdom.political_crisis_months >= CRISIS_MONTHS_REQUIRED
        ),
        "max_political_crisis_months": max(
            (kingdom.political_crisis_months for kingdom in world.kingdoms.values()),
            default=0,
        ),
        "collapse_eligible_kingdoms": sum(1 for item in assessments if item.eligible),
        "regime_overthrow_eligible": sum(
            1 for item in assessments if item.eligible and item.outcome == "regime_overthrow"
        ),
        "regional_secession_eligible": sum(
            1 for item in assessments if item.eligible and item.outcome == "regional_secession"
        ),
        "civil_war_eligible": sum(
            1 for item in assessments if item.eligible and item.outcome == "civil_war"
        ),
        "max_collapse_pressure": max((item.pressure for item in assessments), default=0.0),
    }


def install_political_collapse_model() -> None:
    """Replace Slice 1A's secession-only fragility hook with Slice 1C resolution."""
    LivingWorldEngine._political_fragility = _political_fragility_with_collapse
