from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .domain import (
    GovernmentType,
    Kingdom,
    NPC,
    PoliticalFaction,
    PoliticalFactionType,
    PoliticalOffice,
    PoliticalOfficeType,
)

if TYPE_CHECKING:
    from .world_engine import FinalWorldEngine


@dataclass(frozen=True)
class FactionTemplate:
    kind: PoliticalFactionType
    label: str
    preferred_goals: dict[str, float]
    preferred_tax_rate: float
    preferred_border_open: float
    preferred_refugee_open: float


FACTION_TEMPLATES: dict[PoliticalFactionType, FactionTemplate] = {
    PoliticalFactionType.NOBILITY: FactionTemplate(
        PoliticalFactionType.NOBILITY,
        "Landed Nobility",
        {"food": 0.55, "wealth": 0.70, "security": 0.72, "expansion": 0.58, "stability": 0.92},
        0.13,
        0.42,
        0.28,
    ),
    PoliticalFactionType.MERCHANTS: FactionTemplate(
        PoliticalFactionType.MERCHANTS,
        "Merchant League",
        {"food": 0.70, "wealth": 0.96, "security": 0.58, "expansion": 0.28, "stability": 0.82},
        0.09,
        0.92,
        0.68,
    ),
    PoliticalFactionType.MILITARY: FactionTemplate(
        PoliticalFactionType.MILITARY,
        "Military Bloc",
        {"food": 0.52, "wealth": 0.42, "security": 0.98, "expansion": 0.82, "stability": 0.72},
        0.15,
        0.30,
        0.20,
    ),
    PoliticalFactionType.PRIESTHOOD: FactionTemplate(
        PoliticalFactionType.PRIESTHOOD,
        "Priesthood",
        {"food": 0.68, "wealth": 0.42, "security": 0.58, "expansion": 0.34, "stability": 0.93},
        0.12,
        0.52,
        0.62,
    ),
    PoliticalFactionType.GUILDS: FactionTemplate(
        PoliticalFactionType.GUILDS,
        "Guild Coalition",
        {"food": 0.66, "wealth": 0.88, "security": 0.52, "expansion": 0.25, "stability": 0.80},
        0.10,
        0.86,
        0.62,
    ),
    PoliticalFactionType.FRONTIER: FactionTemplate(
        PoliticalFactionType.FRONTIER,
        "Frontier Lords",
        {"food": 0.62, "wealth": 0.46, "security": 0.96, "expansion": 0.76, "stability": 0.68},
        0.11,
        0.48,
        0.34,
    ),
    PoliticalFactionType.COMMONERS: FactionTemplate(
        PoliticalFactionType.COMMONERS,
        "Popular Assembly",
        {"food": 0.98, "wealth": 0.62, "security": 0.62, "expansion": 0.14, "stability": 0.86},
        0.07,
        0.72,
        0.86,
    ),
}


GOVERNMENT_FACTIONS: dict[GovernmentType, tuple[PoliticalFactionType, ...]] = {
    GovernmentType.MONARCHY: (
        PoliticalFactionType.NOBILITY,
        PoliticalFactionType.MILITARY,
        PoliticalFactionType.PRIESTHOOD,
        PoliticalFactionType.MERCHANTS,
    ),
    GovernmentType.ELECTIVE_MONARCHY: (
        PoliticalFactionType.NOBILITY,
        PoliticalFactionType.MERCHANTS,
        PoliticalFactionType.MILITARY,
        PoliticalFactionType.PRIESTHOOD,
    ),
    GovernmentType.COUNCIL: (
        PoliticalFactionType.MERCHANTS,
        PoliticalFactionType.GUILDS,
        PoliticalFactionType.COMMONERS,
        PoliticalFactionType.MILITARY,
    ),
    GovernmentType.CLAN_CONFEDERACY: (
        PoliticalFactionType.FRONTIER,
        PoliticalFactionType.NOBILITY,
        PoliticalFactionType.MILITARY,
        PoliticalFactionType.PRIESTHOOD,
    ),
    GovernmentType.THEOCRACY: (
        PoliticalFactionType.PRIESTHOOD,
        PoliticalFactionType.NOBILITY,
        PoliticalFactionType.COMMONERS,
        PoliticalFactionType.MILITARY,
    ),
    GovernmentType.MERCHANT_OLIGARCHY: (
        PoliticalFactionType.MERCHANTS,
        PoliticalFactionType.GUILDS,
        PoliticalFactionType.NOBILITY,
        PoliticalFactionType.MILITARY,
    ),
    GovernmentType.MILITARY_REGIME: (
        PoliticalFactionType.MILITARY,
        PoliticalFactionType.NOBILITY,
        PoliticalFactionType.MERCHANTS,
        PoliticalFactionType.COMMONERS,
    ),
}


