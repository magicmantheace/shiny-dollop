"""Durable non-authoritative media infrastructure for Underreach Phase 30.5 Slice 2.

30.5.1 established a read-only MediaEnvelope membrane. 30.5.2 persists those
presentation envelopes in a physically separate SQLite database, adds an
idempotent restart-safe job queue, and introduces capability/policy based
provider routing. No provider is invoked by this module.

The canonical Crawl database is never opened or mutated here. Paid providers
require explicit global and per-request permission; credentials alone can never
cause billable routing.
"""
from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
from threading import RLock
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import JSON, Boolean, Integer, String, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool

from .runtime_checkpoint import payload_digest
from .underreach_media_event_export import MediaEnvelope, validate_media_envelope


PROTOCOL = "underreach.media-foundation.v1"
IMPLEMENTATION_VERSION = "30.5.2"
PHASE = "30.5"

PROVIDER_KINDS = ("narrative", "verification", "image", "video", "voice")
JOB_STATUSES = ("queued", "running", "retry", "held", "completed", "failed")
ATTEMPT_STATUSES = ("running", "completed", "failed", "interrupted")


class MediaFoundationError(ValueError):
    """Raised when media persistence or routing violates the 30.5.2 contract."""


class ProviderKind(StrEnum):
    NARRATIVE = "narrative"
    VERIFICATION = "verification"
    IMAGE = "image"
    VIDEO = "video"
    VOICE = "voice"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY = "retry"
    HELD = "held"
    COMPLETED = "completed"
    FAILED = "failed"


class ProviderDescriptor(BaseModel):
    """Immutable provider capabilities; this is metadata, not an executable provider."""

    model_config = ConfigDict(frozen=True)

    provider_id: str
    kind: ProviderKind
    local: bool
    paid: bool
    available: bool = True
    healthy: bool = True
    capability_flags: tuple[str, ...] = ()
    deterministic_seed: bool = False
    reference_conditioning: bool = False
    image_to_video: bool = False
    max_width: int | None = Field(default=None, ge=1)
    max_height: int | None = Field(default=None, ge=1)
    max_duration_seconds: float | None = Field(default=None, ge=0.0)
    estimated_vram_mb: int = Field(default=0, ge=0)
    estimated_runtime_seconds: float = Field(default=0.0, ge=0.0)
    estimated_cost_microusd: int = Field(default=0, ge=0)
    quality_rank: int = Field(default=0, ge=0, le=100)
    quality_profile: str = "baseline"

    @model_validator(mode="after")
    def validate_provider(self) -> "ProviderDescriptor":
        if not self.provider_id.strip():
            raise ValueError("provider_id must be non-empty")
        if len(self.capability_flags) != len(set(self.capability_flags)):
            raise ValueError("provider capability flags must be unique")
        if self.paid and self.estimated_cost_microusd <= 0:
            raise ValueError("paid providers require a positive estimated monetary cost")
        if not self.paid and self.estimated_cost_microusd != 0:
            raise ValueError("free providers cannot report a billable estimated cost")
        return self


class ProviderPolicy(BaseModel):
    """Global routing policy. Defaults are intentionally local-only and zero-spend."""

    model_config = ConfigDict(frozen=True)

    local_only: bool = True
    cloud_allowed: bool = False
    allow_paid: bool = False
    require_explicit_paid_policy: bool = True
    daily_paid_budget_microusd: int = Field(default=0, ge=0)
    max_vram_mb: int | None = Field(default=None, ge=0)


class ProviderRequest(BaseModel):
    """Capabilities and policy constraints requested by one media job."""

    model_config = ConfigDict(frozen=True)

    kind: ProviderKind
    required_flags: tuple[str, ...] = ()
    local_required: bool = False
    paid_allowed: bool = False
    explicit_paid_authorization: bool = False
    deterministic_seed_required: bool = False
    reference_conditioning_required: bool = False
    image_to_video_required: bool = False
    min_width: int | None = Field(default=None, ge=1)
    min_height: int | None = Field(default=None, ge=1)
    min_duration_seconds: float | None = Field(default=None, ge=0.0)
    max_vram_mb: int | None = Field(default=None, ge=0)
    max_estimated_cost_microusd: int | None = Field(default=None, ge=0)
    min_quality_rank: int = Field(default=0, ge=0, le=100)

    @model_validator(mode="after")
    def validate_request(self) -> "ProviderRequest":
        if len(self.required_flags) != len(set(self.required_flags)):
            raise ValueError("required provider flags must be unique")
        if self.explicit_paid_authorization and not self.paid_allowed:
            raise ValueError("explicit paid authorization requires paid_allowed=true")
        return self


