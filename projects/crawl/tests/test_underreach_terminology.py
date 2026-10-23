from __future__ import annotations

from livingworld.arbiter import Arbiter
from livingworld.crawl_domain import (
    Crawl,
    CrawlEvent,
    CrawlFloor,
    CrawlLocation,
    CrawlStatus,
    CrawlerParticipation,
    LocationKind,
)
from livingworld.descender_domain import DescenderAgentState, build_descender_agent
from livingworld.echoes import Echo, EchoDetector, EchoReelAssembler
from livingworld.feed_state import public_descender, public_descent, public_ledger_event, public_stratum
from livingworld.underreach_domain import Descent, LedgerEvent, Sector, Stratum
from livingworld.underreach_terminology import (
    DESCENT_NAME,
    FEED_NAME,
    LEDGER_NAME,
    UNDERREACH_NAME,
    legacy_event_type,
    public_event_type,
    public_participation_status,
    public_protocol,
)


def _descent() -> Crawl:
    sector = CrawlLocation(
        id="sector_001",
        floor_number=1,
        name="Entrance Refuge",
        kind=LocationKind.SAFE_AREA,
    )
    stratum = CrawlFloor(
        number=1,
        seed="stratum-seed",
        theme="stone",
        locations={sector.id: sector},
        entrance_location_id=sector.id,
        exit_location_ids=[sector.id],
        safe_area_ids=[sector.id],
    )
    participant = CrawlerParticipation(
        npc_id="descender_001",
        crawl_id="descent_001",
        current_floor=1,
        current_location_id=sector.id,
    )
    return Crawl(
        id="descent_001",
        seed="underreach-test",
        status=CrawlStatus.RUNNING,
        ruleset_id="rules",
        ruleset_version="1",
        starting_crawler_count=1,
        surviving_crawler_count=1,
        eliminated_crawler_count=0,
        floors={1: stratum},
        participants={participant.npc_id: participant},
    )


def test_underreach_domain_aliases_preserve_proven_models():
    assert Descent is Crawl
    assert LedgerEvent is CrawlEvent
    assert Stratum is CrawlFloor
    assert Sector is CrawlLocation
    assert issubclass(Arbiter, object)
    assert Echo.__name__ == "StoryArc"
    assert EchoDetector.__name__ == "StoryArcDetector"
    assert EchoReelAssembler.__name__ == "HighlightReelAssembler"
    assert DescenderAgentState.__name__ == "CrawlerAgentState"


def test_public_vocabulary_translates_only_the_projection():
    assert public_event_type("CRAWLER_DIED") == "DESCENDER_DIED"
    assert public_event_type("FLOOR_COMPLETED") == "STRATUM_COMPLETED"
    assert public_event_type("CRAWL_STARTED") == "DESCENT_STARTED"
    assert public_event_type("COMBAT_HIT") == "COMBAT_HIT"
    assert legacy_event_type("DESCENDER_DIED") == "CRAWLER_DIED"
    assert legacy_event_type("STRATUM_COMPLETED") == "FLOOR_COMPLETED"
    assert public_participation_status("dead") == "fallen"
    assert public_protocol("crawl.presentation-stage.v1") == "underreach.presentation-stage.v1"


def test_feed_projection_uses_underreach_terms_without_mutating_descent():
    descent = _descent()
    before = descent.model_dump(mode="json")
    fingerprint = descent.fingerprint()

    payload = public_descent(descent)
    stratum = public_stratum(descent)
    descender = public_descender(descent, "descender_001")

    assert payload["world"] == UNDERREACH_NAME
    assert payload["competition"] == DESCENT_NAME
    assert payload["broadcast"] == FEED_NAME
    assert payload["record"] == LEDGER_NAME
    assert payload["current_stratum"] == 1
    assert payload["starting_descender_count"] == 1
    assert "current_floor" not in payload
    assert "starting_crawler_count" not in payload

    assert stratum["number"] == 1
    assert stratum["refuge_sector_ids"] == ["sector_001"]
    assert stratum["sectors"][0]["kind"] == "refuge"
    assert "locations" not in stratum

    assert descender["descender_id"] == "descender_001"
    assert descender["current_stratum"] == 1
    assert descender["current_sector_id"] == "sector_001"
    assert "current_floor" not in descender

    assert descent.model_dump(mode="json") == before
    assert descent.fingerprint() == fingerprint


def test_ledger_projection_preserves_canonical_id_and_event_object():
    descent = _descent()
    event = CrawlEvent(
        id="crawl_event_001",
        crawl_id=descent.id,
        floor_number=1,
        tick=4,
        event_type="CRAWLER_DIED",
        summary="Descender fell in the test sector.",
        actor_ids=["descender_001"],
        location_id="sector_001",
    )
    before = event.model_dump(mode="json")

    projected = public_ledger_event(event)

    assert projected["id"] == event.id
    assert projected["descent_id"] == descent.id
    assert projected["stratum_number"] == 1
    assert projected["sector_id"] == "sector_001"
    assert projected["event_type"] == "DESCENDER_DIED"
    assert projected["canonical"] is True
    assert event.model_dump(mode="json") == before


def test_descender_agent_alias_does_not_change_deterministic_generation():
    a = build_descender_agent("same-seed", "descender_001")
    b = build_descender_agent("same-seed", "descender_001")
    assert a == b