GOVERNMENT_OFFICES: dict[GovernmentType, tuple[PoliticalOfficeType, ...]] = {
    GovernmentType.MONARCHY: (
        PoliticalOfficeType.RULER,
        PoliticalOfficeType.HEIR,
        PoliticalOfficeType.CHANCELLOR,
        PoliticalOfficeType.TREASURER,
        PoliticalOfficeType.MARSHAL,
    ),
    GovernmentType.ELECTIVE_MONARCHY: (
        PoliticalOfficeType.RULER,
        PoliticalOfficeType.CHANCELLOR,
        PoliticalOfficeType.TREASURER,
        PoliticalOfficeType.MARSHAL,
        PoliticalOfficeType.COUNCILOR,
    ),
    GovernmentType.COUNCIL: (
        PoliticalOfficeType.RULER,
        PoliticalOfficeType.CHANCELLOR,
        PoliticalOfficeType.TREASURER,
        PoliticalOfficeType.MARSHAL,
        PoliticalOfficeType.COUNCILOR,
    ),
    GovernmentType.CLAN_CONFEDERACY: (
        PoliticalOfficeType.RULER,
        PoliticalOfficeType.MARSHAL,
        PoliticalOfficeType.COUNCILOR,
        PoliticalOfficeType.TREASURER,
    ),
    GovernmentType.THEOCRACY: (
        PoliticalOfficeType.RULER,
        PoliticalOfficeType.HIGH_PRIEST,
        PoliticalOfficeType.CHANCELLOR,
        PoliticalOfficeType.TREASURER,
        PoliticalOfficeType.MARSHAL,
    ),
    GovernmentType.MERCHANT_OLIGARCHY: (
        PoliticalOfficeType.RULER,
        PoliticalOfficeType.TREASURER,
        PoliticalOfficeType.GUILD_REPRESENTATIVE,
        PoliticalOfficeType.CHANCELLOR,
        PoliticalOfficeType.MARSHAL,
    ),
    GovernmentType.MILITARY_REGIME: (
        PoliticalOfficeType.RULER,
        PoliticalOfficeType.MARSHAL,
        PoliticalOfficeType.CHANCELLOR,
        PoliticalOfficeType.TREASURER,
    ),
}


RULER_TITLES: dict[GovernmentType, str] = {
    GovernmentType.MONARCHY: "Sovereign",
    GovernmentType.ELECTIVE_MONARCHY: "Elected Sovereign",
    GovernmentType.COUNCIL: "First Speaker",
    GovernmentType.CLAN_CONFEDERACY: "High Chieftain",
    GovernmentType.THEOCRACY: "Hierophant",
    GovernmentType.MERCHANT_OLIGARCHY: "First Consul",
    GovernmentType.MILITARY_REGIME: "Marshal-Protector",
}


OFFICE_TITLES: dict[PoliticalOfficeType, str] = {
    PoliticalOfficeType.RULER: "Ruler",
    PoliticalOfficeType.HEIR: "Heir",
    PoliticalOfficeType.CHANCELLOR: "Chancellor",
    PoliticalOfficeType.TREASURER: "Treasurer",
    PoliticalOfficeType.MARSHAL: "Marshal",
    PoliticalOfficeType.HIGH_PRIEST: "High Priest",
    PoliticalOfficeType.GOVERNOR: "Governor",
    PoliticalOfficeType.MAYOR: "Mayor",
    PoliticalOfficeType.COUNCILOR: "Councilor",
    PoliticalOfficeType.GUILD_REPRESENTATIVE: "Guild Representative",
}


PERIODIC_REVIEW_YEARS: dict[GovernmentType, int] = {
    GovernmentType.ELECTIVE_MONARCHY: 6,
    GovernmentType.COUNCIL: 4,
    GovernmentType.CLAN_CONFEDERACY: 5,
    GovernmentType.MERCHANT_OLIGARCHY: 5,
}


def _adult_npcs(engine: FinalWorldEngine, kingdom: Kingdom) -> list[NPC]:
    return [
        npc
        for npc in engine.world.npcs.values()
        if npc.alive and npc.kingdom_id == kingdom.id and npc.age >= 18
    ]


def _social_score(npc: NPC) -> float:
    status = {
        "ruler": 1.0,
        "elite": 0.88,
        "notable": 0.72,
        "respected": 0.58,
        "commoner": 0.38,
        "child": 0.05,
    }.get(npc.social_status, 0.42)
    wealth = min(1.0, math.log1p(max(0.0, npc.wealth)) / math.log(250.0))
    return status * 0.65 + wealth * 0.35


