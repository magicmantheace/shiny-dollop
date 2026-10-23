from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import httpx
import pytest

from livingworld.runtime_checkpoint import payload_digest
from livingworld.underreach_comfyui_providers import (
    ComfyUIImageProvider,
    ComfyUIProviderConfig,
    ComfyUIProviderError,
    ComfyUIWanVideoProvider,
)
from livingworld.underreach_delver_chronicle_profile import ChapterKind, ChronicleChapter
from livingworld.underreach_headless_local_image_production import (
    ImageProductionSpec,
    ImagePurpose,
    ImageRenderRequest,
)
from livingworld.underreach_highlight_story_arc import HighlightTier
from livingworld.underreach_kokoro_provider import KokoroProviderConfig, KokoroVoiceProvider
from livingworld.underreach_local_video_enhancement import (
    VideoEnhancementSpec,
    VideoRenderRequest,
    VideoSourceShot,
)
from livingworld.underreach_media_event_export import AllowedFact
from livingworld.underreach_media_foundation import (
    MediaPersistence,
    MediaProviderRouter,
    ProviderKind,
    ProviderPolicy,
    ProviderRequest,
)
from livingworld.underreach_narration_captions_audio import (
    NarrationPackageSpec,
    VoiceSynthesisRequest,
    deterministic_wav_bytes,
)
from livingworld.underreach_ollama_providers import (
    OllamaAuxiliaryVerificationProvider,
    OllamaNarrativeProvider,
    OllamaProviderConfig,
    OllamaProviderError,
)
from livingworld.underreach_presentation_identity import ReferenceKind
from livingworld.underreach_production_provider_stack import (
    ProductionProviderSettings,
    build_production_provider_stack,
)


def _stable_id(prefix: str, *parts: object) -> str:
    text = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(text.encode('utf-8')).hexdigest()[:24]}"


def _chapter() -> ChronicleChapter:
    profile_id = "profile_001"
    envelope_id = "envelope_001"
    chapter_id = _stable_id("chronicle_chapter", profile_id, ChapterKind.HIGHLIGHT.value, "none", envelope_id)
    body = {
        "protocol": "underreach.delver-chronicle-profile.v1",
        "implementation_version": "30.5.4",
        "phase": "30.5",
        "chapter_id": chapter_id,
        "profile_id": profile_id,
        "crawl_id": "crawl_001",
        "delver_id": "descender_001",
        "chapter_kind": ChapterKind.HIGHLIGHT.value,
        "title_code": "HIGHLIGHT_COMBAT_ENDED",
        "canonical_tick": 10,
        "source_envelope_ids": [envelope_id],
        "source_event_ids": ["event_001"],
        "allowed_fact_ids": ["fact_001", "fact_002"],
        "highlight_id": None,
        "arc_ids": [],
        "trigger_codes": ["chapter:highlight", "event:COMBAT_ENDED"],
        "terminal": False,
        "structured_only": True,
        "claim_verification_required": True,
        "generated_prose_used": False,
        "presentation_can_mutate_simulation": False,
    }
    return ChronicleChapter.model_validate({**body, "digest": payload_digest(body)})


def _facts() -> tuple[AllowedFact, ...]:
    return (
        AllowedFact(
            fact_id="fact_001",
            scope="event",
            subject="descender_001",
            predicate="event_type",
            value="COMBAT_ENDED",
            source_event_ids=("event_001",),
        ),
        AllowedFact(
            fact_id="fact_002",
            scope="event",
            subject="descender_001",
            predicate="stratum",
            value=2,
            source_event_ids=("event_001",),
        ),
    )


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")


