from __future__ import annotations

import heapq
from hashlib import sha256

from .crawl_domain import CrawlFloor, CrawlerParticipation, LocationKind
from .crawler_decision import CrawlerDecision
from .crawler_domain import LocationKnowledge


def _deterministic_roll(*parts: object) -> float:
    payload = ":".join(str(part) for part in parts).encode("utf-8")
    return int(sha256(payload).hexdigest()[:8], 16) / 0xFFFFFFFF


def _hidden_neighbor(location_tags: list[str], neighbor_id: str) -> bool:
    return f"hidden_path:{neighbor_id}" in location_tags


def perceive(participant: CrawlerParticipation, floor: CrawlFloor, tick: int) -> list[str]:
    agent = participant.agent
    if agent is None or participant.current_location_id is None:
        return []
    current = floor.locations[participant.current_location_id]
    visible_neighbors: dict[str, float] = {}
    discovered: list[str] = []
    for neighbor_id, cost in current.adjacency.items():
        hidden = _hidden_neighbor(current.environmental_tags, neighbor_id)
        if hidden:
            detection = 0.18 + agent.skills.perception * 0.62 + agent.skills.navigation * 0.20
            roll = _deterministic_roll(floor.seed, participant.npc_id, current.id, neighbor_id)
            if roll > detection:
                continue
        visible_neighbors[neighbor_id] = cost
    existing = agent.knowledge.get(current.id)
    visits = (existing.visits if existing else 0) + 1
    agent.knowledge[current.id] = LocationKnowledge(
        location_id=current.id,
        last_observed_tick=tick,
        confidence=1.0,
        known_neighbors=visible_neighbors,
        tags=list(current.environmental_tags),
        hazard_tags=list(current.hazards),
        believed_safe=current.kind in {LocationKind.ENTRANCE, LocationKind.SAFE_AREA},
        believed_exit=current.kind == LocationKind.EXIT,
        visits=visits,
    )
    for neighbor_id in visible_neighbors:
        if neighbor_id in agent.knowledge:
            continue
        neighbor = floor.locations[neighbor_id]
        confidence = max(0.35, min(0.9, 0.35 + agent.skills.perception * neighbor.visibility * 0.55))
        agent.knowledge[neighbor_id] = LocationKnowledge(
            location_id=neighbor_id,
            last_observed_tick=tick,
            confidence=confidence,
            known_neighbors={},
            tags=[tag for tag in neighbor.environmental_tags if not tag.startswith("hidden_path:")],
            hazard_tags=list(neighbor.hazards) if confidence >= 0.62 else [],
            believed_safe=neighbor.kind == LocationKind.SAFE_AREA and confidence >= 0.5,
            believed_exit=neighbor.kind == LocationKind.EXIT and confidence >= 0.5,
            visits=0,
        )
        discovered.append(neighbor_id)
    local_danger = min(1.0, floor.danger_level + 0.12 * len(current.hazards))
    agent.needs.perceived_danger = round(local_danger, 4)
    return discovered


def _known_path(participant: CrawlerParticipation, start_id: str, targets: set[str]) -> list[str] | None:
    agent = participant.agent
    if agent is None or not targets:
        return None
    queue: list[tuple[float, str, list[str]]] = [(0.0, start_id, [start_id])]
    best: dict[str, float] = {start_id: 0.0}
    while queue:
        cost, current, path = heapq.heappop(queue)
        if current in targets:
            return path
        knowledge = agent.knowledge.get(current)
        if knowledge is None:
            continue
        for neighbor, edge_cost in knowledge.known_neighbors.items():
            candidate = cost + edge_cost
            if candidate >= best.get(neighbor, float("inf")):
                continue
            best[neighbor] = candidate
            heapq.heappush(queue, (candidate, neighbor, [*path, neighbor]))
    return None


def _current_floor_exploration_complete(participant: CrawlerParticipation, floor: CrawlFloor) -> bool:
    agent = participant.agent
    if agent is None:
        return False
    known_non_exits = [knowledge for location_id, knowledge in agent.knowledge.items() if location_id in floor.locations and not knowledge.believed_exit]
    return bool(known_non_exits) and all(knowledge.visits > 0 for knowledge in known_non_exits)


def _known_unvisited_non_exit_targets(participant: CrawlerParticipation, floor: CrawlFloor) -> set[str]:
    agent = participant.agent
    if agent is None:
        return set()
    return {location_id for location_id, knowledge in agent.knowledge.items() if location_id in floor.locations and not knowledge.believed_exit and knowledge.visits == 0}


def _safety_critical(participant: CrawlerParticipation) -> bool:
    agent = participant.agent
    if agent is None:
        return participant.health <= 0.40
    return participant.health <= 0.40 or agent.needs.stamina <= 0.20 or agent.needs.stress >= 0.75