class ProviderSelection(BaseModel):
    model_config = ConfigDict(frozen=True)

    selected: bool
    provider_id: str | None = None
    reason_code: str
    paid: bool = False
    estimated_cost_microusd: int = 0
    candidate_count: int = 0


class MediaJob(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_id: str
    idempotency_key: str
    spec_digest: str
    envelope_id: str | None = None
    job_type: str
    status: JobStatus
    priority: int
    payload: dict[str, Any]
    provider_request: ProviderRequest | None = None
    attempt_count: int
    max_attempts: int
    selected_provider_id: str | None = None
    last_reason_code: str | None = None
    dependency_job_ids: tuple[str, ...] = ()


class JobLease(BaseModel):
    model_config = ConfigDict(frozen=True)

    job: MediaJob
    attempt_id: str
    attempt_number: int
    worker_id: str


class MediaBase(DeclarativeBase):
    pass


class MediaEnvelopeRow(MediaBase):
    __tablename__ = "media_envelopes"

    envelope_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    crawl_id: Mapped[str] = mapped_column(String(96), index=True)
    canonical_fingerprint: Mapped[str] = mapped_column(String(96), index=True)
    envelope_digest: Mapped[str] = mapped_column(String(96), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class MediaJobRow(MediaBase):
    __tablename__ = "media_jobs"

    job_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    spec_digest: Mapped[str] = mapped_column(String(96), nullable=False)
    envelope_id: Mapped[str | None] = mapped_column(String(96), index=True, nullable=True)
    job_type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    provider_request: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    selected_provider_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    last_reason_code: Mapped[str | None] = mapped_column(String(120), nullable=True)


class MediaJobDependencyRow(MediaBase):
    __tablename__ = "media_job_dependencies"

    dependency_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(96), index=True)
    depends_on_job_id: Mapped[str] = mapped_column(String(96), index=True)


class MediaAttemptRow(MediaBase):
    __tablename__ = "media_job_attempts"

    attempt_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(96), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    worker_id: Mapped[str] = mapped_column(String(96))
    provider_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    reason_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    resource_usage: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class MediaArtifactRow(MediaBase):
    __tablename__ = "media_artifacts"

    artifact_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(96), index=True)
    artifact_kind: Mapped[str] = mapped_column(String(64), index=True)
    uri: Mapped[str] = mapped_column(String(1024))
    digest: Mapped[str] = mapped_column(String(96))
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    review_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False)


class MediaProviderExecutionRow(MediaBase):
    __tablename__ = "media_provider_executions"

    execution_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(96), index=True)
    attempt_id: Mapped[str] = mapped_column(String(96), index=True)
    provider_id: Mapped[str] = mapped_column(String(96), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    estimated_cost_microusd: Mapped[int] = mapped_column(Integer, default=0)
    actual_cost_microusd: Mapped[int] = mapped_column(Integer, default=0)
    estimated_gpu_ms: Mapped[int] = mapped_column(Integer, default=0)
    actual_gpu_ms: Mapped[int] = mapped_column(Integer, default=0)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


def _stable_id(prefix: str, *parts: object) -> str:
    text = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(text.encode('utf-8')).hexdigest()[:24]}"


