"""Alpha entry point for the live production media worker.

This adapter keeps the generic production worker reusable while binding live
Alpha to its versioned deterministic scoring profile. Alpha adds viewer-only
editorial policy, stable delver reference conditioning, coherent setup/action/
outcome scene packs, compact captions, and tighter motion-story pacing. None of
these presentation choices can mutate canonical simulation truth.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import signal

from . import underreach_live_production_media_worker as base_worker
from . import underreach_production_provider_stack as provider_stack_module
from .runtime_checkpoint import payload_digest
from .underreach_alpha_cinematic_reference_image import AlphaContinuityComfyUIImageProvider
from .underreach_alpha_highlight_scoring import (
    ALPHA_SCORING_PROFILE,
    AlphaHighlightStoryArcService,
)
from .underreach_alpha_ollama_runtime import (
    VERIFIER_NUM_PREDICT,
    WRITER_NUM_PREDICT,
    install_alpha_ollama_runtime,
)
from .underreach_alpha_presentation_polish import (
    ALPHA_SCENE_STAGING,
    MAX_VIEWER_SENTENCE_CHARS,
    alpha_scene_variant_spec,
    find_reference_artifact,
    render_alpha_viewer_sentence,
    reorder_motion_story_shots,
    with_reference_artifacts,
)
from .underreach_media_event_export import AllowedFact
from .underreach_narrative_claim_verification import ClaimSpec, ClaimType
from .underreach_ollama_providers import ALPHA_VIEWER_FACING_ENV
from .underreach_presentation_identity import ReferenceKind


ALPHA_FACT_FALLBACK_PROVIDER_ID = "alpha_deterministic_fact_narrative"
ALPHA_EDITORIAL_PROVIDER_ID = "alpha_deterministic_editorial_narrative_v2"
_ALPHA_LEGACY_CAPTION_STYLE = re.compile(
    r"FontSize=\d+,Alignment=2,MarginV=\d+,Outline=2,Shadow=0"
)


def _alpha_caption_style(output_height: int) -> str:
    """Compact bottom subtitle style sized for two short viewer lines."""
    font_size = max(16, int(round(output_height * 0.022)))
    margin_v = max(26, int(round(output_height * 0.055)))
    return (
        f"FontSize={font_size},Alignment=2,MarginV={margin_v},"
        "Outline=1,Shadow=1,BorderStyle=1,WrapStyle=0,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,"
        "MarginL=38,MarginR=38"
    )


def _alpha_fact_stage(fact: AllowedFact) -> str:
    predicate = fact.predicate.upper()
    value = str(fact.value).upper() if isinstance(fact.value, str) else ""
    if predicate == "EVENT_TYPE":
        if value in {"ENCOUNTER_TRIGGERED", "COMBAT_STARTED", "LOCATION_DISCOVERED"}:
            return "setup"
        if value in {"COMBAT_HIT", "ATTACK", "DAMAGE", "ITEM_CONSUMED"}:
            return "action"
        if value in {"ENEMY_DEFEATED", "COMBAT_ENDED", "ENCOUNTER_RESOLVED", "VICTORY"}:
            return "outcome"
        if value in {"ITEM_ACQUIRED", "GROUND_LOOT_ACQUIRED", "LOOT_ACQUIRED"}:
            return "reward"
        if value in {"CRAWLER_ADVANCED", "LEVEL_GAINED", "ABILITY_UNLOCKED", "FLOOR_ADVANCED", "STRATUM_ADVANCED"}:
            return "progression"
        if value in {"PARTY_FORMED", "ALLIANCE_FORMED"}:
            return "social"
        if value in {"CRAWLER_MOVED"}:
            return "movement"
    if predicate in {"STRATUM", "FLOOR", "LEVEL", "RANK", "ADVANCEMENT", "PROGRESSION"}:
        return "progression"
    if predicate in {"ITEM", "ITEM_NAME", "LOOT", "EQUIPMENT"}:
        return "reward"
    if predicate in {"PARTY", "PARTY_STATUS", "PARTY_ID", "ALLIANCE"}:
        return "social"
    if predicate in {"SECTOR", "LOCATION_ID", "LOCATION"}:
        return "movement"
    return "other"


def _select_alpha_editorial_facts(facts: tuple[AllowedFact, ...], limit: int = 3) -> tuple[AllowedFact, ...]:
    """Choose a concise deterministic story arc and suppress semantic repetition."""
    ordered = tuple(sorted(facts, key=lambda item: item.fact_id))
    buckets: dict[str, list[AllowedFact]] = {
        key: [] for key in ("setup", "action", "outcome", "reward", "progression", "social", "movement", "other")
    }
    for fact in ordered:
        buckets[_alpha_fact_stage(fact)].append(fact)

    chosen: list[AllowedFact] = []
    seen_sentences: set[str] = set()

    def take(stage: str) -> None:
        for fact in buckets[stage]:
            sentence = render_alpha_viewer_sentence(fact).strip().lower()
            if sentence and sentence not in seen_sentences:
                chosen.append(fact)
                seen_sentences.add(sentence)
                return

    for stage in ("setup", "action", "outcome"):
        if len(chosen) < limit:
            take(stage)

    if len(chosen) < limit:
        if buckets["reward"]:
            take("reward")
        else:
            take("progression")

    for stage in ("progression", "social", "reward", "movement", "other"):
        if len(chosen) >= limit:
            break
        take(stage)

    return tuple(chosen[:limit])


class AlphaFfmpegMotionStoryService(base_worker.AutomatedFfmpegMotionStoryService):
    """Alpha-only editorial motion-story presentation."""

    def _video_filter(self, spec):
        filters = super()._video_filter(spec)
        if not spec.burn_captions:
            return filters
        style = _alpha_caption_style(spec.output_height)
        return [_ALPHA_LEGACY_CAPTION_STYLE.sub(style, value) for value in filters]

    def plan(self, *, package_job_id: str, image_artifact_ids: tuple[str, ...]):
        _, narration = self._package(package_job_id)
        candidates = [
            item
            for item in self.media.snapshot()["artifacts"]
            if item["artifact_kind"] == "image/png"
            and (item.get("metadata") or {}).get("chapter_id") == narration.chapter_id
        ]
        ids = list(dict.fromkeys(image_artifact_ids))
        for item in sorted(candidates, key=lambda value: value["artifact_id"]):
            if item["artifact_id"] not in ids:
                ids.append(item["artifact_id"])
            if len(ids) >= 3:
                break
        ordered = tuple(ids[:3])
        spec = super().plan(package_job_id=package_job_id, image_artifact_ids=ordered)
        return reorder_motion_story_shots(spec, ordered)


class AlphaLiveProductionMediaWorker(base_worker.LiveProductionMediaWorker):
    def __init__(self, **kwargs) -> None:
        install_alpha_ollama_runtime()
        super().__init__(**kwargs)
        self._alpha_scoring_reindex_complete = False
        self._alpha_reindexed_highlights = 0
        self._alpha_narrative_aux_bypass_count = 0
        self._alpha_narrative_fact_fallback_count = 0

    def _status(self, state: str, **extra) -> None:
        extra.setdefault("scoring_profile", ALPHA_SCORING_PROFILE)
        extra.setdefault("reindexed_highlight_count", self._alpha_reindexed_highlights)
        extra.setdefault("ollama_thinking_enabled", False)
        extra.setdefault("ollama_writer_num_predict", WRITER_NUM_PREDICT)
        extra.setdefault("ollama_verifier_num_predict", VERIFIER_NUM_PREDICT)
        extra.setdefault("narrative_aux_bypass_count", self._alpha_narrative_aux_bypass_count)
        extra.setdefault("narrative_fact_fallback_count", self._alpha_narrative_fact_fallback_count)
        extra.setdefault("viewer_facing_narrative", os.environ.get(ALPHA_VIEWER_FACING_ENV) == "true")
        extra.setdefault("presentation_polish_version", "alpha-continuity-v2")
        extra.setdefault("compact_bottom_captions", True)
        extra.setdefault("max_caption_lines", 2)
        extra.setdefault("max_caption_sentence_chars", MAX_VIEWER_SENTENCE_CHARS)
        extra.setdefault("editorial_story_beats", True)
        extra.setdefault("max_story_sentences", 3)
        extra.setdefault("multi_scene_stills", 3)
        extra.setdefault("stable_identity_reference", True)
        extra.setdefault("equipment_reference_chaining", True)
        extra.setdefault("reference_conditioned_scenes", True)
        extra.setdefault("short_opening_fade_ms", 80)
        extra.setdefault("transition_ms", 180)
        extra.setdefault("target_shot_seconds", 3.1)
        extra.setdefault("minimum_motion_seconds", 9.0)
        extra.setdefault("qwen_verifier_blocks_promotion", False)
        super()._status(state, **extra)

    def _initialize_media(self) -> bool:
        original_highlight_service = base_worker.HighlightStoryArcService
        original_motion_service = base_worker.AutomatedFfmpegMotionStoryService
        original_image_provider = provider_stack_module.ProductionComfyUIImageProvider
        base_worker.HighlightStoryArcService = AlphaHighlightStoryArcService
        base_worker.AutomatedFfmpegMotionStoryService = AlphaFfmpegMotionStoryService
        provider_stack_module.ProductionComfyUIImageProvider = AlphaContinuityComfyUIImageProvider
        try:
            ready = super()._initialize_media()
        finally:
            base_worker.HighlightStoryArcService = original_highlight_service
            base_worker.AutomatedFfmpegMotionStoryService = original_motion_service
            provider_stack_module.ProductionComfyUIImageProvider = original_image_provider

        if ready and self.motion is not None:
            desired = {
                "video_fade_ms": 80,
                "transition_ms": 180,
                "target_shot_seconds": 3.1,
                "minimum_duration_seconds": 9.0,
                "minimum_shots": 3,
                "maximum_shots": 4,
            }
            if any(getattr(self.motion.policy, key) != value for key, value in desired.items()):
                self.motion.policy = self.motion.policy.model_copy(update=desired)

        if ready and not self._alpha_scoring_reindex_complete:
            if not isinstance(self.highlights, AlphaHighlightStoryArcService):
                raise RuntimeError("Alpha media worker did not initialize the calibrated highlight service")
            if not isinstance(self.motion, AlphaFfmpegMotionStoryService):
                raise RuntimeError("Alpha media worker did not initialize the editorial motion service")
            if self.chronicle is None:
                raise RuntimeError("Alpha media worker Chronicle service is unavailable during score reindex")
            selected = self.highlights.reindex_unhighlighted()
            if selected:
                self.chronicle.process_many(selected)
            self._alpha_reindexed_highlights = len(selected)
            self._alpha_scoring_reindex_complete = True
        return ready

    @staticmethod
    def _claim_spec_from_claim(claim, *, sentence_index: int | None = None) -> ClaimSpec:
        return ClaimSpec(
            claim_type=claim.claim_type,
            sentence_index=claim.sentence_index if sentence_index is None else sentence_index,
            subject=claim.subject,
            predicate=claim.predicate,
            target_or_value=claim.target_or_value,
            supporting_allowed_fact_ids=claim.supporting_allowed_fact_ids,
            confidence=claim.confidence,
        )

    def _chapter_and_allowed_facts(self, chapter_id: str):
        if self.chronicle is None or self.media is None:
            raise RuntimeError("Alpha editorial narrative services are unavailable")
        matches = [chapter for chapter in self.chronicle.list_chapters() if chapter.chapter_id == chapter_id]
        if len(matches) != 1:
            raise RuntimeError("Alpha editorial narrative requires exactly one Chronicle chapter")
        chapter = matches[0]
        allowed = set(chapter.allowed_fact_ids)
        found: dict[str, AllowedFact] = {}
        for envelope_id in chapter.source_envelope_ids:
            envelope = self.media.get_envelope(envelope_id)
            if envelope is None:
                raise RuntimeError("Alpha editorial narrative lost a source MediaEnvelope")
            for fact in envelope.allowed_facts:
                if fact.fact_id in allowed:
                    found[fact.fact_id] = fact
        if set(found) != allowed:
            raise RuntimeError("Alpha editorial narrative could not reconstruct the chapter allowlist")
        return chapter, tuple(found[key] for key in sorted(found))

    def _build_alpha_editorial_verification(self, chapter_id: str):
        if self.verifier is None:
            raise RuntimeError("Alpha editorial narrative requires the deterministic verifier")
        chapter, facts = self._chapter_and_allowed_facts(chapter_id)
        selected = _select_alpha_editorial_facts(facts, limit=3)
        if not selected:
            raise RuntimeError("Alpha editorial narrative found no usable canonical facts")

        sentences = tuple(render_alpha_viewer_sentence(fact) for fact in selected)
        prose = " ".join(sentences)
        draft = self.verifier.register_draft(
            chapter_id=chapter.chapter_id,
            prose=prose,
            writer_provider_id=ALPHA_EDITORIAL_PROVIDER_ID,
            writer_provider_local=True,
            writer_provider_paid=False,
        )
        specs = tuple(
            ClaimSpec(
                claim_type=ClaimType.FACTUAL,
                sentence_index=index,
                subject=fact.subject,
                predicate=fact.predicate,
                target_or_value=fact.value,
                supporting_allowed_fact_ids=(fact.fact_id,),
                confidence=1.0,
            )
            for index, fact in enumerate(selected)
        )
        manifest = self.verifier.register_manifest(
            draft_id=draft.draft_id,
            claim_specs=specs,
            auxiliary_assessments=(),
        )
        verification = self.verifier.verify(manifest.manifest_id)
        if not verification.review_ready:
            raise RuntimeError("Alpha editorial narrative did not pass deterministic claim verification")
        return verification

    def _recover_alpha_narrative_verification(self, narrative):
        if self.verifier is None:
            raise RuntimeError("Alpha narrative recovery requires the deterministic verifier")
        manifest = self.verifier.get_manifest(narrative.manifest_id)
        if manifest is None:
            raise RuntimeError("Alpha narrative recovery lost the original claim manifest")

        claim_specs = tuple(self._claim_spec_from_claim(claim) for claim in manifest.claims)
        clean_manifest = self.verifier.register_manifest(
            draft_id=manifest.draft_id,
            claim_specs=claim_specs,
            auxiliary_assessments=(),
        )
        clean_verification = self.verifier.verify(clean_manifest.manifest_id)
        if clean_verification.review_ready:
            self._alpha_narrative_aux_bypass_count += 1
            return clean_verification

        factual_claims = tuple(
            sorted(
                (claim for claim in manifest.claims if claim.claim_type == ClaimType.FACTUAL),
                key=lambda claim: (claim.sentence_index, claim.claim_id),
            )
        )
        if not factual_claims:
            raise RuntimeError("Alpha narrative recovery found no deterministic factual claims")

        fact_only_prose = " ".join(claim.text for claim in factual_claims)
        fact_draft = self.verifier.register_draft(
            chapter_id=manifest.chapter_id,
            prose=fact_only_prose,
            writer_provider_id=ALPHA_FACT_FALLBACK_PROVIDER_ID,
            writer_provider_local=True,
            writer_provider_paid=False,
        )
        fact_specs = tuple(
            self._claim_spec_from_claim(claim, sentence_index=index)
            for index, claim in enumerate(factual_claims)
        )
        fact_manifest = self.verifier.register_manifest(
            draft_id=fact_draft.draft_id,
            claim_specs=fact_specs,
            auxiliary_assessments=(),
        )
        fact_verification = self.verifier.verify(fact_manifest.manifest_id)
        if not fact_verification.review_ready:
            raise RuntimeError("Alpha deterministic fact-only narrative did not pass deterministic claim verification")
        self._alpha_narrative_fact_fallback_count += 1
        return fact_verification

    def _ensure_alpha_review_ready_verification(self, chapter_id: str):
        if self.verifier is None:
            raise RuntimeError("Alpha narrative promotion services are not initialized")
        for verification in self.verifier.list_verifications():
            if verification.chapter_id != chapter_id or not verification.review_ready:
                continue
            draft = self.verifier.get_draft(verification.draft_id)
            if draft is not None and draft.writer_provider_id == ALPHA_EDITORIAL_PROVIDER_ID:
                return verification
        if self.media is None or self.chronicle is None:
            raise RuntimeError("Alpha narrative promotion services are not initialized")
        return self._build_alpha_editorial_verification(chapter_id)

    @staticmethod
    def _slot_for_kind(state, kind: ReferenceKind):
        if kind == ReferenceKind.CURRENT_EQUIPMENT:
            return state.equipment_revision.reference_slot
        matches = [slot for slot in state.identity.reference_slots if slot.kind == kind]
        if len(matches) != 1:
            raise RuntimeError(f"Alpha identity is missing reference slot {kind.value}")
        return matches[0]

    def _ensure_reference_artifact(
        self,
        profile,
        state,
        kind: ReferenceKind,
        *,
        source_reference_ids: tuple[str, ...] = (),
        priority: int,
    ) -> str:
        if self.image is None or self.media is None:
            raise RuntimeError("Alpha reference image services are unavailable")
        slot = self._slot_for_kind(state, kind)
        existing = find_reference_artifact(
            self.media.snapshot(),
            identity_id=state.identity.identity_id,
            reference_id=slot.reference_id,
        )
        if existing is not None:
            return existing

        spec = self.image.plan_reference(profile, kind, width=432, height=768)
        if source_reference_ids:
            spec = with_reference_artifacts(spec, source_reference_ids)
        job = self.image.enqueue(spec, priority=priority)
        terminal = self._run_job_to_terminal(job.job_id)
        if terminal is None or terminal.status != base_worker.JobStatus.COMPLETED:
            raise RuntimeError(f"Alpha {kind.value} reference did not complete")
        artifact = self._artifact_for_job(job.job_id, "image/png")
        if artifact is None:
            raise RuntimeError(f"Alpha {kind.value} reference completed without PNG artifact")
        return artifact["artifact_id"]

    def _ensure_delver_scene_reference(self, profile) -> str:
        if self.identities is None:
            raise RuntimeError("Alpha presentation identity service is unavailable")
        state = self.identities.ensure_identity(profile)
        identity_reference = self._ensure_reference_artifact(
            profile,
            state,
            ReferenceKind.THREE_QUARTER,
            priority=525,
        )
        return self._ensure_reference_artifact(
            profile,
            state,
            ReferenceKind.CURRENT_EQUIPMENT,
            source_reference_ids=(identity_reference,),
            priority=520,
        )

    def _ensure_scene_variants(self, chapter) -> tuple[str, tuple[str, ...]]:
        if self.image is None or self.chronicle is None or self.identities is None:
            raise RuntimeError("Alpha scene-variant services are unavailable")
        profile = self.chronicle.get_profile(chapter.crawl_id, chapter.delver_id)
        if profile is None:
            raise RuntimeError("Alpha scene variants lost their Delver profile")
        scene_reference = self._ensure_delver_scene_reference(profile)
        base_spec = self.image.plan_scene(
            profile,
            chapter,
            reference_artifact_ids=(scene_reference,),
            width=432,
            height=768,
        )
        artifacts: list[str] = []
        for index, staging in enumerate(ALPHA_SCENE_STAGING[1:], start=1):
            variant = alpha_scene_variant_spec(base_spec, index, staging)
            job = self.image.enqueue(variant, priority=510 - index)
            terminal = self._run_job_to_terminal(job.job_id)
            if terminal is None or terminal.status != base_worker.JobStatus.COMPLETED:
                raise RuntimeError(f"Alpha conditioned scene variant {index} did not complete")
            artifact = self._artifact_for_job(job.job_id, "image/png")
            if artifact is None:
                raise RuntimeError(f"Alpha conditioned scene variant {index} has no PNG artifact")
            artifacts.append(artifact["artifact_id"])
        return scene_reference, tuple(artifacts)

    def _promote_one(self, crawl_id: str) -> bool:
        pending = self._featured_pending_chapter(crawl_id)
        if pending is None:
            return False
        chapter, _highlight = pending
        alpha_verification = self._ensure_alpha_review_ready_verification(chapter.chapter_id)
        scene_reference, scene_extras = self._ensure_scene_variants(chapter)
        if self.image is None or self.motion is None:
            raise RuntimeError("Alpha promotion presentation services are unavailable")

        original_image_plan = self.image.plan_scene
        original_motion_plan = self.motion.plan
        original_existing_verification = self._existing_review_ready_verification

        def conditioned_setup_plan(profile, chapter_arg, **kwargs):
            kwargs["reference_artifact_ids"] = (scene_reference,)
            spec = original_image_plan(profile, chapter_arg, **kwargs)
            return alpha_scene_variant_spec(spec, 0, ALPHA_SCENE_STAGING[0])

        def ordered_motion_plan(*, package_job_id: str, image_artifact_ids: tuple[str, ...]):
            ordered = tuple(image_artifact_ids) + scene_extras
            return original_motion_plan(package_job_id=package_job_id, image_artifact_ids=ordered)

        def pinned_verification(chapter_id: str):
            if chapter_id == chapter.chapter_id:
                return alpha_verification
            return original_existing_verification(chapter_id)

        self.image.plan_scene = conditioned_setup_plan
        self.motion.plan = ordered_motion_plan
        self._existing_review_ready_verification = pinned_verification
        try:
            return super()._promote_one(crawl_id)
        finally:
            self.image.plan_scene = original_image_plan
            self.motion.plan = original_motion_plan
            self._existing_review_ready_verification = original_existing_verification


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tail Underreach Alpha canonical history into calibrated local production media"
    )
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--state-directory", type=Path, required=True)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()

    os.environ[ALPHA_VIEWER_FACING_ENV] = "true"

    worker = AlphaLiveProductionMediaWorker(
        repo_root=args.repo_root,
        state_directory=args.state_directory,
        poll_seconds=args.poll_seconds,
    )

    def stop(_signum, _frame):
        worker.request_stop()

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)
    raise SystemExit(worker.run())


if __name__ == "__main__":
    main()
