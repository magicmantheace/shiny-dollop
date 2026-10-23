"""Underreach Slice 29D.4 deterministic combat-motion polish.

This layer consumes the accepted 29D.3 real animation bindings and derives
presentation-only transition, spacing, recoil, foot-lock, contact refinement,
and Feed camera timing directives. It never changes canonical simulation truth.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

from .underreach_reaction_death_binding import (
    build_reaction_death_binding_proof,
    validate_reaction_death_binding,
)

PROTOCOL = "underreach.combat-motion-polish.v1"
GENERATOR_VERSION = "29d4.1"
MAX_PAIR_ALIGNMENT_CM = 120.0
MAX_KNOCKBACK_CM = 32.0
MAX_STAGGER_CM = 18.0
MIN_BLEND_SECONDS = 0.06
MAX_BLEND_SECONDS = 0.18
CAMERA_CONTACT_HOLD_SECONDS = 0.10
DEATH_AFTERMATH_HOLD_SECONDS = 0.45


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def rebuild_digest(manifest: dict[str, Any]) -> str:
    value = dict(manifest)
    value.pop("digest", None)
    return _digest(value)


def _blend_for(kind: str) -> tuple[float, float]:
    if kind == "attack":
        return 0.08, 0.12
    if kind == "hit_reaction":
        return 0.06, 0.10
    if kind == "death":
        return 0.08, 0.16
    return 0.10, 0.10


def build_combat_motion_polish(
    reaction_death_proof: dict[str, Any],
    attack_measurements: dict[str, Any],
    reaction_measurements: dict[str, Any],
) -> dict[str, Any]:
    animation_proof = reaction_death_proof["animation_binding_proof"]
    source = reaction_death_proof["reaction_death_binding"]
    validate_reaction_death_binding(source, animation_proof, attack_measurements, reaction_measurements)
    combat_proof = animation_proof["combat_proof"]
    windows = {w["window_id"]: w for w in combat_proof["presentation"]["windows"]}

    directives: list[dict[str, Any]] = []
    paired_reactions: dict[str, str] = {}
    for binding in source["bindings"]:
        if binding["presentation_kind"] == "hit_reaction":
            paired_reactions[str(binding["paired_attack_window_id"])] = str(binding["window_id"])

    for binding in source["bindings"]:
        kind = str(binding["presentation_kind"])
        if kind not in {"attack", "hit_reaction", "death"}:
            continue
        window = windows[binding["window_id"]]
        blend_in, blend_out = _blend_for(kind)
        directive: dict[str, Any] = {
            "directive_id": f"motion_{len(directives):04d}",
            "binding_id": binding["binding_id"],
            "window_id": binding["window_id"],
            "actor_id": binding["actor_id"],
            "target_id": binding.get("target_id"),
            "presentation_kind": kind,
            "asset_name": binding.get("asset_name"),
            "asset_path": binding.get("asset_path"),
            "facing_yaw_degrees": binding.get("facing_yaw_degrees"),
            "camera_shot": binding.get("camera_shot"),
            "blend_in_seconds": blend_in,
            "blend_out_seconds": blend_out,
            "root_motion_policy": "presentation_only",
            "canonical_position_cm": deepcopy(window.get("canonical_position_cm")),
            "canonical_target_position_cm": deepcopy(window.get("canonical_target_position_cm")),
        }
        if kind == "attack":
            raw_alignment = float(binding.get("bounded_alignment_request_cm", 0.0))
            alignment = min(raw_alignment, MAX_PAIR_ALIGNMENT_CM)
            directive.update({
                "paired_reaction_window_id": paired_reactions.get(str(binding["window_id"])),
                "contact_seconds": float(window["contact_seconds"]),
                "contact_effector": binding.get("contact_effector"),
                "contact_alignment_cm": round(alignment, 6),
                "contact_alignment_clamped": raw_alignment > MAX_PAIR_ALIGNMENT_CM,
                "weapon_contact_refinement": "effector_to_target_centerline",
                "foot_lock_policy": "lock_support_foot_during_contact",
                "foot_slide_budget_cm": 3.0,
                "camera_contact_hold_seconds": CAMERA_CONTACT_HOLD_SECONDS,
                "canonical_hit": bool(binding.get("canonical_hit", False)),
                "canonical_damage": float(binding.get("canonical_damage", 0.0)),
            })
        elif kind == "hit_reaction":
            damage = float(window.get("canonical_damage", 0.0))
            displacement = MAX_KNOCKBACK_CM if damage >= 0.08 else MAX_STAGGER_CM
            directive.update({
                "paired_attack_window_id": binding.get("paired_attack_window_id"),
                "reaction_start_seconds": float(window["start_seconds"]),
                "contact_sync_error_seconds": float(binding.get("contact_sync_error_seconds", 0.0)),
                "reaction_motion": "knockback" if damage >= 0.08 else "stagger",
                "reaction_displacement_cm": displacement,
                "reaction_direction": "away_from_attacker",
                "canonical_hit": True,
                "canonical_damage": damage,
            })
        else:
            directive.update({
                "death_start_seconds": float(window["start_seconds"]),
                "terminal_pose_required": True,
                "corpse_root_lock": True,
                "aftermath_camera_hold_seconds": DEATH_AFTERMATH_HOLD_SECONDS,
                "canonical_death": True,
            })
        directives.append(directive)

    manifest = {
        "protocol": PROTOCOL,
        "generator_version": GENERATOR_VERSION,
        "authoritative": False,
        "canonical_state_mutation_allowed": False,
        "simulation_time_independent": True,
        "source_reaction_death_binding_digest": source["digest"],
        "source_animation_binding_digest": animation_proof["binding"]["digest"],
        "source_presentation_digest": combat_proof["presentation"]["digest"],
        "source_canonical_digest": combat_proof["source"]["canonical_digest"],
        "max_pair_alignment_cm": MAX_PAIR_ALIGNMENT_CM,
        "max_knockback_cm": MAX_KNOCKBACK_CM,
        "max_stagger_cm": MAX_STAGGER_CM,
        "camera_contact_hold_seconds": CAMERA_CONTACT_HOLD_SECONDS,
        "death_aftermath_hold_seconds": DEATH_AFTERMATH_HOLD_SECONDS,
        "directives": directives,
    }
    manifest["digest"] = _digest(manifest)
    validate_combat_motion_polish(manifest, reaction_death_proof, attack_measurements, reaction_measurements)
    return manifest


def validate_combat_motion_polish(
    manifest: dict[str, Any],
    reaction_death_proof: dict[str, Any],
    attack_measurements: dict[str, Any],
    reaction_measurements: dict[str, Any],
) -> bool:
    animation_proof = reaction_death_proof["animation_binding_proof"]
    source = reaction_death_proof["reaction_death_binding"]
    validate_reaction_death_binding(source, animation_proof, attack_measurements, reaction_measurements)
    combat_proof = animation_proof["combat_proof"]
    if manifest.get("protocol") != PROTOCOL or manifest.get("authoritative") is not False:
        raise ValueError("29D.4 protocol/authority invalid")
    if manifest.get("canonical_state_mutation_allowed") is not False or manifest.get("simulation_time_independent") is not True:
        raise ValueError("29D.4 authority boundary violated")
    expected = {
        "source_reaction_death_binding_digest": source["digest"],
        "source_animation_binding_digest": animation_proof["binding"]["digest"],
        "source_presentation_digest": combat_proof["presentation"]["digest"],
        "source_canonical_digest": combat_proof["source"]["canonical_digest"],
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(f"29D.4 source binding mismatch: {key}")
    source_by_binding = {b["binding_id"]: b for b in source["bindings"]}
    windows = {w["window_id"]: w for w in combat_proof["presentation"]["windows"]}
    expected_ids = {b["binding_id"] for b in source["bindings"] if b["presentation_kind"] in {"attack", "hit_reaction", "death"}}
    seen: set[str] = set()
    for directive in manifest.get("directives") or []:
        bid = directive.get("binding_id")
        if bid in seen or bid not in expected_ids:
            raise ValueError("29D.4 duplicate or unknown motion directive")
        seen.add(str(bid))
        binding = source_by_binding[str(bid)]
        window = windows[binding["window_id"]]
        for field in ("window_id", "actor_id", "target_id", "presentation_kind", "asset_name", "asset_path", "facing_yaw_degrees", "camera_shot"):
            if directive.get(field) != binding.get(field):
                raise ValueError(f"29D.4 changed accepted binding field: {field}")
        blend_in = float(directive["blend_in_seconds"])
        blend_out = float(directive["blend_out_seconds"])
        if not MIN_BLEND_SECONDS <= blend_in <= MAX_BLEND_SECONDS or not MIN_BLEND_SECONDS <= blend_out <= MAX_BLEND_SECONDS:
            raise ValueError("29D.4 transition blend outside safe bounds")
        kind = directive["presentation_kind"]
        if kind == "attack":
            if float(directive["contact_alignment_cm"]) > MAX_PAIR_ALIGNMENT_CM:
                raise ValueError("29D.4 attack alignment exceeds presentation bound")
            if float(directive["foot_slide_budget_cm"]) > 3.0:
                raise ValueError("29D.4 foot-slide budget exceeded")
            if bool(directive["canonical_hit"]) != bool(binding.get("canonical_hit", False)):
                raise ValueError("29D.4 changed canonical hit")
            if float(directive["canonical_damage"]) != float(binding.get("canonical_damage", 0.0)):
                raise ValueError("29D.4 changed canonical damage")
        elif kind == "hit_reaction":
            if float(directive["contact_sync_error_seconds"]) > 0.001:
                raise ValueError("29D.4 reaction lost contact synchronization")
            if float(directive["reaction_displacement_cm"]) > MAX_KNOCKBACK_CM:
                raise ValueError("29D.4 reaction displacement exceeds bound")
            if window.get("canonical_hit") is not True:
                raise ValueError("29D.4 invented reaction for non-hit")
        else:
            if directive.get("canonical_death") is not True or directive.get("terminal_pose_required") is not True or directive.get("corpse_root_lock") is not True:
                raise ValueError("29D.4 death/corpse persistence contract invalid")
    if seen != expected_ids:
        raise ValueError("29D.4 did not polish every combat animation binding")
    if manifest.get("digest") != rebuild_digest(manifest):
        raise ValueError("29D.4 digest mismatch")
    return True


def build_combat_motion_polish_proof(
    attack_measurements: dict[str, Any],
    reaction_measurements: dict[str, Any],
    seed: str = "underreach-29d4-combat-motion-polish-proof",
) -> dict[str, Any]:
    source = build_reaction_death_binding_proof(attack_measurements, reaction_measurements, seed)
    polish = build_combat_motion_polish(source, attack_measurements, reaction_measurements)
    return {"reaction_death_proof": source, "motion_polish": polish}
