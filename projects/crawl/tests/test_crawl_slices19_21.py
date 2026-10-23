from fastapi.testclient import TestClient

from livingworld.crawl_domain import Crawl
from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.crawler_social import relationship
from livingworld.headless_mvp_simulation import HeadlessCrawlMVP
from livingworld.party_system import maybe_form_party, update_party_stability
from livingworld.replay_engine import ReplayArchive
from livingworld.spectator_api import SpectatorRepository, create_spectator_app
from livingworld.spectator_state import public_crawler, visible_encounters
from livingworld.unreal_spectator_bridge import BRIDGE_PROTOCOL, bridge_bootstrap, build_bridge_frame


def make_completed_crawl(tmp_path, seed="batch5", crawlers=16, floors=2):
    persistence = CrawlPersistence(f"sqlite:///{tmp_path / 'batch5.db'}")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    crawl = service.create_seeded_crawl(
        seed=seed,
        crawler_ids=[f"npc_{index:03d}" for index in range(crawlers)],
        floor_count=floors,
    )
    service.start(crawl)
    mvp = HeadlessCrawlMVP(service, intermission_ticks=2, director_interval=4)
    mvp.run(crawl, max_steps=5000)
    return persistence, crawl


def test_public_projection_does_not_leak_hidden_authoritative_state(tmp_path):
    persistence, crawl = make_completed_crawl(tmp_path, seed="spectator-safe")
    payload = public_crawler(crawl, "npc_000", include_social=True)
    serialized = str(payload)

    assert "knowledge" not in payload
    assert "memories" not in payload
    assert "traits" not in payload
    assert "preferences" not in payload
    assert "_crawl_director" not in serialized
    assert "_semantic_ledger" not in serialized
    assert all(item["status"] != "dormant" for item in visible_encounters(crawl))

    repo = SpectatorRepository(persistence, crawl.id)
    app = create_spectator_app(repo)
    client = TestClient(app)
    response = client.get("/api/spectator/crawl")
    assert response.status_code == 200
    assert "modifiers" not in response.json()


def test_spectator_api_can_follow_one_crawler_using_only_public_endpoints(tmp_path):
    persistence, crawl = make_completed_crawl(tmp_path, seed="spectator-client")
    client = TestClient(create_spectator_app(SpectatorRepository(persistence, crawl.id)))

    directory = client.get("/api/spectator/crawlers", params={"limit": 5})
    assert directory.status_code == 200
    npc_id = directory.json()[0]["npc_id"]

    profile = client.get(f"/api/spectator/crawlers/{npc_id}")
    history = client.get(f"/api/spectator/crawlers/{npc_id}/history")
    trending = client.get("/api/spectator/trending")
    replay = client.get("/api/spectator/replay")

    assert profile.status_code == 200
    assert profile.json()["npc_id"] == npc_id
    assert history.status_code == 200
    assert isinstance(history.json(), list)
    assert trending.status_code == 200
    assert replay.status_code == 200
    assert replay.json()["crawl_id"] == crawl.id


def test_replay_archive_is_complete_ordered_and_digest_stable(tmp_path):
    persistence, crawl = make_completed_crawl(tmp_path, seed="replay-stable", crawlers=24, floors=3)
    events = persistence.list_events(crawl.id, limit=10000)
    first = ReplayArchive(crawl, events)
    second = ReplayArchive(crawl, list(reversed(events)))

    assert first.manifest.event_count == len(events)
    assert first.manifest.event_count == len(crawl.history_event_ids)
    assert first.manifest.authoritative_event_digest == second.manifest.authoritative_event_digest
    assert first.manifest.final_state_fingerprint == crawl.fingerprint()
    assert list(first.events) == sorted(first.events, key=lambda event: (event.tick, event.id))

    public = first.public_window(limit=5000)
    assert public["manifest"]["event_count"] == len(events)
    assert public["events"]
    assert all("data" not in event for event in public["events"])


def test_replay_cause_chain_uses_semantic_parent_links(tmp_path):
    persistence, crawl = make_completed_crawl(tmp_path, seed="replay-causes", crawlers=8, floors=1)
    service = CrawlLifecycleService(persistence)
    parent = service.record_event(crawl, "NEAR_DEATH", "A crawler barely survived.", actor_ids=["npc_000"], data={"danger": 0.95})
    child = service.record_event(crawl, "RESCUE", "A crawler returned to help.", actor_ids=["npc_000", "npc_001"], data={"relationship_impact": 0.7, "reversal": True})
    archive = ReplayArchive(crawl, persistence.list_events(crawl.id, limit=10000))

    chain = archive.cause_chain(child.id)
    assert child.id in [event.id for event in chain]
    assert parent.id in [event.id for event in chain]


def test_unreal_bridge_is_read_only_and_contains_renderable_authoritative_state(tmp_path):
    persistence, crawl = make_completed_crawl(tmp_path, seed="unreal-bridge")
    events = persistence.list_events(crawl.id, limit=10000)
    before = crawl.fingerprint()

    bootstrap = bridge_bootstrap(crawl)
    frame = build_bridge_frame(crawl, events, since_tick=max(0, crawl.current_tick - 5)).as_dict()

    assert bootstrap["protocol"] == BRIDGE_PROTOCOL
    assert bootstrap["authority"] == "backend"
    assert "resolve_combat" in bootstrap["contracts"]["unreal_must_not"]
    assert frame["protocol"] == BRIDGE_PROTOCOL
    assert frame["crawl_id"] == crawl.id
    assert all("location_id" in item for item in frame["crawlers"])
    assert crawl.fingerprint() == before


def test_dissolving_party_preserves_valid_historical_roster_when_leader_becomes_inactive():
    service = CrawlLifecycleService()
    crawl = service.create_seeded_crawl(
        seed="party-leader-cleanup",
        crawler_ids=["npc_000", "npc_001", "npc_002"],
        floor_count=1,
    )
    service.start(crawl)

    for participant in crawl.participants.values():
        participant.agent.traits.sociability = 1.0
        participant.agent.traits.loyalty = 1.0
    ids = sorted(crawl.participants)
    for left in ids:
        for right in ids:
            if left == right:
                continue
            rel = relationship(crawl.participants[left].agent, right)
            rel.trust = 1.0
            rel.resentment = 0.0

    party = maybe_form_party(crawl, ids)
    assert party is not None
    original_members = list(party.member_npc_ids)
    original_leader = party.leader_npc_id

    for npc_id in original_members:
        if npc_id != original_members[-1]:
            service.eliminate(crawl, npc_id, summary="Regression setup elimination.")

    assert update_party_stability(crawl, party.id) is False
    assert party.active is False
    assert party.member_npc_ids == original_members
    assert original_leader in party.member_npc_ids
    assert all(crawl.participants[npc_id].current_party_id is None for npc_id in original_members)
    Crawl.model_validate(crawl.model_dump(mode="python"))


def test_in_memory_sqlite_survives_spectator_testclient_thread_boundary():
    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    crawl = service.create_seeded_crawl(
        seed="spectator-memory-thread",
        crawler_ids=["npc_000", "npc_001"],
        floor_count=1,
    )
    service.start(crawl)

    client = TestClient(create_spectator_app(SpectatorRepository(persistence, crawl.id)))
    response = client.get("/api/spectator/crawlers")

    assert response.status_code == 200
    assert {row["npc_id"] for row in response.json()} == {"npc_000", "npc_001"}
