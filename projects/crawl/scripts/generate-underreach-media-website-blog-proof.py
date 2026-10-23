from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from sqlalchemy.orm import Session

from livingworld.runtime_checkpoint import canonical_json, payload_digest
from livingworld.underreach_delver_chronicle_profile import (
    ChapterKind,
    ChronicleChapter,
    ChronicleChapterRow,
    DelverChronicleProfileService,
    DelverProfile,
    DelverProfileRow,
    ProfileEquipment,
    ProfileStatus,
    validate_chapter,
    validate_profile,
)
from livingworld.underreach_ffmpeg_motion_story import JOB_TYPE as MOTION_STORY_JOB_TYPE
from livingworld.underreach_headless_local_image_production import JOB_TYPE as IMAGE_JOB_TYPE, deterministic_png_bytes
from livingworld.underreach_highlight_story_arc import (
    HighlightScore,
    HighlightStoryArcService,
    MediaHighlight,
    MediaHighlightRow,
    tier_for_score,
    validate_highlight,
)
from livingworld.underreach_media_foundation import JobStatus, MediaArtifactRow, MediaPersistence
from livingworld.underreach_media_website_blog import MediaWebsiteBlogService
from livingworld.underreach_narrative_claim_verification import (
    NarrativeClaimVerificationService,
    NarrativeDraft,
    NarrativeDraftRow,
    NarrativeVerification,
    NarrativeVerificationRow,
    VerificationStatus,
    validate_draft,
    validate_verification,
)


PROOF_PROTOCOL = "underreach.media-website-blog-proof.v1"
CRAWL_ID = "descent_30_5_11_proof"
REVIEW_READY_TEXT = "Mara held the line while the Underreach watched."
REJECTED_TEXT = "THIS REJECTED NARRATIVE MUST NEVER APPEAR ON THE SITE."


def _stable_id(prefix: str, *parts: object) -> str:
    text = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(text.encode('utf-8')).hexdigest()[:24]}"


def _insert_highlight(detector: HighlightStoryArcService, envelope_id: str, event_id: str) -> MediaHighlight:
    score = HighlightScore(
        danger=20,
        rarity=15,
        social_stakes=20,
        character_significance=10,
        outcome_reversal=10,
        continuity=12,
        visual_potential=5,
        total=92,
    )
    highlight_id = _stable_id("media_highlight", envelope_id, detector.policy.digest)
    body = {
        "protocol": "underreach.highlight-story-arc.v1",
        "implementation_version": "30.5.3",
        "phase": "30.5",
        "highlight_id": highlight_id,
        "envelope_id": envelope_id,
        "crawl_id": CRAWL_ID,
        "source_event_ids": [event_id],
        "delver_ids": ["descender_active"],
        "score": score.model_dump(mode="json"),
        "output_tier": tier_for_score(score.total, detector.policy).value,
        "reason_codes": ["proof:website"],
        "arc_ids": [],
        "policy_digest": detector.policy.digest,
        "presentation_can_mutate_simulation": False,
        "llm_decision_used": False,
        "unreal_dependency": False,
        "provider_invocation_used": False,
    }
    value = MediaHighlight.model_validate({**body, "digest": payload_digest(body)})
    validate_highlight(value, detector.policy)
    with Session(detector.media.engine) as session:
        session.add(
            MediaHighlightRow(
                highlight_id=value.highlight_id,
                envelope_id=value.envelope_id,
                crawl_id=value.crawl_id,
                policy_digest=value.policy_digest,
                total_score=value.score.total,
                output_tier=value.output_tier.value,
                payload=value.model_dump(mode="json"),
                digest=value.digest,
            )
        )
        session.commit()
    return value


