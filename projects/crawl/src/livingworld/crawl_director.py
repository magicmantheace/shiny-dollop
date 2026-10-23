from __future__ import annotations

from hashlib import sha256
from typing import Any

from .crawl_domain import Crawl, ParticipationStatus
from .crawl_service import CrawlLifecycleService
from .gameplay_domain import EncounterState, EncounterStatus, EncounterType
from .item_system import generate_item


DIRECTOR_STATE_KEY = "_crawl_director"

INTERVENTION_COSTS = {
    "announcement": 2.0,
    "reveal_route": 8.0,
    "spawn_resource_opportunity": 12.0,
    "schedule_hazard": 16.0,
}


def _state(crawl: Crawl) -> dict[str, Any]:
    state = crawl.modifiers.setdefault(DIRECTOR_STATE_KEY, {})
    state.setdefault("spent_by_floor", {})
    state.setdefault("last_intervention_tick", -999999)
    state.setdefault("interventions", [])
    state.setdefault("position_snapshots", {})
    return state


def _stable_roll(*parts: object) -> float:
    payload = ":".join(str(part) for part in parts).encode("utf-8")
    return int(sha256(payload).hexdigest()[:12], 16) / 0xFFFFFFFFFFFF


def _floor_spent(crawl: Crawl, floor_number: int) -> float:
    return float(_state(crawl)["spent_by_floor"].get(str(floor_number), 0.0))


def remaining_budget(crawl: Crawl, floor_number: int | None = None) -> float:
    number = floor_number or crawl.current_floor
    return max(0.0, float(crawl.floors[number].director_budget) - _floor_spent(crawl, number))


def director_metrics(crawl: Crawl) -> dict[str, float]:
    active = [p for p in crawl.participants.values() if p.status == ParticipationStatus.ACTIVE and p.current_floor == crawl.current_floor]
    if not active:
        return {"active": 0.0, "average_health": 0.0, "average_stamina": 0.0, "location_concentration": 0.0, "resolved_encounter_ratio": 1.0, "stagnation_ratio": 0.0}
    occupancy: dict[str, int] = {}
    for p in active:
        if p.current_location_id is not None:
            occupancy[p.current_location_id] = occupancy.get(p.current_location_id, 0) + 1
    floor_encounters = [e for e in crawl.encounters.values() if e.floor_number == crawl.current_floor]
    resolved_ratio = sum(e.status in {EncounterStatus.RESOLVED, EncounterStatus.FAILED} for e in floor_encounters) / len(floor_encounters) if floor_encounters else 0.0
    state = _state(crawl)
    previous = state["position_snapshots"]
    unchanged = 0
    for p in active:
        if previous.get(p.npc_id) == p.current_location_id:
            unchanged += 1
        previous[p.npc_id] = p.current_location_id
    return {
        "active": float(len(active)),
        "average_health": round(sum(p.health for p in active) / len(active), 4),
        "average_stamina": round(sum(p.gameplay.stamina for p in active) / len(active), 4),
        "location_concentration": round(max(occupancy.values(), default=0) / len(active), 4),
        "resolved_encounter_ratio": round(resolved_ratio, 4),
        "stagnation_ratio": round(unchanged / len(active), 4),
        "floor_danger": round(crawl.floors[crawl.current_floor].danger_level, 4),
    }


def _pick_underused_location(crawl: Crawl) -> str | None:
    floor = crawl.floors[crawl.current_floor]
    occupancy = {location_id: 0 for location_id in floor.locations}
    for p in crawl.participants.values():
        if p.status == ParticipationStatus.ACTIVE and p.current_floor == crawl.current_floor and p.current_location_id in occupancy:
            occupancy[p.current_location_id] += 1
    candidates = [location_id for location_id in floor.locations if location_id not in floor.exit_location_ids and location_id != floor.entrance_location_id]
    return min(candidates, key=lambda location_id: (occupancy.get(location_id, 0), location_id)) if candidates else None


def _pick_populated_location(crawl: Crawl) -> str | None:
    floor = crawl.floors[crawl.current_floor]
    occupancy: dict[str, int] = {}
    for p in crawl.participants.values():
        if p.status != ParticipationStatus.ACTIVE or p.current_floor != crawl.current_floor:
            continue
        if p.current_location_id is None or p.current_location_id in floor.exit_location_ids:
            continue
        occupancy[p.current_location_id] = occupancy.get(p.current_location_id, 0) + 1
    return max(occupancy, key=lambda location_id: (occupancy[location_id], location_id)) if occupancy else None


def _spend(crawl: Crawl, action: str) -> None:
    state = _state(crawl)
    key = str(crawl.current_floor)
    state["spent_by_floor"][key] = round(float(state["spent_by_floor"].get(key, 0.0)) + INTERVENTION_COSTS[action], 4)
    state["last_intervention_tick"] = crawl.current_tick
    state["interventions"].append({"tick": crawl.current_tick, "floor": crawl.current_floor, "action": action, "cost": INTERVENTION_COSTS[action]})
    del state["interventions"][:-500]


def _can_spend(crawl: Crawl, action: str) -> bool:
    return remaining_budget(crawl) + 1e-9 >= INTERVENTION_COSTS[action]


