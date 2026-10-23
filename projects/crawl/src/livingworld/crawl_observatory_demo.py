from __future__ import annotations

import argparse
import json
from pathlib import Path

from .crawl_observatory import build_observatory_snapshot
from .crawl_observatory_html import render_observatory_html
from .crawl_persistence import CrawlPersistence
from .crawl_service import CrawlLifecycleService
from .tier_runtime_probe import run_with_live_tier_probe


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Crawl Observatory diagnostic snapshot")
    parser.add_argument("--seed", default="crawl-observatory-demo")
    parser.add_argument("--crawlers", type=int, default=50)
    parser.add_argument("--floors", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=10000)
    parser.add_argument("--output", default="validation/crawl-v0.5-observatory.json")
    parser.add_argument("--html-output", default="validation/crawl-v0.5-observatory.html")
    args = parser.parse_args()

    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    crawler_ids = [f"observatory_crawler_{index:05d}" for index in range(args.crawlers)]
    crawl = service.create_seeded_crawl(seed=args.seed, crawler_ids=crawler_ids, floor_count=args.floors)
    service.start(crawl)

    focused = sorted(crawl.participants)[: min(5, args.crawlers)]
    live_tiers = run_with_live_tier_probe(
        crawl,
        service,
        max_steps=args.max_steps,
        focused_ids=focused,
        rebalance_interval=4,
        intermission_ticks=2,
        director_interval=5,
    )
    tier_telemetry = live_tiers.as_dict()
    events = persistence.list_events(crawl.id, limit=1000)

    snapshot = build_observatory_snapshot(
        crawl,
        events,
        telemetry={
            "elapsed_seconds": tier_telemetry["elapsed_seconds"],
            "steps": tier_telemetry["steps"],
            "milliseconds_per_step": round(
                float(tier_telemetry["elapsed_seconds"]) * 1000 / max(1, int(tier_telemetry["steps"])),
                6,
            ),
            "events_loaded": len(events),
            "state_bytes": len(crawl.model_dump_json()),
            "live_tier_scheduler": tier_telemetry,
        },
        selected_crawler_id=focused[0] if focused else None,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    html_output = Path(args.html_output)
    html_output.parent.mkdir(parents=True, exist_ok=True)
    html_output.write_text(render_observatory_html(snapshot), encoding="utf-8")

    print(json.dumps({
        "status": crawl.status.value,
        "tick": crawl.current_tick,
        "survivors": crawl.surviving_crawler_count,
        "eliminated": crawl.eliminated_crawler_count,
        "detail_tiers": snapshot["population"]["detail_tiers"],
        "live_scheduler": tier_telemetry,
        "interesting_events": len(snapshot["interesting_events"]),
        "director_interventions": len(snapshot["director_interventions"]),
        "selected_crawler": snapshot["selected_crawler"]["npc_id"] if snapshot["selected_crawler"] else None,
    }, indent=2))
    print(f"JSON report: {output}")
    print(f"HTML dashboard: {html_output}")

    if int(tier_telemetry["scheduled_updates"]) <= 0 or not (0.0 < float(tier_telemetry["scheduled_ratio"]) < 1.0):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
