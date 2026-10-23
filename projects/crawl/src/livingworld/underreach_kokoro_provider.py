"""Concrete local Kokoro TTS provider for Underreach narration.

Production defaults invoke the exact Kokoro-82M v1.0 files installed by
``install-underreach-media-pipeline.bat`` through the installer's dedicated
Python environment.  The older loopback OpenAI-compatible HTTP backend remains
available for explicit development configurations.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any, Literal
import wave

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .underreach_media_foundation import ProviderDescriptor, ProviderKind
from .underreach_narration_captions_audio import (
    HeadlessVoiceProvider,
    NarrationAudioError,
    VoiceSynthesisOutput,
    VoiceSynthesisRequest,
)


PROTOCOL = "underreach.kokoro-provider.v1"
STACK_VERSION = "production-provider-stack.1"
KOKORO_INSTALLER_MODEL_FILE = "kokoro-v1_0.pth"
KOKORO_INSTALLER_REPO = "hexgrad/Kokoro-82M"


class KokoroProviderError(RuntimeError):
    """Raised when the local Kokoro backend cannot satisfy the voice contract."""


class KokoroProviderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    backend: Literal["http", "subprocess"] = "http"
    base_url: str = "http://127.0.0.1:8880/v1"
    model: str = "kokoro"
    voice: str = "af_bella"
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    timeout_seconds: float = Field(default=180.0, gt=0.0, le=1800.0)
    python_executable: Path | None = None
    model_home: Path | None = None
    runner_path: Path | None = None

    @model_validator(mode="after")
    def validate_config(self) -> "KokoroProviderConfig":
        if not self.model.strip() or not self.voice.strip():
            raise ValueError("Kokoro model and voice must be non-empty")
        if self.backend == "http":
            if not self.base_url.startswith(("http://127.0.0.1", "http://localhost", "http://[::1]")):
                raise ValueError("Kokoro HTTP provider must use a loopback-only endpoint")
        else:
            if self.python_executable is None or self.model_home is None or self.runner_path is None:
                raise ValueError("Kokoro subprocess backend requires python_executable, model_home, and runner_path")
        return self


def _wav_info(payload: bytes) -> tuple[int, int, int]:
    if not payload.startswith(b"RIFF") or b"WAVE" not in payload[:16]:
        raise KokoroProviderError("Kokoro response was not a RIFF/WAVE payload")
    try:
        with wave.open(BytesIO(payload), "rb") as handle:
            channels = int(handle.getnchannels())
            sample_rate = int(handle.getframerate())
            frames = int(handle.getnframes())
    except (wave.Error, EOFError) as exc:
        raise KokoroProviderError("Kokoro WAV payload could not be parsed") from exc
    if channels not in {1, 2} or sample_rate < 8000 or frames <= 0:
        raise KokoroProviderError("Kokoro WAV metadata is outside the accepted voice contract")
    duration_ms = max(1, int(round(frames * 1000.0 / sample_rate)))
    return sample_rate, channels, duration_ms


class KokoroVoiceProvider(HeadlessVoiceProvider):
    """Local Kokoro adapter with installer-native subprocess production mode."""

    def __init__(
        self,
        config: KokoroProviderConfig | None = None,
        *,
        client: httpx.Client | None = None,
        descriptor: ProviderDescriptor | None = None,
    ) -> None:
        self.config = config or KokoroProviderConfig()
        self._client = client
        self._descriptor = descriptor or ProviderDescriptor(
            provider_id="kokoro_local_tts",
            kind=ProviderKind.VOICE,
            local=True,
            paid=False,
            available=True,
            healthy=True,
            capability_flags=("headless_voice", "wav_output", "kokoro", "offline"),
            deterministic_seed=True,
            max_duration_seconds=300.0,
            estimated_vram_mb=1536,
            estimated_runtime_seconds=6.0,
            estimated_cost_microusd=0,
            quality_rank=90,
            quality_profile="kokoro_local_production_voice",
        )
        if self._descriptor.kind != ProviderKind.VOICE:
            raise NarrationAudioError("Kokoro descriptor must have kind=voice")

    @property
    def descriptor(self) -> ProviderDescriptor:
        return self._descriptor

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            if self._client is not None:
                response = self._client.request(method, path, **kwargs)
            else:
                with httpx.Client(base_url=self.config.base_url, timeout=self.config.timeout_seconds) as client:
                    response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            raise KokoroProviderError(f"Kokoro request failed: {type(exc).__name__}") from exc

    def _subprocess_assets(self) -> dict[str, Path]:
        assert self.config.python_executable is not None
        assert self.config.model_home is not None
        assert self.config.runner_path is not None
        home = self.config.model_home
        return {
            "python": self.config.python_executable,
            "runner": self.config.runner_path,
            "config": home / "config.json",
            "model": home / KOKORO_INSTALLER_MODEL_FILE,
            "voice": home / "voices" / f"{self.config.voice}.pt",
        }

    def health(self) -> dict[str, Any]:
        if self.config.backend == "subprocess":
            assets = self._subprocess_assets()
            missing = [name for name, path in assets.items() if not path.is_file()]
            return {
                "provider_id": self.descriptor.provider_id,
                "ready": not missing,
                "backend": "subprocess",
                "model": "Kokoro-82M v1.0",
                "model_file": KOKORO_INSTALLER_MODEL_FILE,
                "voice": self.config.voice,
                "model_home": str(self.config.model_home),
                "missing_assets": missing,
                "exact_installer_model": not missing,
            }

        errors: list[str] = []
        for path in ("/audio/voices", "/models"):
            try:
                response = self._request("GET", path)
                body: Any
                try:
                    body = response.json()
                except ValueError:
                    body = response.text
                return {
                    "provider_id": self.descriptor.provider_id,
                    "ready": True,
                    "backend": "http",
                    "model": self.config.model,
                    "voice": self.config.voice,
                    "health_path": path,
                    "response": body,
                }
            except KokoroProviderError as exc:
                errors.append(str(exc))
        return {
            "provider_id": self.descriptor.provider_id,
            "ready": False,
            "backend": "http",
            "model": self.config.model,
            "voice": self.config.voice,
            "errors": errors,
        }

    def _synthesize_subprocess(self, request: VoiceSynthesisRequest) -> VoiceSynthesisOutput:
        assets = self._subprocess_assets()
        missing = [name for name, path in assets.items() if not path.is_file()]
        if missing:
            raise KokoroProviderError(f"Kokoro installer assets are missing: {','.join(missing)}")

        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="underreach-kokoro-") as temp_dir:
            output = Path(temp_dir) / "narration.wav"
            command = [
                str(assets["python"]),
                str(assets["runner"]),
                "--model-home",
                str(self.config.model_home),
                "--voice",
                self.config.voice,
                "--speed",
                str(self.config.speed),
                "--output",
                str(output),
            ]
            try:
                process = subprocess.run(
                    command,
                    input=request.spec.script,
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    timeout=self.config.timeout_seconds,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise KokoroProviderError("Kokoro subprocess failed to start or timed out") from exc
            if process.returncode != 0 or not output.is_file():
                detail = (process.stderr or process.stdout or "unknown subprocess failure")[-800:]
                raise KokoroProviderError(f"Kokoro subprocess failed: {detail}")
            payload = output.read_bytes()

        sample_rate, channels, duration_ms = _wav_info(payload)
        elapsed_ms = max(0, int(round((time.monotonic() - started) * 1000.0)))
        return VoiceSynthesisOutput(
            wav_bytes=payload,
            sample_rate=sample_rate,
            channels=channels,
            duration_ms=duration_ms,
            metadata={
                "renderer": "kokoro_subprocess",
                "model": "Kokoro-82M v1.0",
                "model_file": KOKORO_INSTALLER_MODEL_FILE,
                "voice": self.config.voice,
                "speed": self.config.speed,
                "elapsed_ms": elapsed_ms,
                "exact_installer_model": True,
                "verified_script_verbatim": True,
                "presentation_only": True,
            },
            actual_gpu_ms=0,
        )

    def synthesize(self, request: VoiceSynthesisRequest) -> VoiceSynthesisOutput:
        if not request.spec.script.strip():
            raise KokoroProviderError("Kokoro voice request contains an empty verified script")
        if self.config.backend == "subprocess":
            return self._synthesize_subprocess(request)

        started = time.monotonic()
        response = self._request(
            "POST",
            "/audio/speech",
            json={
                "model": self.config.model,
                "input": request.spec.script,
                "voice": self.config.voice,
                "response_format": "wav",
                "speed": self.config.speed,
            },
            headers={"Accept": "audio/wav"},
        )
        payload = bytes(response.content)
        sample_rate, channels, duration_ms = _wav_info(payload)
        elapsed_ms = max(0, int(round((time.monotonic() - started) * 1000.0)))
        return VoiceSynthesisOutput(
            wav_bytes=payload,
            sample_rate=sample_rate,
            channels=channels,
            duration_ms=duration_ms,
            metadata={
                "renderer": "kokoro_http",
                "model": self.config.model,
                "voice": self.config.voice,
                "speed": self.config.speed,
                "elapsed_ms": elapsed_ms,
                "verified_script_verbatim": True,
                "presentation_only": True,
            },
            actual_gpu_ms=0,
        )


__all__ = [
    "PROTOCOL",
    "STACK_VERSION",
    "KOKORO_INSTALLER_MODEL_FILE",
    "KOKORO_INSTALLER_REPO",
    "KokoroProviderConfig",
    "KokoroProviderError",
    "KokoroVoiceProvider",
]
