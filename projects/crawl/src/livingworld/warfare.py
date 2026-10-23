from __future__ import annotations

import math
from collections import deque
from typing import TYPE_CHECKING

from .domain import Settlement, SettlementType, War, WarState

if TYPE_CHECKING:
    from .simulation import WorldEngine


def _distance(a: Settlement, b: Settlement) -> float:
    return math.hypot(a.position.x - b.position.x, a.position.y - b.position.y)


def _active_settlements(engine: WorldEngine, kingdom_id: str) -> list[Settlement]:
    return [
        settlement for settlement in engine.world.settlements.values()
        if settlement.kingdom_id == kingdom_id
        and settlement.population > 0
        and settlement.type != SettlementType.RUIN
    ]


def _armies(engine: WorldEngine, kingdom_id: str):
    kingdom = engine.world.kingdoms.get(kingdom_id)
    if not kingdom:
        return []
    return [
        engine.world.armies[army_id]
        for army_id in kingdom.army_ids
        if army_id in engine.world.armies and engine.world.armies[army_id].active
    ]


def _route_graph(engine: WorldEngine, kingdom_id: str) -> dict[str, set[str]]:
    world = engine.world
    graph: dict[str, set[str]] = {}
    controlled = {
        settlement.id for settlement in world.settlements.values()
        if settlement.kingdom_id == kingdom_id or settlement.occupied_by_kingdom_id == kingdom_id
    }
    for route in world.trade_routes.values():
        if not route.active:
            continue
        if route.origin_settlement_id not in controlled or route.destination_settlement_id not in controlled:
            continue
        graph.setdefault(route.origin_settlement_id, set()).add(route.destination_settlement_id)
        graph.setdefault(route.destination_settlement_id, set()).add(route.origin_settlement_id)
    return graph


def _connected(graph: dict[str, set[str]], start: str, targets: set[str]) -> bool:
    if start in targets:
        return True
    queue = deque([start])
    seen = {start}
    while queue:
        current = queue.popleft()
        for nxt in graph.get(current, set()):
            if nxt in targets:
                return True
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return False


def refresh_fronts(engine: WorldEngine, war: War) -> list[str]:
    world = engine.world
    attacker = _active_settlements(engine, war.attacker_kingdom_id)
    defender = _active_settlements(engine, war.defender_kingdom_id)
    if not attacker or not defender:
        war.front_settlement_ids = []
        return []

    pairs: list[tuple[float, int, str, str]] = []
    for a in attacker:
        for d in defender:
            distance = _distance(a, d)
            frontier_bonus = int(a.frontier) + int(d.frontier) + int(a.type == SettlementType.FORT) + int(d.type == SettlementType.FORT)
            if distance <= 48.0:
                pairs.append((distance, -frontier_bonus, a.id, d.id))
    if not pairs:
        nearest = min(
            ((_distance(a, d), 0, a.id, d.id) for a in attacker for d in defender),
            key=lambda item: (item[0], item[2], item[3]),
        )
        pairs = [nearest]

    fronts: list[str] = []
    for _, _, a_id, d_id in sorted(pairs)[:4]:
        for settlement_id in (a_id, d_id):
            if settlement_id not in fronts:
                fronts.append(settlement_id)
    war.front_settlement_ids = fronts[:6]

    attacker_targets = [world.settlements[sid] for sid in war.front_settlement_ids if world.settlements[sid].kingdom_id == war.defender_kingdom_id]
    defender_targets = [world.settlements[sid] for sid in war.front_settlement_ids if world.settlements[sid].kingdom_id == war.defender_kingdom_id]
    if not attacker_targets:
        attacker_targets = defender
    if not defender_targets:
        defender_targets = defender

    for army in _armies(engine, war.attacker_kingdom_id):
        location = world.settlements.get(army.location_settlement_id)
        if location and attacker_targets:
            target = min(attacker_targets, key=lambda s: (_distance(location, s), s.id))
            if army.location_settlement_id != target.id:
                army.destination_settlement_id = target.id
    for army in _armies(engine, war.defender_kingdom_id):
        location = world.settlements.get(army.location_settlement_id)
        if location and defender_targets:
            target = min(defender_targets, key=lambda s: (_distance(location, s), s.id))
            if army.location_settlement_id != target.id:
                army.destination_settlement_id = target.id
    return war.front_settlement_ids


