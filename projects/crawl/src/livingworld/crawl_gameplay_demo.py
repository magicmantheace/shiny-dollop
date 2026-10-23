from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .crawl_domain import CrawlStatus, ParticipationStatus
from .crawl_service import CrawlLifecycleService
from .gameplay_simulation import GameplayCrawlSimulator


def build_report(crawl, summaries) -> dict:
    encounter_types = Counter(encounter.type.value for encounter in crawl.encounters.values())
    encounter_statuses = Counter(encounter.status.value for encounter in crawl.encounters.values())
    rarity_counts = Counter(item.rarity.value for item in crawl.items.values())
    specializations = Counter(
        participant.gameplay.progression.specialization or "unassigned"
        for participant in crawl.participants.values()
    )
    active_parties = [party for party in crawl.parties.values() if party.active]
    top_crawlers = sorted(
        crawl.participants.values(),
        key=lambda participant: (
            -participant.gameplay.progression.level,
            -participant.gameplay.kills,
            -participant.gameplay.encounters_survived,
            participant.npc_id,
        ),
    )[:15]

    return {
        "seed": crawl.seed,
        "crawl_id": crawl.id,
        "status": crawl.status.value,
        "ticks": crawl.current_tick,
        "floors": len(crawl.floors),
        "starting_crawlers": crawl.starting_crawler_count,
        "survivors": crawl.surviving_crawler_count,
        "eliminated": crawl.eliminated_crawler_count,
        "dead": sum(participant.status == ParticipationStatus.DEAD for participant in crawl.participants.values()),
        "steps": len(summaries),
        "moves": sum(summary.moved for summary in summaries),
        "rests": sum(summary.rested for summary in summaries),
        "discoveries": sum(summary.discovered for summary in summaries),
        "parties_formed": sum(summary.parties_formed for summary in summaries),
        "active_parties": len(active_parties),
        "encounters_resolved_by_steps": sum(summary.encounters_resolved for summary in summaries),
        "encounter_types": dict(sorted(encounter_types.items())),
        "encounter_statuses": dict(sorted(encounter_statuses.items())),
        "remaining_items_by_rarity": dict(sorted(rarity_counts.items())),
        "specializations": dict(sorted(specializations.items())),
        "total_kills": sum(participant.gameplay.kills for participant in crawl.participants.values()),
        "total_damage_dealt": round(sum(participant.gameplay.damage_dealt for participant in crawl.participants.values()), 4),
        "total_damage_taken": round(sum(participant.gameplay.damage_taken for participant in crawl.participants.values()), 4),
        "injuries_remaining": sum(len(participant.gameplay.injuries) for participant in crawl.participants.values()),
        "fingerprint": crawl.fingerprint(),
        "top_crawlers": [
            {
                "npc_id": participant.npc_id,
                "status": participant.status.value,
                "health": round(participant.health, 4),
                "level": participant.gameplay.progression.level,
                "specialization": participant.gameplay.progression.specialization,
                "abilities": list(participant.gameplay.progression.ability_ids),
                "kills": participant.gameplay.kills,
                "encounters_survived": participant.gameplay.encounters_survived,
                "inventory_items": len(participant.gameplay.inventory_item_ids),
                "party_id": participant.current_party_id,
            }
            for participant in top_crawlers
        ],
    }


def run_demo(seed: str, crawlers: int, floors: int, max_steps: int) -> dict:
    if crawlers < 1 or floors < 1 or max_steps < 1:
        raise ValueError("crawlers, floors, and max_steps must be positive")
    lifecycle = CrawlLifecycleService()
    crawl = lifecycle.create_seeded_crawl(
        seed=seed,
        crawler_ids=[f"crawler_{index:06d}" for index in range(crawlers)],
        floor_count=floors,
    )
    lifecycle.start(crawl)
    simulator = GameplayCrawlSimulator(lifecycle)
    summaries = simulator.run(crawl, max_steps=max_steps)
    report = build_report(crawl, summaries)
    if crawl.status == CrawlStatus.RUNNING:
        report["warning"] = "crawl did not reach a terminal state before max_steps"
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Crawl v0.4 Slices 7-11 gameplay demo.")
    parser.add_argument("--seed", default="crawl-gameplay-evening")
    parser.add_argument("--crawlers", type=int, default=100)
    parser.add_argument("--floors", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=10000)
    parser.add_argument("--output", default="validation/crawl-v0.4-slices7-11-demo.json")
    args = parser.parse_args()

    report = run_demo(args.seed, args.crawlers, args.floors, args.max_steps)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    if report.get("warning"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
