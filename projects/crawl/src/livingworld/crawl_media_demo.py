from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ai_dramatization import DramatizationPlanner, validate_dramatization_job
from .commentary_system import CommentaryMode, validate_commentary_grounding
from .crawl_persistence import CrawlPersistence
from .crawl_service import CrawlLifecycleService
from .headless_mvp_simulation import HeadlessCrawlMVP
from .highlight_reels import HighlightReelAssembler, validate_highlight_package
from .story_highlights import StoryArcDetector


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate grounded commentary, highlight packages, and AI dramatization specs")
    parser.add_argument("--seed", default="crawl-v08-media")
    parser.add_argument("--crawlers", type=int, default=50)
    parser.add_argument("--floors", type=int, default=3)
    parser.add_argument("--max-steps", type=int, default=10000)
    parser.add_argument("--output", default="validation/crawl-v0.8-slices25-27-media.json")
    args = parser.parse_args()

    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    crawler_ids = [f"media_crawler_{index:05d}" for index in range(args.crawlers)]
    crawl = service.create_seeded_crawl(seed=args.seed, crawler_ids=crawler_ids, floor_count=args.floors)
    service.start(crawl)
    steps = HeadlessCrawlMVP(service, intermission_ticks=2, director_interval=5).run(crawl, max_steps=args.max_steps)

    # Acceptance fixture: canonical events inserted through the same lifecycle/event
    # path, solely to guarantee every validation seed exercises a rescue story.
    fixture_a = crawler_ids[0]
    fixture_b = crawler_ids[min(1, len(crawler_ids) - 1)]
    service.record_event(
        crawl,
        "NEAR_DEATH",
        "Media acceptance crawler reached a near-death moment.",
        actor_ids=[fixture_a],
        data={"danger": 0.97},
    )
    service.record_event(
        crawl,
        "RESCUE",
        "Media acceptance ally returned to help.",
        actor_ids=[fixture_a, fixture_b],
        data={"relationship_impact": 0.8, "reversal": True},
    )

    events = persistence.list_events(crawl.id, limit=10000)
    authoritative_ids = set(crawl.history_event_ids)
    stories = StoryArcDetector(minimum_score=0.3).analyze(events, limit=50)
    rescue = next((arc for arc in stories if arc.story_type in {"rescue_comeback", "rescue"}), None)
    if rescue is None:
        raise SystemExit("No rescue story found for media acceptance run")

    before = crawl.fingerprint()
    assembler = HighlightReelAssembler()
    package = assembler.assemble(
        crawl,
        events,
        rescue,
        commentary_mode=CommentaryMode.DOCUMENTARY,
    )
    repeated = assembler.assemble(
        crawl,
        reversed(events),
        rescue,
        commentary_mode=CommentaryMode.DOCUMENTARY,
    )
    drama = DramatizationPlanner().build_job(
        package,
        events,
        provider="unassigned",
        model=None,
    )

    checks = {
        "crawl_completed": crawl.status.value == "completed",
        "rescue_story_found": rescue is not None,
        "commentary_nonempty": bool(package.commentary.lines),
        "commentary_grounded": validate_commentary_grounding(package.commentary, authoritative_ids),
        "commentary_deterministic": package.commentary.digest == repeated.commentary.digest,
        "highlight_package_valid": validate_highlight_package(package, authoritative_ids),
        "highlight_package_deterministic": package.package_digest == repeated.package_digest,
        "replay_window_contains_story": (
            package.replay_window.start_tick <= rescue.start_tick
            and package.replay_window.end_tick >= rescue.end_tick
        ),
        "camera_plan_present": bool(package.camera_plan.shots),
        "edit_timeline_present": bool(package.timeline),
        "multi_format_outputs_present": {output.value for output in package.outputs} == {"short_vertical", "standard_horizontal"},
        "dramatization_traceable": validate_dramatization_job(drama, authoritative_ids),
        "dramatization_noncanonical": drama.canonical is False and all(scene.canonical is False for scene in drama.scenes),
        "presentation_read_only": crawl.fingerprint() == before,
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
        "story": rescue.as_dict(),
        "commentary": package.commentary.as_dict(),
        "highlight": package.as_dict(),
        "dramatization": drama.as_dict(),
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