def update_army_supply(engine: WorldEngine, war: War) -> None:
    world = engine.world
    for kingdom_id in (war.attacker_kingdom_id, war.defender_kingdom_id):
        kingdom = world.kingdoms.get(kingdom_id)
        if not kingdom:
            continue
        graph = _route_graph(engine, kingdom_id)
        friendly = {
            settlement.id for settlement in world.settlements.values()
            if settlement.kingdom_id == kingdom_id
            and settlement.population > 0
            and settlement.type != SettlementType.RUIN
        }
        supply_candidates = {
            settlement.id for settlement in world.settlements.values()
            if settlement.id in friendly
            and settlement.food_security >= 0.30
            and settlement.resources.get("grain") is not None
            and settlement.resources["grain"].quantity > 5
        }
        for army in _armies(engine, kingdom_id):
            location = world.settlements.get(army.location_settlement_id)
            if not location:
                army.supply_efficiency = 0.15
                continue
            if location.id in supply_candidates:
                efficiency = 1.0
                source = location
            else:
                connected_sources = [world.settlements[sid] for sid in supply_candidates if _connected(graph, location.id, {sid})]
                if connected_sources:
                    source = min(connected_sources, key=lambda s: (_distance(location, s), s.id))
                    efficiency = max(0.55, 0.92 - _distance(location, source) / 180.0)
                else:
                    source = min((world.settlements[sid] for sid in supply_candidates), key=lambda s: (_distance(location, s), s.id), default=None)
                    efficiency = 0.28 if source and _distance(location, source) <= 40 else 0.12
            army.supply_efficiency = max(0.05, min(1.0, efficiency))
            army.supply_source_settlement_id = source.id if source else None
            if source and army.supply_efficiency >= 0.45:
                grain = source.resources.get("grain")
                needed = max(1.0, army.troop_count / 220.0)
                drawn = min(needed, grain.quantity if grain else 0.0)
                if grain:
                    grain.quantity -= drawn
                army.supply_days = min(45.0, army.supply_days + drawn * army.supply_efficiency * 0.9)
            if army.supply_efficiency < 0.3:
                army.morale = max(0.1, army.morale - 0.025)
                army.readiness = max(0.1, army.readiness - 0.018)


def _army_power(army) -> float:
    return army.troop_count * army.readiness * army.morale * max(0.25, army.supply_efficiency)


def _settlement_defense(settlement: Settlement) -> float:
    defenses = settlement.infrastructure.get("defenses", 0.25)
    type_bonus = 0.42 if settlement.type == SettlementType.FORT else 0.18 if settlement.type in {SettlementType.TOWN, SettlementType.CITY} else 0.08
    return max(0.15, min(1.6, 0.35 + defenses * 0.75 + type_bonus + settlement.stability * 0.15))


def _apply_battle(engine: WorldEngine, war: War) -> None:
    rng = engine._rng(f"front-battle:{war.id}:{war.months_active}")
    attackers = _armies(engine, war.attacker_kingdom_id)
    defenders = _armies(engine, war.defender_kingdom_id)
    if not attackers or not defenders:
        return

    front_set = set(war.front_settlement_ids)
    a_front = [army for army in attackers if army.location_settlement_id in front_set]
    d_front = [army for army in defenders if army.location_settlement_id in front_set]
    if not a_front or not d_front:
        return
    a_power = sum(_army_power(army) for army in a_front) * rng.uniform(0.90, 1.10)
    d_power = sum(_army_power(army) for army in d_front) * rng.uniform(0.92, 1.12)
    total = max(1.0, a_power + d_power)
    intensity = rng.uniform(0.012, 0.042)
    a_total = sum(army.troop_count for army in a_front)
    d_total = sum(army.troop_count for army in d_front)
    a_loss = max(0, int(a_total * intensity * d_power / total))
    d_loss = max(0, int(d_total * intensity * a_power / total))
    engine._apply_army_losses(a_front, a_loss)
    engine._apply_army_losses(d_front, d_loss)
    war.casualties[war.attacker_kingdom_id] = war.casualties.get(war.attacker_kingdom_id, 0) + a_loss
    war.casualties[war.defender_kingdom_id] = war.casualties.get(war.defender_kingdom_id, 0) + d_loss
    delta = (d_loss - a_loss) / max(1, a_loss + d_loss) * 8.0
    war.attacker_score += delta
    war.defender_score -= delta
    engine.emit(
        "FRONT_BATTLE",
        f"The front shifted after a battle costing {a_loss + d_loss:,} soldiers.",
        [war.id, war.attacker_kingdom_id, war.defender_kingdom_id, *war.front_settlement_ids[:4]],
        data={"attacker_losses": a_loss, "defender_losses": d_loss, "attacker_score": war.attacker_score},
        importance=0.72,
    )


