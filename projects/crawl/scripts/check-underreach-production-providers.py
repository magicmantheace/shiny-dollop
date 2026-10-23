from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import tempfile
from typing import Any

from livingworld.runtime_checkpoint import canonical_json
from livingworld.underreach_media_foundation import MediaPersistence
from livingworld.underreach_production_provider_stack import (
    INSTALLER_KOKORO_MODEL,
    INSTALLER_SDXL_CHECKPOINT,
    INSTALLER_VERIFIER_MODEL,
    INSTALLER_WAN_MODEL,
    INSTALLER_WAN_TEXT_ENCODER,
    INSTALLER_WAN_VAE,
    INSTALLER_WRITER_MODEL,
    ProductionProviderSettings,
    build_production_provider_stack,
)


def _command_ready(value: str) -> bool:
    path = Path(value)
    if path.name == value:
        return shutil.which(value) is not None
    return path.is_file()


def _provider_health(stack_health: dict[str, Any], prefix: str) -> list[dict[str, Any]]:
    providers = stack_health.get("providers", {})
    if not isinstance(providers, dict):
        return []
    return [
        status
        for provider_id, status in providers.items()
        if isinstance(provider_id, str)
        and provider_id.startswith(prefix)
        and isinstance(status, dict)
    ]


def build_report(settings: ProductionProviderSettings) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="underreach-provider-check-") as temp_dir:
        media = MediaPersistence("sqlite:///:memory:")
        media.initialize()
        stack = build_production_provider_stack(
            media,
            media_root=temp_dir,
            settings=settings,
            probe=True,
        )

        image_health = _provider_health(stack.health, "comfyui_local_image")
        video_health = _provider_health(stack.health, "comfyui_wan22_ti2v_5b")
        voice_health = _provider_health(stack.health, "kokoro_local_tts")
        writer_health = _provider_health(stack.health, "ollama_narrative_")
        verifier_health = _provider_health(stack.health, "ollama_verification_")

        report = {
            "stack_version": stack.health.get("stack_version"),
            "local_only": True,
            "paid_providers_configured": False,
            "cloud_providers_configured": False,
            "installer_contract": {
                "writer": INSTALLER_WRITER_MODEL,
                "verifier": INSTALLER_VERIFIER_MODEL,
                "image": INSTALLER_SDXL_CHECKPOINT,
                "video": INSTALLER_WAN_MODEL,
                "video_text_encoder": INSTALLER_WAN_TEXT_ENCODER,
                "video_vae": INSTALLER_WAN_VAE,
                "voice": INSTALLER_KOKORO_MODEL,
            },
            "writer": {
                "ready": stack.ollama_writer is not None,
                "required_model": INSTALLER_WRITER_MODEL,
                "health": writer_health,
            },
            "verifier": {
                "ready": stack.ollama_verifier is not None,
                "required_model": INSTALLER_VERIFIER_MODEL,
                "health": verifier_health,
            },
            "image": {
                "ready": any(item.get("exact_installer_checkpoint_ready") is True for item in image_health),
                "required_checkpoint": INSTALLER_SDXL_CHECKPOINT,
                "health": image_health,
            },
            "video": {
                "ready": any(item.get("exact_installer_models_ready") is True for item in video_health),
                "required_model": INSTALLER_WAN_MODEL,
                "required_text_encoder": INSTALLER_WAN_TEXT_ENCODER,
                "required_vae": INSTALLER_WAN_VAE,
                "workflow": str(settings.comfyui_video_workflow_path),
                "health": video_health,
            },
            "voice": {
                "ready": any(item.get("ready") is True and item.get("exact_installer_model") is True for item in voice_health),
                "backend": settings.kokoro_backend,
                "required_model": INSTALLER_KOKORO_MODEL,
                "model_home": str(settings.kokoro_model_home),
                "health": voice_health,
            },
            "ffmpeg": {
                "ready": _command_ready(settings.ffmpeg_path),
                "command": settings.ffmpeg_path,
            },
            "ffprobe": {
                "ready": _command_ready(settings.ffprobe_path),
                "command": settings.ffprobe_path,
            },
            "factory_health": stack.health,
            "active_descriptors": [item.model_dump(mode="json") for item in stack.descriptors],
        }
        return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check the exact local Underreach production providers installed by install-underreach-media-pipeline.bat."
    )
    parser.add_argument("--require-writer", action="store_true")
    parser.add_argument("--require-image", action="store_true")
    parser.add_argument("--require-voice", action="store_true")
    parser.add_argument("--require-video", action="store_true")
    parser.add_argument("--require-all", action="store_true")
    args = parser.parse_args()

    settings = ProductionProviderSettings()
    report = build_report(settings)
    print(canonical_json(report))

    required = {
        "writer": bool(args.require_writer or args.require_all),
        "image": bool(args.require_image or args.require_all),
        "voice": bool(args.require_voice or args.require_all),
        "video": bool(args.require_video or args.require_all),
    }
    failures: list[str] = []
    if required["writer"] and not report["writer"]["ready"]:
        failures.append("writer")
    if required["image"] and not report["image"]["ready"]:
        failures.append("image")
    if required["voice"] and not report["voice"]["ready"]:
        failures.append("voice")
    if required["video"] and not report["video"]["ready"]:
        failures.append("video")
    if required["video"] and (not report["ffmpeg"]["ready"] or not report["ffprobe"]["ready"]):
        failures.append("ffmpeg")
    if failures:
        print(f"provider_check_failed={','.join(sorted(set(failures)))}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
