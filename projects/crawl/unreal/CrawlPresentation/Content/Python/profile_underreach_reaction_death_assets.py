"""Discover and deterministically profile real Manny-compatible hit/death assets."""
import json
from pathlib import Path
import unreal

MESH_PATH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"
BONES = ("pelvis", "spine_03", "head")
SAMPLE_PHASES = (0.0, 0.2, 0.4, 0.6, 0.8, 0.999)
REACTION_KEYS = ("hit", "react", "hurt", "impact", "damage")
DEATH_KEYS = ("death", "die", "dying", "dead")
EXCLUDE_KEYS = ("attack", "run", "walk", "jump", "idle", "turn", "land", "falling")


def _project_dir():
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def _class_name(data):
    value = data.asset_class_path.asset_name if hasattr(data, "asset_class_path") else data.asset_class
    return str(value)


def _kind(name):
    low = name.lower()
    if any(k in low for k in EXCLUDE_KEYS):
        return None
    if any(k in low for k in DEATH_KEYS):
        return "death"
    if any(k in low for k in REACTION_KEYS):
        return "hit_reaction"
    return None


def _translation(pose, bone):
    transform = unreal.AnimPoseExtensions.get_bone_pose(pose, bone, unreal.AnimPoseSpaces.WORLD)
    v = transform.translation
    return (float(v.x), float(v.y), float(v.z))


def _variation(samples, bone):
    vals = [sample[bone] for sample in samples]
    return len({tuple(round(x, 4) for x in value) for value in vals})


def _profile(animation, mesh, kind):
    duration = float(animation.get_play_length())
    if duration <= 0.10:
        return None
    options = unreal.AnimPoseEvaluationOptions()
    options.set_editor_property("optional_skeletal_mesh", mesh)
    options.set_editor_property("extract_root_motion", False)
    options.set_editor_property("incorporate_root_motion_into_pose", True)
    samples = []
    for phase in SAMPLE_PHASES:
        seconds = min(duration - 1e-6, duration * phase)
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(animation, seconds, options)
        if not unreal.AnimPoseExtensions.is_valid(pose):
            return None
        samples.append({bone: _translation(pose, bone) for bone in BONES})
    variation = {
        "unique_pelvis": _variation(samples, "pelvis"),
        "unique_spine": _variation(samples, "spine_03"),
        "unique_head": _variation(samples, "head"),
    }
    if max(variation.values()) <= 4:
        return None
    start = samples[0]["pelvis"]
    end = samples[-1]["pelvis"]
    end_delta = ((end[0]-start[0])**2 + (end[1]-start[1])**2 + (end[2]-start[2])**2) ** 0.5
    return {
        "kind": kind,
        "asset_name": animation.get_name(),
        "asset_path": animation.get_path_name(),
        "source_duration_seconds": duration,
        "pose_variation": variation,
        "terminal_pelvis_delta_cm": float(end_delta),
        "sample_phases": list(SAMPLE_PHASES),
    }


def main():
    mesh = unreal.load_asset(MESH_PATH)
    if mesh is None:
        raise RuntimeError(f"Manny mesh missing: {MESH_PATH}")
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    candidates = []
    for data in registry.get_assets_by_path("/Game", recursive=True):
        if _class_name(data) not in {"AnimSequence", "AnimMontage"}:
            continue
        name = str(data.asset_name)
        kind = _kind(name)
        if kind:
            candidates.append((kind, str(data.package_name), name))
    candidates.sort()
    profiles = []
    rejected = []
    for kind, package, name in candidates:
        try:
            animation = unreal.load_asset(f"{package}.{name}")
            profile = _profile(animation, mesh, kind) if animation else None
            if profile:
                profiles.append(profile)
            else:
                rejected.append({"asset_name": name, "reason": "incompatible_or_frozen"})
        except Exception as exc:
            rejected.append({"asset_name": name, "reason": str(exc)[:240]})
    output = _project_dir() / "Generated" / "underreach-29d3" / "reaction-death-profiles.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "protocol": "underreach.reaction-death-profile-measurements.v1",
        "authoritative": False,
        "evaluation_mode": "anim_pose_component_space_root_locked",
        "profiles": profiles,
        "rejected_candidates": rejected,
        "candidate_count": len(candidates),
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    reaction_count = sum(p["kind"] == "hit_reaction" for p in profiles)
    death_count = sum(p["kind"] == "death" for p in profiles)
    unreal.log(f"[29D.3] profiled reactions={reaction_count} deaths={death_count}; {output}")
    if reaction_count < 1 or death_count < 1:
        unreal.log_error("[29D.3] At least one real compatible reaction and death asset are required")
    return output

main()