def _normalize_json(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


class MediaProviderRouter:
    """Deterministic capability router. It selects metadata only and invokes nothing."""

    def __init__(self) -> None:
        self._providers: dict[str, ProviderDescriptor] = {}

    def register(self, provider: ProviderDescriptor) -> ProviderDescriptor:
        existing = self._providers.get(provider.provider_id)
        if existing is not None and existing != provider:
            raise MediaFoundationError("provider_id is already registered with different capabilities")
        self._providers[provider.provider_id] = provider
        return provider

    def providers(self) -> tuple[ProviderDescriptor, ...]:
        return tuple(self._providers[key] for key in sorted(self._providers))

    @staticmethod
    def _eligible(
        provider: ProviderDescriptor,
        request: ProviderRequest,
        policy: ProviderPolicy,
        daily_paid_spend_microusd: int,
    ) -> bool:
        if provider.kind != request.kind or not provider.available or not provider.healthy:
            return False
        if policy.local_only and not provider.local:
            return False
        if not provider.local and not policy.cloud_allowed:
            return False
        if request.local_required and not provider.local:
            return False
        if not set(request.required_flags).issubset(set(provider.capability_flags)):
            return False
        if request.deterministic_seed_required and not provider.deterministic_seed:
            return False
        if request.reference_conditioning_required and not provider.reference_conditioning:
            return False
        if request.image_to_video_required and not provider.image_to_video:
            return False
        if request.min_width is not None and (provider.max_width is None or provider.max_width < request.min_width):
            return False
        if request.min_height is not None and (provider.max_height is None or provider.max_height < request.min_height):
            return False
        if request.min_duration_seconds is not None and (
            provider.max_duration_seconds is None or provider.max_duration_seconds < request.min_duration_seconds
        ):
            return False
        effective_vram_limit = request.max_vram_mb
        if policy.max_vram_mb is not None:
            effective_vram_limit = (
                policy.max_vram_mb
                if effective_vram_limit is None
                else min(effective_vram_limit, policy.max_vram_mb)
            )
        if effective_vram_limit is not None and provider.estimated_vram_mb > effective_vram_limit:
            return False
        if provider.quality_rank < request.min_quality_rank:
            return False
        if request.max_estimated_cost_microusd is not None and (
            provider.estimated_cost_microusd > request.max_estimated_cost_microusd
        ):
            return False
        if provider.paid:
            if not policy.allow_paid or not request.paid_allowed:
                return False
            if policy.require_explicit_paid_policy and not request.explicit_paid_authorization:
                return False
            if policy.daily_paid_budget_microusd <= 0:
                return False
            if daily_paid_spend_microusd + provider.estimated_cost_microusd > policy.daily_paid_budget_microusd:
                return False
        return True

    def select(
        self,
        request: ProviderRequest,
        policy: ProviderPolicy | None = None,
        *,
        daily_paid_spend_microusd: int = 0,
    ) -> ProviderSelection:
        if daily_paid_spend_microusd < 0:
            raise MediaFoundationError("daily paid spend cannot be negative")
        effective_policy = policy or ProviderPolicy()
        candidates = [
            provider
            for provider in self.providers()
            if self._eligible(provider, request, effective_policy, daily_paid_spend_microusd)
        ]
        if not candidates:
            return ProviderSelection(
                selected=False,
                provider_id=None,
                reason_code="no_eligible_provider",
                paid=False,
                estimated_cost_microusd=0,
                candidate_count=0,
            )
        candidates.sort(
            key=lambda item: (
                0 if item.local else 1,
                0 if not item.paid else 1,
                -item.quality_rank,
                item.estimated_cost_microusd,
                item.estimated_runtime_seconds,
                item.provider_id,
            )
        )
        chosen = candidates[0]
        return ProviderSelection(
            selected=True,
            provider_id=chosen.provider_id,
            reason_code="selected",
            paid=chosen.paid,
            estimated_cost_microusd=chosen.estimated_cost_microusd,
            candidate_count=len(candidates),
        )


class MediaPersistence:
    """Separate SQLite-backed presentation store and durable job queue."""

    def __init__(self, database_url: str) -> None:
        if not database_url.startswith("sqlite"):
            raise MediaFoundationError("30.5.2 media persistence currently requires SQLite")
        self.database_url = database_url
        self._session_lock = RLock()
        connect_args = {"check_same_thread": False}
        engine_kwargs: dict[str, Any] = {
            "future": True,
            "pool_pre_ping": True,
            "connect_args": connect_args,
        }
        if database_url in {"sqlite:///:memory:", "sqlite://"}:
            engine_kwargs["poolclass"] = StaticPool
        self.engine = create_engine(database_url, **engine_kwargs)

    def initialize(self) -> None:
        with self._session_lock:
            MediaBase.metadata.create_all(self.engine)

    def reset_all(self) -> None:
        with self._session_lock:
            with Session(self.engine) as session:
                for table in (
                    MediaProviderExecutionRow,
                    MediaArtifactRow,
                    MediaAttemptRow,
                    MediaJobDependencyRow,
                    MediaJobRow,
                    MediaEnvelopeRow,
                ):
                    session.execute(delete(table))
                session.commit()

    def register_envelope(self, envelope: MediaEnvelope) -> MediaEnvelope:
        validate_media_envelope(envelope)
        payload = envelope.model_dump(mode="json")
        with self._session_lock:
            with Session(self.engine) as session:
                by_id = session.get(MediaEnvelopeRow, envelope.envelope_id)
                by_key = session.scalar(
                    select(MediaEnvelopeRow).where(MediaEnvelopeRow.idempotency_key == envelope.idempotency_key)
                )
                existing = by_id or by_key
                if existing is not None:
                    if existing.envelope_id != envelope.envelope_id or existing.envelope_digest != envelope.digest:
                        raise MediaFoundationError("media envelope idempotency conflict")
                    if existing.payload != payload:
                        raise MediaFoundationError("media envelope payload changed for existing identity")
                    return MediaEnvelope.model_validate(existing.payload)
                session.add(
                    MediaEnvelopeRow(
                        envelope_id=envelope.envelope_id,
                        idempotency_key=envelope.idempotency_key,
                        crawl_id=envelope.crawl_id,
                        canonical_fingerprint=envelope.canonical_fingerprint,
                        envelope_digest=envelope.digest,
                        payload=payload,
                    )
                )
                session.commit()
        return envelope

    def get_envelope(self, envelope_id: str) -> MediaEnvelope | None:
        with self._session_lock:
            with Session(self.engine) as session:
                row = session.get(MediaEnvelopeRow, envelope_id)
                return MediaEnvelope.model_validate(row.payload) if row is not None else None

    def enqueue_job(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
        envelope_id: str | None = None,
        dependencies: Iterable[str] = (),
        provider_request: ProviderRequest | None = None,
        priority: int = 100,
        max_attempts: int = 3,
    ) -> MediaJob:
        if not job_type or len(job_type) > 80:
            raise MediaFoundationError("job_type must be a bounded non-empty identifier")
        if max_attempts < 1 or max_attempts > 100:
            raise MediaFoundationError("max_attempts must be between 1 and 100")
        dependency_ids = tuple(sorted(set(dependencies)))
        request_payload = provider_request.model_dump(mode="json") if provider_request else None
        spec = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "job_type": job_type,
            "envelope_id": envelope_id,
            "payload": payload,
            "dependencies": list(dependency_ids),
            "provider_request": request_payload,
            "priority": int(priority),
            "max_attempts": int(max_attempts),
        }
        spec_digest = payload_digest(spec)
        idempotency_key = payload_digest({"phase": PHASE, "job_spec": spec})
        job_id = _stable_id("media_job", idempotency_key)
        with self._session_lock:
            with Session(self.engine) as session:
                if envelope_id is not None and session.get(MediaEnvelopeRow, envelope_id) is None:
                    raise MediaFoundationError("media job references an unknown envelope")
                for dependency_id in dependency_ids:
                    if dependency_id == job_id:
                        raise MediaFoundationError("media job cannot depend on itself")
                    if session.get(MediaJobRow, dependency_id) is None:
                        raise MediaFoundationError("media job dependency does not exist")
                existing = session.get(MediaJobRow, job_id)
                if existing is None:
                    existing = session.scalar(
                        select(MediaJobRow).where(MediaJobRow.idempotency_key == idempotency_key)
                    )
                if existing is not None:
                    if existing.job_id != job_id or existing.spec_digest != spec_digest:
                        raise MediaFoundationError("media job idempotency conflict")
                    return self._job_model(session, existing)
                row = MediaJobRow(
                    job_id=job_id,
                    idempotency_key=idempotency_key,
                    spec_digest=spec_digest,
                    envelope_id=envelope_id,
                    job_type=job_type,
                    status=JobStatus.QUEUED.value,
                    priority=int(priority),
                    payload=payload,
                    provider_request=request_payload,
                    attempt_count=0,
                    max_attempts=int(max_attempts),
                    selected_provider_id=None,
                    last_reason_code=None,
                )
                session.add(row)
                for dependency_id in dependency_ids:
                    session.add(
                        MediaJobDependencyRow(
                            dependency_id=_stable_id("media_dependency", job_id, dependency_id),
                            job_id=job_id,
                            depends_on_job_id=dependency_id,
                        )
                    )
                session.commit()
                return self._job_model(session, row)

    @staticmethod
    def _dependencies(session: Session, job_id: str) -> tuple[str, ...]:
        values = session.scalars(
            select(MediaJobDependencyRow)
            .where(MediaJobDependencyRow.job_id == job_id)
            .order_by(MediaJobDependencyRow.depends_on_job_id)
        ).all()
        return tuple(row.depends_on_job_id for row in values)

    def _job_model(self, session: Session, row: MediaJobRow) -> MediaJob:
        return MediaJob(
            job_id=row.job_id,
            idempotency_key=row.idempotency_key,
            spec_digest=row.spec_digest,
            envelope_id=row.envelope_id,
            job_type=row.job_type,
            status=JobStatus(row.status),
            priority=row.priority,
            payload=dict(row.payload),
            provider_request=ProviderRequest.model_validate(row.provider_request) if row.provider_request else None,
            attempt_count=row.attempt_count,
            max_attempts=row.max_attempts,
            selected_provider_id=row.selected_provider_id,
            last_reason_code=row.last_reason_code,
            dependency_job_ids=self._dependencies(session, row.job_id),
        )

    def get_job(self, job_id: str) -> MediaJob | None:
        with self._session_lock:
            with Session(self.engine) as session:
                row = session.get(MediaJobRow, job_id)
                return self._job_model(session, row) if row is not None else None

    def list_jobs(self) -> tuple[MediaJob, ...]:
        with self._session_lock:
            with Session(self.engine) as session:
                rows = session.scalars(select(MediaJobRow).order_by(MediaJobRow.job_id)).all()
                return tuple(self._job_model(session, row) for row in rows)

    @staticmethod
    def _dependencies_completed(session: Session, job_id: str) -> bool:
        dependencies = session.scalars(
            select(MediaJobDependencyRow).where(MediaJobDependencyRow.job_id == job_id)
        ).all()
        for dependency in dependencies:
            row = session.get(MediaJobRow, dependency.depends_on_job_id)
            if row is None or row.status != JobStatus.COMPLETED.value:
                return False
        return True

    def claim_next(self, worker_id: str) -> JobLease | None:
        if not worker_id.strip():
            raise MediaFoundationError("worker_id must be non-empty")
        with self._session_lock:
            with Session(self.engine) as session:
                rows = session.scalars(
                    select(MediaJobRow)
                    .where(MediaJobRow.status.in_([JobStatus.QUEUED.value, JobStatus.RETRY.value]))
                    .order_by(MediaJobRow.priority.desc(), MediaJobRow.job_id)
                ).all()
                row = next((item for item in rows if self._dependencies_completed(session, item.job_id)), None)
                if row is None:
                    return None
                if row.attempt_count >= row.max_attempts:
                    row.status = JobStatus.FAILED.value
                    row.last_reason_code = "attempt_limit_reached"
                    session.commit()
                    return None
                row.attempt_count += 1
                row.status = JobStatus.RUNNING.value
                row.last_reason_code = None
                attempt_id = _stable_id("media_attempt", row.job_id, row.attempt_count)
                session.add(
                    MediaAttemptRow(
                        attempt_id=attempt_id,
                        job_id=row.job_id,
                        attempt_number=row.attempt_count,
                        worker_id=worker_id,
                        provider_id=row.selected_provider_id,
                        status="running",
                        reason_code=None,
                        resource_usage={},
                    )
                )
                session.commit()
                return JobLease(
                    job=self._job_model(session, row),
                    attempt_id=attempt_id,
                    attempt_number=row.attempt_count,
                    worker_id=worker_id,
                )

    @staticmethod
    def _running_attempt(session: Session, row: MediaJobRow) -> MediaAttemptRow:
        attempt_id = _stable_id("media_attempt", row.job_id, row.attempt_count)
        attempt = session.get(MediaAttemptRow, attempt_id)
        if attempt is None or attempt.status != "running":
            raise MediaFoundationError("running media job has no active attempt record")
        return attempt

    def complete_job(self, job_id: str, *, resource_usage: dict[str, Any] | None = None) -> MediaJob:
        with self._session_lock:
            with Session(self.engine) as session:
                row = session.get(MediaJobRow, job_id)
                if row is None or row.status != JobStatus.RUNNING.value:
                    raise MediaFoundationError("only a running media job can complete")
                attempt = self._running_attempt(session, row)
                attempt.status = "completed"
                attempt.resource_usage = resource_usage or {}
                row.status = JobStatus.COMPLETED.value
                row.last_reason_code = None
                session.commit()
                return self._job_model(session, row)

    def fail_job(
        self,
        job_id: str,
        *,
        reason_code: str,
        retryable: bool = True,
        resource_usage: dict[str, Any] | None = None,
    ) -> MediaJob:
        if not reason_code.strip():
            raise MediaFoundationError("failure reason_code must be non-empty")
        with self._session_lock:
            with Session(self.engine) as session:
                row = session.get(MediaJobRow, job_id)
                if row is None or row.status != JobStatus.RUNNING.value:
                    raise MediaFoundationError("only a running media job can fail")
                attempt = self._running_attempt(session, row)
                attempt.status = "failed"
                attempt.reason_code = reason_code
                attempt.resource_usage = resource_usage or {}
                row.last_reason_code = reason_code
                row.status = (
                    JobStatus.RETRY.value
                    if retryable and row.attempt_count < row.max_attempts
                    else JobStatus.FAILED.value
                )
                session.commit()
                return self._job_model(session, row)

    def hold_job(self, job_id: str, *, reason_code: str) -> MediaJob:
        if not reason_code.strip():
            raise MediaFoundationError("hold reason_code must be non-empty")
        with self._session_lock:
            with Session(self.engine) as session:
                row = session.get(MediaJobRow, job_id)
                if row is None or row.status not in {
                    JobStatus.QUEUED.value,
                    JobStatus.RETRY.value,
                    JobStatus.HELD.value,
                }:
                    raise MediaFoundationError("only queued/retry/held jobs can be held")
                row.status = JobStatus.HELD.value
                row.last_reason_code = reason_code
                session.commit()
                return self._job_model(session, row)

    def release_held(self, job_id: str) -> MediaJob:
        with self._session_lock:
            with Session(self.engine) as session:
                row = session.get(MediaJobRow, job_id)
                if row is None or row.status != JobStatus.HELD.value:
                    raise MediaFoundationError("only held jobs can be released")
                row.status = JobStatus.QUEUED.value
                row.last_reason_code = None
                session.commit()
                return self._job_model(session, row)

    def recover_interrupted_jobs(self, *, reason_code: str = "worker_restart") -> int:
        """Recover jobs left RUNNING by a process/machine restart without duplicating attempts."""
        recovered = 0
        with self._session_lock:
            with Session(self.engine) as session:
                rows = session.scalars(
                    select(MediaJobRow).where(MediaJobRow.status == JobStatus.RUNNING.value)
                ).all()
                for row in rows:
                    attempt = self._running_attempt(session, row)
                    attempt.status = "interrupted"
                    attempt.reason_code = reason_code
                    row.last_reason_code = reason_code
                    row.status = (
                        JobStatus.RETRY.value
                        if row.attempt_count < row.max_attempts
                        else JobStatus.FAILED.value
                    )
                    recovered += 1
                session.commit()
        return recovered

    def route_job(
        self,
        job_id: str,
        router: MediaProviderRouter,
        policy: ProviderPolicy | None = None,
        *,
        daily_paid_spend_microusd: int = 0,
    ) -> ProviderSelection:
        with self._session_lock:
            with Session(self.engine) as session:
                row = session.get(MediaJobRow, job_id)
                if row is None:
                    raise MediaFoundationError("media job does not exist")
                if row.provider_request is None:
                    raise MediaFoundationError("media job has no provider request")
                request = ProviderRequest.model_validate(row.provider_request)
                selection = router.select(
                    request,
                    policy,
                    daily_paid_spend_microusd=daily_paid_spend_microusd,
                )
                if selection.selected:
                    row.selected_provider_id = selection.provider_id
                    if row.status == JobStatus.HELD.value:
                        row.status = JobStatus.QUEUED.value
                    row.last_reason_code = None
                else:
                    if row.status in {JobStatus.QUEUED.value, JobStatus.RETRY.value, JobStatus.HELD.value}:
                        row.status = JobStatus.HELD.value
                    row.selected_provider_id = None
                    row.last_reason_code = selection.reason_code
                session.commit()
                return selection

    def record_artifact(
        self,
        *,
        job_id: str,
        artifact_kind: str,
        uri: str,
        digest: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        identity = _stable_id("media_artifact", job_id, artifact_kind, digest, uri)
        with self._session_lock:
            with Session(self.engine) as session:
                if session.get(MediaJobRow, job_id) is None:
                    raise MediaFoundationError("artifact references an unknown media job")
                row = session.get(MediaArtifactRow, identity)
                if row is None:
                    session.add(
                        MediaArtifactRow(
                            artifact_id=identity,
                            job_id=job_id,
                            artifact_kind=artifact_kind,
                            uri=uri,
                            digest=digest,
                            metadata_payload=metadata or {},
                            review_status="pending",
                            published=False,
                        )
                    )
                    session.commit()
                elif row.digest != digest or row.uri != uri:
                    raise MediaFoundationError("artifact identity conflict")
        return identity

    def record_provider_execution(
        self,
        *,
        job_id: str,
        attempt_id: str,
        provider_id: str,
        status: str,
        estimated_cost_microusd: int = 0,
        actual_cost_microusd: int = 0,
        estimated_gpu_ms: int = 0,
        actual_gpu_ms: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        for value in (estimated_cost_microusd, actual_cost_microusd, estimated_gpu_ms, actual_gpu_ms):
            if value < 0:
                raise MediaFoundationError("provider execution resources/costs cannot be negative")
        execution_id = _stable_id("media_execution", job_id, attempt_id, provider_id)
        body = {
            "job_id": job_id,
            "attempt_id": attempt_id,
            "provider_id": provider_id,
            "status": status,
            "estimated_cost_microusd": estimated_cost_microusd,
            "actual_cost_microusd": actual_cost_microusd,
            "estimated_gpu_ms": estimated_gpu_ms,
            "actual_gpu_ms": actual_gpu_ms,
            "metadata": metadata or {},
        }
        with self._session_lock:
            with Session(self.engine) as session:
                if session.get(MediaJobRow, job_id) is None or session.get(MediaAttemptRow, attempt_id) is None:
                    raise MediaFoundationError("provider execution lacks durable job/attempt provenance")
                existing = session.get(MediaProviderExecutionRow, execution_id)
                if existing is None:
                    session.add(
                        MediaProviderExecutionRow(
                            execution_id=execution_id,
                            job_id=job_id,
                            attempt_id=attempt_id,
                            provider_id=provider_id,
                            status=status,
                            estimated_cost_microusd=estimated_cost_microusd,
                            actual_cost_microusd=actual_cost_microusd,
                            estimated_gpu_ms=estimated_gpu_ms,
                            actual_gpu_ms=actual_gpu_ms,
                            metadata_payload=metadata or {},
                        )
                    )
                    session.commit()
                else:
                    existing_body = {
                        "job_id": existing.job_id,
                        "attempt_id": existing.attempt_id,
                        "provider_id": existing.provider_id,
                        "status": existing.status,
                        "estimated_cost_microusd": existing.estimated_cost_microusd,
                        "actual_cost_microusd": existing.actual_cost_microusd,
                        "estimated_gpu_ms": existing.estimated_gpu_ms,
                        "actual_gpu_ms": existing.actual_gpu_ms,
                        "metadata": existing.metadata_payload,
                    }
                    if payload_digest(existing_body) != payload_digest(body):
                        raise MediaFoundationError("provider execution identity conflict")
        return execution_id

    def snapshot(self) -> dict[str, Any]:
        """Deterministic semantic snapshot; excludes SQLite/runtime wall-clock details."""
        with self._session_lock:
            with Session(self.engine) as session:
                envelopes = [
                    {
                        "envelope_id": row.envelope_id,
                        "idempotency_key": row.idempotency_key,
                        "crawl_id": row.crawl_id,
                        "canonical_fingerprint": row.canonical_fingerprint,
                        "envelope_digest": row.envelope_digest,
                    }
                    for row in session.scalars(select(MediaEnvelopeRow).order_by(MediaEnvelopeRow.envelope_id)).all()
                ]
                jobs = [
                    self._job_model(session, row).model_dump(mode="json")
                    for row in session.scalars(select(MediaJobRow).order_by(MediaJobRow.job_id)).all()
                ]
                attempts = [
                    {
                        "attempt_id": row.attempt_id,
                        "job_id": row.job_id,
                        "attempt_number": row.attempt_number,
                        "worker_id": row.worker_id,
                        "provider_id": row.provider_id,
                        "status": row.status,
                        "reason_code": row.reason_code,
                        "resource_usage": row.resource_usage,
                    }
                    for row in session.scalars(select(MediaAttemptRow).order_by(MediaAttemptRow.attempt_id)).all()
                ]
                artifacts = [
                    {
                        "artifact_id": row.artifact_id,
                        "job_id": row.job_id,
                        "artifact_kind": row.artifact_kind,
                        "uri": row.uri,
                        "digest": row.digest,
                        "metadata": row.metadata_payload,
                        "review_status": row.review_status,
                        "published": row.published,
                    }
                    for row in session.scalars(select(MediaArtifactRow).order_by(MediaArtifactRow.artifact_id)).all()
                ]
                executions = [
                    {
                        "execution_id": row.execution_id,
                        "job_id": row.job_id,
                        "attempt_id": row.attempt_id,
                        "provider_id": row.provider_id,
                        "status": row.status,
                        "estimated_cost_microusd": row.estimated_cost_microusd,
                        "actual_cost_microusd": row.actual_cost_microusd,
                        "estimated_gpu_ms": row.estimated_gpu_ms,
                        "actual_gpu_ms": row.actual_gpu_ms,
                        "metadata": row.metadata_payload,
                    }
                    for row in session.scalars(
                        select(MediaProviderExecutionRow).order_by(MediaProviderExecutionRow.execution_id)
                    ).all()
                ]
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "authoritative": False,
            "canonical_owner": "deterministic_simulation",
            "presentation_can_mutate_simulation": False,
            "unreal_dependency": False,
            "required_cloud_api": False,
            "required_paid_provider": False,
            "envelopes": envelopes,
            "jobs": jobs,
            "attempts": attempts,
            "artifacts": artifacts,
            "provider_executions": executions,
        }
        return {**body, "digest": payload_digest(body)}


__all__ = [
    "PROTOCOL",
    "IMPLEMENTATION_VERSION",
    "PHASE",
    "ProviderKind",
    "JobStatus",
    "ProviderDescriptor",
    "ProviderPolicy",
    "ProviderRequest",
    "ProviderSelection",
    "MediaJob",
    "JobLease",
    "MediaFoundationError",
    "MediaProviderRouter",
    "MediaPersistence",
]
