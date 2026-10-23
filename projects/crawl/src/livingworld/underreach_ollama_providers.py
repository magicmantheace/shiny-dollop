"""Concrete local Ollama providers for Underreach presentation narrative.

These adapters sit on top of the accepted Phase 30.5 media boundary. They may
select and order allowed facts and add tightly bounded stylistic language, but
they never become canonical authority. The accepted 30.5.5 deterministic claim
verifier remains the final gate for REVIEW_READY narrative.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
import re
from typing import Any, Iterable, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .runtime_checkpoint import canonical_json, payload_digest
from .underreach_delver_chronicle_profile import ChronicleChapter, DelverChronicleProfileService, validate_chapter
from .underreach_media_event_export import AllowedFact
from .underreach_media_foundation import MediaPersistence, ProviderDescriptor, ProviderKind
from .underreach_narrative_claim_verification import (
    AssessmentClassification,
    AuxiliaryAssessment,
    ClaimSpec,
    ClaimType,
    NarrativeClaimVerificationService,
    NarrativeVerification,
)


PROTOCOL = "underreach.ollama-providers.v1"
STACK_VERSION = "production-provider-stack.1"
ALPHA_VIEWER_FACING_ENV = "UNDERREACH_ALPHA_VIEWER_FACING"


class OllamaProviderError(RuntimeError):
    """Raised when the local Ollama provider cannot produce a valid bounded result."""


class OllamaProviderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_url: str = "http://127.0.0.1:11434"
    writer_model: str = "qwen3:8b"
    verifier_model: str = "qwen3:4b"
    timeout_seconds: float = Field(default=300.0, gt=0.0, le=3600.0)
    keep_alive: str | int = "0"
    writer_temperature: float = Field(default=0.15, ge=0.0, le=2.0)
    verifier_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_selected_facts: int = Field(default=6, ge=1, le=12)
    allow_stylistic_line: bool = True

    @model_validator(mode="after")
    def validate_config(self) -> "OllamaProviderConfig":
        if not self.base_url.startswith(("http://127.0.0.1", "http://localhost", "http://[::1]")):
            raise ValueError("Ollama provider defaults to a loopback-only local endpoint")
        if not self.writer_model.strip() or not self.verifier_model.strip():
            raise ValueError("Ollama writer/verifier model names must be non-empty")
        return self


class OllamaStorySelection(BaseModel):
    """The LLM chooses canonical facts; it does not author their factual values."""

    model_config = ConfigDict(frozen=True)

    fact_ids: tuple[str, ...]
    style_line: str | None = None
    tone: str = "cinematic"

    @model_validator(mode="after")
    def validate_selection(self) -> "OllamaStorySelection":
        if not self.fact_ids or len(self.fact_ids) != len(set(self.fact_ids)):
            raise ValueError("story selection requires unique fact IDs")
        return self


class OllamaAssessmentItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    sentence_index: int = Field(ge=0)
    classification: Literal["factual", "stylistic", "ambiguous", "contradiction"]
    reason_code: str = "ollama_auxiliary_assessment"


class OllamaAssessmentBatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    assessments: tuple[OllamaAssessmentItem, ...]


class OllamaNarrativePipelineResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    chapter_id: str
    draft_id: str
    manifest_id: str
    verification_id: str
    verification_status: str
    review_ready: bool
    writer_provider_id: str
    verifier_provider_id: str | None
    selected_fact_ids: tuple[str, ...]
    prose: str
    digest: str


def _stable_seed(*parts: object) -> int:
    text = ":".join(str(part) for part in parts)
    return int(sha256(text.encode("utf-8")).hexdigest()[:15], 16)


def _compact_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return canonical_json(value)


def _humanize_identifier(value: str) -> str:
    return value.replace("_", " ").strip()


def _alpha_viewer_facing() -> bool:
    return os.environ.get(ALPHA_VIEWER_FACING_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _render_canonical_fact_sentence(fact: AllowedFact) -> str:
    """Original provider rendering retained outside the live Alpha viewer path."""
    subject = _humanize_identifier(fact.subject)
    predicate = _humanize_identifier(fact.predicate)
    value = _compact_value(fact.value)
    if fact.predicate == "event_type":
        return f"{subject} is tied to the canonical event {value}."
    if fact.predicate in {"summary", "event_summary"} and isinstance(fact.value, str):
        text = fact.value.strip()
        return text if text.endswith((".", "!", "?")) else f"{text}."
    if fact.predicate in {"stratum", "floor"}:
        return f"{subject} reached canonical {predicate} {value}."
    if fact.predicate in {"sector", "location_id"}:
        return f"{subject} was recorded at canonical {predicate} {value}."
    return f"Canonical record: {subject} has {predicate} {value}."


_INTERNAL_ID = re.compile(
    r"\b(?:live_descender|descender|crawler|event|fact|envelope|sector|location|party|alliance|"
    r"profile|chapter|highlight|identity|reference|crawl)_[A-Za-z0-9_-]+\b",
    re.IGNORECASE,
)
_INTERNAL_HASH = re.compile(r"\b[a-f0-9]{16,}\b", re.IGNORECASE)


def _scrub_presentation_text(text: str) -> str:
    """Remove storage/debug identifiers from viewer-facing presentation text."""
    value = text.replace("Canonical record:", "").replace("canonical record:", "")
    value = _INTERNAL_ID.sub("", value)
    value = _INTERNAL_HASH.sub("", value)
    value = re.sub(r"\b(?:source_event_ids?|allowed_fact_ids?|semantic_flags?|state_changes?)\b\s*[:=]?", "", value, flags=re.IGNORECASE)
    value = re.sub(r"[_]{2,}", " ", value)
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    value = re.sub(r"\s{2,}", " ", value).strip(" -,:;")
    return value


def _display_subject(subject: str) -> str:
    lowered = subject.lower()
    if lowered.startswith(("live_descender_", "descender_", "crawler_")):
        return "A delver"
    if lowered.startswith("party_"):
        return "The party"
    if lowered.startswith("alliance_"):
        return "The alliance"
    return "The delver"


def _event_phrase(value: str) -> str:
    mapping = {
        "COMBAT_STARTED": "combat broke out",
        "COMBAT_HIT": "the fight turned violent",
        "COMBAT_ENDED": "the fight came to an end",
        "ENEMY_DEFEATED": "an enemy was defeated",
        "ENCOUNTER_TRIGGERED": "a dangerous encounter began",
        "ENCOUNTER_RESOLVED": "the encounter was resolved",
        "ITEM_ACQUIRED": "new loot was secured",
        "GROUND_LOOT_ACQUIRED": "loot was recovered from the dungeon",
        "ITEM_CONSUMED": "valuable supplies were spent",
        "PARTY_FORMED": "a new party came together",
        "CRAWLER_ADVANCED": "a delver pushed deeper into the crawl",
        "CRAWLER_MOVED": "the expedition moved deeper into the dungeon",
        "LOCATION_DISCOVERED": "a new part of the dungeon was discovered",
    }
    return mapping.get(value.upper(), "the crawl took another turn")


def _render_viewer_fact_sentence(fact: AllowedFact) -> str:
    """Render concise viewer-facing prose while exact values remain in ClaimSpec."""
    subject = _display_subject(fact.subject)
    predicate = fact.predicate.lower().strip()

    if predicate == "event_type" and isinstance(fact.value, str):
        phrase = _event_phrase(fact.value)
        return phrase[:1].upper() + phrase[1:] + "."
    if predicate in {"summary", "event_summary"} and isinstance(fact.value, str):
        text = _scrub_presentation_text(fact.value)
        if text and len(text) <= 96 and not re.search(r"\b(?:id|digest|hash|flag|predicate|payload)\b", text, re.IGNORECASE):
            return text if text.endswith((".", "!", "?")) else f"{text}."
        return "The crawl reached a meaningful turning point."
    if predicate in {"stratum", "floor"}:
        return f"{subject} pushed deeper into the crawl."
    if predicate in {"sector", "location_id", "location"}:
        return f"{subject} entered a new section of the dungeon."
    if predicate in {"item", "item_name", "loot", "equipment"}:
        return f"{subject} secured new loot."
    if predicate in {"party", "party_status", "party_id"}:
        return f"{subject} joined forces with other delvers."
    if predicate in {"level", "rank", "advancement", "progression"}:
        return f"{subject} grew stronger."
    return "The crawl recorded another meaningful development."


def _render_fact_sentence(fact: AllowedFact) -> str:
    if _alpha_viewer_facing():
        return _render_viewer_fact_sentence(fact)
    return _render_canonical_fact_sentence(fact)


_STYLE_FACT_WORDS = re.compile(
    r"\b(kill(?:ed|er|ing)?|attack(?:ed|er|ing)?|dead|died|death|injur(?:y|ed)|"
    r"stratum|sector|floor|party|alliance|leader|betray(?:al|ed)?|rescue(?:d)?|"
    r"retreat(?:ed)?|item|relic|health|boss|elite|victory|defeat|won|lost|"
    r"stole|stolen|abandon(?:ed)?|revenge|combat|crawler|delver)\b",
    re.IGNORECASE,
)


def _safe_style_line(text: str | None, facts: Iterable[AllowedFact]) -> str | None:
    if text is None:
        return None
    value = " ".join(text.split()).strip()
    if not value or len(value) > 180 or re.search(r"\d", value) or _STYLE_FACT_WORDS.search(value):
        return None
    lower = value.lower()
    for fact in facts:
        tokens = [fact.subject]
        if isinstance(fact.value, str):
            tokens.append(fact.value)
        for token in tokens:
            token = token.strip()
            if len(token) >= 5 and token.lower() in lower:
                return None
    if not value.endswith((".", "!", "?")):
        value += "."
    return value


class _OllamaClient:
    def __init__(self, config: OllamaProviderConfig, client: httpx.Client | None = None) -> None:
        self.config = config
        self._client = client

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            if self._client is not None:
                response = self._client.post(path, json=payload)
            else:
                with httpx.Client(base_url=self.config.base_url, timeout=self.config.timeout_seconds) as client:
                    response = client.post(path, json=payload)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaProviderError(f"Ollama request failed: {type(exc).__name__}") from exc
        if not isinstance(body, dict):
            raise OllamaProviderError("Ollama returned a non-object response")
        return body

    def chat_json(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        temperature: float,
        seed: int,
    ) -> dict[str, Any]:
        body = self._post(
            "/api/chat",
            {
                "model": model,
                "messages": messages,
                "stream": False,
                "format": schema,
                "keep_alive": self.config.keep_alive,
                "options": {"temperature": temperature, "seed": seed},
            },
        )
        message = body.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise OllamaProviderError("Ollama response omitted message.content")
        try:
            parsed = json.loads(message["content"])
        except json.JSONDecodeError as exc:
            raise OllamaProviderError("Ollama structured output was not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise OllamaProviderError("Ollama structured output was not a JSON object")
        return parsed

    def models(self) -> tuple[str, ...]:
        try:
            if self._client is not None:
                response = self._client.get("/api/tags")
            else:
                with httpx.Client(base_url=self.config.base_url, timeout=min(15.0, self.config.timeout_seconds)) as client:
                    response = client.get("/api/tags")
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaProviderError(f"Ollama health check failed: {type(exc).__name__}") from exc
        models = body.get("models", []) if isinstance(body, dict) else []
        names = []
        for item in models:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                names.append(item["name"])
        return tuple(sorted(set(names)))


class OllamaNarrativeProvider:
    """Local Qwen/Ollama fact-selector and narrative planner.

    Factual sentence values are rendered deterministically from AllowedFact
    records after model selection. This prevents a writer model from silently
    substituting a different canonical value into an auto-reviewable claim.
    """

    def __init__(self, config: OllamaProviderConfig | None = None, *, client: httpx.Client | None = None) -> None:
        self.config = config or OllamaProviderConfig()
        self.client = _OllamaClient(self.config, client)
        self._descriptor = ProviderDescriptor(
            provider_id=f"ollama_narrative_{self.config.writer_model.replace(':', '_')}",
            kind=ProviderKind.NARRATIVE,
            local=True,
            paid=False,
            available=True,
            healthy=True,
            capability_flags=("headless_narrative", "structured_output", "allowed_fact_selection", "offline"),
            deterministic_seed=True,
            estimated_vram_mb=7168,
            estimated_runtime_seconds=20.0,
            estimated_cost_microusd=0,
            quality_rank=88,
            quality_profile="local_qwen_structured_narrative",
        )

    @property
    def descriptor(self) -> ProviderDescriptor:
        return self._descriptor

    def health(self) -> dict[str, Any]:
        models = self.client.models()
        requested = self.config.writer_model
        ready = requested in models
        return {"provider_id": self.descriptor.provider_id, "ready": ready, "model": requested, "models": list(models)}

    def select(self, chapter: ChronicleChapter, facts: tuple[AllowedFact, ...]) -> OllamaStorySelection:
        validate_chapter(chapter)
        if not facts:
            raise OllamaProviderError("Ollama writer requires allowed facts")
        ordered = tuple(sorted(facts, key=lambda item: item.fact_id))
        fact_payload = [
            {
                "fact_id": fact.fact_id,
                "scope": fact.scope,
                "subject": fact.subject,
                "predicate": fact.predicate,
                "value": fact.value,
            }
            for fact in ordered
        ]
        schema = OllamaStorySelection.model_json_schema()
        prompt = (
            "You are the non-canonical presentation writer for Underreach. Select a small ordered subset of the supplied "
            "allowed facts that forms the clearest short Chronicle beat. You may optionally supply ONE atmospheric style_line, "
            "but that line must contain no names, IDs, numbers, locations, combat outcomes, items, relationships, or other factual claims. "
            f"Select at most {self.config.max_selected_facts} fact IDs. Never invent a fact ID. Return only the required JSON schema.\n\n"
            f"Chapter: {chapter.title_code}\nAllowed facts:\n{canonical_json(fact_payload)}"
        )
        parsed = self.client.chat_json(
            model=self.config.writer_model,
            messages=[
                {"role": "system", "content": "Canonical simulation truth is read-only. You only select allowed fact IDs."},
                {"role": "user", "content": prompt},
            ],
            schema=schema,
            temperature=self.config.writer_temperature,
            seed=_stable_seed(chapter.chapter_id, chapter.canonical_tick, self.config.writer_model),
        )
        try:
            selection = OllamaStorySelection.model_validate(parsed)
        except Exception as exc:
            raise OllamaProviderError("Ollama writer output failed schema validation") from exc

        known = {fact.fact_id for fact in ordered}
        if _alpha_viewer_facing():
            sanitized: list[str] = []
            seen: set[str] = set()
            for fact_id in selection.fact_ids:
                if fact_id in known and fact_id not in seen:
                    sanitized.append(fact_id)
                    seen.add(fact_id)
            if not sanitized:
                sanitized = [fact.fact_id for fact in ordered[: self.config.max_selected_facts]]
            fact_ids = tuple(sanitized[: self.config.max_selected_facts])
        else:
            if any(fact_id not in known for fact_id in selection.fact_ids):
                raise OllamaProviderError("Ollama writer selected a fact outside the chapter allowlist")
            fact_ids = selection.fact_ids[: self.config.max_selected_facts]

        return OllamaStorySelection(
            fact_ids=fact_ids,
            style_line=_safe_style_line(selection.style_line, ordered) if self.config.allow_stylistic_line else None,
            tone=selection.tone,
        )

    def build_prose_and_claims(
        self,
        chapter: ChronicleChapter,
        facts: tuple[AllowedFact, ...],
    ) -> tuple[str, tuple[ClaimSpec, ...], tuple[str, ...]]:
        selection = self.select(chapter, facts)
        by_id = {fact.fact_id: fact for fact in facts}
        sentences: list[str] = []
        claim_specs: list[ClaimSpec] = []
        if selection.style_line:
            sentences.append(selection.style_line)
            claim_specs.append(ClaimSpec(claim_type=ClaimType.STYLISTIC, sentence_index=0, confidence=1.0))
        for fact_id in selection.fact_ids:
            fact = by_id[fact_id]
            index = len(sentences)
            sentences.append(_render_fact_sentence(fact))
            claim_specs.append(
                ClaimSpec(
                    claim_type=ClaimType.FACTUAL,
                    sentence_index=index,
                    subject=fact.subject,
                    predicate=fact.predicate,
                    target_or_value=fact.value,
                    supporting_allowed_fact_ids=(fact.fact_id,),
                    confidence=1.0,
                )
            )
        prose = " ".join(sentences)
        if not prose.strip():
            raise OllamaProviderError("Ollama writer produced no usable narrative")
        return prose, tuple(claim_specs), selection.fact_ids


class OllamaAuxiliaryVerificationProvider:
    """Advisory local sentence classifier; deterministic 30.5.5 checks remain authoritative."""

    def __init__(self, config: OllamaProviderConfig | None = None, *, client: httpx.Client | None = None) -> None:
        self.config = config or OllamaProviderConfig()
        self.client = _OllamaClient(self.config, client)
        self._descriptor = ProviderDescriptor(
            provider_id=f"ollama_verification_{self.config.verifier_model.replace(':', '_')}",
            kind=ProviderKind.VERIFICATION,
            local=True,
            paid=False,
            available=True,
            healthy=True,
            capability_flags=("headless_verification", "structured_output", "advisory_only", "offline"),
            deterministic_seed=True,
            estimated_vram_mb=4096,
            estimated_runtime_seconds=8.0,
            estimated_cost_microusd=0,
            quality_rank=80,
            quality_profile="local_qwen_auxiliary_verifier",
        )

    @property
    def descriptor(self) -> ProviderDescriptor:
        return self._descriptor

    def health(self) -> dict[str, Any]:
        models = self.client.models()
        requested = self.config.verifier_model
        ready = requested in models
        return {"provider_id": self.descriptor.provider_id, "ready": ready, "model": requested, "models": list(models)}

    def assess(self, *, sentences: tuple[str, ...], facts: tuple[AllowedFact, ...], seed_material: str) -> tuple[AuxiliaryAssessment, ...]:
        if not sentences:
            return ()
        fact_payload = [
            {"fact_id": f.fact_id, "subject": f.subject, "predicate": f.predicate, "value": f.value}
            for f in sorted(facts, key=lambda item: item.fact_id)
        ]
        schema = OllamaAssessmentBatch.model_json_schema()
        prompt = (
            "Classify every sentence against the supplied allowed facts. factual = sentence makes a supported factual claim; "
            "stylistic = atmosphere only with no factual assertion; ambiguous = unclear factual status; contradiction = conflicts with an allowed fact. "
            "Return exactly one assessment per sentence_index. This classification is advisory and cannot override deterministic checks.\n\n"
            f"Sentences: {canonical_json(list(sentences))}\nAllowed facts: {canonical_json(fact_payload)}"
        )
        parsed = self.client.chat_json(
            model=self.config.verifier_model,
            messages=[
                {"role": "system", "content": "Be conservative. Mark uncertain factual language ambiguous rather than supported."},
                {"role": "user", "content": prompt},
            ],
            schema=schema,
            temperature=self.config.verifier_temperature,
            seed=_stable_seed(seed_material, self.config.verifier_model),
        )
        try:
            batch = OllamaAssessmentBatch.model_validate(parsed)
        except Exception as exc:
            raise OllamaProviderError("Ollama verifier output failed schema validation") from exc
        by_index = {item.sentence_index: item for item in batch.assessments}
        if set(by_index) != set(range(len(sentences))):
            raise OllamaProviderError("Ollama verifier did not classify every narrative sentence exactly once")
        mapping = {
            "factual": AssessmentClassification.FACTUAL,
            "stylistic": AssessmentClassification.STYLISTIC,
            "ambiguous": AssessmentClassification.AMBIGUOUS,
            "contradiction": AssessmentClassification.CONTRADICTION,
        }
        return tuple(
            AuxiliaryAssessment(
                sentence_index=index,
                classification=mapping[by_index[index].classification],
                provider_id=self.descriptor.provider_id,
                provider_local=True,
                provider_paid=False,
                reason_code=by_index[index].reason_code,
            )
            for index in range(len(sentences))
        )


class OllamaNarrativePipeline:
    """Persist an Ollama-selected Chronicle draft through the accepted 30.5.5 verifier."""

    def __init__(
        self,
        media: MediaPersistence,
        *,
        chronicle: DelverChronicleProfileService,
        verifier: NarrativeClaimVerificationService,
        writer: OllamaNarrativeProvider,
        assessor: OllamaAuxiliaryVerificationProvider | None = None,
    ) -> None:
        self.media = media
        self.chronicle = chronicle
        self.verifier = verifier
        self.writer = writer
        self.assessor = assessor

    def _chapter(self, chapter_id: str) -> ChronicleChapter:
        matches = [chapter for chapter in self.chronicle.list_chapters() if chapter.chapter_id == chapter_id]
        if len(matches) != 1:
            raise OllamaProviderError("Ollama narrative pipeline requires exactly one persisted Chronicle chapter")
        validate_chapter(matches[0])
        return matches[0]

    def _facts(self, chapter: ChronicleChapter) -> tuple[AllowedFact, ...]:
        allowed = set(chapter.allowed_fact_ids)
        facts: dict[str, AllowedFact] = {}
        for envelope_id in chapter.source_envelope_ids:
            envelope = self.media.get_envelope(envelope_id)
            if envelope is None:
                raise OllamaProviderError("Chronicle source MediaEnvelope disappeared")
            for fact in envelope.allowed_facts:
                if fact.fact_id in allowed:
                    facts[fact.fact_id] = fact
        if set(facts) != allowed:
            raise OllamaProviderError("Chronicle allowed fact set is incomplete")
        return tuple(facts[key] for key in sorted(facts))

    def generate_and_verify(self, chapter_id: str) -> OllamaNarrativePipelineResult:
        chapter = self._chapter(chapter_id)
        facts = self._facts(chapter)
        prose, claim_specs, selected_fact_ids = self.writer.build_prose_and_claims(chapter, facts)
        draft = self.verifier.register_draft(
            chapter_id=chapter.chapter_id,
            prose=prose,
            writer_provider_id=self.writer.descriptor.provider_id,
            writer_provider_local=True,
            writer_provider_paid=False,
        )
        assessments = (
            self.assessor.assess(sentences=draft.sentences, facts=facts, seed_material=draft.digest)
            if self.assessor is not None
            else ()
        )
        manifest = self.verifier.register_manifest(
            draft_id=draft.draft_id,
            claim_specs=claim_specs,
            auxiliary_assessments=assessments,
        )
        verification: NarrativeVerification = self.verifier.verify(manifest.manifest_id)
        body = {
            "chapter_id": chapter.chapter_id,
            "draft_id": draft.draft_id,
            "manifest_id": manifest.manifest_id,
            "verification_id": verification.verification_id,
            "verification_status": verification.status.value,
            "review_ready": verification.review_ready,
            "writer_provider_id": self.writer.descriptor.provider_id,
            "verifier_provider_id": self.assessor.descriptor.provider_id if self.assessor is not None else None,
            "selected_fact_ids": list(selected_fact_ids),
            "prose": draft.prose,
        }
        return OllamaNarrativePipelineResult.model_validate({**body, "digest": payload_digest(body)})


__all__ = [
    "PROTOCOL",
    "STACK_VERSION",
    "ALPHA_VIEWER_FACING_ENV",
    "OllamaProviderConfig",
    "OllamaProviderError",
    "OllamaStorySelection",
    "OllamaAssessmentItem",
    "OllamaAssessmentBatch",
    "OllamaNarrativePipelineResult",
    "OllamaNarrativeProvider",
    "OllamaAuxiliaryVerificationProvider",
    "OllamaNarrativePipeline",
]
