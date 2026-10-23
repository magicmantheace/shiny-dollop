"""Narrative claim manifests and deterministic fact verification for Phase 30.5.5.

This slice is the first place generated prose may be stored. Prose never becomes
canonical truth. Review-ready status requires a structured claim manifest whose
factual claims resolve exactly to the chapter's allowed MediaEnvelope facts.
Optional auxiliary local-model assessments may make a result stricter, but can
never override a deterministic contradiction or unsupported claim.
"""
from __future__ import annotations

import re
from enum import StrEnum
from hashlib import sha256
from threading import RLock
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import JSON, Boolean, Integer, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .runtime_checkpoint import canonical_json, payload_digest
from .underreach_delver_chronicle_profile import (
    ChronicleChapter,
    DelverChronicleProfileService,
    validate_chapter,
)
from .underreach_media_event_export import AllowedFact, MediaEnvelope, validate_media_envelope
from .underreach_media_foundation import MediaPersistence


PROTOCOL = "underreach.narrative-claim-verification.v1"
IMPLEMENTATION_VERSION = "30.5.5"
PHASE = "30.5"


class NarrativeVerificationError(ValueError):
    """Raised when narrative verification invariants are violated."""


class ClaimType(StrEnum):
    FACTUAL = "factual"
    STYLISTIC = "stylistic"


class ClaimStatus(StrEnum):
    VERIFIED = "verified"
    STYLE_SAFE = "style_safe"
    REJECTED = "rejected"


class VerificationStatus(StrEnum):
    REVIEW_READY = "review_ready"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


class AssessmentClassification(StrEnum):
    FACTUAL = "factual"
    STYLISTIC = "stylistic"
    AMBIGUOUS = "ambiguous"
    CONTRADICTION = "contradiction"


class VerificationPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    require_sentence_coverage: bool = True
    allow_stylistic_sentences: bool = True
    max_draft_chars: int = Field(default=12000, ge=128, le=100000)
    max_sentences: int = Field(default=128, ge=1, le=512)
    max_claims: int = Field(default=256, ge=1, le=1024)

    @property
    def digest(self) -> str:
        return payload_digest(self.model_dump(mode="json"))


