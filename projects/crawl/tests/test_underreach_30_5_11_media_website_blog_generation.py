from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from sqlalchemy.orm import Session

from livingworld.runtime_checkpoint import payload_digest
from livingworld.underreach_delver_chronicle_profile import (
    ChapterKind,
    ChronicleChapter,
    ChronicleChapterRow,
    ChroniclePolicy,
    DelverChronicleProfileService,
    DelverProfile,
    DelverProfileRow,
    ProfileEquipment,
    ProfileRelationship,
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


CRAWL_ID = "descent_30_5_11_fixture"
REVIEW_READY_TEXT = "Mara held the line while the Underreach watched."
REJECTED_TEXT = "THIS REJECTED NARRATIVE MUST NEVER APPEAR ON THE SITE."


def _stable_id(prefix: str, *parts: object) -> str:
    text = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(text.encode('utf-8')).hexdigest()[:24]}"


def _body(model) -> str:
    return payload_digest(model.model_dump(mode="json", exclude={"digest"}))


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
        "reason_codes": ["fixture:website"],
        "arc_ids": [],
        "policy_digest": detector.policy.digest,
        "presentation_can_mutate_simulation": False,
        "llm_decision_used": False,
        "unreal_dependency": False,
        "provider_invocation_used": False,
    }
    highlight = MediaHighlight.model_validate({**body, "digest": payload_digest(body)})
    validate_highlight(highlight, detector.policy)
    with Session(detector.media.engine) as session:
        session.add(
            MediaHighlightRow(
                highlight_id=highlight.highlight_id,
                envelope_id=highlight.envelope_id,
                crawl_id=highlight.crawl_id,
                policy_digest=highlight.policy_digest,
                total_score=highlight.score.total,
                output_tier=highlight.output_tier.value,
                payload=highlight.model_dump(mode="json"),
                digest=highlight.digest,
            )
        )
        session.commit()
    return highlight


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
    ally = ProfileRelationship(
        delver_id="descender_active",
        strength=0.75,
        dimensions={"trust": 0.75},
    )
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
        "known_allies": [] if status == ProfileStatus.ACTIVE else [ally.model_dump(mode="json")],
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


def _insert_chronicle_rows(
    chronicle: DelverChronicleProfileService,
    detector: HighlightStoryArcService,
) -> tuple[tuple[DelverProfile, ...], tuple[ChronicleChapter, ...]]:
    active_envelope = "media_envelope_active"
    active_event = "crawl_event_active"
    highlight = _insert_highlight(detector, active_envelope, active_event)
    specs = (
        ("descender_active", "Mara Vane", ProfileStatus.ACTIVE, active_envelope, active_event, ChapterKind.HIGHLIGHT, highlight.highlight_id, 10),
        ("descender_retired", "Bram Coil", ProfileStatus.RETREATED, "media_envelope_retired", "crawl_event_retired", ChapterKind.TERMINAL, None, 20),
        ("descender_dead", "Cyra Flint", ProfileStatus.DEAD, "media_envelope_dead", "crawl_event_dead", ChapterKind.TERMINAL, None, 30),
    )
    profiles: list[DelverProfile] = []
    chapters: list[ChronicleChapter] = []
    for delver_id, public_name, status, envelope_id, event_id, kind, highlight_id, tick in specs:
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
            public_name=public_name,
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


