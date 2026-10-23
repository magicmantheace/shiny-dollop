from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

from .crawl_domain import Crawl, CrawlStatus
from .crawl_service import CrawlLifecycleService
from .detail_tiers import tier_distribution
from .tier_runtime_probe import run_with_live_tier_probe


@dataclass
class SeedResult:
    seed: str
    completed: bool
    steps: int
    ticks: int
    survivors: int
    eliminated: int
    floors_reached: int
    parties: int
    encounters_resolved: int
    encounters_total: int
    items_owned: int
    level_min: int
    level_max: int
    director_interventions: int
    semantic_notable_events: int
    history_events: int
    state_bytes: int
    elapsed_seconds: float
    fingerprint: str
    replay_fingerprint: str
    deterministic_replay: bool
    model_valid: bool
    tier_distribution: dict[str, int]
    scheduler_load: dict[str, object]


def _crawler_ids(count: int) -> list[str]:
    return [f"scale_crawler_{index:06d}" for index in range(count)]


def _run_once(seed: str, crawlers: int, floors: int, max_steps: int) -> tuple[Crawl, dict[str, object]]:
    service = CrawlLifecycleService()
    crawl = service.create_seeded_crawl(seed=seed, crawler_ids=_crawler_ids(crawlers), floor_count=floors)
    service.start(crawl)
    focused = sorted(crawl.participants)[: min(5, crawlers)]
    telemetry = run_with_live_tier_probe(
        crawl,
        service,
        max_steps=max_steps,
        focused_ids=focused,
        rebalance_interval=4,
        intermission_ticks=2,
        director_interval=6,
    )
    return crawl, telemetry.as_dict()


def validate_seed(seed: str, *, crawlers: int, floors: int, max_steps: int, replay: bool = True) -> SeedResult:
    crawl, scheduler = _run_once(seed, crawlers, floors, max_steps)
    steps = int(scheduler["steps"])
    elapsed = float(scheduler["elapsed_seconds"])

    model_valid = True
    try:
        Crawl.model_validate(crawl.model_dump(mode="python"))
    except Exception:
        model_valid = False

    replay_fingerprint = ""
    deterministic = True
    if replay:
        replay_crawl, replay_scheduler = _run_once(seed, crawlers, floors, max_steps)
        replay_fingerprint = replay_crawl.fingerprint()
        deterministic = (
            replay_fingerprint == crawl.fingerprint()
            and int(replay_scheduler["steps"]) == steps
            and int(replay_scheduler["scheduled_updates"]) == int(scheduler["scheduled_updates"])
            and replay_scheduler["observed_distributions"] == scheduler["observed_distributions"]
        )

    levels = [participant.gameplay.progression.level for participant in crawl.participants.values()]
    encounters_resolved = sum(1 for encounter in crawl.encounters.values() if encounter.status.value == "resolved")
    items_owned = sum(1 for item in crawl.items.values() if item.owner_npc_id is not None)
    director_state = crawl.modifiers.get("_crawl_director", {})
    semantic_state = crawl.modifiers.get("_semantic_ledger", {})

    return SeedResult(
        seed=seed,
        completed=crawl.status == CrawlStatus.COMPLETED,
        steps=steps,
        ticks=crawl.current_tick,
        survivors=crawl.surviving_crawler_count,
        eliminated=crawl.eliminated_crawler_count,
        floors_reached=crawl.current_floor,
        parties=sum(1 for party in crawl.parties.values() if party.active),
        encounters_resolved=encounters_resolved,
        encounters_total=len(crawl.encounters),
        items_owned=items_owned,
        level_min=min(levels) if levels else 0,
        level_max=max(levels) if levels else 0,
        director_interventions=len(director_state.get("interventions", [])),
        semantic_notable_events=len(semantic_state.get("notable_event_ids", [])),
        history_events=len(crawl.history_event_ids),
        state_bytes=len(crawl.model_dump_json()),
        elapsed_seconds=round(elapsed, 6),
        fingerprint=crawl.fingerprint(),
        replay_fingerprint=replay_fingerprint,
        deterministic_replay=deterministic,
        model_valid=model_valid,
        tier_distribution=tier_distribution(crawl),
        scheduler_load=scheduler,
    )


def run_matrix(*, base_seed: str, seeds: int, crawlers: int, floors: int, max_steps: int, replay: bool = True) -> dict:
    if seeds < 1 or crawlers < 1 or floors < 1:
        raise ValueError("seeds, crawlers, and floors must be positive")

    results: list[SeedResult] = []
    started = time.perf_counter()
    for index in range(seeds):
        digest = sha256(f"{base_seed}:{index}".encode("utf-8")).hexdigest()[:12]
        seed = f"{base_seed}-{index:03d}-{digest}"
        results.append(validate_seed(seed, crawlers=crawlers, floors=floors, max_steps=max_steps, replay=replay))
    wall = time.perf_counter() - started

    elapsed_values = [item.elapsed_seconds for item in results]
    survival_rates = [item.survivors / crawlers for item in results]
    scheduler_ratios = [float(item.scheduler_load["scheduled_ratio"]) for item in results]
    scheduler_live_failures = [
        item.seed
        for item in results
        if int(item.scheduler_load["full_frequency_updates"]) <= 0
        or int(item.scheduler_load["scheduled_updates"]) <= 0
        or not (0.0 < float(item.scheduler_load["scheduled_ratio"]) < 1.0)
    ]
    structural_failures = [item.seed for item in results if not item.completed or not item.model_valid]
    replay_failures = [item.seed for item in results if replay and not item.deterministic_replay]

    report = {
        "matrix": {
            "base_seed": base_seed,
            "seeds": seeds,
            "crawlers_per_seed": crawlers,
            "floors_per_seed": floors,
            "max_steps": max_steps,
            "deterministic_replay_enabled": replay,
        },
        "summary": {
            "completed_runs": sum(1 for item in results if item.completed),
            "structural_failures": structural_failures,
            "replay_failures": replay_failures,
            "scheduler_live_failures": scheduler_live_failures,
            "survival_rate_mean": round(statistics.mean(survival_rates), 6),
            "survival_rate_min": round(min(survival_rates), 6),
            "survival_rate_max": round(max(survival_rates), 6),
            "elapsed_seconds_mean": round(statistics.mean(elapsed_values), 6),
            "elapsed_seconds_max": round(max(elapsed_values), 6),
            "matrix_wall_seconds": round(wall, 6),
            "scheduler_ratio_mean": round(statistics.mean(scheduler_ratios), 6),
            "all_structural_invariants_passed": not structural_failures,
            "all_replays_deterministic": not replay_failures,
            "live_scheduler_exercised": not scheduler_live_failures,
            "overall": not structural_failures and not replay_failures and not scheduler_live_failures,
        },
        "results": [asdict(item) for item in results],
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Crawl v0.5 multi-seed validation matrix")
    parser.add_argument("--base-seed", default="crawl-v05-matrix")
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--crawlers", type=int, default=100)
    parser.add_argument("--floors", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=25000)
    parser.add_argument("--skip-replay", action="store_true")
    parser.add_argument("--output", default="validation/crawl-v0.5-slices16-18-matrix.json")
    args = parser.parse_args()

    report = run_matrix(
        base_seed=args.base_seed,
        seeds=args.seeds,
        crawlers=args.crawlers,
        floors=args.floors,
        max_steps=args.max_steps,
        replay=not args.skip_replay,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Report: {output}")
    if not report["summary"]["overall"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
