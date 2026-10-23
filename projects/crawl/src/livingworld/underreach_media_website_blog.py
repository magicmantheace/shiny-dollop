"""Static media-owned website/blog generation for Underreach Phase 30.5.11.

30.5.11 consumes only presentation/media state already persisted by accepted
Phase 30.5 slices. It renders portable static HTML, CSS, selected presentation
images, and explicitly approved/published promotional videos. Generated prose is
published only when the accepted 30.5.5 verifier marked it REVIEW_READY.

The generator never opens the canonical Crawl database, never queries a live
simulation mutation path, never invokes Unreal or an AI/media provider, and never
feeds website output back into canonical truth. The output is a plain static
file tree that can be served without Python or SQLite.
"""
from __future__ import annotations

from hashlib import sha256
from html import escape
import json
import posixpath
from pathlib import Path, PurePosixPath
import re
import shutil
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .runtime_checkpoint import canonical_json, payload_digest
from .underreach_delver_chronicle_profile import (
    ChronicleChapter,
    DelverChronicleProfileService,
    DelverProfile,
    ProfileStatus,
    validate_chapter,
    validate_profile,
)
from .underreach_headless_local_image_production import (
    JOB_TYPE as IMAGE_JOB_TYPE,
    ImagePurpose,
)
from .underreach_highlight_story_arc import HighlightStoryArcService, MediaHighlight, validate_highlight
from .underreach_local_video_enhancement import JOB_TYPE as VIDEO_ENHANCEMENT_JOB_TYPE
from .underreach_ffmpeg_motion_story import JOB_TYPE as MOTION_STORY_JOB_TYPE
from .underreach_media_foundation import JobStatus, MediaJob, MediaPersistence
from .underreach_narrative_claim_verification import (
    NarrativeClaimVerificationService,
    NarrativeDraft,
    NarrativeVerification,
    VerificationStatus,
    validate_draft,
    validate_verification,
)


PROTOCOL = "underreach.media-website-blog.v1"
IMPLEMENTATION_VERSION = "30.5.11"
PHASE = "30.5"
JOB_TYPE = "underreach.website.generate"
SITE_SCHEMA_VERSION = "underreach.static-site.v1"


class MediaWebsiteError(ValueError):
    """Raised when 30.5.11 public-static-site invariants are violated."""


class WebsitePolicy(BaseModel):
    """Deterministic publication policy for the local static site."""

    model_config = ConfigDict(frozen=True)

    site_title: str = "The Underreach"
    site_subtitle: str = "Living chronicles from the crawl"
    output_directory: str = "website"
    publish_review_ready_prose: bool = True
    require_approved_published_video: bool = True
    copy_portraits: bool = True
    copy_published_video: bool = True
    max_equipment_items: int = Field(default=12, ge=1, le=64)
    max_relationships_per_kind: int = Field(default=8, ge=1, le=32)

    @model_validator(mode="after")
    def validate_policy(self) -> "WebsitePolicy":
        if not self.site_title.strip() or not self.site_subtitle.strip():
            raise ValueError("website title/subtitle cannot be blank")
        value = PurePosixPath(self.output_directory)
        if value.is_absolute() or ".." in value.parts or not self.output_directory.strip():
            raise ValueError("website output directory must be a safe relative path")
        return self

    @property
    def digest(self) -> str:
        return payload_digest(self.model_dump(mode="json"))


class PublicNarrative(BaseModel):
    model_config = ConfigDict(frozen=True)

    chapter_id: str
    draft_id: str
    verification_id: str
    prose: str
    draft_digest: str
    verification_digest: str
    digest: str


class PublicMediaAsset(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_artifact_id: str
    source_job_id: str
    artifact_kind: str
    source_uri: str
    source_digest: str
    public_uri: str
    role: str
    profile_id: str | None = None
    chapter_id: str | None = None
    story_id: str | None = None
    digest: str


class WebsiteBuildSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol: str = PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    phase: str = PHASE
    site_schema_version: str = SITE_SCHEMA_VERSION
    build_id: str
    crawl_id: str | None = None
    crawl_ids: tuple[str, ...]
    profile_count: int = Field(ge=0)
    chapter_count: int = Field(ge=0)
    verified_narrative_count: int = Field(ge=0)
    excluded_unverified_draft_count: int = Field(ge=0)
    highlight_count: int = Field(ge=0)
    portrait_count: int = Field(ge=0)
    published_video_count: int = Field(ge=0)
    source_artifact_ids: tuple[str, ...]
    source_job_ids: tuple[str, ...]
    source_digest: str
    policy_digest: str
    static_only: bool = True
    live_database_required_after_build: bool = False
    canonical_database_opened: bool = False
    live_simulation_query_used: bool = False
    provider_invocation_used: bool = False
    network_dependency: bool = False
    unreal_dependency: bool = False
    canonical_authority: bool = False
    presentation_can_mutate_simulation: bool = False
    digest: str


class WebsiteBuildResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    build_id: str
    job_id: str
    status: JobStatus
    public_root: str | None = None
    manifest_artifact_id: str | None = None
    manifest_uri: str | None = None
    manifest_digest: str | None = None
    page_count: int = 0
    copied_asset_count: int = 0
    artifact_count: int = 0
    reason_code: str | None = None
    canonical_authority: bool = False
    presentation_can_mutate_simulation: bool = False


def _stable_id(prefix: str, *parts: object) -> str:
    text = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(text.encode('utf-8')).hexdigest()[:24]}"


