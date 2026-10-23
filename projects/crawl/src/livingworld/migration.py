from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .domain import BorderPolicy, CampStatus, RefugeeCamp, RefugeePolicy, Settlement

if TYPE_CHECKING:
    from .simulation import WorldEngine


def _distance(a: Settlement, b: Settlement) -> float:
    return math.hypot(a.position.x - b.position.x, a.position.y - b.position.y)


def _travel_cost(engine: WorldEngine, a: Settlement, b: Settlement) -> float:
    """Approximate migration friction using distance plus established travel corridors."""
    distance = _distance(a, b)
    for route in engine.world.trade_routes.values():
        if not route.active:
            continue
        endpoints = {route.origin_settlement_id, route.destination_settlement_id}
        if endpoints == {a.id, b.id}:
            return distance * (0.62 + (1.0 - route.safety) * 0.22)
    return distance


def _push_score(settlement: Settlement, at_war: bool) -> float:
    scarcity = max(0.0, 0.60 - settlement.food_security) * 1.45
    instability = max(0.0, 0.55 - settlement.stability) * 1.05
    overcrowding = max(0.0, settlement.population / max(1, settlement.housing_capacity) - 0.92) * 0.85
    war_pressure = 0.65 if at_war else 0.0
    return scarcity + instability + overcrowding + war_pressure


def _pull_score(settlement: Settlement, travel_cost: float, destination_at_war: bool) -> float:
    free_housing = max(0.0, (settlement.housing_capacity - settlement.population) / max(1, settlement.housing_capacity))
    prosperity = min(1.0, settlement.wealth / max(1.0, settlement.population * 8.0))
    score = (
        settlement.food_security * 0.42
        + settlement.stability * 0.28
        + settlement.health * 0.12
        + free_housing * 0.12
        + prosperity * 0.06
        - min(0.45, travel_cost / 700.0)
    )
    if destination_at_war:
        score -= 0.28
    return score


def _border_acceptance(engine: WorldEngine, source: Settlement, destination: Settlement, refugee: bool) -> float:
    if source.kingdom_id == destination.kingdom_id:
        return 1.0
    host = engine.world.kingdoms.get(destination.kingdom_id)
    if not host:
        return 0.0

    if not refugee:
        return {
            BorderPolicy.OPEN: 1.0,
            BorderPolicy.CONTROLLED: 0.55,
            BorderPolicy.CLOSED: 0.0,
        }[host.border_policy]

    base = {
        RefugeePolicy.WELCOME: 1.0,
        RefugeePolicy.LIMITED: 0.45,
        RefugeePolicy.REJECT: 0.0,
    }[host.refugee_policy]
    border_factor = {
        BorderPolicy.OPEN: 1.0,
        BorderPolicy.CONTROLLED: 0.75,
        BorderPolicy.CLOSED: 0.20,
    }[host.border_policy]
    return base * border_factor


def _take_ancestry(source: Settlement, amount: int, source_population_before: int) -> dict[object, int]:
    if amount <= 0 or source_population_before <= 0:
        return {}

    allocations: dict[object, int] = {}
    fractions: list[tuple[float, object]] = []
    moved = 0
    for ancestry, count in source.ancestry_population.items():
        raw = amount * count / source_population_before
        take = min(count, int(raw))
        allocations[ancestry] = take
        moved += take
        fractions.append((raw - take, ancestry))

    remaining = amount - moved
    for _, ancestry in sorted(fractions, reverse=True):
        if remaining <= 0:
            break
        available = source.ancestry_population.get(ancestry, 0) - allocations.get(ancestry, 0)
        if available <= 0:
            continue
        allocations[ancestry] = allocations.get(ancestry, 0) + 1
        remaining -= 1

    for ancestry, count in allocations.items():
        if count > 0:
            source.ancestry_population[ancestry] = max(0, source.ancestry_population.get(ancestry, 0) - count)
    return allocations