def _insert_narratives(verifier: NarrativeClaimVerificationService, active_chapter: ChronicleChapter, retired_chapter: ChronicleChapter) -> None:
    draft_body = {
        "protocol": "underreach.narrative-claim-verification.v1",
        "implementation_version": "30.5.5",
        "phase": "30.5",
        "draft_id": "narrative_draft_review_ready_fixture",
        "chapter_id": active_chapter.chapter_id,
        "prose": REVIEW_READY_TEXT,
        "sentences": [REVIEW_READY_TEXT],
        "writer_provider_id": "local_fixture_writer",
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
        "verification_id": "narrative_verification_review_ready_fixture",
        "draft_id": draft.draft_id,
        "manifest_id": "claim_manifest_review_ready_fixture",
        "chapter_id": active_chapter.chapter_id,
        "status": VerificationStatus.REVIEW_READY.value,
        "review_ready": True,
        "claim_results": [],
        "reason_codes": [],
        "all_sentences_covered": True,
        "deterministic_contradiction_count": 0,
        "unsupported_claim_count": 0,
        "auxiliary_assessment_used": False,
        "auxiliary_model_can_override_deterministic_checks": False,
        "presentation_can_mutate_simulation": False,
        "canonical_authority": False,
        "policy_digest": verifier.policy.digest,
    }
    verification = NarrativeVerification.model_validate({**verification_body, "digest": payload_digest(verification_body)})
    validate_verification(verification)

    rejected_body = {
        "protocol": "underreach.narrative-claim-verification.v1",
        "implementation_version": "30.5.5",
        "phase": "30.5",
        "draft_id": "narrative_draft_rejected_fixture",
        "chapter_id": retired_chapter.chapter_id,
        "prose": REJECTED_TEXT,
        "sentences": [REJECTED_TEXT],
        "writer_provider_id": "local_fixture_writer",
        "writer_provider_local": True,
        "writer_provider_paid": False,
        "generated_prose": True,
        "presentation_can_mutate_simulation": False,
        "canonical_authority": False,
    }
    rejected_draft = NarrativeDraft.model_validate({**rejected_body, "digest": payload_digest(rejected_body)})
    validate_draft(rejected_draft)
    rejected_verification_body = {
        "protocol": "underreach.narrative-claim-verification.v1",
        "implementation_version": "30.5.5",
        "phase": "30.5",
        "verification_id": "narrative_verification_rejected_fixture",
        "draft_id": rejected_draft.draft_id,
        "manifest_id": "claim_manifest_rejected_fixture",
        "chapter_id": retired_chapter.chapter_id,
        "status": VerificationStatus.REJECTED.value,
        "review_ready": False,
        "claim_results": [],
        "reason_codes": ["fixture_rejected"],
        "all_sentences_covered": True,
        "deterministic_contradiction_count": 1,
        "unsupported_claim_count": 0,
        "auxiliary_assessment_used": False,
        "auxiliary_model_can_override_deterministic_checks": False,
        "presentation_can_mutate_simulation": False,
        "canonical_authority": False,
        "policy_digest": verifier.policy.digest,
    }
    rejected_verification = NarrativeVerification.model_validate(
        {**rejected_verification_body, "digest": payload_digest(rejected_verification_body)}
    )
    validate_verification(rejected_verification)
    with Session(verifier.media.engine) as session:
        session.add(NarrativeDraftRow(draft_id=draft.draft_id, chapter_id=draft.chapter_id, payload=draft.model_dump(mode="json"), digest=draft.digest))
        session.add(
            NarrativeVerificationRow(
                verification_id=verification.verification_id,
                draft_id=verification.draft_id,
                manifest_id=verification.manifest_id,
                chapter_id=verification.chapter_id,
                status=verification.status.value,
                review_ready=True,
                payload=verification.model_dump(mode="json"),
                digest=verification.digest,
            )
        )
        session.add(
            NarrativeDraftRow(
                draft_id=rejected_draft.draft_id,
                chapter_id=rejected_draft.chapter_id,
                payload=rejected_draft.model_dump(mode="json"),
                digest=rejected_draft.digest,
            )
        )
        session.add(
            NarrativeVerificationRow(
                verification_id=rejected_verification.verification_id,
                draft_id=rejected_verification.draft_id,
                manifest_id=rejected_verification.manifest_id,
                chapter_id=rejected_verification.chapter_id,
                status=rejected_verification.status.value,
                review_ready=False,
                payload=rejected_verification.model_dump(mode="json"),
                digest=rejected_verification.digest,
            )
        )
        session.commit()


