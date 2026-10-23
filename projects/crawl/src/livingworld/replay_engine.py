from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

from .crawl_domain import Crawl, CrawlEvent
from .spectator_state import public_crawl, public_event, public_floor


def _event_digest(events: Iterable[CrawlEvent]) -> str:
    payload = [event.model_dump(mode="json") for event in sorted(events, key=lambda e: (e.tick, e.id))]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ReplayManifest:
    crawl_id: str
    seed: str
    ruleset_id: str
    ruleset_version: str
    first_tick: int
    last_tick: int
    event_count: int
    authoritative_event_digest: str
    final_state_fingerprint: str
    floors: int

    def as_dict(self) -> dict:
        return {
            "crawl_id": self.crawl_id,
            "seed": self.seed,
            "ruleset_id": self.ruleset_id,
            "ruleset_version": self.ruleset_version,
            "first_tick": self.first_tick,
            "last_tick": self.last_tick,
            "event_count": self.event_count,
            "authoritative_event_digest": self.authoritative_event_digest,
            "final_state_fingerprint": self.final_state_fingerprint,
            "floors": self.floors,
        }


class ReplayArchive:
    """Read-only replay view over canonical CrawlEvent history.

    Replay never invents outcomes. It presents the ordered authoritative ledger plus
    a final-state fingerprint that clients can use to verify they are replaying the
    same simulation record.
    """

    def __init__(self, crawl: Crawl, events: Iterable[CrawlEvent]) -> None:
        self.crawl = crawl
        self.events = tuple(sorted(events, key=lambda event: (event.tick, event.id)))
        first_tick = self.events[0].tick if self.events else crawl.started_at_tick or 0
        last_tick = self.events[-1].tick if self.events else crawl.current_tick
        self.manifest = ReplayManifest(
            crawl_id=crawl.id,
            seed=crawl.seed,
            ruleset_id=crawl.ruleset_id,
            ruleset_version=crawl.ruleset_version,
            first_tick=first_tick,
            last_tick=last_tick,
            event_count=len(self.events),
            authoritative_event_digest=_event_digest(self.events),
            final_state_fingerprint=crawl.fingerprint(),
            floors=len(crawl.floors),
        )

    def events_between(
        self,
        *,
        start_tick: int | None = None,
        end_tick: int | None = None,
        actor_id: str | None = None,
        limit: int = 500,
    ) -> list[CrawlEvent]:
        items = list(self.events)
        if start_tick is not None:
            items = [event for event in items if event.tick >= start_tick]
        if end_tick is not None:
            items = [event for event in items if event.tick <= end_tick]
        if actor_id is not None:
            items = [event for event in items if actor_id in event.actor_ids]
        return items[: max(1, min(5000, limit))]

    def public_window(
        self,
        *,
        start_tick: int | None = None,
        end_tick: int | None = None,
        actor_id: str | None = None,
        limit: int = 500,
    ) -> dict:
        events = self.events_between(
            start_tick=start_tick,
            end_tick=end_tick,
            actor_id=actor_id,
            limit=limit,
        )
        return {
            "manifest": self.manifest.as_dict(),
            "events": [public_event(event) for event in events],
        }

    def cause_chain(self, event_id: str, *, max_depth: int = 12) -> list[CrawlEvent]:
        by_id = {event.id: event for event in self.events}
        root = by_id.get(event_id)
        if root is None:
            raise KeyError(event_id)
        selected: dict[str, CrawlEvent] = {root.id: root}
        frontier = [(root, 0)]
        while frontier:
            event, depth = frontier.pop(0)
            if depth >= max_depth:
                continue
            semantic = event.data.get("semantic", {}) if isinstance(event.data, dict) else {}
            for parent_id in semantic.get("causal_parent_ids", []):
                parent = by_id.get(parent_id)
                if parent is not None and parent.id not in selected:
                    selected[parent.id] = parent
                    frontier.append((parent, depth + 1))
        return sorted(selected.values(), key=lambda event: (event.tick, event.id))

    def bootstrap(self) -> dict:
        """Return presentation bootstrap state, not a second source of truth."""

        return {
            "manifest": self.manifest.as_dict(),
            "crawl": public_crawl(self.crawl),
            "current_floor": public_floor(self.crawl),
        }