def _split_ancestry(allocations: dict[object, int], first_amount: int, total_amount: int) -> tuple[dict[object, int], dict[object, int]]:
    if total_amount <= 0 or first_amount <= 0:
        return {}, dict(allocations)
    if first_amount >= total_amount:
        return dict(allocations), {}

    first: dict[object, int] = {}
    fractions: list[tuple[float, object]] = []
    assigned = 0
    for ancestry, count in allocations.items():
        raw = first_amount * count / total_amount
        take = min(count, int(raw))
        first[ancestry] = take
        assigned += take
        fractions.append((raw - take, ancestry))
    remaining = first_amount - assigned
    for _, ancestry in sorted(fractions, reverse=True):
        if remaining <= 0:
            break
        available = allocations.get(ancestry, 0) - first.get(ancestry, 0)
        if available > 0:
            first[ancestry] = first.get(ancestry, 0) + 1
            remaining -= 1
    second = {ancestry: count - first.get(ancestry, 0) for ancestry, count in allocations.items()}
    return first, second


def _add_ancestry(target: dict, allocations: dict[object, int]) -> None:
    for ancestry, count in allocations.items():
        if count > 0:
            target[ancestry] = target.get(ancestry, 0) + count


def _transfer_ancestry(source: Settlement, destination: Settlement, amount: int, source_population_before: int) -> None:
    allocations = _take_ancestry(source, amount, source_population_before)
    _add_ancestry(destination.ancestry_population, allocations)


def _move_persistent_npcs(
    engine: WorldEngine,
    source: Settlement,
    destination: Settlement,
    amount: int,
    source_population_before: int,
    refugee: bool,
) -> list[str]:
    world = engine.world
    commander_ids = {army.commander_npc_id for army in world.armies.values() if army.active and army.commander_npc_id}
    ruler_ids = {kingdom.ruler_npc_id for kingdom in world.kingdoms.values() if kingdom.ruler_npc_id}
    residents = [
        npc for npc in world.npcs.values()
        if npc.alive
        and npc.settlement_id == source.id
        and npc.id not in commander_ids
        and npc.id not in ruler_ids
        and npc.social_status != "ruler"
    ]
    if not residents or amount <= 0:
        return []

    ratio = amount / max(1, source_population_before)
    target = min(5, max(0, round(len(residents) * ratio)))
    if refugee and amount >= 20:
        target = max(1, target)
    if target <= 0:
        return []

    rng = engine._rng(f"migration-npcs:{source.id}:{destination.id}")
    selected = list(rng.sample(residents, k=min(target, len(residents))))
    selected_ids = {npc.id for npc in selected}
    resident_by_id = {npc.id: npc for npc in residents}

    for npc in list(selected):
        if len(selected) >= 5:
            break
        family_ids = [npc.spouse_id, *npc.child_ids]
        for family_id in family_ids:
            if len(selected) >= 5:
                break
            family = resident_by_id.get(family_id or "")
            if family and family.id not in selected_ids:
                selected.append(family)
                selected_ids.add(family.id)

    for npc in selected:
        npc.settlement_id = destination.id
        npc.kingdom_id = destination.kingdom_id

    return [npc.id for npc in selected]


def _reason(source: Settlement, at_war: bool) -> str:
    if at_war:
        return "war"
    if source.food_security < 0.45:
        return "food_shortage"
    if source.stability < 0.45:
        return "instability"
    if source.population > source.housing_capacity * 0.95:
        return "overcrowding"
    return "opportunity"


def _apply_arrival_pressure(destination: Settlement, accepted: int) -> None:
    if accepted <= 0:
        return
    ratio = accepted / max(1, destination.population)
    grain = destination.resources.get("grain")
    if grain:
        grain.quantity = max(0.0, grain.quantity - accepted * 0.18)
    destination.food_security = max(0.05, destination.food_security - min(0.06, ratio * 0.09))
    destination.health = max(0.10, destination.health - min(0.025, ratio * 0.03))
    destination.stability = max(0.10, destination.stability - min(0.02, ratio * 0.025))