def _member_score(npc: NPC, kind: PoliticalFactionType) -> float:
    occupation = npc.occupation
    occupation_bonus = 0.0
    if kind == PoliticalFactionType.NOBILITY:
        occupation_bonus = 0.45 if npc.social_status in {"elite", "ruler", "notable"} else 0.0
    elif kind == PoliticalFactionType.MERCHANTS:
        occupation_bonus = 0.55 if occupation in {"merchant", "innkeeper", "teamster", "scribe"} else 0.0
    elif kind == PoliticalFactionType.MILITARY:
        occupation_bonus = 0.58 if occupation in {"soldier", "guard", "ruler"} else 0.0
    elif kind == PoliticalFactionType.PRIESTHOOD:
        occupation_bonus = 0.65 if occupation == "priest" else 0.0
    elif kind == PoliticalFactionType.GUILDS:
        occupation_bonus = 0.52 if occupation in {
            "smith", "carpenter", "miller", "weaver", "mason", "brewer", "healer", "teacher",
        } else 0.0
    elif kind == PoliticalFactionType.FRONTIER:
        occupation_bonus = 0.45 if occupation in {"guard", "soldier", "farmer", "hunter", "miner"} else 0.0
    elif kind == PoliticalFactionType.COMMONERS:
        occupation_bonus = 0.34 if npc.social_status in {"commoner", "respected"} else 0.0

    value_bonus = {
        PoliticalFactionType.NOBILITY: npc.values.get("status", 0.5),
        PoliticalFactionType.MERCHANTS: npc.values.get("wealth", 0.5),
        PoliticalFactionType.MILITARY: npc.traits.get("courage", 0.5),
        PoliticalFactionType.PRIESTHOOD: npc.values.get("faith", 0.5),
        PoliticalFactionType.GUILDS: (npc.traits.get("ambition", 0.5) + npc.values.get("wealth", 0.5)) / 2,
        PoliticalFactionType.FRONTIER: (npc.traits.get("courage", 0.5) + npc.values.get("freedom", 0.5)) / 2,
        PoliticalFactionType.COMMONERS: (npc.values.get("freedom", 0.5) + npc.traits.get("empathy", 0.5)) / 2,
    }[kind]
    return _social_score(npc) * 0.35 + occupation_bonus + value_bonus * 0.35


def _office_score(engine: FinalWorldEngine, kingdom: Kingdom, npc: NPC, role: PoliticalOfficeType) -> float:
    base = _social_score(npc) * 0.35 + npc.traits.get("ambition", 0.5) * 0.18 + npc.traits.get("loyalty", 0.5) * 0.12
    if role == PoliticalOfficeType.TREASURER:
        base += (0.45 if npc.occupation in {"merchant", "scribe", "innkeeper"} else 0.0) + npc.values.get("wealth", 0.5) * 0.25
    elif role == PoliticalOfficeType.MARSHAL:
        base += (0.50 if npc.occupation in {"soldier", "guard"} else 0.0) + npc.traits.get("courage", 0.5) * 0.25
    elif role == PoliticalOfficeType.HIGH_PRIEST:
        base += (0.62 if npc.occupation == "priest" else 0.0) + npc.values.get("faith", 0.5) * 0.28
        if npc.religion_id == kingdom.religion_id:
            base += 0.18
    elif role == PoliticalOfficeType.CHANCELLOR:
        base += (0.30 if npc.occupation in {"scribe", "teacher", "merchant"} else 0.0) + npc.traits.get("empathy", 0.5) * 0.22
    elif role == PoliticalOfficeType.GUILD_REPRESENTATIVE:
        base += 0.40 if npc.occupation in {"smith", "carpenter", "miller", "weaver", "mason", "brewer"} else 0.0
    elif role == PoliticalOfficeType.COUNCILOR:
        base += npc.values.get("status", 0.5) * 0.22 + npc.traits.get("empathy", 0.5) * 0.14
    elif role == PoliticalOfficeType.HEIR:
        ruler = engine.world.npcs.get(kingdom.ruler_npc_id or "")
        if ruler and npc.id in ruler.child_ids:
            base += 1.2
        base += max(0.0, 0.25 - abs(npc.age - 30) * 0.006)
    return base


def _faction_support(engine: FinalWorldEngine, kingdom: Kingdom, npc: NPC) -> float:
    support = 0.0
    total = 0.0
    for faction_id in kingdom.faction_ids:
        faction = engine.world.political_factions.get(faction_id)
        if not faction or not faction.active:
            continue
        total += faction.influence
        if npc.id == faction.leader_npc_id:
            support += faction.influence
        elif npc.id in faction.member_npc_ids:
            support += faction.influence * 0.55
        else:
            template = FACTION_TEMPLATES[faction.kind]
            affinity = 1.0 - abs(npc.values.get("wealth", 0.5) - template.preferred_goals["wealth"])
            support += faction.influence * max(0.0, affinity) * 0.18
    return support / max(0.001, total)


def _ruler_candidate_score(engine: FinalWorldEngine, kingdom: Kingdom, npc: NPC) -> float:
    score = _social_score(npc) * 0.30
    score += npc.traits.get("ambition", 0.5) * 0.20
    score += npc.traits.get("loyalty", 0.5) * 0.10
    score += _faction_support(engine, kingdom, npc) * 0.35

    if kingdom.government == GovernmentType.MONARCHY:
        ruler = engine.world.npcs.get(kingdom.ruler_npc_id or "")
        if ruler and npc.id in ruler.child_ids:
            score += 1.5
        score += npc.values.get("status", 0.5) * 0.25
    elif kingdom.government == GovernmentType.ELECTIVE_MONARCHY:
        score += npc.values.get("status", 0.5) * 0.32
    elif kingdom.government == GovernmentType.COUNCIL:
        score += npc.traits.get("empathy", 0.5) * 0.25 + npc.values.get("freedom", 0.5) * 0.18
    elif kingdom.government == GovernmentType.CLAN_CONFEDERACY:
        score += npc.traits.get("courage", 0.5) * 0.28 + npc.values.get("family", 0.5) * 0.18
    elif kingdom.government == GovernmentType.THEOCRACY:
        if npc.occupation == "priest":
            score += 0.65
        if npc.religion_id == kingdom.religion_id:
            score += 0.25
        score += npc.values.get("faith", 0.5) * 0.32
    elif kingdom.government == GovernmentType.MERCHANT_OLIGARCHY:
        score += min(0.50, math.log1p(max(0.0, npc.wealth)) / 12.0)
        if npc.occupation in {"merchant", "innkeeper", "teamster", "scribe"}:
            score += 0.35
    elif kingdom.government == GovernmentType.MILITARY_REGIME:
        if npc.occupation in {"soldier", "guard"}:
            score += 0.55
        score += npc.traits.get("courage", 0.5) * 0.32
    return score


