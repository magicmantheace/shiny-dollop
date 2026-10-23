from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

from .crawl_domain import CrawlEvent
from .semantic_event_ledger import semantic_score


@dataclass(frozen=True)
class StoryArc:
    id: str
    story_type: str
    score: float
    start_tick: int
    end_tick: int
    floor_numbers: tuple[int, ...]
    participant_ids: tuple[str, ...]
    event_ids: tuple[str, ...]
    explanation: str
    evidence: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "story_type": self.story_type,
            "score": round(self.score, 4),
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "floor_numbers": list(self.floor_numbers),
            "participant_ids": list(self.participant_ids),
            "event_ids": list(self.event_ids),
            "explanation": self.explanation,
            "evidence": list(self.evidence),
        }


def _semantic(event: CrawlEvent) -> dict:
    if not isinstance(event.data, dict):
        return {}
    value = event.data.get("semantic", {})
    return value if isinstance(value, dict) else {}


def _relationship_impact(event: CrawlEvent) -> float:
    try:
        return float(_semantic(event).get("relationship_impact", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _arc_id(story_type: str, event_ids: tuple[str, ...]) -> str:
    payload = f"{story_type}:{','.join(event_ids)}".encode("utf-8")
    return f"story_{sha256(payload).hexdigest()[:20]}"


def _classify(events: list[CrawlEvent]) -> str:
    types = [event.event_type.upper() for event in events]
    tags = {
        str(tag)
        for event in events
        for tag in _semantic(event).get("audience_interest_tags", [])
    }
    impacts = [_relationship_impact(event) for event in events]

    if "CRAWLER_DIED" in types or any("DIED" in value for value in types):
        return "notable_death"
    if "BETRAYAL" in types:
        return "betrayal"
    if "RESCUE" in types and "NEAR_DEATH" in types:
        return "rescue_comeback"
    if "RESCUE" in types:
        return "rescue"
    if types.count("NEAR_DEATH") >= 2:
        return "repeated_near_death"
    if any("BOSS" in value for value in types) or "boss" in tags:
        return "boss_outcome"
    if "PARTY_DISSOLVED" in types:
        return "party_collapse"
    if min(impacts, default=0.0) < -0.35 and max(impacts, default=0.0) > 0.35:
        return "relationship_reversal"
    if "PARTY_FORMED" in types and min(impacts, default=0.0) < -0.2:
        return "unlikely_alliance"
    if any("ADVANCED" in value or "FLOOR_COMPLETED" in value for value in types):
        return "progression_sequence"
    return "emergent_sequence"


def _score(events: list[CrawlEvent]) -> float:
    if not events:
        return 0.0
    semantic_scores = [semantic_score(event) for event in events]
    danger = []
    reversals = 0
    for event in events:
        semantic = _semantic(event)
        try:
            danger.append(float(semantic.get("danger_level", 0.0) or 0.0))
        except (TypeError, ValueError):
            danger.append(0.0)
        reversals += int(bool(semantic.get("reversal")))
    value = (
        max(semantic_scores, default=0.0) * 0.56
        + (sum(semantic_scores) / len(semantic_scores)) * 0.18
        + max(danger, default=0.0) * 0.10
        + min(0.10, len(events) * 0.015)
        + min(0.06, reversals * 0.03)
    )
    return max(0.0, min(1.0, value))


def _make_arc(events: list[CrawlEvent], *, participant_scope: set[str] | None = None) -> StoryArc:
    ordered = sorted({event.id: event for event in events}.values(), key=lambda event: (event.tick, event.id))
    event_ids = tuple(event.id for event in ordered)
    story_type = _classify(ordered)
    all_participants = {actor for event in ordered for actor in event.actor_ids}
    if participant_scope:
        scoped = all_participants.intersection(participant_scope)
        participants = tuple(sorted(scoped or all_participants))
    else:
        participants = tuple(sorted(all_participants))
    floors = tuple(sorted({event.floor_number for event in ordered if event.floor_number is not None}))
    event_types = [event.event_type for event in ordered]
    evidence = tuple(f"{event.event_type}:{event.id}" for event in ordered)
    explanation = (
        f"Detected {story_type.replace('_', ' ')} from {len(ordered)} authoritative events "
        f"spanning ticks {ordered[0].tick}-{ordered[-1].tick}: "
        + " -> ".join(event_types)
    )
    return StoryArc(
        id=_arc_id(story_type, event_ids),
        story_type=story_type,
        score=_score(ordered),
        start_tick=ordered[0].tick,
        end_tick=ordered[-1].tick,
        floor_numbers=floors,
        participant_ids=participants,
        event_ids=event_ids,
        explanation=explanation,
        evidence=evidence,
    )


def _event_is_local_to(event: CrawlEvent, core_actors: set[str]) -> bool:
    if not core_actors:
        return True
    actors = set(event.actor_ids)
    if not actors.intersection(core_actors):
        return False
    overlap = len(actors.intersection(core_actors))
    if len(actors) <= 8 or overlap >= min(2, len(core_actors)):
        return True
    return semantic_score(event) >= 0.78


def _bounded_anchor_events(
    selected: dict[str, CrawlEvent],
    *,
    anchor: CrawlEvent,
    max_events: int,
) -> list[CrawlEvent]:
    if len(selected) <= max_events:
        return list(selected.values())
    ranked = sorted(
        selected.values(),
        key=lambda event: (
            event.id != anchor.id,
            -semantic_score(event),
            abs(event.tick - anchor.tick),
            event.tick,
            event.id,
        ),
    )
    keep = ranked[:max_events]
    if anchor.id not in {event.id for event in keep}:
        keep[-1] = anchor
    return keep


def _signature_types(story_type: str) -> set[str]:
    return {
        "rescue": {"RESCUE"},
        "rescue_comeback": {"RESCUE", "NEAR_DEATH"},
        "repeated_near_death": {"NEAR_DEATH"},
        "betrayal": {"BETRAYAL"},
        "notable_death": {"CRAWLER_DIED", "CRAWLER_ELIMINATED"},
        "party_collapse": {"PARTY_DISSOLVED"},
    }.get(story_type, set())


def _anchor_supports_story(anchor: CrawlEvent, story_type: str) -> bool:
    signature = _signature_types(story_type)
    if not signature:
        return True
    return anchor.event_type.upper() in signature


def _signature_event_ids(arc: StoryArc, by_id: dict[str, CrawlEvent]) -> set[str]:
    signature = _signature_types(arc.story_type)
    if not signature:
        return set()
    return {
        event_id
        for event_id in arc.event_ids
        if event_id in by_id and by_id[event_id].event_type.upper() in signature
    }


class StoryArcDetector:
    """Group authoritative structured events into explainable story candidates.

    This is deterministic rule/graph analysis, not narrative generation. Every arc
    contains the exact event IDs that caused it to be selected. Anchor-driven arcs
    are intentionally bounded around their core actors so broad combat events do
    not swallow an entire floor into one personal highlight.
    """

    def __init__(
        self,
        *,
        lookback_ticks: int = 24,
        follow_ticks: int = 12,
        minimum_score: float = 0.42,
        max_anchor_events: int = 16,
    ) -> None:
        self.lookback_ticks = max(1, lookback_ticks)
        self.follow_ticks = max(0, follow_ticks)
        self.minimum_score = minimum_score
        self.max_anchor_events = max(4, max_anchor_events)

    def analyze(self, events: Iterable[CrawlEvent], *, limit: int = 50) -> list[StoryArc]:
        ordered = sorted(events, key=lambda event: (event.tick, event.id))
        by_id = {event.id: event for event in ordered}
        by_actor: dict[str, list[CrawlEvent]] = defaultdict(list)
        for event in ordered:
            for actor in event.actor_ids:
                by_actor[actor].append(event)

        candidates: dict[tuple[str, tuple[str, ...]], StoryArc] = {}
        anchor_types = {
            "RESCUE",
            "BETRAYAL",
            "CRAWLER_DIED",
            "CRAWLER_ELIMINATED",
            "PARTY_DISSOLVED",
            "NEAR_DEATH",
            "FLOOR_COMPLETED",
            "CRAWLER_ADVANCED",
        }

        for anchor in ordered:
            semantic = _semantic(anchor)
            tags = {str(tag) for tag in semantic.get("audience_interest_tags", [])}
            is_anchor = (
                anchor.event_type.upper() in anchor_types
                or "BOSS" in anchor.event_type.upper()
                or "boss" in tags
                or semantic_score(anchor) >= 0.68
            )
            if not is_anchor:
                continue

            core_actors = set(anchor.actor_ids)
            selected: dict[str, CrawlEvent] = {anchor.id: anchor}
            frontier = list(semantic.get("causal_parent_ids", []))
            depth = 0
            while frontier and depth < 5 and len(selected) < self.max_anchor_events:
                next_frontier: list[str] = []
                for event_id in sorted(set(frontier)):
                    parent = by_id.get(event_id)
                    if parent is None or parent.id in selected:
                        continue
                    if not _event_is_local_to(parent, core_actors):
                        continue
                    selected[parent.id] = parent
                    next_frontier.extend(_semantic(parent).get("causal_parent_ids", []))
                    if len(selected) >= self.max_anchor_events:
                        break
                frontier = next_frontier
                depth += 1

            if core_actors:
                local_candidates = []
                for event in ordered:
                    if not _event_is_local_to(event, core_actors):
                        continue
                    if not (anchor.tick - self.lookback_ticks <= event.tick <= anchor.tick + self.follow_ticks):
                        continue
                    if semantic_score(event) >= 0.34 or event.event_type.upper() in anchor_types:
                        local_candidates.append(event)
                local_candidates.sort(
                    key=lambda event: (
                        -semantic_score(event),
                        abs(event.tick - anchor.tick),
                        event.tick,
                        event.id,
                    )
                )
                for event in local_candidates:
                    selected[event.id] = event
                    if len(selected) >= self.max_anchor_events:
                        break

            arc_events = _bounded_anchor_events(selected, anchor=anchor, max_events=self.max_anchor_events)
            arc = _make_arc(arc_events, participant_scope=core_actors or None)
            if not _anchor_supports_story(anchor, arc.story_type):
                continue
            if arc.score >= self.minimum_score and len(arc.event_ids) >= 2:
                candidates[(arc.story_type, arc.event_ids)] = arc

        for actor, actor_events in sorted(by_actor.items()):
            notable = [
                event
                for event in actor_events
                if semantic_score(event) >= 0.56
                or event.event_type.upper() in {"RESCUE", "BETRAYAL", "NEAR_DEATH", "CRAWLER_DIED", "PARTY_DISSOLVED"}
            ]
            if len(notable) < 2:
                continue
            recent = notable[-8:]
            scope = {actor}
            for event in recent:
                if abs(_relationship_impact(event)) >= 0.30 or event.event_type.upper() in {"RESCUE", "BETRAYAL"}:
                    scope.update(event.actor_ids)
            arc = _make_arc(recent, participant_scope=scope)
            if arc.score >= self.minimum_score:
                candidates[(arc.story_type, arc.event_ids)] = arc

        arcs = list(candidates.values())
        arcs.sort(key=lambda arc: (-arc.score, arc.start_tick, arc.id))

        selected_arcs: list[StoryArc] = []
        used_sets: list[set[str]] = []
        used_signature_sets: list[tuple[str, set[str]]] = []
        for arc in arcs:
            event_set = set(arc.event_ids)
            signature_ids = _signature_event_ids(arc, by_id)
            signature_duplicate = bool(signature_ids) and any(
                arc.story_type == story_type and bool(signature_ids.intersection(existing))
                for story_type, existing in used_signature_sets
            )
            redundant = signature_duplicate or any(
                event_set <= used or (len(event_set.intersection(used)) / max(1, len(event_set))) >= 0.85
                for used in used_sets
            )
            if redundant:
                continue
            selected_arcs.append(arc)
            used_sets.append(event_set)
            if signature_ids:
                used_signature_sets.append((arc.story_type, signature_ids))
            if len(selected_arcs) >= max(1, limit):
                break
        return selected_arcs