def choose_destination(participant: CrawlerParticipation, floor: CrawlFloor, decision: CrawlerDecision) -> str | None:
    agent = participant.agent
    current_id = participant.current_location_id
    if agent is None or current_id is None:
        return None
    current = floor.locations[current_id]
    knowledge = agent.knowledge.get(current_id)
    visible = knowledge.known_neighbors if knowledge is not None else {}
    if decision.action == "wait":
        return current_id
    if decision.action in {"recover", "seek_safety"} and current.kind == LocationKind.SAFE_AREA:
        return current_id
    known_exits = {item.location_id for item in agent.knowledge.values() if item.location_id in floor.locations and item.believed_exit}
    if known_exits and (decision.action == "seek_exit" or _current_floor_exploration_complete(participant, floor)):
        path = _known_path(participant, current_id, known_exits)
        if path and len(path) > 1:
            return path[1]
    if decision.action == "recover":
        if _safety_critical(participant):
            targets = {item.location_id for item in agent.knowledge.values() if item.location_id in floor.locations and item.believed_safe}
            path = _known_path(participant, current_id, targets)
            if path and len(path) > 1:
                return path[1]
        return current_id
    if decision.action == "seek_safety" and _safety_critical(participant):
        targets = {item.location_id for item in agent.knowledge.values() if item.location_id in floor.locations and item.believed_safe}
        path = _known_path(participant, current_id, targets)
        if path and len(path) > 1:
            return path[1]
    frontier = _known_unvisited_non_exit_targets(participant, floor)
    if frontier:
        path = _known_path(participant, current_id, frontier)
        if path and len(path) > 1:
            return path[1]
    if known_exits:
        path = _known_path(participant, current_id, known_exits)
        if path and len(path) > 1:
            return path[1]
    if decision.action == "seek_safety":
        targets = {item.location_id for item in agent.knowledge.values() if item.location_id in floor.locations and item.believed_safe}
        path = _known_path(participant, current_id, targets)
        if path and len(path) > 1:
            return path[1]
    if not visible:
        return current_id
    ranked = sorted(visible, key=lambda neighbor_id: (agent.knowledge.get(neighbor_id).visits if agent.knowledge.get(neighbor_id) else 0, 1 if agent.knowledge.get(neighbor_id) and agent.knowledge[neighbor_id].hazard_tags else 0, neighbor_id))
    if decision.action == "seek_safety" and agent.traits.caution > 0.65:
        ranked.sort(key=lambda neighbor_id: (0 if agent.knowledge.get(neighbor_id) and agent.knowledge[neighbor_id].believed_safe else 1, 1 if agent.knowledge.get(neighbor_id) and agent.knowledge[neighbor_id].hazard_tags else 0, neighbor_id))
    return ranked[0]


def traverse(participant: CrawlerParticipation, floor: CrawlFloor, destination_id: str) -> float:
    if participant.current_location_id is None:
        raise ValueError("crawler has no current location")
    current = floor.locations[participant.current_location_id]
    if destination_id == current.id:
        return 0.0
    if destination_id not in current.adjacency:
        raise ValueError("destination is not adjacent to crawler location")
    cost = current.adjacency[destination_id]
    participant.current_location_id = destination_id
    participant.floor_statistics["moves"] = participant.floor_statistics.get("moves", 0.0) + 1.0
    participant.floor_statistics["distance_cost"] = participant.floor_statistics.get("distance_cost", 0.0) + cost
    agent = participant.agent
    if agent is not None:
        agent.needs.stamina = max(0.0, agent.needs.stamina - min(0.08, cost * 0.018))
        agent.needs.hunger = min(1.0, agent.needs.hunger + min(0.015, cost * 0.0025))
        destination = floor.locations[destination_id]
        stress_delta = floor.danger_level * 0.008 + len(destination.hazards) * 0.012
        agent.needs.stress = min(1.0, agent.needs.stress + stress_delta)
    return cost


def recover(participant: CrawlerParticipation, floor: CrawlFloor) -> None:
    agent = participant.agent
    if agent is None or participant.current_location_id is None:
        return
    location = floor.locations[participant.current_location_id]
    safe_bonus = 1.0 if location.kind == LocationKind.SAFE_AREA else 0.35
    agent.needs.stamina = min(1.0, agent.needs.stamina + 0.12 * safe_bonus)
    agent.needs.stress = max(0.0, agent.needs.stress - 0.08 * safe_bonus)
    agent.needs.morale = min(1.0, agent.needs.morale + 0.025 * safe_bonus)
    participant.floor_statistics["rests"] = participant.floor_statistics.get("rests", 0.0) + 1.0