def _spawn_director_encounter(crawl: Crawl, *, location_id: str, encounter_type: EncounterType) -> EncounterState:
    existing = [e for e in crawl.encounters.values() if e.floor_number == crawl.current_floor and e.location_id == location_id and e.status == EncounterStatus.DORMANT]
    if existing:
        return min(existing, key=lambda item: item.id)
    digest = sha256(f"{crawl.seed}:director:{crawl.current_floor}:{crawl.current_tick}:{location_id}:{encounter_type.value}".encode("utf-8")).hexdigest()[:20]
    encounter = EncounterState(
        id=f"director_encounter_{digest}",
        floor_number=crawl.current_floor,
        location_id=location_id,
        type=encounter_type,
        difficulty=max(0.05, min(1.0, crawl.floors[crawl.current_floor].danger_level * 0.65)),
        trigger={"type": "director_scheduled", "once": True},
        possible_outcomes=["resolved", "ignored", "failed"],
        failure_consequences={"stress": 0.06},
    )
    crawl.encounters[encounter.id] = encounter
    if encounter_type == EncounterType.RESOURCE_DILEMMA:
        item = generate_item(crawl.seed, source_id=encounter.id, index=0, floor_number=crawl.current_floor, holder=encounter.id)
        crawl.items[item.id] = item
        encounter.reward_item_ids.append(item.id)
    return encounter


class CrawlDirector:
    def __init__(self, lifecycle: CrawlLifecycleService, *, minimum_interval: int = 8) -> None:
        self.lifecycle = lifecycle
        self.minimum_interval = max(1, minimum_interval)

    def evaluate(self, crawl: Crawl) -> dict[str, Any] | None:
        if crawl.status.value != "running":
            return None
        state = _state(crawl)
        if crawl.current_tick - int(state["last_intervention_tick"]) < self.minimum_interval:
            return None
        metrics = director_metrics(crawl)
        roll = _stable_roll(crawl.seed, crawl.current_floor, crawl.current_tick, "director")
        action: str | None = None
        location_id: str | None = None
        details: dict[str, Any] = {"metrics": metrics}
        if metrics["active"] <= 0:
            return None
        if metrics["stagnation_ratio"] >= 0.88 and _can_spend(crawl, "reveal_route"):
            action = "reveal_route"
        elif metrics["average_health"] >= 0.78 and metrics["resolved_encounter_ratio"] >= 0.55 and roll > 0.45 and _can_spend(crawl, "schedule_hazard"):
            action = "schedule_hazard"
        elif metrics["average_health"] <= 0.42 and _can_spend(crawl, "spawn_resource_opportunity"):
            action = "spawn_resource_opportunity"
        elif metrics["location_concentration"] >= 0.60 and _can_spend(crawl, "announcement"):
            action = "announcement"
        elif not any(int(entry.get("floor", -1)) == crawl.current_floor for entry in state["interventions"]) and _can_spend(crawl, "announcement"):
            action = "announcement"
            details["reason"] = "floor_status"
        else:
            return None
        if action == "reveal_route":
            location_id = _pick_underused_location(crawl)
            if location_id is None:
                return None
            revealed_to: list[str] = []
            floor = crawl.floors[crawl.current_floor]
            for npc_id, p in sorted(crawl.participants.items()):
                if p.status != ParticipationStatus.ACTIVE or p.agent is None or p.current_floor != crawl.current_floor or p.current_location_id is None:
                    continue
                knowledge = p.agent.knowledge.get(p.current_location_id)
                if knowledge is None or location_id not in floor.locations[p.current_location_id].adjacency:
                    continue
                knowledge.known_neighbors[location_id] = floor.locations[p.current_location_id].adjacency[location_id]
                revealed_to.append(npc_id)
                if len(revealed_to) >= 5:
                    break
            details["revealed_to"] = revealed_to
            details["target_location_id"] = location_id
        elif action == "spawn_resource_opportunity":
            location_id = _pick_underused_location(crawl)
            if location_id is None:
                return None
            encounter = _spawn_director_encounter(crawl, location_id=location_id, encounter_type=EncounterType.RESOURCE_DILEMMA)
            details["encounter_id"] = encounter.id
            details["reward_item_ids"] = list(encounter.reward_item_ids)
        elif action == "schedule_hazard":
            location_id = _pick_populated_location(crawl)
            if location_id is None:
                return None
            encounter = _spawn_director_encounter(crawl, location_id=location_id, encounter_type=EncounterType.HAZARD)
            details["encounter_id"] = encounter.id
        elif action == "announcement":
            location_id = _pick_populated_location(crawl)
            details["message"] = "The Crawl Director reports a pacing update; route and risk conditions remain authoritative."
        _spend(crawl, action)
        event = self.lifecycle._record(crawl, "DIRECTOR_INTERVENTION", f"Crawl Director applied {action.replace('_', ' ')}.", location_id=location_id, data={"action": action, "cost": INTERVENTION_COSTS[action], "remaining_budget": remaining_budget(crawl), **details})
        return {"action": action, "event_id": event.id, "location_id": location_id, **details}