def _occupy(engine: WorldEngine, war: War, settlement: Settlement, occupier_id: str) -> None:
    if settlement.occupied_by_kingdom_id == occupier_id:
        return
    settlement.occupied_by_kingdom_id = occupier_id
    settlement.occupation_months = 0
    settlement.besieged_by_kingdom_id = None
    settlement.siege_progress = 0.0
    war.siege_progress.pop(settlement.id, None)
    war.occupation_by_settlement[settlement.id] = occupier_id
    if settlement.id not in war.occupied_settlement_ids:
        war.occupied_settlement_ids.append(settlement.id)
    for claim in engine.world.territory_claims.values():
        if claim.get("settlement_id") == settlement.id and claim.get("status") != "abandoned":
            claim["status"] = "occupied"
            claim["occupying_kingdom_id"] = occupier_id
            claim["contested_by_kingdom_ids"] = sorted(set(claim.get("contested_by_kingdom_ids", [])) | {occupier_id})
    settlement.stability = max(0.05, settlement.stability - 0.15)
    engine.emit(
        "SETTLEMENT_OCCUPIED",
        f"{engine.world.kingdoms[occupier_id].name} occupied {settlement.name} after the siege.",
        [war.id, settlement.id, occupier_id, settlement.kingdom_id],
        settlement.id,
        data={"war_id": war.id, "occupier_kingdom_id": occupier_id, "owner_kingdom_id": settlement.kingdom_id},
        importance=0.88,
    )


def update_sieges_and_occupations(engine: WorldEngine, war: War) -> None:
    world = engine.world
    for settlement_id, occupier_id in list(war.occupation_by_settlement.items()):
        settlement = world.settlements.get(settlement_id)
        if not settlement or settlement.type == SettlementType.RUIN:
            war.occupation_by_settlement.pop(settlement_id, None)
            continue
        settlement.occupation_months += 1
        garrison = sum(_army_power(a) for a in _armies(engine, occupier_id) if a.location_settlement_id == settlement.id)
        if garrison <= 0:
            settlement.stability = min(1.0, settlement.stability + 0.03)
            if settlement.occupation_months >= 2:
                settlement.occupied_by_kingdom_id = None
                settlement.occupation_months = 0
                war.occupation_by_settlement.pop(settlement_id, None)
                if settlement_id in war.occupied_settlement_ids:
                    war.occupied_settlement_ids.remove(settlement_id)
                engine.emit("OCCUPATION_BROKEN", f"Occupation of {settlement.name} collapsed after the garrison withdrew.", [war.id, settlement.id], settlement.id, importance=0.62)
        else:
            settlement.stability = max(0.05, settlement.stability - 0.015)
            settlement.food_security = max(0.0, settlement.food_security - 0.01)

    for attacker_id, defender_id in (
        (war.attacker_kingdom_id, war.defender_kingdom_id),
        (war.defender_kingdom_id, war.attacker_kingdom_id),
    ):
        attacking_armies = _armies(engine, attacker_id)
        for army in attacking_armies:
            target = world.settlements.get(army.location_settlement_id)
            if not target or target.kingdom_id != defender_id or target.type == SettlementType.RUIN:
                continue
            if target.occupied_by_kingdom_id == attacker_id:
                continue
            defense_armies = [a for a in _armies(engine, defender_id) if a.location_settlement_id == target.id]
            attack_power = _army_power(army)
            defense_power = sum(_army_power(a) for a in defense_armies)
            settlement_defense = _settlement_defense(target)
            ratio = attack_power / max(1.0, defense_power + target.population * 0.08 * settlement_defense)
            progress = max(0.01, min(0.32, 0.055 * (ratio / (ratio + 50.0)) * max(0.2, army.supply_efficiency) / settlement_defense))
            if army.supply_efficiency < 0.25:
                progress *= 0.35
            current = max(target.siege_progress, war.siege_progress.get(target.id, 0.0))
            current = min(1.0, current + progress)
            target.besieged_by_kingdom_id = attacker_id
            target.siege_progress = current
            war.siege_progress[target.id] = current
            target.food_security = max(0.0, target.food_security - progress * 0.08)
            if current >= 1.0:
                _occupy(engine, war, target, attacker_id)
            elif current >= 0.25:
                engine.emit(
                    "SIEGE_PROGRESS",
                    f"The siege of {target.name} reached {int(current * 100)}% progress.",
                    [war.id, target.id, attacker_id, defender_id],
                    target.id,
                    data={"progress": current, "defense": settlement_defense, "supply_efficiency": army.supply_efficiency},
                    importance=0.48,
                )


