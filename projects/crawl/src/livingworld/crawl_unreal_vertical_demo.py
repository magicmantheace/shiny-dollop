from __future__ import annotations

import argparse
import json
from pathlib import Path

from .camera_director import AutomatedCameraDirector
from .crawl_domain import Crawl, CrawlEvent
from .crawl_persistence import CrawlPersistence
from .crawl_service import CrawlLifecycleService
from .headless_mvp_simulation import HeadlessCrawlMVP
from .presentation_animation import PresentationAnimationPlanner, validate_animation_plan
from .presentation_staging import PresentationStagingResolver, validate_staging_manifest


TERMINAL_EVENT_TYPES = {"ENEMY_DEFEATED", "CRAWLER_DIED", "CRAWLER_ELIMINATED"}


def _event_data(event: CrawlEvent) -> dict:
    return event.data if isinstance(event.data, dict) else {}


def _canonical_order(crawl: Crawl, events: list[CrawlEvent]) -> list[CrawlEvent]:
    order = {event_id: index for index, event_id in enumerate(crawl.history_event_ids)}
    return sorted(events, key=lambda event: (event.tick, order.get(event.id, len(order) + 1), event.id))


def _encounter_events(crawl: Crawl, events: list[CrawlEvent], encounter_id: str) -> list[CrawlEvent]:
    selected = [event for event in events if str(_event_data(event).get("encounter_id", "")) == encounter_id]
    return _canonical_order(crawl, selected)


