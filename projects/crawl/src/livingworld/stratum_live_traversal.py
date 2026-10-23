"""Live multi-Sector traversal presentation state for Underreach Slice 29B.2.1.

This module remains presentation-only. It consumes the accepted Stratum and
multi-Sector manifests, creates a deterministic Descender traversal stream, and
tracks Follow/Auto Feed focus plus checkpoint/resume state. It never authorizes
movement or changes simulation outcomes.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

LIVE_TRAVERSAL_PROTOCOL = "underreach.live-multisector-traversal.v1"
CHECKPOINT_PROTOCOL = "underreach.live-multisector-checkpoint.v1"
GENERATOR_VERSION = "29b2.1.1"
SAMPLES_PER_TRANSITION = 8
FOLLOW_CAMERA_OFFSET_CM = (-520.0, -620.0, 270.0)
AUTO_CAMERA_OFFSET_CM = (620.0, -760.0, 340.0)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _lerp(a: float, b: float, alpha: float) -> float:
    return a + (b - a) * alpha


def _distance(a: dict[str, float], b: dict[str, float]) -> float:
    return math.sqrt(sum((float(a[k]) - float(b[k])) ** 2 for k in ("x", "y", "z")))


def _position_between(a: dict[str, float], b: dict[str, float], alpha: float) -> dict[str, float]:
    return {axis: _lerp(float(a[axis]), float(b[axis]), alpha) for axis in ("x", "y", "z")}


def build_live_traversal_stream(
    stratum_manifest: dict[str, Any],
    multisector_plan: dict[str, Any],
    *,
    descender_id: str = "descender_000",
    samples_per_transition: int = SAMPLES_PER_TRANSITION,
) -> dict[str, Any]:
    """Build a deterministic live presentation stream across the proof route."""
    if stratum_manifest.get("digest") != multisector_plan.get("stratum_environment_digest"):
        raise ValueError("multi-Sector plan does not match Stratum manifest")
    if multisector_plan.get("authoritative") is not False:
        raise ValueError("multi-Sector input must remain presentation-only")
    if samples_per_transition < 2:
        raise ValueError("samples_per_transition must be at least 2")

    by_id = {sector["sector_id"]: sector for sector in stratum_manifest["sectors"]}
    route = list(multisector_plan["proof_route_sector_ids"])
    frames: list[dict[str, Any]] = []
    sequence = 0

    def append_frame(*, sector_id: str, next_sector_id: str | None, phase: str, alpha: float, position: dict[str, float]) -> None:
        nonlocal sequence
        follow_camera = {
            "x": position["x"] + FOLLOW_CAMERA_OFFSET_CM[0],
            "y": position["y"] + FOLLOW_CAMERA_OFFSET_CM[1],
            "z": position["z"] + FOLLOW_CAMERA_OFFSET_CM[2],
        }
        auto_camera = {
            "x": position["x"] + AUTO_CAMERA_OFFSET_CM[0],
            "y": position["y"] + AUTO_CAMERA_OFFSET_CM[1],
            "z": position["z"] + AUTO_CAMERA_OFFSET_CM[2],
        }
        frames.append({
            "sequence": sequence,
            "descender_id": descender_id,
            "sector_id": sector_id,
            "next_sector_id": next_sector_id,
            "phase": phase,
            "transition_alpha": round(alpha, 6),
            "transform": {"x": position["x"], "y": position["y"], "z": 94.0},
            "feed": {
                "follow": {"mode": "follow", "target_id": descender_id, "camera": follow_camera, "stale": False, "empty": False},
                "auto": {"mode": "auto", "target_id": descender_id, "camera": auto_camera, "stale": False, "empty": False},
            },
        })
        sequence += 1

    for index, sector_id in enumerate(route):
        current_origin = dict(by_id[sector_id]["world_origin_cm"])
        append_frame(
            sector_id=sector_id,
            next_sector_id=route[index + 1] if index + 1 < len(route) else None,
            phase="sector_hold",
            alpha=0.0,
            position=current_origin,
        )
        if index + 1 >= len(route):
            continue
        next_id = route[index + 1]
        next_origin = dict(by_id[next_id]["world_origin_cm"])
        for sample in range(1, samples_per_transition + 1):
            alpha = sample / samples_per_transition
            logical_sector = next_id if math.isclose(alpha, 1.0) else sector_id
            append_frame(
                sector_id=logical_sector,
                next_sector_id=None if math.isclose(alpha, 1.0) else next_id,
                phase="sector_arrival" if math.isclose(alpha, 1.0) else "sector_transition",
                alpha=alpha,
                position=_position_between(current_origin, next_origin, alpha),
            )

    stream = {
        "protocol": LIVE_TRAVERSAL_PROTOCOL,
        "generator_version": GENERATOR_VERSION,
        "authoritative": False,
        "descender_id": descender_id,
        "stratum_environment_digest": stratum_manifest["digest"],
        "multisector_digest": multisector_plan["digest"],
        "route_sector_ids": route,
        "samples_per_transition": samples_per_transition,
        "frames": frames,
    }
    validate_live_traversal_stream(stream, stratum_manifest)
    stream["digest"] = _digest(stream)
    return stream


def validate_live_traversal_stream(stream: dict[str, Any], stratum_manifest: dict[str, Any]) -> bool:
    if stream.get("protocol") != LIVE_TRAVERSAL_PROTOCOL or stream.get("authoritative") is not False:
        raise ValueError("live traversal must use the presentation-only protocol")
    if stream.get("stratum_environment_digest") != stratum_manifest.get("digest"):
        raise ValueError("live traversal Stratum digest mismatch")
    frames = stream.get("frames") or []
    if not frames:
        raise ValueError("live traversal has no frames")
    if [frame["sequence"] for frame in frames] != list(range(len(frames))):
        raise ValueError("live traversal frame sequence is not contiguous")
    route = stream.get("route_sector_ids") or []
    if frames[0]["sector_id"] != route[0] or frames[-1]["sector_id"] != route[-1]:
        raise ValueError("live traversal does not span the proof route")
    valid_sectors = {sector["sector_id"] for sector in stratum_manifest["sectors"]}
    visited = []
    previous = None
    for frame in frames:
        if frame["sector_id"] not in valid_sectors:
            raise ValueError("live traversal references an unknown Sector")
        if frame["sector_id"] != previous:
            visited.append(frame["sector_id"])
            previous = frame["sector_id"]
        if frame["feed"]["follow"]["target_id"] != stream["descender_id"]:
            raise ValueError("Follow Feed lost the Descender")
        if frame["feed"]["auto"]["target_id"] != stream["descender_id"]:
            raise ValueError("Auto Feed lost the Descender")
        if frame["feed"]["follow"]["empty"] or frame["feed"]["follow"]["stale"]:
            raise ValueError("Follow Feed contains empty/stale frame")
        if frame["feed"]["auto"]["empty"] or frame["feed"]["auto"]["stale"]:
            raise ValueError("Auto Feed contains empty/stale frame")
    if visited != route:
        raise ValueError("live traversal Sector visit order differs from proof route")
    return True


def make_checkpoint(stream: dict[str, Any], frame_index: int) -> dict[str, Any]:
    if not 0 <= frame_index < len(stream["frames"]):
        raise IndexError("checkpoint frame is outside stream")
    frame = stream["frames"][frame_index]
    checkpoint = {
        "protocol": CHECKPOINT_PROTOCOL,
        "authoritative": False,
        "stream_digest": stream["digest"],
        "stratum_environment_digest": stream["stratum_environment_digest"],
        "multisector_digest": stream["multisector_digest"],
        "descender_id": stream["descender_id"],
        "frame_index": frame_index,
        "sequence": frame["sequence"],
        "current_sector_id": frame["sector_id"],
        "transform": dict(frame["transform"]),
        "follow_target_id": frame["feed"]["follow"]["target_id"],
        "auto_target_id": frame["feed"]["auto"]["target_id"],
    }
    checkpoint["digest"] = _digest(checkpoint)
    return checkpoint


def resume_from_checkpoint(stream: dict[str, Any], checkpoint: dict[str, Any]) -> list[dict[str, Any]]:
    if checkpoint.get("protocol") != CHECKPOINT_PROTOCOL or checkpoint.get("authoritative") is not False:
        raise ValueError("unsupported traversal checkpoint")
    if checkpoint.get("stream_digest") != stream.get("digest"):
        raise ValueError("checkpoint stream digest mismatch")
    if checkpoint.get("stratum_environment_digest") != stream.get("stratum_environment_digest"):
        raise ValueError("checkpoint Stratum digest mismatch")
    if checkpoint.get("multisector_digest") != stream.get("multisector_digest"):
        raise ValueError("checkpoint multi-Sector digest mismatch")
    index = int(checkpoint["frame_index"])
    expected = stream["frames"][index]
    if checkpoint.get("current_sector_id") != expected.get("sector_id"):
        raise ValueError("checkpoint current Sector does not match stream")
    if _distance(checkpoint["transform"], expected["transform"]) > 1e-6:
        raise ValueError("checkpoint Descender transform does not match stream")
    return stream["frames"][index:]


def rebuild_digest(stream: dict[str, Any]) -> str:
    payload = dict(stream)
    payload.pop("digest", None)
    return _digest(payload)