def _record_refugee_diplomacy(engine: WorldEngine, source: Settlement, destination: Settlement, accepted: int, camped: int) -> None:
    if source.kingdom_id == destination.kingdom_id:
        return
    origin = engine.world.kingdoms.get(source.kingdom_id)
    host = engine.world.kingdoms.get(destination.kingdom_id)
    if not origin or not host:
        return
    origin_relation = origin.relations.get(host.id)
    host_relation = host.relations.get(origin.id)
    if camped > 0:
        grievance = f"Refugees denied entry in year {engine.world.date.year}"
        if origin_relation:
            origin_relation.opinion = max(-1.0, origin_relation.opinion - min(0.12, camped / 1500.0))
            if grievance not in origin_relation.grievances:
                origin_relation.grievances.append(grievance)
        if host_relation:
            host_relation.opinion = max(-1.0, host_relation.opinion - min(0.05, camped / 3000.0))
    elif accepted > 0 and origin_relation:
        origin_relation.opinion = min(1.0, origin_relation.opinion + min(0.04, accepted / 4000.0))


def _create_or_expand_camp(
    engine: WorldEngine,
    source: Settlement,
    host: Settlement,
    people: int,
    ancestry: dict[object, int],
) -> RefugeeCamp | None:
    if people <= 0:
        return None
    for camp in engine.world.refugee_camps.values():
        if (
            camp.status != CampStatus.CLOSED
            and camp.host_settlement_id == host.id
            and camp.origin_kingdom_id == source.kingdom_id
        ):
            camp.people += people
            _add_ancestry(camp.ancestry_population, ancestry)
            camp.last_arrival_at = engine.world.date.model_copy(deep=True)
            return camp

    camp = RefugeeCamp(
        id=engine.world.new_entity_id("camp"),
        host_settlement_id=host.id,
        host_kingdom_id=host.kingdom_id,
        origin_kingdom_id=source.kingdom_id,
        people=people,
        ancestry_population=dict(ancestry),
        created_at=engine.world.date.model_copy(deep=True),
        last_arrival_at=engine.world.date.model_copy(deep=True),
    )
    engine.world.refugee_camps[camp.id] = camp
    engine.emit(
        "REFUGEE_CAMP_FOUNDED",
        f"A refugee camp of {people:,} people formed outside {host.name} after entry was restricted.",
        [camp.id, source.id, host.id],
        host.id,
        data={"camp_id": camp.id, "people": people, "origin_kingdom_id": source.kingdom_id, "host_kingdom_id": host.kingdom_id},
        importance=0.66,
    )
    return camp


