"""Slice 28A terminal death-persistence wrapper.

Builds on the accepted attack-variety/contact/camera/transition source and makes
canonical death/defeat a terminal presentation state. Later animation cannot
visually resurrect the actor, and evaluated bones are checked near the end of
the sequence for corpse-pose persistence.
"""

from pathlib import Path

import unreal


BASE_WRAPPER = "build_vertical_slice_polish.py"


def _replace_once(source, old, new, description):
    if old not in source:
        raise RuntimeError(f"{description}; death-persistence wrapper needs updating")
    return source.replace(old, new, 1)


def _validated_source():
    wrapper_path = Path(__file__).with_name(BASE_WRAPPER)
    source = wrapper_path.read_text(encoding="utf-8")
    terminal = "\n\nmain()"
    if not source.rstrip().endswith("main()") or terminal not in source:
        raise RuntimeError("Transition-polish wrapper entrypoint changed")
    namespace = {"__file__": str(wrapper_path), "__name__": "__crawl_polish_library__"}
    exec(compile(source.rsplit(terminal, 1)[0], str(wrapper_path), "exec"), namespace, namespace)
    return namespace["_polished_source"]()


def _death_source():
    source_path, source = _validated_source()

    source = _replace_once(
        source,
        "from animation_transitions import blend_frames, orient_pose_for_travel\n",
        "from animation_transitions import blend_frames, orient_pose_for_travel\n"
        "from death_persistence import TERMINAL_ROLES, corpse_transform_pose, intent_allowed_after_terminal, terminal_start_seconds\n",
        "Transition import anchor changed",
    )
    source = _replace_once(source, 'SCRIPT_VERSION = "v10"', 'SCRIPT_VERSION = "v11"', "Expected v10 builder")

    source = _replace_once(
        source,
        '''        elif action in {"defeat", "death"} and target_id in pose_by_id:
            if target_id not in skeletal_actor_ids:
                target = pose_by_id[target_id]
                fallen = _copy_pose(target)
                fallen["z"] = 40.0
                fallen["pitch"] = 88.0
                key_actor(target_id, start, target)
                key_actor(target_id, end, fallen)
                pose_by_id[target_id] = fallen
''',
        '''        elif action in {"defeat", "death"} and target_id in pose_by_id:
            target = pose_by_id[target_id]
            if target_id in skeletal_actor_ids:
                # Manny death clips rotate the body but leave the skeletal root
                # near standing height. Ease the presentation root down and
                # back during the authored fall so the final pose rests at the
                # proof-floor height instead of hovering in a bent pose.
                fallen = corpse_transform_pose(target)
                linear = unreal.MovieSceneKeyInterpolation.LINEAR
                key_actor(target_id, start, target, linear)
                key_actor(target_id, end, fallen, linear)
                pose_by_id[target_id] = fallen
            else:
                fallen = _copy_pose(target)
                fallen["z"] = 40.0
                fallen["pitch"] = 88.0
                key_actor(target_id, start, target)
                key_actor(target_id, end, fallen)
                pose_by_id[target_id] = fallen
''',
        "Terminal skeletal transform anchor changed",
    )

    source = _replace_once(
        source,
        '''    combat_by_beat = {entry["attack_id"]: entry for entry in combat_debug}
    effective_priority_start_by_intent = {}
''',
        '''    combat_by_beat = {entry["attack_id"]: entry for entry in combat_debug}
    terminal_start_by_actor = {
        actor_id: terminal_start_seconds(actor_intents)
        for actor_id, actor_intents in intents_by_actor.items()
    }
    diagnostics["terminal_actor_ids"] = sorted(
        actor_id for actor_id, terminal_start in terminal_start_by_actor.items()
        if terminal_start is not None
    )
    effective_priority_start_by_intent = {}
''',
        "Terminal setup anchor changed",
    )

    source = _replace_once(
        source,
        '''        rig = rig_by_id.get(actor_id, {})
        active_ranges = []
''',
        '''        rig = rig_by_id.get(actor_id, {})
        active_ranges = []
        terminal_start = terminal_start_by_actor.get(actor_id)
        terminal_frame = (
            int(round(float(terminal_start) * FPS))
            if terminal_start is not None
            else None
        )
''',
        "Actor terminal state anchor changed",
    )

    source = _replace_once(
        source,
        '''        for intent in sorted(intents_by_actor.get(actor_id, []), key=lambda item: (item["start_seconds"], -item.get("priority", 0), item["id"])):
            slot = intent.get("asset_slot")
''',
        '''        for intent in sorted(intents_by_actor.get(actor_id, []), key=lambda item: (item["start_seconds"], -item.get("priority", 0), item["id"])):
            if not intent_allowed_after_terminal(intent, terminal_start):
                diagnostics.setdefault("suppressed_post_terminal_intents", []).append(intent["id"])
                continue
            slot = intent.get("asset_slot")
''',
        "Intent terminal guard anchor changed",
    )

    source = _replace_once(
        source,
        '''            start = int(round(intent_start * FPS))
            end = min(end_frame, int(round((intent_start + intent_duration) * FPS)))
            row = layer_rows.get(intent.get("layer"), 2)
''',
        '''            if intent.get("role") in TERMINAL_ROLES:
                # A canonical terminal event must be allowed to play its authored
                # fall completely. Later presentation clips are suppressed, so
                # once this section finishes Sequencer must retain the final pose.
                play_rate = 1.0
                source_death_duration = float(animation_asset.get_play_length())
                intent_duration = min(
                    source_death_duration,
                    max(0.1, end_frame / float(FPS) - intent_start),
                )
                diagnostics.setdefault("terminal_sections", []).append({
                    "actor_id": actor_id,
                    "role": intent.get("role"),
                    "asset_slot": slot,
                    "start_seconds": intent_start,
                    "source_duration_seconds": source_death_duration,
                    "section_duration_seconds": intent_duration,
                })
            start = int(round(intent_start * FPS))
            end = min(end_frame, int(round((intent_start + intent_duration) * FPS)))
            row = layer_rows.get(intent.get("layer"), 2)
''',
        "Terminal timing anchor changed",
    )

    source = _replace_once(
        source,
        '''            if cursor < end_frame:
                idle_ranges.append((cursor, end_frame))
''',
        '''            idle_end_frame = terminal_frame if terminal_frame is not None else end_frame
            if cursor < idle_end_frame:
                idle_ranges.append((cursor, idle_end_frame))
            # Never fill an idle gap at or after canonical death/defeat. Leaving
            # the skeletal track empty after the terminal clip preserves the
            # last evaluated corpse pose instead of visually resurrecting it.
            idle_ranges = [
                (idle_start, min(idle_end, idle_end_frame))
                for idle_start, idle_end in idle_ranges
                if idle_start < idle_end_frame
            ]
''',
        "Idle terminal clamp anchor changed",
    )

    capture_function = '''\n\ndef _capture_death_persistence(sequence, animation_plan, world_actors, slots, debug_path):
    terminal_intents = [
        intent for intent in animation_plan.get("intents", [])
        if intent.get("role") in TERMINAL_ROLES and intent.get("actor_id") in world_actors
    ]
    payload = {
        "protocol": "crawl.presentation-death-debug.v2",
        "authoritative": False,
        "position_tolerance_cm": 2.0,
        "orientation_tolerance_degrees": 1.0,
        "actor_transform_tolerance_cm": 0.1,
        "actor_transform_orientation_tolerance_degrees": 0.1,
        "terminal_count": len(terminal_intents),
        "actors": [],
    }
    if not terminal_intents:
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    unreal.EditorAssetLibrary.save_loaded_asset(sequence, False)
    unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
    sequence_end = int(sequence.get_playback_end())
    bones = ("pelvis", "spine_05", "head", "hand_r", "hand_l", "foot_r", "foot_l")

    def angular_delta_degrees(a, b):
        return abs((float(b) - float(a) + 180.0) % 360.0 - 180.0)

    for intent in terminal_intents:
        actor_id = intent["actor_id"]
        actor = world_actors[actor_id]
        component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
        asset_path = _slot_path(slots, intent.get("asset_slot"))
        animation_asset = unreal.load_asset(asset_path) if asset_path else None
        if component is None or animation_asset is None:
            raise RuntimeError(f"Cannot validate terminal pose for {actor_id}")
        start_frame = int(round(float(intent["start_seconds"]) * FPS))
        source_frames = max(1, int(round(float(animation_asset.get_play_length()) * FPS)))
        intent_frames = max(1, int(round(float(intent.get("duration_seconds", 0.0)) * FPS)))
        final_pose_frame = min(
            sequence_end - 2,
            max(start_frame + source_frames - 1, start_frame + intent_frames),
        )
        later_frames = sorted(set(
            min(sequence_end - 1, max(final_pose_frame + 1, frame))
            for frame in (
                final_pose_frame + int(round(0.25 * FPS)),
                final_pose_frame + int(round(1.0 * FPS)),
                final_pose_frame + int(round(2.0 * FPS)),
                sequence_end - 2,
            )
        ))

        def sample(frame):
            unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(int(frame))
            values = {"bones": {}}
            for bone in bones:
                p = component.get_socket_location(bone)
                r = component.get_socket_rotation(bone)
                values["bones"][bone] = {
                    "location": {"x": float(p.x), "y": float(p.y), "z": float(p.z)},
                    "rotation": {"roll": float(r.roll), "pitch": float(r.pitch), "yaw": float(r.yaw)},
                }
            actor_location = actor.get_actor_location()
            actor_rotation = actor.get_actor_rotation()
            values["actor_transform"] = {
                "location": {
                    "x": float(actor_location.x),
                    "y": float(actor_location.y),
                    "z": float(actor_location.z),
                },
                "rotation": {
                    "roll": float(actor_rotation.roll),
                    "pitch": float(actor_rotation.pitch),
                    "yaw": float(actor_rotation.yaw),
                },
            }
            return values

        final_pose = sample(final_pose_frame)
        samples = []
        maximum = 0.0
        maximum_rotation = 0.0
        maximum_transform_delta = 0.0
        maximum_transform_rotation = 0.0
        for later_frame in later_frames:
            later_pose = sample(later_frame)
            deltas = {}
            rotation_deltas = {}
            for bone in bones:
                a = final_pose["bones"][bone]
                b = later_pose["bones"][bone]
                dx = b["location"]["x"] - a["location"]["x"]
                dy = b["location"]["y"] - a["location"]["y"]
                dz = b["location"]["z"] - a["location"]["z"]
                delta = math.sqrt(dx * dx + dy * dy + dz * dz)
                rotation_delta = max(
                    angular_delta_degrees(a["rotation"][axis], b["rotation"][axis])
                    for axis in ("roll", "pitch", "yaw")
                )
                deltas[bone] = delta
                rotation_deltas[bone] = rotation_delta
                maximum = max(maximum, delta)
                maximum_rotation = max(maximum_rotation, rotation_delta)
            actor_a = final_pose["actor_transform"]
            actor_b = later_pose["actor_transform"]
            actor_dx = actor_b["location"]["x"] - actor_a["location"]["x"]
            actor_dy = actor_b["location"]["y"] - actor_a["location"]["y"]
            actor_dz = actor_b["location"]["z"] - actor_a["location"]["z"]
            actor_delta = math.sqrt(actor_dx * actor_dx + actor_dy * actor_dy + actor_dz * actor_dz)
            actor_rotation_delta = max(
                angular_delta_degrees(actor_a["rotation"][axis], actor_b["rotation"][axis])
                for axis in ("roll", "pitch", "yaw")
            )
            maximum_transform_delta = max(maximum_transform_delta, actor_delta)
            maximum_transform_rotation = max(maximum_transform_rotation, actor_rotation_delta)
            samples.append({
                "frame": later_frame,
                "seconds": later_frame / float(FPS),
                "seconds_after_settle": (later_frame - final_pose_frame) / float(FPS),
                "bone_deltas_cm": deltas,
                "bone_rotation_deltas_degrees": rotation_deltas,
                "maximum_bone_delta_cm": max(deltas.values()),
                "maximum_bone_rotation_delta_degrees": max(rotation_deltas.values()),
                "actor_transform_delta_cm": actor_delta,
                "actor_transform_rotation_delta_degrees": actor_rotation_delta,
            })
        terminal_start = float(intent["start_seconds"])
        fall_end = min(
            sequence_end / float(FPS),
            terminal_start + max(
                float(animation_asset.get_play_length()),
                float(intent.get("duration_seconds", 0.0)),
            ),
        )
        suppressed = [
            other["id"]
            for other in animation_plan.get("intents", [])
            if other.get("actor_id") == actor_id
            and not intent_allowed_after_terminal(other, terminal_start)
        ]
        persistent = (
            maximum <= 2.0
            and maximum_rotation <= 1.0
            and maximum_transform_delta <= 0.1
            and maximum_transform_rotation <= 0.1
        )
        entry = {
            "actor_id": actor_id,
            "role": intent.get("role"),
            "event_id": intent.get("event_id"),
            "asset_slot": intent.get("asset_slot"),
            "asset_path": asset_path,
            "death_start_seconds": terminal_start,
            "source_duration_seconds": float(animation_asset.get_play_length()),
            "fall_end_seconds": fall_end,
            "corpse_hold_start_seconds": fall_end,
            "sequence_end_seconds": sequence_end / float(FPS),
            "corpse_hold_duration_seconds": max(0.0, sequence_end / float(FPS) - fall_end),
            "final_pose_frame": final_pose_frame,
            "final_pose_seconds": final_pose_frame / float(FPS),
            "later_sample_frames": later_frames,
            "sampled_bones": list(bones),
            "settled_pose": final_pose,
            "samples": samples,
            "maximum_bone_delta_cm": maximum,
            "maximum_bone_rotation_delta_degrees": maximum_rotation,
            "maximum_actor_transform_delta_cm": maximum_transform_delta,
            "maximum_actor_transform_rotation_delta_degrees": maximum_transform_rotation,
            "transform_stable": maximum_transform_delta <= 0.1 and maximum_transform_rotation <= 0.1,
            "orientation_stable": maximum_rotation <= 1.0,
            "suppressed_post_terminal_intents": suppressed,
            "completion_mode": "keep_state",
            "hold_mechanism": "natural_speed_terminal_section_then_keep_state",
            "persistent": persistent,
        }
        payload["actors"].append(entry)
        if not persistent:
            raise RuntimeError(
                f"Terminal corpse pose did not persist for {actor_id}: "
                f"position={maximum:.3f}cm rotation={maximum_rotation:.3f}deg "
                f"transform={maximum_transform_delta:.3f}cm/{maximum_transform_rotation:.3f}deg"
            )

    debug_path.parent.mkdir(parents=True, exist_ok=True)
    debug_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
'''
    source = _replace_once(
        source,
        '\n\ndef _capture_evaluated_combat_contacts(sequence, world_actors, combat_debug):\n',
        capture_function + '\n\ndef _capture_evaluated_combat_contacts(sequence, world_actors, combat_debug):\n',
        "Death validation insertion anchor changed",
    )

    source = _replace_once(
        source,
        '''    _capture_evaluated_combat_contacts(sequence, world_actors, combat_debug)
    combat_debug_path = _project_dir() / "Generated" / "combat_debug.json"
''',
        '''    # Validate contact before corpse sampling. A terminal section using
    # KeepState intentionally leaves its final pose on the component after it
    # has been evaluated. Sampling the corpse first therefore contaminates a
    # later backwards scrub to an earlier combat frame in unattended Sequencer.
    _capture_evaluated_combat_contacts(sequence, world_actors, combat_debug)
    death_debug_path = _project_dir() / "Generated" / "death_debug.json"
    death_debug = _capture_death_persistence(
        sequence,
        animation_plan,
        world_actors,
        slots,
        death_debug_path,
    )
    diagnostics["terminal_validation_count"] = int(death_debug["terminal_count"])
    combat_debug_path = _project_dir() / "Generated" / "combat_debug.json"
''',
        "Death validation call anchor changed",
    )

    source = _replace_once(
        source,
        '''        "combat_debug": str(combat_debug_path),
        "camera_architecture": camera_debug["architecture"],
''',
        '''        "combat_debug": str(combat_debug_path),
        "death_debug": str(death_debug_path),
        "terminal_actor_count": int(death_debug["terminal_count"]),
        "camera_architecture": camera_debug["architecture"],
''',
        "Death result metadata anchor changed",
    )

    return source_path, source


def main():
    source_path, source = _death_source()
    unreal.log(f"[CrawlDeathPersistence] Running terminal corpse-persistence build: {source_path.name}")
    namespace = {"__file__": str(source_path), "__name__": "__crawl_death_persistence_build__"}
    exec(compile(source, str(source_path), "exec"), namespace, namespace)


main()
