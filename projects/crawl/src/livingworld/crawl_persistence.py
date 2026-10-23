from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, create_engine, delete, func, or_, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool

from .crawl_domain import Crawl, CrawlEvent


STATE_PROTOCOL = "underreach.crawl-state.v1"
EVENT_PROTOCOL = "underreach.crawl-event.v1"
STATE_SCHEMA_VERSION = 1
EVENT_SCHEMA_VERSION = 1


class PersistenceVersionError(RuntimeError):
    """Raised when a persisted blob carries an unknown protocol or schema version."""


def _encode_state(crawl: Crawl) -> dict[str, Any]:
    """Wrap canonical Crawl state in a versioned envelope."""
    return {
        "protocol": STATE_PROTOCOL,
        "schema_version": STATE_SCHEMA_VERSION,
        "state": crawl.model_dump(mode="json"),
    }


def _encode_event(event: CrawlEvent) -> dict[str, Any]:
    """Wrap a canonical Ledger event in a versioned envelope."""
    return {
        "protocol": EVENT_PROTOCOL,
        "schema_version": EVENT_SCHEMA_VERSION,
        "event": event.model_dump(mode="json"),
    }


def _decode_state(payload: Any) -> Crawl:
    """Validate a persisted Crawl-state blob, rejecting unknown versions.

    Blobs written before envelopes existed carry no ``protocol`` field and are
    treated as schema v1 for backwards compatibility.
    """
    if isinstance(payload, dict) and isinstance(payload.get("protocol"), str):
        protocol = payload.get("protocol")
        if protocol != STATE_PROTOCOL:
            raise PersistenceVersionError(f"unsupported crawl-state protocol: {protocol!r}")
        version = payload.get("schema_version")
        if version != STATE_SCHEMA_VERSION:
            raise PersistenceVersionError(
                f"unsupported crawl-state schema version: {version!r} "
                f"(expected {STATE_SCHEMA_VERSION})"
            )
        state = payload.get("state")
        if not isinstance(state, dict):
            raise PersistenceVersionError("crawl-state envelope is missing its state payload")
        return Crawl.model_validate(state)
    return Crawl.model_validate(payload)


def _decode_event(payload: Any) -> CrawlEvent:
    """Validate a persisted Ledger-event blob, rejecting unknown versions.

    Blobs written before envelopes existed carry no ``protocol`` field and are
    treated as schema v1 for backwards compatibility.
    """
    if isinstance(payload, dict) and isinstance(payload.get("protocol"), str):
        protocol = payload.get("protocol")
        if protocol != EVENT_PROTOCOL:
            raise PersistenceVersionError(f"unsupported crawl-event protocol: {protocol!r}")
        version = payload.get("schema_version")
        if version != EVENT_SCHEMA_VERSION:
            raise PersistenceVersionError(
                f"unsupported crawl-event schema version: {version!r} "
                f"(expected {EVENT_SCHEMA_VERSION})"
            )
        event = payload.get("event")
        if not isinstance(event, dict):
            raise PersistenceVersionError("crawl-event envelope is missing its event payload")
        return CrawlEvent.model_validate(event)
    return CrawlEvent.model_validate(payload)