def test_ollama_writer_selects_allowlisted_fact_but_factual_value_is_rendered_from_canonical_fact() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["model"] == "qwen3:8b"
        assert isinstance(body["format"], dict)
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "fact_ids": ["fact_002"],
                            "style_line": "The air seemed to hold its breath.",
                            "tone": "cinematic",
                        }
                    ),
                }
            },
        )

    config = OllamaProviderConfig(base_url="http://127.0.0.1:11434")
    provider = OllamaNarrativeProvider(config, client=_mock_client(handler))
    prose, claims, selected = provider.build_prose_and_claims(_chapter(), _facts())

    assert selected == ("fact_002",)
    assert "canonical stratum 2" in prose.lower()
    assert len(claims) == 2
    assert claims[0].claim_type.value == "stylistic"
    factual = claims[1]
    assert factual.subject == "descender_001"
    assert factual.predicate == "stratum"
    assert factual.target_or_value == 2
    assert factual.supporting_allowed_fact_ids == ("fact_002",)


def test_ollama_writer_rejects_fact_id_outside_chapter_allowlist() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"message": {"content": json.dumps({"fact_ids": ["invented_fact"], "style_line": None, "tone": "cinematic"})}},
        )

    provider = OllamaNarrativeProvider(OllamaProviderConfig(), client=_mock_client(handler))
    with pytest.raises(OllamaProviderError, match="outside the chapter allowlist"):
        provider.select(_chapter(), _facts())


def test_ollama_auxiliary_verifier_maps_every_sentence_and_remains_advisory() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "qwen3:4b"
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps(
                        {
                            "assessments": [
                                {"sentence_index": 0, "classification": "stylistic", "reason_code": "atmosphere_only"},
                                {"sentence_index": 1, "classification": "factual", "reason_code": "fact_signal"},
                            ]
                        }
                    )
                }
            },
        )

    provider = OllamaAuxiliaryVerificationProvider(OllamaProviderConfig(), client=_mock_client(handler))
    assessments = provider.assess(
        sentences=("The air seemed to hold its breath.", "Canonical record: descender 001 has stratum 2."),
        facts=_facts(),
        seed_material="draft_digest",
    )
    assert [item.classification.value for item in assessments] == ["stylistic", "factual"]
    assert all(item.provider_local is True and item.provider_paid is False for item in assessments)
    assert all(item.provider_id == provider.descriptor.provider_id for item in assessments)


def _image_spec() -> ImageProductionSpec:
    return ImageProductionSpec(
        spec_id="image_spec_test",
        purpose=ImagePurpose.IDENTITY_REFERENCE,
        crawl_id="crawl_001",
        profile_id="profile_001",
        delver_id="descender_001",
        identity_id="identity_001",
        identity_version=1,
        equipment_revision_id=None,
        source_envelope_id="envelope_001",
        source_event_ids=("event_001",),
        reference_id="reference_001",
        reference_kind=ReferenceKind.PORTRAIT,
        chapter_id=None,
        reference_artifact_ids=(),
        deterministic_seed=42,
        width=64,
        height=64,
        prompt="A presentation-only portrait.",
        negative_prompt="text, watermark",
        provider_request=ProviderRequest(
            kind=ProviderKind.IMAGE,
            required_flags=("headless_image", "png_output"),
            local_required=True,
            deterministic_seed_required=True,
            min_width=64,
            min_height=64,
            max_vram_mb=12288,
        ),
        policy_digest="policy",
        digest="digest",
    )


def test_comfyui_builtin_image_graph_submits_checkpoint_prompt_seed_and_resolution() -> None:
    captured: dict = {}
    png = b"\x89PNG\r\n\x1a\nmock-png"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/prompt":
            body = json.loads(request.content)
            captured.update(body["prompt"])
            return httpx.Response(200, json={"prompt_id": "prompt-image"})
        if request.url.path == "/history/prompt-image":
            return httpx.Response(
                200,
                json={"prompt-image": {"status": {"status_str": "success"}, "outputs": {"7": {"images": [{"filename": "portrait.png", "subfolder": "", "type": "output"}]}}}},
            )
        if request.url.path == "/view":
            return httpx.Response(200, content=png)
        raise AssertionError(request.url.path)

    media = MediaPersistence("sqlite:///:memory:")
    media.initialize()
    provider = ComfyUIImageProvider(
        media=media,
        media_root=Path("."),
        config=ComfyUIProviderConfig(image_checkpoint="local-sdxl.safetensors", poll_interval_seconds=0.001),
        client=_mock_client(handler),
    )
    output = provider.render(ImageRenderRequest(spec=_image_spec(), job_id="job", attempt_id="attempt"))

    assert output.image_bytes == png
    assert captured["1"]["inputs"]["ckpt_name"] == "local-sdxl.safetensors"
    assert captured["4"]["inputs"]["width"] == 64
    assert captured["4"]["inputs"]["height"] == 64
    assert captured["5"]["inputs"]["seed"] == 42
    assert captured["2"]["inputs"]["text"] == "A presentation-only portrait."