def update_war_exhaustion(engine: WorldEngine, war: War) -> None:
    world = engine.world
    war.months_active += 1
    initial_scale = 1_000.0
    a_losses = war.casualties.get(war.attacker_kingdom_id, 0)
    d_losses = war.casualties.get(war.defender_kingdom_id, 0)
    a_supply = [_armies(engine, war.attacker_kingdom_id), _armies(engine, war.defender_kingdom_id)]
    attacker_armies, defender_armies = a_supply
    a_shortage = 1.0 - (sum(a.supply_efficiency for a in attacker_armies) / max(1, len(attacker_armies)))
    d_shortage = 1.0 - (sum(a.supply_efficiency for a in defender_armies) / max(1, len(defender_armies)))
    a_occupied = sum(1 for sid, kid in war.occupation_by_settlement.items() if world.settlements.get(sid) and world.settlements[sid].kingdom_id == war.attacker_kingdom_id and kid == war.defender_kingdom_id)
    d_occupied = sum(1 for sid, kid in war.occupation_by_settlement.items() if world.settlements.get(sid) and world.settlements[sid].kingdom_id == war.defender_kingdom_id and kid == war.attacker_kingdom_id)
    duration = min(0.035, war.months_active * 0.0015)
    war.attacker_exhaustion = min(1.0, war.attacker_exhaustion + duration + min(0.08, a_losses / initial_scale * 0.01) + a_shortage * 0.035 + a_occupied * 0.025)
    war.defender_exhaustion = min(1.0, war.defender_exhaustion + duration + min(0.08, d_losses / initial_scale * 0.01) + d_shortage * 0.035 + d_occupied * 0.025)


def _transfer_settlement(engine: WorldEngine, settlement_id: str, winner_id: str, loser_id: str, war: War) -> None:
    world = engine.world
    settlement = world.settlements[settlement_id]
    winner = world.kingdoms[winner_id]
    loser = world.kingdoms[loser_id]
    if settlement.id == loser.capital_settlement_id:
        return
    if settlement.id in loser.settlement_ids:
        loser.settlement_ids.remove(settlement.id)
    if settlement.id not in winner.settlement_ids:
        winner.settlement_ids.append(settlement.id)
    settlement.kingdom_id = winner_id
    settlement.occupied_by_kingdom_id = None
    settlement.occupation_months = 0
    settlement.besieged_by_kingdom_id = None
    settlement.siege_progress = 0.0
    for npc in world.npcs.values():
        if npc.alive and npc.settlement_id == settlement.id:
            npc.kingdom_id = winner_id
    for claim_id, claim in world.territory_claims.items():
        if claim.get("settlement_id") == settlement.id:
            old_owner = claim.get("kingdom_id")
            claim["kingdom_id"] = winner_id
            claim["status"] = "active"
            claim.pop("occupying_kingdom_id", None)
            claim["contested_by_kingdom_ids"] = []
            if old_owner in world.kingdoms and claim_id in world.kingdoms[old_owner].claims:
                world.kingdoms[old_owner].claims.remove(claim_id)
            if claim_id not in winner.claims:
                winner.claims.append(claim_id)
    engine.emit("BORDER_CHANGED", f"{settlement.name} was ceded from {loser.name} to {winner.name} in the peace settlement.", [war.id, settlement.id, winner_id, loser_id], settlement.id, importance=0.9)