def _escape_like(value: str) -> str:
    """Escape SQL LIKE wildcards so a search needle is matched literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class CrawlBase(DeclarativeBase):
    pass


class CrawlRow(CrawlBase):
    __tablename__ = "crawls"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    current_floor: Mapped[int] = mapped_column(Integer, index=True)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CrawlEventRow(CrawlBase):
    __tablename__ = "crawl_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    crawl_id: Mapped[str] = mapped_column(String(64), index=True)
    floor_number: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    tick: Mapped[int] = mapped_column(Integer, index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    event: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CrawlPersistence:
    """Persistence boundary for crawl-specific authoritative state.

    It intentionally uses separate tables from the inherited LivingWorld state so
    the crawl pivot can evolve without destabilizing the existing continent save.
    """

    def __init__(self, database_url: str) -> None:
        # StaticPool deliberately shares one in-memory SQLite connection across
        # the producer and viewer threads. Serialize every Session lifecycle so
        # polling the live spectator API cannot overlap a simulation commit on
        # that single DB-API connection.
        self._session_lock = RLock()
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        engine_kwargs: dict[str, Any] = {
            "future": True,
            "pool_pre_ping": True,
            "connect_args": connect_args,
        }
        if database_url in {"sqlite:///:memory:", "sqlite://"}:
            # SQLite in-memory databases are connection-local by default. TestClient
            # serves requests from another thread/connection, so use one shared
            # connection for the lifetime of this persistence object.
            engine_kwargs["poolclass"] = StaticPool
        self.engine = create_engine(database_url, **engine_kwargs)

    def initialize(self) -> None:
        with self._session_lock:
            CrawlBase.metadata.create_all(self.engine)

    def reset_all(self) -> None:
        with self._session_lock:
            with Session(self.engine) as session:
                session.execute(delete(CrawlEventRow))
                session.execute(delete(CrawlRow))
                session.commit()

    def save_crawl(self, crawl: Crawl) -> None:
        payload = _encode_state(crawl)
        now = datetime.now(timezone.utc)
        with self._session_lock:
            with Session(self.engine) as session:
                row = session.get(CrawlRow, crawl.id)
                if row is None:
                    session.add(
                        CrawlRow(
                            id=crawl.id,
                            status=crawl.status.value,
                            current_floor=crawl.current_floor,
                            state=payload,
                            updated_at=now,
                        )
                    )
                else:
                    row.status = crawl.status.value
                    row.current_floor = crawl.current_floor
                    row.state = payload
                    row.updated_at = now
                session.commit()

    def load_crawl(self, crawl_id: str) -> Crawl | None:
        with self._session_lock:
            with Session(self.engine) as session:
                row = session.get(CrawlRow, crawl_id)
                return _decode_state(row.state) if row else None

    def list_crawls(self, limit: int = 100, status: str | None = None) -> list[Crawl]:
        limit = max(1, min(500, limit))
        stmt = select(CrawlRow)
        if status is not None:
            stmt = stmt.where(CrawlRow.status == status)
        stmt = stmt.order_by(CrawlRow.updated_at.desc(), CrawlRow.id).limit(limit)
        with self._session_lock:
            with Session(self.engine) as session:
                return [_decode_state(row.state) for row in session.scalars(stmt).all()]

    def append_event(self, event: CrawlEvent) -> None:
        with self._session_lock:
            with Session(self.engine) as session:
                if session.get(CrawlEventRow, event.id):
                    return
                session.add(
                    CrawlEventRow(
                        id=event.id,
                        crawl_id=event.crawl_id,
                        floor_number=event.floor_number,
                        tick=event.tick,
                        event_type=event.event_type,
                        event=_encode_event(event),
                        created_at=datetime.now(timezone.utc),
                    )
                )
                session.commit()

    def list_events(
        self,
        crawl_id: str,
        limit: int = 200,
        event_type: str | None = None,
    ) -> list[CrawlEvent]:
        # Formal 100-crawler crawls already produce ~4k-5k canonical events.
        # Keep ordinary API calls bounded while allowing complete replay archives.
        limit = max(1, min(10000, limit))
        stmt = select(CrawlEventRow).where(CrawlEventRow.crawl_id == crawl_id)
        if event_type is not None:
            stmt = stmt.where(CrawlEventRow.event_type == event_type)
        stmt = stmt.order_by(CrawlEventRow.tick.desc(), CrawlEventRow.id.desc()).limit(limit)
        with self._session_lock:
            with Session(self.engine) as session:
                return [_decode_event(row.event) for row in session.scalars(stmt).all()]

    def search_events(
        self,
        crawl_id: str,
        needle: str,
        *,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[CrawlEvent]:
        """Substring search over the complete canonical Ledger, filtered in SQL.

        Unlike ``list_events``, the match is applied at the database level with
        no premature row limit, so queries matching only old events are still
        found.  The needle is matched case-insensitively against the event
        type, the event summary, and the actor-id list.  SQL LIKE wildcards in
        the needle are escaped so they match literally.  Results are
        deterministic: ascending ``(tick, id)``, truncated to ``limit``.
        """
        needle = needle.strip().lower()
        if not needle:
            return []
        limit = max(1, min(1000, limit))
        pattern = f"%{_escape_like(needle)}%"
        # Enveloped blobs nest the event under "event"; pre-envelope legacy
        # rows hold it at the top level.  json_extract returns NULL for the
        # path that does not exist, which never matches.
        conditions = [
            func.lower(CrawlEventRow.event_type).like(pattern, escape="\\"),
        ]
        for path in (
            "$.event.summary",
            "$.summary",
            "$.event.actor_ids",
            "$.actor_ids",
        ):
            conditions.append(
                func.lower(func.json_extract(CrawlEventRow.event, path)).like(
                    pattern, escape="\\"
                )
            )
        stmt = (
            select(CrawlEventRow)
            .where(CrawlEventRow.crawl_id == crawl_id)
            .where(or_(*conditions))
        )
        if event_type is not None:
            stmt = stmt.where(CrawlEventRow.event_type == event_type)
        stmt = stmt.order_by(CrawlEventRow.tick, CrawlEventRow.id).limit(limit)
        with self._session_lock:
            with Session(self.engine) as session:
                return [_decode_event(row.event) for row in session.scalars(stmt).all()]

    def events_by_ids(self, event_ids: list[str]) -> list[CrawlEvent]:
        """Load a small ordered event slice without replaying the whole Ledger."""
        if not event_ids:
            return []
        if len(event_ids) > 5000:
            raise ValueError("events_by_ids is intended for bounded incremental pages")
        wanted = {event_id: index for index, event_id in enumerate(event_ids)}
        stmt = select(CrawlEventRow).where(CrawlEventRow.id.in_(event_ids))
        with self._session_lock:
            with Session(self.engine) as session:
                values = [_decode_event(row.event) for row in session.scalars(stmt).all()]
        values.sort(key=lambda item: wanted[item.id])
        if [item.id for item in values] != event_ids:
            missing = [event_id for event_id in event_ids if event_id not in {item.id for item in values}]
            raise KeyError(f"Ledger events are missing: {missing[:5]}")
        return values

    def replay_events(self, crawl_id: str) -> list[CrawlEvent]:
        """Return the complete canonical Ledger in deterministic order."""
        stmt = (
            select(CrawlEventRow)
            .where(CrawlEventRow.crawl_id == crawl_id)
            .order_by(CrawlEventRow.tick, CrawlEventRow.id)
        )
        with self._session_lock:
            with Session(self.engine) as session:
                return [_decode_event(row.event) for row in session.scalars(stmt).all()]

    def restore_checkpoint_state(self, crawl: Crawl) -> int:
        """Restore one proven canonical state and discard only post-checkpoint rows.

        The caller must validate the checkpoint digest first.  Every event ID
        referenced by the checkpoint must already exist in durable storage;
        missing canonical history is a hard failure.  Rows written after the
        checkpoint are removed so a resumed deterministic run can regenerate
        them with the same stable IDs.
        """
        keep = set(crawl.history_event_ids)
        with self._session_lock:
            with Session(self.engine) as session:
                rows = session.scalars(
                    select(CrawlEventRow).where(CrawlEventRow.crawl_id == crawl.id)
                ).all()
                present = {row.id for row in rows}
                missing = keep - present
                if missing:
                    raise RuntimeError(
                        f"checkpoint Ledger prefix is incomplete ({len(missing)} missing events)"
                    )
                removed = 0
                for row in rows:
                    if row.id not in keep:
                        session.delete(row)
                        removed += 1
                state = _encode_state(crawl)
                existing = session.get(CrawlRow, crawl.id)
                now = datetime.now(timezone.utc)
                if existing is None:
                    session.add(CrawlRow(
                        id=crawl.id,
                        status=crawl.status.value,
                        current_floor=crawl.current_floor,
                        state=state,
                        updated_at=now,
                    ))
                else:
                    existing.status = crawl.status.value
                    existing.current_floor = crawl.current_floor
                    existing.state = state
                    existing.updated_at = now
                session.commit()
                return removed
