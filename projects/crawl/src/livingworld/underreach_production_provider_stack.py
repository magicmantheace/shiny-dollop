"""Configuration and factory for the real local Underreach media provider stack.

The production stack is intentionally bound to the exact local models installed
by ``install-underreach-media-pipeline.bat``.  Model names are not fuzzy family
selectors: health gating requires the exact Ollama tags and exact ComfyUI model
filenames used by the installer.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .underreach_comfyui_production_image import ProductionComfyUIImageProvider
from .underreach_comfyui_providers import ComfyUIProviderConfig, ComfyUIWanVideoProvider
from .underreach_delver_chronicle_profile import DelverChronicleProfileService
from .underreach_headless_local_image_production import DeterministicLocalPngProvider, HeadlessImageProvider
from .underreach_kokoro_provider import KokoroProviderConfig, KokoroVoiceProvider
from .underreach_local_video_enhancement import DeterministicLocalI2VProvider, HeadlessVideoProvider
from .underreach_media_foundation import MediaPersistence, MediaProviderRouter, ProviderDescriptor
from .underreach_narration_captions_audio import DeterministicLocalWavProvider, HeadlessVoiceProvider
from .underreach_narrative_claim_verification import NarrativeClaimVerificationService
from .underreach_ollama_providers import (
    OllamaAuxiliaryVerificationProvider,
    OllamaNarrativePipeline,
    OllamaNarrativeProvider,
    OllamaProviderConfig,
)


STACK_VERSION = "production-provider-stack.2"
INSTALLER_WRITER_MODEL = "qwen3:8b"
INSTALLER_VERIFIER_MODEL = "qwen3:4b"
INSTALLER_SDXL_CHECKPOINT = "sd_xl_base_1.0.safetensors"
INSTALLER_WAN_MODEL = "wan2.2_ti2v_5B_fp16.safetensors"
INSTALLER_WAN_TEXT_ENCODER = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
INSTALLER_WAN_VAE = "wan2.2_vae.safetensors"
INSTALLER_KOKORO_MODEL = "kokoro-v1_0.pth"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_media_home() -> Path:
    configured = os.environ.get("UNDERREACH_MEDIA_HOME", "").strip()
    if configured:
        return Path(configured).expanduser()
    return _repo_root().parent / "CrawlMedia"


def _default_wan_workflow() -> Path:
    return _repo_root() / "config" / "comfyui" / "wan2.2-ti2v-5b-api.json"


def _default_kokoro_python() -> Path:
    return _default_media_home() / "python" / ".venv" / "Scripts" / "python.exe"


def _default_kokoro_home() -> Path:
    return _default_media_home() / "models" / "Kokoro-82M"


def _default_kokoro_runner() -> Path:
    return _repo_root() / "scripts" / "run-underreach-kokoro-tts.py"


class ProductionProviderSettings(BaseSettings):
    """Environment-backed settings for the local production media stack.

    The installer model identities are deliberately pinned.  Operational knobs
    such as URLs, timeouts, dimensions, voice selection and fallback behavior
    remain configurable through ``UNDERREACH_PROVIDER_*`` variables.
    """

    model_config = SettingsConfigDict(
        env_prefix="UNDERREACH_PROVIDER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama_enabled: bool = True
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_writer_model: str = INSTALLER_WRITER_MODEL
    ollama_verifier_model: str = INSTALLER_VERIFIER_MODEL
    ollama_timeout_seconds: float = Field(default=300.0, gt=0.0, le=3600.0)
    ollama_keep_alive: str = "0"

    comfyui_image_enabled: bool = True
    comfyui_video_enabled: bool = True
    comfyui_base_url: str = "http://127.0.0.1:8188"
    comfyui_timeout_seconds: float = Field(default=1800.0, gt=0.0, le=7200.0)
    comfyui_image_checkpoint: str = INSTALLER_SDXL_CHECKPOINT
    comfyui_image_workflow_path: Path | None = None
    comfyui_video_workflow_path: Path = Field(default_factory=_default_wan_workflow)
    comfyui_video_generation_width: int = Field(default=432, ge=128, le=1080)
    comfyui_video_generation_height: int = Field(default=768, ge=128, le=1920)
    comfyui_video_generation_fps: int = Field(default=16, ge=4, le=60)
    comfyui_video_max_frames: int = Field(default=81, ge=9, le=161)
    comfyui_free_gpu_after_image: bool = False
    comfyui_free_gpu_after_video: bool = True

    kokoro_enabled: bool = True
    kokoro_backend: Literal["subprocess", "http"] = "subprocess"
    kokoro_base_url: str = "http://127.0.0.1:8880/v1"
    kokoro_model: str = "kokoro"
    kokoro_voice: str = "af_bella"
    kokoro_speed: float = Field(default=1.0, ge=0.25, le=4.0)
    kokoro_timeout_seconds: float = Field(default=180.0, gt=0.0, le=1800.0)
    kokoro_python_executable: Path = Field(default_factory=_default_kokoro_python)
    kokoro_model_home: Path = Field(default_factory=_default_kokoro_home)
    kokoro_runner_path: Path = Field(default_factory=_default_kokoro_runner)

    deterministic_image_fallback_enabled: bool = True
    deterministic_voice_fallback_enabled: bool = True
    deterministic_video_fallback_enabled: bool = True

    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"

    @field_validator(
        "comfyui_image_workflow_path",
        "comfyui_video_workflow_path",
        "kokoro_python_executable",
        "kokoro_model_home",
        "kokoro_runner_path",
        mode="before",
    )
    @classmethod
    def blank_path_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def pin_installer_model_identities(self) -> "ProductionProviderSettings":
        expected = {
            "ollama_writer_model": INSTALLER_WRITER_MODEL,
            "ollama_verifier_model": INSTALLER_VERIFIER_MODEL,
            "comfyui_image_checkpoint": INSTALLER_SDXL_CHECKPOINT,
        }
        for field_name, required in expected.items():
            actual = getattr(self, field_name)
            if actual != required:
                raise ValueError(
                    f"{field_name} is pinned to installer model {required!r}; got {actual!r}"
                )
        return self

    def ollama_config(self) -> OllamaProviderConfig:
        return OllamaProviderConfig(
            base_url=self.ollama_base_url,
            writer_model=self.ollama_writer_model,
            verifier_model=self.ollama_verifier_model,
            timeout_seconds=self.ollama_timeout_seconds,
            keep_alive=self.ollama_keep_alive,
        )

    def comfyui_config(self) -> ComfyUIProviderConfig:
        return ComfyUIProviderConfig(
            base_url=self.comfyui_base_url,
            timeout_seconds=self.comfyui_timeout_seconds,
            image_checkpoint=self.comfyui_image_checkpoint,
            image_workflow_path=self.comfyui_image_workflow_path,
            video_workflow_path=self.comfyui_video_workflow_path,
            video_generation_width=self.comfyui_video_generation_width,
            video_generation_height=self.comfyui_video_generation_height,
            video_generation_fps=self.comfyui_video_generation_fps,
            video_max_frames=self.comfyui_video_max_frames,
            ffmpeg_path=self.ffmpeg_path,
            ffprobe_path=self.ffprobe_path,
            free_gpu_after_image=self.comfyui_free_gpu_after_image,
            free_gpu_after_video=self.comfyui_free_gpu_after_video,
        )

    def kokoro_config(self) -> KokoroProviderConfig:
        return KokoroProviderConfig(
            backend=self.kokoro_backend,
            base_url=self.kokoro_base_url,
            model=self.kokoro_model,
            voice=self.kokoro_voice,
            speed=self.kokoro_speed,
            timeout_seconds=self.kokoro_timeout_seconds,
            python_executable=self.kokoro_python_executable,
            model_home=self.kokoro_model_home,
            runner_path=self.kokoro_runner_path,
        )


@dataclass(frozen=True)
class ProductionProviderStack:
    settings: ProductionProviderSettings
    image_providers: tuple[HeadlessImageProvider, ...]
    voice_providers: tuple[HeadlessVoiceProvider, ...]
    video_providers: tuple[HeadlessVideoProvider, ...]
    ollama_writer: OllamaNarrativeProvider | None
    ollama_verifier: OllamaAuxiliaryVerificationProvider | None
    health: dict[str, Any]

    @property
    def descriptors(self) -> tuple[ProviderDescriptor, ...]:
        values: list[ProviderDescriptor] = []
        values.extend(provider.descriptor for provider in self.image_providers)
        values.extend(provider.descriptor for provider in self.voice_providers)
        values.extend(provider.descriptor for provider in self.video_providers)
        if self.ollama_writer is not None:
            values.append(self.ollama_writer.descriptor)
        if self.ollama_verifier is not None:
            values.append(self.ollama_verifier.descriptor)
        return tuple(sorted(values, key=lambda item: (item.kind.value, item.provider_id)))

    def new_router(self) -> MediaProviderRouter:
        router = MediaProviderRouter()
        for descriptor in self.descriptors:
            router.register(descriptor)
        return router

    def build_narrative_pipeline(
        self,
        media: MediaPersistence,
        *,
        chronicle: DelverChronicleProfileService,
        verifier: NarrativeClaimVerificationService,
        use_auxiliary_verifier: bool = True,
    ) -> OllamaNarrativePipeline:
        if self.ollama_writer is None:
            raise RuntimeError("Ollama narrative writer is not available in the production provider stack")
        return OllamaNarrativePipeline(
            media,
            chronicle=chronicle,
            verifier=verifier,
            writer=self.ollama_writer,
            assessor=self.ollama_verifier if use_auxiliary_verifier else None,
        )


def _probe(provider: Any) -> tuple[bool, dict[str, Any]]:
    health_fn = getattr(provider, "health", None)
    if not callable(health_fn):
        return True, {"ready": True, "reason": "no_health_probe_required"}
    try:
        result = health_fn()
    except Exception as exc:  # external process/socket failure is expected during discovery
        return False, {"ready": False, "error_type": type(exc).__name__, "error": str(exc)}
    if not isinstance(result, dict):
        return False, {"ready": False, "error": "health probe returned non-object"}
    return bool(result.get("ready")), result


def _exact_ollama_model_ready(health: dict[str, Any], requested: str) -> bool:
    models = health.get("models")
    return isinstance(models, list) and requested in models


def _contains_string(value: Any, needle: str) -> bool:
    if isinstance(value, str):
        return value == needle
    if isinstance(value, dict):
        return any(_contains_string(item, needle) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_string(item, needle) for item in value)
    return False


def _wan_workflow_exact(path: Path) -> tuple[bool, list[str]]:
    required = [INSTALLER_WAN_MODEL, INSTALLER_WAN_TEXT_ENCODER, INSTALLER_WAN_VAE]
    if not path.is_file():
        return False, required
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, required
    missing = [name for name in required if not _contains_string(payload, name)]
    return not missing, missing


def _comfy_model_inventory(provider: Any) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = provider.client.object_info()
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    return payload if isinstance(payload, dict) else {}, None


def build_production_provider_stack(
    media: MediaPersistence,
    *,
    media_root: str | Path,
    settings: ProductionProviderSettings | None = None,
    probe: bool = True,
) -> ProductionProviderStack:
    """Build the exact installer-backed local stack without downloading models."""

    effective = settings or ProductionProviderSettings()
    health: dict[str, Any] = {
        "stack_version": STACK_VERSION,
        "probe_enabled": probe,
        "installer_contract": {
            "writer": INSTALLER_WRITER_MODEL,
            "verifier": INSTALLER_VERIFIER_MODEL,
            "image": INSTALLER_SDXL_CHECKPOINT,
            "video": INSTALLER_WAN_MODEL,
            "video_text_encoder": INSTALLER_WAN_TEXT_ENCODER,
            "video_vae": INSTALLER_WAN_VAE,
            "voice": INSTALLER_KOKORO_MODEL,
        },
        "providers": {},
    }

    image_providers: list[HeadlessImageProvider] = []
    voice_providers: list[HeadlessVoiceProvider] = []
    video_providers: list[HeadlessVideoProvider] = []
    writer: OllamaNarrativeProvider | None = None
    auxiliary: OllamaAuxiliaryVerificationProvider | None = None

    if effective.ollama_enabled:
        config = effective.ollama_config()
        writer_candidate = OllamaNarrativeProvider(config)
        verifier_candidate = OllamaAuxiliaryVerificationProvider(config)
        if probe:
            writer_ready, writer_health = _probe(writer_candidate)
            verifier_ready, verifier_health = _probe(verifier_candidate)
            writer_exact = _exact_ollama_model_ready(writer_health, INSTALLER_WRITER_MODEL)
            verifier_exact = _exact_ollama_model_ready(verifier_health, INSTALLER_VERIFIER_MODEL)
            writer_ready = writer_ready and writer_exact
            verifier_ready = verifier_ready and verifier_exact
            writer_health = {**writer_health, "exact_model_ready": writer_exact}
            verifier_health = {**verifier_health, "exact_model_ready": verifier_exact}
        else:
            writer_ready = verifier_ready = True
            writer_health = verifier_health = {"ready": True, "reason": "probe_disabled", "exact_model_ready": None}
        health["providers"][writer_candidate.descriptor.provider_id] = writer_health
        health["providers"][verifier_candidate.descriptor.provider_id] = verifier_health
        writer = writer_candidate if writer_ready else None
        auxiliary = verifier_candidate if verifier_ready else None

    comfy_config = effective.comfyui_config()
    image_configured = bool(comfy_config.image_checkpoint or comfy_config.image_workflow_path)
    if effective.comfyui_image_enabled and image_configured:
        image_candidate = ProductionComfyUIImageProvider(media=media, media_root=media_root, config=comfy_config)
        if probe:
            ready, status = _probe(image_candidate)
            inventory, inventory_error = _comfy_model_inventory(image_candidate)
            exact_checkpoint = bool(
                inventory is not None
                and _contains_string(inventory.get("CheckpointLoaderSimple", {}), INSTALLER_SDXL_CHECKPOINT)
            )
            ready = ready and exact_checkpoint
            status = {
                **status,
                "exact_installer_checkpoint_ready": exact_checkpoint,
                "required_checkpoint": INSTALLER_SDXL_CHECKPOINT,
                "model_inventory_error": inventory_error,
            }
        else:
            ready, status = True, {"ready": True, "reason": "probe_disabled", "exact_installer_checkpoint_ready": None}
        health["providers"][image_candidate.descriptor.provider_id] = status
        if ready:
            image_providers.append(image_candidate)
    elif effective.comfyui_image_enabled:
        health["providers"]["comfyui_local_image"] = {
            "ready": False,
            "reason": "image_checkpoint_or_workflow_not_configured",
        }

    video_path = comfy_config.video_workflow_path
    video_configured = video_path is not None and video_path.is_file()
    if effective.comfyui_video_enabled and video_configured:
        video_candidate = ComfyUIWanVideoProvider(config=comfy_config)
        workflow_exact, workflow_missing = _wan_workflow_exact(video_path)
        if probe:
            ready, status = _probe(video_candidate)
            inventory, inventory_error = _comfy_model_inventory(video_candidate)
            exact_inventory = bool(
                inventory is not None
                and _contains_string(inventory.get("UNETLoader", {}), INSTALLER_WAN_MODEL)
                and _contains_string(inventory.get("CLIPLoader", {}), INSTALLER_WAN_TEXT_ENCODER)
                and _contains_string(inventory.get("VAELoader", {}), INSTALLER_WAN_VAE)
            )
            exact_video = workflow_exact and exact_inventory
            ready = ready and exact_video
            status = {
                **status,
                "exact_installer_models_ready": exact_video,
                "workflow_exact": workflow_exact,
                "workflow_missing_models": workflow_missing,
                "model_inventory_exact": exact_inventory,
                "model_inventory_error": inventory_error,
                "required_model": INSTALLER_WAN_MODEL,
                "required_text_encoder": INSTALLER_WAN_TEXT_ENCODER,
                "required_vae": INSTALLER_WAN_VAE,
            }
        else:
            ready, status = True, {
                "ready": True,
                "reason": "probe_disabled",
                "workflow_exact": workflow_exact,
                "workflow_missing_models": workflow_missing,
            }
        health["providers"][video_candidate.descriptor.provider_id] = status
        if ready:
            video_providers.append(video_candidate)
    elif effective.comfyui_video_enabled:
        health["providers"]["comfyui_wan22_ti2v_5b"] = {
            "ready": False,
            "reason": "video_workflow_not_configured",
            "required_workflow": str(effective.comfyui_video_workflow_path),
        }

    if effective.kokoro_enabled:
        voice_candidate = KokoroVoiceProvider(effective.kokoro_config())
        if probe:
            ready, status = _probe(voice_candidate)
        else:
            ready, status = True, {"ready": True, "reason": "probe_disabled"}
        health["providers"][voice_candidate.descriptor.provider_id] = status
        if ready:
            voice_providers.append(voice_candidate)

    if effective.deterministic_image_fallback_enabled:
        fallback = DeterministicLocalPngProvider()
        image_providers.append(fallback)
        health["providers"][fallback.descriptor.provider_id] = {"ready": True, "fallback": True}
    if effective.deterministic_voice_fallback_enabled:
        fallback = DeterministicLocalWavProvider()
        voice_providers.append(fallback)
        health["providers"][fallback.descriptor.provider_id] = {"ready": True, "fallback": True}
    if effective.deterministic_video_fallback_enabled:
        fallback = DeterministicLocalI2VProvider(ffmpeg_path=effective.ffmpeg_path)
        video_providers.append(fallback)
        health["providers"][fallback.descriptor.provider_id] = {"ready": True, "fallback": True}

    health["active"] = {
        "narrative": writer.descriptor.provider_id if writer is not None else None,
        "verification": auxiliary.descriptor.provider_id if auxiliary is not None else None,
        "image": [provider.descriptor.provider_id for provider in image_providers],
        "voice": [provider.descriptor.provider_id for provider in voice_providers],
        "video": [provider.descriptor.provider_id for provider in video_providers],
    }

    return ProductionProviderStack(
        settings=effective,
        image_providers=tuple(image_providers),
        voice_providers=tuple(voice_providers),
        video_providers=tuple(video_providers),
        ollama_writer=writer,
        ollama_verifier=auxiliary,
        health=health,
    )


__all__ = [
    "STACK_VERSION",
    "INSTALLER_WRITER_MODEL",
    "INSTALLER_VERIFIER_MODEL",
    "INSTALLER_SDXL_CHECKPOINT",
    "INSTALLER_WAN_MODEL",
    "INSTALLER_WAN_TEXT_ENCODER",
    "INSTALLER_WAN_VAE",
    "INSTALLER_KOKORO_MODEL",
    "ProductionProviderSettings",
    "ProductionProviderStack",
    "build_production_provider_stack",
]
