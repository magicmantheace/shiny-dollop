"""Headless UE 5.8 real-animation consumer proof for Underreach Slice 29D.2.

This proof loads the actual Manny skeletal mesh and every measured attack asset,
evaluates source poses deterministically with AnimPose, checks contact geometry and
pose variation, and verifies the 29D.2 binding artifact remains unchanged. It does
not run simulation or claim unvalidated reaction/death clips.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import unreal

PROJECT_DIR = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
OUTPUT_DIR = PROJECT_DIR / "Generated" / "underreach-29d2"
PROOF_PATH = OUTPUT_DIR / "animation-binding-proof.json"
DEBUG_PATH = OUTPUT_DIR / "animation-binding-unreal-debug.json"
MESH_PATH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"
ROOT_BONE = "root"
DEFAULT_TORSO_BONE = "spine_05"
REACH_TOLERANCE_CM = 1.0
MIN_SAMPLE_VARIATION_CM = 0.05


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _translation(pose, bone):
    return unreal.AnimPoseExtensions.get_bone_pose(pose, bone, unreal.AnimPoseSpaces.WORLD).translation


def _evaluate(animation, mesh, seconds):
    options = unreal.AnimPoseEvaluationOptions()
    options.set_editor_property("optional_skeletal_mesh", mesh)
    options.set_editor_property("extract_root_motion", False)
    options.set_editor_property("incorporate_root_motion_into_pose", True)
    pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(animation, float(seconds), options)
    if not unreal.AnimPoseExtensions.is_valid(pose):
        raise RuntimeError(f"29D.2 invalid AnimPose for {animation.get_name()} at {seconds:.6f}s")
    return pose


def _root_relative_forward(pose, effector):
    root = _translation(pose, ROOT_BONE)
    point = _translation(pose, effector)
    return float(point.y - root.y)


def _root_relative_xyz(pose, effector):
    root = _translation(pose, ROOT_BONE)
    point = _translation(pose, effector)
    return (float(point.x - root.x), float(point.y - root.y), float(point.z - root.z))


def _distance(a, b):
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not PROOF_PATH.exists():
        raise RuntimeError(f"29D.2 proof missing: {PROOF_PATH}")

    hash_before = _sha(PROOF_PATH)
    proof = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    combat = proof["combat_proof"]
    binding = proof["binding"]
    if binding.get("protocol") != "underreach.animation-binding.v1" or binding.get("authoritative") is not False:
        raise RuntimeError("29D.2 binding contract invalid")
    if binding.get("source_presentation_digest") != combat["presentation"].get("digest"):
        raise RuntimeError("29D.2 source presentation binding mismatch")
    if binding.get("source_canonical_digest") != combat["source"].get("canonical_digest"):
        raise RuntimeError("29D.2 canonical binding mismatch")

    mesh = unreal.load_asset(MESH_PATH)
    if mesh is None:
        raise RuntimeError(f"29D.2 Manny mesh missing: {MESH_PATH}")

    attacks = [item for item in binding["bindings"] if item["presentation_kind"] == "attack"]
    fallbacks = [item for item in binding["bindings"] if item["binding_status"] == "semantic_fallback"]
    asset_results = {}
    missing_assets = []
    invalid_poses = []
    frozen_assets = []
    max_reach_delta = 0.0
    max_alignment = 0.0
    max_facing_delta = 0.0
    evaluated_contacts = 0

    windows = {item["window_id"]: item for item in combat["presentation"]["windows"]}
    for item in attacks:
        path = item["asset_path"]
        animation = unreal.load_asset(path)
        if animation is None:
            missing_assets.append(path)
            continue
        duration = float(animation.get_play_length())
        if duration <= 0.0:
            invalid_poses.append(path)
            continue
        contact_seconds = min(max(0.0, float(item["contact_seconds_source"])), max(0.0, duration - 1.0e-6))
        try:
            contact_pose = _evaluate(animation, mesh, contact_seconds)
            measured_reach = _root_relative_forward(contact_pose, item["contact_effector"])
            expected_reach = float(item["profile_forward_reach_cm"])
            reach_delta = abs(measured_reach - expected_reach)
            max_reach_delta = max(max_reach_delta, reach_delta)
            evaluated_contacts += 1

            sample_points = []
            for phase in (0.15, float(item["contact_phase"]), 0.85):
                seconds = min(duration - 1.0e-6, max(0.0, duration * phase))
                pose = _evaluate(animation, mesh, seconds)
                sample_points.append(_root_relative_xyz(pose, item["contact_effector"]))
            variation = max(_distance(sample_points[a], sample_points[b]) for a in range(3) for b in range(a + 1, 3))
            if variation <= MIN_SAMPLE_VARIATION_CM:
                frozen_assets.append(path)

            asset_results[path] = {
                "asset_name": item["asset_name"],
                "duration_seconds": duration,
                "contact_effector": item["contact_effector"],
                "contact_seconds": contact_seconds,
                "profile_reach_cm": expected_reach,
                "evaluated_reach_cm": measured_reach,
                "reach_delta_cm": reach_delta,
                "sample_variation_cm": variation,
            }
        except Exception as exc:
            invalid_poses.append(f"{path}: {exc}")

        max_alignment = max(max_alignment, float(item["bounded_alignment_request_cm"]))
        source_window = windows[item["window_id"]]
        expected_yaw = source_window.get("facing_yaw_degrees")
        bound_yaw = item.get("facing_yaw_degrees")
        if expected_yaw is not None and bound_yaw is not None:
            max_facing_delta = max(max_facing_delta, abs(float(expected_yaw) - float(bound_yaw)))

    hash_after = _sha(PROOF_PATH)
    unique_paths = {item["asset_path"] for item in attacks}
    required_names = set(binding.get("real_attack_assets_required") or [])
    bound_names = {item["asset_name"] for item in attacks}
    combat_shots_preserved = all(item.get("camera_shot") == windows[item["window_id"]].get("camera_shot") for item in binding["bindings"])
    fallbacks_truthful = all(item.get("asset_path") is None and item.get("asset_name") is None for item in fallbacks)

    validation = {
        "proof_file_unchanged": hash_before == hash_after,
        "binding_non_authoritative": binding.get("authoritative") is False,
        "canonical_mutation_forbidden": binding.get("canonical_state_mutation_allowed") is False,
        "real_attack_assets_complete": bool(attacks) and required_names <= bound_names,
        "all_bound_assets_loaded": not missing_assets and len(asset_results) == len(unique_paths),
        "all_contact_poses_valid": not invalid_poses and evaluated_contacts == len(attacks),
        "contact_geometry_matches_profile": max_reach_delta <= REACH_TOLERANCE_CM,
        "no_frozen_attack_assets": not frozen_assets,
        "alignment_requests_bounded": max_alignment <= float(binding["max_presentation_alignment_cm"]),
        "facing_preserved": max_facing_delta <= 0.001,
        "feed_camera_intent_preserved": combat_shots_preserved,
        "reaction_death_fallbacks_truthful": fallbacks_truthful,
    }
    validation["all_pass"] = all(validation.values())

    debug = {
        "protocol": "underreach.animation-binding-unreal-debug.v1",
        "authoritative": False,
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "mesh_path": MESH_PATH,
        "source_canonical_digest": binding["source_canonical_digest"],
        "source_presentation_digest": binding["source_presentation_digest"],
        "binding_digest": binding["digest"],
        "proof_file_sha256_before": hash_before,
        "proof_file_sha256_after": hash_after,
        "attack_window_count": len(attacks),
        "unique_attack_asset_count": len(unique_paths),
        "evaluated_contact_count": evaluated_contacts,
        "semantic_fallback_count": len(fallbacks),
        "missing_assets": sorted(set(missing_assets)),
        "invalid_poses": invalid_poses,
        "frozen_assets": sorted(set(frozen_assets)),
        "max_profile_reach_delta_cm": max_reach_delta,
        "max_alignment_request_cm": max_alignment,
        "max_facing_delta_degrees": max_facing_delta,
        "asset_results": [asset_results[key] for key in sorted(asset_results)],
        "validation": validation,
    }
    DEBUG_PATH.write_text(json.dumps(debug, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not validation["all_pass"]:
        raise RuntimeError(f"29D.2 Unreal animation binding validation failed: {validation}")
    unreal.log(
        f"[Underreach29D2] PASS attacks={len(attacks)} assets={len(unique_paths)} "
        f"contacts={evaluated_contacts} maxReachDelta={max_reach_delta:.6f}cm"
    )
    unreal.log(f"[Underreach29D2] Output={DEBUG_PATH}")


main()
