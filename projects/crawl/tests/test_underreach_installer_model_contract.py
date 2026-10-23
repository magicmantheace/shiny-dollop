from __future__ import annotations

import json
from pathlib import Path

from livingworld.underreach_production_provider_stack import (
    INSTALLER_KOKORO_MODEL,
    INSTALLER_SDXL_CHECKPOINT,
    INSTALLER_VERIFIER_MODEL,
    INSTALLER_WAN_MODEL,
    INSTALLER_WAN_TEXT_ENCODER,
    INSTALLER_WAN_VAE,
    INSTALLER_WRITER_MODEL,
    ProductionProviderSettings,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _contains_string(value: object, expected: str) -> bool:
    if isinstance(value, str):
        return value == expected
    if isinstance(value, dict):
        return any(_contains_string(item, expected) for item in value.values())
    if isinstance(value, list):
        return any(_contains_string(item, expected) for item in value)
    return False


def test_installer_and_runtime_share_exact_model_contract() -> None:
    installer = (REPO_ROOT / "install-underreach-media-pipeline.bat").read_text(encoding="utf-8")
    required_installer_text = (
        f'set "WRITER_MODEL={INSTALLER_WRITER_MODEL}"',
        f'set "VERIFIER_MODEL={INSTALLER_VERIFIER_MODEL}"',
        INSTALLER_SDXL_CHECKPOINT,
        INSTALLER_WAN_MODEL,
        INSTALLER_WAN_TEXT_ENCODER,
        INSTALLER_WAN_VAE,
        INSTALLER_KOKORO_MODEL,
    )
    for expected in required_installer_text:
        assert expected in installer

    settings = ProductionProviderSettings()
    assert settings.ollama_writer_model == INSTALLER_WRITER_MODEL == "qwen3:8b"
    assert settings.ollama_verifier_model == INSTALLER_VERIFIER_MODEL == "qwen3:4b"
    assert settings.comfyui_image_checkpoint == INSTALLER_SDXL_CHECKPOINT == "sd_xl_base_1.0.safetensors"
    assert settings.kokoro_backend == "subprocess"
    assert settings.kokoro_model_home.name == "Kokoro-82M"
    assert settings.kokoro_runner_path.name == "run-underreach-kokoro-tts.py"


def test_bundled_wan_api_workflow_uses_only_installer_wan_assets() -> None:
    workflow_path = REPO_ROOT / "config" / "comfyui" / "wan2.2-ti2v-5b-api.json"
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))

    assert _contains_string(workflow, INSTALLER_WAN_MODEL)
    assert _contains_string(workflow, INSTALLER_WAN_TEXT_ENCODER)
    assert _contains_string(workflow, INSTALLER_WAN_VAE)
    assert _contains_string(workflow, "{{INPUT_IMAGE}}")
    assert _contains_string(workflow, "{{PROMPT}}")
    assert _contains_string(workflow, "{{NEGATIVE_PROMPT}}")
    assert _contains_string(workflow, "{{SEED}}")

    classes = {
        node.get("class_type")
        for node in workflow.values()
        if isinstance(node, dict)
    }
    assert {
        "UNETLoader",
        "CLIPLoader",
        "VAELoader",
        "LoadImage",
        "Wan22ImageToVideoLatent",
        "KSampler",
        "VAEDecode",
        "CreateVideo",
        "SaveVideo",
    }.issubset(classes)