def update_refugee_camps(engine: WorldEngine) -> None:
    world = engine.world
    active = 0
    camp_population = 0
    resettled_total = 0

    for camp in list(world.refugee_camps.values()):
        if camp.status == CampStatus.CLOSED or camp.people <= 0:
            continue
        host = world.settlements.get(camp.host_settlement_id)
        kingdom = world.kingdoms.get(camp.host_kingdom_id)
        if not host or not kingdom:
            continue

        camp.months_active += 1
        active += 1
        camp_population += camp.people
        grain = host.resources.get("grain")
        aid_need = camp.people * 0.10
        if grain:
            provided = min(grain.quantity, aid_need)
            grain.quantity -= provided
            coverage = provided / max(1.0, aid_need)
        else:
            coverage = 0.0
        camp.food_security = max(0.05, min(1.0, camp.food_security * 0.75 + coverage * 0.25))
        crowding = camp.people / max(50.0, host.housing_capacity * 0.35)
        camp.health = max(0.10, min(1.0, camp.health + (camp.food_security - 0.55) * 0.04 - max(0.0, crowding - 1.0) * 0.015))
        host.food_security = max(0.05, host.food_security - min(0.025, camp.people / max(1, host.population) * 0.02))
        host.health = max(0.10, host.health - min(0.012, max(0.0, 0.55 - camp.health) * 0.02))

        if camp.health < 0.46:
            rng = engine._rng(f"camp-disease:{camp.id}")
            if rng.random() < min(0.45, 0.12 + (0.46 - camp.health)):
                host.health = max(0.10, host.health - 0.02)
                engine.emit(
                    "CAMP_DISEASE_OUTBREAK",
                    f"Disease spread through the refugee camp outside {host.name}, straining local healers.",
                    [camp.id, host.id], host.id,
                    data={"camp_id": camp.id, "people": camp.people, "camp_health": camp.health},
                    importance=0.72,
                )

        if kingdom.refugee_policy != RefugeePolicy.REJECT and kingdom.border_policy != BorderPolicy.CLOSED:
            free_capacity = max(0, host.housing_capacity - host.population)
            rate = 0.08 if kingdom.refugee_policy == RefugeePolicy.WELCOME else 0.03
            resettle = min(free_capacity, max(0, int(camp.people * rate)), 120)
            if resettle > 0:
                allocations = _take_camp_ancestry(camp, resettle)
                _add_ancestry(host.ancestry_population, allocations)
                camp.people -= resettle
                host.population += resettle
                resettled_total += resettle
                camp.status = CampStatus.RESETTLING
                _apply_arrival_pressure(host, resettle)
                engine.emit(
                    "REFUGEE_RESETTLED",
                    f"{resettle:,} refugees from {camp.id} were resettled in {host.name}.",
                    [camp.id, host.id], host.id,
                    data={"camp_id": camp.id, "people": resettle, "host_kingdom_id": kingdom.id},
                    importance=0.46,
                )

        if camp.people <= 0:
            camp.people = 0
            camp.status = CampStatus.CLOSED
            active -= 1
            engine.emit(
                "REFUGEE_CAMP_CLOSED",
                f"The refugee camp outside {host.name} closed after its remaining residents resettled.",
                [camp.id, host.id], host.id, importance=0.42,
            )

    world.metrics["active_refugee_camps"] = float(max(0, active))
    world.metrics["refugee_camp_population"] = float(sum(c.people for c in world.refugee_camps.values() if c.status != CampStatus.CLOSED))
    world.metrics["refugees_resettled_last_month"] = float(resettled_total)


def _take_camp_ancestry(camp: RefugeeCamp, amount: int) -> dict[object, int]:
    if amount <= 0 or camp.people <= 0:
        return {}
    fake = type("CampPopulation", (), {})()
    fake.ancestry_population = camp.ancestry_population
    return _take_ancestry(fake, amount, camp.people)


