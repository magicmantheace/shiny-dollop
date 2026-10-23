from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from .crawl_domain import Crawl, CrawlEvent, ParticipationStatus
from .semantic_event_ledger import semantic_score


def _public_semantic(event: CrawlEvent) -> dict[str, Any]:
    semantic = event.data.get("semantic", {}) if isinstance(event.data, dict) else {}
    return {
        "importance_score": float(semantic.get("importance_score", 0.0) or 0.0),
        "rarity_score": float(semantic.get("rarity_score", 0.0) or 0.0),
        "danger_level": float(semantic.get("danger_level", 0.0) or 0.0),
        "reversal": bool(semantic.get("reversal", False)),
        "relationship_impact": float(semantic.get("relationship_impact", 0.0) or 0.0),
        "audience_interest_tags": list(semantic.get("audience_interest_tags", [])),
        "causal_parent_ids": list(semantic.get("causal_parent_ids", [])),
    }


def public_event(event: CrawlEvent) -> dict[str, Any]:
    """Project an authoritative event into spectator-safe structured truth."""

    return {
        "id": event.id,
        "crawl_id": event.crawl_id,
        "floor_number": event.floor_number,
        "tick": event.tick,
        "event_type": event.event_type,
        "summary": event.summary,
        "actor_ids": list(event.actor_ids),
        "location_id": event.location_id,
        "semantic": _public_semantic(event),
    }


def public_floor(crawl: Crawl, floor_number: int | None = None) -> dict[str, Any]:
    number = crawl.current_floor if floor_number is None else floor_number
    floor = crawl.floors[number]
    occupancy = Counter(
        p.current_location_id
        for p in crawl.participants.values()
        if p.current_floor == number and p.current_location_id is not None
        and p.status not in {ParticipationStatus.DEAD, ParticipationStatus.ELIMINATED}
    )
    return {
        "number": floor.number,
        "theme": floor.theme,
        "status": floor.status.value,
        "danger_level": floor.danger_level,
        "started_at_tick": floor.started_at_tick,
        "deadline_tick": floor.deadline_tick,
        "entrance_location_id": floor.entrance_location_id,
        "exit_location_ids": list(floor.exit_location_ids),
        "safe_area_ids": list(floor.safe_area_ids),
        "locations": [
            {
                "id": loc.id,
                "name": loc.name,
                "kind": loc.kind.value,
                "adjacent_location_ids": sorted(loc.adjacency),
                "occupancy": occupancy.get(loc.id, 0),
            }
            for loc in sorted(floor.locations.values(), key=lambda item: item.id)
        ],
    }


def public_crawl(crawl: Crawl) -> dict[str, Any]:
    return {
        "id": crawl.id,
        "status": crawl.status.value,
        "current_tick": crawl.current_tick,
        "current_floor": crawl.current_floor,
        "floor_count": len(crawl.floors),
        "starting_crawler_count": crawl.starting_crawler_count,
        "surviving_crawler_count": crawl.surviving_crawler_count,
        "eliminated_crawler_count": crawl.eliminated_crawler_count,
        "ruleset_id": crawl.ruleset_id,
        "ruleset_version": crawl.ruleset_version,
    }


def public_crawler(crawl: Crawl, npc_id: str, *, include_social: bool = False) -> dict[str, Any]:
    participant = crawl.participants[npc_id]
    agent = participant.agent
    progression = participant.gameplay.progression
    inventory = [
        crawl.items[item_id]
        for item_id in participant.gameplay.inventory_item_ids
        if item_id in crawl.items
    ]
    equipment = {
        slot: item_id for slot, item_id in participant.gameplay.equipment.items()
        if item_id in crawl.items
    }
    payload: dict[str, Any] = {
        "npc_id": npc_id,
        "status": participant.status.value,
        "health": participant.health,
        "current_floor": participant.current_floor,
        "current_location_id": participant.current_location_id,
        "current_party_id": participant.current_party_id,
        "current_objective": participant.current_objective,
        "level": progression.level,
        "experience": progression.experience,
        "specialization": progression.specialization,
        "abilities": list(progression.ability_ids),
        "kills": participant.gameplay.kills,
        "encounters_survived": participant.gameplay.encounters_survived,
        "injuries": [injury.model_dump(mode="json") for injury in participant.gameplay.injuries],
        "inventory": [
            {
                "id": item.id,
                "name": item.name,
                "category": item.category.value,
                "rarity": item.rarity.value,
                "stats": dict(item.stats),
            }
            for item in sorted(inventory, key=lambda value: value.id)
        ],
        "equipment": equipment,
    }
    if agent is not None:
        payload["public_profile"] = {
            "current_goal": agent.current_goal,
            "last_action": agent.last_action,
            "decision_count": agent.decision_count,
        }
        if include_social:
            payload["relationships"] = [
                {
                    "target_id": rel.target_id,
                    "trust": rel.trust,
                    "respect": rel.respect,
                    "rivalry": rel.rivalry,
                    "familiarity": rel.familiarity,
                }
                for rel in sorted(agent.relationships.values(), key=lambda item: item.target_id)
            ]
    return payload


def public_party(crawl: Crawl, party_id: str) -> dict[str, Any]:
    party = crawl.parties[party_id]
    return {
        "id": party.id,
        "active": party.active,
        "leader_npc_id": party.leader_npc_id,
        "member_npc_ids": list(party.member_npc_ids),
        "cohesion": party.cohesion,
        "loot_policy": party.loot_policy.value,
    }


def visible_encounters(crawl: Crawl) -> list[dict[str, Any]]:
    """Expose only encounters that are active or have become historical truth."""

    return [
        {
            "id": encounter.id,
            "floor_number": encounter.floor_number,
            "location_id": encounter.location_id,
            "encounter_type": encounter.type.value,
            "status": encounter.status.value,
            "participant_npc_ids": list(encounter.participant_npc_ids),
            "difficulty": encounter.difficulty,
        }
        for encounter in sorted(crawl.encounters.values(), key=lambda item: item.id)
        if encounter.status.value != "dormant"
    ]


def leaderboard(crawl: Crawl, *, limit: int = 25) -> list[dict[str, Any]]:
    rows = [public_crawler(crawl, npc_id) for npc_id in crawl.participants]
    rows.sort(
        key=lambda row: (
            row["status"] in {"dead", "eliminated"},
            -row["current_floor"],
            -row["level"],
            -row["kills"],
            row["npc_id"],
        )
    )
    return rows[: max(1, limit)]


def trending_crawlers(crawl: Crawl, events: Iterable[CrawlEvent], *, limit: int = 20) -> list[dict[str, Any]]:
    scores: Counter[str] = Counter()
    for event in events:
        score = semantic_score(event)
        for npc_id in event.actor_ids:
            if npc_id in crawl.participants:
                scores[npc_id] += score
    rows = [
        {"npc_id": npc_id, "interest_score": round(score, 4), "crawler": public_crawler(crawl, npc_id)}
        for npc_id, score in scores.items()
    ]
    rows.sort(key=lambda row: (-row["interest_score"], row["npc_id"]))
    return rows[: max(1, limit)]
