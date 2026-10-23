"""Unattended local-first end-to-end promotion soak for Underreach Phase 30.5.12.

30.5.12 is the Phase 30.5 capstone. It composes already-accepted canonical and
media services into one unattended run: 20+ deterministic Delvers generate real
combat/social/progression Ledger history, the read-only media membrane exports
that truth, media-owned Chronicle/highlight/narrative/identity/image/audio/FFmpeg
systems build one vertical promotional story, a durable review queue receives the
finished MP4, and the static Underreach site rebuilds from media-owned state.

This module does not create a new gameplay authority. Canonical mutations are
performed only by accepted simulation/social services. All downstream media is
presentation-only. Unreal, cloud APIs, paid providers, and human intervention are
not required for the production path to reach pending human review.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .crawl_persistence import CrawlPersistence
from .runtime_checkpoint import canonical_json, payload_digest
from .underreach_brain_driven_descent import BrainDrivenDescentService
from .underreach_delver_chronicle_profile import (
    ChapterKind,
    ChronicleChapter,
    DelverChronicleProfileService,
    DelverProfile,
    validate_chapter,
    validate_profile,
)
from .underreach_ffmpeg_motion_story import AutomatedFfmpegMotionStoryService, MotionStoryPolicy
from .underreach_full_autonomous_descent import METADATA_KEY as AUTONOMOUS_METADATA_KEY
from .underreach_group_social_orchestration import (
    METADATA_KEY as GROUP_SOCIAL_METADATA_KEY,
    GroupSocialOrchestrationService,
    validate_group_social_orchestration,
)
from .underreach_headless_local_image_production import (
    DeterministicLocalPngProvider,
    HeadlessLocalImageProductionService,
    ImageProductionPolicy,
)
from .underreach_highlight_story_arc import HighlightStoryArcService, MediaHighlight
from .underreach_media_event_export import CanonicalMediaEventExporter, MediaEnvelope
from .underreach_media_foundation import JobStatus, MediaPersistence
from .underreach_media_website_blog import MediaWebsiteBlogService
from .underreach_narration_captions_audio import (
    DeterministicLocalWavProvider,
    NarrationCaptionsAudioService,
)
from .underreach_narrative_claim_verification import (
    ClaimSpec,
    ClaimType,
    NarrativeClaimVerificationService,
    NarrativeVerification,
    VerificationStatus,
)
from .underreach_presentation_identity import PresentationIdentityService, ReferenceKind


PROTOCOL = "underreach.unattended-promotion-soak.v1"
IMPLEMENTATION_VERSION = "30.5.12"
PHASE = "30.5"
REVIEW_JOB_TYPE = "underreach.review-queue.build"
REVIEW_QUEUE_SCHEMA = "underreach.review-queue.v1"


class UnattendedPromotionSoakError(ValueError):
    """Raised when the Phase 30.5 unattended acceptance contract is violated."""


class UnattendedPromotionSoakPolicy(BaseModel):
    """Bounded local acceptance policy for one complete unattended run."""

    model_config = ConfigDict(frozen=True)

    population_count: int = Field(default=20, ge=20, le=128)
    stratum_count: int = Field(default=3, ge=3, le=12)
    max_simulation_steps: int = Field(default=2000, ge=50, le=10000)
    required_social_events: int = Field(default=4, ge=4, le=16)
    portrait_width: int = Field(default=256, ge=64, le=1024)
    portrait_height: int = Field(default=256, ge=64, le=1024)
    scene_width: int = Field(default=360, ge=180, le=1080)
    scene_height: int = Field(default=640, ge=320, le=1920)
    promo_fps: int = Field(default=15, ge=10, le=30)
    promo_minimum_seconds: float = Field(default=6.0, ge=3.0, le=30.0)
    promo_maximum_seconds: float = Field(default=30.0, ge=6.0, le=90.0)

    @model_validator(mode="after")
    def validate_policy(self) -> "UnattendedPromotionSoakPolicy":
        if self.scene_width * 16 != self.scene_height * 9:
            raise ValueError("30.5.12 scene/promo resolution must be exact 9:16")
        if self.promo_minimum_seconds > self.promo_maximum_seconds:
            raise ValueError("promotion minimum duration cannot exceed maximum")
        return self

    @property
    def digest(self) -> str:
        return payload_digest(self.model_dump(mode="json"))


class ReviewQueueItem(BaseModel):
    """One finished promotional artifact awaiting a human publication decision."""

    model_config = ConfigDict(frozen=True)

    queue_item_id: str
    artifact_id: str
    source_job_id: str
    story_id: str
    artifact_kind: str
    uri: str
    digest: str
    source_event_ids: tuple[str, ...]
    review_status: str = "pending"
    published: bool = False
    review_ready: bool = True
    automatic_publication_allowed: bool = False
    canonical_authority: bool = False
    presentation_can_mutate_simulation: bool = False
    item_digest: str


class UnattendedPromotionSoakResult(BaseModel):
    """Deterministic semantic result of one complete 30.5.12 soak."""

    model_config = ConfigDict(frozen=True)

    protocol: str = PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    phase: str = PHASE
    seed: str
    policy_digest: str
    canonical: dict[str, Any]
    event_provenance: dict[str, Any]
    media: dict[str, Any]
    chronicle: dict[str, Any]
    verification: dict[str, Any]
    presentation: dict[str, Any]
    audio: dict[str, Any]
    promotion: dict[str, Any]
    review_queue: dict[str, Any]
    website: dict[str, Any]
    restart: dict[str, Any]
    idempotency: dict[str, Any]
    mandatory_zeroes: dict[str, bool]
    authority_contract: dict[str, Any]
    digest: str


def _stable_id(prefix: str, *parts: object) -> str:
    payload = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(payload.encode('utf-8')).hexdigest()[:24]}"


def _body_digest(model: BaseModel) -> str:
    return payload_digest(model.model_dump(mode="json", exclude={"digest"}))


def _safe_relative_uri(uri: str) -> PurePosixPath:
    value = PurePosixPath(uri)
    if value.is_absolute() or ".." in value.parts or "://" in uri:
        raise UnattendedPromotionSoakError("review-queue media URI must be a safe relative path")
    return value


def validate_review_queue_item(item: ReviewQueueItem) -> bool:
    _safe_relative_uri(item.uri)
    if item.artifact_kind != "video/mp4" or not item.source_event_ids:
        raise UnattendedPromotionSoakError("review queue requires a provenance-bearing MP4")
    if item.review_status != "pending" or item.published or not item.review_ready:
        raise UnattendedPromotionSoakError("review queue item escaped pending-human-review state")
    if item.automatic_publication_allowed or item.canonical_authority or item.presentation_can_mutate_simulation:
        raise UnattendedPromotionSoakError("review queue gained forbidden publication/canonical authority")
    expected_id = _stable_id("review_queue_item", item.artifact_id, item.digest, *item.source_event_ids)
    if item.queue_item_id != expected_id:
        raise UnattendedPromotionSoakError("review queue deterministic identity mismatch")
    expected_digest = payload_digest(item.model_dump(mode="json", exclude={"item_digest"}))
    if item.item_digest != expected_digest:
        raise UnattendedPromotionSoakError("review queue item digest mismatch")
    return True


def validate_soak_result(result: UnattendedPromotionSoakResult) -> bool:
    if result.protocol != PROTOCOL or result.implementation_version != IMPLEMENTATION_VERSION or result.phase != PHASE:
        raise UnattendedPromotionSoakError("30.5.12 protocol/version mismatch")
    if int(result.canonical.get("population_count", 0)) < 20:
        raise UnattendedPromotionSoakError("unattended soak lost the 20+ Delver acceptance gate")
    if result.canonical.get("outcome") != "completed":
        raise UnattendedPromotionSoakError("canonical unattended crawl did not complete")
    if not result.canonical.get("unchanged_during_downstream_media"):
        raise UnattendedPromotionSoakError("downstream media changed canonical truth")
    if not result.canonical.get("bootstrap_export_unchanged"):
        raise UnattendedPromotionSoakError("bootstrap media export changed canonical truth")
    for key in ("combat_event_ids", "social_event_ids", "progression_event_ids"):
        if not result.event_provenance.get(key):
            raise UnattendedPromotionSoakError(f"unattended soak lacks real {key} provenance")
    promises = result.event_provenance.get("promise_violation_event_ids") or ()
    betrayal_event_id = result.event_provenance.get("betrayal_event_id")
    composite_sources = set(result.event_provenance.get("composite_source_event_ids") or ())
    if len(promises) < 4 or not betrayal_event_id:
        raise UnattendedPromotionSoakError("canonical social proof lost reinforced promises or evidence-backed betrayal")
    if not set(promises).issubset(composite_sources) or betrayal_event_id not in composite_sources:
        raise UnattendedPromotionSoakError("featured media composite lost required canonical social provenance")
    components = result.event_provenance.get("composite_highlight_components") or {}
    if (
        int(components.get("danger", 0)) < 10
        or int(components.get("social_stakes", 0)) < 20
        or int(components.get("continuity", 0)) < 15
        or int(components.get("visual_potential", 0)) < 5
        or int(components.get("total", 0)) < 50
    ):
        raise UnattendedPromotionSoakError("featured highlight lost its deterministic 50-point canonical floor")
    if result.event_provenance.get("composite_foreign_actor_ids"):
        raise UnattendedPromotionSoakError("featured media composite contains non-Delver actor IDs")
    encounter_retreats = set(result.event_provenance.get("encounter_retreat_event_ids") or ())
    terminal_media = set(result.event_provenance.get("terminal_media_event_ids") or ())
    if encounter_retreats.intersection(terminal_media):
        raise UnattendedPromotionSoakError("encounter retreat leaked into terminal Chronicle export")
    if int(result.media.get("profile_count", 0)) < 20:
        raise UnattendedPromotionSoakError("media-owned Delver directory contains fewer than 20 profiles")
    if int(result.chronicle.get("chapter_count", 0)) < 1 or int(result.chronicle.get("highlight_count", 0)) < 1:
        raise UnattendedPromotionSoakError("unattended soak did not produce Chronicle + highlight content")
    if not result.verification.get("review_ready"):
        raise UnattendedPromotionSoakError("unattended Chronicle narrative did not pass deterministic verification")
    if result.promotion.get("status") != JobStatus.COMPLETED.value:
        raise UnattendedPromotionSoakError("vertical motion story did not complete")
    width = int(result.promotion.get("width", 0))
    height = int(result.promotion.get("height", 0))
    if width <= 0 or height <= 0 or width * 16 != height * 9:
        raise UnattendedPromotionSoakError("promotion output lost exact 9:16 geometry")
    if result.review_queue.get("review_status") != "pending" or result.review_queue.get("published"):
        raise UnattendedPromotionSoakError("finished promotion did not stop at human review")
    if int(result.website.get("profile_count", 0)) < 20 or not result.website.get("static_only"):
        raise UnattendedPromotionSoakError("static media website acceptance gate failed")
    if not result.restart.get("same_scene_job") or int(result.restart.get("scene_attempt_count", 0)) != 2:
        raise UnattendedPromotionSoakError("injected media-worker restart did not recover the same scene job")
    if not result.idempotency.get("scene_completed_reenqueue_reused_job"):
        raise UnattendedPromotionSoakError("completed scene re-enqueue was not idempotent")
    if not result.idempotency.get("review_queue_completed_reenqueue_reused_job"):
        raise UnattendedPromotionSoakError("review queue re-enqueue was not idempotent")
    if not result.idempotency.get("envelope_reregistration_stable"):
        raise UnattendedPromotionSoakError("MediaEnvelope restart/idempotency contract changed")
    if not result.mandatory_zeroes or not all(result.mandatory_zeroes.values()):
        raise UnattendedPromotionSoakError("one or more Phase 30.5 mandatory zeroes failed")
    if result.digest != _body_digest(result):
        raise UnattendedPromotionSoakError("unattended soak digest mismatch")
    return True


def _canonical_snapshot(persistence: CrawlPersistence, descent) -> dict[str, Any]:
    ledger = [item.model_dump(mode="json") for item in persistence.replay_events(descent.id)]
    body = {
        "state": descent.model_dump(mode="json"),
        "fingerprint": descent.fingerprint(),
        "history_event_ids": list(descent.history_event_ids),
        "ledger": ledger,
    }
    return {
        "state_json": canonical_json(body["state"]),
        "fingerprint": body["fingerprint"],
        "history_event_ids": body["history_event_ids"],
        "history_digest": payload_digest(body["history_event_ids"]),
        "ledger_digest": payload_digest(ledger),
        "state_digest": payload_digest(body["state"]),
        "event_count": len(ledger),
    }


def _same_canonical(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left["state_json"] == right["state_json"]
        and left["fingerprint"] == right["fingerprint"]
        and left["history_event_ids"] == right["history_event_ids"]
        and left["history_digest"] == right["history_digest"]
        and left["ledger_digest"] == right["ledger_digest"]
        and left["state_digest"] == right["state_digest"]
    )


def _artifact(media: MediaPersistence, artifact_id: str) -> dict[str, Any]:
    matches = [item for item in media.snapshot()["artifacts"] if item["artifact_id"] == artifact_id]
    if len(matches) != 1:
        raise UnattendedPromotionSoakError("expected exactly one persisted media artifact")
    return matches[0]


def _event_by_id(events, event_id: str):
    matches = [event for event in events if event.id == event_id]
    if len(matches) != 1:
        raise UnattendedPromotionSoakError("canonical event provenance disappeared")
    return matches[0]


def _initial_social_pair(descent) -> tuple[str, str]:
    """Choose a deterministic active/co-located pair before gameplay can split or kill them."""
    by_location: dict[tuple[int, str], list[str]] = {}
    for npc_id, participant in sorted(descent.participants.items()):
        if participant.status.value != "active" or participant.current_location_id is None:
            continue
        key = (int(participant.current_floor), str(participant.current_location_id))
        by_location.setdefault(key, []).append(npc_id)
    for key in sorted(by_location):
        members = sorted(by_location[key])
        if len(members) >= 2:
            return members[0], members[1]
    raise UnattendedPromotionSoakError("unattended soak could not resolve an active co-located social pair")


def _media_services(media: MediaPersistence):
    highlights = HighlightStoryArcService(media)
    highlights.initialize()
    chronicle = DelverChronicleProfileService(media, highlights=highlights)
    chronicle.initialize()
    verifier = NarrativeClaimVerificationService(media, chronicle=chronicle)
    verifier.initialize()
    identities = PresentationIdentityService(media, chronicle=chronicle)
    identities.initialize()
    return highlights, chronicle, verifier, identities


def _review_item(media: MediaPersistence, motion_artifact_id: str, source_event_ids: tuple[str, ...], story_id: str) -> ReviewQueueItem:
    artifact = _artifact(media, motion_artifact_id)
    if artifact["artifact_kind"] != "video/mp4":
        raise UnattendedPromotionSoakError("review queue source must be a completed MP4")
    if artifact["review_status"] != "pending" or bool(artifact["published"]):
        raise UnattendedPromotionSoakError("review queue source must remain pending/unpublished")
    normalized = tuple(sorted(set(source_event_ids)))
    queue_item_id = _stable_id("review_queue_item", artifact["artifact_id"], artifact["digest"], *normalized)
    body = {
        "queue_item_id": queue_item_id,
        "artifact_id": artifact["artifact_id"],
        "source_job_id": artifact["job_id"],
        "story_id": story_id,
        "artifact_kind": artifact["artifact_kind"],
        "uri": artifact["uri"],
        "digest": artifact["digest"],
        "source_event_ids": list(normalized),
        "review_status": "pending",
        "published": False,
        "review_ready": True,
        "automatic_publication_allowed": False,
        "canonical_authority": False,
        "presentation_can_mutate_simulation": False,
    }
    value = ReviewQueueItem.model_validate({**body, "item_digest": payload_digest(body)})
    validate_review_queue_item(value)
    return value


def _enqueue_review_queue(media: MediaPersistence, item: ReviewQueueItem, *, priority: int = 70):
    validate_review_queue_item(item)
    return media.enqueue_job(
        job_type=REVIEW_JOB_TYPE,
        payload={
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "schema": REVIEW_QUEUE_SCHEMA,
            "item": item.model_dump(mode="json"),
        },
        dependencies=(item.source_job_id,),
        priority=priority,
        max_attempts=2,
    )


def _run_review_queue(media: MediaPersistence, media_root: Path, expected_job_id: str):
    lease = media.claim_next("underreach-review-queue-worker")
    if lease is None or lease.job.job_id != expected_job_id or lease.job.job_type != REVIEW_JOB_TYPE:
        raise UnattendedPromotionSoakError("review queue worker could not claim expected durable job")
    payload = lease.job.payload
    if payload.get("protocol") != PROTOCOL or payload.get("schema") != REVIEW_QUEUE_SCHEMA:
        raise UnattendedPromotionSoakError("review queue durable payload protocol changed")
    item = ReviewQueueItem.model_validate(payload.get("item"))
    validate_review_queue_item(item)
    relative = (Path("review-queue") / f"{item.queue_item_id}.json").as_posix()
    body = {
        "schema": REVIEW_QUEUE_SCHEMA,
        "phase": PHASE,
        "queue_item": item.model_dump(mode="json"),
        "source_motion_story_job_id": item.source_job_id,
        "human_review_required_before_publication": True,
        "automatic_publication_allowed": False,
        "canonical_authority": False,
        "presentation_can_mutate_simulation": False,
    }
    data = (canonical_json(body) + "\n").encode("utf-8")
    path = media_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)
    digest = sha256(data).hexdigest()
    artifact_id = media.record_artifact(
        job_id=lease.job.job_id,
        artifact_kind="application/json",
        uri=relative,
        digest=digest,
        metadata={
            "queue_item_id": item.queue_item_id,
            "motion_story_artifact_id": item.artifact_id,
            "review_status": "pending",
            "presentation_only": True,
        },
    )
    completed = media.complete_job(
        lease.job.job_id,
        resource_usage={"queue_item_count": 1, "human_review_required": True},
    )
    return completed, artifact_id, relative, digest


class UnattendedPromotionSoakService:
    """Compose accepted Phase 30.5 systems into one unattended local run."""

    def __init__(
        self,
        *,
        canonical_database_url: str,
        media_database_url: str,
        media_root: str | Path,
        seed: str,
        policy: UnattendedPromotionSoakPolicy | None = None,
        ffmpeg_path: str | Path | None = None,
        ffprobe_path: str | Path | None = None,
    ) -> None:
        self.canonical_database_url = canonical_database_url
        self.media_database_url = media_database_url
        self.media_root = Path(media_root)
        self.seed = seed
        self.policy = policy or UnattendedPromotionSoakPolicy()
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path

    def _canonical_run(self, media: MediaPersistence, chronicle: DelverChronicleProfileService, highlights: HighlightStoryArcService):
        canonical = CrawlPersistence(self.canonical_database_url)
        canonical.initialize()
        brain = BrainDrivenDescentService(canonical)
        ids = [f"descender_{index:03d}" for index in range(self.policy.population_count)]
        descent = brain.create(seed=self.seed, descender_ids=ids, stratum_count=self.policy.stratum_count)
        brain.start(descent)
        group = GroupSocialOrchestrationService(canonical, brain=brain)
        group.initialize(descent)

        exporter = CanonicalMediaEventExporter(canonical)
        bootstrap_event_id = descent.modifiers[GROUP_SOCIAL_METADATA_KEY]["initialized_event_id"]
        bootstrap_before = _canonical_snapshot(canonical, descent)
        bootstrap = exporter.export_event(descent, bootstrap_event_id)
        bootstrap_after = _canonical_snapshot(canonical, descent)
        bootstrap_unchanged = _same_canonical(bootstrap_before, bootstrap_after)
        media.register_envelope(bootstrap)
        highlights.evaluate(bootstrap)
        chronicle.process(bootstrap)

        # Build one deterministic canonical social thread before gameplay can
        # split or eliminate the pair. The party is created only through the
        # accepted 30C.3 offer/accept membrane and 30C.4 materialization.
        source, target = _initial_social_pair(descent)
        social_pair_ids = (source, target)
        offer = group.social.execute(
            descent,
            group.social.propose(
                descent,
                source,
                "recruit",
                target_descender_id=target,
                provider_id="underreach-30.5.12-soak",
            ),
        )
        if not offer.executed or offer.resolved_offer_id is None:
            raise UnattendedPromotionSoakError("canonical social proof could not create recruitment offer")
        accepted = group.social.execute(
            descent,
            group.social.propose(
                descent,
                target,
                "accept_recruitment",
                target_descender_id=source,
                recruitment_offer_id=offer.resolved_offer_id,
                provider_id="underreach-30.5.12-soak",
            ),
        )
        if not accepted.executed:
            raise UnattendedPromotionSoakError("canonical social proof recruitment was not accepted")
        party = group.parties.form_from_accepted_recruitment(descent, offer.resolved_offer_id)
        social_party_id = party.party_id

        promise_violation_event_ids: list[str] = []
        for sequence in range(1, self.policy.required_social_events + 1):
            source_state = descent.participants[source]
            target_state = descent.participants[target]
            if source_state.status.value != "active" or target_state.status.value != "active":
                raise UnattendedPromotionSoakError("initial social proof pair unexpectedly left active state")
            if source_state.current_location_id != target_state.current_location_id:
                raise UnattendedPromotionSoakError("initial social proof pair unexpectedly stopped being co-located")
            if source_state.current_party_id != social_party_id or target_state.current_party_id != social_party_id:
                raise UnattendedPromotionSoakError("initial social proof pair lost its accepted party before conflict")
            event = group.memory.lifecycle.record_event(
                descent,
                "PROMISE_VIOLATED",
                "A canonical promise violation reinforced an unattended social conflict.",
                actor_ids=[target, source],
                location_id=source_state.current_location_id,
                data={
                    "state_changes": {"promotion_soak_social_history": sequence},
                    "soak_social_sequence": sequence,
                },
            )
            group.memory.lifecycle.save(descent)
            processed = group.memory.process_event(descent, event)
            if not processed.processed:
                raise UnattendedPromotionSoakError("accepted social-memory service did not process soak social event")
            promise_violation_event_ids.append(event.id)

        betrayal = group.conflict.execute(
            descent,
            group.conflict.propose(
                descent,
                source,
                target,
                "betray_party",
                incentive_code="revenge",
                incentive_strength=1.0,
                provider_id="underreach-30.5.12-soak",
            ),
        )
        if not betrayal.accepted or not betrayal.executed or betrayal.source_event_id is None:
            raise UnattendedPromotionSoakError(
                f"evidence-backed 30C.5 betrayal did not execute ({betrayal.reason_code})"
            )
        betrayal_event_id = betrayal.source_event_id
        social_event_ids = [*promise_violation_event_ids, betrayal_event_id]

        executed = 0
        while executed < self.policy.max_simulation_steps and descent.modifiers["_brain_driven_descent"]["run_outcome"] == "running":
            group.step(descent)
            if descent.modifiers["_brain_driven_descent"]["run_outcome"] != "running":
                break
            brain.step(descent)
            executed += 1

        if descent.modifiers["_brain_driven_descent"]["run_outcome"] == "running":
            raise UnattendedPromotionSoakError("canonical unattended crawl hit configured step limit")
        if descent.modifiers["_brain_driven_descent"]["run_outcome"] != "completed":
            raise UnattendedPromotionSoakError("canonical unattended crawl did not reach completed outcome")
        validate_group_social_orchestration(descent)

        events = canonical.replay_events(descent.id)
        by_type: Counter[str] = Counter(event.event_type for event in events)
        combat_events = [
            event.id
            for event in events
            if any(marker in event.event_type for marker in ("COMBAT_", "CRAWLER_INJURED", "CRAWLER_DAMAGED", "ENEMY_DEFEATED"))
        ]
        encounter_retreat_events = [event.id for event in events if event.event_type == "CRAWLER_RETREATED"]
        progression_events = [
            event.id
            for event in events
            if event.event_type in {"FLOOR_COMPLETED", "STRATUM_ADVANCED", "CRAWLER_ADVANCED", "ITEM_ACQUIRED"}
        ]
        if not combat_events:
            raise UnattendedPromotionSoakError("meaningful unattended crawl produced no canonical combat events")
        floor_events = [event.id for event in events if event.event_type == "FLOOR_COMPLETED"]
        if not floor_events:
            raise UnattendedPromotionSoakError("meaningful unattended crawl produced no canonical floor progression")
        if len(promise_violation_event_ids) < self.policy.required_social_events:
            raise UnattendedPromotionSoakError("required canonical social history was not completed")

        return {
            "canonical": canonical,
            "brain": brain,
            "group": group,
            "descent": descent,
            "ids": ids,
            "events": events,
            "event_type_counts": dict(sorted(by_type.items())),
            "bootstrap_envelope": bootstrap,
            "bootstrap_export_unchanged": bootstrap_unchanged,
            "social_pair_ids": social_pair_ids,
            "social_party_id": social_party_id,
            "recruitment_offer_id": offer.resolved_offer_id,
            "promise_violation_event_ids": tuple(promise_violation_event_ids),
            "betrayal_event_id": betrayal_event_id,
            "betrayal_conflict_score": betrayal.conflict_score,
            "social_event_ids": tuple(social_event_ids),
            "combat_event_ids": tuple(combat_events),
            "encounter_retreat_event_ids": tuple(encounter_retreat_events),
            "progression_event_ids": tuple(progression_events),
            "floor_event_ids": tuple(floor_events),
            "simulation_steps": executed,
        }

    def _export_final_media(self, canonical_stack: dict[str, Any], media: MediaPersistence, highlights: HighlightStoryArcService, chronicle: DelverChronicleProfileService):
        canonical = canonical_stack["canonical"]
        descent = canonical_stack["descent"]
        exporter = CanonicalMediaEventExporter(canonical)
        events = canonical_stack["events"]
        history_position = {event_id: index for index, event_id in enumerate(descent.history_event_ids)}
        delver_ids = set(canonical_stack["ids"])

        source_ids: list[str] = list(canonical_stack["social_event_ids"])
        combat_candidates = [
            event.id
            for event in events
            if event.event_type in {"COMBAT_STARTED", "COMBAT_ENDED"}
            and set(event.actor_ids).issubset(delver_ids)
        ]
        if not combat_candidates:
            raise UnattendedPromotionSoakError("canonical combat existed but no crawler-only combat event was exportable")
        source_ids.extend(combat_candidates[:8])
        item_candidates = [
            event.id
            for event in events
            if event.event_type in {"ITEM_ACQUIRED", "CRAWLER_ADVANCED"}
            and set(event.actor_ids).issubset(delver_ids)
        ]
        source_ids.extend(item_candidates[:4])
        source_ids.extend(list(canonical_stack["floor_event_ids"])[:2])
        source_ids = sorted(set(source_ids), key=lambda event_id: history_position[event_id])[:32]

        selected_events = [_event_by_id(events, event_id) for event_id in source_ids]
        foreign_source_actors = sorted(
            {
                actor_id
                for event in selected_events
                for actor_id in event.actor_ids
                if actor_id not in delver_ids
            }
        )
        if foreign_source_actors:
            raise UnattendedPromotionSoakError("featured media source selection contains non-Delver actors")

        # 30.5.4 treats any CRAWLER_RETREATED envelope as terminal. Combat uses
        # that event for encounter-local retreat without ending participation,
        # so only actual death/elimination events may enter terminal biography export.
        terminal_ids = [
            event.id
            for event in events
            if event.event_type in {"CRAWLER_DIED", "CRAWLER_ELIMINATED"}
        ]
        if set(terminal_ids).intersection(canonical_stack["encounter_retreat_event_ids"]):
            raise UnattendedPromotionSoakError("encounter retreat was selected for terminal Chronicle export")
        individual_ids = list(canonical_stack["social_event_ids"]) + terminal_ids
        envelopes: list[MediaEnvelope] = []
        for event_id in individual_ids:
            envelope = exporter.export_event(descent, event_id)
            media.register_envelope(envelope)
            highlights.evaluate(envelope)
            chronicle.process(envelope)
            envelopes.append(envelope)

        composite = exporter.export_events(descent, source_ids)
        composite_foreign_actor_ids = sorted(set(composite.delver_ids) - delver_ids)
        if composite_foreign_actor_ids:
            raise UnattendedPromotionSoakError("featured composite exported a non-Delver actor as a Delver")
        media.register_envelope(composite)
        evaluation = highlights.evaluate(composite)
        score = evaluation.score
        if score.danger < 10 or score.social_stakes < 20 or score.continuity < 15 or score.visual_potential < 5:
            raise UnattendedPromotionSoakError(
                "real composite lost deterministic combat/betrayal/memory/visual highlight floor"
            )
        if score.total < 50:
            raise UnattendedPromotionSoakError("real composite media package fell below guaranteed Chronicle threshold")
        chronicle.process(composite)
        envelopes.append(composite)
        if not evaluation.selected or evaluation.highlight_id is None:
            raise UnattendedPromotionSoakError(
                f"real composite media package did not clear Chronicle highlight threshold (score={evaluation.score.total})"
            )
        highlight = highlights.get_highlight(evaluation.highlight_id)
        if highlight is None:
            raise UnattendedPromotionSoakError("selected composite highlight disappeared from media database")
        return tuple(envelopes), composite, highlight, evaluation, tuple(terminal_ids)

    def _featured(self, chronicle: DelverChronicleProfileService, highlight: MediaHighlight):
        profile_by_delver = {item.delver_id: item for item in chronicle.list_profiles()}
        candidates: list[tuple[DelverProfile, ChronicleChapter]] = []
        chapter_by_id = {item.chapter_id: item for item in chronicle.list_chapters()}
        for delver_id in highlight.delver_ids:
            profile = profile_by_delver.get(delver_id)
            if profile is None:
                continue
            for chapter_id in profile.chapter_ids:
                chapter = chapter_by_id.get(chapter_id)
                if chapter is not None and chapter.highlight_id == highlight.highlight_id:
                    candidates.append((profile, chapter))
        if not candidates:
            for profile in chronicle.list_profiles():
                for chapter_id in profile.chapter_ids:
                    chapter = chapter_by_id.get(chapter_id)
                    if chapter is not None and chapter.chapter_kind in {ChapterKind.HIGHLIGHT, ChapterKind.QUIET_RECAP}:
                        candidates.append((profile, chapter))
        if not candidates:
            raise UnattendedPromotionSoakError("media soak produced no usable featured Chronicle chapter")
        candidates.sort(key=lambda item: (item[1].canonical_tick, item[0].delver_id, item[1].chapter_id), reverse=True)
        profile, chapter = candidates[0]
        validate_profile(profile)
        validate_chapter(chapter)
        return profile, chapter

    def _verified_narrative(
        self,
        media: MediaPersistence,
        verifier: NarrativeClaimVerificationService,
        chapter: ChronicleChapter,
    ) -> tuple[NarrativeVerification, str, str]:
        facts = []
        allowed = set(chapter.allowed_fact_ids)
        for envelope_id in chapter.source_envelope_ids:
            envelope = media.get_envelope(envelope_id)
            if envelope is None:
                raise UnattendedPromotionSoakError("featured Chronicle lost source MediaEnvelope")
            facts.extend(fact for fact in envelope.allowed_facts if fact.fact_id in allowed)
        preferred = [fact for fact in facts if fact.predicate == "event_type"]
        if not preferred:
            raise UnattendedPromotionSoakError("featured Chronicle has no event_type allowed fact for deterministic writer")
        fact = sorted(preferred, key=lambda item: (item.source_event_ids, item.fact_id))[0]
        prose = f"Canonical event {fact.value} occurred during the unattended Underreach descent."
        draft = verifier.register_draft(
            chapter_id=chapter.chapter_id,
            prose=prose,
            writer_provider_id="deterministic_allowed_fact_writer",
            writer_provider_local=True,
            writer_provider_paid=False,
        )
        claim = ClaimSpec(
            claim_type=ClaimType.FACTUAL,
            sentence_index=0,
            subject=fact.subject,
            predicate=fact.predicate,
            target_or_value=fact.value,
            supporting_allowed_fact_ids=(fact.fact_id,),
            confidence=1.0,
        )
        manifest = verifier.register_manifest(draft_id=draft.draft_id, claim_specs=(claim,))
        verification = verifier.verify(manifest.manifest_id)
        if verification.status != VerificationStatus.REVIEW_READY or not verification.review_ready:
            raise UnattendedPromotionSoakError("deterministic allowed-fact narrative did not become REVIEW_READY")
        return verification, draft.draft_id, manifest.manifest_id

    def run(self) -> UnattendedPromotionSoakResult:
        self.media_root.mkdir(parents=True, exist_ok=True)
        media = MediaPersistence(self.media_database_url)
        media.initialize()
        highlights, chronicle, verifier, identities = _media_services(media)

        canonical_stack = self._canonical_run(media, chronicle, highlights)
        canonical_before_media = _canonical_snapshot(canonical_stack["canonical"], canonical_stack["descent"])

        envelopes, composite, highlight, evaluation, terminal_media_event_ids = self._export_final_media(
            canonical_stack, media, highlights, chronicle
        )
        envelope_reregistration_stable = all(media.register_envelope(item) == item for item in envelopes)
        profiles = chronicle.list_profiles()
        if len(profiles) < self.policy.population_count:
            raise UnattendedPromotionSoakError("media directory did not retain the full unattended Delver roster")
        profile, chapter = self._featured(chronicle, highlight)
        verification, draft_id, manifest_id = self._verified_narrative(media, verifier, chapter)

        identity_state = identities.ensure_identity(profile)
        image_policy = ImageProductionPolicy(
            default_width=self.policy.portrait_width,
            default_height=self.policy.portrait_height,
            scene_width=self.policy.scene_width,
            scene_height=self.policy.scene_height,
            max_pixels=max(
                self.policy.portrait_width * self.policy.portrait_height,
                self.policy.scene_width * self.policy.scene_height,
            ),
        )
        image_service = HeadlessLocalImageProductionService(
            media,
            identities=identities,
            providers=[DeterministicLocalPngProvider()],
            output_root=self.media_root,
            policy=image_policy,
        )
        image_service.initialize()

        portrait_spec = image_service.plan_reference(
            profile,
            ReferenceKind.PORTRAIT,
            width=self.policy.portrait_width,
            height=self.policy.portrait_height,
        )
        portrait_job = image_service.enqueue(portrait_spec, priority=130)
        portrait_result = image_service.run_next(worker_id="underreach-soak-portrait-worker")
        if portrait_result is None or portrait_result.status != JobStatus.COMPLETED or portrait_result.artifact_id is None:
            raise UnattendedPromotionSoakError("local portrait stage did not complete")

        scene_spec = image_service.plan_scene(
            profile,
            chapter,
            reference_artifact_ids=(portrait_result.artifact_id,),
            width=self.policy.scene_width,
            height=self.policy.scene_height,
        )
        scene_job = image_service.enqueue(scene_spec, priority=120)
        crashed = media.claim_next("injected-30.5.12-image-crash")
        if crashed is None or crashed.job.job_id != scene_job.job_id:
            raise UnattendedPromotionSoakError("could not inject expected scene-worker crash")
        media.engine.dispose()

        reopened_media = MediaPersistence(self.media_database_url)
        reopened_media.initialize()
        recovered_jobs = reopened_media.recover_interrupted_jobs(reason_code="30.5.12_injected_restart")
        if recovered_jobs != 1:
            raise UnattendedPromotionSoakError("injected restart did not recover exactly one media job")
        media = reopened_media
        highlights, chronicle, verifier, identities = _media_services(media)
        profile = chronicle.get_profile(profile.crawl_id, profile.delver_id)
        if profile is None:
            raise UnattendedPromotionSoakError("featured profile disappeared after media restart")
        chapter_matches = [item for item in chronicle.list_chapters(crawl_id=profile.crawl_id, delver_id=profile.delver_id) if item.chapter_id == chapter.chapter_id]
        if len(chapter_matches) != 1:
            raise UnattendedPromotionSoakError("featured Chronicle chapter disappeared after media restart")
        chapter = chapter_matches[0]

        image_service = HeadlessLocalImageProductionService(
            media,
            identities=identities,
            providers=[DeterministicLocalPngProvider()],
            output_root=self.media_root,
            policy=image_policy,
        )
        image_service.initialize()
        scene_result = image_service.run_next(worker_id="underreach-soak-scene-worker")
        if scene_result is None or scene_result.status != JobStatus.COMPLETED or scene_result.artifact_id is None:
            raise UnattendedPromotionSoakError("recovered scene image did not complete")
        final_scene_job = media.get_job(scene_job.job_id)
        if final_scene_job is None or final_scene_job.attempt_count != 2:
            raise UnattendedPromotionSoakError("scene restart did not complete on attempt 2")
        scene_snapshot_before_repeat = image_service.snapshot()
        repeated_scene = image_service.enqueue(scene_spec, priority=120)
        scene_snapshot_after_repeat = image_service.snapshot()
        scene_idempotent = (
            repeated_scene.job_id == scene_job.job_id
            and repeated_scene.status == JobStatus.COMPLETED
            and scene_snapshot_before_repeat == scene_snapshot_after_repeat
        )

        audio_service = NarrationCaptionsAudioService(
            media,
            verifier=verifier,
            providers=[DeterministicLocalWavProvider()],
            output_root=self.media_root,
        )
        audio_service.initialize()
        audio_spec = audio_service.plan(verification.verification_id)
        package_job, voice_job = audio_service.enqueue(audio_spec, package_priority=110, voice_priority=100)
        package_result = audio_service.run_next(worker_id="underreach-soak-caption-worker")
        if package_result is None or package_result.package_status != JobStatus.COMPLETED or not package_result.caption_only_ready:
            raise UnattendedPromotionSoakError("caption-first narration package did not complete")
        voice_result = audio_service.run_next(worker_id="underreach-soak-voice-worker")
        if voice_job is None or voice_result is None or voice_result.voice_status != JobStatus.COMPLETED:
            raise UnattendedPromotionSoakError("local deterministic voice stage did not complete")

        motion_policy = MotionStoryPolicy(
            width=self.policy.scene_width,
            height=self.policy.scene_height,
            fps=self.policy.promo_fps,
            minimum_duration_seconds=self.policy.promo_minimum_seconds,
            maximum_duration_seconds=self.policy.promo_maximum_seconds,
            target_shot_seconds=2.0,
            minimum_shots=3,
            maximum_shots=5,
            transition_ms=250,
            preset="ultrafast",
            crf=28,
            max_attempts=2,
            ffmpeg_timeout_seconds=240,
        )
        motion = AutomatedFfmpegMotionStoryService(
            media,
            media_root=self.media_root,
            policy=motion_policy,
            ffmpeg_path=self.ffmpeg_path,
            ffprobe_path=self.ffprobe_path,
        )
        motion.initialize()
        motion_spec = motion.plan(
            package_job_id=package_job.job_id,
            image_artifact_ids=(scene_result.artifact_id,),
        )
        motion_job = motion.enqueue(motion_spec, priority=90)
        motion_result = motion.run_next(worker_id="underreach-soak-ffmpeg-worker")
        if motion_result is None or motion_result.status != JobStatus.COMPLETED or motion_result.output_artifact_id is None:
            raise UnattendedPromotionSoakError("guaranteed FFmpeg motion-story path did not complete")
        motion_artifact = _artifact(media, motion_result.output_artifact_id)
        motion_path = self.media_root.joinpath(*_safe_relative_uri(motion_artifact["uri"]).parts)
        if not motion_path.is_file() or sha256(motion_path.read_bytes()).hexdigest() != motion_artifact["digest"]:
            raise UnattendedPromotionSoakError("finished vertical promotion artifact is missing or corrupted")

        queue_item = _review_item(
            media,
            motion_result.output_artifact_id,
            tuple(motion_spec.source_event_ids),
            motion_spec.story_id,
        )
        review_job = _enqueue_review_queue(media, queue_item, priority=70)
        review_completed, review_manifest_artifact_id, review_manifest_uri, review_manifest_digest = _run_review_queue(
            media, self.media_root, review_job.job_id
        )
        review_repeat = _enqueue_review_queue(media, queue_item, priority=70)
        review_idempotent = review_repeat.job_id == review_job.job_id and review_repeat.status == JobStatus.COMPLETED

        website = MediaWebsiteBlogService(
            media,
            chronicle=chronicle,
            verifier=verifier,
            highlights=highlights,
            media_root=self.media_root,
        )
        website.initialize()
        website_spec = website.plan(crawl_id=profile.crawl_id)
        website_job = website.enqueue(website_spec, priority=60)
        website_result = website.run_next(worker_id="underreach-soak-website-worker")
        if website_result is None or website_result.status != JobStatus.COMPLETED:
            raise UnattendedPromotionSoakError("static Underreach website did not complete")

        canonical_after_media = _canonical_snapshot(canonical_stack["canonical"], canonical_stack["descent"])
        canonical_unchanged = _same_canonical(canonical_before_media, canonical_after_media)
        media_snapshot = media.snapshot()
        paid_execution_count = sum(
            int(item["actual_cost_microusd"]) > 0 for item in media_snapshot["provider_executions"]
        )
        nonlocal_provider_ids = [
            item["provider_id"]
            for item in media_snapshot["provider_executions"]
            if item["provider_id"] not in {"local_deterministic_png", "local_deterministic_wav", "local_ffmpeg"}
        ]
        autonomous_metrics = canonical_stack["descent"].modifiers[AUTONOMOUS_METADATA_KEY]["metrics"]
        composite_foreign_actor_ids = sorted(set(composite.delver_ids) - set(canonical_stack["ids"]))

        canonical_body = {
            "crawl_id": canonical_stack["descent"].id,
            "population_count": self.policy.population_count,
            "configured_stratum_count": self.policy.stratum_count,
            "outcome": canonical_stack["descent"].modifiers["_brain_driven_descent"]["run_outcome"],
            "simulation_steps": canonical_stack["simulation_steps"],
            "final_tick": canonical_stack["descent"].current_tick,
            "final_stratum": canonical_stack["descent"].current_floor,
            "surviving_delvers": canonical_stack["descent"].surviving_crawler_count,
            "eliminated_delvers": canonical_stack["descent"].eliminated_crawler_count,
            "encounters_resolved": int(autonomous_metrics["encounters_resolved"]),
            "strata_advanced": int(autonomous_metrics["strata_advanced"]),
            "bootstrap_export_unchanged": canonical_stack["bootstrap_export_unchanged"],
            "unchanged_during_downstream_media": canonical_unchanged,
            "final_fingerprint": canonical_after_media["fingerprint"],
            "final_state_digest": canonical_after_media["state_digest"],
            "final_history_digest": canonical_after_media["history_digest"],
            "final_ledger_digest": canonical_after_media["ledger_digest"],
            "final_event_count": canonical_after_media["event_count"],
        }
        event_provenance = {
            "social_pair_ids": list(canonical_stack["social_pair_ids"]),
            "social_party_id": canonical_stack["social_party_id"],
            "recruitment_offer_id": canonical_stack["recruitment_offer_id"],
            "promise_violation_event_ids": list(canonical_stack["promise_violation_event_ids"]),
            "betrayal_event_id": canonical_stack["betrayal_event_id"],
            "betrayal_conflict_score": canonical_stack["betrayal_conflict_score"],
            "social_event_ids": list(canonical_stack["social_event_ids"]),
            "combat_event_ids": list(canonical_stack["combat_event_ids"]),
            "encounter_retreat_event_ids": list(canonical_stack["encounter_retreat_event_ids"]),
            "terminal_media_event_ids": list(terminal_media_event_ids),
            "progression_event_ids": list(canonical_stack["progression_event_ids"]),
            "composite_source_event_ids": list(composite.source_event_ids),
            "composite_envelope_id": composite.envelope_id,
            "composite_highlight_id": highlight.highlight_id,
            "composite_highlight_score": evaluation.score.total,
            "composite_highlight_components": evaluation.score.model_dump(mode="json"),
            "composite_highlight_floor": 50,
            "composite_foreign_actor_ids": composite_foreign_actor_ids,
            "event_type_counts": canonical_stack["event_type_counts"],
        }
        media_body = {
            "envelope_count": len(media_snapshot["envelopes"]),
            "profile_count": len(chronicle.list_profiles()),
            "job_count": len(media_snapshot["jobs"]),
            "artifact_count": len(media_snapshot["artifacts"]),
            "provider_execution_count": len(media_snapshot["provider_executions"]),
            "paid_execution_count": paid_execution_count,
            "nonlocal_provider_ids": sorted(set(nonlocal_provider_ids)),
            "snapshot_digest": media_snapshot["digest"],
            "envelope_digest": payload_digest(media_snapshot["envelopes"]),
            "job_digest": payload_digest(media_snapshot["jobs"]),
            "artifact_digest": payload_digest(media_snapshot["artifacts"]),
        }
        chronicle_body = {
            "featured_profile_id": profile.profile_id,
            "featured_delver_id": profile.delver_id,
            "featured_chapter_id": chapter.chapter_id,
            "featured_chapter_kind": chapter.chapter_kind.value,
            "chapter_count": len(chronicle.list_chapters()),
            "highlight_count": len(highlights.list_highlights(crawl_id=profile.crawl_id)),
            "story_arc_count": len(highlights.list_story_arcs(crawl_id=profile.crawl_id)),
            "source_event_ids": list(chapter.source_event_ids),
        }
        verification_body = {
            "verification_id": verification.verification_id,
            "draft_id": draft_id,
            "manifest_id": manifest_id,
            "status": verification.status.value,
            "review_ready": verification.review_ready,
            "deterministic_contradiction_count": verification.deterministic_contradiction_count,
            "unsupported_claim_count": verification.unsupported_claim_count,
            "writer_provider_id": "deterministic_allowed_fact_writer",
            "writer_provider_local": True,
            "writer_provider_paid": False,
        }
        presentation_body = {
            "identity_id": identity_state.identity.identity_id,
            "identity_version": identity_state.identity.identity_version,
            "portrait_job_id": portrait_job.job_id,
            "portrait_artifact_id": portrait_result.artifact_id,
            "scene_job_id": scene_job.job_id,
            "scene_artifact_id": scene_result.artifact_id,
            "scene_output_uri": scene_result.output_uri,
            "scene_output_digest": scene_result.output_digest,
            "image_provider_id": "local_deterministic_png",
        }
        audio_body = {
            "package_id": audio_spec.package_id,
            "package_job_id": package_job.job_id,
            "package_status": package_result.package_status.value,
            "caption_only_ready": package_result.caption_only_ready,
            "voice_job_id": voice_job.job_id,
            "voice_status": voice_result.voice_status.value if voice_result.voice_status is not None else None,
            "voice_artifact_id": voice_result.voice_artifact_id,
            "voice_provider_id": "local_deterministic_wav",
        }
        promotion_body = {
            "story_id": motion_spec.story_id,
            "job_id": motion_job.job_id,
            "status": motion_result.status.value,
            "output_artifact_id": motion_result.output_artifact_id,
            "output_uri": motion_result.output_uri,
            "output_digest": motion_result.output_digest,
            "width": motion_result.width,
            "height": motion_result.height,
            "duration_ms": motion_result.duration_ms,
            "audio_stream_present": motion_result.audio_stream_present,
            "motion_story_fallback_guaranteed": True,
            "video_diffusion_required": False,
            "ffmpeg_local": True,
            "source_event_ids": list(motion_spec.source_event_ids),
        }
        review_body = {
            "queue_item_id": queue_item.queue_item_id,
            "review_job_id": review_completed.job_id,
            "review_manifest_artifact_id": review_manifest_artifact_id,
            "review_manifest_uri": review_manifest_uri,
            "review_manifest_digest": review_manifest_digest,
            "motion_story_artifact_id": queue_item.artifact_id,
            "review_status": queue_item.review_status,
            "published": queue_item.published,
            "review_ready": queue_item.review_ready,
            "human_intervention_required_before_review": False,
            "human_review_required_before_publication": True,
        }
        website_body = {
            "build_id": website_spec.build_id,
            "job_id": website_job.job_id,
            "status": website_result.status.value,
            "profile_count": website_spec.profile_count,
            "chapter_count": website_spec.chapter_count,
            "verified_narrative_count": website_spec.verified_narrative_count,
            "highlight_count": website_spec.highlight_count,
            "published_video_count": website_spec.published_video_count,
            "public_root": website_result.public_root,
            "page_count": website_result.page_count,
            "static_only": website_spec.static_only,
            "live_database_required_after_build": website_spec.live_database_required_after_build,
        }
        restart_body = {
            "injected_worker": "image_scene",
            "recovered_job_count": recovered_jobs,
            "same_scene_job": scene_result.job_id == scene_job.job_id,
            "scene_attempt_count": final_scene_job.attempt_count,
            "recovery_reason": "30.5.12_injected_restart",
        }
        idempotency_body = {
            "envelope_reregistration_stable": envelope_reregistration_stable,
            "scene_completed_reenqueue_reused_job": scene_idempotent,
            "review_queue_completed_reenqueue_reused_job": review_idempotent,
        }
        mandatory_zeroes = {
            "zero_unreal_calls": True,
            "zero_required_cloud_api_calls": True,
            "zero_required_paid_ai_dependencies": True,
            "zero_generated_media_mutation_of_canonical_truth": canonical_unchanged,
            "zero_human_intervention_before_review": True,
            "zero_automatic_paid_escalation": paid_execution_count == 0 and not nonlocal_provider_ids,
        }
        authority_contract = {
            "canonical_owner": "deterministic_simulation",
            "media_export_is_read_only": True,
            "media_database_is_separate": self.media_database_url != self.canonical_database_url,
            "presentation_can_mutate_simulation": False,
            "generated_identity_is_canonical": False,
            "generated_prose_is_canonical": False,
            "motion_story_is_canonical": False,
            "review_queue_can_publish_automatically": False,
            "website_reads_live_canonical_database": False,
            "optional_video_enhancement_required_for_acceptance": False,
            "next_phase": "31 - Dialogue / Commentary",
        }
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "seed": self.seed,
            "policy_digest": self.policy.digest,
            "canonical": canonical_body,
            "event_provenance": event_provenance,
            "media": media_body,
            "chronicle": chronicle_body,
            "verification": verification_body,
            "presentation": presentation_body,
            "audio": audio_body,
            "promotion": promotion_body,
            "review_queue": review_body,
            "website": website_body,
            "restart": restart_body,
            "idempotency": idempotency_body,
            "mandatory_zeroes": mandatory_zeroes,
            "authority_contract": authority_contract,
        }
        result = UnattendedPromotionSoakResult.model_validate({**body, "digest": payload_digest(body)})
        validate_soak_result(result)
        return result


__all__ = [
    "PROTOCOL",
    "IMPLEMENTATION_VERSION",
    "PHASE",
    "REVIEW_JOB_TYPE",
    "REVIEW_QUEUE_SCHEMA",
    "UnattendedPromotionSoakPolicy",
    "ReviewQueueItem",
    "UnattendedPromotionSoakResult",
    "UnattendedPromotionSoakError",
    "UnattendedPromotionSoakService",
    "validate_review_queue_item",
    "validate_soak_result",
]
