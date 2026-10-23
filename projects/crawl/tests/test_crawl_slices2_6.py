from livingworld.crawl_domain import CrawlStatus
from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.crawl_simulation import AutonomousCrawlSimulator
from livingworld.crawler_decision import CrawlerDecision, choose_action
from livingworld.crawler_domain import build_crawler_agent
from livingworld.crawler_navigation import choose_destination, perceive
from livingworld.crawler_social import apply_social_event, willingness_to_help
from livingworld.floor_generation import generate_floor


def test_crawler_profiles_are_deterministic_and_distinct():
    first = build_crawler_agent("profile-seed", "npc_a")
    repeat = build_crawler_agent("profile-seed", "npc_a")
    other = build_crawler_agent("profile-seed", "npc_b")
    assert first.model_dump() == repeat.model_dump()
    assert first.model_dump() != other.model_dump()
    assert 0 <= first.traits.courage <= 1
    assert 0 <= first.skills.navigation <= 1


def test_traits_and_needs_change_action_selection():
    cautious = build_crawler_agent("decision-seed", "cautious")
    cautious.traits.caution = 0.95
    cautious.traits.curiosity = 0.05
    cautious.traits.risk_tolerance = 0.05
    cautious.needs.perceived_danger = 0.8
    cautious.needs.stamina = 0.3
    cautious.needs.stress = 0.6
    cautious_choice = choose_action(cautious, health=0.4, seed="decision")
    assert cautious_choice.action in {"seek_safety", "recover", "seek_exit"}

    explorer = build_crawler_agent("decision-seed", "explorer")
    explorer.traits.caution = 0.05
    explorer.traits.curiosity = 0.95
    explorer.traits.risk_tolerance = 0.95
    explorer.preferences.unknown_rooms = 0.95
    explorer.needs.perceived_danger = 0.05
    explorer.needs.stamina = 1.0
    explorer.needs.stress = 0.0
    explorer_choice = choose_action(explorer, health=1.0, seed="decision")
    assert explorer_choice.action == "explore"


def test_perception_does_not_reveal_the_whole_floor():
    service = CrawlLifecycleService()
    crawl = service.create_seeded_crawl(seed="knowledge", crawler_ids=["npc_a"], floor_count=1)
    service.start(crawl)
    participant = crawl.participants["npc_a"]
    floor = crawl.floors[1]
    discovered = perceive(participant, floor, crawl.current_tick)
    assert discovered
    assert participant.agent is not None
    assert participant.current_location_id in participant.agent.knowledge
    assert len(participant.agent.knowledge) < len(floor.locations)


def test_social_events_change_future_help_willingness():
    agent = build_crawler_agent("social", "npc_a")
    before = willingness_to_help(agent, "npc_b")
    apply_social_event(agent, target_id="npc_b", event_type="rescue", magnitude=0.8)
    after_rescue = willingness_to_help(agent, "npc_b")
    assert after_rescue > before
    apply_social_event(agent, target_id="npc_b", event_type="betrayed", magnitude=1.0)
    after_betrayal = willingness_to_help(agent, "npc_b")
    assert after_betrayal < after_rescue


def test_procedural_floor_is_deterministic_connected_and_deeper_than_slice1():
    first = generate_floor("floor-v2", 4)
    second = generate_floor("floor-v2", 4)
    assert first.model_dump() == second.model_dump()
    assert len(first.locations) >= 12
    assert len(first.safe_area_ids) >= 1
    assert first.entrance_location_id != first.exit_location_ids[0]
    assert any("hidden_path:" in tag for loc in first.locations.values() for tag in loc.environmental_tags)


def test_agent_state_survives_save_reload(tmp_path):
    persistence = CrawlPersistence(f"sqlite:///{tmp_path / 'agents.db'}")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    crawl = service.create_seeded_crawl(seed="persist-agents", crawler_ids=["npc_a", "npc_b"], floor_count=2)
    service.start(crawl)
    simulator = AutonomousCrawlSimulator(service)
    for _ in range(4):
        simulator.step(crawl)
    before = crawl.participants["npc_a"].agent
    loaded = persistence.load_crawl(crawl.id)
    assert loaded is not None
    assert loaded.participants["npc_a"].agent is not None
    assert loaded.participants["npc_a"].agent.model_dump() == before.model_dump()


def test_seek_safety_stays_put_when_crawler_is_already_safe():
    service = CrawlLifecycleService()
    crawl = service.create_seeded_crawl(seed="safe-recovery", crawler_ids=["npc_a"], floor_count=1)
    service.start(crawl)
    participant = crawl.participants["npc_a"]
    floor = crawl.floors[1]
    participant.current_location_id = floor.safe_area_ids[0]
    perceive(participant, floor, crawl.current_tick)
    decision = CrawlerDecision(action="seek_safety", score=1.0, reasons={})
    assert choose_destination(participant, floor, decision) == participant.current_location_id


def test_evening_demo_seed_completes_25_crawlers_two_floors():
    service = CrawlLifecycleService()
    crawl = service.create_seeded_crawl(
        seed="crawl-evening-demo",
        crawler_ids=[f"demo_crawler_{index:04d}" for index in range(25)],
        floor_count=2,
    )
    service.start(crawl)
    simulator = AutonomousCrawlSimulator(service)
    summaries = simulator.run(crawl, max_steps=5_000)
    assert summaries
    assert crawl.status == CrawlStatus.COMPLETED


def test_headless_agents_can_complete_a_multifloor_crawl():
    service = CrawlLifecycleService()
    crawl = service.create_seeded_crawl(
        seed="autonomous-multifloor",
        crawler_ids=[f"npc_{index:02d}" for index in range(8)],
        floor_count=3,
    )
    service.start(crawl)
    simulator = AutonomousCrawlSimulator(service)
    summaries = simulator.run(crawl, max_steps=2_000)
    assert summaries
    assert crawl.status == CrawlStatus.COMPLETED
    assert all(participant.agent is not None for participant in crawl.participants.values())
    assert all(participant.floor_statistics.get("moves", 0) > 0 for participant in crawl.participants.values())
    assert any(participant.agent.memories for participant in crawl.participants.values())
    assert any(participant.agent.relationships for participant in crawl.participants.values())
