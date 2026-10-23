from livingworld.crawl_domain import Crawl
from livingworld.crawl_observatory import build_observatory_snapshot
from livingworld.crawl_scale_validation import run_matrix
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.detail_tiers import (
    SimulationDetailTier,
    due_crawlers,
    rebalance_detail_tiers,
    scheduler_load,
    set_tier,
    tier_distribution,
    tier_for,
)
from livingworld.headless_mvp_simulation import HeadlessCrawlMVP


def make_crawl(seed="batch4", crawlers=12, floors=2):
    service = CrawlLifecycleService()
    crawl = service.create_seeded_crawl(
        seed=seed,
        crawler_ids=[f"npc_{index:03d}" for index in range(crawlers)],
        floor_count=floors,
    )
    service.start(crawl)
    return service, crawl


def test_detail_tier_transition_preserves_authoritative_crawler_state():
    service, crawl = make_crawl(seed="tier-continuity", crawlers=4, floors=1)
    npc_id = "npc_000"
    before = crawl.participants[npc_id].model_dump(mode="json")

    changed = set_tier(
        crawl,
        npc_id,
        SimulationDetailTier.FOCUSED,
        reason="watched",
        lifecycle=service,
    )

    assert changed is True
    assert tier_for(crawl, npc_id) == SimulationDetailTier.FOCUSED
    assert crawl.participants[npc_id].model_dump(mode="json") == before
    Crawl.model_validate(crawl.model_dump(mode="python"))


def test_detail_tier_scheduler_is_deterministic_and_reduces_update_load():
    _, first = make_crawl(seed="tier-scheduler", crawlers=40, floors=1)
    _, second = make_crawl(seed="tier-scheduler", crawlers=40, floors=1)
    focused = ["npc_000", "npc_001"]

    first_distribution = rebalance_detail_tiers(first, focused_ids=focused)
    second_distribution = rebalance_detail_tiers(second, focused_ids=focused)

    assert first_distribution == second_distribution
    assert tier_distribution(first) == tier_distribution(second)
    assert due_crawlers(first, tick=17) == due_crawlers(second, tick=17)
    assert tier_for(first, "npc_000") == SimulationDetailTier.FOCUSED
    load = scheduler_load(first, horizon_ticks=32)
    assert 0 < load["scheduled_ratio"] < 1
    assert load["scheduled_updates"] < load["full_frequency_updates"]


def test_multi_seed_validation_checks_replay_structural_invariants_and_live_scheduler():
    report = run_matrix(
        base_seed="batch4-matrix-test",
        seeds=2,
        crawlers=12,
        floors=2,
        max_steps=3000,
        replay=True,
    )

    assert report["summary"]["overall"] is True
    assert report["summary"]["all_structural_invariants_passed"] is True
    assert report["summary"]["all_replays_deterministic"] is True
    assert report["summary"]["live_scheduler_exercised"] is True
    assert report["summary"]["scheduler_live_failures"] == []
    assert 0 < report["summary"]["scheduler_ratio_mean"] < 1
    assert len(report["results"]) == 2
    assert all(item["completed"] for item in report["results"])
    assert all(item["deterministic_replay"] for item in report["results"])
    assert all(item["scheduler_load"]["scheduled_updates"] > 0 for item in report["results"])
    assert all(item["scheduler_load"]["rebalances"] > 0 for item in report["results"])
    assert all(
        any(sum(distribution[tier] for tier in ("A", "B", "C")) > 0 for distribution in item["scheduler_load"]["observed_distributions"])
        for item in report["results"]
    )


def test_observatory_exposes_required_debug_views_and_decision_trace():
    service, crawl = make_crawl(seed="observatory", crawlers=10, floors=2)
    mvp = HeadlessCrawlMVP(service, intermission_ticks=2, director_interval=2)
    mvp.prepare(crawl)

    event_a = service.record_event(
        crawl,
        "NEAR_DEATH",
        "Crawler nearly died during an observatory test.",
        actor_ids=["npc_000"],
        data={"danger": 0.95},
    )
    event_b = service.record_event(
        crawl,
        "RESCUE",
        "Crawler 000 helped Crawler 001.",
        actor_ids=["npc_000", "npc_001"],
        data={"relationship_impact": 0.5, "reversal": True},
    )
    rebalance_detail_tiers(crawl, focused_ids=["npc_000"])

    snapshot = build_observatory_snapshot(
        crawl,
        [event_a, event_b],
        telemetry={"step_ms": 1.25},
        selected_crawler_id="npc_000",
    )

    assert snapshot["crawl"]["id"] == crawl.id
    assert "occupancy" in snapshot["floor"]
    assert "detail_tiers" in snapshot["population"]
    assert "scheduler" in snapshot["population"]
    assert "active_encounters" in snapshot
    assert "active_parties" in snapshot
    assert "director_interventions" in snapshot
    assert "interesting_events" in snapshot
    assert snapshot["performance"]["step_ms"] == 1.25
    diagnostic = snapshot["selected_crawler"]
    assert diagnostic["npc_id"] == "npc_000"
    assert diagnostic["detail_tier"] == "A"
    assert "decision_trace" in diagnostic
    assert diagnostic["recent_events"]
