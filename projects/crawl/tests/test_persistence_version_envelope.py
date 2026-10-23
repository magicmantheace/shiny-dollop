"""Versioned persistence envelopes for canonical Crawl state and Ledger events."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from livingworld.crawl_domain import CrawlEvent
from livingworld.crawl_persistence import (
    EVENT_PROTOCOL,
    EVENT_SCHEMA_VERSION,
    STATE_PROTOCOL,
    STATE_SCHEMA_VERSION,
    CrawlEventRow,
    CrawlPersistence,
    CrawlRow,
    PersistenceVersionError,
)
from livingworld.crawl_service import CrawlLifecycleService


def _setup(tmp_path):
    persistence = CrawlPersistence(f"sqlite:///{tmp_path / 'envelope.db'}")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    descent = service.create_seeded_crawl(
        seed="envelope", crawler_ids=["walker"], floor_count=1
    )
    service.start(descent, tick=3)
    event = service.record_event(
        descent, "CRAWLER_MOVED", "walker moved on", actor_ids=["walker"]
    )
    return persistence, descent, event


def _insert_raw_state_row(persistence, crawl, payload: dict) -> None:
    now = datetime.now(timezone.utc)
    with Session(persistence.engine) as session:
        session.add(
            CrawlRow(
                id=crawl.id,
                status=crawl.status.value,
                current_floor=crawl.current_floor,
                state=payload,
                updated_at=now,
            )
        )
        session.commit()


def _insert_raw_event_row(persistence, event: CrawlEvent, payload: dict) -> None:
    with Session(persistence.engine) as session:
        session.add(
            CrawlEventRow(
                id=event.id,
                crawl_id=event.crawl_id,
                floor_number=event.floor_number,
                tick=event.tick,
                event_type=event.event_type,
                event=payload,
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()


def test_state_blob_carries_version_envelope_and_roundtrips(tmp_path):
    persistence, descent, _ = _setup(tmp_path)
    with Session(persistence.engine) as session:
        row = session.get(CrawlRow, descent.id)
        assert row is not None
        assert row.state["protocol"] == STATE_PROTOCOL
        assert row.state["schema_version"] == STATE_SCHEMA_VERSION
        assert isinstance(row.state["state"], dict)
    loaded = persistence.load_crawl(descent.id)
    assert loaded is not None
    assert loaded.fingerprint() == descent.fingerprint()


def test_event_blob_carries_version_envelope_and_roundtrips(tmp_path):
    persistence, _, event = _setup(tmp_path)
    with Session(persistence.engine) as session:
        row = session.get(CrawlEventRow, event.id)
        assert row is not None
        assert row.event["protocol"] == EVENT_PROTOCOL
        assert row.event["schema_version"] == EVENT_SCHEMA_VERSION
        assert isinstance(row.event["event"], dict)
    events = persistence.list_events(event.crawl_id)
    assert event.id in [item.id for item in events]


def test_legacy_pre_envelope_blobs_load_as_v1(tmp_path):
    persistence, descent, event = _setup(tmp_path)
    persistence.reset_all()
    _insert_raw_state_row(persistence, descent, descent.model_dump(mode="json"))
    _insert_raw_event_row(persistence, event, event.model_dump(mode="json"))
    loaded = persistence.load_crawl(descent.id)
    assert loaded is not None
    assert loaded.fingerprint() == descent.fingerprint()
    events = persistence.list_events(descent.id)
    assert event.id in [item.id for item in events]
    # Search still finds legacy rows through the pre-envelope JSON paths.
    hits = persistence.search_events(descent.id, "walker moved")
    assert [item.id for item in hits] == [event.id]


def test_unknown_state_protocol_is_rejected(tmp_path):
    persistence, descent, _ = _setup(tmp_path)
    persistence.reset_all()
    _insert_raw_state_row(
        persistence,
        descent,
        {
            "protocol": "underreach.crawl-state.v9",
            "schema_version": 1,
            "state": descent.model_dump(mode="json"),
        },
    )
    with pytest.raises(PersistenceVersionError, match="unsupported crawl-state protocol"):
        persistence.load_crawl(descent.id)


def test_unknown_state_schema_version_is_rejected(tmp_path):
    persistence, descent, _ = _setup(tmp_path)
    persistence.reset_all()
    _insert_raw_state_row(
        persistence,
        descent,
        {
            "protocol": STATE_PROTOCOL,
            "schema_version": 999,
            "state": descent.model_dump(mode="json"),
        },
    )
    with pytest.raises(
        PersistenceVersionError, match="unsupported crawl-state schema version"
    ):
        persistence.load_crawl(descent.id)


def test_unknown_event_schema_version_is_rejected(tmp_path):
    persistence, descent, event = _setup(tmp_path)
    persistence.reset_all()
    _insert_raw_event_row(
        persistence,
        event,
        {
            "protocol": EVENT_PROTOCOL,
            "schema_version": 2,
            "event": event.model_dump(mode="json"),
        },
    )
    with pytest.raises(
        PersistenceVersionError, match="unsupported crawl-event schema version"
    ):
        persistence.list_events(descent.id)


def test_malformed_envelope_is_rejected(tmp_path):
    persistence, descent, _ = _setup(tmp_path)
    persistence.reset_all()
    _insert_raw_state_row(
        persistence,
        descent,
        {"protocol": STATE_PROTOCOL, "schema_version": STATE_SCHEMA_VERSION},
    )
    with pytest.raises(PersistenceVersionError, match="missing its state payload"):
        persistence.load_crawl(descent.id)
