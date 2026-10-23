from __future__ import annotations

import random

from .advanced_simulation import LivingWorldEngine
from .domain import Kingdom, NPC
from .generation import FIRST_NAMES, GOALS, OCCUPATIONS
from .politics import RULER_TITLES, refresh_offices
from .political_collapse import _opposition_faction


FOUNDING_CAST_TARGET = 4
_ORIGINAL_FOUND_BREAKAWAY = LivingWorldEngine._found_breakaway_kingdom
_INSTALLED = False


def _founder_score(npc: NPC) -> tuple[float, float, float, str]:
    return (
        npc.traits.get("ambition", 0.5),
        npc.traits.get("courage", 0.5),
        npc.values.get("status", 0.5),
        npc.id,
    )


def _is_valid_adult_founder(npc: NPC | None, kingdom: Kingdom) -> bool:
    return bool(
        npc
        and npc.alive
        and npc.age >= 18
        and npc.kingdom_id == kingdom.id
    )


def _adult_residents(engine: LivingWorldEngine, kingdom: Kingdom) -> list[NPC]:
    return [
        npc
        for npc in engine.world.npcs.values()
        if _is_valid_adult_founder(npc, kingdom)
    ]


def _move_founder(npc: NPC, new: Kingdom, settlement_id: str) -> None:
    npc.kingdom_id = new.id
    npc.settlement_id = settlement_id
    npc.culture_id = new.culture_id
    if npc.social_status == "ruler":
        npc.social_status = "elite"
    if npc.occupation == "ruler":
        npc.occupation = "statesman"
    if npc.title and "Sovereign" in npc.title:
        npc.title = None


def _materialize_founder(
    engine: LivingWorldEngine,
    new: Kingdom,
    settlement_id: str,
    rng: random.Random,
) -> NPC:
    settlement = engine.world.settlements[settlement_id]
    ancestry = max(settlement.ancestry_population, key=settlement.ancestry_population.get)
    npc_id = engine.world.new_entity_id("npc")
    first_name = rng.choice(FIRST_NAMES[ancestry])
    surname = settlement.name.split()[0].replace("'", "") or "Founder"
    goals = rng.sample(GOALS, k=min(2, len(GOALS)))
    npc = NPC(
        id=npc_id,
        name=f"{first_name} {surname}",
        ancestry=ancestry,
        culture_id=new.culture_id,
        religion_id=new.religion_id,
        settlement_id=settlement_id,
        kingdom_id=new.id,
        age=rng.randint(24, 48),
        sex=rng.choice(["female", "male"]),
        health=rng.uniform(0.72, 0.96),
        wealth=rng.uniform(18.0, 55.0),
        occupation=rng.choice(OCCUPATIONS),
        social_status="notable",
        traits={
            "ambition": rng.uniform(0.52, 0.82),
            "courage": rng.uniform(0.48, 0.82),
            "loyalty": rng.uniform(0.45, 0.72),
            "empathy": rng.uniform(0.38, 0.72),
        },
        values={
            "status": rng.uniform(0.48, 0.76),
            "wealth": rng.uniform(0.35, 0.68),
            "faith": rng.uniform(0.30, 0.72),
            "freedom": rng.uniform(0.58, 0.88),
            "family": rng.uniform(0.42, 0.78),
        },
        goals=goals,
        goal_progress={goal: 0.0 for goal in goals},
    )
    engine.world.npcs[npc.id] = npc
    return npc


def _demote_invalid_ruler(engine: LivingWorldEngine, new: Kingdom) -> None:
    ruler = engine.world.npcs.get(new.ruler_npc_id or "")
    if _is_valid_adult_founder(ruler, new):
        return

    if ruler and ruler.kingdom_id == new.id:
        ruler.title = None
        if ruler.age < 16:
            ruler.occupation = "child"
            ruler.social_status = "child"
        else:
            if ruler.occupation == "ruler":
                ruler.occupation = "statesman"
            if ruler.social_status == "ruler":
                ruler.social_status = "notable"
    new.ruler_npc_id = None