def initialize_kingdom_politics(engine: FinalWorldEngine, kingdom: Kingdom) -> None:
    if kingdom.politics_initialized:
        return
    adults = _adult_npcs(engine, kingdom)
    if not adults:
        kingdom.politics_initialized = True
        kingdom.last_leadership_review_year = engine.world.date.year
        return

    rng = engine._rng(f"politics-init:{kingdom.id}")
    faction_kinds = GOVERNMENT_FACTIONS.get(kingdom.government, GOVERNMENT_FACTIONS[GovernmentType.MONARCHY])
    created: list[PoliticalFaction] = []
    for index, kind in enumerate(faction_kinds):
        template = FACTION_TEMPLATES[kind]
        ranked = sorted(adults, key=lambda npc: (_member_score(npc, kind), npc.id), reverse=True)
        member_count = min(len(ranked), max(4, min(12, len(ranked) // 4 or 4)))
        members = [npc.id for npc in ranked[:member_count]]
        leader_id = members[0] if members else None

        regional_base_id = None
        if kind == PoliticalFactionType.FRONTIER:
            candidates = [
                engine.world.settlements[sid]
                for sid in kingdom.settlement_ids
                if sid in engine.world.settlements and sid != kingdom.capital_settlement_id
            ]
            if candidates:
                regional_base_id = min(candidates, key=lambda item: (item.stability, item.id)).id
        elif kind in {PoliticalFactionType.MERCHANTS, PoliticalFactionType.GUILDS, PoliticalFactionType.COMMONERS}:
            candidates = [engine.world.settlements[sid] for sid in kingdom.settlement_ids if sid in engine.world.settlements]
            if candidates:
                regional_base_id = max(candidates, key=lambda item: (item.population, item.id)).id

        faction = PoliticalFaction(
            id=engine.world.new_entity_id("faction"),
            kingdom_id=kingdom.id,
            name=f"{kingdom.name} {template.label}",
            kind=kind,
            leader_npc_id=leader_id,
            member_npc_ids=members,
            ideology=dict(template.preferred_goals),
            economic_interests={"preferred_tax_rate": template.preferred_tax_rate},
            religious_interests={"state_faith": 1.0 if kind == PoliticalFactionType.PRIESTHOOD else 0.35},
            influence=max(0.12, 0.22 + rng.uniform(-0.04, 0.04) + (0.04 if index == 0 else 0.0)),
            loyalty=max(0.20, min(0.92, kingdom.legitimacy * 0.55 + kingdom.stability * 0.25 + rng.uniform(0.0, 0.18))),
            preferred_policies={
                "tax_rate": template.preferred_tax_rate,
                "border_openness": template.preferred_border_open,
                "refugee_openness": template.preferred_refugee_open,
            },
            regional_base_settlement_id=regional_base_id,
            created_at=engine.world.date.model_copy(deep=True),
        )
        engine.world.political_factions[faction.id] = faction
        kingdom.faction_ids.append(faction.id)
        created.append(faction)

    total_influence = sum(faction.influence for faction in created)
    if total_influence > 0:
        for faction in created:
            faction.influence /= total_influence

    kingdom.politics_initialized = True
    kingdom.last_leadership_review_year = engine.world.date.year
    refresh_offices(engine, kingdom, emit_changes=False)
    engine.emit(
        "POLITICAL_ORDER_FORMED",
        f"The political institutions of {kingdom.name} took recognizable form under its {kingdom.government.value.replace('_', ' ')} government.",
        [kingdom.id, *kingdom.faction_ids],
        kingdom.capital_settlement_id,
        data={"government": kingdom.government.value, "faction_ids": list(kingdom.faction_ids)},
        importance=0.42,
    )


def ensure_political_society(engine: FinalWorldEngine) -> None:
    for kingdom in list(engine.world.kingdoms.values()):
        initialize_kingdom_politics(engine, kingdom)
    refresh_political_metrics(engine)


def _eligible_for_office(engine: FinalWorldEngine, kingdom: Kingdom, role: PoliticalOfficeType) -> list[NPC]:
    adults = _adult_npcs(engine, kingdom)
    if role == PoliticalOfficeType.RULER:
        ruler = engine.world.npcs.get(kingdom.ruler_npc_id or "")
        return [ruler] if ruler and ruler.alive else []
    if role == PoliticalOfficeType.HEIR:
        ruler = engine.world.npcs.get(kingdom.ruler_npc_id or "")
        if not ruler:
            return []
        children = [engine.world.npcs[cid] for cid in ruler.child_ids if cid in engine.world.npcs and engine.world.npcs[cid].alive and engine.world.npcs[cid].age >= 16]
        return children
    return adults


def refresh_offices(engine: FinalWorldEngine, kingdom: Kingdom, *, emit_changes: bool = True) -> None:
    desired_roles = GOVERNMENT_OFFICES.get(kingdom.government, GOVERNMENT_OFFICES[GovernmentType.MONARCHY])
    desired_keys = {role.value for role in desired_roles}
    for key in list(kingdom.political_offices):
        if key not in desired_keys:
            del kingdom.political_offices[key]

    for role in desired_roles:
        key = role.value
        existing = kingdom.political_offices.get(key)
        holder = engine.world.npcs.get(existing.holder_npc_id or "") if existing else None
        if role == PoliticalOfficeType.RULER:
            holder = engine.world.npcs.get(kingdom.ruler_npc_id or "")
        if holder and holder.alive and holder.kingdom_id == kingdom.id:
            if existing:
                existing.holder_npc_id = holder.id
            else:
                kingdom.political_offices[key] = PoliticalOffice(
                    role=role,
                    title=RULER_TITLES[kingdom.government] if role == PoliticalOfficeType.RULER else OFFICE_TITLES[role],
                    holder_npc_id=holder.id,
                    appointed_at=engine.world.date.model_copy(deep=True),
                )
            continue

        candidates = _eligible_for_office(engine, kingdom, role)
        used = {
            office.holder_npc_id
            for office_key, office in kingdom.political_offices.items()
            if office_key != key and office.holder_npc_id
        }
        candidates = [npc for npc in candidates if npc.id not in used or role in {PoliticalOfficeType.RULER, PoliticalOfficeType.HEIR}]
        new_holder = max(candidates, key=lambda npc: (_office_score(engine, kingdom, npc, role), npc.id), default=None)
        prior_id = existing.holder_npc_id if existing else None
        office = PoliticalOffice(
            role=role,
            title=RULER_TITLES[kingdom.government] if role == PoliticalOfficeType.RULER else OFFICE_TITLES[role],
            holder_npc_id=new_holder.id if new_holder else None,
            appointed_at=engine.world.date.model_copy(deep=True),
        )
        kingdom.political_offices[key] = office
        if emit_changes and new_holder and new_holder.id != prior_id:
            engine.emit(
                "OFFICE_APPOINTED",
                f"{new_holder.name} became {office.title} of {kingdom.name}.",
                [kingdom.id, new_holder.id],
                kingdom.capital_settlement_id,
                data={"office": role.value, "previous_holder_id": prior_id},
                importance=0.38 if role != PoliticalOfficeType.RULER else 0.75,
            )


def _faction_conditions(engine: FinalWorldEngine, kingdom: Kingdom, faction: PoliticalFaction) -> tuple[float, list[str]]:
    template = FACTION_TEMPLATES[faction.kind]
    settlements = [engine.world.settlements[sid] for sid in kingdom.settlement_ids if sid in engine.world.settlements]
    avg_food = sum(s.food_security for s in settlements) / max(1, len(settlements))
    avg_stability = sum(s.stability for s in settlements) / max(1, len(settlements))
    at_war = engine._war_for_kingdom(kingdom.id) is not None

    satisfaction = kingdom.legitimacy * 0.25 + avg_stability * 0.22 + avg_food * 0.18
    satisfaction += max(0.0, 1.0 - abs(kingdom.tax_rate - template.preferred_tax_rate) / 0.12) * 0.12
    satisfaction += kingdom.military_readiness * (0.10 if faction.kind in {PoliticalFactionType.MILITARY, PoliticalFactionType.FRONTIER} else 0.04)
    satisfaction += min(0.08, kingdom.treasury / max(1, engine.world.total_population) * 0.4)
    if at_war:
        satisfaction += 0.06 if faction.kind == PoliticalFactionType.MILITARY else -0.03
    satisfaction = max(0.0, min(1.0, satisfaction))

    grievances: list[str] = []
    if avg_food < 0.42:
        grievances.append("Food insecurity")
    if avg_stability < 0.42:
        grievances.append("Local disorder")
    if kingdom.legitimacy < 0.40:
        grievances.append("Weak legitimacy")
    if kingdom.tax_rate > template.preferred_tax_rate + 0.045:
        grievances.append("Excessive taxation")
    if faction.kind == PoliticalFactionType.MILITARY and kingdom.military_readiness < 0.42:
        grievances.append("Military neglect")
    if faction.kind == PoliticalFactionType.MERCHANTS:
        blocked = sum(1 for relation in kingdom.relations.values() if not relation.trade_access)
        if blocked >= max(1, len(kingdom.relations) // 2):
            grievances.append("Restricted trade")
    if faction.kind == PoliticalFactionType.PRIESTHOOD:
        leader = engine.world.npcs.get(faction.leader_npc_id or "")
        if leader and kingdom.religion_id and leader.religion_id != kingdom.religion_id:
            grievances.append("Religious leadership dispute")
    if faction.regional_base_settlement_id:
        base = engine.world.settlements.get(faction.regional_base_settlement_id)
        if base and base.stability < 0.34:
            grievances.append(f"Neglect of {base.name}")
    return satisfaction, grievances


def update_factions(engine: FinalWorldEngine, kingdom: Kingdom) -> None:
    active = [engine.world.political_factions[fid] for fid in kingdom.faction_ids if fid in engine.world.political_factions and engine.world.political_factions[fid].active]
    if not active:
        return
    raw_influence: dict[str, float] = {}
    for faction in active:
        satisfaction, grievances = _faction_conditions(engine, kingdom, faction)
        faction.loyalty = max(0.0, min(1.0, faction.loyalty + (satisfaction - 0.55) * 0.025))
        faction.grievances = grievances

        leader = engine.world.npcs.get(faction.leader_npc_id or "")
        leader_factor = 0.5 if not leader or not leader.alive else 0.65 + leader.traits.get("ambition", 0.5) * 0.45
        institutional = {
            PoliticalFactionType.NOBILITY: 1.06 if kingdom.government in {GovernmentType.MONARCHY, GovernmentType.ELECTIVE_MONARCHY} else 0.92,
            PoliticalFactionType.MERCHANTS: 1.12 if kingdom.government == GovernmentType.MERCHANT_OLIGARCHY else 1.0,
            PoliticalFactionType.MILITARY: 1.15 if kingdom.government == GovernmentType.MILITARY_REGIME else 1.0,
            PoliticalFactionType.PRIESTHOOD: 1.18 if kingdom.government == GovernmentType.THEOCRACY else 1.0,
            PoliticalFactionType.GUILDS: 1.08 if kingdom.government == GovernmentType.COUNCIL else 0.96,
            PoliticalFactionType.FRONTIER: 1.08 if kingdom.government == GovernmentType.CLAN_CONFEDERACY else 0.96,
            PoliticalFactionType.COMMONERS: 1.04 if kingdom.government == GovernmentType.COUNCIL else 0.92,
        }[faction.kind]
        grievance_pressure = min(0.22, len(faction.grievances) * 0.05)
        raw_influence[faction.id] = max(0.04, faction.influence * 0.72 + leader_factor * institutional * 0.24 + grievance_pressure * 0.10)

    total = sum(raw_influence.values())
    if total:
        for faction in active:
            faction.influence = raw_influence[faction.id] / total


def update_legitimacy(engine: FinalWorldEngine, kingdom: Kingdom) -> None:
    factions = [engine.world.political_factions[fid] for fid in kingdom.faction_ids if fid in engine.world.political_factions and engine.world.political_factions[fid].active]
    faction_support = sum(f.influence * f.loyalty for f in factions) / max(0.001, sum(f.influence for f in factions)) if factions else 0.5
    settlements = [engine.world.settlements[sid] for sid in kingdom.settlement_ids if sid in engine.world.settlements]
    food = sum(s.food_security * max(1, s.population) for s in settlements) / max(1, sum(max(1, s.population) for s in settlements)) if settlements else 0.0
    local_stability = sum(s.stability for s in settlements) / max(1, len(settlements)) if settlements else 0.0
    tax_acceptance = max(0.0, min(1.0, 1.0 - max(0.0, kingdom.tax_rate - 0.08) / 0.16))
    target = faction_support * 0.35 + food * 0.20 + local_stability * 0.25 + tax_acceptance * 0.10 + kingdom.military_readiness * 0.10
    if kingdom.overlord_kingdom_id:
        target -= 0.08
    war = engine._war_for_kingdom(kingdom.id)
    if war:
        exhaustion = war.attacker_exhaustion if war.attacker_kingdom_id == kingdom.id else war.defender_exhaustion
        target -= exhaustion * 0.12
    target = max(0.0, min(1.0, target))
    kingdom.legitimacy = max(0.0, min(1.0, kingdom.legitimacy + (target - kingdom.legitimacy) * 0.035))


def apply_faction_pressure_to_goals(engine: FinalWorldEngine, kingdom: Kingdom) -> None:
    factions = [engine.world.political_factions[fid] for fid in kingdom.faction_ids if fid in engine.world.political_factions and engine.world.political_factions[fid].active]
    total = sum(f.influence for f in factions)
    if total <= 0:
        return
    changes: dict[str, float] = {}
    for goal in {"food", "wealth", "security", "expansion", "stability"}:
        target = sum(f.influence * f.ideology.get(goal, 0.5) for f in factions) / total
        current = kingdom.goals.get(goal, 0.5)
        updated = max(0.0, min(1.0, current + (target - current) * 0.045))
        if abs(updated - current) >= 0.002:
            changes[goal] = updated - current
        kingdom.goals[goal] = updated
    if changes and engine.world.date.month == 1:
        strongest = max(factions, key=lambda f: (f.influence, f.id))
        engine.emit(
            "FACTION_INFLUENCE",
            f"Political pressure led by the {strongest.name} shifted the priorities of {kingdom.name}.",
            [kingdom.id, strongest.id],
            kingdom.capital_settlement_id,
            data={"goal_changes": changes, "strongest_faction_id": strongest.id},
            importance=0.34,
        )


def _refresh_faction_membership(engine: FinalWorldEngine, kingdom: Kingdom) -> None:
    adults = _adult_npcs(engine, kingdom)
    for faction_id in kingdom.faction_ids:
        faction = engine.world.political_factions.get(faction_id)
        if not faction or not faction.active:
            continue
        ranked = sorted(adults, key=lambda npc: (_member_score(npc, faction.kind), npc.id), reverse=True)
        member_count = min(len(ranked), max(4, min(12, len(ranked) // 4 or 4)))
        faction.member_npc_ids = [npc.id for npc in ranked[:member_count]]
        leader = engine.world.npcs.get(faction.leader_npc_id or "")
        if not leader or not leader.alive or leader.kingdom_id != kingdom.id:
            prior = faction.leader_npc_id
            faction.leader_npc_id = faction.member_npc_ids[0] if faction.member_npc_ids else None
            if faction.leader_npc_id and faction.leader_npc_id != prior:
                new_leader = engine.world.npcs[faction.leader_npc_id]
                engine.emit(
                    "FACTION_LEADER_CHANGED",
                    f"{new_leader.name} became leader of the {faction.name}.",
                    [kingdom.id, faction.id, new_leader.id],
                    new_leader.settlement_id,
                    data={"previous_leader_id": prior},
                    importance=0.38,
                )


def select_successor(engine: FinalWorldEngine, kingdom: Kingdom, prior_ruler: NPC | None) -> NPC | None:
    candidates = _adult_npcs(engine, kingdom)
    if not candidates:
        return None
    if kingdom.government == GovernmentType.MONARCHY and prior_ruler:
        children = [
            engine.world.npcs[cid]
            for cid in prior_ruler.child_ids
            if cid in engine.world.npcs and engine.world.npcs[cid].alive and engine.world.npcs[cid].age >= 18 and engine.world.npcs[cid].kingdom_id == kingdom.id
        ]
        if children:
            return max(children, key=lambda npc: (_ruler_candidate_score(engine, kingdom, npc), npc.age, npc.id))
    return max(candidates, key=lambda npc: (_ruler_candidate_score(engine, kingdom, npc), npc.id))


def install_ruler(
    engine: FinalWorldEngine,
    kingdom: Kingdom,
    successor: NPC,
    prior_ruler: NPC | None,
    *,
    method: str,
    succession: bool,
) -> None:
    if prior_ruler and prior_ruler.id != successor.id and prior_ruler.alive:
        prior_ruler.title = "Former Sovereign"
        prior_ruler.occupation = "statesman"
        prior_ruler.social_status = "elite"
    title = RULER_TITLES.get(kingdom.government, "Sovereign")
    successor.title = title
    successor.occupation = "ruler"
    successor.social_status = "ruler"
    kingdom.ruler_npc_id = successor.id
    kingdom.last_leadership_review_year = engine.world.date.year
    if succession:
        kingdom.legitimacy = max(0.18, min(1.0, kingdom.legitimacy + (0.06 if method == "hereditary succession" else -0.01)))
    else:
        kingdom.legitimacy = max(0.30, min(0.78, kingdom.legitimacy + 0.08))
    refresh_offices(engine, kingdom, emit_changes=False)
    event_type = "RULER_SUCCEEDED" if succession else "LEADERSHIP_CHANGED"
    old_name = prior_ruler.name if prior_ruler else "the previous ruler"
    verb = "succeeded" if succession else "replaced"
    engine.emit(
        event_type,
        f"{successor.name} {verb} {old_name} as {title} of {kingdom.name} through {method}.",
        [successor.id, kingdom.id] + ([prior_ruler.id] if prior_ruler else []),
        kingdom.capital_settlement_id,
        data={"method": method, "prior_ruler_id": prior_ruler.id if prior_ruler else None},
        importance=0.90 if succession else 0.86,
    )


def succession_check(engine: FinalWorldEngine) -> None:
    ensure_political_society(engine)
    for kingdom in list(engine.world.kingdoms.values()):
        ruler = engine.world.npcs.get(kingdom.ruler_npc_id or "")
        if ruler and ruler.alive:
            continue
        successor = select_successor(engine, kingdom, ruler)
        if not successor:
            kingdom.ruler_npc_id = None
            kingdom.legitimacy = max(0.0, kingdom.legitimacy - 0.08)
            continue
        method = {
            GovernmentType.MONARCHY: "hereditary succession",
            GovernmentType.ELECTIVE_MONARCHY: "electoral succession",
            GovernmentType.COUNCIL: "council selection",
            GovernmentType.CLAN_CONFEDERACY: "clan acclamation",
            GovernmentType.THEOCRACY: "clerical succession",
            GovernmentType.MERCHANT_OLIGARCHY: "oligarchic selection",
            GovernmentType.MILITARY_REGIME: "military succession",
        }.get(kingdom.government, "political succession")
        install_ruler(engine, kingdom, successor, ruler, method=method, succession=True)


def _leadership_review(engine: FinalWorldEngine, kingdom: Kingdom) -> None:
    ruler = engine.world.npcs.get(kingdom.ruler_npc_id or "")
    if not ruler or not ruler.alive:
        return
    interval = PERIODIC_REVIEW_YEARS.get(kingdom.government)
    due_periodic = bool(interval and engine.world.date.year - kingdom.last_leadership_review_year >= interval)
    hostile_factions = [
        engine.world.political_factions[fid]
        for fid in kingdom.faction_ids
        if fid in engine.world.political_factions
        and engine.world.political_factions[fid].active
        and engine.world.political_factions[fid].loyalty < 0.28
        and engine.world.political_factions[fid].influence >= 0.24
    ]
    due_crisis = kingdom.legitimacy < 0.30 and bool(hostile_factions)
    if not due_periodic and not due_crisis:
        return

    candidates = _adult_npcs(engine, kingdom)
    if len(candidates) < 2:
        kingdom.last_leadership_review_year = engine.world.date.year
        return
    successor = max(candidates, key=lambda npc: (_ruler_candidate_score(engine, kingdom, npc), npc.id))
    current_score = _ruler_candidate_score(engine, kingdom, ruler)
    successor_score = _ruler_candidate_score(engine, kingdom, successor)
    required_margin = -0.04 if due_crisis else 0.08
    if successor.id == ruler.id or successor_score < current_score + required_margin:
        kingdom.last_leadership_review_year = engine.world.date.year
        kingdom.legitimacy = min(1.0, kingdom.legitimacy + (0.025 if due_periodic else 0.0))
        return

    if due_crisis:
        method = {
            GovernmentType.MONARCHY: "court coup",
            GovernmentType.THEOCRACY: "synod removal",
            GovernmentType.MILITARY_REGIME: "officer coup",
        }.get(kingdom.government, "emergency vote")
    else:
        method = {
            GovernmentType.ELECTIVE_MONARCHY: "scheduled election",
            GovernmentType.COUNCIL: "council vote",
            GovernmentType.CLAN_CONFEDERACY: "clan moot",
            GovernmentType.MERCHANT_OLIGARCHY: "oligarchic election",
        }.get(kingdom.government, "leadership review")
    install_ruler(engine, kingdom, successor, ruler, method=method, succession=False)


def rebellion_candidate(engine: FinalWorldEngine, kingdom: Kingdom) -> tuple[PoliticalFaction, str] | None:
    if len(kingdom.settlement_ids) < 2:
        return None
    factions = [engine.world.political_factions[fid] for fid in kingdom.faction_ids if fid in engine.world.political_factions and engine.world.political_factions[fid].active]
    if not factions:
        return None
    faction = max(factions, key=lambda item: (item.influence * (1.0 - item.loyalty), item.id))
    pressure = (1.0 - kingdom.legitimacy) * 0.38 + (1.0 - kingdom.stability) * 0.30 + faction.influence * (1.0 - faction.loyalty) * 0.52
    pressure += min(0.12, len(faction.grievances) * 0.025)
    if pressure < 0.68:
        return None
    rng = engine._rng(f"faction-rebellion:{kingdom.id}:{faction.id}")
    chance = min(0.09, max(0.008, (pressure - 0.64) * 0.18))
    if rng.random() >= chance:
        return None

    settlement_id = faction.regional_base_settlement_id
    if not settlement_id or settlement_id == kingdom.capital_settlement_id or settlement_id not in kingdom.settlement_ids:
        candidates = [
            engine.world.settlements[sid]
            for sid in kingdom.settlement_ids
            if sid in engine.world.settlements and sid != kingdom.capital_settlement_id
        ]
        if not candidates:
            return None
        settlement_id = min(candidates, key=lambda settlement: (settlement.stability, settlement.food_security, settlement.id)).id
    return faction, settlement_id


def run_political_cycle(engine: FinalWorldEngine) -> None:
    ensure_political_society(engine)
    for kingdom in list(engine.world.kingdoms.values()):
        update_factions(engine, kingdom)
        update_legitimacy(engine, kingdom)
        if engine.world.date.month in {1, 4, 7, 10}:
            apply_faction_pressure_to_goals(engine, kingdom)
        if engine.world.date.month == 1:
            _refresh_faction_membership(engine, kingdom)
            refresh_offices(engine, kingdom)
            _leadership_review(engine, kingdom)
    refresh_political_metrics(engine)


def refresh_political_metrics(engine: FinalWorldEngine) -> None:
    active_factions = [faction for faction in engine.world.political_factions.values() if faction.active and faction.kingdom_id in engine.world.kingdoms]
    kingdoms = list(engine.world.kingdoms.values())
    engine.world.metrics["political_factions"] = float(len(active_factions))
    engine.world.metrics["average_legitimacy"] = sum(k.legitimacy for k in kingdoms) / max(1, len(kingdoms))
    engine.world.metrics["average_faction_loyalty"] = sum(f.loyalty for f in active_factions) / max(1, len(active_factions))
    engine.world.metrics["low_legitimacy_kingdoms"] = float(sum(1 for k in kingdoms if k.legitimacy < 0.35))