def test_comfyui_custom_image_workflow_requires_digest_valid_reference(tmp_path: Path) -> None:
    workflow = tmp_path / "image-workflow.json"
    workflow.write_text(
        json.dumps(
            {
                "1": {"class_type": "LoadImage", "inputs": {"image": "{{INPUT_IMAGE}}"}},
                "2": {"class_type": "CLIPTextEncode", "_meta": {"title": "Positive Prompt"}, "inputs": {"text": "{{PROMPT}}"}},
                "3": {"class_type": "SaveImage", "inputs": {"filename_prefix": "{{OUTPUT_PREFIX}}"}},
            }
        ),
        encoding="utf-8",
    )
    media = MediaPersistence("sqlite:///:memory:")
    media.initialize()
    provider = ComfyUIImageProvider(
        media=media,
        media_root=tmp_path,
        config=ComfyUIProviderConfig(image_workflow_path=workflow),
        client=_mock_client(lambda _request: httpx.Response(500)),
    )
    spec = _image_spec().model_copy(update={"reference_artifact_ids": ("missing_artifact",)})
    with pytest.raises(ComfyUIProviderError, match="persisted PNG artifact"):
        provider.render(ImageRenderRequest(spec=spec, job_id="job", attempt_id="attempt"))


def _narration_spec() -> NarrationPackageSpec:
    return NarrationPackageSpec(
        package_id="package_001",
        verification_id="verification_001",
        verification_digest="verification_digest",
        draft_id="draft_001",
        draft_digest="draft_digest",
        manifest_id="manifest_001",
        chapter_id="chapter_001",
        script="The verified script is spoken exactly.",
        sentences=("The verified script is spoken exactly.",),
        caption_cues=(
            {"index": 1, "start_ms": 0, "end_ms": 1800, "text": "The verified script is spoken exactly.", "digest": "cue"},
        ),
        duration_ms=1800,
        voice_requested=True,
        voice_provider_request=ProviderRequest(
            kind=ProviderKind.VOICE,
            required_flags=("headless_voice", "wav_output"),
            local_required=True,
            deterministic_seed_required=True,
            min_duration_seconds=1.8,
        ),
        deterministic_seed=9,
        policy_digest="policy",
        digest="digest",
    )


def test_kokoro_posts_verified_script_and_returns_real_wav_metadata() -> None:
    wav = deterministic_wav_bytes(duration_ms=1200, sample_rate=22050, seed=4)
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/audio/speech"
        captured.update(json.loads(request.content))
        return httpx.Response(200, content=wav, headers={"content-type": "audio/wav"})

    provider = KokoroVoiceProvider(
        KokoroProviderConfig(base_url="http://127.0.0.1:8880/v1", voice="af_bella"),
        client=_mock_client(handler),
    )
    output = provider.synthesize(VoiceSynthesisRequest(spec=_narration_spec(), job_id="voice_job", attempt_id="attempt"))

    assert captured["input"] == "The verified script is spoken exactly."
    assert captured["response_format"] == "wav"
    assert captured["voice"] == "af_bella"
    assert output.wav_bytes.startswith(b"RIFF")
    assert output.sample_rate == 22050
    assert output.channels == 1
    assert 1100 <= output.duration_ms <= 1300


