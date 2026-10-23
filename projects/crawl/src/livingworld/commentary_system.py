from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Iterable

from .crawl_domain import CrawlEvent
from .story_highlights import StoryArc


class CommentaryMode(StrEnum):
    PLAY_BY_PLAY = "play_by_play"
    ANALYTICAL = "analytical"
    DOCUMENTARY = "documentary"
    CRAWLER_RECAP = "crawler_recap"


@dataclass(frozen=True)
class CommentaryLine:
    text: str
    source_event_ids: tuple[str, ...]
    factual: bool = True

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "source_event_ids": list(self.source_event_ids),
            "factual": self.factual,
        }


@dataclass(frozen=True)
class CommentaryScript:
    mode: CommentaryMode
    lines: tuple[CommentaryLine, ...]
    source_event_ids: tuple[str, ...]
    digest: str

    def as_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "line_count": len(self.lines),
            "source_event_ids": list(self.source_event_ids),
            "digest": self.digest,
            "lines": [line.as_dict() for line in self.lines],
        }


def _digest(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def _actor_label(event: CrawlEvent) -> str:
    if not event.actor_ids:
        return "The crawl"
    if len(event.actor_ids) == 1:
        return event.actor_ids[0]
    if len(event.actor_ids) == 2:
        return f"{event.actor_ids[0]} and {event.actor_ids[1]}"
    return f"{event.actor_ids[0]} and {len(event.actor_ids) - 1} others"


def _event_fact(event: CrawlEvent, mode: CommentaryMode) -> str:
    event_type = event.event_type.upper()
    actors = _actor_label(event)
    floor = f" on Floor {event.floor_number}" if event.floor_number is not None else ""

    facts = {
        "NEAR_DEATH": f"{actors} reached a near-death moment{floor}.",
        "RESCUE": f"{actors} were involved in a rescue{floor}.",
        "BETRAYAL": f"{actors} were involved in a betrayal{floor}.",
        "CRAWLER_DIED": f"{actors} died{floor}.",
        "CRAWLER_ELIMINATED": f"{actors} were eliminated{floor}.",
        "PARTY_FORMED": f"{actors} formed a party{floor}.",
        "PARTY_DISSOLVED": f"A party involving {actors} dissolved{floor}.",
        "CRAWLER_ADVANCED": f"{actors} advanced{floor}.",
        "ITEM_ACQUIRED": f"{actors} acquired an item{floor}.",
        "ENEMY_DEFEATED": f"{actors} defeated an enemy{floor}.",
        "COMBAT_STARTED": f"Combat began involving {actors}{floor}.",
        "COMBAT_ENDED": f"Combat involving {actors} ended{floor}.",
        "FLOOR_COMPLETED": f"Floor {event.floor_number} was completed.",
        "CRAWL_COMPLETED": "The crawl was completed.",
    }
    base = facts.get(event_type, event.summary.strip() or event_type.replace("_", " ").title())

    if mode == CommentaryMode.PLAY_BY_PLAY:
        return base
    if mode == CommentaryMode.ANALYTICAL:
        return f"At tick {event.tick}, {base[0].lower() + base[1:] if base else base}"
    if mode == CommentaryMode.DOCUMENTARY:
        return f"The record shows that {base[0].lower() + base[1:] if base else base}"
    return base


class GroundedCommentaryGenerator:
    """Deterministic commentary baseline grounded only in canonical CrawlEvents.

    A later LLM adapter may rewrite these facts for style, but it must retain the
    supplied event citations and pass the same grounding validator before use.
    """

    def generate(
        self,
        events: Iterable[CrawlEvent],
        *,
        mode: CommentaryMode = CommentaryMode.DOCUMENTARY,
        story: StoryArc | None = None,
        actor_id: str | None = None,
        max_lines: int = 12,
    ) -> CommentaryScript:
        ordered = sorted(events, key=lambda event: (event.tick, event.id))
        if story is not None:
            allowed = set(story.event_ids)
            ordered = [event for event in ordered if event.id in allowed]
        if actor_id is not None:
            ordered = [event for event in ordered if actor_id in event.actor_ids]
        if not ordered:
            return self._build(mode, ())

        if len(ordered) > max(1, max_lines):
            # Preserve opening context, highest-value middle events by semantic score,
            # and the final consequence without inventing transitions.
            from .semantic_event_ledger import semantic_score

            first = ordered[0]
            last = ordered[-1]
            middle = sorted(
                ordered[1:-1],
                key=lambda event: (-semantic_score(event), event.tick, event.id),
            )[: max(0, max_lines - 2)]
            ordered = sorted({event.id: event for event in [first, *middle, last]}.values(), key=lambda e: (e.tick, e.id))

        lines = [
            CommentaryLine(
                text=_event_fact(event, mode),
                source_event_ids=(event.id,),
                factual=True,
            )
            for event in ordered
        ]

        if story is not None and lines:
            lines.insert(
                0,
                CommentaryLine(
                    text=f"This {story.story_type.replace('_', ' ')} sequence spans ticks {story.start_tick} through {story.end_tick}.",
                    source_event_ids=tuple(story.event_ids),
                    factual=True,
                ),
            )
        return self._build(mode, tuple(lines))

    def _build(self, mode: CommentaryMode, lines: tuple[CommentaryLine, ...]) -> CommentaryScript:
        source_ids = tuple(dict.fromkeys(event_id for line in lines for event_id in line.source_event_ids))
        payload = {
            "mode": mode.value,
            "lines": [line.as_dict() for line in lines],
            "source_event_ids": list(source_ids),
        }
        return CommentaryScript(mode=mode, lines=lines, source_event_ids=source_ids, digest=_digest(payload))


def validate_commentary_grounding(script: CommentaryScript, authoritative_event_ids: set[str]) -> bool:
    if any(not line.source_event_ids for line in script.lines):
        return False
    if any(not set(line.source_event_ids).issubset(authoritative_event_ids) for line in script.lines):
        return False
    return set(script.source_event_ids).issubset(authoritative_event_ids)
