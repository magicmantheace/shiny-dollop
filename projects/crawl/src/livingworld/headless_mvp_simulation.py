from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .crawl_director import CrawlDirector
from .crawl_domain import Crawl, CrawlStatus
from .crawl_service import CrawlLifecycleService
from .floor_lifecycle import FloorLifecycleService, floor_phase
from .gameplay_simulation import GameplayCrawlSimulator, GameplayStepSummary


@dataclass
class MVPGameplayStep:
    tick: int
    phase: str
    gameplay: GameplayStepSummary | None = None
    director_action: str | None = None
    floor_transition: dict[str, Any] | None = None


class HeadlessCrawlMVP:
    """Compose Slices 2-14 into the Slice 15 headless crawl milestone."""

    def __init__(
        self,
        lifecycle: CrawlLifecycleService,
        *,
        intermission_ticks: int = 5,
        director_interval: int = 8,
    ) -> None:
        self.lifecycle = lifecycle
        self.gameplay = GameplayCrawlSimulator(lifecycle, auto_complete_floors=False)
        self.floor_cycle = FloorLifecycleService(lifecycle, intermission_ticks=intermission_ticks)
        self.director = CrawlDirector(lifecycle, minimum_interval=director_interval)

    def prepare(self, crawl: Crawl) -> None:
        self.gameplay.prepare(crawl)
        self.floor_cycle.synchronize(crawl)
        self.lifecycle._record(
            crawl,
            "HEADLESS_MVP_PREPARED",
            "Headless autonomous crawl systems prepared.",
            data={
                "crawler_count": crawl.starting_crawler_count,
                "floor_count": len(crawl.floors),
                "state_changes": {"mvp_prepared": True},
            },
        )
        self.lifecycle.save(crawl)

    def step(self, crawl: Crawl) -> MVPGameplayStep:
        if crawl.status != CrawlStatus.RUNNING:
            return MVPGameplayStep(tick=crawl.current_tick, phase="complete")

        phase = floor_phase(crawl)
        if phase == "intermission":
            transition = self.floor_cycle.evaluate(crawl)
            return MVPGameplayStep(
                tick=crawl.current_tick,
                phase=floor_phase(crawl),
                gameplay=None,
                floor_transition=transition,
            )

        current_floor = crawl.floors[crawl.current_floor]
        if current_floor.status.value == "pending":
            self.lifecycle.activate_floor(crawl, crawl.current_floor)
            self.floor_cycle.synchronize(crawl)

        gameplay_summary = self.gameplay.step(crawl)
        if crawl.status != CrawlStatus.RUNNING:
            return MVPGameplayStep(
                tick=crawl.current_tick,
                phase="complete",
                gameplay=gameplay_summary,
            )

        director_result = self.director.evaluate(crawl)
        transition = self.floor_cycle.evaluate(crawl)
        self.lifecycle.save(crawl)
        return MVPGameplayStep(
            tick=crawl.current_tick,
            phase=floor_phase(crawl),
            gameplay=gameplay_summary,
            director_action=director_result.get("action") if director_result else None,
            floor_transition=transition,
        )

    def run(self, crawl: Crawl, *, max_steps: int = 25_000) -> list[MVPGameplayStep]:
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        if not crawl.encounters:
            self.prepare(crawl)

        steps: list[MVPGameplayStep] = []
        for _ in range(max_steps):
            if crawl.status != CrawlStatus.RUNNING:
                break
            steps.append(self.step(crawl))
        return steps
