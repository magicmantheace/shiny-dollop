from livingworld.crawl_domain import CrawlEvent
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.presentation_animation import (
    ANIMATION_PROTOCOL,
    PresentationAnimationPlanner,
    validate_animation_plan,
)
from livingworld.presentation_staging import PresentationStagingResolver


def make_crawl(seed="animation-plan", crawlers=3):
    service = CrawlLifecycleService()
    crawl = service.create_seeded_crawl(
        seed=seed,
        crawler_ids=[f"npc_{index:03d}" for index in range(crawlers)],
        floor_count=2,
    )
    service.start(crawl)
    return crawl


def event(event_id, tick, event_type, actors):
    return CrawlEvent(
        id=event_id,
        crawl_id="crawl-test",
        floor_number=1,
        tick=tick,
        event_type=event_type,
        summary=event_type.replace("_", " ").title(),
        actor_ids=list(actors),
        location_id="arena",
        data={},
    )


def test_animation_plan_is_deterministic_and_non_authoritative():
    crawl = make_crawl()
    events = [
        event("e1", 10, "COMBAT_HIT", ["npc_000", "enemy_a"]),
        event("e2", 11, "CRAWLER_RETREATED", ["npc_000"]),
    ]
    crawl.history_event_ids.extend(["e1", "e2"])
    staging = PresentationStagingResolver(max_actors=3).resolve(
        crawl,
        events,
        focus_actor_ids=["npc_000"],
        presentation_seed="stable",
    )

    planner = PresentationAnimationPlanner()
    first = planner.plan(staging)
    second = planner.plan(staging)

    assert first.as_dict() == second.as_dict()
    assert first.protocol == ANIMATION_PROTOCOL
    assert first.authoritative is False
    assert first.source_staging_digest == staging.digest
    assert validate_animation_plan(first, staging)


def test_attack_hit_generates_attack_and_reaction_intents():
    crawl = make_crawl()
    events = [event("e1", 4, "COMBAT_HIT", ["npc_000", "enemy_a"])]
    crawl.history_event_ids.append("e1")
    staging = PresentationStagingResolver(max_actors=3).resolve(
        crawl,
        events,
        focus_actor_ids=["npc_000"],
    )

    plan = PresentationAnimationPlanner().plan(staging)
    by_role = {intent.role: intent for intent in plan.intents}

    assert by_role["attack"].actor_id == "npc_000"
    assert by_role["attack"].target_actor_id == "enemy_a"
    assert by_role["attack"].asset_slot == "humanoid.combat.attack.default"
    assert by_role["attack"].root_motion_policy == "motion_warp_to_target"
    assert by_role["hit_reaction"].actor_id == "enemy_a"
    assert by_role["hit_reaction"].asset_slot == "enemy.biped.reaction.hit.light"
    assert by_role["hit_reaction"].contact_policy == "react_at_contact"


def test_validation_attack_cycle_proves_all_profiled_silhouettes_deterministically():
    crawl = make_crawl("animation-variety-cycle", crawlers=3)
    events = [
        event(f"e{index}", 4 + index, "COMBAT_HIT", ["npc_000", "enemy_a"])
        for index in range(5)
    ]
    crawl.history_event_ids.extend(item.id for item in events)
    staging = PresentationStagingResolver(max_actors=3).resolve(
        crawl,
        events,
        focus_actor_ids=["npc_000"],
    )

    first = PresentationAnimationPlanner(validation_attack_cycle=True).plan(staging)
    second = PresentationAnimationPlanner(validation_attack_cycle=True).plan(staging)
    selected = [intent.asset_slot for intent in first.intents if intent.role == "attack"]

    assert first == second
    assert selected == [
        "humanoid.combat.attack.default",
        "humanoid.combat.attack.02",
        "humanoid.combat.attack.default",
        "humanoid.combat.attack.charged",
        "humanoid.combat.attack.03",
    ]


def test_rescue_generates_paired_interaction_without_creating_new_event():
    crawl = make_crawl(crawlers=2)
    events = [event("rescue-event", 20, "RESCUE", ["npc_000", "npc_001"])]
    crawl.history_event_ids.append("rescue-event")
    staging = PresentationStagingResolver(max_actors=2).resolve(
        crawl,
        events,
        focus_actor_ids=["npc_000", "npc_001"],
    )

    plan = PresentationAnimationPlanner().plan(staging)

    assert {intent.event_id for intent in plan.intents} == {"rescue-event"}
    assert {intent.role for intent in plan.intents} == {"rescue", "rescued_reaction"}
    assert all(intent.contact_policy == "paired_interaction" for intent in plan.intents)
    assert validate_animation_plan(plan, staging)


def test_navigation_actions_request_locomotion_instead_of_authoritative_motion():
    crawl = make_crawl()
    events = [
        event("move-event", 1, "CRAWLER_MOVED", ["npc_000"]),
        event("retreat-event", 2, "CRAWLER_RETREATED", ["npc_000"]),
    ]
    crawl.history_event_ids.extend(["move-event", "retreat-event"])
    staging = PresentationStagingResolver(max_actors=2).resolve(crawl, events, focus_actor_ids=["npc_000"])

    plan = PresentationAnimationPlanner().plan(staging)
    by_event = {intent.event_id: intent for intent in plan.intents}

    assert by_event["move-event"].layer == "locomotion"
    assert by_event["move-event"].locomotion_mode == "move_to_stage_target"
    assert by_event["move-event"].root_motion_policy == "navigation_driven"
    assert by_event["retreat-event"].locomotion_mode == "run_away"
    assert by_event["retreat-event"].authoritative is False


def test_animation_plan_references_only_staged_actors_and_events():
    crawl = make_crawl(crawlers=12)
    crowd = [f"npc_{index:03d}" for index in range(12)]
    events = [
        event("start", 1, "COMBAT_STARTED", crowd),
        event("hit", 2, "COMBAT_HIT", ["npc_000", "enemy_a"]),
    ]
    crawl.history_event_ids.extend(["start", "hit"])
    staging = PresentationStagingResolver(max_actors=3).resolve(crawl, events, focus_actor_ids=["npc_000"])

    plan = PresentationAnimationPlanner().plan(staging)
    staged = {actor.actor_id for actor in staging.actors}

    assert all(intent.actor_id in staged for intent in plan.intents)
    assert all(intent.target_actor_id is None or intent.target_actor_id in staged for intent in plan.intents)
    assert all(intent.event_id in set(staging.source_event_ids) for intent in plan.intents)
    assert validate_animation_plan(plan, staging)