def _completed_artifact_job(media: MediaPersistence, *, job_type: str, payload: dict, worker: str):
    job = media.enqueue_job(job_type=job_type, payload=payload, priority=100)
    lease = media.claim_next(worker)
    assert lease is not None and lease.job.job_id == job.job_id
    return job


def _insert_media_assets(media: MediaPersistence, root: Path, active: DelverProfile, active_chapter: ChronicleChapter) -> dict:
    image_job = _completed_artifact_job(
        media,
        job_type=IMAGE_JOB_TYPE,
        payload={
            "spec": {
                "profile_id": active.profile_id,
                "purpose": "identity_reference",
                "reference_kind": "portrait",
                "identity_version": 1,
            }
        },
        worker="fixture-portrait",
    )
    portrait_rel = "fixture/public/portrait.png"
    portrait_bytes = deterministic_png_bytes(96, 96, "30.5.11-portrait")
    portrait_path = root / portrait_rel
    portrait_path.parent.mkdir(parents=True, exist_ok=True)
    portrait_path.write_bytes(portrait_bytes)
    portrait_artifact = media.record_artifact(
        job_id=image_job.job_id,
        artifact_kind="image/png",
        uri=portrait_rel,
        digest=sha256(portrait_bytes).hexdigest(),
        metadata={"profile_id": active.profile_id, "presentation_only": True},
    )
    media.complete_job(image_job.job_id, resource_usage={"fixture": True})

    published_job = _completed_artifact_job(
        media,
        job_type=MOTION_STORY_JOB_TYPE,
        payload={"fixture": "published-motion-story"},
        worker="fixture-published-video",
    )
    published_rel = "fixture/public/published.mp4"
    published_bytes = b"\x00\x00\x00\x18ftypmp42underreach-published-fixture"
    published_path = root / published_rel
    published_path.parent.mkdir(parents=True, exist_ok=True)
    published_path.write_bytes(published_bytes)
    published_artifact = media.record_artifact(
        job_id=published_job.job_id,
        artifact_kind="video/mp4",
        uri=published_rel,
        digest=sha256(published_bytes).hexdigest(),
        metadata={"story_id": "story_public_fixture", "chapter_id": active_chapter.chapter_id, "presentation_only": True},
    )
    media.complete_job(published_job.job_id, resource_usage={"fixture": True})
    with Session(media.engine) as session:
        row = session.get(MediaArtifactRow, published_artifact)
        assert row is not None
        row.review_status = "approved"
        row.published = True
        session.commit()

    pending_job = _completed_artifact_job(
        media,
        job_type=MOTION_STORY_JOB_TYPE,
        payload={"fixture": "pending-motion-story"},
        worker="fixture-pending-video",
    )
    pending_rel = "fixture/private/pending-secret.mp4"
    pending_bytes = b"PENDING-VIDEO-MUST-NOT-BE-PUBLISHED"
    pending_path = root / pending_rel
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    pending_path.write_bytes(pending_bytes)
    pending_artifact = media.record_artifact(
        job_id=pending_job.job_id,
        artifact_kind="video/mp4",
        uri=pending_rel,
        digest=sha256(pending_bytes).hexdigest(),
        metadata={"story_id": "story_pending_fixture", "chapter_id": active_chapter.chapter_id, "presentation_only": True},
    )
    media.complete_job(pending_job.job_id, resource_usage={"fixture": True})
    return {
        "portrait": portrait_artifact,
        "published": published_artifact,
        "pending": pending_artifact,
        "pending_bytes": pending_bytes,
    }


def _fixture(tmp_path: Path, *, database_url: str = "sqlite://", root: Path | None = None) -> dict:
    media_root = root or tmp_path / "media"
    media = MediaPersistence(database_url)
    media.initialize()
    detector = HighlightStoryArcService(media)
    detector.initialize()
    chronicle = DelverChronicleProfileService(media, highlights=detector)
    chronicle.initialize()
    verifier = NarrativeClaimVerificationService(media, chronicle=chronicle)
    verifier.initialize()
    profiles, chapters = _insert_chronicle_rows(chronicle, detector)
    _insert_narratives(verifier, chapters[0], chapters[1])
    assets = _insert_media_assets(media, media_root, profiles[0], chapters[0])
    service = MediaWebsiteBlogService(
        media,
        chronicle=chronicle,
        verifier=verifier,
        highlights=detector,
        media_root=media_root,
    )
    service.initialize()
    return {
        "media": media,
        "detector": detector,
        "chronicle": chronicle,
        "verifier": verifier,
        "service": service,
        "root": media_root,
        "profiles": profiles,
        "chapters": chapters,
        "assets": assets,
    }


