from __future__ import annotations

import argparse
import json
from pathlib import Path

from .crawl_service import CrawlLifecycleService
from .crawl_simulation import AutonomousCrawlSimulator


def build_report(*, seed: str, crawlers: int, floors: int, max_steps: int) -> dict:
    service = CrawlLifecycleService()
    crawler_ids = [f"demo_crawler_{index:04d}" for index in range(crawlers)]
    crawl = service.create_seeded_crawl(seed=seed, crawler_ids=crawler_ids, floor_count=floors)
    service.start(crawl)
    simulator = AutonomousCrawlSimulator(service)
    summaries = simulator.run(crawl, max_steps=max_steps)

    agents = [item.agent for item in crawl.participants.values() if item.agent is not None]
    goal_counts: dict[str, int] = {}
    for agent in agents:
        goal_counts[agent.current_goal] = goal_counts.get(agent.current_goal, 0) + 1

    total_moves = sum(item.floor_statistics.get("moves", 0.0) for item in crawl.participants.values())
    total_memories = sum(len(agent.memories) for agent in agents)
    total_relationships = sum(len(agent.relationships) for agent in agents)
    total_knowledge = sum(len(agent.knowledge) for agent in agents)

    samples = []
    for npc_id in sorted(crawl.participants)[: min(10, crawlers)]:
        participant = crawl.participants[npc_id]
        agent = participant.agent
        if agent is None:
            continue
        samples.append(
            {
                "npc_id": npc_id,
                "status": participant.status.value,
                "floor": participant.current_floor,
                "location": participant.current_location_id,
                "goal": agent.current_goal,
                "moves_current_floor": participant.floor_statistics.get("moves", 0.0),
                "known_locations": len(agent.knowledge),
                "memories": len(agent.memories),
                "relationships": len(agent.relationships),
                "traits": agent.traits.model_dump(),
            }
        )

    return {
        "seed": seed,
        "crawl_id": crawl.id,
        "status": crawl.status.value,
        "current_floor": crawl.current_floor,
        "configured_floors": floors,
        "crawler_count": crawlers,
        "steps_executed": len(summaries),
        "simulation_tick": crawl.current_tick,
        "survivors": crawl.surviving_crawler_count,
        "eliminated": crawl.eliminated_crawler_count,
        "history_events": len(crawl.history_event_ids),
        "floor_themes": {str(number): floor.theme for number, floor in crawl.floors.items()},
        "floor_room_counts": {str(number): len(floor.locations) for number, floor in crawl.floors.items()},
        "goal_counts": goal_counts,
        "total_moves_current_floor": total_moves,
        "average_known_locations": round(total_knowledge / max(1, len(agents)), 2),
        "average_memories": round(total_memories / max(1, len(agents)), 2),
        "average_relationships": round(total_relationships / max(1, len(agents)), 2),
        "sample_crawlers": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Crawl v0.4 Slices 2-6 headless demo.")
    parser.add_argument("--seed", default="crawl-evening-demo")
    parser.add_argument("--crawlers", type=int, default=100)
    parser.add_argument("--floors", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=5000)
    parser.add_argument("--output", default="validation/crawl-v0.4-slices2-6-demo.json")
    args = parser.parse_args()

    if args.crawlers < 1 or args.floors < 1 or args.max_steps < 1:
        parser.error("crawlers, floors, and max-steps must all be positive")

    report = build_report(
        seed=args.seed,
        crawlers=args.crawlers,
        floors=args.floors,
        max_steps=args.max_steps,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    if report["status"] != "completed":
        print(f"ERROR: crawl did not complete within {args.max_steps} steps")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