class NarrativeDraft(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    phase: str = PHASE
    draft_id: str
    chapter_id: str
    prose: str
    sentences: tuple[str, ...]
    writer_provider_id: str | None = None
    writer_provider_local: bool | None = None
    writer_provider_paid: bool | None = None
    generated_prose: bool = True
    presentation_can_mutate_simulation: bool = False
    canonical_authority: bool = False
    digest: str


class ClaimSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim_type: ClaimType
    sentence_index: int = Field(ge=0)
    subject: str | None = None
    predicate: str | None = None
    target_or_value: Any = None
    supporting_allowed_fact_ids: tuple[str, ...] = ()
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_shape(self) -> "ClaimSpec":
        if self.claim_type == ClaimType.FACTUAL:
            if not self.subject or not self.predicate or not self.supporting_allowed_fact_ids:
                raise ValueError("factual claim requires subject, predicate, and supporting allowed facts")
        else:
            if self.subject is not None or self.predicate is not None or self.target_or_value is not None:
                raise ValueError("stylistic claim cannot carry factual assertion fields")
            if self.supporting_allowed_fact_ids:
                raise ValueError("stylistic claim cannot cite factual support")
        if tuple(sorted(set(self.supporting_allowed_fact_ids))) != self.supporting_allowed_fact_ids:
            raise ValueError("supporting allowed fact IDs must be normalized")
        return self


class NarrativeClaim(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim_id: str
    claim_type: ClaimType
    sentence_index: int = Field(ge=0)
    text: str
    subject: str | None = None
    predicate: str | None = None
    target_or_value: Any = None
    supporting_allowed_fact_ids: tuple[str, ...] = ()
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class AuxiliaryAssessment(BaseModel):
    """Optional classifier/extractor output. It is advisory and never authoritative."""

    model_config = ConfigDict(frozen=True)

    sentence_index: int = Field(ge=0)
    classification: AssessmentClassification
    provider_id: str | None = None
    provider_local: bool | None = None
    provider_paid: bool | None = None
    reason_code: str = "auxiliary_assessment"


class ClaimManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    phase: str = PHASE
    manifest_id: str
    draft_id: str
    chapter_id: str
    claims: tuple[NarrativeClaim, ...]
    auxiliary_assessments: tuple[AuxiliaryAssessment, ...] = ()
    writer_self_certification_trusted: bool = False
    auxiliary_model_can_override_deterministic_checks: bool = False
    digest: str


class ClaimVerification(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim_id: str
    sentence_index: int
    status: ClaimStatus
    matched_fact_id: str | None = None
    reason_codes: tuple[str, ...]


class NarrativeVerification(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    phase: str = PHASE
    verification_id: str
    draft_id: str
    manifest_id: str
    chapter_id: str
    status: VerificationStatus
    review_ready: bool
    claim_results: tuple[ClaimVerification, ...]
    reason_codes: tuple[str, ...]
    all_sentences_covered: bool
    deterministic_contradiction_count: int = Field(ge=0)
    unsupported_claim_count: int = Field(ge=0)
    auxiliary_assessment_used: bool = False
    auxiliary_model_can_override_deterministic_checks: bool = False
    presentation_can_mutate_simulation: bool = False
    canonical_authority: bool = False
    policy_digest: str
    digest: str


class NarrativeBase(DeclarativeBase):
    """30.5.5-only tables in the non-authoritative media database."""


class NarrativeDraftRow(NarrativeBase):
    __tablename__ = "media_narrative_drafts"

    draft_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    chapter_id: Mapped[str] = mapped_column(String(96), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    digest: Mapped[str] = mapped_column(String(96), nullable=False)


class ClaimManifestRow(NarrativeBase):
    __tablename__ = "media_claim_manifests"

    manifest_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    draft_id: Mapped[str] = mapped_column(String(96), index=True)
    chapter_id: Mapped[str] = mapped_column(String(96), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    digest: Mapped[str] = mapped_column(String(96), nullable=False)


class NarrativeVerificationRow(NarrativeBase):
    __tablename__ = "media_narrative_verifications"

    verification_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    draft_id: Mapped[str] = mapped_column(String(96), index=True)
    manifest_id: Mapped[str] = mapped_column(String(96), index=True)
    chapter_id: Mapped[str] = mapped_column(String(96), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    review_ready: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    digest: Mapped[str] = mapped_column(String(96), nullable=False)


def _stable_id(prefix: str, *parts: object) -> str:
    text = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(text.encode('utf-8')).hexdigest()[:24]}"


def _body_digest(model: BaseModel) -> str:
    return payload_digest(model.model_dump(mode="json", exclude={"digest"}))


def _sentence_split(prose: str) -> tuple[str, ...]:
    normalized = prose.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ()
    chunks = re.split(r"(?<=[.!?])\s+|\n+", normalized)
    return tuple(chunk.strip() for chunk in chunks if chunk.strip())


def _json_equal(left: Any, right: Any) -> bool:
    return canonical_json(left) == canonical_json(right)


_STYLE_FACT_WORDS = re.compile(
    r"\b(kill(?:ed|er|ing)?|attack(?:ed|er|ing)?|dead|died|death|injur(?:y|ed)|"
    r"stratum|sector|floor|party|alliance|leader|join(?:ed)?|left|leave|betray(?:al|ed)?|"
    r"rescue(?:d)?|surviv(?:e|ed|al)|retreat(?:ed)?|own(?:s|ed)?|carr(?:y|ied)|item|relic|"
    r"health|boss|elite|victory|defeat|won|lost|stole|stolen|abandon(?:ed)?|revenge)\b",
    re.IGNORECASE,
)


def _style_sentence_safe(text: str, facts: Iterable[AllowedFact]) -> bool:
    if re.search(r"\d", text) or _STYLE_FACT_WORDS.search(text):
        return False
    lower = text.lower()
    for fact in facts:
        candidates = [fact.subject]
        if isinstance(fact.value, str):
            candidates.append(fact.value)
        elif isinstance(fact.value, list):
            candidates.extend(item for item in fact.value if isinstance(item, str))
        for value in candidates:
            token = value.strip()
            if len(token) >= 6 and ("_" in token or token.lower().startswith(("descender", "party", "alliance", "sector"))):
                if token.lower() in lower:
                    return False
    return True


def validate_draft(draft: NarrativeDraft) -> bool:
    if draft.protocol != PROTOCOL or draft.implementation_version != IMPLEMENTATION_VERSION or draft.phase != PHASE:
        raise NarrativeVerificationError("narrative draft protocol/version mismatch")
    if not draft.prose.strip() or not draft.sentences or draft.sentences != _sentence_split(draft.prose):
        raise NarrativeVerificationError("narrative draft sentence structure is invalid")
    if draft.presentation_can_mutate_simulation or draft.canonical_authority:
        raise NarrativeVerificationError("narrative draft escaped presentation-only authority")
    if draft.digest != _body_digest(draft):
        raise NarrativeVerificationError("narrative draft digest mismatch")
    return True


def validate_manifest(manifest: ClaimManifest, draft: NarrativeDraft) -> bool:
    if manifest.protocol != PROTOCOL or manifest.implementation_version != IMPLEMENTATION_VERSION or manifest.phase != PHASE:
        raise NarrativeVerificationError("claim manifest protocol/version mismatch")
    if manifest.draft_id != draft.draft_id or manifest.chapter_id != draft.chapter_id:
        raise NarrativeVerificationError("claim manifest does not belong to draft/chapter")
    if manifest.writer_self_certification_trusted or manifest.auxiliary_model_can_override_deterministic_checks:
        raise NarrativeVerificationError("claim manifest granted generated content authority")
    claim_ids = [item.claim_id for item in manifest.claims]
    if len(claim_ids) != len(set(claim_ids)):
        raise NarrativeVerificationError("claim IDs must be unique")
    for claim in manifest.claims:
        if claim.sentence_index >= len(draft.sentences) or claim.text != draft.sentences[claim.sentence_index]:
            raise NarrativeVerificationError("claim text/index does not exactly cover draft sentence")
        spec = ClaimSpec(
            claim_type=claim.claim_type,
            sentence_index=claim.sentence_index,
            subject=claim.subject,
            predicate=claim.predicate,
            target_or_value=claim.target_or_value,
            supporting_allowed_fact_ids=claim.supporting_allowed_fact_ids,
            confidence=claim.confidence,
        )
        expected = _stable_id("narrative_claim", draft.draft_id, payload_digest(spec.model_dump(mode="json")))
        if claim.claim_id != expected:
            raise NarrativeVerificationError("claim deterministic identity mismatch")
    for assessment in manifest.auxiliary_assessments:
        if assessment.sentence_index >= len(draft.sentences):
            raise NarrativeVerificationError("auxiliary assessment sentence is out of range")
    if manifest.digest != _body_digest(manifest):
        raise NarrativeVerificationError("claim manifest digest mismatch")
    return True


def validate_verification(result: NarrativeVerification) -> bool:
    if result.protocol != PROTOCOL or result.implementation_version != IMPLEMENTATION_VERSION or result.phase != PHASE:
        raise NarrativeVerificationError("narrative verification protocol/version mismatch")
    if result.review_ready != (result.status == VerificationStatus.REVIEW_READY):
        raise NarrativeVerificationError("review-ready flag diverged from verification status")
    if result.auxiliary_model_can_override_deterministic_checks:
        raise NarrativeVerificationError("auxiliary model gained authority over deterministic verification")
    if result.presentation_can_mutate_simulation or result.canonical_authority:
        raise NarrativeVerificationError("verified narrative gained canonical authority")
    if result.digest != _body_digest(result):
        raise NarrativeVerificationError("narrative verification digest mismatch")
    return True


class NarrativeClaimVerificationService:
    """Persist drafts/manifests and independently verify claims against allowed facts."""

    def __init__(
        self,
        media: MediaPersistence,
        *,
        chronicle: DelverChronicleProfileService,
        policy: VerificationPolicy | None = None,
    ) -> None:
        self.media = media
        self.chronicle = chronicle
        self.policy = policy or VerificationPolicy()
        self._lock = RLock()

    def initialize(self) -> None:
        with self._lock:
            NarrativeBase.metadata.create_all(self.media.engine)

    def _chapter(self, chapter_id: str) -> ChronicleChapter:
        matches = [item for item in self.chronicle.list_chapters() if item.chapter_id == chapter_id]
        if len(matches) != 1:
            raise NarrativeVerificationError("narrative draft requires exactly one existing Chronicle chapter")
        validate_chapter(matches[0])
        return matches[0]

    def _chapter_facts(self, chapter: ChronicleChapter) -> dict[str, AllowedFact]:
        allowed = set(chapter.allowed_fact_ids)
        facts: dict[str, AllowedFact] = {}
        for envelope_id in chapter.source_envelope_ids:
            envelope = self.media.get_envelope(envelope_id)
            if envelope is None:
                raise NarrativeVerificationError("Chronicle source MediaEnvelope is missing")
            validate_media_envelope(envelope)
            for fact in envelope.allowed_facts:
                if fact.fact_id not in allowed:
                    continue
                existing = facts.get(fact.fact_id)
                if existing is not None and existing != fact:
                    raise NarrativeVerificationError("allowed fact identity resolved to different payload")
                facts[fact.fact_id] = fact
        missing = allowed - set(facts)
        if missing:
            raise NarrativeVerificationError("Chronicle allowed-fact provenance is incomplete")
        return facts

    def register_draft(
        self,
        *,
        chapter_id: str,
        prose: str,
        writer_provider_id: str | None = None,
        writer_provider_local: bool | None = None,
        writer_provider_paid: bool | None = None,
    ) -> NarrativeDraft:
        self._chapter(chapter_id)
        sentences = _sentence_split(prose)
        if len(prose) > self.policy.max_draft_chars:
            raise NarrativeVerificationError("narrative draft exceeds configured character limit")
        if not sentences or len(sentences) > self.policy.max_sentences:
            raise NarrativeVerificationError("narrative draft sentence count is outside configured bounds")
        identity_body = {
            "chapter_id": chapter_id,
            "prose": prose.strip(),
            "writer_provider_id": writer_provider_id,
            "writer_provider_local": writer_provider_local,
            "writer_provider_paid": writer_provider_paid,
        }
        draft_id = _stable_id("narrative_draft", payload_digest(identity_body))
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "draft_id": draft_id,
            "chapter_id": chapter_id,
            "prose": prose.strip(),
            "sentences": list(sentences),
            "writer_provider_id": writer_provider_id,
            "writer_provider_local": writer_provider_local,
            "writer_provider_paid": writer_provider_paid,
            "generated_prose": True,
            "presentation_can_mutate_simulation": False,
            "canonical_authority": False,
        }
        draft = NarrativeDraft.model_validate({**body, "digest": payload_digest(body)})
        validate_draft(draft)
        payload = draft.model_dump(mode="json")
        with self._lock:
            with Session(self.media.engine) as session:
                row = session.get(NarrativeDraftRow, draft.draft_id)
                if row is None:
                    session.add(NarrativeDraftRow(draft_id=draft.draft_id, chapter_id=chapter_id, payload=payload, digest=draft.digest))
                    session.commit()
                elif row.digest != draft.digest or row.payload != payload:
                    raise NarrativeVerificationError("narrative draft identity conflict")
        return draft

    def get_draft(self, draft_id: str) -> NarrativeDraft | None:
        with self._lock:
            with Session(self.media.engine) as session:
                row = session.get(NarrativeDraftRow, draft_id)
                if row is None:
                    return None
                value = NarrativeDraft.model_validate(row.payload)
                validate_draft(value)
                return value

    def make_claim(self, draft: NarrativeDraft, spec: ClaimSpec) -> NarrativeClaim:
        validate_draft(draft)
        if spec.sentence_index >= len(draft.sentences):
            raise NarrativeVerificationError("claim sentence index is out of range")
        claim_id = _stable_id("narrative_claim", draft.draft_id, payload_digest(spec.model_dump(mode="json")))
        return NarrativeClaim(
            claim_id=claim_id,
            claim_type=spec.claim_type,
            sentence_index=spec.sentence_index,
            text=draft.sentences[spec.sentence_index],
            subject=spec.subject,
            predicate=spec.predicate,
            target_or_value=spec.target_or_value,
            supporting_allowed_fact_ids=spec.supporting_allowed_fact_ids,
            confidence=spec.confidence,
        )

    def register_manifest(
        self,
        *,
        draft_id: str,
        claim_specs: Iterable[ClaimSpec],
        auxiliary_assessments: Iterable[AuxiliaryAssessment] = (),
    ) -> ClaimManifest:
        draft = self.get_draft(draft_id)
        if draft is None:
            raise NarrativeVerificationError("claim manifest references unknown narrative draft")
        specs = tuple(claim_specs)
        if not specs or len(specs) > self.policy.max_claims:
            raise NarrativeVerificationError("claim manifest claim count is outside configured bounds")
        claims = tuple(sorted((self.make_claim(draft, spec) for spec in specs), key=lambda item: (item.sentence_index, item.claim_id)))
        assessments = tuple(sorted(auxiliary_assessments, key=lambda item: (item.sentence_index, item.classification.value, item.reason_code)))
        identity = {
            "draft_id": draft.draft_id,
            "chapter_id": draft.chapter_id,
            "claims": [item.model_dump(mode="json") for item in claims],
            "auxiliary_assessments": [item.model_dump(mode="json") for item in assessments],
        }
        manifest_id = _stable_id("claim_manifest", payload_digest(identity))
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "manifest_id": manifest_id,
            "draft_id": draft.draft_id,
            "chapter_id": draft.chapter_id,
            "claims": [item.model_dump(mode="json") for item in claims],
            "auxiliary_assessments": [item.model_dump(mode="json") for item in assessments],
            "writer_self_certification_trusted": False,
            "auxiliary_model_can_override_deterministic_checks": False,
        }
        manifest = ClaimManifest.model_validate({**body, "digest": payload_digest(body)})
        validate_manifest(manifest, draft)
        payload = manifest.model_dump(mode="json")
        with self._lock:
            with Session(self.media.engine) as session:
                row = session.get(ClaimManifestRow, manifest.manifest_id)
                if row is None:
                    session.add(ClaimManifestRow(manifest_id=manifest.manifest_id, draft_id=draft.draft_id, chapter_id=draft.chapter_id, payload=payload, digest=manifest.digest))
                    session.commit()
                elif row.digest != manifest.digest or row.payload != payload:
                    raise NarrativeVerificationError("claim manifest identity conflict")
        return manifest

    def get_manifest(self, manifest_id: str) -> ClaimManifest | None:
        with self._lock:
            with Session(self.media.engine) as session:
                row = session.get(ClaimManifestRow, manifest_id)
                if row is None:
                    return None
                manifest = ClaimManifest.model_validate(row.payload)
        draft = self.get_draft(manifest.draft_id)
        if draft is None:
            raise NarrativeVerificationError("persisted claim manifest lost draft")
        validate_manifest(manifest, draft)
        return manifest

    @staticmethod
    def _claim_result(claim: NarrativeClaim, status: ClaimStatus, *reasons: str, matched_fact_id: str | None = None) -> ClaimVerification:
        return ClaimVerification(
            claim_id=claim.claim_id,
            sentence_index=claim.sentence_index,
            status=status,
            matched_fact_id=matched_fact_id,
            reason_codes=tuple(sorted(set(reasons))),
        )

    def verify(self, manifest_id: str) -> NarrativeVerification:
        manifest = self.get_manifest(manifest_id)
        if manifest is None:
            raise NarrativeVerificationError("verification references unknown claim manifest")
        draft = self.get_draft(manifest.draft_id)
        if draft is None:
            raise NarrativeVerificationError("verification lost narrative draft")
        chapter = self._chapter(manifest.chapter_id)
        facts = self._chapter_facts(chapter)
        allowed_ids = set(facts)
        by_key: dict[tuple[str, str], list[AllowedFact]] = {}
        for fact in facts.values():
            by_key.setdefault((fact.subject, fact.predicate), []).append(fact)

        results: list[ClaimVerification] = []
        contradiction_count = 0
        unsupported_count = 0
        sentence_claims: dict[int, list[NarrativeClaim]] = {index: [] for index in range(len(draft.sentences))}
        for claim in manifest.claims:
            sentence_claims[claim.sentence_index].append(claim)
            if claim.claim_type == ClaimType.STYLISTIC:
                if not self.policy.allow_stylistic_sentences or not _style_sentence_safe(claim.text, facts.values()):
                    results.append(self._claim_result(claim, ClaimStatus.REJECTED, "stylistic_sentence_contains_factual_signal"))
                    unsupported_count += 1
                else:
                    results.append(self._claim_result(claim, ClaimStatus.STYLE_SAFE, "bounded_stylistic_language"))
                continue

            support_ids = set(claim.supporting_allowed_fact_ids)
            if not support_ids.issubset(allowed_ids):
                results.append(self._claim_result(claim, ClaimStatus.REJECTED, "support_fact_outside_chapter_allowlist"))
                unsupported_count += 1
                continue
            candidates = by_key.get((claim.subject or "", claim.predicate or ""), [])
            exact = [fact for fact in candidates if _json_equal(fact.value, claim.target_or_value)]
            supported_exact = [fact for fact in exact if fact.fact_id in support_ids]
            if supported_exact:
                irrelevant = [fact_id for fact_id in support_ids if fact_id not in {item.fact_id for item in exact}]
                if irrelevant:
                    results.append(self._claim_result(claim, ClaimStatus.REJECTED, "irrelevant_support_fact"))
                    unsupported_count += 1
                else:
                    matched = sorted(supported_exact, key=lambda item: item.fact_id)[0]
                    results.append(self._claim_result(claim, ClaimStatus.VERIFIED, "exact_allowed_fact_match", matched_fact_id=matched.fact_id))
            elif candidates:
                results.append(self._claim_result(claim, ClaimStatus.REJECTED, "deterministic_fact_contradiction"))
                contradiction_count += 1
            else:
                results.append(self._claim_result(claim, ClaimStatus.REJECTED, "unsupported_factual_claim"))
                unsupported_count += 1

        covered = all(bool(sentence_claims[index]) for index in sentence_claims)
        reasons: set[str] = set()
        rejected = any(item.status == ClaimStatus.REJECTED for item in results)
        needs_review = False
        if self.policy.require_sentence_coverage and not covered:
            rejected = True
            reasons.add("uncovered_draft_sentence")

        for assessment in manifest.auxiliary_assessments:
            if assessment.classification == AssessmentClassification.CONTRADICTION:
                rejected = True
                reasons.add("auxiliary_contradiction_signal")
            elif assessment.classification == AssessmentClassification.AMBIGUOUS:
                needs_review = True
                reasons.add("auxiliary_ambiguous_signal")
            elif assessment.classification == AssessmentClassification.FACTUAL:
                if not any(claim.claim_type == ClaimType.FACTUAL for claim in sentence_claims[assessment.sentence_index]):
                    rejected = True
                    reasons.add("auxiliary_found_unmanifested_factual_sentence")

        if contradiction_count:
            reasons.add("deterministic_contradiction")
        if unsupported_count:
            reasons.add("unsupported_claim")
        if rejected:
            status = VerificationStatus.REJECTED
        elif needs_review:
            status = VerificationStatus.NEEDS_REVIEW
        else:
            status = VerificationStatus.REVIEW_READY
        review_ready = status == VerificationStatus.REVIEW_READY

        assessment_digest = payload_digest([item.model_dump(mode="json") for item in manifest.auxiliary_assessments])
        verification_id = _stable_id("narrative_verification", manifest.manifest_id, self.policy.digest, assessment_digest)
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "verification_id": verification_id,
            "draft_id": draft.draft_id,
            "manifest_id": manifest.manifest_id,
            "chapter_id": chapter.chapter_id,
            "status": status.value,
            "review_ready": review_ready,
            "claim_results": [item.model_dump(mode="json") for item in sorted(results, key=lambda item: item.claim_id)],
            "reason_codes": sorted(reasons),
            "all_sentences_covered": covered,
            "deterministic_contradiction_count": contradiction_count,
            "unsupported_claim_count": unsupported_count,
            "auxiliary_assessment_used": bool(manifest.auxiliary_assessments),
            "auxiliary_model_can_override_deterministic_checks": False,
            "presentation_can_mutate_simulation": False,
            "canonical_authority": False,
            "policy_digest": self.policy.digest,
        }
        result = NarrativeVerification.model_validate({**body, "digest": payload_digest(body)})
        validate_verification(result)
        payload = result.model_dump(mode="json")
        with self._lock:
            with Session(self.media.engine) as session:
                row = session.get(NarrativeVerificationRow, result.verification_id)
                if row is None:
                    session.add(
                        NarrativeVerificationRow(
                            verification_id=result.verification_id,
                            draft_id=result.draft_id,
                            manifest_id=result.manifest_id,
                            chapter_id=result.chapter_id,
                            status=result.status.value,
                            review_ready=result.review_ready,
                            payload=payload,
                            digest=result.digest,
                        )
                    )
                    session.commit()
                elif row.digest != result.digest or row.payload != payload:
                    raise NarrativeVerificationError("narrative verification identity conflict")
        return result

    def list_drafts(self) -> tuple[NarrativeDraft, ...]:
        with self._lock:
            with Session(self.media.engine) as session:
                rows = session.scalars(select(NarrativeDraftRow).order_by(NarrativeDraftRow.draft_id)).all()
                values = tuple(NarrativeDraft.model_validate(row.payload) for row in rows)
        for item in values:
            validate_draft(item)
        return values

    def list_manifests(self) -> tuple[ClaimManifest, ...]:
        with self._lock:
            with Session(self.media.engine) as session:
                rows = session.scalars(select(ClaimManifestRow).order_by(ClaimManifestRow.manifest_id)).all()
                values = tuple(ClaimManifest.model_validate(row.payload) for row in rows)
        for item in values:
            draft = self.get_draft(item.draft_id)
            if draft is None:
                raise NarrativeVerificationError("persisted manifest lost draft")
            validate_manifest(item, draft)
        return values

    def list_verifications(self) -> tuple[NarrativeVerification, ...]:
        with self._lock:
            with Session(self.media.engine) as session:
                rows = session.scalars(select(NarrativeVerificationRow).order_by(NarrativeVerificationRow.verification_id)).all()
                values = tuple(NarrativeVerification.model_validate(row.payload) for row in rows)
        for item in values:
            validate_verification(item)
        return values

    def snapshot(self) -> dict[str, Any]:
        drafts = [item.model_dump(mode="json") for item in self.list_drafts()]
        manifests = [item.model_dump(mode="json") for item in self.list_manifests()]
        verifications = [item.model_dump(mode="json") for item in self.list_verifications()]
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "authoritative": False,
            "canonical_owner": "deterministic_simulation",
            "presentation_can_mutate_simulation": False,
            "writer_self_certification_trusted": False,
            "auxiliary_model_can_override_deterministic_checks": False,
            "local_model_required": False,
            "cloud_api_required": False,
            "paid_provider_required": False,
            "provider_invocation_used": False,
            "policy": self.policy.model_dump(mode="json"),
            "policy_digest": self.policy.digest,
            "drafts": drafts,
            "draft_count": len(drafts),
            "draft_digest": payload_digest(drafts),
            "manifests": manifests,
            "manifest_count": len(manifests),
            "manifest_digest": payload_digest(manifests),
            "verifications": verifications,
            "verification_count": len(verifications),
            "verification_digest": payload_digest(verifications),
        }
        return {**body, "digest": payload_digest(body)}


__all__ = [
    "PROTOCOL",
    "IMPLEMENTATION_VERSION",
    "PHASE",
    "ClaimType",
    "ClaimStatus",
    "VerificationStatus",
    "AssessmentClassification",
    "VerificationPolicy",
    "NarrativeDraft",
    "ClaimSpec",
    "NarrativeClaim",
    "AuxiliaryAssessment",
    "ClaimManifest",
    "ClaimVerification",
    "NarrativeVerification",
    "NarrativeVerificationError",
    "NarrativeClaimVerificationService",
    "validate_draft",
    "validate_manifest",
    "validate_verification",
]
