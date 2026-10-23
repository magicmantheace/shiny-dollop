"""Fresh-process pose sampling for the saved 29A.1 render sequence."""

import json
import math
from pathlib import Path

import unreal


FPS = 60


def project_dir():
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def xyz(value):
    return {"x": float(value.x), "y": float(value.y), "z": float(value.z)}


def distance(left, right):
    return math.sqrt(sum((left[key] - right[key]) ** 2 for key in ("x", "y", "z")))


def relative(point, origin):
    return {key: point[key] - origin[key] for key in ("x", "y", "z")}


def main():
    generated = project_dir() / "Generated"
    result = json.loads((generated / "live_unreal_result.json").read_text(encoding="utf-8"))
    report = json.loads((generated / "29a1" / "character_29a1_validation_report.json").read_text(encoding="utf-8"))
    contact = next(item for item in report["contact_validation"] if item.get("procedural_species") == "human")
    level = result["level_asset"]
    sequence = unreal.load_asset(result["sequence_asset"])
    if sequence is None:
        raise RuntimeError("Saved 29A.1 sequence is missing")
    if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(level):
        raise RuntimeError("Saved 29A.1 render level is missing")
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence)
    actors = [
        item for item in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
        if item.get_actor_label() == f"Underreach_Human_{contact['actor_id']}"
    ]
    if not actors:
        raise RuntimeError("Saved 29A.1 Human actor is missing")
    duration = 1.5
    phase = 25.0 / 45.0
    start = float(contact["contact_seconds"]) - duration * phase
    times = [start, start + 0.35, float(contact["contact_seconds"]), start + 1.25]
    actor_records = []
    for actor in actors:
        component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
        samples = []
        for seconds in times:
            unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(int(round(seconds * FPS)))
            unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
            samples.append({
                "seconds": seconds,
                "hand_r": xyz(component.get_socket_location("hand_r")),
                "hand_l": xyz(component.get_socket_location("hand_l")),
                "spine_03": xyz(component.get_socket_location("spine_03")),
            })
        start_hand_relative = relative(samples[0]["hand_r"], samples[0]["spine_03"])
        maximum_hand_delta = max(
            distance(start_hand_relative, relative(item["hand_r"], item["spine_03"]))
            for item in samples[1:]
        )
        body_height = max(1.0, abs(samples[0]["spine_03"]["z"] - float(actor.get_actor_location().z)))
        actor_records.append({
            "actor_path": actor.get_path_name(),
            "samples": samples,
            "maximum_hand_delta_cm": maximum_hand_delta,
            "maximum_hand_delta_body_height_fraction": maximum_hand_delta / body_height,
            "measurement": "hand_r_relative_to_spine_03",
        })
    body_fraction = max(item["maximum_hand_delta_body_height_fraction"] for item in actor_records)
    body = {
        "protocol": "underreach.character-render-sequence-pose.v1",
        "level_asset": level,
        "sequence_asset": result["sequence_asset"],
        "actor_id": contact["actor_id"],
        "actors": actor_records,
        "matching_actor_count": len(actor_records),
        "maximum_hand_delta_body_height_fraction": body_fraction,
        "pose_varies": body_fraction >= 0.10,
    }
    output = generated / "29a1" / "render_sequence_pose_validation.json"
    output.write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
    if not body["pose_varies"]:
        raise RuntimeError(f"Saved 29A.1 attack pose is frozen: {body_fraction:.6f} body-heights")
    unreal.log(f"[Underreach29A1] SAVED RENDER SEQUENCE POSE PASS: {output}")


main()