def _chapter(
    *,
    profile_id: str,
    delver_id: str,
    envelope_id: str,
    event_id: str,
    kind: ChapterKind,
    highlight_id: str | None,
    tick: int,
) -> ChronicleChapter:
    chapter_id = _stable_id("chronicle_chapter", profile_id, kind.value, highlight_id or "none", envelope_id)
    terminal = kind == ChapterKind.TERMINAL
    body = {
        "protocol": "underreach.delver-chronicle-profile.v1",
        "implementation_version": "30.5.4",
        "phase": "30.5",
        "chapter_id": chapter_id,
        "profile_id": profile_id,
        "crawl_id": CRAWL_ID,
        "delver_id": delver_id,
        "chapter_kind": kind.value,
        "title_code": "HIGHLIGHT_RESCUE" if not terminal else "TERMINAL_RETREAT" if "retired" in delver_id else "TERMINAL_DEATH",
        "canonical_tick": tick,
        "source_envelope_ids": [envelope_id],
        "source_event_ids": [event_id],
        "allowed_fact_ids": [f"allowed_fact_{delver_id}"],
        "highlight_id": highlight_id,
        "arc_ids": [],
        "trigger_codes": sorted([f"chapter:{kind.value}", "event:FIXTURE"]),
        "terminal": terminal,
        "structured_only": True,
        "claim_verification_required": True,
        "generated_prose_used": False,
        "presentation_can_mutate_simulation": False,
    }
    value = ChronicleChapter.model_validate({**body, "digest": payload_digest(body)})
    validate_chapter(value)
    return value


def _profile(
    *,
    chronicle: DelverChronicleProfileService,
    delver_id: str,
    public_name: str,
    status: ProfileStatus,
    envelope_id: str,
    event_id: str,
    chapter_id: str,
    tick: int,
) -> DelverProfile:
    profile_id = _stable_id("delver_profile", CRAWL_ID, delver_id)
    equipment = ProfileEquipment(
        item_id=f"item_{delver_id}",
        name="Ironbound Relic",
        category="relic",
        rarity="rare",
        slot="hand",
        important=True,
    )
    body = {
        "protocol": "underreach.delver-chronicle-profile.v1",
        "implementation_version": "30.5.4",
        "phase": "30.5",
        "profile_id": profile_id,
        "crawl_id": CRAWL_ID,
        "delver_id": delver_id,
        "public_name": public_name,
        "status": status.value,
        "current_stratum": 2,
        "current_sector": "Sector Ashfall",
        "current_party_id": "party_north" if status == ProfileStatus.ACTIVE else None,
        "current_alliance_ids": ["alliance_ember"] if status == ProfileStatus.ACTIVE else [],
        "known_allies": [],
        "known_rivals": [],
        "notable_equipment": [equipment.model_dump(mode="json")],
        "presentation_identity_ref": f"presentation_identity_{delver_id}",
        "as_of_tick": tick,
        "as_of_envelope_id": envelope_id,
        "source_envelope_ids": [envelope_id],
        "source_event_ids": [event_id],
        "chapter_ids": [chapter_id],
        "pending_quiet_envelope_ids": [],
        "chronicle_closed": status != ProfileStatus.ACTIVE,
        "policy_digest": chronicle.policy.digest,
        "presentation_can_mutate_simulation": False,
        "generated_prose_used": False,
        "unreal_dependency": False,
        "provider_invocation_used": False,
    }
    value = DelverProfile.model_validate({**body, "digest": payload_digest(body)})
    validate_profile(value)
    return value


