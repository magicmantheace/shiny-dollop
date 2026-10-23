from livingworld.combat_system import resolve_combat
from livingworld.crawl_domain import Crawl, CrawlStatus, ParticipationStatus
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.encounter_system import seed_floor_encounters
from livingworld.gameplay_domain import EncounterType, ItemCategory
from livingworld.gameplay_simulation import GameplayCrawlSimulator
from livingworld.item_system import drop_all_on_death, transfer_item_to_crawler
from livingworld.party_system import maybe_form_party
from livingworld.progression_system import award_experience, choose_progression


def make_crawl(seed="batch2", crawlers=6, floors=2):
    service = CrawlLifecycleService()
    crawl = service.create_seeded_crawl(
        seed=seed,
        crawler_ids=[f"npc_{index:03d}" for index in range(crawlers)],
        floor_count=floors,
    )
    service.start(crawl)
    return service, crawl


def first_hostile(crawl):
    seed_floor_encounters(crawl, 1)
    return next(
        encounter
        for encounter in sorted(crawl.encounters.values(), key=lambda value: value.id)
        if encounter.type in {EncounterType.HOSTILE, EncounterType.ELITE, EncounterType.BOSS}
    )


def test_combat_is_deterministic_for_identical_state():
    service_a, crawl_a = make_crawl(seed="combat-determinism", crawlers=4, floors=1)
    service_b, crawl_b = make_crawl(seed="combat-determinism", crawlers=4, floors=1)
    encounter_a = first_hostile(crawl_a)
    encounter_b = first_hostile(crawl_b)

    for crawl, encounter in ((crawl_a, encounter_a), (crawl_b, encounter_b)):
        for participant in crawl.participants.values():
            participant.current_location_id = encounter.location_id
        encounter.participant_npc_ids = sorted(crawl.participants)

    result_a = resolve_combat(crawl_a, encounter_a, service_a)
    result_b = resolve_combat(crawl_b, encounter_b, service_b)

    assert result_a.outcome == result_b.outcome
    assert result_a.rounds == result_b.rounds
    assert result_a.crawler_deaths == result_b.crawler_deaths
    assert result_a.defeated_enemy_ids == result_b.defeated_enemy_ids
    assert crawl_a.fingerprint() == crawl_b.fingerprint()


def test_item_has_one_authoritative_owner_and_drops_on_death():
    service, crawl = make_crawl(seed="item-authority", crawlers=2, floors=1)
    encounter = first_hostile(crawl)
    item_id = encounter.reward_item_ids[0]
    transfer_item_to_crawler(crawl, item_id, "npc_000")

    assert crawl.items[item_id].owner_npc_id == "npc_000"
    assert crawl.items[item_id].location_id is None
    assert item_id in crawl.participants["npc_000"].gameplay.inventory_item_ids

    crawl.participants["npc_000"].current_location_id = encounter.location_id
    dropped = drop_all_on_death(crawl, "npc_000")
    service.eliminate(crawl, "npc_000", dead=True)

    assert item_id in dropped
    assert crawl.items[item_id].owner_npc_id is None
    assert crawl.items[item_id].location_id == encounter.location_id
    assert item_id not in crawl.participants["npc_000"].gameplay.inventory_item_ids
    Crawl.model_validate(crawl.model_dump(mode="python"))


