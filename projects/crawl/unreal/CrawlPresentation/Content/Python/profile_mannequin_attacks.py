"""Measure Manny attack geometry with UE's deterministic AnimPose evaluator.

The profiler runs locally through UnrealEditor-Cmd and never changes canonical
Crawl state or Epic source assets. Earlier live-component/temporary-Sequencer
attempts produced held poses in unattended mode. AnimPose evaluates the same
animation data in component space at an exact source time, without depending on
an editor viewport, a selected actor, or a tick. Every activated profile is
still verified against the final Sequencer-evaluated rendered pose.
"""

import json
import math
from pathlib import Path

import unreal


SAMPLE_COUNT = 240
MESH_PATH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"
ATTACK_NAMES = ["MM_Attack_01", "MM_Attack_02", "MM_Attack_03", "MM_ChargedAttack"]
CONTACT_EFFECTORS = ("hand_r", "hand_l", "foot_r", "foot_l")
ATTACK_EFFECTORS = {
    "MM_Attack_01": ("hand_r", "hand_l"),
    "MM_Attack_02": ("hand_r", "hand_l"),
    # Visual inspection of the evaluated clip identifies Attack_03 as a high
    # kick. Measuring only its hands finds a later follow-through and delays
    # the reaction past the actual strike.
    "MM_Attack_03": ("foot_r", "foot_l"),
    "MM_ChargedAttack": ("hand_r", "hand_l"),
}
TORSO_BONE = "spine_05"
ROOT_BONE = "root"
ROOT_YAW_OFFSET_DEGREES = -90.0
MINIMUM_POSE_VARIATION = 8
MINIMUM_PLAUSIBLE_REACH_CM = 60.0


def _project_dir():
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def _asset_class_name(asset_data):
    value = asset_data.asset_class_path.asset_name if hasattr(asset_data, "asset_class_path") else asset_data.asset_class
    return str(value)


def _find_animation(name):
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    assets = registry.get_assets_by_path("/Game", recursive=True)
    matches = [
        asset for asset in assets
        if str(asset.asset_name) == name and _asset_class_name(asset) in {"AnimSequence", "AnimMontage"}
    ]
    if not matches:
        return None
    matches.sort(key=lambda asset: str(asset.package_name))
    return unreal.load_asset(f"{matches[0].package_name}.{matches[0].asset_name}")


def _translation(pose, bone):
    transform = unreal.AnimPoseExtensions.get_bone_pose(
        pose,
        bone,
        unreal.AnimPoseSpaces.WORLD,
    )
    return transform.translation


def _root_relative(vector, root):
    return {
        "forward_cm": float(vector.y - root.y),
        "lateral_cm": float(vector.x - root.x),
        "height_cm": float(vector.z - root.z),
    }


def _distance(a, b):
    return math.sqrt(
        (a["forward_cm"] - b["forward_cm"]) ** 2
        + (a["lateral_cm"] - b["lateral_cm"]) ** 2
        + (a["height_cm"] - b["height_cm"]) ** 2
    )


def _variation(samples, effector):
    values = [sample["effectors"][effector] for sample in samples]
    return {
        "unique_forward": len({round(item["forward_cm"], 4) for item in values}),
        "unique_lateral": len({round(item["lateral_cm"], 4) for item in values}),
        "unique_height": len({round(item["height_cm"], 4) for item in values}),
    }


def _candidate_for_effector(samples, effector):
    # Ignore the first/last tenth of the clip so an authored guard or recovery
    # pose cannot beat the actual strike simply by starting farther forward.
    eligible = [sample for sample in samples if 0.10 <= sample["phase"] <= 0.90]
    maximum_forward = max(
        item["effectors"][effector]["forward_cm"]
        for item in eligible
    )
    near_maximum = [
        item for item in eligible
        if item["effectors"][effector]["forward_cm"] >= maximum_forward * 0.90
    ]
    # A late low follow-through can be the mathematical maximum while missing a
    # tall target's torso. Select a centerline/chest-aligned sample from the
    # near-maximum extension neighborhood instead. This keeps a readable strike
    # silhouette and makes the candidate robust across Manny/Quinn scale.
    def contact_score(item):
        value = item["effectors"][effector]
        return (
            abs(value["lateral_cm"])
            + 2.0 * abs(value["height_cm"] - 130.0)
            + 0.15 * (maximum_forward - value["forward_cm"])
        )

    contact = min(near_maximum, key=contact_score)
    index = int(contact["index"])
    neighborhood = max(1, int(round(SAMPLE_COUNT * 0.05)))
    before = samples[max(0, index - neighborhood)]["effectors"][effector]
    after = samples[min(SAMPLE_COUNT, index + neighborhood)]["effectors"][effector]
    value = contact["effectors"][effector]
    return {
        "contact_effector": effector,
        "sample_index": index,
        "phase": float(contact["phase"]),
        "seconds": float(contact["seconds"]),
        "forward_reach_cm": float(value["forward_cm"]),
        "maximum_forward_reach_cm": float(maximum_forward),
        "near_maximum_reach_fraction": float(value["forward_cm"] / maximum_forward),
        "lateral_reach_cm": float(value["lateral_cm"]),
        "contact_height_cm": float(value["height_cm"]),
        "forward_gain_from_pre_contact_cm": float(value["forward_cm"] - before["forward_cm"]),
        "forward_recovery_after_contact_cm": float(value["forward_cm"] - after["forward_cm"]),
        "variation": _variation(samples, effector),
    }


