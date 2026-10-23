"""Underreach Feed projections over authoritative simulation state.

This module is intentionally read-only. It translates terminology and field names
for public consumers while preserving canonical event IDs and simulation truth.
Legacy spectator projections remain available for compatibility.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from .crawl_domain import Crawl, CrawlEvent, ParticipationStatus
from .semantic_event_ledger import semantic_score
from .spectator_state import public_crawler as _legacy_public_crawler
from .underreach_terminology import (
    DESCENT_NAME,
    FEED_NAME,
    LEDGER_NAME,
    UNDERREACH_NAME,
    public_event_type,
    public_location_kind,
    public_participation_status,
)


def _semantic(event: CrawlEvent) -> dict[str, Any]:
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


def public_ledger_event(event: CrawlEvent) -> dict[str, Any]:
    """Project one canonical ledger event into Feed terminology."""

    return {
        "id": event.id,
        "descent_id": event.crawl_id,
        "stratum_number": event.floor_number,
        "tick": event.tick,
        "event_type": public_event_type(event.event_type),
        "summary": event.summary,
        "actor_ids": list(event.actor_ids),
        "sector_id": event.location_id,
        "semantic": _semantic(event),
        "canonical": True,
    }


def public_stratum(descent: Crawl, stratum_number: int | None = None) -> dict[str, Any]:
    number = descent.current_floor if stratum_number is None else stratum_number
    stratum = descent.floors[number]
    occupancy = Counter(
        p.current_location_id
        for p in descent.participants.values()
        if p.current_floor == number
        and p.current_location_id is not None
        and p.status not in {ParticipationStatus.DEAD, ParticipationStatus.ELIMINATED}
    )
    return {
        "number": stratum.number,
        "theme": stratum.theme,
        "status": stratum.status.value,
        "danger_level": stratum.danger_level,
        "started_at_tick": stratum.started_at_tick,
        "deadline_tick": stratum.deadline_tick,
        "entrance_sector_id": stratum.entrance_location_id,
        "exit_sector_ids": list(stratum.exit_location_ids),
        "refuge_sector_ids": list(stratum.safe_area_ids),
        "sectors": [
            {
                "id": sector.id,
                "name": sector.name,
                "kind": public_location_kind(sector.kind.value),
                "adjacent_sector_ids": sorted(sector.adjacency),
                "occupancy": occupancy.get(sector.id, 0),
            }
            for sector in sorted(stratum.locations.values(), key=lambda item: item.id)
        ],
    }


def public_descent(descent: Crawl) -> dict[str, Any]:
    return {
        "id": descent.id,
        "world": UNDERREACH_NAME,
        "competition": DESCENT_NAME,
        "broadcast": FEED_NAME,
        "record": LEDGER_NAME,
        "status": descent.status.value,
        "current_tick": descent.current_tick,
        "current_stratum": descent.current_floor,
        "stratum_count": len(descent.floors),
        "starting_descender_count": descent.starting_crawler_count,
        "surviving_descender_count": descent.surviving_crawler_count,
        "eliminated_descender_count": descent.eliminated_crawler_count,
        "ruleset_id": descent.ruleset_id,
        "ruleset_version": descent.ruleset_version,
    }


def public_descender(descent: Crawl, descender_id: str, *, include_social: bool = False) -> dict[str, Any]:
    legacy = _legacy_public_crawler(descent, descender_id, include_social=include_social)
    return {
        "descender_id": descender_id,
        "status": public_participation_status(legacy["status"]),
        "health": legacy["health"],
        "current_stratum": legacy["current_floor"],
        "current_sector_id": legacy["current_location_id"],
        "current_party_id": legacy["current_party_id"],
        "current_objective": legacy["current_objective"],
        "level": legacy["level"],
        "experience": legacy["experience"],
        "specialization": legacy["specialization"],
        "abilities": list(legacy["abilities"]),
        "kills": legacy["kills"],
        "encounters_survived": legacy["encounters_survived"],
        "injuries": list(legacy["injuries"]),
        "inventory": list(legacy["inventory"]),
        "equipment": dict(legacy["equipment"]),
        **({"public_profile": legacy["public_profile"]} if "public_profile" in legacy else {}),
        **({"relationships": legacy["relationships"]} if "relationships" in legacy else {}),
    }


def public_party(descent: Crawl, party_id: str) -> dict[str, Any]:
    party = descent.parties[party_id]
    return {
        "id": party.id,
        "active": party.active,
        "leader_descender_id": party.leader_npc_id,
        "member_descender_ids": list(party.member_npc_ids),
        "cohesion": party.cohesion,
        "loot_policy": party.loot_policy.value,
    }


def visible_encounters(descent: Crawl) -> list[dict[str, Any]]:
    return [
        {
            "id": encounter.id,
            "stratum_number": encounter.floor_number,
            "sector_id": encounter.location_id,
            "encounter_type": encounter.type.value,
            "status": encounter.status.value,
            "participant_descender_ids": list(encounter.participant_npc_ids),
            "difficulty": encounter.difficulty,
        }
        for encounter in sorted(descent.encounters.values(), key=lambda item: item.id)
        if encounter.status.value != "dormant"
    ]


def ledger_standings(descent: Crawl, *, limit: int = 25) -> list[dict[str, Any]]:
    rows = [public_descender(descent, descender_id) for descender_id in descent.participants]
    rows.sort(
        key=lambda row: (
            row["status"] in {"fallen", "eliminated"},
            -row["current_stratum"],
            -row["level"],
            -row["kills"],
            row["descender_id"],
        )
    )
    return rows[: max(1, limit)]


def trending_descenders(
    descent: Crawl,
    events: Iterable[CrawlEvent],
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    scores: Counter[str] = Counter()
    for event in events:
        score = semantic_score(event)
        for descender_id in event.actor_ids:
            if descender_id in descent.participants:
                scores[descender_id] += score
    rows = [
        {
            "descender_id": descender_id,
            "interest_score": round(score, 4),
            "descender": public_descender(descent, descender_id),
        }
        for descender_id, score in scores.items()
    ]
    rows.sort(key=lambda row: (-row["interest_score"], row["descender_id"]))
    return rows[: max(1, limit)]