def _all_public_text(public_root: Path) -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in public_root.rglob("*.html"))


def test_plan_contains_only_public_media_semantics(tmp_path: Path) -> None:
    stack = _fixture(tmp_path)
    spec = stack["service"].plan(crawl_id=CRAWL_ID)

    assert spec.profile_count == 3
    assert spec.chapter_count == 3
    assert spec.verified_narrative_count == 1
    assert spec.excluded_unverified_draft_count == 1
    assert spec.highlight_count == 1
    assert spec.portrait_count == 1
    assert spec.published_video_count == 1
    assert len(spec.source_artifact_ids) == 2
    assert spec.static_only is True
    assert spec.live_database_required_after_build is False
    assert spec.canonical_database_opened is False
    assert spec.live_simulation_query_used is False
    assert spec.provider_invocation_used is False
    assert spec.network_dependency is False
    assert spec.unreal_dependency is False
    assert spec.canonical_authority is False
    assert spec.presentation_can_mutate_simulation is False


def test_build_creates_portable_static_site_and_excludes_rejected_or_pending_content(tmp_path: Path) -> None:
    stack = _fixture(tmp_path)
    service = stack["service"]
    spec = service.plan(crawl_id=CRAWL_ID)
    job = service.enqueue(spec, priority=120)
    result = service.run_next()

    assert result is not None and result.status == JobStatus.COMPLETED
    assert result.job_id == job.job_id
    assert result.page_count == 13
    assert result.copied_asset_count == 2
    assert result.artifact_count == 17
    public_root = stack["root"] / result.public_root
    assert (public_root / "index.html").is_file()
    assert (public_root / "delvers" / "index.html").is_file()
    assert (public_root / "chronicles" / "index.html").is_file()
    assert (public_root / "highlights" / "index.html").is_file()
    for status in ("active", "retreated", "dead"):
        assert (public_root / "status" / status / "index.html").is_file()
    text = _all_public_text(public_root)
    assert REVIEW_READY_TEXT in text
    assert REJECTED_TEXT not in text
    assert "story_public_fixture" in text
    assert "story_pending_fixture" not in text
    assert stack["assets"]["pending_bytes"] not in b"".join(path.read_bytes() for path in public_root.rglob("*.*"))
    manifest = json.loads((public_root / "site-manifest.json").read_text(encoding="utf-8"))
    assert manifest["static_only"] is True
    assert manifest["live_database_required_after_build"] is False
    assert manifest["canonical_database_opened"] is False
    assert manifest["live_simulation_query_used"] is False
    assert manifest["provider_invocation_used"] is False
    assert manifest["published_video_count"] == 1


def test_completed_reenqueue_is_idempotent(tmp_path: Path) -> None:
    stack = _fixture(tmp_path)
    service = stack["service"]
    spec = service.plan(crawl_id=CRAWL_ID)
    first_job = service.enqueue(spec, priority=120)
    first = service.run_next()
    assert first is not None and first.status == JobStatus.COMPLETED
    before = service.snapshot()

    second_job = service.enqueue(spec, priority=120)
    after = service.snapshot()

    assert second_job.job_id == first_job.job_id
    assert second_job.status == JobStatus.COMPLETED
    assert before == after
    assert service.run_next() is None


