from __future__ import annotations

from collections import defaultdict
from typing import Any

from .crawl_domain import Crawl, CrawlEvent


_BASE_IMPORTANCE: dict[str, float] = {
    "CRAWLER_DIED": 0.92,
    "CRAWLER_ELIMINATED": 0.70,
    "CRAWL_COMPLETED": 0.90,
    "CRAWL_ENDED_NO_SURVIVORS": 0.95,
    "FLOOR_COMPLETED": 0.60,
    "FLOOR_DEADLINE_WARNING": 0.45,
    "FLOOR_DEADLINE_ELIMINATION": 0.78,
    "COMBAT_STARTED": 0.38,
    "COMBAT_ENDED": 0.55,
    "ENCOUNTER_TRIGGERED": 0.30,
    "ENCOUNTER_RESOLVED": 0.46,
    "ITEM_ACQUIRED": 0.22,
    "CRAWLER_ADVANCED": 0.42,
    "PARTY_FORMED": 0.48,
    "PARTY_DISSOLVED": 0.55,
    "DIRECTOR_INTERVENTION": 0.52,
    "DIRECTOR_ANNOUNCEMENT": 0.30,
    "RESCUE": 0.82,
    "BETRAYAL": 0.86,
    "NEAR_DEATH": 0.74,
}

_RARE_EVENT_TYPES = {
    "CRAWLER_DIED",
    "CRAWL_ENDED_NO_SURVIVORS",
    "RESCUE",
    "BETRAYAL",
    "NEAR_DEATH",
    "DIRECTOR_INTERVENTION",
}


def _semantic_state(crawl: Crawl) -> dict[str, Any]:
    state = crawl.modifiers.setdefault("_semantic_ledger", {})
    state.setdefault("last_event_by_actor", {})
    state.setdefault("event_type_counts", {})
    state.setdefault("notable_event_ids", [])
    return state


def _danger_from_event(crawl: Crawl, event: CrawlEvent) -> float:
    if "danger" in event.data:
        try:
            return max(0.0, min(1.0, float(event.data["danger"])))
        except (TypeError, ValueError):
            pass
    floor_number = event.floor_number or crawl.current_floor
    floor = crawl.floors.get(floor_number)
    return round(floor.danger_level if floor is not None else 0.0, 4)


def _relationship_impact(event: CrawlEvent) -> float:
    explicit = event.data.get("relationship_impact")
    if explicit is not None:
        try:
            return max(-1.0, min(1.0, float(explicit)))
        except (TypeError, ValueError):
            pass
    event_type = event.event_type.upper()
    if event_type in {"RESCUE", "PARTY_FORMED", "SHARED_RESOURCE", "HEALED"}:
        return 0.55
    if event_type in {"BETRAYAL", "ABANDONED", "PARTY_DISSOLVED"}:
        return -0.60
    return 0.0


def _audience_tags(event: CrawlEvent, danger: float) -> list[str]:
    event_type = event.event_type.upper()
    tags: set[str] = set()
    if "DEATH" in event_type or event_type == "CRAWLER_DIED":
        tags.add("death")
    if "BOSS" in event_type:
        tags.add("boss")
    if event_type in {"RESCUE", "HEALED"}:
        tags.update({"rescue", "relationship"})
    if event_type in {"BETRAYAL", "ABANDONED", "PARTY_DISSOLVED"}:
        tags.update({"social_drama", "relationship"})
    if event_type.startswith("DIRECTOR_"):
        tags.add("director")
    if "ITEM" in event_type:
        tags.add("loot")
    if "COMBAT" in event_type or "ENCOUNTER" in event_type:
        tags.add("action")
    if "FLOOR" in event_type or "ADVANCED" in event_type:
        tags.add("progression")
    if danger >= 0.65:
        tags.add("high_danger")
    return sorted(tags)


def annotate_event(crawl: Crawl, event: CrawlEvent) -> CrawlEvent:
    """Attach deterministic, recalculable story metadata to an authoritative event.

    Metadata is stored inside ``event.data['semantic']`` so the existing event
    persistence schema remains compatible with earlier v0.4 batches.
    """

    state = _semantic_state(crawl)
    counts: dict[str, int] = state["event_type_counts"]
    count_before = int(counts.get(event.event_type, 0))
    counts[event.event_type] = count_before + 1

    last_by_actor: dict[str, str] = state["last_event_by_actor"]
    causal_parent_ids = sorted({last_by_actor[actor] for actor in event.actor_ids if actor in last_by_actor})
    for actor in event.actor_ids:
        last_by_actor[actor] = event.id

    danger = _danger_from_event(crawl, event)
    rarity = 1.0 / (1.0 + count_before)
    if event.event_type.upper() in _RARE_EVENT_TYPES:
        rarity = max(rarity, 0.72)

    relationship_impact = _relationship_impact(event)
    reversal = bool(event.data.get("reversal", False))
    if event.event_type.upper() in {"RESCUE", "BETRAYAL", "NEAR_DEATH"} and causal_parent_ids:
        reversal = True

    base = _BASE_IMPORTANCE.get(event.event_type.upper(), 0.16)
    actor_bonus = min(0.12, max(0, len(event.actor_ids) - 1) * 0.025)
    importance = min(
        1.0,
        base
        + danger * 0.14
        + rarity * 0.10
        + abs(relationship_impact) * 0.12
        + (0.08 if reversal else 0.0)
        + actor_bonus,
    )

    state_changes = event.data.get("state_changes", {})
    if not isinstance(state_changes, dict):
        state_changes = {"value": state_changes}

    semantic = {
        "importance_score": round(importance, 4),
        "rarity_score": round(max(0.0, min(1.0, rarity)), 4),
        "danger_level": round(danger, 4),
        "reversal": reversal,
        "relationship_impact": round(relationship_impact, 4),
        "audience_interest_tags": _audience_tags(event, danger),
        "causal_parent_ids": causal_parent_ids,
        "state_changes": state_changes,
        "replay_checkpoint_ref": event.data.get("replay_checkpoint_ref"),
    }
    event.data["semantic"] = semantic

    if importance >= 0.68:
        notable = state["notable_event_ids"]
        if event.id not in notable:
            notable.append(event.id)
            del notable[:-500]
    return event


def semantic_score(event: CrawlEvent) -> float:
    semantic = event.data.get("semantic", {})
    try:
        return float(semantic.get("importance_score", 0.0))
    except (TypeError, ValueError):
        return 0.0


def notable_events(events: list[CrawlEvent], *, minimum_score: float = 0.68, limit: int = 50) -> list[CrawlEvent]:
    selected = [event for event in events if semantic_score(event) >= minimum_score]
    selected.sort(key=lambda item: (-semantic_score(item), -item.tick, item.id))
    return selected[: max(1, limit)]


def build_actor_arcs(events: list[CrawlEvent]) -> dict[str, list[str]]:
    """Return ordered event-id arcs for each actor without inventing narrative facts."""

    arcs: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for event in events:
        for actor_id in event.actor_ids:
            arcs[actor_id].append((event.tick, event.id))
    return {
        actor_id: [event_id for _, event_id in sorted(items, key=lambda row: (row[0], row[1]))]
        for actor_id, items in arcs.items()
    }
