"""Validate imported 29A.1 semantic animations with UE's deterministic AnimPose API."""

import json
import math
from pathlib import Path

import unreal


SPECIES = ("Human", "Dwarf")
ROLES = ("Idle", "Walk", "Attack", "Reaction", "Death")
BONES = ("spine_03", "hand_r", "hand_l", "foot_r", "foot_l")


def project_dir():
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def bone_xyz(pose, bone):
    value = unreal.AnimPoseExtensions.get_bone_pose(pose, bone, unreal.AnimPoseSpaces.WORLD).translation
    return (float(value.x), float(value.y), float(value.z))


def distance(left, right):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))


def main():
    records = []
    for species in SPECIES:
        mesh = unreal.load_asset(f"/Game/Underreach29A1/Characters/SK_Underreach{species}")
        if mesh is None:
            raise RuntimeError(f"Missing 29A.1 mesh for {species}")
        options = unreal.AnimPoseEvaluationOptions()
        options.set_editor_property("optional_skeletal_mesh", mesh)
        options.set_editor_property("extract_root_motion", False)
        options.set_editor_property("incorporate_root_motion_into_pose", True)
        role_assets = [
            (role, f"/Game/Underreach29A1/Characters/A_Underreach{species}_{role}")
            for role in ROLES
        ]
        in_place = f"/Game/CrawlGenerated/PresentationAnimations/A_Underreach{species}_Attack_InPlace"
        if unreal.EditorAssetLibrary.does_asset_exist(in_place):
            role_assets.append(("AttackInPlace", in_place))
        for role, asset_path in role_assets:
            animation = unreal.load_asset(asset_path)
            if animation is None:
                raise RuntimeError(f"Missing 29A.1 {species} {role} animation")
            duration = float(animation.get_play_length())
            samples = []
            for phase in (0.0, 0.25, 0.5, 0.75, 0.999):
                pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(animation, duration * phase, options)
                if not unreal.AnimPoseExtensions.is_valid(pose):
                    raise RuntimeError(f"AnimPose evaluation failed: {animation.get_path_name()} at {phase}")
                samples.append({bone: bone_xyz(pose, bone) for bone in BONES})
            maximum_delta = max(
                distance(samples[0][bone], sample[bone])
                for sample in samples[1:]
                for bone in BONES
            )
            reference_height = max(1.0e-6, abs(samples[0]["spine_03"][2]))
            relative_delta = maximum_delta / reference_height
            minimum_relative_delta = 0.001 if role.lower() == "idle" else 0.02
            record = {
                "species": species.lower(),
                "role": role.lower(),
                "asset_path": animation.get_path_name(),
                "duration_seconds": duration,
                "maximum_sampled_bone_delta_units": maximum_delta,
                "reference_spine_height_units": reference_height,
                "maximum_delta_body_height_fraction": relative_delta,
                "minimum_required_body_height_fraction": minimum_relative_delta,
                "pose_varies": relative_delta >= minimum_relative_delta,
            }
            records.append(record)
    body = {"protocol": "underreach.character-animation-validation.v1", "records": records}
    output = project_dir() / "Generated" / "29a1" / "animation_pose_validation.json"
    output.write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
    frozen = [record for record in records if not record["pose_varies"]]
    if frozen:
        raise RuntimeError(
            "Frozen imported animations: "
            + ", ".join(f"{record['species']}/{record['role']}={record['maximum_delta_body_height_fraction']:.6f} body-heights" for record in frozen)
        )
    unreal.log(f"[Underreach29A1] ANIMATION POSE VALIDATION PASS: {output}")


main()