def run_migration_cycle(engine: WorldEngine) -> None:
    """Move population monthly, respecting border/refugee policy and camp overflow."""
    world = engine.world
    if len(world.settlements) < 2:
        world.metrics["migration_last_month"] = 0.0
        world.metrics["refugees_last_month"] = 0.0
        return

    active_wars = world.active_wars()
    war_kingdoms = {
        kingdom_id
        for war in active_wars
        for kingdom_id in (war.attacker_kingdom_id, war.defender_kingdom_id)
    }

    sources = sorted(
        world.settlements.values(),
        key=lambda settlement: _push_score(settlement, settlement.kingdom_id in war_kingdoms),
        reverse=True,
    )
    max_flows = max(1, min(12, len(world.settlements) // 12))
    total_migrants = 0
    total_refugees = 0
    accepted_refugees = 0
    rejected_refugees = 0
    flows = 0

    for source in sources:
        if flows >= max_flows or source.population <= 30:
            break

        source_at_war = source.kingdom_id in war_kingdoms
        pressure = _push_score(source, source_at_war)
        if pressure < 0.24:
            continue

        candidates: list[tuple[float, Settlement, float]] = []
        for destination in world.settlements.values():
            if destination.id == source.id:
                continue
            free_capacity = destination.housing_capacity - destination.population
            acceptance = _border_acceptance(engine, source, destination, source_at_war)
            if not source_at_war and acceptance <= 0:
                continue
            if not source_at_war and free_capacity < 2:
                continue
            if (
                destination.food_security <= source.food_security + 0.08
                and destination.stability <= source.stability + 0.08
            ):
                continue
            travel_cost = _travel_cost(engine, source, destination)
            score = _pull_score(destination, travel_cost, destination.kingdom_id in war_kingdoms)
            if source_at_war and destination.kingdom_id not in war_kingdoms:
                score += 0.22
            if source.kingdom_id != destination.kingdom_id:
                score += (acceptance - 0.5) * 0.18
            candidates.append((score, destination, acceptance))

        if not candidates:
            continue

        _, destination, acceptance = max(candidates, key=lambda item: item[0])
        free_capacity = max(0, destination.housing_capacity - destination.population)
        target_rate = min(0.012, 0.002 + pressure * 0.004)
        desired = min(max(1, int(source.population * target_rate)), 250, max(0, source.population - 25))
        if desired <= 0:
            continue

        if source_at_war:
            accepted = min(free_capacity, int(round(desired * acceptance)))
            camped = desired - accepted
            amount = desired
        else:
            amount = min(desired, free_capacity, max(0, int(free_capacity * acceptance)))
            accepted = amount
            camped = 0
        if amount <= 0:
            continue

        source_population_before = source.population
        allocations = _take_ancestry(source, amount, source_population_before)
        accepted_ancestry, camp_ancestry = _split_ancestry(allocations, accepted, amount)
        source.population -= amount
        if accepted:
            destination.population += accepted
            _add_ancestry(destination.ancestry_population, accepted_ancestry)
            _apply_arrival_pressure(destination, accepted)
        camp = _create_or_expand_camp(engine, source, destination, camped, camp_ancestry) if camped else None

        moved_npcs = _move_persistent_npcs(
            engine, source, destination, accepted, source_population_before, source_at_war,
        )
        reason = _reason(source, source_at_war)
        event_type = "REFUGEE_MOVEMENT" if source_at_war else "MIGRATION"
        verb = "fled" if source_at_war else "moved"

        engine.emit(
            event_type,
            f"{amount:,} people {verb} from {source.name}; {accepted:,} entered {destination.name}" + (f" and {camped:,} remained in a border camp." if camped else "."),
            [source.id, destination.id, *moved_npcs, *([camp.id] if camp else [])],
            destination.id,
            data={
                "origin_settlement_id": source.id,
                "destination_settlement_id": destination.id,
                "origin_region_id": source.region_id,
                "destination_region_id": destination.region_id,
                "origin_kingdom_id": source.kingdom_id,
                "destination_kingdom_id": destination.kingdom_id,
                "people": amount,
                "accepted_people": accepted,
                "camped_people": camped,
                "camp_id": camp.id if camp else None,
                "persistent_npc_ids": moved_npcs,
                "reason": reason,
                "refugee": source_at_war,
                "border_policy": world.kingdoms[destination.kingdom_id].border_policy.value,
                "refugee_policy": world.kingdoms[destination.kingdom_id].refugee_policy.value,
            },
            importance=0.68 if source_at_war else 0.36,
        )

        if source_at_war:
            _record_refugee_diplomacy(engine, source, destination, accepted, camped)
            if camped:
                engine.emit(
                    "BORDER_REJECTION",
                    f"{destination.kingdom_id} restricted entry for {camped:,} refugees fleeing {source.name}.",
                    [source.kingdom_id, destination.kingdom_id, source.id, destination.id], destination.id,
                    data={"people": camped, "camp_id": camp.id if camp else None}, importance=0.58,
                )
            elif accepted:
                engine.emit(
                    "REFUGEE_ACCEPTED",
                    f"{destination.kingdom_id} admitted {accepted:,} refugees fleeing {source.name}.",
                    [source.kingdom_id, destination.kingdom_id, source.id, destination.id], destination.id,
                    data={"people": accepted}, importance=0.44,
                )

        total_migrants += amount
        if source_at_war:
            total_refugees += amount
            accepted_refugees += accepted
            rejected_refugees += camped
        flows += 1

    world.metrics["migration_last_month"] = float(total_migrants)
    world.metrics["refugees_last_month"] = float(total_refugees)
    world.metrics["refugees_accepted_last_month"] = float(accepted_refugees)
    world.metrics["refugees_rejected_last_month"] = float(rejected_refugees)
    world.metrics["migration_flows_last_month"] = float(flows)