def _ensure_breakaway_leadership(
    engine: LivingWorldEngine,
    new: Kingdom,
    adults: list[NPC],
) -> None:
    _demote_invalid_ruler(engine, new)

    if not new.ruler_npc_id:
        ruler = max(adults, key=_founder_score)
        new.ruler_npc_id = ruler.id
        ruler.title = RULER_TITLES.get(new.government, "Sovereign")
        ruler.occupation = "ruler"
        ruler.social_status = "ruler"

    commander = next(
        (npc for npc in adults if npc.id != new.ruler_npc_id),
        engine.world.npcs.get(new.ruler_npc_id or ""),
    )
    if not commander:
        return

    for army_id in new.army_ids:
        army = engine.world.armies.get(army_id)
        if not army:
            continue
        current = engine.world.npcs.get(army.commander_npc_id or "")
        if not _is_valid_adult_founder(current, new):
            army.commander_npc_id = commander.id


def _seed_breakaway_political_cast(
    engine: LivingWorldEngine,
    parent: Kingdom,
    new: Kingdom,
    settlement_id: str,
    rng: random.Random,
) -> list[NPC]:
    adults = _adult_residents(engine, new)

    faction = _opposition_faction(engine.world, parent)
    prioritized_ids: list[str] = []
    if faction:
        prioritized_ids.extend(
            npc_id
            for npc_id in [faction.leader_npc_id, *faction.member_npc_ids]
            if npc_id
        )

    parent_adults = sorted(
        (
            npc
            for npc in engine.world.npcs.values()
            if npc.alive
            and npc.age >= 18
            and npc.kingdom_id == parent.id
            and npc.id != parent.ruler_npc_id
        ),
        key=_founder_score,
        reverse=True,
    )
    prioritized_ids.extend(npc.id for npc in parent_adults)

    seen = {npc.id for npc in adults}
    relocated: list[NPC] = []
    for npc_id in prioritized_ids:
        if len(adults) >= FOUNDING_CAST_TARGET or npc_id in seen:
            continue
        npc = engine.world.npcs.get(npc_id)
        if (
            not npc
            or not npc.alive
            or npc.age < 18
            or npc.kingdom_id != parent.id
            or npc.id == parent.ruler_npc_id
        ):
            continue
        seen.add(npc.id)
        _move_founder(npc, new, settlement_id)
        adults.append(npc)
        relocated.append(npc)

    materialized: list[NPC] = []
    while len(adults) < FOUNDING_CAST_TARGET:
        npc = _materialize_founder(engine, new, settlement_id, rng)
        adults.append(npc)
        materialized.append(npc)

    _ensure_breakaway_leadership(engine, new, adults)

    # Founders may have held offices in the parent state. Refill those offices now;
    # faction membership is reconciled immediately after this wrapper returns.
    refresh_offices(engine, parent, emit_changes=False)

    if relocated or materialized:
        engine.emit(
            "BREAKAWAY_FOUNDERS_ASSEMBLED",
            f"A founding political delegation assembled in {engine.world.settlements[settlement_id].name} to organize {new.name}.",
            [parent.id, new.id, *(npc.id for npc in relocated + materialized)],
            settlement_id,
            data={
                "relocated_npc_ids": [npc.id for npc in relocated],
                "materialized_npc_ids": [npc.id for npc in materialized],
                "founding_cast_size": len(adults),
                "ruler_npc_id": new.ruler_npc_id,
            },
            importance=0.66,
        )
    return adults


def _found_breakaway_with_political_cast(
    self: LivingWorldEngine,
    parent: Kingdom,
    settlement_id: str,
    rng: random.Random,
) -> Kingdom:
    new = _ORIGINAL_FOUND_BREAKAWAY(self, parent, settlement_id, rng)
    _seed_breakaway_political_cast(self, parent, new, settlement_id, rng)
    return new


def install_breakaway_political_bootstrap() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    LivingWorldEngine._found_breakaway_kingdom = _found_breakaway_with_political_cast
    _INSTALLED = True
