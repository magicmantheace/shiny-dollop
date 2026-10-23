"""Slice 29D.3: bind hit reactions and deaths to measured real Unreal assets.

This module is presentation-only. Canonical hit, damage, death, actor positions,
outcome, and Ledger truth remain owned by the accepted 29C/29D source chain.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

from .underreach_animation_binding import (
    PROFILE_PROTOCOL as ATTACK_PROFILE_PROTOCOL,
    build_animation_binding_proof,
    validate_animation_binding,
)

PROTOCOL = "underreach.reaction-death-binding.v1"
GENERATOR_VERSION = "29d3.1"
PROFILE_PROTOCOL = "underreach.reaction-death-profile-measurements.v1"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def rebuild_digest(manifest: dict[str, Any]) -> str:
    value = dict(manifest)
    value.pop("digest", None)
    return _digest(value)


def _profiles(measurements: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    if measurements.get("protocol") != PROFILE_PROTOCOL or measurements.get("authoritative") is not False:
        raise ValueError("29D.3 requires non-authoritative reaction/death measurements")
    if measurements.get("evaluation_mode") != "anim_pose_component_space_root_locked":
        raise ValueError("29D.3 profile evaluation mode unsupported")
    result = {"hit_reaction": [], "death": []}
    seen: set[str] = set()
    for profile in measurements.get("profiles") or []:
        path = str(profile.get("asset_path", ""))
        kind = str(profile.get("kind", ""))
        if not path or path in seen or kind not in result:
            raise ValueError("29D.3 duplicate, unnamed, or unclassified profile")
        seen.add(path)
        variation = profile.get("pose_variation") or {}
        if max(int(variation.get(k, 0)) for k in ("unique_pelvis", "unique_spine", "unique_head")) <= 4:
            raise ValueError(f"29D.3 frozen measured profile: {path}")
        duration = float(profile.get("source_duration_seconds", 0.0))
        if duration <= 0.10:
            raise ValueError(f"29D.3 implausibly short measured profile: {path}")
        result[kind].append(profile)
    for kind in result:
        result[kind].sort(key=lambda p: (str(p.get("asset_name", "")), str(p.get("asset_path", ""))))
        if not result[kind]:
            raise ValueError(f"29D.3 no measured real {kind} asset available")
    return result


def build_reaction_death_binding(
    animation_binding_proof: dict[str, Any],
    attack_measurements: dict[str, Any],
    reaction_measurements: dict[str, Any],
) -> dict[str, Any]:
    combat_proof = animation_binding_proof["combat_proof"]
    source_binding = animation_binding_proof["binding"]
    validate_animation_binding(source_binding, combat_proof, attack_measurements)
    profiles = _profiles(reaction_measurements)
    windows = {w["window_id"]: w for w in combat_proof["presentation"]["windows"]}

    attacks_by_source: dict[tuple[int, int], dict[str, Any]] = {}
    for w in combat_proof["presentation"]["windows"]:
        if w["presentation_kind"] == "attack":
            attacks_by_source[(int(w["source_frame_index"]), int(w["source_action_index"]))] = w

    bindings: list[dict[str, Any]] = []
    reaction_i = 0
    death_i = 0
    for old in source_binding["bindings"]:
        item = deepcopy(old)
        kind = item["presentation_kind"]
        if kind not in {"hit_reaction", "death"}:
            bindings.append(item)
            continue
        pool = profiles[kind]
        index = reaction_i if kind == "hit_reaction" else death_i
        profile = pool[index % len(pool)]
        if kind == "hit_reaction":
            reaction_i += 1
        else:
            death_i += 1
        window = windows[item["window_id"]]
        pair_key = (int(window["source_frame_index"]), int(window["source_action_index"]))
        attack = attacks_by_source.get(pair_key)
        if attack is None:
            raise ValueError("29D.3 reaction/death window has no canonical attack pair")
        item.update({
            "binding_status": "measured_real_asset",
            "asset_name": profile["asset_name"],
            "asset_path": profile["asset_path"],
            "source_duration_seconds": float(profile["source_duration_seconds"]),
            "profile_kind": kind,
            "profile_pose_variation": deepcopy(profile["pose_variation"]),
            "paired_attack_window_id": attack["window_id"],
            "paired_attack_contact_seconds": float(attack["contact_seconds"]),
            "presentation_start_seconds": float(window["start_seconds"]),
            "presentation_end_seconds": float(window["end_seconds"]),
            "contact_sync_error_seconds": round(
                abs(float(window["start_seconds"]) - float(attack["contact_seconds"])), 6
            ) if kind == "hit_reaction" else None,
            "terminal_pose_required": kind == "death",
            "canonical_death": bool(window.get("canonical_death", False)),
        })
        bindings.append(item)

    manifest = {
        "protocol": PROTOCOL,
        "generator_version": GENERATOR_VERSION,
        "authoritative": False,
        "canonical_state_mutation_allowed": False,
        "simulation_time_independent": True,
        "source_animation_binding_digest": source_binding["digest"],
        "source_presentation_digest": combat_proof["presentation"]["digest"],
        "source_canonical_digest": combat_proof["source"]["canonical_digest"],
        "attack_profile_protocol": ATTACK_PROFILE_PROTOCOL,
        "attack_profile_measurements_digest": _digest(attack_measurements),
        "reaction_death_profile_protocol": PROFILE_PROTOCOL,
        "reaction_death_measurements_digest": _digest(reaction_measurements),
        "reaction_asset_count": len(profiles["hit_reaction"]),
        "death_asset_count": len(profiles["death"]),
        "bindings": bindings,
    }
    manifest["digest"] = _digest(manifest)
    validate_reaction_death_binding(manifest, animation_binding_proof, attack_measurements, reaction_measurements)
    return manifest


def validate_reaction_death_binding(
    manifest: dict[str, Any],
    animation_binding_proof: dict[str, Any],
    attack_measurements: dict[str, Any],
    reaction_measurements: dict[str, Any],
) -> bool:
    combat_proof = animation_binding_proof["combat_proof"]
    source_binding = animation_binding_proof["binding"]
    if manifest.get("protocol") != PROTOCOL or manifest.get("authoritative") is not False:
        raise ValueError("29D.3 protocol/authority invalid")
    if manifest.get("canonical_state_mutation_allowed") is not False or manifest.get("simulation_time_independent") is not True:
        raise ValueError("29D.3 authority boundary violated")
    if manifest.get("source_animation_binding_digest") != source_binding["digest"]:
        raise ValueError("29D.3 wrong 29D.2 binding digest")
    if manifest.get("source_presentation_digest") != combat_proof["presentation"]["digest"]:
        raise ValueError("29D.3 wrong 29D.1 presentation digest")
    if manifest.get("source_canonical_digest") != combat_proof["source"]["canonical_digest"]:
        raise ValueError("29D.3 wrong canonical digest")
    if manifest.get("attack_profile_measurements_digest") != _digest(attack_measurements):
        raise ValueError("29D.3 attack measurement digest mismatch")
    if manifest.get("reaction_death_measurements_digest") != _digest(reaction_measurements):
        raise ValueError("29D.3 reaction/death measurement digest mismatch")
    profiles = _profiles(reaction_measurements)
    profile_paths = {p["asset_path"] for group in profiles.values() for p in group}
    source_by_id = {b["binding_id"]: b for b in source_binding["bindings"]}
    windows = {w["window_id"]: w for w in combat_proof["presentation"]["windows"]}
    ids: set[str] = set()
    real_reactions = real_deaths = 0
    for item in manifest.get("bindings") or []:
        bid = item["binding_id"]
        if bid in ids or bid not in source_by_id:
            raise ValueError("29D.3 duplicate or unknown binding")
        ids.add(bid)
        old = source_by_id[bid]
        window = windows[item["window_id"]]
        for field in ("window_id", "source_frame_index", "source_action_index", "actor_id", "target_id", "presentation_kind", "facing_yaw_degrees", "camera_shot"):
            if item.get(field) != old.get(field):
                raise ValueError(f"29D.3 changed accepted binding field: {field}")
        kind = item["presentation_kind"]
        if kind in {"hit_reaction", "death"}:
            if item.get("binding_status") != "measured_real_asset" or item.get("asset_path") not in profile_paths:
                raise ValueError("29D.3 reaction/death is not bound to a measured real asset")
            if kind == "hit_reaction":
                real_reactions += 1
                if float(item.get("contact_sync_error_seconds", 999)) > 0.001:
                    raise ValueError("29D.3 hit reaction is not synchronized to attack contact")
                if window.get("canonical_hit") is not True:
                    raise ValueError("29D.3 invented reaction for non-hit")
            else:
                real_deaths += 1
                if item.get("canonical_death") is not True or item.get("terminal_pose_required") is not True:
                    raise ValueError("29D.3 death binding lacks canonical death/terminal hold")
        elif item != old:
            raise ValueError("29D.3 changed non-reaction/death 29D.2 binding")
    expected_reactions = sum(w["presentation_kind"] == "hit_reaction" for w in windows.values())
    expected_deaths = sum(w["presentation_kind"] == "death" for w in windows.values())
    if real_reactions != expected_reactions or real_deaths != expected_deaths:
        raise ValueError("29D.3 did not bind every reaction/death window")
    if manifest.get("digest") != rebuild_digest(manifest):
        raise ValueError("29D.3 binding digest mismatch")
    return True


def build_reaction_death_binding_proof(
    attack_measurements: dict[str, Any],
    reaction_measurements: dict[str, Any],
    seed: str = "underreach-29d3-reaction-death-proof",
) -> dict[str, Any]:
    animation_binding_proof = build_animation_binding_proof(attack_measurements, seed)
    binding = build_reaction_death_binding(animation_binding_proof, attack_measurements, reaction_measurements)
    return {"animation_binding_proof": animation_binding_proof, "reaction_death_binding": binding}