def _select_real_combat(
    crawl: Crawl,
    events: list[CrawlEvent],
    *,
    require_terminal: bool = False,
) -> tuple[str, list[CrawlEvent], str]:
    starts = [event for event in events if event.event_type.upper() == "COMBAT_STARTED"]
    if not starts:
        raise RuntimeError("autonomous crawl produced no COMBAT_STARTED event")

    candidates: list[tuple[int, int, int, str, list[CrawlEvent], CrawlEvent]] = []
    for start in starts:
        encounter_id = str(_event_data(start).get("encounter_id", ""))
        if not encounter_id:
            continue
        related = _encounter_events(crawl, events, encounter_id)
        terminal_count = sum(event.event_type.upper() in TERMINAL_EVENT_TYPES for event in related)
        if require_terminal and terminal_count == 0:
            continue
        action_count = sum(
            event.event_type.upper() in {
                "COMBAT_HIT",
                "CRAWLER_DAMAGED",
                "CRAWLER_INJURED",
                "ENEMY_DEFEATED",
                "CRAWLER_RETREATED",
                "CRAWLER_DIED",
                "CRAWLER_ELIMINATED",
            }
            for event in related
        )
        if action_count == 0:
            continue
        # Prefer a visually manageable encounter. For death QA, then prefer an
        # encounter with more terminal evidence before considering action count.
        candidates.append(
            (
                len(start.actor_ids),
                -terminal_count if require_terminal else 0,
                -action_count,
                encounter_id,
                related,
                start,
            )
        )

    if not candidates:
        if require_terminal:
            raise RuntimeError(
                "autonomous crawl produced no renderable combat encounter containing a canonical death/defeat event"
            )
        raise RuntimeError("autonomous crawl produced combat starts but no renderable combat actions")

    _, _, _, encounter_id, related, start = min(candidates, key=lambda item: (item[0], item[1], item[2], item[3]))
    crawler_ids = [str(actor_id) for actor_id in start.actor_ids if str(actor_id) in crawl.participants]
    if not crawler_ids:
        raise RuntimeError("selected encounter contains no crawler participant")
    return encounter_id, related, crawler_ids[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a real Crawl combat encounter as Unreal presentation manifests")
    parser.add_argument("--seed", default="crawl-v09-unreal-vertical")
    parser.add_argument("--crawlers", type=int, default=12)
    parser.add_argument("--floors", type=int, default=2)
    parser.add_argument("--max-steps", type=int, default=5000)
    parser.add_argument("--max-actors", type=int, default=8)
    parser.add_argument("--output", default="validation/crawl-v0.9-unreal-vertical-slice.json")
    parser.add_argument("--manifest", default="unreal/CrawlPresentation/Generated/stage_manifest.json")
    parser.add_argument("--animation-plan", default="unreal/CrawlPresentation/Generated/animation_plan.json")
    parser.add_argument(
        "--validation-attack-cycle",
        action="store_true",
        help="Cycle validated attack profiles for presentation QA only.",
    )
    parser.add_argument(
        "--require-terminal",
        action="store_true",
        help="Select only a canonical combat encounter containing death/defeat for corpse-persistence QA.",
    )
    parser.add_argument(
        "--post-roll-seconds",
        type=float,
        default=2.0,
        help="Presentation-only tail after the final canonical event; useful for terminal-pose validation.",
    )
    args = parser.parse_args()

    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    crawler_ids = [f"unreal_crawler_{index:03d}" for index in range(args.crawlers)]
    crawl = service.create_seeded_crawl(seed=args.seed, crawler_ids=crawler_ids, floor_count=args.floors)
    service.start(crawl)
    steps = HeadlessCrawlMVP(service, intermission_ticks=2, director_interval=5).run(crawl, max_steps=args.max_steps)

    events = persistence.list_events(crawl.id, limit=10000)
    authoritative_ids = set(crawl.history_event_ids)
    encounter_id, encounter_events, focus_actor_id = _select_real_combat(
        crawl,
        events,
        require_terminal=args.require_terminal,
    )

    before = crawl.fingerprint()
    camera = AutomatedCameraDirector(minimum_score=0.0).plan(
        crawl,
        encounter_events,
        start_tick=min(event.tick for event in encounter_events),
        end_tick=max(event.tick for event in encounter_events),
        focus_actor_id=focus_actor_id,
        max_shots=12,
    )
    resolver = PresentationStagingResolver(
        max_actors=args.max_actors,
        post_roll_seconds=max(0.0, args.post_roll_seconds),
    )
    manifest = resolver.resolve(
        crawl,
        encounter_events,
        focus_actor_ids=[focus_actor_id],
        camera_plan=camera,
        presentation_seed=f"{args.seed}:{encounter_id}",
    )
    animation_plan = PresentationAnimationPlanner(
        validation_attack_cycle=args.validation_attack_cycle,
    ).plan(manifest)
    after = crawl.fingerprint()

    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest.as_dict(), indent=2), encoding="utf-8")

    animation_plan_path = Path(args.animation_plan)
    animation_plan_path.parent.mkdir(parents=True, exist_ok=True)
    animation_plan_path.write_text(json.dumps(animation_plan.as_dict(), indent=2), encoding="utf-8")

    source_order = {event_id: index for index, event_id in enumerate(crawl.history_event_ids)}
    source_indexes = [source_order[event_id] for event_id in manifest.source_event_ids]
    staged_actor_ids = {actor.actor_id for actor in manifest.actors}
    actions = {beat.action for beat in manifest.beats}
    terminal_beats = [beat for beat in manifest.beats if beat.action in {"death", "defeat"}]

    checks = {
        "crawl_completed": crawl.status.value == "completed",
        "real_combat_selected": bool(encounter_id) and bool(encounter_events),
        "contains_real_combat_action": "attack_hit" in actions or "defeat" in actions or "death" in actions,
        "terminal_event_present_when_required": (not args.require_terminal) or bool(terminal_beats),
        "manifest_valid": validate_staging_manifest(manifest, authoritative_ids),
        "animation_plan_valid": validate_animation_plan(animation_plan, manifest),
        "animation_plan_grounded": animation_plan.source_event_ids == manifest.source_event_ids,
        "source_events_canonical": set(manifest.source_event_ids).issubset(authoritative_ids),
        "event_order_preserved": source_indexes == sorted(source_indexes),
        "presentation_non_authoritative": manifest.authoritative is False and animation_plan.authoritative is False,
        "staging_read_only": before == after,
        "bounded_actor_count": 1 <= len(staged_actor_ids) <= args.max_actors,
        "focus_actor_staged": focus_actor_id in staged_actor_ids,
        "camera_cues_present": bool(manifest.camera_cues),
        "animation_intents_present": bool(animation_plan.intents),
        "positive_presentation_duration": manifest.duration_seconds > 0,
    }

    report = {
        "seed": args.seed,
        "validation_attack_cycle": args.validation_attack_cycle,
        "require_terminal": args.require_terminal,
        "post_roll_seconds": max(0.0, args.post_roll_seconds),
        "crawl_id": crawl.id,
        "status": crawl.status.value,
        "steps": len(steps),
        "tick": crawl.current_tick,
        "crawlers": crawl.starting_crawler_count,
        "floors": len(crawl.floors),
        "history_events": len(crawl.history_event_ids),
        "selected_encounter_id": encounter_id,
        "focus_actor_id": focus_actor_id,
        "canonical_encounter_events": len(encounter_events),
        "terminal_event_count": len(terminal_beats),
        "terminal_actions": [beat.action for beat in terminal_beats],
        "staging": {
            "protocol": manifest.protocol,
            "digest": manifest.digest,
            "source_event_count": len(manifest.source_event_ids),
            "actor_count": len(manifest.actors),
            "beat_count": len(manifest.beats),
            "camera_cue_count": len(manifest.camera_cues),
            "duration_seconds": round(manifest.duration_seconds, 3),
            "actions": sorted(actions),
            "actor_ids": [actor.actor_id for actor in manifest.actors],
        },
        "animation": {
            "protocol": animation_plan.protocol,
            "digest": animation_plan.digest,
            "rig_count": len(animation_plan.rigs),
            "intent_count": len(animation_plan.intents),
            "asset_slots": sorted({intent.asset_slot for intent in animation_plan.intents}),
        },
        "manifest_path": str(manifest_path),
        "animation_plan_path": str(animation_plan_path),
        "checks": checks,
        "overall": all(checks.values()),
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Staging manifest: {manifest_path}")
    print(f"Animation plan: {animation_plan_path}")
    print(f"Report: {output}")
    if not report["overall"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