def end_war(engine: WorldEngine, war: War, winner_id: str | None, reason: str) -> None:
    if war.state != WarState.ACTIVE:
        return
    world = engine.world
    attacker = world.kingdoms[war.attacker_kingdom_id]
    defender = world.kingdoms[war.defender_kingdom_id]
    terms: dict = {"winner_id": winner_id, "reason": reason, "ceded_settlement_ids": [], "vassalized_kingdom_id": None}
    if winner_id:
        loser_id = defender.id if winner_id == attacker.id else attacker.id
        winner = world.kingdoms[winner_id]
        loser = world.kingdoms[loser_id]
        occupied = [
            sid for sid, occupier in war.occupation_by_settlement.items()
            if occupier == winner_id and sid in world.settlements and world.settlements[sid].kingdom_id == loser_id
        ]
        occupied.sort(key=lambda sid: (world.settlements[sid].type == SettlementType.FORT, world.settlements[sid].frontier, world.settlements[sid].population), reverse=True)
        transferable = [sid for sid in occupied if sid != loser.capital_settlement_id][:3]
        if not transferable:
            candidates = [sid for sid in loser.settlement_ids if sid != loser.capital_settlement_id and world.settlements[sid].type != SettlementType.RUIN]
            if candidates and abs(war.attacker_score) >= 35:
                cap = world.settlements[winner.capital_settlement_id]
                transferable = [min(candidates, key=lambda sid: (_distance(cap, world.settlements[sid]), sid))]
        for sid in transferable:
            _transfer_settlement(engine, sid, winner_id, loser_id, war)
        terms["ceded_settlement_ids"] = transferable
        loser_exhaustion = war.defender_exhaustion if loser_id == war.defender_kingdom_id else war.attacker_exhaustion
        decisive = abs(war.attacker_score) >= 60 or loser_exhaustion >= 0.88
        if decisive and len(loser.settlement_ids) <= 5:
            loser.overlord_kingdom_id = winner_id
            terms["vassalized_kingdom_id"] = loser_id
            engine.emit("KINGDOM_VASSALIZED", f"{loser.name} became a vassal of {winner.name} under the peace terms.", [war.id, loser_id, winner_id], loser.capital_settlement_id, importance=0.96)
    for sid in list(war.occupation_by_settlement):
        settlement = world.settlements.get(sid)
        if settlement:
            settlement.occupied_by_kingdom_id = None
            settlement.occupation_months = 0
            settlement.besieged_by_kingdom_id = None
            settlement.siege_progress = 0.0
    war.occupation_by_settlement.clear()
    war.siege_progress.clear()
    war.front_settlement_ids = []
    war.state = WarState.ENDED
    war.ended_at = world.date.model_copy(deep=True)
    war.peace_terms = terms
    for kingdom in (attacker, defender):
        other_id = defender.id if kingdom.id == attacker.id else attacker.id
        relation = kingdom.relations.get(other_id)
        if relation:
            relation.truce_until_year = world.date.year + 3
            relation.opinion = min(relation.opinion, -0.45)
        for army in _armies(engine, kingdom.id):
            army.destination_settlement_id = kingdom.capital_settlement_id
            army.supply_source_settlement_id = kingdom.capital_settlement_id
    if winner_id:
        summary = f"{world.kingdoms[winner_id].name} won the war between {attacker.name} and {defender.name} through {reason}."
    else:
        summary = f"The war between {attacker.name} and {defender.name} ended without a clear victor due to {reason}."
    engine.emit("WAR_ENDED", summary, [war.id, attacker.id, defender.id], data=terms, importance=0.95)


def run_warfare_cycle(engine: WorldEngine) -> None:
    for war in list(engine.world.active_wars()):
        attacker = engine.world.kingdoms.get(war.attacker_kingdom_id)
        defender = engine.world.kingdoms.get(war.defender_kingdom_id)
        if not attacker or not defender:
            war.state = WarState.ENDED
            continue
        a_armies = _armies(engine, attacker.id)
        d_armies = _armies(engine, defender.id)
        if not a_armies or not d_armies:
            end_war(engine, war, defender.id if not a_armies else attacker.id, "military collapse")
            continue
        refresh_fronts(engine, war)
        update_army_supply(engine, war)
        _apply_battle(engine, war)
        update_sieges_and_occupations(engine, war)
        update_war_exhaustion(engine, war)

        occupation_score = 0.0
        for sid, occupier in war.occupation_by_settlement.items():
            settlement = engine.world.settlements.get(sid)
            if not settlement:
                continue
            value = 10.0 if settlement.frontier else 16.0 if settlement.type == SettlementType.FORT else 22.0
            if occupier == attacker.id and settlement.kingdom_id == defender.id:
                occupation_score += value
            elif occupier == defender.id and settlement.kingdom_id == attacker.id:
                occupation_score -= value
        war.attacker_score += occupation_score * 0.12
        war.defender_score = -war.attacker_score

        if war.attacker_score >= 55 or war.defender_exhaustion >= 0.96:
            end_war(engine, war, attacker.id, "territorial and military advantage")
        elif war.attacker_score <= -55 or war.attacker_exhaustion >= 0.96:
            end_war(engine, war, defender.id, "territorial and military advantage")
        elif war.months_active >= 18 and war.attacker_exhaustion >= 0.72 and war.defender_exhaustion >= 0.72:
            winner_id = attacker.id if war.attacker_score >= 20 else defender.id if war.attacker_score <= -20 else None
            end_war(engine, war, winner_id, "mutual war exhaustion")


def refresh_warfare_metrics(world) -> None:
    wars = world.active_wars()
    world.metrics["active_fronts"] = float(sum(len(war.front_settlement_ids) for war in wars))
    world.metrics["active_sieges"] = float(sum(len(war.siege_progress) for war in wars))
    world.metrics["occupied_settlements"] = float(sum(len(war.occupation_by_settlement) for war in wars))
    world.metrics["avg_war_exhaustion"] = float(
        sum((war.attacker_exhaustion + war.defender_exhaustion) / 2 for war in wars) / max(1, len(wars))
    )
