"""Underreach Slice 29D.2 real-animation source binding and contact planning.

This layer is presentation-only. It binds accepted 29D.1 semantic attack windows
onto measured Unreal animation assets and derives bounded motion-warp/contact
requests. Canonical simulation state, damage, death, timing and outcomes remain
owned by the 29C/29D source proof.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from typing import Any

from .underreach_combat_presentation import build_combat_presentation_proof

PROTOCOL = "underreach.animation-binding.v1"
GENERATOR_VERSION = "29d2.1"
SOURCE_PROTOCOL = "underreach.combat-presentation.v1"
PROFILE_PROTOCOL = "crawl.presentation-attack-profile-measurements.v3"
MAX_PRESENTATION_ALIGNMENT_CM = 180.0
MIN_PLAUSIBLE_REACH_CM = 60.0
MIN_POSE_VARIATION = 8

ATTACK_ASSET_ORDER = (
    "MM_Attack_01",
    "MM_Attack_02",
    "MM_Attack_03",
    "MM_ChargedAttack",
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def rebuild_digest(manifest: dict[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("digest", None)
    return _digest(payload)


def _distance(a: dict[str, Any] | None, b: dict[str, Any] | None) -> float:
    if not a or not b:
        return 0.0
    return math.hypot(float(b["x"]) - float(a["x"]), float(b["y"]) - float(a["y"]))


def _profiles_by_name(measurements: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if measurements.get("protocol") != PROFILE_PROTOCOL or measurements.get("authoritative") is not False:
        raise ValueError("29D.2 requires non-authoritative measured attack profiles v3")
    if measurements.get("evaluation_mode") != "anim_pose_component_space_root_locked":
        raise ValueError("29D.2 attack measurements use unsupported evaluation mode")
    profiles = measurements.get("profiles") or []
    result: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        name = str(profile.get("asset_name", ""))
        if not name or name in result:
            raise ValueError("29D.2 duplicate or unnamed measured attack profile")
        variation = profile.get("pose_variation") or {}
        if max((int(variation.get(key, 0)) for key in ("unique_forward", "unique_lateral", "unique_height")), default=0) <= MIN_POSE_VARIATION:
            raise ValueError(f"29D.2 frozen measured attack profile: {name}")
        phase = float(profile.get("candidate_contact_phase", -1.0))
        reach = float(profile.get("candidate_forward_reach_cm", 0.0))
        if not 0.0 < phase < 1.0 or reach < MIN_PLAUSIBLE_REACH_CM:
            raise ValueError(f"29D.2 implausible measured attack profile: {name}")
        if not profile.get("asset_path") or not profile.get("contact_effector"):
            raise ValueError(f"29D.2 incomplete measured attack profile: {name}")
        result[name] = profile
    missing = [name for name in ATTACK_ASSET_ORDER if name not in result]
    if missing:
        raise ValueError("29D.2 required measured attack assets missing: " + ", ".join(missing))
    return result


def build_animation_binding(
    combat_proof: dict[str, Any],
    measurements: dict[str, Any],
) -> dict[str, Any]:
    presentation = combat_proof.get("presentation") or {}
    source = combat_proof.get("source") or {}
    if presentation.get("protocol") != SOURCE_PROTOCOL or presentation.get("authoritative") is not False:
        raise ValueError("29D.2 requires accepted non-authoritative 29D.1 presentation")
    profiles = _profiles_by_name(measurements)

    bindings: list[dict[str, Any]] = []
    attack_index = 0
    for window in presentation.get("windows") or []:
        kind = window.get("presentation_kind")
        if kind == "attack":
            asset_name = ATTACK_ASSET_ORDER[attack_index % len(ATTACK_ASSET_ORDER)]
            attack_index += 1
            profile = profiles[asset_name]
            separation = _distance(window.get("canonical_position_cm"), window.get("canonical_target_position_cm"))
            raw_alignment = max(0.0, separation - float(profile["candidate_forward_reach_cm"]))
            alignment = min(raw_alignment, MAX_PRESENTATION_ALIGNMENT_CM)
            bindings.append({
                "binding_id": f"binding_{len(bindings):04d}",
                "window_id": window["window_id"],
                "source_frame_index": window["source_frame_index"],
                "source_action_index": window["source_action_index"],
                "actor_id": window["actor_id"],
                "target_id": window.get("target_id"),
                "presentation_kind": "attack",
                "binding_status": "measured_real_asset",
                "semantic_slot": window.get("animation_slot"),
                "asset_name": asset_name,
                "asset_path": profile["asset_path"],
                "source_duration_seconds": float(profile["source_duration_seconds"]),
                "contact_effector": profile["contact_effector"],
                "target_bone": profile.get("target_torso_bone", "spine_05"),
                "contact_phase": float(profile["candidate_contact_phase"]),
                "contact_seconds_source": float(profile["candidate_contact_seconds"]),
                "profile_forward_reach_cm": float(profile["candidate_forward_reach_cm"]),
                "profile_contact_height_cm": float(profile["candidate_contact_height_cm"]),
                "profile_pose_variation": deepcopy(profile["pose_variation"]),
                "canonical_pair_separation_cm": round(separation, 6),
                "raw_alignment_request_cm": round(raw_alignment, 6),
                "bounded_alignment_request_cm": round(alignment, 6),
                "alignment_was_clamped": raw_alignment > MAX_PRESENTATION_ALIGNMENT_CM,
                "motion_policy": "presentation_motion_warp_or_ik",
                "facing_yaw_degrees": window.get("facing_yaw_degrees"),
                "camera_shot": window.get("camera_shot"),
                "presentation_contact_seconds": window.get("contact_seconds"),
                "canonical_hit": bool(window.get("canonical_hit", False)),
                "canonical_damage": float(window.get("canonical_damage", 0.0)),
            })
        elif kind in {"hit_reaction", "death"}:
            # No real reaction/death asset profile is claimed by this slice.
            bindings.append({
                "binding_id": f"binding_{len(bindings):04d}",
                "window_id": window["window_id"],
                "source_frame_index": window["source_frame_index"],
                "source_action_index": window["source_action_index"],
                "actor_id": window["actor_id"],
                "target_id": window.get("target_id"),
                "presentation_kind": kind,
                "binding_status": "semantic_fallback",
                "semantic_slot": window.get("animation_slot"),
                "asset_name": None,
                "asset_path": None,
                "facing_yaw_degrees": window.get("facing_yaw_degrees"),
                "camera_shot": window.get("camera_shot"),
            })

    manifest = {
        "protocol": PROTOCOL,
        "generator_version": GENERATOR_VERSION,
        "authoritative": False,
        "canonical_state_mutation_allowed": False,
        "simulation_time_independent": True,
        "source_protocol": SOURCE_PROTOCOL,
        "source_presentation_digest": presentation["digest"],
        "source_canonical_digest": source["canonical_digest"],
        "source_outcome": source["canonical_truth"]["outcome"],
        "source_windows_digest": _digest(presentation["windows"]),
        "profile_protocol": PROFILE_PROTOCOL,
        "profile_measurements_digest": _digest(measurements),
        "real_attack_assets_required": list(ATTACK_ASSET_ORDER),
        "reaction_death_asset_policy": "semantic_fallback_until_real_profiles_are_validated",
        "max_presentation_alignment_cm": MAX_PRESENTATION_ALIGNMENT_CM,
        "bindings": bindings,
    }
    manifest["digest"] = _digest(manifest)
    validate_animation_binding(manifest, combat_proof, measurements)
    return manifest


def validate_animation_binding(
    manifest: dict[str, Any],
    combat_proof: dict[str, Any],
    measurements: dict[str, Any],
) -> bool:
    if manifest.get("protocol") != PROTOCOL or manifest.get("authoritative") is not False:
        raise ValueError("29D.2 animation binding protocol/authority invalid")
    if manifest.get("canonical_state_mutation_allowed") is not False or manifest.get("simulation_time_independent") is not True:
        raise ValueError("29D.2 violated presentation authority boundary")
    presentation = combat_proof["presentation"]
    source = combat_proof["source"]
    if manifest.get("source_presentation_digest") != presentation.get("digest"):
        raise ValueError("29D.2 wrong 29D.1 presentation digest")
    if manifest.get("source_canonical_digest") != source.get("canonical_digest"):
        raise ValueError("29D.2 wrong canonical digest")
    if manifest.get("source_outcome") != source["canonical_truth"]["outcome"]:
        raise ValueError("29D.2 changed canonical outcome")
    if manifest.get("source_windows_digest") != _digest(presentation.get("windows") or []):
        raise ValueError("29D.2 source windows digest mismatch")
    if manifest.get("profile_measurements_digest") != _digest(measurements):
        raise ValueError("29D.2 measured profile digest mismatch")
    profiles = _profiles_by_name(measurements)
    windows = {window["window_id"]: window for window in presentation["windows"]}
    ids: set[str] = set()
    bound_attack_windows: set[str] = set()
    for binding in manifest.get("bindings") or []:
        if binding["binding_id"] in ids:
            raise ValueError("29D.2 duplicate binding ids")
        ids.add(binding["binding_id"])
        window = windows.get(binding["window_id"])
        if window is None:
            raise ValueError("29D.2 binding references unknown 29D.1 window")
        if binding["presentation_kind"] != window["presentation_kind"]:
            raise ValueError("29D.2 binding changed presentation action kind")
        if binding.get("facing_yaw_degrees") != window.get("facing_yaw_degrees"):
            raise ValueError("29D.2 binding changed accepted facing")
        if binding.get("camera_shot") != window.get("camera_shot"):
            raise ValueError("29D.2 binding changed accepted Feed camera intent")
        if binding["presentation_kind"] == "attack":
            bound_attack_windows.add(binding["window_id"])
            if binding.get("binding_status") != "measured_real_asset":
                raise ValueError("29D.2 attack is not bound to a measured real asset")
            profile = profiles.get(binding.get("asset_name"))
            if profile is None or binding.get("asset_path") != profile.get("asset_path"):
                raise ValueError("29D.2 attack asset/profile binding mismatch")
            if bool(binding.get("canonical_hit")) != bool(window.get("canonical_hit")):
                raise ValueError("29D.2 changed canonical hit result")
            if float(binding.get("canonical_damage", 0.0)) != float(window.get("canonical_damage", 0.0)):
                raise ValueError("29D.2 changed canonical damage")
            if not 0.0 <= float(binding["bounded_alignment_request_cm"]) <= MAX_PRESENTATION_ALIGNMENT_CM:
                raise ValueError("29D.2 unbounded presentation contact correction")
        else:
            if binding.get("binding_status") != "semantic_fallback" or binding.get("asset_path") is not None:
                raise ValueError("29D.2 falsely claimed real reaction/death asset")
    attack_windows = {window["window_id"] for window in presentation["windows"] if window["presentation_kind"] == "attack"}
    if bound_attack_windows != attack_windows:
        raise ValueError("29D.2 did not bind every accepted attack window")
    if manifest.get("digest") != rebuild_digest(manifest):
        raise ValueError("29D.2 animation binding digest mismatch")
    return True


def build_animation_binding_proof(
    measurements: dict[str, Any],
    seed: str = "underreach-29d2-animation-contact-proof",
) -> dict[str, Any]:
    combat_proof = build_combat_presentation_proof(seed)
    binding = build_animation_binding(combat_proof, measurements)
    return {"combat_proof": combat_proof, "binding": binding}
