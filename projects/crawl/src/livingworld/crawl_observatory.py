from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

from .crawl_domain import Crawl, CrawlEvent, ParticipationStatus
from .detail_tiers import scheduler_load, tier_distribution, tier_for
from .semantic_event_ledger import semantic_score


def _recent(events: Iterable[CrawlEvent], limit: int = 100) -> list[CrawlEvent]:
    ordered = sorted(events, key=lambda event: (event.tick, event.id), reverse=True)
    return ordered[:limit]


def build_crawler_diagnostic(crawl: Crawl, npc_id: str, events: Iterable[CrawlEvent] = ()) -> dict[str, Any]:
    participant = crawl.participants[npc_id]
    agent = participant.agent
    related = [event for event in _recent(events, 500) if npc_id in event.actor_ids]
    recent = related[:25]
    current_location = None
    if participant.current_location_id is not None:
        current_location = crawl.floors[participant.current_floor].locations[participant.current_location_id]

    relationships = []
    memories = []
    if agent is not None:
        relationships = sorted(
            (
                {
                    "npc_id": other_id,
                    **relationship.model_dump(mode="json"),
                }
                for other_id, relationship in agent.relationships.items()
            ),
            key=lambda row: (-abs(row.get("affinity", 0.0)) - abs(row.get("resentment", 0.0)), row["npc_id"]),
        )[:20]
        memories = [memory.model_dump(mode="json") for memory in agent.memories[-20:]][::-1]

    inventory = [
        crawl.items[item_id].model_dump(mode="json")
        for item_id in participant.gameplay.inventory_item_ids
        if item_id in crawl.items
    ]

    return {
        "npc_id": npc_id,
        "status": participant.status.value,
        "detail_tier": tier_for(crawl, npc_id).value,
        "floor": participant.current_floor,
        "location": current_location.model_dump(mode="json") if current_location else None,
        "health": participant.health,
        "stamina": participant.gameplay.stamina,
        "objective": participant.current_objective,
        "party_id": participant.current_party_id,
        "progression": participant.gameplay.progression.model_dump(mode="json"),
        "equipment": dict(participant.gameplay.equipment),
        "inventory": inventory,
        "needs": agent.needs.model_dump(mode="json") if agent else None,
        "traits": agent.traits.model_dump(mode="json") if agent else None,
        "skills": agent.skills.model_dump(mode="json") if agent else None,
        "knowledge_locations": len(agent.knowledge) if agent else 0,
        "relationships": relationships,
        "memories": memories,
        "recent_events": [event.model_dump(mode="json") for event in recent],
        "decision_trace": {
            "current_goal": agent.current_goal if agent else None,
            "last_action": agent.last_action if agent else None,
            "decision_count": agent.decision_count if agent else 0,
            "recent_causal_event_ids": [
                parent_id
                for event in recent[:5]
                for parent_id in event.data.get("semantic", {}).get("causal_parent_ids", [])
            ],
        },
    }


def build_observatory_snapshot(
    crawl: Crawl,
    events: Iterable[CrawlEvent] = (),
    *,
    telemetry: dict[str, Any] | None = None,
    selected_crawler_id: str | None = None,
) -> dict[str, Any]:
    events = list(events)
    floor = crawl.floors[crawl.current_floor]

    occupancy: dict[str, list[str]] = defaultdict(list)
    for npc_id, participant in crawl.participants.items():
        if participant.current_floor == crawl.current_floor and participant.current_location_id:
            occupancy[participant.current_location_id].append(npc_id)

    statuses = Counter(participant.status.value for participant in crawl.participants.values())
    active_encounters = [
        encounter.model_dump(mode="json")
        for encounter in crawl.encounters.values()
        if encounter.floor_number == crawl.current_floor and encounter.status.value in {"dormant", "active"}
    ]
    active_parties = [party.model_dump(mode="json") for party in crawl.parties.values() if party.active]
    deaths = [event.model_dump(mode="json") for event in _recent(events, 500) if event.event_type in {"CRAWLER_DIED", "CRAWLER_ELIMINATED", "FLOOR_DEADLINE_ELIMINATION"}]
    director = [event.model_dump(mode="json") for event in _recent(events, 500) if event.event_type == "DIRECTOR_INTERVENTION"]

    notable = sorted(
        (event for event in events if semantic_score(event) > 0),
        key=lambda event: (-semantic_score(event), -event.tick, event.id),
    )[:50]

    crawler_rows = []
    for npc_id, participant in sorted(crawl.participants.items()):
        crawler_rows.append(
            {
                "npc_id": npc_id,
                "status": participant.status.value,
                "tier": tier_for(crawl, npc_id).value,
                "floor": participant.current_floor,
                "location_id": participant.current_location_id,
                "health": participant.health,
                "stamina": participant.gameplay.stamina,
                "level": participant.gameplay.progression.level,
                "specialization": participant.gameplay.progression.specialization,
                "party_id": participant.current_party_id,
                "objective": participant.current_objective,
                "inventory_count": len(participant.gameplay.inventory_item_ids),
                "kills": participant.gameplay.kills,
            }
        )

    selected = selected_crawler_id
    if selected is None and crawl.participants:
        selected = max(
            crawl.participants,
            key=lambda npc_id: (
                crawl.participants[npc_id].gameplay.kills,
                crawl.participants[npc_id].gameplay.progression.level,
                npc_id,
            ),
        )

    return {
        "crawl": {
            "id": crawl.id,
            "seed": crawl.seed,
            "status": crawl.status.value,
            "tick": crawl.current_tick,
            "current_floor": crawl.current_floor,
            "configured_floors": len(crawl.floors),
            "starting_crawlers": crawl.starting_crawler_count,
            "survivors": crawl.surviving_crawler_count,
            "eliminated": crawl.eliminated_crawler_count,
            "fingerprint": crawl.fingerprint(),
        },
        "floor": {
            **floor.model_dump(mode="json"),
            "occupancy": {location_id: sorted(ids) for location_id, ids in occupancy.items()},
        },
        "population": {
            "statuses": dict(statuses),
            "detail_tiers": tier_distribution(crawl),
            "scheduler": scheduler_load(crawl),
        },
        "crawlers": crawler_rows,
        "active_encounters": active_encounters,
        "active_parties": active_parties,
        "deaths": deaths,
        "director_interventions": director,
        "recent_events": [event.model_dump(mode="json") for event in _recent(events, 100)],
        "interesting_events": [
            {
                **event.model_dump(mode="json"),
                "semantic_score": semantic_score(event),
            }
            for event in notable
        ],
        "performance": telemetry or {},
        "selected_crawler": build_crawler_diagnostic(crawl, selected, events) if selected else None,
    }
