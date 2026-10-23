from __future__ import annotations

from dataclasses import dataclass

from .crawl_domain import Crawl, CrawlStatus, ParticipationStatus
from .crawl_service import CrawlLifecycleService
from .crawler_decision import choose_action
from .crawler_navigation import choose_destination, perceive, recover, traverse
from .crawler_social import remember, relationship


@dataclass
class StepSummary:
    tick: int
    moved: int = 0
    rested: int = 0
    discovered: int = 0
    floor_completed: bool = False


class AutonomousCrawlSimulator:
    """Headless autonomous movement/perception loop for v0.4 Slices 2-6.

    Combat, loot acquisition, parties, and encounters are intentionally deferred.
    This loop proves that distinct persistent crawlers can perceive incomplete
    information, choose bounded goals, navigate a procedural floor, and persist
    the consequences of those choices.
    """

    def __init__(self, lifecycle: CrawlLifecycleService) -> None:
        self.lifecycle = lifecycle

    def step(self, crawl: Crawl) -> StepSummary:
        if crawl.status != CrawlStatus.RUNNING:
            raise ValueError("autonomous step requires a running crawl")

        crawl.current_tick += 1
        floor = crawl.floors[crawl.current_floor]
        summary = StepSummary(tick=crawl.current_tick)

        for npc_id in sorted(crawl.participants):
            participant = crawl.participants[npc_id]
            if participant.status != ParticipationStatus.ACTIVE:
                continue
            if participant.current_floor != crawl.current_floor or participant.agent is None:
                continue

            # Reaching the advancement gate is a terminal navigation state for this floor.
            # Crawlers wait there instead of wandering back out, allowing independent
            # arrival times to converge into deterministic floor completion.
            if participant.current_location_id in floor.exit_location_ids:
                participant.current_objective = "await_floor_completion"
                continue

            discoveries = perceive(participant, floor, crawl.current_tick)
            summary.discovered += len(discoveries)
            for location_id in discoveries:
                event = self.lifecycle._record(
                    crawl,
                    "LOCATION_DISCOVERED",
                    f"Crawler {npc_id} discovered a reachable location.",
                    actor_ids=[npc_id],
                    location_id=location_id,
                    data={"discovered_location_id": location_id},
                )
                remember(
                    participant.agent,
                    event_id=event.id,
                    event_type=event.event_type,
                    tick=crawl.current_tick,
                    floor_number=crawl.current_floor,
                    emotion="curious",
                    importance=0.18,
                )

            decision = choose_action(participant.agent, health=participant.health, seed=floor.seed)
            participant.current_objective = decision.action
            destination = choose_destination(participant, floor, decision)
            if destination is None or destination == participant.current_location_id:
                recover(participant, floor)
                summary.rested += 1
                self.lifecycle._record(
                    crawl,
                    "CRAWLER_RESTED",
                    f"Crawler {npc_id} paused to recover.",
                    actor_ids=[npc_id],
                    location_id=participant.current_location_id,
                    data={"decision": decision.action, "score": decision.score},
                )
                continue

            origin = participant.current_location_id
            cost = traverse(participant, floor, destination)
            perceive(participant, floor, crawl.current_tick)
            summary.moved += 1
            event = self.lifecycle._record(
                crawl,
                "CRAWLER_MOVED",
                f"Crawler {npc_id} moved between crawl locations.",
                actor_ids=[npc_id],
                location_id=destination,
                data={
                    "from": origin,
                    "to": destination,
                    "cost": cost,
                    "decision": decision.action,
                    "score": decision.score,
                },
            )
            remember(
                participant.agent,
                event_id=event.id,
                event_type=event.event_type,
                tick=crawl.current_tick,
                floor_number=crawl.current_floor,
                emotion="alert" if floor.locations[destination].hazards else "neutral",
                importance=0.12 + min(0.3, floor.danger_level * 0.25),
            )

        self._update_colocation_social_state(crawl)

        active = [
            item
            for item in crawl.participants.values()
            if item.status == ParticipationStatus.ACTIVE and item.current_floor == crawl.current_floor
        ]
        if active and all(item.current_location_id in floor.exit_location_ids for item in active):
            self.lifecycle.complete_current_floor(crawl, advance_ticks=0)
            summary.floor_completed = True
        else:
            self.lifecycle.save(crawl)
        return summary

    def run(self, crawl: Crawl, *, max_steps: int = 5_000) -> list[StepSummary]:
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        summaries: list[StepSummary] = []
        for _ in range(max_steps):
            if crawl.status != CrawlStatus.RUNNING:
                break
            summaries.append(self.step(crawl))
        return summaries

    def _update_colocation_social_state(self, crawl: Crawl) -> None:
        by_location: dict[str, list[str]] = {}
        for npc_id, participant in crawl.participants.items():
            if participant.status != ParticipationStatus.ACTIVE or participant.current_location_id is None:
                continue
            by_location.setdefault(participant.current_location_id, []).append(npc_id)

        for members in by_location.values():
            if len(members) < 2:
                continue
            ordered = sorted(members)
            for npc_id in ordered:
                agent = crawl.participants[npc_id].agent
                if agent is None:
                    continue
                for other_id in ordered:
                    if other_id == npc_id:
                        continue
                    rel = relationship(agent, other_id)
                    rel.familiarity = min(1.0, rel.familiarity + 0.002)
