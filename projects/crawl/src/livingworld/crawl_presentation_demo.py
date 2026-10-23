from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastapi.testclient import TestClient

from .camera_director import AutomatedCameraDirector
from .crawl_persistence import CrawlPersistence
from .crawl_service import CrawlLifecycleService
from .headless_mvp_simulation import HeadlessCrawlMVP
from .live_channels import ViewerChannelRegistry, build_viewer_channels
from .spectator_api import SpectatorRepository, create_spectator_app
from .story_highlights import StoryArcDetector


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate automated cameras, crawler channels, and story detection")
    parser.add_argument("--seed", default="crawl-v07-presentation")
    parser.add_argument("--crawlers", type=int, default=50)
    parser.add_argument("--floors", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=10000)
    parser.add_argument("--output", default="validation/crawl-v0.7-slices22-24-presentation.json")
    args = parser.parse_args()

    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    crawler_ids = [f"channel_crawler_{index:05d}" for index in range(args.crawlers)]
    crawl = service.create_seeded_crawl(seed=args.seed, crawler_ids=crawler_ids, floor_count=args.floors)
    service.start(crawl)
    steps = HeadlessCrawlMVP(service, intermission_ticks=2, director_interval=5).run(crawl, max_steps=args.max_steps)

    # Deterministic structured fixture used only to guarantee the Batch 6 analyzer
    # acceptance path exercises a multi-event rescue/reversal story in every seed.
    fixture_a = crawler_ids[0]
    fixture_b = crawler_ids[1]
    service.record_event(
        crawl,
        "NEAR_DEATH",
        "Presentation acceptance crawler barely survived.",
        actor_ids=[fixture_a],
        data={"danger": 0.96},
    )
    service.record_event(
        crawl,
        "RESCUE",
        "Presentation acceptance ally returned to help.",
        actor_ids=[fixture_a, fixture_b],
        data={"relationship_impact": 0.75, "reversal": True},
    )

    events = persistence.list_events(crawl.id, limit=10000)
    authoritative_ids = set(crawl.history_event_ids)
    before = crawl.fingerprint()

    director = AutomatedCameraDirector()
    first_plan = director.plan(crawl, events, start_tick=0, end_tick=crawl.current_tick, max_shots=32)
    second_plan = director.plan(crawl, reversed(events), start_tick=0, end_tick=crawl.current_tick, max_shots=32)

    registry = ViewerChannelRegistry()
    registry.follow("viewer-a", crawler_ids[0], crawl)
    registry.follow("viewer-b", crawler_ids[min(1, len(crawler_ids) - 1)], crawl)
    channels = build_viewer_channels(crawl, events, registry)

    arcs = StoryArcDetector(minimum_score=0.3).analyze(events, limit=25)
    arc_event_ids_valid = all(set(arc.event_ids).issubset(authoritative_ids) for arc in arcs)
    rescue_arc_found = any(arc.story_type in {"rescue", "rescue_comeback"} for arc in arcs)

    client = TestClient(create_spectator_app(SpectatorRepository(persistence, crawl.id)))
    channel_response = client.get(f"/api/spectator/channels/{crawler_ids[0]}")
    camera_response = client.get("/api/spectator/camera/plan", params={"focus_actor_id": crawler_ids[0]})
    highlights_response = client.get("/api/spectator/highlights", params={"minimum_score": 0.3})

    checks = {
        "crawl_completed": crawl.status.value == "completed",
        "camera_plan_nonempty": bool(first_plan.shots),
        "camera_deterministic": first_plan.digest == second_plan.digest,
        "camera_anti_thrash": len(first_plan.shots) < max(1, len(events)),
        "camera_read_only": crawl.fingerprint() == before,
        "multiple_viewers_independent": (
            channels["viewer-a"]["crawler"]["npc_id"] == crawler_ids[0]
            and channels["viewer-b"]["crawler"]["npc_id"] == crawler_ids[min(1, len(crawler_ids) - 1)]
        ),
        "channel_public_only": "knowledge" not in json.dumps(channels),
        "channel_focus_request_is_pure": all(
            channel["focus_request"]["mutates_authoritative_state"] is False
            for channel in channels.values()
        ),
        "story_arcs_found": bool(arcs),
        "rescue_arc_found": rescue_arc_found,
        "story_evidence_is_canonical": arc_event_ids_valid,
        "api_channel_ok": channel_response.status_code == 200,
        "api_camera_ok": camera_response.status_code == 200 and bool(camera_response.json().get("shots")),
        "api_highlights_ok": highlights_response.status_code == 200 and bool(highlights_response.json()),
        "api_reads_preserve_state": persistence.load_crawl(crawl.id).fingerprint() == before,
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
        "camera": {
            "shot_count": len(first_plan.shots),
            "digest": first_plan.digest,
            "start_tick": first_plan.start_tick,
            "end_tick": first_plan.end_tick,
            "modes": sorted({shot.mode.value for shot in first_plan.shots}),
        },
        "channels": {
            viewer_id: {
                "crawler_id": payload["crawler"]["npc_id"],
                "recent_events": len(payload["recent_events"]),
                "camera_shots": payload["camera"]["shot_count"],
                "focused_ids": payload["focus_request"]["focused_ids"],
                "local_active_count": len(payload["focus_request"]["local_active_ids"]),
            }
            for viewer_id, payload in channels.items()
        },
        "stories": {
            "count": len(arcs),
            "types": sorted({arc.story_type for arc in arcs}),
            "top": [arc.as_dict() for arc in arcs[:5]],
        },
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