def _body_digest(model: BaseModel) -> str:
    return payload_digest(model.model_dump(mode="json", exclude={"digest"}))


def _safe_relative_uri(uri: str) -> PurePosixPath:
    value = PurePosixPath(uri)
    if value.is_absolute() or ".." in value.parts or "://" in uri:
        raise MediaWebsiteError("website source URI must be a safe relative media path")
    return value


def _slug(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-").lower()
    if not normalized:
        normalized = "item"
    suffix = sha256(value.encode("utf-8")).hexdigest()[:8]
    return f"{normalized[:72]}-{suffix}"


def _humanize(value: str) -> str:
    text = re.sub(r"[_:-]+", " ", value).strip()
    return " ".join(part.capitalize() for part in text.split()) or "Chronicle Entry"


def _relative_href(page_path: str, target_path: str) -> str:
    base = posixpath.dirname(page_path) or "."
    return posixpath.relpath(target_path, base)


def validate_public_narrative(value: PublicNarrative) -> bool:
    body = value.model_dump(mode="json", exclude={"digest"})
    if not value.prose.strip() or value.digest != payload_digest(body):
        raise MediaWebsiteError("public narrative digest/content is invalid")
    return True


def validate_public_asset(value: PublicMediaAsset) -> bool:
    _safe_relative_uri(value.source_uri)
    _safe_relative_uri(value.public_uri)
    if not value.source_artifact_id or not value.source_job_id or not value.source_digest:
        raise MediaWebsiteError("public media asset provenance is incomplete")
    if value.digest != _body_digest(value):
        raise MediaWebsiteError("public media asset digest mismatch")
    return True


def validate_website_spec(spec: WebsiteBuildSpec) -> bool:
    if spec.protocol != PROTOCOL or spec.implementation_version != IMPLEMENTATION_VERSION or spec.phase != PHASE:
        raise MediaWebsiteError("website build protocol/version mismatch")
    if spec.site_schema_version != SITE_SCHEMA_VERSION:
        raise MediaWebsiteError("website schema version mismatch")
    if tuple(sorted(set(spec.crawl_ids))) != spec.crawl_ids:
        raise MediaWebsiteError("website crawl IDs are not normalized")
    if tuple(sorted(set(spec.source_artifact_ids))) != spec.source_artifact_ids:
        raise MediaWebsiteError("website source artifact IDs are not normalized")
    if tuple(sorted(set(spec.source_job_ids))) != spec.source_job_ids:
        raise MediaWebsiteError("website source job IDs are not normalized")
    if spec.crawl_id is not None and spec.crawl_id not in spec.crawl_ids:
        raise MediaWebsiteError("website crawl scope is inconsistent")
    if (
        not spec.static_only
        or spec.live_database_required_after_build
        or spec.canonical_database_opened
        or spec.live_simulation_query_used
        or spec.provider_invocation_used
        or spec.network_dependency
        or spec.unreal_dependency
        or spec.canonical_authority
        or spec.presentation_can_mutate_simulation
    ):
        raise MediaWebsiteError("website escaped the static media-only authority boundary")
    expected_id = _stable_id("website_build", spec.source_digest, spec.policy_digest, spec.crawl_id or "all")
    if spec.build_id != expected_id:
        raise MediaWebsiteError("website deterministic build identity mismatch")
    if spec.digest != _body_digest(spec):
        raise MediaWebsiteError("website build spec digest mismatch")
    return True


class MediaWebsiteBlogService:
    """Build a portable public static site from media-owned state only."""

    def __init__(
        self,
        media: MediaPersistence,
        *,
        chronicle: DelverChronicleProfileService,
        verifier: NarrativeClaimVerificationService,
        highlights: HighlightStoryArcService,
        media_root: str | Path,
        policy: WebsitePolicy | None = None,
    ) -> None:
        self.media = media
        self.chronicle = chronicle
        self.verifier = verifier
        self.highlights = highlights
        self.media_root = Path(media_root)
        self.policy = policy or WebsitePolicy()

    def initialize(self) -> None:
        self.media_root.mkdir(parents=True, exist_ok=True)

    def _media_snapshot(self) -> dict[str, Any]:
        return self.media.snapshot()

    @staticmethod
    def _jobs_by_id(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {item["job_id"]: item for item in snapshot["jobs"]}

    def _verify_source_file(self, artifact: dict[str, Any]) -> Path:
        relative = _safe_relative_uri(str(artifact["uri"]))
        path = self.media_root.joinpath(*relative.parts)
        if not path.is_file():
            raise MediaWebsiteError("website source media file is missing")
        actual = sha256(path.read_bytes()).hexdigest()
        if actual != artifact["digest"]:
            raise MediaWebsiteError("website source media file digest changed")
        return path

    def _public_narratives(
        self,
        chapter_ids: set[str],
    ) -> tuple[dict[str, PublicNarrative], int]:
        drafts = {item.draft_id: item for item in self.verifier.list_drafts()}
        for draft in drafts.values():
            validate_draft(draft)
        verifications = self.verifier.list_verifications()
        for verification in verifications:
            validate_verification(verification)
        review_ready = [
            item
            for item in verifications
            if item.chapter_id in chapter_ids
            and item.status == VerificationStatus.REVIEW_READY
            and item.review_ready
        ]
        by_chapter: dict[str, list[NarrativeVerification]] = {}
        for verification in review_ready:
            by_chapter.setdefault(verification.chapter_id, []).append(verification)
        result: dict[str, PublicNarrative] = {}
        if self.policy.publish_review_ready_prose:
            for chapter_id in sorted(by_chapter):
                verification = sorted(by_chapter[chapter_id], key=lambda item: item.verification_id)[0]
                draft = drafts.get(verification.draft_id)
                if draft is None or draft.chapter_id != chapter_id:
                    raise MediaWebsiteError("review-ready verification lost its narrative draft")
                body = {
                    "chapter_id": chapter_id,
                    "draft_id": draft.draft_id,
                    "verification_id": verification.verification_id,
                    "prose": draft.prose,
                    "draft_digest": draft.digest,
                    "verification_digest": verification.digest,
                }
                public = PublicNarrative.model_validate({**body, "digest": payload_digest(body)})
                validate_public_narrative(public)
                result[chapter_id] = public
        relevant_drafts = [item for item in drafts.values() if item.chapter_id in chapter_ids]
        selected_draft_ids = {item.draft_id for item in result.values()}
        excluded = len([item for item in relevant_drafts if item.draft_id not in selected_draft_ids])
        return result, excluded

    def _portrait_assets(
        self,
        profiles: tuple[DelverProfile, ...],
        snapshot: dict[str, Any],
    ) -> dict[str, PublicMediaAsset]:
        if not self.policy.copy_portraits:
            return {}
        jobs = self._jobs_by_id(snapshot)
        artifacts_by_job: dict[str, list[dict[str, Any]]] = {}
        for artifact in snapshot["artifacts"]:
            artifacts_by_job.setdefault(artifact["job_id"], []).append(artifact)
        profile_ids = {profile.profile_id for profile in profiles}
        candidates: dict[str, list[tuple[int, str, dict[str, Any]]]] = {}
        for job_id, job in jobs.items():
            if job["job_type"] != IMAGE_JOB_TYPE or job["status"] != JobStatus.COMPLETED.value:
                continue
            spec = (job.get("payload") or {}).get("spec") or {}
            if spec.get("profile_id") not in profile_ids:
                continue
            if spec.get("purpose") != ImagePurpose.IDENTITY_REFERENCE.value or spec.get("reference_kind") != "portrait":
                continue
            images = [item for item in artifacts_by_job.get(job_id, []) if item["artifact_kind"] == "image/png"]
            if len(images) != 1:
                continue
            artifact = images[0]
            self._verify_source_file(artifact)
            profile_id = str(spec["profile_id"])
            candidates.setdefault(profile_id, []).append((int(spec.get("identity_version") or 0), artifact["artifact_id"], artifact))
        result: dict[str, PublicMediaAsset] = {}
        for profile_id in sorted(candidates):
            _, _, artifact = sorted(candidates[profile_id], key=lambda item: (-item[0], item[1]))[0]
            public_uri = f"assets/media/{artifact['artifact_id']}.png"
            body = {
                "source_artifact_id": artifact["artifact_id"],
                "source_job_id": artifact["job_id"],
                "artifact_kind": artifact["artifact_kind"],
                "source_uri": artifact["uri"],
                "source_digest": artifact["digest"],
                "public_uri": public_uri,
                "role": "profile_portrait",
                "profile_id": profile_id,
                "chapter_id": None,
                "story_id": None,
            }
            value = PublicMediaAsset.model_validate({**body, "digest": payload_digest(body)})
            validate_public_asset(value)
            result[profile_id] = value
        return result

    def _published_videos(self, snapshot: dict[str, Any]) -> tuple[PublicMediaAsset, ...]:
        if not self.policy.copy_published_video:
            return ()
        jobs = self._jobs_by_id(snapshot)
        result: list[PublicMediaAsset] = []
        for artifact in snapshot["artifacts"]:
            if artifact["artifact_kind"] != "video/mp4":
                continue
            job = jobs.get(artifact["job_id"])
            if job is None or job["status"] != JobStatus.COMPLETED.value:
                continue
            if job["job_type"] not in {MOTION_STORY_JOB_TYPE, VIDEO_ENHANCEMENT_JOB_TYPE}:
                continue
            if self.policy.require_approved_published_video and not (
                artifact.get("review_status") == "approved" and bool(artifact.get("published"))
            ):
                continue
            self._verify_source_file(artifact)
            metadata = dict(artifact.get("metadata") or {})
            suffix = "enhanced_clip" if job["job_type"] == VIDEO_ENHANCEMENT_JOB_TYPE else "motion_story"
            public_uri = f"assets/media/{artifact['artifact_id']}.mp4"
            body = {
                "source_artifact_id": artifact["artifact_id"],
                "source_job_id": artifact["job_id"],
                "artifact_kind": artifact["artifact_kind"],
                "source_uri": artifact["uri"],
                "source_digest": artifact["digest"],
                "public_uri": public_uri,
                "role": suffix,
                "profile_id": None,
                "chapter_id": metadata.get("chapter_id"),
                "story_id": metadata.get("story_id"),
            }
            value = PublicMediaAsset.model_validate({**body, "digest": payload_digest(body)})
            validate_public_asset(value)
            result.append(value)
        return tuple(sorted(result, key=lambda item: (item.story_id or "", item.role, item.source_artifact_id)))

    def _public_inputs(self, *, crawl_id: str | None) -> dict[str, Any]:
        profiles = self.chronicle.list_profiles(crawl_id=crawl_id)
        for profile in profiles:
            validate_profile(profile)
        chapters = self.chronicle.list_chapters(crawl_id=crawl_id)
        for chapter in chapters:
            validate_chapter(chapter)
        allowed_profiles = {item.profile_id for item in profiles}
        chapters = tuple(item for item in chapters if item.profile_id in allowed_profiles)
        chapter_ids = {item.chapter_id for item in chapters}
        narratives, excluded = self._public_narratives(chapter_ids)
        highlights = self.highlights.list_highlights(crawl_id=crawl_id)
        for highlight in highlights:
            validate_highlight(highlight, self.highlights.policy)
        snapshot = self._media_snapshot()
        portraits = self._portrait_assets(profiles, snapshot)
        videos = self._published_videos(snapshot)
        crawl_ids = tuple(sorted({profile.crawl_id for profile in profiles}))
        public_semantics = {
            "profiles": [item.model_dump(mode="json") for item in profiles],
            "chapters": [item.model_dump(mode="json") for item in chapters],
            "narratives": [narratives[key].model_dump(mode="json") for key in sorted(narratives)],
            "highlights": [item.model_dump(mode="json") for item in highlights],
            "portraits": [portraits[key].model_dump(mode="json") for key in sorted(portraits)],
            "videos": [item.model_dump(mode="json") for item in videos],
            "crawl_id": crawl_id,
            "crawl_ids": list(crawl_ids),
        }
        assets = tuple(list(portraits.values()) + list(videos))
        return {
            "profiles": profiles,
            "chapters": chapters,
            "narratives": narratives,
            "excluded_unverified_draft_count": excluded,
            "highlights": highlights,
            "portraits": portraits,
            "videos": videos,
            "assets": assets,
            "crawl_ids": crawl_ids,
            "source_digest": payload_digest(public_semantics),
        }

    def plan(self, *, crawl_id: str | None = None) -> WebsiteBuildSpec:
        values = self._public_inputs(crawl_id=crawl_id)
        source_artifact_ids = tuple(sorted(item.source_artifact_id for item in values["assets"]))
        source_job_ids = tuple(sorted({item.source_job_id for item in values["assets"]}))
        build_id = _stable_id("website_build", values["source_digest"], self.policy.digest, crawl_id or "all")
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "site_schema_version": SITE_SCHEMA_VERSION,
            "build_id": build_id,
            "crawl_id": crawl_id,
            "crawl_ids": list(values["crawl_ids"]),
            "profile_count": len(values["profiles"]),
            "chapter_count": len(values["chapters"]),
            "verified_narrative_count": len(values["narratives"]),
            "excluded_unverified_draft_count": values["excluded_unverified_draft_count"],
            "highlight_count": len(values["highlights"]),
            "portrait_count": len(values["portraits"]),
            "published_video_count": len(values["videos"]),
            "source_artifact_ids": list(source_artifact_ids),
            "source_job_ids": list(source_job_ids),
            "source_digest": values["source_digest"],
            "policy_digest": self.policy.digest,
            "static_only": True,
            "live_database_required_after_build": False,
            "canonical_database_opened": False,
            "live_simulation_query_used": False,
            "provider_invocation_used": False,
            "network_dependency": False,
            "unreal_dependency": False,
            "canonical_authority": False,
            "presentation_can_mutate_simulation": False,
        }
        spec = WebsiteBuildSpec.model_validate({**body, "digest": payload_digest(body)})
        validate_website_spec(spec)
        return spec

    def enqueue(self, spec: WebsiteBuildSpec, *, priority: int = 100) -> MediaJob:
        validate_website_spec(spec)
        return self.media.enqueue_job(
            job_type=JOB_TYPE,
            payload={
                "protocol": PROTOCOL,
                "implementation_version": IMPLEMENTATION_VERSION,
                "phase": PHASE,
                "spec": spec.model_dump(mode="json"),
            },
            dependencies=spec.source_job_ids,
            priority=priority,
            max_attempts=2,
        )

    @staticmethod
    def _spec_from_job(job: MediaJob) -> WebsiteBuildSpec:
        if job.job_type != JOB_TYPE:
            raise MediaWebsiteError("website worker received wrong job type")
        payload = job.payload
        if payload.get("protocol") != PROTOCOL or payload.get("implementation_version") != IMPLEMENTATION_VERSION or payload.get("phase") != PHASE:
            raise MediaWebsiteError("website job payload protocol/version mismatch")
        spec = WebsiteBuildSpec.model_validate(payload.get("spec"))
        validate_website_spec(spec)
        if job.dependency_job_ids != spec.source_job_ids:
            raise MediaWebsiteError("website durable dependencies diverged from public asset provenance")
        return spec

    @staticmethod
    def _display_name(profile: DelverProfile) -> str:
        return profile.public_name.strip() if profile.public_name and profile.public_name.strip() else profile.delver_id

    def _nav(self, page_path: str) -> str:
        links = (
            ("Underreach", "index.html"),
            ("Delvers", "delvers/index.html"),
            ("Chronicles", "chronicles/index.html"),
            ("Highlights", "highlights/index.html"),
        )
        return "".join(
            f'<a href="{escape(_relative_href(page_path, target))}">{escape(label)}</a>'
            for label, target in links
        )

    def _layout(self, *, page_path: str, title: str, body: str) -> bytes:
        css = escape(_relative_href(page_path, "assets/site.css"))
        html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} | {escape(self.policy.site_title)}</title>