def _insert_chronicle(chronicle: DelverChronicleProfileService, detector: HighlightStoryArcService):
    active_envelope = "media_envelope_active"
    active_event = "crawl_event_active"
    highlight = _insert_highlight(detector, active_envelope, active_event)
    rows = (
        ("descender_active", "Mara Vane", ProfileStatus.ACTIVE, active_envelope, active_event, ChapterKind.HIGHLIGHT, highlight.highlight_id, 10),
        ("descender_retired", "Bram Coil", ProfileStatus.RETREATED, "media_envelope_retired", "crawl_event_retired", ChapterKind.TERMINAL, None, 20),
        ("descender_dead", "Cyra Flint", ProfileStatus.DEAD, "media_envelope_dead", "crawl_event_dead", ChapterKind.TERMINAL, None, 30),
    )
    profiles = []
    chapters = []
    for delver_id, name, status, envelope_id, event_id, kind, highlight_id, tick in rows:
        profile_id = _stable_id("delver_profile", CRAWL_ID, delver_id)
        chapter = _chapter(
            profile_id=profile_id,
            delver_id=delver_id,
            envelope_id=envelope_id,
            event_id=event_id,
            kind=kind,
            highlight_id=highlight_id,
            tick=tick,
        )
        profile = _profile(
            chronicle=chronicle,
            delver_id=delver_id,
            public_name=name,
            status=status,
            envelope_id=envelope_id,
            event_id=event_id,
            chapter_id=chapter.chapter_id,
            tick=tick,
        )
        profiles.append(profile)
        chapters.append(chapter)
    with Session(chronicle.media.engine) as session:
        for profile in profiles:
            session.add(
                DelverProfileRow(
                    profile_id=profile.profile_id,
                    crawl_id=profile.crawl_id,
                    delver_id=profile.delver_id,
                    status=profile.status.value,
                    as_of_tick=profile.as_of_tick,
                    chronicle_closed=profile.chronicle_closed,
                    payload=profile.model_dump(mode="json"),
                    digest=profile.digest,
                )
            )
        for chapter in chapters:
            session.add(
                ChronicleChapterRow(
                    chapter_id=chapter.chapter_id,
                    profile_id=chapter.profile_id,
                    crawl_id=chapter.crawl_id,
                    delver_id=chapter.delver_id,
                    chapter_kind=chapter.chapter_kind.value,
                    canonical_tick=chapter.canonical_tick,
                    terminal=chapter.terminal,
                    payload=chapter.model_dump(mode="json"),
                    digest=chapter.digest,
                )
            )
        session.commit()
    return tuple(profiles), tuple(chapters)


def _insert_narratives(verifier: NarrativeClaimVerificationService, active: ChronicleChapter, retired: ChronicleChapter) -> None:
    def store(draft_id: str, verification_id: str, chapter_id: str, prose: str, status: VerificationStatus) -> None:
        draft_body = {
            "protocol": "underreach.narrative-claim-verification.v1",
            "implementation_version": "30.5.5",
            "phase": "30.5",
            "draft_id": draft_id,
            "chapter_id": chapter_id,
            "prose": prose,
            "sentences": [prose],
            "writer_provider_id": "local_proof_writer",
            "writer_provider_local": True,
            "writer_provider_paid": False,
            "generated_prose": True,
            "presentation_can_mutate_simulation": False,
            "canonical_authority": False,
        }
        draft = NarrativeDraft.model_validate({**draft_body, "digest": payload_digest(draft_body)})
        validate_draft(draft)
        verification_body = {
            "protocol": "underreach.narrative-claim-verification.v1",
            "implementation_version": "30.5.5",
            "phase": "30.5",
            "verification_id": verification_id,
            "draft_id": draft.draft_id,
            "manifest_id": f"manifest_{verification_id}",
            "chapter_id": chapter_id,
            "status": status.value,
            "review_ready": status == VerificationStatus.REVIEW_READY,
            "claim_results": [],
            "reason_codes": [] if status == VerificationStatus.REVIEW_READY else ["proof_rejected"],
            "all_sentences_covered": True,
            "deterministic_contradiction_count": 0 if status == VerificationStatus.REVIEW_READY else 1,
            "unsupported_claim_count": 0,
            "auxiliary_assessment_used": False,
            "auxiliary_model_can_override_deterministic_checks": False,
            "presentation_can_mutate_simulation": False,
            "canonical_authority": False,
            "policy_digest": verifier.policy.digest,
        }
        verification = NarrativeVerification.model_validate({**verification_body, "digest": payload_digest(verification_body)})
        validate_verification(verification)
        with Session(verifier.media.engine) as session:
            session.add(NarrativeDraftRow(draft_id=draft.draft_id, chapter_id=draft.chapter_id, payload=draft.model_dump(mode="json"), digest=draft.digest))
            session.add(
                NarrativeVerificationRow(
                    verification_id=verification.verification_id,
                    draft_id=verification.draft_id,
                    manifest_id=verification.manifest_id,
                    chapter_id=verification.chapter_id,
                    status=verification.status.value,
                    review_ready=verification.review_ready,
                    payload=verification.model_dump(mode="json"),
                    digest=verification.digest,
                )
            )
            session.commit()
    store("draft_review_ready_proof", "verification_review_ready_proof", active.chapter_id, REVIEW_READY_TEXT, VerificationStatus.REVIEW_READY)
    store("draft_rejected_proof", "verification_rejected_proof", retired.chapter_id, REJECTED_TEXT, VerificationStatus.REJECTED)


