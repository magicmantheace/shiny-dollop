from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .domain import CommandRecord, HistoricalEvent, WorldState


class Base(DeclarativeBase):
    pass


class WorldRow(Base):
    __tablename__ = "world_state"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EventRow(Base):
    __tablename__ = "history_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    world_hour: Mapped[int] = mapped_column(Integer, index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    event: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CommandRow(Base):
    __tablename__ = "command_audit"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    command_type: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    command: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SnapshotRow(Base):
    __tablename__ = "world_snapshots"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    world_hour: Mapped[int] = mapped_column(Integer, index=True)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Persistence:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine = create_engine(database_url, future=True, pool_pre_ping=True, connect_args=connect_args)

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)

    def reset_all(self) -> None:
        """Remove one world's mutable/persisted history before deliberate regeneration."""
        with Session(self.engine) as session:
            session.execute(delete(CommandRow))
            session.execute(delete(EventRow))
            session.execute(delete(SnapshotRow))
            session.execute(delete(WorldRow))
            session.commit()

    def load_world(self, world_id: str = "world_0001") -> WorldState | None:
        with Session(self.engine) as session:
            row = session.get(WorldRow, world_id)
            return WorldState.model_validate(row.state) if row else None

    def save_world(self, world: WorldState) -> None:
        now = datetime.now(timezone.utc)
        payload = world.model_dump(mode="json")
        with Session(self.engine) as session:
            row = session.get(WorldRow, world.id)
            if row:
                row.state = payload
                row.updated_at = now
            else:
                session.add(WorldRow(id=world.id, state=payload, updated_at=now))
            session.commit()

    def append_event(self, event: HistoricalEvent) -> None:
        payload = event.model_dump(mode="json")
        with Session(self.engine) as session:
            if session.get(EventRow, event.id):
                return
            session.add(EventRow(
                id=event.id,
                event_type=event.type,
                world_hour=event.occurred_at.ordinal_hour(),
                year=event.occurred_at.year,
                summary=event.summary,
                event=payload,
                created_at=datetime.now(timezone.utc),
            ))
            session.commit()

    def list_events(self, limit: int = 100, event_type: str | None = None, before_world_hour: int | None = None) -> list[HistoricalEvent]:
        limit = max(1, min(1000, limit))
        stmt = select(EventRow)
        if event_type:
            stmt = stmt.where(EventRow.event_type == event_type)
        if before_world_hour is not None:
            stmt = stmt.where(EventRow.world_hour < before_world_hour)
        stmt = stmt.order_by(EventRow.world_hour.desc(), EventRow.id.desc()).limit(limit)
        with Session(self.engine) as session:
            return [HistoricalEvent.model_validate(row.event) for row in session.scalars(stmt).all()]

    def save_command(self, record: CommandRecord) -> None:
        now = datetime.now(timezone.utc)
        payload = record.model_dump(mode="json")
        with Session(self.engine) as session:
            row = session.get(CommandRow, record.id)
            if row:
                row.status = record.status.value
                row.command = payload
                row.updated_at = now
            else:
                session.add(CommandRow(
                    id=record.id,
                    command_type=record.command.type,
                    status=record.status.value,
                    command=payload,
                    updated_at=now,
                ))
            session.commit()

    def list_commands(self, limit: int = 100) -> list[CommandRecord]:
        limit = max(1, min(500, limit))
        stmt = select(CommandRow).order_by(CommandRow.updated_at.desc()).limit(limit)
        with Session(self.engine) as session:
            return [CommandRecord.model_validate(row.command) for row in session.scalars(stmt).all()]

    def create_snapshot(self, world: WorldState, snapshot_id: str, note: str = "") -> str:
        with Session(self.engine) as session:
            if session.get(SnapshotRow, snapshot_id):
                raise ValueError(f"snapshot {snapshot_id!r} already exists")
            session.add(SnapshotRow(
                id=snapshot_id,
                world_hour=world.date.ordinal_hour(),
                state=world.model_dump(mode="json"),
                note=note,
                created_at=datetime.now(timezone.utc),
            ))
            session.commit()
        return snapshot_id

    def restore_snapshot(self, snapshot_id: str) -> WorldState:
        with Session(self.engine) as session:
            row = session.get(SnapshotRow, snapshot_id)
            if not row:
                raise KeyError(f"snapshot {snapshot_id!r} not found")
            world = WorldState.model_validate(row.state)
        self.save_world(world)
        return world

    def list_snapshots(self, limit: int = 50) -> list[dict[str, Any]]:
        stmt = select(SnapshotRow).order_by(SnapshotRow.created_at.desc()).limit(max(1, min(200, limit)))
        with Session(self.engine) as session:
            return [
                {"id": row.id, "world_hour": row.world_hour, "note": row.note, "created_at": row.created_at.isoformat()}
                for row in session.scalars(stmt).all()
            ]
