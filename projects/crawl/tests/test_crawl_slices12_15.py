from livingworld.crawl_director import CrawlDirector, remaining_budget
from livingworld.crawl_domain import Crawl, CrawlStatus, FloorStatus, ParticipationStatus
from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.floor_lifecycle import FloorLifecycleService, floor_phase
from livingworld.headless_mvp_simulation import HeadlessCrawlMVP
from livingworld.semantic_event_ledger import semantic_score


def make_crawl(seed="batch3", crawlers=6, floors=2, persistence=None):
    service = CrawlLifecycleService(persistence)
    crawl = service.create_seeded_crawl(
        seed=seed,
        crawler_ids=[f"npc_{index:03d}" for index in range(crawlers)],
        floor_count=floors,
    )
    service.start(crawl)
    return service, crawl


def test_semantic_ledger_scores_events_and_links_actor_causality():
    service, crawl = make_crawl(seed="semantic-causality", crawlers=2, floors=1)
    first = service.record_event(
        crawl,
        "CRAWLER_MOVED",
        "Crawler moved into danger.",
        actor_ids=["npc_000"],
        location_id=crawl.participants["npc_000"].current_location_id,
    )
    rescue = service.record_event(
        crawl,
        "RESCUE",
        "Crawler 000 returned to help Crawler 001.",
        actor_ids=["npc_000", "npc_001"],
        data={"relationship_impact": 0.7, "reversal": True},
    )

    semantic = rescue.data["semantic"]
    assert semantic_score(rescue) >= 0.68
    assert first.id in semantic["causal_parent_ids"]
    assert semantic["relationship_impact"] > 0
    assert semantic["reversal"] is True
    assert "rescue" in semantic["audience_interest_tags"]


def test_deadline_eliminates_late_crawlers_and_stages_intermission():
    service, crawl = make_crawl(seed="deadline", crawlers=3, floors=2)
    floor = crawl.floors[1]
    exit_id = floor.exit_location_ids[0]
    crawl.participants["npc_000"].current_location_id = exit_id
    crawl.participants["npc_001"].current_location_id = exit_id
    crawl.participants["npc_002"].current_location_id = floor.entrance_location_id
    floor.deadline_tick = crawl.current_tick

    cycle = FloorLifecycleService(service, intermission_ticks=2)
    result = cycle.evaluate(crawl)

    assert result is not None
    assert result["phase"] == "intermission"
    assert crawl.participants["npc_002"].status == ParticipationStatus.ELIMINATED
    assert crawl.current_floor == 2
    assert crawl.floors[1].status == FloorStatus.COMPLETED
    assert crawl.floors[2].status == FloorStatus.PENDING
    assert floor_phase(crawl) == "intermission"
    assert crawl.surviving_crawler_count == 2

    cycle.evaluate(crawl)
    cycle.evaluate(crawl)
    cycle.evaluate(crawl)
    assert floor_phase(crawl) == "active"
    assert crawl.floors[2].status == FloorStatus.ACTIVE
    assert crawl.floors[2].deadline_tick is not None


def test_director_is_budgeted_and_resource_opportunity_preserves_item_authority():
    service, crawl = make_crawl(seed="director-resource", crawlers=5, floors=1)
    for participant in crawl.participants.values():
        participant.health = 0.20
    before_health = {npc_id: participant.health for npc_id, participant in crawl.participants.items()}
    before_budget = remaining_budget(crawl)

    result = CrawlDirector(service, minimum_interval=1).evaluate(crawl)

    assert result is not None
    assert result["action"] == "spawn_resource_opportunity"
    assert remaining_budget(crawl) < before_budget
    assert {npc_id: participant.health for npc_id, participant in crawl.participants.items()} == before_health
    encounter = crawl.encounters[result["encounter_id"]]
    assert encounter.reward_item_ids
    for item_id in encounter.reward_item_ids:
        item = crawl.items[item_id]
        assert item.encounter_id == encounter.id
        assert item.owner_npc_id is None
        assert item.location_id is None
    Crawl.model_validate(crawl.model_dump(mode="python"))


def test_batch3_control_state_survives_save_reload(tmp_path):
    persistence = CrawlPersistence(f"sqlite:///{tmp_path / 'batch3.db'}")
    persistence.initialize()
    service, crawl = make_crawl(seed="batch3-persistence", crawlers=4, floors=2, persistence=persistence)
    director = CrawlDirector(service, minimum_interval=1)
    director.evaluate(crawl)
    service.record_event(crawl, "NEAR_DEATH", "A crawler narrowly survived.", actor_ids=["npc_000"], data={"danger": 0.9})
    service.save(crawl)

    restored = persistence.load_crawl(crawl.id)
    assert restored is not None
    assert restored.modifiers["_crawl_director"] == crawl.modifiers["_crawl_director"]
    assert restored.modifiers["_semantic_ledger"] == crawl.modifiers["_semantic_ledger"]
    assert restored.fingerprint() == crawl.fingerprint()


def test_headless_mvp_composes_gameplay_deadlines_director_and_ledger():
    service, crawl = make_crawl(seed="batch3-integrated", crawlers=24, floors=3)
    for floor in crawl.floors.values():
        floor.completion_rules["floor_duration_ticks"] = 500
    # Recompute the already-active first-floor deadline after shortening the rule.
    crawl.floors[1].deadline_tick = crawl.current_tick + 500

    mvp = HeadlessCrawlMVP(service, intermission_ticks=2, director_interval=4)
    mvp.prepare(crawl)
    steps = mvp.run(crawl, max_steps=5000)

    assert steps
    assert crawl.status == CrawlStatus.COMPLETED
    assert crawl.surviving_crawler_count + crawl.eliminated_crawler_count == crawl.starting_crawler_count
    assert crawl.history_event_ids
    assert crawl.modifiers["_crawl_director"]["interventions"]
    assert crawl.modifiers["_semantic_ledger"]["notable_event_ids"]
    Crawl.model_validate(crawl.model_dump(mode="python"))