def _video_spec() -> VideoEnhancementSpec:
    source = VideoSourceShot(
        shot_index=0,
        timeline_start_ms=0,
        source_duration_ms=4000,
        animation_duration_ms=4000,
        source_image_artifact_id="image_artifact",
        source_image_job_id="image_job",
        source_image_uri="images/source.png",
        source_image_digest="image_digest",
        source_envelope_id="envelope_001",
        source_event_ids=("event_001",),
        digest="source_digest",
    )
    return VideoEnhancementSpec(
        spec_id="video_spec_001",
        story_id="story_001",
        chapter_id="chapter_001",
        motion_story_job_id="motion_job",
        fallback_artifact_id="fallback_artifact",
        fallback_uri="motion/fallback.mp4",
        fallback_digest="fallback_digest",
        fallback_manifest_artifact_id="fallback_manifest",
        fallback_manifest_digest="manifest_digest",
        highlight_ids=("highlight_001",),
        highlight_score=92,
        highlight_tier=HighlightTier.LOCAL_ANIMATION,
        treatment="partial_animation",
        source_shot=source,
        source_envelope_ids=("envelope_001",),
        source_event_ids=("event_001",),
        deterministic_seed=77,
        width=270,
        height=480,
        fps=12,
        provider_request=ProviderRequest(
            kind=ProviderKind.VIDEO,
            required_flags=("headless_video", "mp4_output", "short_shot"),
            local_required=True,
            deterministic_seed_required=True,
            image_to_video_required=True,
            min_width=270,
            min_height=480,
            min_duration_seconds=4.0,
            max_vram_mb=12288,
        ),
        policy_digest="policy",
        digest="digest",
    )


def test_comfyui_wan_uploads_source_patches_workflow_and_writes_scheduler_output(tmp_path: Path) -> None:
    workflow = tmp_path / "wan-api.json"
    workflow.write_text(
        json.dumps(
            {
                "1": {"class_type": "LoadImage", "inputs": {"image": "{{INPUT_IMAGE}}"}},
                "2": {
                    "class_type": "Wan22ImageToVideoLatent",
                    "inputs": {"width": "{{GEN_WIDTH}}", "height": "{{GEN_HEIGHT}}", "length": "{{FRAMES}}"},
                },
                "3": {"class_type": "KSampler", "inputs": {"seed": "{{SEED}}", "steps": 20, "cfg": 5}},
                "4": {"class_type": "CreateVideo", "inputs": {"fps": "{{FPS}}"}},
                "5": {"class_type": "SaveVideo", "inputs": {"filename_prefix": "{{OUTPUT_PREFIX}}"}},
            }
        ),
        encoding="utf-8",
    )
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload/image":
            return httpx.Response(200, json={"name": "source.png", "subfolder": "underreach-video", "type": "input"})
        if request.url.path == "/prompt":
            captured.update(json.loads(request.content)["prompt"])
            return httpx.Response(200, json={"prompt_id": "prompt-video"})
        if request.url.path == "/history/prompt-video":
            return httpx.Response(
                200,
                json={"prompt-video": {"status": {"status_str": "success"}, "outputs": {"5": {"videos": [{"filename": "shot.mp4", "subfolder": "", "type": "output"}]}}}},
            )
        if request.url.path == "/view":
            return httpx.Response(200, content=b"mock-comfy-video")
        if request.url.path == "/free":
            return httpx.Response(200, json={})
        raise AssertionError(request.url.path)

    source = tmp_path / "source.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\nsource")
    output = tmp_path / "shot.mp4"
    provider = ComfyUIWanVideoProvider(
        config=ComfyUIProviderConfig(video_workflow_path=workflow, poll_interval_seconds=0.001),
        client=_mock_client(handler),
    )

    def fake_transcode(raw: Path, request: VideoRenderRequest) -> None:
        assert raw.read_bytes() == b"mock-comfy-video"
        request.output_path.write_bytes(b"normalized-mp4")

    provider._transcode = fake_transcode  # type: ignore[method-assign]
    result = provider.animate(
        VideoRenderRequest(
            spec=_video_spec(),
            job_id="video_job",
            attempt_id="attempt",
            source_image_path=source,
            output_path=output,
        )
    )

    assert output.read_bytes() == b"normalized-mp4"
    assert captured["1"]["inputs"]["image"] == "underreach-video/source.png"
    assert captured["2"]["inputs"]["width"] == 432
    assert captured["2"]["inputs"]["height"] == 768
    assert captured["3"]["inputs"]["seed"] == 77
    assert captured["4"]["inputs"]["fps"] == 16
    assert result.width == 270 and result.height == 480
    assert result.metadata["renderer"] == "comfyui_wan2.2"