def test_adding_new_approved_public_video_changes_build_identity(tmp_path: Path) -> None:
    stack = _fixture(tmp_path)
    service = stack["service"]
    first = service.plan(crawl_id=CRAWL_ID)

    job = _completed_artifact_job(
        stack["media"],
        job_type=MOTION_STORY_JOB_TYPE,
        payload={"fixture": "second-published-motion-story"},
        worker="fixture-second-published-video",
    )
    relative = "fixture/public/second-published.mp4"
    payload = b"SECOND-PUBLISHED-MOTION-STORY"
    path = stack["root"] / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    artifact = stack["media"].record_artifact(
        job_id=job.job_id,
        artifact_kind="video/mp4",
        uri=relative,
        digest=sha256(payload).hexdigest(),
        metadata={"story_id": "story_public_second", "chapter_id": stack["chapters"][0].chapter_id, "presentation_only": True},
    )
    stack["media"].complete_job(job.job_id, resource_usage={"fixture": True})
    with Session(stack["media"].engine) as session:
        row = session.get(MediaArtifactRow, artifact)
        assert row is not None
        row.review_status = "approved"
        row.published = True
        session.commit()

    second = service.plan(crawl_id=CRAWL_ID)
    assert second.published_video_count == 2
    assert second.source_digest != first.source_digest
    assert second.build_id != first.build_id


def test_unverified_chapter_uses_structured_fallback_without_draft_leak(tmp_path: Path) -> None:
    stack = _fixture(tmp_path)
    service = stack["service"]
    spec = service.plan(crawl_id=CRAWL_ID)
    service.enqueue(spec)
    result = service.run_next()
    assert result is not None and result.status == JobStatus.COMPLETED
    root = stack["root"] / result.public_root / "chronicles"
    pages = list(root.glob("*.html"))
    assert len(pages) == 4
    contents = "\n".join(path.read_text(encoding="utf-8") for path in pages)
    assert "This entry has no verification-cleared prose yet" in contents
    assert REJECTED_TEXT not in contents


def test_file_backed_restart_recovers_same_website_job(tmp_path: Path) -> None:
    database = tmp_path / "media.sqlite3"
    root = tmp_path / "media-root"
    database_url = f"sqlite:///{database.as_posix()}"
    stack = _fixture(tmp_path, database_url=database_url, root=root)
    spec = stack["service"].plan(crawl_id=CRAWL_ID)
    job = stack["service"].enqueue(spec, priority=120)
    lease = stack["media"].claim_next("crashed-website-worker")
    assert lease is not None and lease.job.job_id == job.job_id

    reopened_media = MediaPersistence(database_url)
    reopened_media.initialize()
    assert reopened_media.recover_interrupted_jobs() == 1
    detector = HighlightStoryArcService(reopened_media)
    detector.initialize()
    chronicle = DelverChronicleProfileService(reopened_media, highlights=detector)
    chronicle.initialize()
    verifier = NarrativeClaimVerificationService(reopened_media, chronicle=chronicle)
    verifier.initialize()
    reopened = MediaWebsiteBlogService(
        reopened_media,
        chronicle=chronicle,
        verifier=verifier,
        highlights=detector,
        media_root=root,
    )
    reopened.initialize()
    result = reopened.run_next()

    assert result is not None and result.job_id == job.job_id
    assert result.status == JobStatus.COMPLETED
    final = reopened_media.get_job(job.job_id)
    assert final is not None and final.attempt_count == 2
    assert (root / result.public_root / "index.html").is_file()


def test_static_output_survives_without_database_access(tmp_path: Path) -> None:
    stack = _fixture(tmp_path)
    service = stack["service"]
    spec = service.plan(crawl_id=CRAWL_ID)
    service.enqueue(spec)
    result = service.run_next()
    assert result is not None and result.status == JobStatus.COMPLETED
    public_root = stack["root"] / result.public_root

    stack["media"].engine.dispose()
    assert (public_root / "index.html").read_text(encoding="utf-8").startswith("<!doctype html>")
    assert (public_root / "assets" / "site.css").stat().st_size > 100
    assert len(list((public_root / "assets" / "media").glob("*.png"))) == 1
    assert len(list((public_root / "assets" / "media").glob("*.mp4"))) == 1