def _profile(animation, mesh):
    duration = float(animation.get_play_length())
    if duration <= 0.0:
        raise RuntimeError(f"Animation has invalid duration: {animation.get_path_name()}")

    options = unreal.AnimPoseEvaluationOptions()
    options.set_editor_property("optional_skeletal_mesh", mesh)
    options.set_editor_property("extract_root_motion", False)
    options.set_editor_property("incorporate_root_motion_into_pose", True)

    samples = []
    for index in range(SAMPLE_COUNT + 1):
        phase = index / float(SAMPLE_COUNT)
        # Avoid endpoint wrap while retaining a normalized phase=1 diagnostic.
        seconds = min(duration - 1.0e-6, duration * phase)
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(
            animation,
            seconds,
            options,
        )
        if not unreal.AnimPoseExtensions.is_valid(pose):
            raise RuntimeError(
                f"AnimPose evaluation failed for {animation.get_name()} at {seconds:.6f}s"
            )
        root = _translation(pose, ROOT_BONE)
        torso = _root_relative(_translation(pose, TORSO_BONE), root)
        effectors = {
            effector: _root_relative(_translation(pose, effector), root)
            for effector in CONTACT_EFFECTORS
        }
        samples.append({
            "index": index,
            "phase": phase,
            "seconds": seconds,
            "root_translation_cm": {
                "x": float(root.x),
                "y": float(root.y),
                "z": float(root.z),
            },
            "torso": torso,
            "effectors": effectors,
        })

    candidates = [
        _candidate_for_effector(samples, effector)
        for effector in ATTACK_EFFECTORS[animation.get_name()]
    ]
    contact = max(candidates, key=lambda item: item["forward_reach_cm"])
    variation = contact["variation"]
    if max(variation.values()) <= MINIMUM_POSE_VARIATION:
        raise RuntimeError(
            f"AnimPose did not vary for {animation.get_name()}: "
            f"{variation['unique_forward']}/{variation['unique_lateral']}/{variation['unique_height']}"
        )
    if contact["forward_reach_cm"] < MINIMUM_PLAUSIBLE_REACH_CM:
        raise RuntimeError(
            f"No plausible forward strike found for {animation.get_name()}: "
            f"{contact['forward_reach_cm']:.2f}cm"
        )

    contact_sample = samples[contact["sample_index"]]
    torso = contact_sample["torso"]
    effector_value = contact_sample["effectors"][contact["contact_effector"]]
    result = {
        "asset_name": animation.get_name(),
        "asset_path": animation.get_path_name(),
        "source_duration_seconds": duration,
        "sample_count": len(samples),
        "contact_effector": contact["contact_effector"],
        "target_torso_bone": TORSO_BONE,
        "animation_forward_axis": "+Y",
        "root_yaw_offset_degrees": ROOT_YAW_OFFSET_DEGREES,
        "candidate_contact_phase": contact["phase"],
        "candidate_contact_seconds": contact["seconds"],
        "candidate_forward_reach_cm": contact["forward_reach_cm"],
        "candidate_lateral_reach_cm": contact["lateral_reach_cm"],
        "candidate_contact_height_cm": contact["contact_height_cm"],
        "candidate_torso_height_cm": torso["height_cm"],
        "candidate_effector_to_torso_cm": _distance(effector_value, torso),
        "candidate_sample_index": contact["sample_index"],
        "pose_variation": variation,
        "effector_candidates": candidates,
        "samples": samples,
        "validated": False,
        "activation_note": (
            "Measured candidate only. Final Sequencer-evaluated contact and visual render "
            "must pass before this asset enters the selection pool."
        ),
    }

    # MM_Attack_01 is the known control case from the already accepted rendered
    # contact pass. Refuse to trust any profiler run that cannot reproduce it.
    if animation.get_name() == "MM_Attack_01":
        if not (
            result["contact_effector"] == "hand_r"
            and 0.35 <= result["candidate_contact_phase"] <= 0.48
            and 80.0 <= result["candidate_forward_reach_cm"] <= 110.0
        ):
            raise RuntimeError(
                "MM_Attack_01 control measurement disagrees with accepted contact geometry: "
                f"{result['contact_effector']} phase={result['candidate_contact_phase']:.4f} "
                f"reach={result['candidate_forward_reach_cm']:.2f}cm"
            )
    return result


def main():
    mesh = unreal.load_asset(MESH_PATH)
    if mesh is None:
        raise RuntimeError(f"Manny mesh missing: {MESH_PATH}")

    profiles = []
    missing = []
    for name in ATTACK_NAMES:
        animation = _find_animation(name)
        if animation is None:
            missing.append(name)
            continue
        unreal.log(f"[CrawlAttackProfiler] AnimPose-sampling {animation.get_path_name()}")
        profiles.append(_profile(animation, mesh))

    output = _project_dir() / "Generated" / "attack_profiles_measured.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "protocol": "crawl.presentation-attack-profile-measurements.v3",
        "authoritative": False,
        "evaluation_mode": "anim_pose_component_space_root_locked",
        "sample_count_per_asset": SAMPLE_COUNT + 1,
        "profiles": profiles,
        "missing_assets": missing,
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    unreal.log(f"[CrawlAttackProfiler] Wrote {output}")
    if missing:
        unreal.log_warning(f"[CrawlAttackProfiler] Missing assets: {', '.join(missing)}")
    return output


main()