def _claim(media: MediaPersistence, *, job_type: str, payload: dict, worker: str):
    job = media.enqueue_job(job_type=job_type, payload=payload, priority=100)
    lease = media.claim_next(worker)
    if lease is None or lease.job.job_id != job.job_id:
        raise RuntimeError("30.5.11 proof could not claim fixture media job")
    return job


def _insert_assets(media: MediaPersistence, root: Path, active: DelverProfile, active_chapter: ChronicleChapter) -> dict:
    image_job = _claim(
        media,
        job_type=IMAGE_JOB_TYPE,
        payload={"spec": {"profile_id": active.profile_id, "purpose": "identity_reference", "reference_kind": "portrait", "identity_version": 1}},
        worker="proof-portrait",
    )
    portrait_rel = "fixture/public/portrait.png"
    portrait = deterministic_png_bytes(96, 96, "30.5.11-proof-portrait")
    portrait_path = root / portrait_rel
    portrait_path.parent.mkdir(parents=True, exist_ok=True)
    portrait_path.write_bytes(portrait)
    portrait_id = media.record_artifact(
        job_id=image_job.job_id,
        artifact_kind="image/png",
        uri=portrait_rel,
        digest=sha256(portrait).hexdigest(),
        metadata={"profile_id": active.profile_id, "presentation_only": True},
    )
    media.complete_job(image_job.job_id, resource_usage={"proof_fixture": True})

    public_job = _claim(media, job_type=MOTION_STORY_JOB_TYPE, payload={"proof": "published"}, worker="proof-public-video")
    public_rel = "fixture/public/published.mp4"
    public_bytes = b"\x00\x00\x00\x18ftypmp42underreach-30.5.11-public"
    public_path = root / public_rel
    public_path.write_bytes(public_bytes)
    public_id = media.record_artifact(
        job_id=public_job.job_id,
        artifact_kind="video/mp4",
        uri=public_rel,
        digest=sha256(public_bytes).hexdigest(),
        metadata={"story_id": "story_public_proof", "chapter_id": active_chapter.chapter_id, "presentation_only": True},
    )
    media.complete_job(public_job.job_id, resource_usage={"proof_fixture": True})
    with Session(media.engine) as session:
        row = session.get(MediaArtifactRow, public_id)
        if row is None:
            raise RuntimeError("30.5.11 proof lost public video artifact")
        row.review_status = "approved"
        row.published = True
        session.commit()

    pending_job = _claim(media, job_type=MOTION_STORY_JOB_TYPE, payload={"proof": "pending"}, worker="proof-pending-video")
    pending_rel = "fixture/private/pending.mp4"
    pending_bytes = b"PENDING-VIDEO-MUST-NOT-BE-PUBLISHED"
    pending_path = root / pending_rel
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    pending_path.write_bytes(pending_bytes)
    pending_id = media.record_artifact(
        job_id=pending_job.job_id,
        artifact_kind="video/mp4",
        uri=pending_rel,
        digest=sha256(pending_bytes).hexdigest(),
        metadata={"story_id": "story_pending_proof", "chapter_id": active_chapter.chapter_id, "presentation_only": True},
    )
    media.complete_job(pending_job.job_id, resource_usage={"proof_fixture": True})
    return {"portrait_id": portrait_id, "public_id": public_id, "pending_id": pending_id, "pending_bytes": pending_bytes}


