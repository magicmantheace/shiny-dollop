"""Concrete local ComfyUI providers for Underreach still-image and I2V media.

The adapters talk only to a loopback ComfyUI server. ComfyUI owns model loading,
VRAM offload, and graph execution; Crawl retains durable job scheduling,
provenance, review state, and canonical authority boundaries.

Still images implement the accepted HeadlessImageProvider contract. Wan/equivalent
I2V workflows implement the accepted HeadlessVideoProvider contract and write a
short MP4 to the output path supplied by the 30.5.10 GPU scheduler.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
import time
from typing import Any, Iterable
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .runtime_checkpoint import canonical_json, payload_digest
from .underreach_headless_local_image_production import (
    HeadlessImageProvider,
    ImageProductionError,
    ImageRenderOutput,
    ImageRenderRequest,
)
from .underreach_local_video_enhancement import (
    HeadlessVideoProvider,
    VideoEnhancementError,
    VideoRenderOutput,
    VideoRenderRequest,
)
from .underreach_media_foundation import MediaPersistence, ProviderDescriptor, ProviderKind


PROTOCOL = "underreach.comfyui-providers.v1"
STACK_VERSION = "production-provider-stack.1"


class ComfyUIProviderError(RuntimeError):
    """Raised when a local ComfyUI execution cannot satisfy its provider contract."""


class ComfyUIProviderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_url: str = "http://127.0.0.1:8188"
    timeout_seconds: float = Field(default=1800.0, gt=0.0, le=7200.0)
    poll_interval_seconds: float = Field(default=1.0, gt=0.0, le=30.0)
    image_checkpoint: str | None = None
    image_workflow_path: Path | None = None
    video_workflow_path: Path | None = None
    image_steps: int = Field(default=24, ge=1, le=150)
    image_cfg: float = Field(default=5.5, ge=0.0, le=30.0)
    image_sampler: str = "euler"
    image_scheduler: str = "normal"
    video_generation_width: int = Field(default=432, ge=128, le=1080)
    video_generation_height: int = Field(default=768, ge=128, le=1920)
    video_generation_fps: int = Field(default=16, ge=4, le=60)
    video_max_frames: int = Field(default=81, ge=9, le=161)
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    free_gpu_after_image: bool = False
    free_gpu_after_video: bool = True

    @model_validator(mode="after")
    def validate_config(self) -> "ComfyUIProviderConfig":
        if not self.base_url.startswith(("http://127.0.0.1", "http://localhost", "http://[::1]")):
            raise ValueError("ComfyUI provider defaults to a loopback-only local endpoint")
        if self.video_generation_width * 16 != self.video_generation_height * 9:
            raise ValueError("ComfyUI Wan generation resolution must remain exact 9:16")
        if self.video_generation_width % 16 or self.video_generation_height % 16:
            raise ValueError("ComfyUI Wan generation dimensions must be divisible by 16")
        return self


class ComfyUIExecution(BaseModel):
    model_config = ConfigDict(frozen=True)

    prompt_id: str
    output: dict[str, Any]
    elapsed_ms: int = Field(ge=0)


def _safe_media_uri(uri: str) -> PurePosixPath:
    value = PurePosixPath(uri)
    if value.is_absolute() or ".." in value.parts or "://" in uri:
        raise ComfyUIProviderError("ComfyUI provider requires safe relative media artifact URIs")
    return value


def _load_workflow(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ComfyUIProviderError(f"ComfyUI workflow is unreadable: {path}") from exc
    if not isinstance(payload, dict) or not payload:
        raise ComfyUIProviderError("ComfyUI API workflow must be a non-empty JSON object")
    # API exports may be wrapped by callers; accept the exact prompt object or a
    # top-level {prompt:{...}} wrapper without depending on UI workflow format.
    prompt = payload.get("prompt") if isinstance(payload.get("prompt"), dict) else payload
    if not all(isinstance(value, dict) for value in prompt.values()):
        raise ComfyUIProviderError("ComfyUI workflow does not look like API-format prompt JSON")
    return deepcopy(prompt)


def _replace_placeholders(value: Any, replacements: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: _replace_placeholders(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_placeholders(item, replacements) for item in value]
    if isinstance(value, str):
        if value in replacements:
            return replacements[value]
        result = value
        for marker, replacement in replacements.items():
            if marker in result:
                result = result.replace(marker, str(replacement))
        return result
    return value


def _node_title(node: dict[str, Any]) -> str:
    meta = node.get("_meta")
    return str(meta.get("title", "")).lower() if isinstance(meta, dict) else ""


def _patch_workflow(
    workflow: dict[str, Any],
    *,
    prompt: str,
    negative_prompt: str,
    seed: int,
    width: int,
    height: int,
    generation_width: int,
    generation_height: int,
    frames: int,
    fps: int,
    input_image: str | None,
    output_prefix: str,
    checkpoint: str | None,
    image_steps: int,
    image_cfg: float,
    image_sampler: str,
    image_scheduler: str,
) -> dict[str, Any]:
    replacements: dict[str, Any] = {
        "{{PROMPT}}": prompt,
        "{{NEGATIVE_PROMPT}}": negative_prompt,
        "{{SEED}}": seed,
        "{{WIDTH}}": width,
        "{{HEIGHT}}": height,
        "{{GEN_WIDTH}}": generation_width,
        "{{GEN_HEIGHT}}": generation_height,
        "{{FRAMES}}": frames,
        "{{FPS}}": fps,
        "{{INPUT_IMAGE}}": input_image or "",
        "{{OUTPUT_PREFIX}}": output_prefix,
        "{{CHECKPOINT}}": checkpoint or "",
    }
    patched = _replace_placeholders(deepcopy(workflow), replacements)
    positive_used = False
    negative_used = False
    for node_id in sorted(patched, key=str):
        node = patched[node_id]
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type", ""))
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        title = _node_title(node)
        if class_type == "CheckpointLoaderSimple" and checkpoint:
            inputs["ckpt_name"] = checkpoint
        elif class_type == "CLIPTextEncode":
            if "negative" in title:
                inputs["text"] = negative_prompt
                negative_used = True
            elif "positive" in title:
                inputs["text"] = prompt
                positive_used = True
            elif not positive_used:
                inputs["text"] = prompt
                positive_used = True
            elif not negative_used:
                inputs["text"] = negative_prompt
                negative_used = True
        elif class_type == "EmptyLatentImage":
            inputs["width"] = width
            inputs["height"] = height
            inputs["batch_size"] = 1
        elif class_type in {"KSampler", "KSamplerAdvanced"}:
            if "seed" in inputs:
                inputs["seed"] = seed
            if "noise_seed" in inputs:
                inputs["noise_seed"] = seed
            if "steps" in inputs:
                inputs["steps"] = image_steps
            if "cfg" in inputs:
                inputs["cfg"] = image_cfg
            if "sampler_name" in inputs:
                inputs["sampler_name"] = image_sampler
            if "scheduler" in inputs:
                inputs["scheduler"] = image_scheduler
        elif class_type == "LoadImage" and input_image:
            inputs["image"] = input_image
        elif class_type in {"Wan22ImageToVideoLatent", "WanImageToVideo", "WanFirstLastFrameToVideo"}:
            for key in ("width", "video_width"):
                if key in inputs:
                    inputs[key] = generation_width
            for key in ("height", "video_height"):
                if key in inputs:
                    inputs[key] = generation_height
            for key in ("length", "frames", "frame_count", "num_frames"):
                if key in inputs:
                    inputs[key] = frames
        elif class_type in {"CreateVideo", "VideoCombine", "VHS_VideoCombine"}:
            for key in ("fps", "frame_rate"):
                if key in inputs:
                    inputs[key] = fps
        if class_type in {"SaveImage", "SaveVideo", "VHS_VideoCombine", "VideoCombine"}:
            for key in ("filename_prefix", "filename", "prefix"):
                if key in inputs and isinstance(inputs[key], str):
                    inputs[key] = output_prefix
                    break
    return patched


def _default_image_workflow(
    *, checkpoint: str, prompt: str, negative_prompt: str, seed: int, width: int, height: int,
    steps: int, cfg: float, sampler: str, scheduler: str, output_prefix: str,
) -> dict[str, Any]:
    # Standard ComfyUI API graph using only core nodes. This works with ordinary
    # SD/SDXL-style checkpoints whose CLIP/VAE are supplied by the checkpoint.
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "2": {"class_type": "CLIPTextEncode", "_meta": {"title": "Positive Prompt"}, "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "_meta": {"title": "Negative Prompt"}, "inputs": {"text": negative_prompt, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": output_prefix, "images": ["6", 0]}},
    }


def _collect_output_refs(value: Any) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    if isinstance(value, dict):
        filename = value.get("filename")
        if isinstance(filename, str) and filename:
            refs.append(
                {
                    "filename": filename,
                    "subfolder": str(value.get("subfolder", "")),
                    "type": str(value.get("type", "output")),
                }
            )
        for nested in value.values():
            refs.extend(_collect_output_refs(nested))
    elif isinstance(value, list):
        for nested in value:
            refs.extend(_collect_output_refs(nested))
    # Preserve first appearance while removing duplicate filename tuples.
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for ref in refs:
        key = (ref["filename"], ref["subfolder"], ref["type"])
        if key not in seen:
            seen.add(key)
            unique.append(ref)
    return unique


class _ComfyUIClient:
    def __init__(self, config: ComfyUIProviderConfig, client: httpx.Client | None = None) -> None:
        self.config = config
        self._client = client

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
            raise ComfyUIProviderError(f"ComfyUI request failed: {type(exc).__name__}") from exc

    def system_stats(self) -> dict[str, Any]:
        response = self._request("GET", "/system_stats")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ComfyUIProviderError("ComfyUI system_stats returned invalid JSON") from exc
        return payload if isinstance(payload, dict) else {}

    def object_info(self) -> dict[str, Any]:
        response = self._request("GET", "/object_info")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ComfyUIProviderError("ComfyUI object_info returned invalid JSON") from exc
        return payload if isinstance(payload, dict) else {}

    def upload_image(self, path: Path, *, subfolder: str = "underreach") -> str:
        if not path.is_file():
            raise ComfyUIProviderError("ComfyUI upload source does not exist")
        with path.open("rb") as handle:
            response = self._request(
                "POST",
                "/upload/image",
                files={"image": (path.name, handle, "image/png")},
                data={"overwrite": "true", "type": "input", "subfolder": subfolder},
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise ComfyUIProviderError("ComfyUI upload returned invalid JSON") from exc
        name = body.get("name") if isinstance(body, dict) else None
        returned_subfolder = body.get("subfolder", subfolder) if isinstance(body, dict) else subfolder
        if not isinstance(name, str) or not name:
            raise ComfyUIProviderError("ComfyUI upload did not return an image name")
        return f"{returned_subfolder}/{name}" if returned_subfolder else name

    def queue(self, workflow: dict[str, Any], *, client_id: str) -> str:
        response = self._request("POST", "/prompt", json={"prompt": workflow, "client_id": client_id})
        try:
            body = response.json()
        except ValueError as exc:
            raise ComfyUIProviderError("ComfyUI prompt submission returned invalid JSON") from exc
        prompt_id = body.get("prompt_id") if isinstance(body, dict) else None
        if not isinstance(prompt_id, str) or not prompt_id:
            node_errors = body.get("node_errors") if isinstance(body, dict) else None
            raise ComfyUIProviderError(f"ComfyUI rejected prompt graph: {node_errors or 'missing prompt_id'}")
        return prompt_id

    def history(self, prompt_id: str) -> dict[str, Any] | None:
        response = self._request("GET", f"/history/{prompt_id}")
        try:
            body = response.json()
        except ValueError as exc:
            raise ComfyUIProviderError("ComfyUI history returned invalid JSON") from exc
        if not isinstance(body, dict):
            return None
        record = body.get(prompt_id)
        return record if isinstance(record, dict) else None

    def execute(self, workflow: dict[str, Any]) -> ComfyUIExecution:
        client_id = f"underreach-{uuid4().hex}"
        started = time.monotonic()
        prompt_id = self.queue(workflow, client_id=client_id)
        deadline = started + self.config.timeout_seconds
        while time.monotonic() < deadline:
            record = self.history(prompt_id)
            if record is not None:
                status = record.get("status")
                if isinstance(status, dict) and status.get("status_str") == "error":
                    raise ComfyUIProviderError("ComfyUI execution reported an error")
                outputs = record.get("outputs")
                if isinstance(outputs, dict):
                    return ComfyUIExecution(
                        prompt_id=prompt_id,
                        output=record,
                        elapsed_ms=max(0, int(round((time.monotonic() - started) * 1000.0))),
                    )
            time.sleep(self.config.poll_interval_seconds)
        raise ComfyUIProviderError("ComfyUI execution timed out")

    def fetch_output(self, ref: dict[str, str]) -> bytes:
        response = self._request(
            "GET",
            "/view",
            params={"filename": ref["filename"], "subfolder": ref["subfolder"], "type": ref["type"]},
        )
        if not response.content:
            raise ComfyUIProviderError("ComfyUI output download was empty")
        return response.content

    def free(self) -> None:
        try:
            self._request("POST", "/free", json={"unload_models": True, "free_memory": True})
        except ComfyUIProviderError:
            # Cleanup is best-effort and must not retroactively fail a completed artifact.
            return


class ComfyUIImageProvider(HeadlessImageProvider):
    """Local ComfyUI still-image backend with deterministic seed/provenance."""

    def __init__(
        self,
        *,
        media: MediaPersistence,
        media_root: str | Path,
        config: ComfyUIProviderConfig | None = None,
        client: httpx.Client | None = None,
        descriptor: ProviderDescriptor | None = None,
    ) -> None:
        self.media = media
        self.media_root = Path(media_root)
        self.config = config or ComfyUIProviderConfig()
        self.client = _ComfyUIClient(self.config, client)
        reference_capable = self.config.image_workflow_path is not None
        self._descriptor = descriptor or ProviderDescriptor(
            provider_id="comfyui_local_image",
            kind=ProviderKind.IMAGE,
            local=True,
            paid=False,
            available=True,
            healthy=True,
            capability_flags=("headless_image", "png_output", "comfyui", "offline"),
            deterministic_seed=True,
            reference_conditioning=reference_capable,
            max_width=2048,
            max_height=2048,
            estimated_vram_mb=10240,
            estimated_runtime_seconds=35.0,
            estimated_cost_microusd=0,
            quality_rank=90,
            quality_profile="comfyui_local_production_image",
        )

    @property
    def descriptor(self) -> ProviderDescriptor:
        return self._descriptor

    def health(self) -> dict[str, Any]:
        stats = self.client.system_stats()
        return {"provider_id": self.descriptor.provider_id, "ready": bool(stats), "system_stats": stats}

    def _artifact_path(self, artifact_id: str) -> Path:
        matches = [item for item in self.media.snapshot()["artifacts"] if item["artifact_id"] == artifact_id]
        if len(matches) != 1 or matches[0]["artifact_kind"] != "image/png":
            raise ComfyUIProviderError("ComfyUI reference requires exactly one persisted PNG artifact")
        artifact = matches[0]
        relative = _safe_media_uri(str(artifact["uri"]))
        path = self.media_root.joinpath(*relative.parts)
        if not path.is_file() or sha256(path.read_bytes()).hexdigest() != artifact["digest"]:
            raise ComfyUIProviderError("ComfyUI reference artifact is missing or digest-invalid")
        return path

    def _workflow(self, request: ImageRenderRequest) -> dict[str, Any]:
        spec = request.spec
        uploaded_reference: str | None = None
        if spec.reference_artifact_ids:
            reference_path = self._artifact_path(spec.reference_artifact_ids[0])
            uploaded_reference = self.client.upload_image(reference_path)
        prefix = f"underreach/{spec.spec_id}"
        if self.config.image_workflow_path is not None:
            base = _load_workflow(self.config.image_workflow_path)
            return _patch_workflow(
                base,
                prompt=spec.prompt,
                negative_prompt=spec.negative_prompt,
                seed=spec.deterministic_seed,
                width=spec.width,
                height=spec.height,
                generation_width=spec.width,
                generation_height=spec.height,
                frames=1,
                fps=1,
                input_image=uploaded_reference,
                output_prefix=prefix,
                checkpoint=self.config.image_checkpoint,
                image_steps=self.config.image_steps,
                image_cfg=self.config.image_cfg,
                image_sampler=self.config.image_sampler,
                image_scheduler=self.config.image_scheduler,
            )
        if spec.reference_artifact_ids:
            raise ComfyUIProviderError("reference-conditioned image work requires an API-format ComfyUI workflow")
        if not self.config.image_checkpoint:
            raise ComfyUIProviderError("ComfyUI image_checkpoint or image_workflow_path must be configured")
        return _default_image_workflow(
            checkpoint=self.config.image_checkpoint,
            prompt=spec.prompt,
            negative_prompt=spec.negative_prompt,
            seed=spec.deterministic_seed,
            width=spec.width,
            height=spec.height,
            steps=self.config.image_steps,
            cfg=self.config.image_cfg,
            sampler=self.config.image_sampler,
            scheduler=self.config.image_scheduler,
            output_prefix=prefix,
        )

    def render(self, request: ImageRenderRequest) -> ImageRenderOutput:
        workflow = self._workflow(request)
        try:
            execution = self.client.execute(workflow)
            refs = _collect_output_refs(execution.output.get("outputs", {}))
            images = [ref for ref in refs if Path(ref["filename"]).suffix.lower() in {".png", ".webp", ".jpg", ".jpeg"}]
            if not images:
                raise ComfyUIProviderError("ComfyUI image workflow produced no downloadable image")
            payload = self.client.fetch_output(images[0])
            if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ComfyUIProviderError("ComfyUI image provider must return PNG output")
            return ImageRenderOutput(
                image_bytes=payload,
                extension=".png",
                metadata={
                    "renderer": "comfyui",
                    "prompt_id": execution.prompt_id,
                    "workflow_digest": payload_digest(workflow),
                    "quality_profile": self.descriptor.quality_profile,
                    "reference_artifact_ids": list(request.spec.reference_artifact_ids),
                    "presentation_only": True,
                },
                actual_gpu_ms=execution.elapsed_ms,
            )
        finally:
            if self.config.free_gpu_after_image:
                self.client.free()


class ComfyUIWanVideoProvider(HeadlessVideoProvider):
    """Local ComfyUI/Wan image-to-video backend for optional 30.5.10 enhancement."""

    def __init__(
        self,
        *,
        config: ComfyUIProviderConfig | None = None,
        client: httpx.Client | None = None,
        descriptor: ProviderDescriptor | None = None,
    ) -> None:
        self.config = config or ComfyUIProviderConfig()
        self.client = _ComfyUIClient(self.config, client)
        self._descriptor = descriptor or ProviderDescriptor(
            provider_id="comfyui_wan22_ti2v_5b",
            kind=ProviderKind.VIDEO,
            local=True,
            paid=False,
            available=True,
            healthy=True,
            capability_flags=("headless_video", "mp4_output", "short_shot", "comfyui", "wan2.2", "offline"),
            deterministic_seed=True,
            reference_conditioning=True,
            image_to_video=True,
            max_width=1080,
            max_height=1920,
            max_duration_seconds=5.0,
            estimated_vram_mb=8192,
            estimated_runtime_seconds=180.0,
            estimated_cost_microusd=0,
            quality_rank=85,
            quality_profile="comfyui_wan2.2_ti2v_5b",
        )

    @property
    def descriptor(self) -> ProviderDescriptor:
        return self._descriptor

    def health(self) -> dict[str, Any]:
        stats = self.client.system_stats()
        workflow_ready = self.config.video_workflow_path is not None and self.config.video_workflow_path.is_file()
        return {"provider_id": self.descriptor.provider_id, "ready": bool(stats) and workflow_ready, "workflow_ready": workflow_ready, "system_stats": stats}

    def _workflow(self, request: VideoRenderRequest, uploaded_image: str) -> dict[str, Any]:
        if self.config.video_workflow_path is None:
            raise ComfyUIProviderError("Wan video provider requires an API-format video_workflow_path")
        base = _load_workflow(self.config.video_workflow_path)
        spec = request.spec
        duration_seconds = spec.source_shot.animation_duration_ms / 1000.0
        frames = min(
            self.config.video_max_frames,
            max(9, int(round(duration_seconds * self.config.video_generation_fps)) + 1),
        )
        return _patch_workflow(
            base,
            prompt=(
                "Animate this exact Underreach presentation still with restrained cinematic motion. "
                "Preserve subject identity, clothing/equipment, composition, and event implication. "
                "Do not add characters, items, text, logos, injuries, deaths, victories, or new gameplay facts."
            ),
            negative_prompt="text, watermark, logo, morphing identity, extra limbs, extra people, invented items, unsupported gameplay events",
            seed=spec.deterministic_seed,
            width=spec.width,
            height=spec.height,
            generation_width=self.config.video_generation_width,
            generation_height=self.config.video_generation_height,
            frames=frames,
            fps=self.config.video_generation_fps,
            input_image=uploaded_image,
            output_prefix=f"underreach/{spec.spec_id}",
            checkpoint=None,
            image_steps=self.config.image_steps,
            image_cfg=self.config.image_cfg,
            image_sampler=self.config.image_sampler,
            image_scheduler=self.config.image_scheduler,
        )

    def _transcode(self, source: Path, request: VideoRenderRequest) -> None:
        spec = request.spec
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            self.config.ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-an",
            "-vf",
            f"scale={spec.width}:{spec.height}:force_original_aspect_ratio=increase,crop={spec.width}:{spec.height},fps={spec.fps}",
            "-t",
            f"{spec.source_shot.animation_duration_ms / 1000.0:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(request.output_path),
        ]
        try:
            process = subprocess.run(command, capture_output=True, text=True, timeout=240, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ComfyUIProviderError("FFmpeg post-processing for Wan output failed to start") from exc
        if process.returncode != 0 or not request.output_path.is_file() or request.output_path.stat().st_size <= 0:
            raise ComfyUIProviderError(f"FFmpeg could not normalize Wan output: {process.stderr[-500:]}")

    def animate(self, request: VideoRenderRequest) -> VideoRenderOutput:
        if not request.source_image_path.is_file():
            raise VideoEnhancementError("Wan source image does not exist")
        uploaded = self.client.upload_image(request.source_image_path, subfolder="underreach-video")
        workflow = self._workflow(request, uploaded)
        try:
            execution = self.client.execute(workflow)
            refs = _collect_output_refs(execution.output.get("outputs", {}))
            videos = [ref for ref in refs if Path(ref["filename"]).suffix.lower() in {".mp4", ".webm", ".mkv", ".mov"}]
            if not videos:
                raise ComfyUIProviderError("ComfyUI Wan workflow produced no downloadable video")
            payload = self.client.fetch_output(videos[0])
            suffix = Path(videos[0]["filename"]).suffix.lower() or ".mp4"
            with tempfile.TemporaryDirectory(prefix="underreach-wan-") as temp_dir:
                raw = Path(temp_dir) / f"wan-output{suffix}"
                raw.write_bytes(payload)
                self._transcode(raw, request)
            return VideoRenderOutput(
                duration_ms=request.spec.source_shot.animation_duration_ms,
                width=request.spec.width,
                height=request.spec.height,
                actual_gpu_ms=execution.elapsed_ms,
                metadata={
                    "renderer": "comfyui_wan2.2",
                    "prompt_id": execution.prompt_id,
                    "workflow_digest": payload_digest(workflow),
                    "generation_width": self.config.video_generation_width,
                    "generation_height": self.config.video_generation_height,
                    "generation_fps": self.config.video_generation_fps,
                    "source_image_sha256": sha256(request.source_image_path.read_bytes()).hexdigest(),
                    "presentation_only": True,
                },
            )
        finally:
            if self.config.free_gpu_after_video:
                self.client.free()


__all__ = [
    "PROTOCOL",
    "STACK_VERSION",
    "ComfyUIProviderConfig",
    "ComfyUIProviderError",
    "ComfyUIExecution",
    "ComfyUIImageProvider",
    "ComfyUIWanVideoProvider",
]
