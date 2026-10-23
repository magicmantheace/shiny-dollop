from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from .crawl_domain import Crawl, CrawlStatus
from .crawl_service import CrawlLifecycleService
from .detail_tiers import due_crawlers, rebalance_detail_tiers, tier_distribution
from .headless_mvp_simulation import HeadlessCrawlMVP


@dataclass
class LiveTierTelemetry:
    steps: int = 0
    elapsed_seconds: float = 0.0
    full_frequency_updates: int = 0
    scheduled_updates: int = 0
    rebalances: int = 0
    observed_distributions: list[dict[str, int]] = field(default_factory=list)

    @property
    def scheduled_ratio(self) -> float:
        if self.full_frequency_updates <= 0:
            return 0.0
        return self.scheduled_updates / self.full_frequency_updates

    def as_dict(self) -> dict[str, object]:
        ratio = self.scheduled_ratio
        return {
            "steps": self.steps,
            "elapsed_seconds": round(self.elapsed_seconds, 6),
            "full_frequency_updates": self.full_frequency_updates,
            "scheduled_updates": self.scheduled_updates,
            "scheduled_ratio": round(ratio, 6),
            "estimated_update_reduction": round(1.0 - ratio, 6) if self.full_frequency_updates else 0.0,
            "rebalances": self.rebalances,
            "observed_distributions": self.observed_distributions,
        }


def run_with_live_tier_probe(
    crawl: Crawl,
    lifecycle: CrawlLifecycleService,
    *,
    max_steps: int,
    focused_ids: list[str] | None = None,
    rebalance_interval: int = 4,
    intermission_ticks: int = 2,
    director_interval: int = 6,
) -> LiveTierTelemetry:
    """Run the proven MVP loop while exercising tier assignment/scheduling live.

    Detail tiers remain scheduling metadata in Slice 16, so they do not yet suppress
    authoritative gameplay updates. This probe verifies that promotion/demotion and
    due-update calculations operate against a changing live crawl rather than a
    completed terminal state. Later coarse Tier C/D execution can consume the same
    deterministic scheduler boundary without changing this validation contract.
    """

    if max_steps < 1:
        raise ValueError("max_steps must be positive")
    if rebalance_interval < 1:
        raise ValueError("rebalance_interval must be positive")

    focus = list(focused_ids or sorted(crawl.participants)[: min(5, len(crawl.participants))])
    mvp = HeadlessCrawlMVP(
        lifecycle,
        intermission_ticks=intermission_ticks,
        director_interval=director_interval,
    )
    if not crawl.encounters:
        mvp.prepare(crawl)

    telemetry = LiveTierTelemetry()
    started = perf_counter()

    for index in range(max_steps):
        if crawl.status != CrawlStatus.RUNNING:
            break

        if index == 0 or index % rebalance_interval == 0:
            distribution = rebalance_detail_tiers(crawl, focused_ids=focus)
            telemetry.observed_distributions.append(distribution)
            telemetry.rebalances += 1

        active_count = sum(1 for participant in crawl.participants.values() if participant.status.value == "active")
        telemetry.full_frequency_updates += active_count
        telemetry.scheduled_updates += len(due_crawlers(crawl, crawl.current_tick))

        mvp.step(crawl)
        telemetry.steps += 1

    telemetry.elapsed_seconds = perf_counter() - started

    # Preserve a final observable tier snapshot without relying on it for scheduler
    # load accounting; terminal crawlers will naturally settle into Tier D.
    rebalance_detail_tiers(crawl, focused_ids=focus)
    telemetry.observed_distributions.append(tier_distribution(crawl))
    return telemetry