<link rel="stylesheet" href="{css}">
</head>
<body>
<header><div class="brand"><strong>{escape(self.policy.site_title)}</strong><span>{escape(self.policy.site_subtitle)}</span></div><nav>{self._nav(page_path)}</nav></header>
<main>{body}</main>
<footer>Generated from verified, presentation-safe Underreach media state.</footer>
</body>
</html>
"""
        return html.encode("utf-8")

    @staticmethod
    def _profile_summary(profile: DelverProfile) -> str:
        bits = [f"Status: {escape(profile.status.value)}"]
        if profile.current_stratum is not None:
            bits.append(f"Stratum {profile.current_stratum}")
        if profile.current_sector:
            bits.append(escape(profile.current_sector))
        return " &middot; ".join(bits)

    def _profile_cards(self, page_path: str, profiles: tuple[DelverProfile, ...]) -> str:
        cards = []
        for profile in sorted(profiles, key=lambda item: (self._display_name(item).lower(), item.delver_id)):
            target = f"delvers/{_slug(profile.delver_id)}/index.html"
            cards.append(
                f'<article class="card"><h3><a href="{escape(_relative_href(page_path, target))}">{escape(self._display_name(profile))}</a></h3>'
                f'<p>{self._profile_summary(profile)}</p></article>'
            )
        return "".join(cards) if cards else '<p class="empty">No Delvers in this view.</p>'

    def _chapter_title(self, chapter: ChronicleChapter) -> str:
        return _humanize(chapter.title_code)

    def _render_pages(self, values: dict[str, Any], asset_public_paths: dict[str, str]) -> dict[str, bytes]:
        profiles: tuple[DelverProfile, ...] = values["profiles"]
        chapters: tuple[ChronicleChapter, ...] = values["chapters"]
        narratives: dict[str, PublicNarrative] = values["narratives"]
        portraits: dict[str, PublicMediaAsset] = values["portraits"]
        videos: tuple[PublicMediaAsset, ...] = values["videos"]
        chapters_by_profile: dict[str, list[ChronicleChapter]] = {}
        for chapter in chapters:
            chapters_by_profile.setdefault(chapter.profile_id, []).append(chapter)

        pages: dict[str, bytes] = {}
        index_path = "index.html"
        status_links = " ".join(
            f'<a class="pill" href="{escape(_relative_href(index_path, f"status/{status.value.lower()}/index.html"))}">{escape(status.value.title())}</a>'
            for status in ProfileStatus
        )
        index_body = (
            '<section class="hero"><p class="eyebrow">Headless Chronicle</p>'
            f'<h1>{escape(self.policy.site_title)}</h1><p>{escape(self.policy.site_subtitle)}</p></section>'
            f'<section><h2>Delvers</h2><p>{len(profiles)} public profiles &middot; {len(chapters)} Chronicle entries &middot; {len(videos)} published reels</p>'
            f'<div class="pills">{status_links}</div><div class="grid">{self._profile_cards(index_path, profiles)}</div></section>'
        )
        pages[index_path] = self._layout(page_path=index_path, title="Home", body=index_body)

        delver_index = "delvers/index.html"
        pages[delver_index] = self._layout(
            page_path=delver_index,
            title="Delvers",
            body=f'<h1>Delvers</h1><div class="grid">{self._profile_cards(delver_index, profiles)}</div>',
        )

        for status in ProfileStatus:
            path = f"status/{status.value.lower()}/index.html"
            selected = tuple(item for item in profiles if item.status == status)
            pages[path] = self._layout(
                page_path=path,
                title=f"{status.value.title()} Delvers",
                body=f'<h1>{escape(status.value.title())} Delvers</h1><div class="grid">{self._profile_cards(path, selected)}</div>',
            )

        chronicle_index = "chronicles/index.html"
        chronicle_cards = []
        for chapter in chapters:
            profile = next((item for item in profiles if item.profile_id == chapter.profile_id), None)
            owner = self._display_name(profile) if profile is not None else chapter.delver_id
            target = f"chronicles/{_slug(chapter.chapter_id)}.html"
            chronicle_cards.append(
                f'<article class="card"><p class="eyebrow">{escape(owner)}</p><h3><a href="{escape(_relative_href(chronicle_index, target))}">{escape(self._chapter_title(chapter))}</a></h3>'
                f'<p>Tick {chapter.canonical_tick}</p></article>'
            )
        pages[chronicle_index] = self._layout(
            page_path=chronicle_index,
            title="Chronicles",
            body=f'<h1>The Chronicle</h1><div class="grid">{"".join(chronicle_cards) if chronicle_cards else "<p class=empty>No Chronicle entries yet.</p>"}</div>',
        )

        for profile in profiles:
            path = f"delvers/{_slug(profile.delver_id)}/index.html"
            portrait = portraits.get(profile.profile_id)
            portrait_html = ""
            if portrait is not None:
                public = asset_public_paths[portrait.source_artifact_id]
                portrait_html = f'<img class="portrait" src="{escape(_relative_href(path, public))}" alt="Presentation portrait of {escape(self._display_name(profile))}">'
            equipment = "".join(
                f'<li>{escape(item.name)}{f" ({escape(item.rarity)})" if item.rarity else ""}</li>'
                for item in profile.notable_equipment[: self.policy.max_equipment_items]
            ) or "<li>None recorded</li>"
            allies = "".join(
                f'<li>{escape(item.delver_id)}</li>' for item in profile.known_allies[: self.policy.max_relationships_per_kind]
            ) or "<li>None recorded</li>"
            rivals = "".join(
                f'<li>{escape(item.delver_id)}</li>' for item in profile.known_rivals[: self.policy.max_relationships_per_kind]
            ) or "<li>None recorded</li>"
            chapter_links = []
            for chapter in chapters_by_profile.get(profile.profile_id, []):
                target = f"chronicles/{_slug(chapter.chapter_id)}.html"
                chapter_links.append(
                    f'<li><a href="{escape(_relative_href(path, target))}">{escape(self._chapter_title(chapter))}</a></li>'
                )
            location = []
            if profile.current_stratum is not None:
                location.append(f"Stratum {profile.current_stratum}")
            if profile.current_sector:
                location.append(escape(profile.current_sector))
            body = (
                f'<section class="profile-head">{portrait_html}<div><p class="eyebrow">Delver Profile</p><h1>{escape(self._display_name(profile))}</h1>'
                f'<p class="status">{escape(profile.status.value)}</p><p>{" &middot; ".join(location) if location else "Location not published"}</p></div></section>'
                '<section class="columns">'
                f'<div><h2>Party</h2><p>{escape(profile.current_party_id) if profile.current_party_id else "Independent"}</p>'
                f'<h2>Alliances</h2><p>{", ".join(escape(item) for item in profile.current_alliance_ids) if profile.current_alliance_ids else "None recorded"}</p></div>'
                f'<div><h2>Notable Equipment</h2><ul>{equipment}</ul></div>'
                f'<div><h2>Known Allies</h2><ul>{allies}</ul><h2>Known Rivals</h2><ul>{rivals}</ul></div></section>'
                f'<section><h2>The Chronicle</h2><ol>{"".join(chapter_links) if chapter_links else "<li>No entries yet.</li>"}</ol></section>'
            )
            pages[path] = self._layout(page_path=path, title=self._display_name(profile), body=body)

        for chapter in chapters:
            path = f"chronicles/{_slug(chapter.chapter_id)}.html"
            profile = next((item for item in profiles if item.profile_id == chapter.profile_id), None)
            owner = self._display_name(profile) if profile is not None else chapter.delver_id
            narrative = narratives.get(chapter.chapter_id)
            if narrative is not None:
                prose_html = "".join(f"<p>{escape(paragraph)}</p>" for paragraph in narrative.prose.splitlines() if paragraph.strip())
                if not prose_html:
                    prose_html = f"<p>{escape(narrative.prose)}</p>"
                verification_note = '<p class="verified">Verification-cleared Chronicle prose</p>'
            else:
                prose_html = '<p class="empty">This entry has no verification-cleared prose yet. Structured Chronicle metadata is shown instead.</p>'
                verification_note = ""
            triggers = "".join(f"<li>{escape(_humanize(item))}</li>" for item in chapter.trigger_codes)
            body = (
                f'<p class="eyebrow">{escape(owner)} &middot; Tick {chapter.canonical_tick}</p><h1>{escape(self._chapter_title(chapter))}</h1>'
                f'{verification_note}<article class="prose">{prose_html}</article>'
                f'<details><summary>Structured entry</summary><p>Type: {escape(chapter.chapter_kind.value)}</p><ul>{triggers}</ul></details>'
            )
            pages[path] = self._layout(page_path=path, title=self._chapter_title(chapter), body=body)

        highlight_path = "highlights/index.html"
        reels = []
        for video in videos:
            public = asset_public_paths[video.source_artifact_id]
            label = "Enhanced Shot" if video.role == "enhanced_clip" else "Motion Story"
            reels.append(
                f'<article class="reel card"><p class="eyebrow">{escape(label)}</p><video controls preload="metadata" src="{escape(_relative_href(highlight_path, public))}"></video>'
                f'<p>{escape(video.story_id or "Underreach highlight")}</p></article>'
            )
        pages[highlight_path] = self._layout(
            page_path=highlight_path,
            title="Highlights",
            body=f'<h1>Published Highlights</h1><p>Only approved, published promotional media appears here.</p><div class="grid">{"".join(reels) if reels else "<p class=empty>No approved highlights have been published yet.</p>"}</div>',
        )
        return pages

    @staticmethod
    def _css() -> bytes:
        return b"""*{box-sizing:border-box}body{margin:0;background:#0d0f12;color:#ece8df;font-family:system-ui,-apple-system,Segoe UI,sans-serif;line-height:1.55}a{color:#d6b77b}header{position:sticky;top:0;z-index:2;background:#11151acc;border-bottom:1px solid #2b3138;padding:1rem 5vw;display:flex;gap:2rem;align-items:center;justify-content:space-between;backdrop-filter:blur(10px)}.brand{display:flex;flex-direction:column}.brand span{color:#8f9aa5;font-size:.8rem}nav{display:flex;gap:1rem;flex-wrap:wrap}main{width:min(1120px,90vw);margin:0 auto;padding:3rem 0 5rem}.hero{padding:6rem 0 4rem}.hero h1,h1{font-size:clamp(2rem,7vw,5rem);line-height:1;margin:.25rem 0 1rem}.eyebrow{text-transform:uppercase;letter-spacing:.14em;color:#aab2ba;font-size:.75rem}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:1rem}.card{border:1px solid #2b3138;background:#15191e;padding:1rem;border-radius:.75rem}.card h3{margin:.25rem 0}.pills{display:flex;gap:.5rem;flex-wrap:wrap;margin:1rem 0 2rem}.pill,.status{display:inline-block;border:1px solid #4a5159;border-radius:999px;padding:.25rem .7rem}.profile-head{display:flex;gap:2rem;align-items:center;margin-bottom:2rem}.portrait{width:min(280px,40vw);aspect-ratio:1;object-fit:cover;border-radius:1rem;border:1px solid #343b43}.columns{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:2rem;border-top:1px solid #2b3138;border-bottom:1px solid #2b3138;padding:2rem 0}.prose{font-family:Georgia,serif;font-size:1.1rem;max-width:760px}.verified{color:#8fc79a}.empty{color:#8f9aa5}.reel video{width:100%;aspect-ratio:9/16;max-height:620px;background:#050607}details{margin-top:2rem;border-top:1px solid #2b3138;padding-top:1rem}footer{border-top:1px solid #2b3138;color:#7f8992;padding:2rem 5vw;text-align:center}@media(max-width:680px){header{position:static;align-items:flex-start;flex-direction:column}.profile-head{align-items:flex-start;flex-direction:column}.portrait{width:100%;max-width:320px}}"""

    def _build_file_tree(self, spec: WebsiteBuildSpec, values: dict[str, Any], temp_public: Path) -> tuple[list[dict[str, Any]], int, int]:
        assets: tuple[PublicMediaAsset, ...] = values["assets"]
        asset_public_paths = {item.source_artifact_id: item.public_uri for item in assets}
        entries: list[dict[str, Any]] = []
        copied_assets = 0
        for asset in sorted(assets, key=lambda item: item.public_uri):
            source_artifact = next(
                item for item in self.media.snapshot()["artifacts"] if item["artifact_id"] == asset.source_artifact_id
            )
            source = self._verify_source_file(source_artifact)
            target = temp_public.joinpath(*PurePosixPath(asset.public_uri).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = source.read_bytes()
            target.write_bytes(payload)
            entries.append({
                "path": asset.public_uri,
                "artifact_kind": asset.artifact_kind,
                "sha256": sha256(payload).hexdigest(),
                "source_artifact_id": asset.source_artifact_id,
                "role": asset.role,
            })
            copied_assets += 1

        css_path = temp_public / "assets" / "site.css"
        css_path.parent.mkdir(parents=True, exist_ok=True)
        css = self._css()
        css_path.write_bytes(css)
        entries.append({"path": "assets/site.css", "artifact_kind": "text/css", "sha256": sha256(css).hexdigest()})

        pages = self._render_pages(values, asset_public_paths)
        for relative, payload in sorted(pages.items()):
            path = temp_public.joinpath(*PurePosixPath(relative).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            entries.append({"path": relative, "artifact_kind": "text/html", "sha256": sha256(payload).hexdigest()})
        return entries, len(pages), copied_assets

    def run_next(self, *, worker_id: str = "underreach-static-website-worker") -> WebsiteBuildResult | None:
        lease = self.media.claim_next(worker_id)
        if lease is None:
            return None
        job = lease.job
        if job.job_type != JOB_TYPE:
            self.media.fail_job(job.job_id, reason_code="wrong_website_worker_job_type", retryable=False)
            return None
        try:
            spec = self._spec_from_job(job)
        except Exception:
            self.media.fail_job(job.job_id, reason_code="invalid_website_build_spec", retryable=False)
            raise
        try:
            values = self._public_inputs(crawl_id=spec.crawl_id)
            if values["source_digest"] != spec.source_digest:
                self.media.fail_job(job.job_id, reason_code="website_source_changed", retryable=False)
                return WebsiteBuildResult(
                    build_id=spec.build_id,
                    job_id=job.job_id,
                    status=JobStatus.FAILED,
                    reason_code="website_source_changed",
                )

            base = PurePosixPath(self.policy.output_directory) / spec.build_id
            public_rel = (base / "public").as_posix()
            final_public = self.media_root.joinpath(*PurePosixPath(public_rel).parts)
            temp_public = final_public.with_name(f"{final_public.name}.tmp")
            if temp_public.exists():
                shutil.rmtree(temp_public)
            temp_public.mkdir(parents=True, exist_ok=True)
            entries, page_count, copied_asset_count = self._build_file_tree(spec, values, temp_public)
            manifest_body = {
                "protocol": PROTOCOL,
                "implementation_version": IMPLEMENTATION_VERSION,
                "phase": PHASE,
                "site_schema_version": SITE_SCHEMA_VERSION,
                "build_id": spec.build_id,
                "source_digest": spec.source_digest,
                "policy_digest": spec.policy_digest,
                "crawl_id": spec.crawl_id,
                "crawl_ids": list(spec.crawl_ids),
                "profile_count": spec.profile_count,
                "chapter_count": spec.chapter_count,
                "verified_narrative_count": spec.verified_narrative_count,
                "excluded_unverified_draft_count": spec.excluded_unverified_draft_count,
                "highlight_count": spec.highlight_count,
                "portrait_count": spec.portrait_count,
                "published_video_count": spec.published_video_count,
                "page_count": page_count,
                "copied_asset_count": copied_asset_count,
                "files": sorted(entries, key=lambda item: item["path"]),
                "static_only": True,
                "live_database_required_after_build": False,
                "canonical_database_opened": False,
                "live_simulation_query_used": False,
                "provider_invocation_used": False,
                "network_dependency": False,
                "unreal_dependency": False,
                "canonical_authority": False,
                "presentation_can_mutate_simulation": False,
            }
            manifest_bytes = canonical_json(manifest_body).encode("utf-8")
            manifest_digest = sha256(manifest_bytes).hexdigest()
            manifest_rel_inside = "site-manifest.json"
            (temp_public / manifest_rel_inside).write_bytes(manifest_bytes)

            if final_public.exists():
                shutil.rmtree(final_public)
            final_public.parent.mkdir(parents=True, exist_ok=True)
            temp_public.replace(final_public)

            recorded = 0
            manifest_artifact_id: str | None = None
            for entry in sorted(entries, key=lambda item: item["path"]):
                uri = (PurePosixPath(public_rel) / entry["path"]).as_posix()
                artifact_id = self.media.record_artifact(
                    job_id=job.job_id,
                    artifact_kind=entry["artifact_kind"],
                    uri=uri,
                    digest=entry["sha256"],
                    metadata={
                        "build_id": spec.build_id,
                        "public_static": True,
                        "source_artifact_id": entry.get("source_artifact_id"),
                        "presentation_only": True,
                    },
                )
                recorded += 1
            manifest_uri = (PurePosixPath(public_rel) / manifest_rel_inside).as_posix()
            manifest_artifact_id = self.media.record_artifact(
                job_id=job.job_id,
                artifact_kind="application/json",
                uri=manifest_uri,
                digest=manifest_digest,
                metadata={"build_id": spec.build_id, "site_manifest": True, "public_static": True, "presentation_only": True},
            )
            recorded += 1
            completed = self.media.complete_job(
                job.job_id,
                resource_usage={
                    "page_count": page_count,
                    "copied_asset_count": copied_asset_count,
                    "artifact_count": recorded,
                    "provider_invocation_used": False,
                },
            )
            return WebsiteBuildResult(
                build_id=spec.build_id,
                job_id=job.job_id,
                status=completed.status,
                public_root=public_rel,
                manifest_artifact_id=manifest_artifact_id,
                manifest_uri=manifest_uri,
                manifest_digest=manifest_digest,
                page_count=page_count,
                copied_asset_count=copied_asset_count,
                artifact_count=recorded,
            )
        except Exception:
            current = self.media.get_job(job.job_id)
            if current is not None and current.status == JobStatus.RUNNING:
                self.media.fail_job(job.job_id, reason_code="website_build_failed", retryable=True)
            raise

    def snapshot(self) -> dict[str, Any]:
        media_snapshot = self.media.snapshot()
        jobs = [item for item in media_snapshot["jobs"] if item["job_type"] == JOB_TYPE]
        job_ids = {item["job_id"] for item in jobs}
        artifacts = [item for item in media_snapshot["artifacts"] if item["job_id"] in job_ids]
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "site_schema_version": SITE_SCHEMA_VERSION,
            "authoritative": False,
            "canonical_owner": "deterministic_simulation",
            "presentation_can_mutate_simulation": False,
            "canonical_database_opened": False,
            "live_simulation_query_used": False,
            "provider_invocation_used": False,
            "network_dependency": False,
            "unreal_dependency": False,
            "live_database_required_after_build": False,
            "static_only": True,
            "policy": self.policy.model_dump(mode="json"),
            "policy_digest": self.policy.digest,
            "jobs": jobs,
            "job_count": len(jobs),
            "job_digest": payload_digest(jobs),
            "artifacts": artifacts,
            "artifact_count": len(artifacts),
            "artifact_digest": payload_digest(artifacts),
        }
        return {**body, "digest": payload_digest(body)}


__all__ = [
    "PROTOCOL",
    "IMPLEMENTATION_VERSION",
    "PHASE",
    "JOB_TYPE",
    "SITE_SCHEMA_VERSION",
    "WebsitePolicy",
    "PublicNarrative",
    "PublicMediaAsset",
    "WebsiteBuildSpec",
    "WebsiteBuildResult",
    "MediaWebsiteError",
    "MediaWebsiteBlogService",
    "validate_public_narrative",
    "validate_public_asset",
    "validate_website_spec",
]
