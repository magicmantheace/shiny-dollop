from __future__ import annotations

from hashlib import sha256
from typing import Iterable

from .crawl_domain import (
    Crawl,
    CrawlEvent,
    CrawlerParticipation,
    CrawlStatus,
    FloorStatus,
    ParticipationStatus,
)
from .crawl_persistence import CrawlPersistence
from .crawler_domain import build_crawler_agent
from .floor_generation import generate_floor
from .semantic_event_ledger import annotate_event


def _stable_id(prefix: str, *parts: object) -> str:
    payload = ":".join(str(part) for part in parts)
    digest = sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


class CrawlLifecycleService:
    def __init__(self, persistence: CrawlPersistence | None = None) -> None:
        self.persistence = persistence

    def create_seeded_crawl(
        self,
        *,
        seed: str,
        crawler_ids: Iterable[str],
        floor_count: int = 3,
        ruleset_id: str = "crawl.standard",
        ruleset_version: str = "0.4.0",
        modifiers: dict | None = None,
        crawl_id: str | None = None,
    ) -> Crawl:
        if floor_count < 1:
            raise ValueError("floor_count must be at least 1")
        supplied_ids = tuple(crawler_ids)
        ids = tuple(dict.fromkeys(supplied_ids))
        if not ids:
            raise ValueError("at least one crawler is required")
        if len(ids) != len(supplied_ids):
            raise ValueError("crawler_ids must be unique")

        roster_fingerprint = sha256("|".join(sorted(ids)).encode("utf-8")).hexdigest()[:12]
        actual_id = crawl_id or _stable_id(
            "crawl", seed, ruleset_id, ruleset_version, floor_count, roster_fingerprint
        )
        floors = {number: generate_floor(seed, number) for number in range(1, floor_count + 1)}
        entrance = floors[1].entrance_location_id
        participants = {
            npc_id: CrawlerParticipation(
                npc_id=npc_id,
                crawl_id=actual_id,
                current_floor=1,
                current_location_id=entrance,
                agent=build_crawler_agent(seed, npc_id),
            )
            for npc_id in ids
        }
        crawl = Crawl(
            id=actual_id,
            seed=seed,
            ruleset_id=ruleset_id,
            ruleset_version=ruleset_version,
            starting_crawler_count=len(participants),
            surviving_crawler_count=len(participants),
            eliminated_crawler_count=0,
            modifiers=modifiers or {},
            floors=floors,
            participants=participants,
        )
        self._record(crawl, "CRAWL_CREATED", "Seeded crawl created.")
        self._save(crawl)
        return crawl

    def start(self, crawl: Crawl, *, tick: int = 0) -> Crawl:
        if crawl.status != CrawlStatus.PLANNED:
            raise ValueError("only a planned crawl can be started")
        if tick < crawl.current_tick:
            raise ValueError("start tick cannot move backwards")
        crawl.current_tick = tick
        crawl.started_at_tick = tick
        crawl.status = CrawlStatus.RUNNING
        self._activate_floor(crawl, 1)
        self._record(crawl, "CRAWL_STARTED", "Crawl started.")
        self._save(crawl)
        return crawl

    def set_tick(self, crawl: Crawl, tick: int) -> Crawl:
        if tick < crawl.current_tick:
            raise ValueError("crawl tick cannot move backwards")
        crawl.current_tick = tick
        self._save(crawl)
        return crawl

    def eliminate(
        self,
        crawl: Crawl,
        npc_id: str,
        *,
        dead: bool = False,
        summary: str | None = None,
    ) -> Crawl:
        if crawl.status != CrawlStatus.RUNNING:
            raise ValueError("crawler elimination requires a running crawl")
        participant = crawl.participants.get(npc_id)
        if participant is None:
            raise KeyError(f"crawler {npc_id!r} is not participating")
        if participant.status in {ParticipationStatus.DEAD, ParticipationStatus.ELIMINATED}:
            return crawl

        participant.status = ParticipationStatus.DEAD if dead else ParticipationStatus.ELIMINATED
        if dead:
            participant.health = 0.0
        self._recount(crawl)
        current_floor = crawl.floors[crawl.current_floor]
        current_floor.active_crawler_count = crawl.surviving_crawler_count
        self._record(
            crawl,
            "CRAWLER_DIED" if dead else "CRAWLER_ELIMINATED",
            summary or f"Crawler {npc_id} was {'killed' if dead else 'eliminated'}.",
            actor_ids=[npc_id],
            location_id=participant.current_location_id,
            data={"state_changes": {"participation_status": participant.status.value, "health": participant.health}},
        )
        self._save(crawl)
        return crawl

    def complete_current_floor(
        self,
        crawl: Crawl,
        *,
        advance_ticks: int = 1,
        activate_next: bool = True,
    ) -> Crawl:
        if crawl.status != CrawlStatus.RUNNING:
            raise ValueError("floor completion requires a running crawl")
        if advance_ticks < 0:
            raise ValueError("advance_ticks cannot be negative")

        floor_state = crawl.floors[crawl.current_floor]
        if floor_state.status != FloorStatus.ACTIVE:
            raise ValueError("current floor is not active")
        floor_state.status = FloorStatus.COMPLETED
        floor_state.active_crawler_count = 0
        crawl.current_tick += advance_ticks

        for participant in crawl.participants.values():
            if participant.status == ParticipationStatus.ACTIVE:
                participant.status = ParticipationStatus.ADVANCED

        self._record(
            crawl,
            "FLOOR_COMPLETED",
            f"Floor {floor_state.number} completed.",
            floor_number=floor_state.number,
            data={"state_changes": {"floor_status": "completed"}},
        )

        if crawl.current_floor == max(crawl.floors):
            crawl.status = CrawlStatus.COMPLETED
            self._record(
                crawl,
                "CRAWL_COMPLETED",
                "Final floor completed.",
                data={"state_changes": {"crawl_status": "completed"}},
            )
            self._save(crawl)
            return crawl

        next_number = crawl.current_floor + 1
        crawl.current_floor = next_number
        next_floor = crawl.floors[next_number]
        entrance = next_floor.entrance_location_id
        for participant in crawl.participants.values():
            if participant.status == ParticipationStatus.ADVANCED:
                participant.status = ParticipationStatus.ACTIVE
                participant.current_floor = next_number
                participant.current_location_id = entrance
                participant.floor_statistics = {}
                if participant.agent is not None:
                    participant.agent.current_plan = []
                    participant.agent.needs.perceived_danger = 0.0
        if activate_next:
            self._activate_floor(crawl, next_number)
        else:
            next_floor.status = FloorStatus.PENDING
            next_floor.started_at_tick = None
            next_floor.deadline_tick = None
            next_floor.active_crawler_count = 0
        self._save(crawl)
        return crawl

    def activate_floor(self, crawl: Crawl, number: int | None = None) -> Crawl:
        if crawl.status != CrawlStatus.RUNNING:
            raise ValueError("floor activation requires a running crawl")
        floor_number = crawl.current_floor if number is None else number
        if floor_number != crawl.current_floor:
            raise ValueError("only the current floor can be activated")
        floor_state = crawl.floors[floor_number]
        if floor_state.status == FloorStatus.ACTIVE:
            return crawl
        if floor_state.status != FloorStatus.PENDING:
            raise ValueError("only a pending floor can be activated")
        self._activate_floor(crawl, floor_number)
        self._save(crawl)
        return crawl

    def archive(self, crawl: Crawl) -> Crawl:
        if crawl.status != CrawlStatus.COMPLETED:
            raise ValueError("only a completed crawl can be archived")
        crawl.status = CrawlStatus.ARCHIVED
        crawl.archived_at_tick = crawl.current_tick
        self._record(
            crawl,
            "CRAWL_ARCHIVED",
            "Crawl archived.",
            data={"state_changes": {"crawl_status": "archived"}},
        )
        self._save(crawl)
        return crawl

    def record_event(
        self,
        crawl: Crawl,
        event_type: str,
        summary: str,
        *,
        floor_number: int | None = None,
        actor_ids: list[str] | None = None,
        location_id: str | None = None,
        data: dict | None = None,
    ) -> CrawlEvent:
        event = self._record(
            crawl,
            event_type,
            summary,
            floor_number=floor_number,
            actor_ids=actor_ids,
            location_id=location_id,
            data=data,
        )
        self._save(crawl)
        return event

    def save(self, crawl: Crawl) -> None:
        self._save(crawl)

    def _activate_floor(self, crawl: Crawl, number: int) -> None:
        floor_state = crawl.floors[number]
        floor_state.status = FloorStatus.ACTIVE
        floor_state.started_at_tick = crawl.current_tick
        duration = int(floor_state.completion_rules.get("floor_duration_ticks", 10_000))
        floor_state.deadline_tick = crawl.current_tick + max(1, duration)
        floor_state.active_crawler_count = crawl.surviving_crawler_count
        self._record(
            crawl,
            "FLOOR_STARTED",
            f"Floor {number} started.",
            floor_number=number,
            data={
                "deadline_tick": floor_state.deadline_tick,
                "state_changes": {"floor_status": "active"},
            },
        )

    def _recount(self, crawl: Crawl) -> None:
        eliminated = sum(
            participant.status in {ParticipationStatus.DEAD, ParticipationStatus.ELIMINATED}
            for participant in crawl.participants.values()
        )
        crawl.eliminated_crawler_count = int(eliminated)
        crawl.surviving_crawler_count = crawl.starting_crawler_count - crawl.eliminated_crawler_count

    def _record(
        self,
        crawl: Crawl,
        event_type: str,
        summary: str,
        *,
        floor_number: int | None = None,
        actor_ids: list[str] | None = None,
        location_id: str | None = None,
        data: dict | None = None,
    ) -> CrawlEvent:
        event_id = _stable_id(
            "crawl_event",
            crawl.id,
            len(crawl.history_event_ids),
            crawl.current_tick,
            event_type,
        )
        event = CrawlEvent(
            id=event_id,
            crawl_id=crawl.id,
            floor_number=floor_number if floor_number is not None else crawl.current_floor,
            tick=crawl.current_tick,
            event_type=event_type,
            summary=summary,
            actor_ids=actor_ids or [],
            location_id=location_id,
            data=data or {},
        )
        annotate_event(crawl, event)
        crawl.history_event_ids.append(event.id)
        if self.persistence is not None:
            self.persistence.append_event(event)
        return event

    def _save(self, crawl: Crawl) -> None:
        validated = Crawl.model_validate(crawl.model_dump(mode="python"))
        if self.persistence is not None:
            self.persistence.save_crawl(validated)