def test_stack_prefers_real_local_providers_and_retains_deterministic_fallbacks(tmp_path: Path) -> None:
    workflow = tmp_path / "wan-api.json"
    workflow.write_text(json.dumps({"1": {"class_type": "LoadImage", "inputs": {"image": "{{INPUT_IMAGE}}"}}}), encoding="utf-8")
    media = MediaPersistence("sqlite:///:memory:")
    media.initialize()
    settings = ProductionProviderSettings(
        ollama_enabled=True,
        comfyui_image_enabled=True,
        comfyui_video_enabled=True,
        comfyui_image_checkpoint="sd_xl_base_1.0.safetensors",
        comfyui_video_workflow_path=workflow,
        kokoro_enabled=True,
    )
    stack = build_production_provider_stack(media, media_root=tmp_path, settings=settings, probe=False)

    image_ids = [item.descriptor.provider_id for item in stack.image_providers]
    voice_ids = [item.descriptor.provider_id for item in stack.voice_providers]
    video_ids = [item.descriptor.provider_id for item in stack.video_providers]
    assert image_ids == ["comfyui_local_image", "local_deterministic_png"]
    assert voice_ids == ["kokoro_local_tts", "local_deterministic_wav"]
    assert video_ids == ["comfyui_wan22_ti2v_5b", "local_deterministic_i2v"]
    assert stack.ollama_writer is not None and stack.ollama_verifier is not None

    router = stack.new_router()
    policy = ProviderPolicy(local_only=True, cloud_allowed=False, allow_paid=False, max_vram_mb=12288)
    image_selection = router.select(
        ProviderRequest(
            kind=ProviderKind.IMAGE,
            required_flags=("headless_image", "png_output"),
            local_required=True,
            deterministic_seed_required=True,
            min_width=512,
            min_height=512,
            max_vram_mb=12288,
        ),
        policy,
    )
    voice_selection = router.select(
        ProviderRequest(
            kind=ProviderKind.VOICE,
            required_flags=("headless_voice", "wav_output"),
            local_required=True,
            deterministic_seed_required=True,
            min_duration_seconds=2.0,
        ),
        policy,
    )
    video_selection = router.select(
        ProviderRequest(
            kind=ProviderKind.VIDEO,
            required_flags=("headless_video", "mp4_output", "short_shot"),
            local_required=True,
            deterministic_seed_required=True,
            image_to_video_required=True,
            min_width=270,
            min_height=480,
            min_duration_seconds=4.0,
            max_vram_mb=12288,
        ),
        policy,
    )
    assert image_selection.provider_id == "comfyui_local_image"
    assert voice_selection.provider_id == "kokoro_local_tts"
    assert video_selection.provider_id == "comfyui_wan22_ti2v_5b"
    assert all(not descriptor.paid and descriptor.local for descriptor in stack.descriptors)


def test_stack_omits_disabled_real_services_but_keeps_fallbacks(tmp_path: Path) -> None:
    media = MediaPersistence("sqlite:///:memory:")
    media.initialize()
    stack = build_production_provider_stack(
        media,
        media_root=tmp_path,
        settings=ProductionProviderSettings(
            ollama_enabled=False,
            comfyui_image_enabled=False,
            comfyui_video_enabled=False,
            kokoro_enabled=False,
        ),
        probe=True,
    )
    assert stack.ollama_writer is None and stack.ollama_verifier is None
    assert [item.descriptor.provider_id for item in stack.image_providers] == ["local_deterministic_png"]
    assert [item.descriptor.provider_id for item in stack.voice_providers] == ["local_deterministic_wav"]
    assert [item.descriptor.provider_id for item in stack.video_providers] == ["local_deterministic_i2v"]
    assert all(not descriptor.paid and descriptor.local for descriptor in stack.descriptors)