def _build_fixture(database_url: str, root: Path):
    media = MediaPersistence(database_url)
    media.initialize()
    detector = HighlightStoryArcService(media)
    detector.initialize()
    chronicle = DelverChronicleProfileService(media, highlights=detector)
    chronicle.initialize()
    verifier = NarrativeClaimVerificationService(media, chronicle=chronicle)
    verifier.initialize()
    profiles, chapters = _insert_chronicle(chronicle, detector)
    _insert_narratives(verifier, chapters[0], chapters[1])
    assets = _insert_assets(media, root, profiles[0], chapters[0])
    service = MediaWebsiteBlogService(
        media,
        chronicle=chronicle,
        verifier=verifier,
        highlights=detector,
        media_root=root,
    )
    service.initialize()
    return media, detector, chronicle, verifier, service, profiles, chapters, assets


def _reopen(database_url: str, root: Path):
    media = MediaPersistence(database_url)
    media.initialize()
    detector = HighlightStoryArcService(media)
    detector.initialize()
    chronicle = DelverChronicleProfileService(media, highlights=detector)
    chronicle.initialize()
    verifier = NarrativeClaimVerificationService(media, chronicle=chronicle)
    verifier.initialize()
    service = MediaWebsiteBlogService(
        media,
        chronicle=chronicle,
        verifier=verifier,
        highlights=detector,
        media_root=root,
    )
    service.initialize()
    return media, service


def _static_files(root: Path) -> list[dict[str, str]]:
    return [
        {"path": path.relative_to(root).as_posix(), "sha256": sha256(path.read_bytes()).hexdigest()}
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    ]


