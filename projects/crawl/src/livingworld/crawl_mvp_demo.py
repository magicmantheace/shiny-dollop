from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .crawl_director import remaining_budget
from .crawl_persistence import CrawlPersistence
from .crawl_service import CrawlLifecycleService
from .headless_mvp_simulation import HeadlessCrawlMVP
from .semantic_event_ledger import notable_events, semantic_score


def _top_crawlers(crawl, limit: int = 12) -> list[dict[str, Any]]:
    ranked = sorted(
        crawl.participants.values(),
        key=lambda p: (
            p.status.value not in {"dead", "eliminated"},
            p.gameplay.progression.level,
            p.gameplay.kills,
            p.gameplay.encounters_survived,
            p.health,
            p.npc_id,
        ),
        reverse=True,
    )
    rows = []
    for p in ranked[:limit]:
        rows.append(
            {
                "npc_id": p.npc_id,
                "status": p.status.value,
                "health": round(p.health, 4),
                "level": p.gameplay.progression.level,
                "specialization": p.gameplay.progression.specialization,
                "abilities": list(p.gameplay.progression.ability_ids),
                "kills": p.gameplay.kills,
                "encounters_survived": p.gameplay.encounters_survived,
                "inventory_items": len(p.gameplay.inventory_item_ids),
                "party_id": p.current_party_id,
                "memories": len(p.agent.memories) if p.agent else 0,
                "relationships": len(p.agent.relationships) if p.agent else 0,
            }
        )
    return rows


def run_demo(
    *,
    seed: str,
    crawlers: int,
    floors: int,
    max_steps: int,
    output: Path,
) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    database = output.with_suffix(".db")
    if database.exists():
        database.unlink()

    persistence = CrawlPersistence(f"sqlite:///{database}")
    persistence.initialize()
    lifecycle = CrawlLifecycleService(persistence)
    crawl = lifecycle.create_seeded_crawl(
        seed=seed,
        crawler_ids=[f"crawler_{index:04d}" for index in range(crawlers)],
        floor_count=floors,
        ruleset_version="0.4.0-batch3",
    )
    lifecycle.start(crawl)

    mvp = HeadlessCrawlMVP(lifecycle, intermission_ticks=5, director_interval=8)
    mvp.prepare(crawl)
    steps = mvp.run(crawl, max_steps=max_steps)

    events = list(reversed(persistence.list_events(crawl.id, limit=1000)))
    event_counts = Counter(event.event_type for event in events)
    notable = notable_events(events, minimum_score=0.68, limit=30)
    director_state = crawl.modifiers.get("_crawl_director", {})
    semantic_state = crawl.modifiers.get("_semantic_ledger", {})
    floor_cycle_state = crawl.modifiers.get("_floor_cycle", {})

    gameplay_steps = [step.gameplay for step in steps if step.gameplay is not None]
    director_actions = [step.director_action for step in steps if step.director_action]
    floor_transitions = [step.floor_transition for step in steps if step.floor_transition]

    report: dict[str, Any] = {
        "seed": seed,
        "requested": {"crawlers": crawlers, "floors": floors, "max_steps": max_steps},
        "result": {
            "crawl_id": crawl.id,
            "status": crawl.status.value,
            "tick": crawl.current_tick,
            "current_floor": crawl.current_floor,
            "survivors": crawl.surviving_crawler_count,
            "eliminated": crawl.eliminated_crawler_count,
            "steps": len(steps),
        },
        "activity": {
            "moves": sum(step.moved for step in gameplay_steps),
            "rests": sum(step.rested for step in gameplay_steps),
            "discoveries": sum(step.discovered for step in gameplay_steps),
            "encounters_resolved": sum(step.encounters_resolved for step in gameplay_steps),
            "deaths_observed_in_steps": sum(step.deaths for step in gameplay_steps),
            "parties_formed": sum(step.parties_formed for step in gameplay_steps),
            "items_looted": sum(step.items_looted for step in gameplay_steps),
            "director_actions": Counter(director_actions),
            "floor_transitions": floor_transitions,
        },
        "systems": {
            "parties_total": len(crawl.parties),
            "parties_active": sum(party.active for party in crawl.parties.values()),
            "items_live": len(crawl.items),
            "encounters_total": len(crawl.encounters),
            "director_interventions": len(director_state.get("interventions", [])),
            "director_remaining_budget_current_floor": round(remaining_budget(crawl), 4),
            "semantic_notable_ids": len(semantic_state.get("notable_event_ids", [])),
            "floor_phase": floor_cycle_state.get("phase"),
        },
        "event_counts_recent_1000": dict(sorted(event_counts.items())),
        "notable_events_recent_1000": [
            {
                "id": event.id,
                "tick": event.tick,
                "floor": event.floor_number,
                "type": event.event_type,
                "summary": event.summary,
                "actors": event.actor_ids,
                "location_id": event.location_id,
                "importance": semantic_score(event),
                "semantic": event.data.get("semantic", {}),
            }
            for event in notable
        ],
        "top_crawlers": _top_crawlers(crawl),
    }

    report["mvp_gate"] = {
        "minimum_100_crawlers": crawl.starting_crawler_count >= 100,
        "minimum_3_floors": len(crawl.floors) >= 3,
        "crawl_reached_terminal_state": crawl.status.value == "completed",
        "generated_encounters": len(crawl.encounters) > 0,
        "structured_event_history": len(crawl.history_event_ids) > 0,
        "semantic_metadata_present": any("semantic" in event.data for event in events),
        "director_operational": len(director_state.get("interventions", [])) > 0,
        "state_counts_valid": crawl.surviving_crawler_count + crawl.eliminated_crawler_count == crawl.starting_crawler_count,
    }
    report["mvp_gate"]["overall"] = all(report["mvp_gate"].values())

    output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Crawl v0.4 Batch 3 headless MVP demonstration.")
    parser.add_argument("--seed", default="crawl-batch3-mvp")
    parser.add_argument("--crawlers", type=int, default=100)
    parser.add_argument("--floors", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=25000)
    parser.add_argument("--output", default="validation/crawl-v0.4-slices12-15-mvp.json")
    args = parser.parse_args()

    report = run_demo(
        seed=args.seed,
        crawlers=max(1, args.crawlers),
        floors=max(1, args.floors),
        max_steps=max(1, args.max_steps),
        output=Path(args.output),
    )
    print(json.dumps(report["result"], indent=2))
    print(json.dumps(report["mvp_gate"], indent=2))
    if args.crawlers >= 100 and args.floors >= 3 and not report["mvp_gate"]["overall"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
