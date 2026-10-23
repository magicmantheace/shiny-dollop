from pydantic import ValidationError
import pytest

from livingworld.crawl_domain import CrawlFloor, CrawlLocation, CrawlStatus, FloorStatus, LocationKind, ParticipationStatus
from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService, generate_floor


def make_service(tmp_path):
    persistence = CrawlPersistence(f"sqlite:///{tmp_path / 'crawl.db'}")
    persistence.initialize()
    return CrawlLifecycleService(persistence), persistence


def test_seeded_crawl_creation_is_deterministic(tmp_path):
    service, _ = make_service(tmp_path)
    first = service.create_seeded_crawl(
        seed="slice1-determinism",
        crawler_ids=["npc_a", "npc_b", "npc_c"],
        floor_count=3,
    )

    other = CrawlLifecycleService()
    second = other.create_seeded_crawl(
        seed="slice1-determinism",
        crawler_ids=["npc_a", "npc_b", "npc_c"],
        floor_count=3,
    )

    assert first.fingerprint() == second.fingerprint()
    assert first.starting_crawler_count == 3
    assert first.surviving_crawler_count == 3
    assert list(first.floors) == [1, 2, 3]


def test_floor_graph_has_reachable_exit():
    floor = generate_floor("graph-seed", 2)
    assert floor.entrance_location_id in floor.locations
    assert floor.exit_location_ids
    assert all(exit_id in floor.locations for exit_id in floor.exit_location_ids)


def test_invalid_floor_graph_is_rejected():
    entrance = CrawlLocation(
        id="entrance",
        floor_number=1,
        name="Entrance",
        kind=LocationKind.ENTRANCE,
        adjacency={"missing": 1.0},
    )
    exit_location = CrawlLocation(
        id="exit",
        floor_number=1,
        name="Exit",
        kind=LocationKind.EXIT,
    )
    with pytest.raises(ValidationError):
        CrawlFloor(
            number=1,
            seed="bad",
            theme="bad",
            locations={"entrance": entrance, "exit": exit_location},
            entrance_location_id="entrance",
            exit_location_ids=["exit"],
        )


def test_crawl_save_reload_advance_complete_and_archive(tmp_path):
    service, persistence = make_service(tmp_path)
    crawl = service.create_seeded_crawl(
        seed="lifecycle",
        crawler_ids=["npc_a", "npc_b"],
        floor_count=2,
    )

    service.start(crawl, tick=25)
    assert crawl.status == CrawlStatus.RUNNING
    assert crawl.floors[1].status == FloorStatus.ACTIVE
    assert crawl.floors[1].started_at_tick == 25

    reloaded = persistence.load_crawl(crawl.id)
    assert reloaded is not None
    assert reloaded.model_dump(mode="json") == crawl.model_dump(mode="json")

    service.complete_current_floor(crawl, advance_ticks=5)
    assert crawl.current_floor == 2
    assert crawl.floors[1].status == FloorStatus.COMPLETED
    assert crawl.floors[2].status == FloorStatus.ACTIVE
    assert all(participant.current_floor == 2 for participant in crawl.participants.values())
    assert all(participant.status == ParticipationStatus.ACTIVE for participant in crawl.participants.values())

    service.complete_current_floor(crawl, advance_ticks=5)
    assert crawl.status == CrawlStatus.COMPLETED

    service.archive(crawl)
    assert crawl.status == CrawlStatus.ARCHIVED
    archived = persistence.load_crawl(crawl.id)
    assert archived is not None
    assert archived.status == CrawlStatus.ARCHIVED
    assert archived.archived_at_tick == crawl.current_tick


def test_elimination_updates_authoritative_counts_and_history(tmp_path):
    service, persistence = make_service(tmp_path)
    crawl = service.create_seeded_crawl(
        seed="elimination",
        crawler_ids=["npc_a", "npc_b", "npc_c"],
        floor_count=1,
    )
    service.start(crawl)
    service.eliminate(crawl, "npc_b", dead=True)

    assert crawl.participants["npc_b"].status == ParticipationStatus.DEAD
    assert crawl.participants["npc_b"].health == 0
    assert crawl.surviving_crawler_count == 2
    assert crawl.eliminated_crawler_count == 1
    assert crawl.floors[1].active_crawler_count == 2

    events = persistence.list_events(crawl.id)
    event_types = {event.event_type for event in events}
    assert "CRAWLER_DIED" in event_types
    assert "CRAWL_CREATED" in event_types
    assert "CRAWL_STARTED" in event_types


def test_duplicate_crawler_ids_are_rejected():
    service = CrawlLifecycleService()
    with pytest.raises(ValueError, match="unique"):
        service.create_seeded_crawl(
            seed="duplicates",
            crawler_ids=["npc_a", "npc_a"],
            floor_count=1,
        )