def generate(output: Path, *, seed: str) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    database = output.with_suffix(".sqlite3")
    if database.exists():
        database.unlink()
    database_url = f"sqlite:///{database.as_posix()}"
    root = output.parent / f"site-media-{sha256(seed.encode('utf-8')).hexdigest()[:10]}"
    if root.exists():
        import shutil
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    media, detector, chronicle, verifier, service, profiles, chapters, assets = _build_fixture(database_url, root)
    spec = service.plan(crawl_id=CRAWL_ID)
    job = service.enqueue(spec, priority=120)
    crash = media.claim_next("30-5-11-proof-crashed-worker")
    if crash is None or crash.job.job_id != job.job_id:
        raise RuntimeError("30.5.11 proof could not claim restart probe")

    reopened_media, reopened = _reopen(database_url, root)
    recovered_count = reopened_media.recover_interrupted_jobs()
    result = reopened.run_next()
    if result is None or result.status != JobStatus.COMPLETED:
        raise RuntimeError("30.5.11 proof website build did not complete")
    final_job = reopened_media.get_job(job.job_id)
    if final_job is None:
        raise RuntimeError("30.5.11 proof website job disappeared")

    snapshot_before_repeat = reopened.snapshot()
    repeat_spec = reopened.plan(crawl_id=CRAWL_ID)
    repeat_job = reopened.enqueue(repeat_spec, priority=120)
    snapshot_after_repeat = reopened.snapshot()

    public_root = root / result.public_root
    manifest = json.loads((public_root / "site-manifest.json").read_text(encoding="utf-8"))
    html_text = "\n".join(path.read_text(encoding="utf-8") for path in public_root.rglob("*.html"))
    all_bytes = b"".join(path.read_bytes() for path in sorted(item for item in public_root.rglob("*") if item.is_file()))
    files = _static_files(public_root)
    static_digest = payload_digest(files)
    copied_pngs = list((public_root / "assets" / "media").glob("*.png"))
    copied_mp4s = list((public_root / "assets" / "media").glob("*.mp4"))

    reopened_media.engine.dispose()
    static_survives_db_close = (public_root / "index.html").is_file() and (public_root / "assets" / "site.css").is_file()

    site_snapshot = reopened.snapshot()
    body = {
        "protocol": PROOF_PROTOCOL,
        "slice_protocol": site_snapshot["protocol"],
        "implementation_version": site_snapshot["implementation_version"],
        "phase": site_snapshot["phase"],
        "seed": seed,
        "authority_contract": {
            "authoritative": site_snapshot["authoritative"],
            "canonical_owner": site_snapshot["canonical_owner"],
            "presentation_can_mutate_simulation": site_snapshot["presentation_can_mutate_simulation"],
            "canonical_database_opened": site_snapshot["canonical_database_opened"],
            "live_simulation_query_used": site_snapshot["live_simulation_query_used"],
            "provider_invocation_used": site_snapshot["provider_invocation_used"],
            "network_dependency": site_snapshot["network_dependency"],
            "unreal_dependency": site_snapshot["unreal_dependency"],
            "live_database_required_after_build": site_snapshot["live_database_required_after_build"],
            "static_only": site_snapshot["static_only"],
        },
        "public_input": {
            "profile_count": spec.profile_count,
            "chapter_count": spec.chapter_count,
            "verified_narrative_count": spec.verified_narrative_count,
            "excluded_unverified_draft_count": spec.excluded_unverified_draft_count,
            "highlight_count": spec.highlight_count,
            "portrait_count": spec.portrait_count,
            "published_video_count": spec.published_video_count,
            "source_artifact_count": len(spec.source_artifact_ids),
            "source_digest": spec.source_digest,
        },
        "content_guards": {
            "review_ready_text_present": REVIEW_READY_TEXT in html_text,
            "rejected_text_absent": REJECTED_TEXT not in html_text,
            "pending_story_absent": "story_pending_proof" not in html_text,
            "pending_video_bytes_absent": assets["pending_bytes"] not in all_bytes,
            "approved_story_present": "story_public_proof" in html_text,
            "active_status_page": (public_root / "status" / "active" / "index.html").is_file(),
            "retreated_status_page": (public_root / "status" / "retreated" / "index.html").is_file(),
            "dead_status_page": (public_root / "status" / "dead" / "index.html").is_file(),
            "copied_portrait_count": len(copied_pngs),
            "copied_video_count": len(copied_mp4s),
        },
        "build": {
            "build_id": spec.build_id,
            "job_id": job.job_id,
            "page_count": result.page_count,
            "copied_asset_count": result.copied_asset_count,
            "artifact_count": result.artifact_count,
            "manifest_digest": result.manifest_digest,
            "manifest_source_digest": manifest["source_digest"],
            "static_file_count": len(files),
            "static_file_digest": static_digest,
            "static_survives_database_close": static_survives_db_close,
        },
        "restart": {
            "recovered_count": recovered_count,
            "same_job": result.job_id == job.job_id,
            "attempt_count": final_job.attempt_count,
            "completed": final_job.status == JobStatus.COMPLETED,
        },
        "idempotency": {
            "repeat_spec_same_build": repeat_spec.build_id == spec.build_id,
            "repeat_same_job": repeat_job.job_id == job.job_id,
            "snapshot_equal_after_repeat": snapshot_before_repeat == snapshot_after_repeat,
        },
        "media": {
            "job_count": site_snapshot["job_count"],
            "artifact_count": site_snapshot["artifact_count"],
            "job_digest": site_snapshot["job_digest"],
            "artifact_digest": site_snapshot["artifact_digest"],
            "snapshot_digest": site_snapshot["digest"],
        },
    }
    proof = {**body, "digest": payload_digest(body)}
    output.write_text(canonical_json(proof), encoding="utf-8")
    print(json.dumps({
        "digest": proof["digest"],
        "pages": result.page_count,
        "assets": result.copied_asset_count,
        "artifacts": result.artifact_count,
        "restart_attempts": final_job.attempt_count,
    }, sort_keys=True))
    return proof


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", required=True)
    args = parser.parse_args()
    generate(args.output, seed=args.seed)


if __name__ == "__main__":
    main()
