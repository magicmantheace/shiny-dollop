from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastapi.testclient import TestClient

from .crawl_persistence import CrawlPersistence
from .crawl_service import CrawlLifecycleService
from .headless_mvp_simulation import HeadlessCrawlMVP
from .spectator_api import SpectatorRepository, create_spectator_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Crawl spectator API, Unreal bridge, and replay archive")
    parser.add_argument("--seed", default="crawl-v06-spectator")
    parser.add_argument("--crawlers", type=int, default=50)
    parser.add_argument("--floors", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=10000)
    parser.add_argument("--output", default="validation/crawl-v0.6-slices19-21-spectator.json")
    args = parser.parse_args()

    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    crawler_ids = [f"spectator_crawler_{index:05d}" for index in range(args.crawlers)]
    crawl = service.create_seeded_crawl(seed=args.seed, crawler_ids=crawler_ids, floor_count=args.floors)
    service.start(crawl)
    steps = HeadlessCrawlMVP(service, intermission_ticks=2, director_interval=5).run(crawl, max_steps=args.max_steps)

    repository = SpectatorRepository(persistence, crawl.id)
    client = TestClient(create_spectator_app(repository))
    directory = client.get("/api/spectator/crawlers", params={"limit": 10})
    sample_id = directory.json()[0]["npc_id"]
    profile = client.get(f"/api/spectator/crawlers/{sample_id}")
    history = client.get(f"/api/spectator/crawlers/{sample_id}/history")
    replay = client.get("/api/spectator/replay")
    replay_window = client.get("/api/spectator/replay/events", params={"limit": 5000})
    bootstrap = client.get("/api/spectator/unreal/bootstrap")
    frame = client.get("/api/spectator/unreal/frame")
    crawl_payload = client.get("/api/spectator/crawl").json()

    checks = {
        "crawl_completed": crawl.status.value == "completed",
        "directory_ok": directory.status_code == 200 and bool(directory.json()),
        "profile_ok": profile.status_code == 200 and profile.json().get("npc_id") == sample_id,
        "history_ok": history.status_code == 200 and isinstance(history.json(), list),
        "public_state_hides_modifiers": "modifiers" not in crawl_payload,
        "public_profile_hides_knowledge": "knowledge" not in profile.json(),
        "replay_manifest_ok": replay.status_code == 200,
        "replay_complete": replay.json().get("event_count") == len(crawl.history_event_ids),
        "replay_window_ok": replay_window.status_code == 200 and bool(replay_window.json().get("events")),
        "unreal_bootstrap_ok": bootstrap.status_code == 200 and bootstrap.json().get("authority") == "backend",
        "unreal_frame_ok": frame.status_code == 200 and frame.json().get("crawl_id") == crawl.id,
    }
    report = {
        "seed": args.seed,
        "crawl_id": crawl.id,
        "status": crawl.status.value,
        "steps": len(steps),
        "tick": crawl.current_tick,
        "crawlers": crawl.starting_crawler_count,
        "floors": len(crawl.floors),
        "history_events": len(crawl.history_event_ids),
        "sample_crawler": sample_id,
        "replay": replay.json(),
        "unreal_protocol": bootstrap.json().get("protocol"),
        "checks": checks,
        "overall": all(checks.values()),
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Report: {output}")
    if not report["overall"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