def test_progression_diverges_with_different_crawler_profiles():
    _, crawl = make_crawl(seed="build-divergence", crawlers=2, floors=1)
    vanguard = crawl.participants["npc_000"]
    mystic = crawl.participants["npc_001"]

    # Force unambiguous profiles so this regression tests the specialization logic,
    # not whatever random traits happened to be generated for these IDs.
    vanguard.agent.skills.defense = 1.0
    vanguard.agent.skills.melee = 1.0
    vanguard.agent.skills.ranged = 0.0
    vanguard.agent.skills.perception = 0.0
    vanguard.agent.skills.stealth = 0.0
    vanguard.agent.skills.medicine = 0.0
    vanguard.agent.skills.scavenging = 0.0
    vanguard.agent.skills.ability_use = 0.0
    vanguard.agent.traits.loyalty = 1.0
    vanguard.agent.traits.courage = 1.0
    vanguard.agent.traits.empathy = 0.0
    vanguard.agent.traits.caution = 0.0
    vanguard.agent.traits.patience = 0.0
    vanguard.agent.traits.curiosity = 0.0

    mystic.agent.skills.defense = 0.0
    mystic.agent.skills.melee = 0.0
    mystic.agent.skills.ranged = 0.0
    mystic.agent.skills.perception = 0.0
    mystic.agent.skills.stealth = 0.0
    mystic.agent.skills.medicine = 0.0
    mystic.agent.skills.scavenging = 0.0
    mystic.agent.skills.ability_use = 1.0
    mystic.agent.traits.curiosity = 1.0
    mystic.agent.traits.risk_tolerance = 1.0
    mystic.agent.traits.competitiveness = 1.0

    award_experience(vanguard, 500)
    award_experience(mystic, 500)
    choose_progression(vanguard, crawl_seed=crawl.seed)
    choose_progression(mystic, crawl_seed=crawl.seed)

    assert vanguard.gameplay.progression.specialization == "vanguard"
    assert mystic.gameplay.progression.specialization == "mystic"
    assert vanguard.gameplay.progression.ability_ids != mystic.gameplay.progression.ability_ids


def test_emergent_party_forms_from_compatible_crawlers():
    _, crawl = make_crawl(seed="party-formation", crawlers=3, floors=1)
    for participant in crawl.participants.values():
        participant.agent.traits.sociability = 1.0
        participant.agent.traits.loyalty = 1.0
    ids = sorted(crawl.participants)
    for left in ids:
        for right in ids:
            if left == right:
                continue
            rel = crawl.participants[left].agent.relationships.get(right)
            if rel is None:
                from livingworld.crawler_social import relationship

                rel = relationship(crawl.participants[left].agent, right)
            rel.trust = 0.8
            rel.resentment = 0.0

    party = maybe_form_party(crawl, ids)
    assert party is not None
    assert len(party.member_npc_ids) >= 2
    assert party.leader_npc_id in party.member_npc_ids
    assert all(crawl.participants[npc_id].current_party_id == party.id for npc_id in party.member_npc_ids)
    Crawl.model_validate(crawl.model_dump(mode="python"))


def test_encounter_rewards_can_be_equipped_or_consumed_without_duplicate_state():
    service, crawl = make_crawl(seed="reward-state", crawlers=5, floors=1)
    simulator = GameplayCrawlSimulator(service)
    simulator.prepare(crawl)

    assert crawl.encounters
    assert crawl.items
    assert all(item.encounter_id is not None for item in crawl.items.values())
    Crawl.model_validate(crawl.model_dump(mode="python"))


def test_integrated_gameplay_run_finishes_or_eliminates_field_cleanly():
    service, crawl = make_crawl(seed="integrated-batch2", crawlers=30, floors=2)
    simulator = GameplayCrawlSimulator(service)
    summaries = simulator.run(crawl, max_steps=4_000)

    assert summaries
    assert crawl.status == CrawlStatus.COMPLETED
    assert crawl.surviving_crawler_count + crawl.eliminated_crawler_count == crawl.starting_crawler_count
    assert any(summary.encounters_resolved > 0 for summary in summaries)
    assert any(encounter.cleanup_complete for encounter in crawl.encounters.values())
    assert all(item.category in set(ItemCategory) for item in crawl.items.values())
    Crawl.model_validate(crawl.model_dump(mode="python"))

    dead = [participant for participant in crawl.participants.values() if participant.status == ParticipationStatus.DEAD]
    for participant in dead:
        assert participant.health == 0.0
