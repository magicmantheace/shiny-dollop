"""Compatibility entrypoint for the integrated Slice 28A presentation build.

The canonical ledger remains untouched. This wrapper substitutes the accepted
time-aware camera and deterministic, asset-profiled combat presentation pass.
"""

from pathlib import Path

import unreal


SOURCE_NAME = "build_vertical_slice.py"


def _replace_once(source, old, new, description):
    if old not in source:
        raise RuntimeError(f"{description}; integrated builder needs updating")
    return source.replace(old, new, 1)


def _patched_source():
    source_path = Path(__file__).with_name(SOURCE_NAME)
    source = source_path.read_text(encoding="utf-8")

    source = _replace_once(
        source,
        "from camera_planning import HORIZONTAL_FOV_DEGREES, plan_master_camera\n",
        "from camera_planning import HORIZONTAL_FOV_DEGREES\n"
        "from camera_focus import plan_master_camera\n"
        "from combat_staging import stage_attack_exchange\n",
        "Integrated camera import anchor changed",
    )
    source = _replace_once(
        source,
        'SCRIPT_VERSION = "v6"',
        'SCRIPT_VERSION = "v9"',
        "Expected v6 integrated builder",
    )

    source = _replace_once(
        source,
        '''def _animate_actors(sequence, actor_payloads, world_actors, beats, skeletal_actor_ids):
''',
        '''def _animate_actors(sequence, actor_payloads, world_actors, beats, animation_plan, skeletal_actor_ids):
''',
        "Expected actor animation signature was not found",
    )
    source = _replace_once(
        source,
        '''    combat_debug = []

    def key_actor(actor_id, frame, pose, interpolation=None):
''',
        '''    combat_debug = []
    attack_slot_by_beat = {
        intent["beat_id"]: intent["asset_slot"]
        for intent in animation_plan.get("intents", [])
        if intent.get("role") == "attack" and intent.get("asset_slot")
    }

    def key_actor(actor_id, frame, pose, interpolation=None):
''',
        "Expected combat diagnostics setup was not found",
    )

    old_attack = '''        if action == "attack_hit" and performer_id in pose_by_id and target_id in pose_by_id:
            performer = pose_by_id[performer_id]
            target = pose_by_id[target_id]
            px, py = _distance_direction(performer, target)
            lunge = _copy_pose(performer)
            lunge["x"] = target["x"] - px * 105.0
            lunge["y"] = target["y"] - py * 105.0
            lunge["yaw"] = _face(lunge, target)
            key_actor(performer_id, start, performer)
            key_actor(performer_id, mid, lunge)
            key_actor(performer_id, end, performer)

            knock = _copy_pose(target)
            knock["x"] += px * 48.0
            knock["y"] += py * 48.0
            if target_id not in skeletal_actor_ids:
                knock["pitch"] = -8.0
            key_actor(target_id, start, target)
            key_actor(target_id, mid, knock)
            knock["pitch"] = 0.0
            key_actor(target_id, end, knock)
            pose_by_id[target_id] = knock
'''
    new_attack = '''        if action == "attack_hit" and performer_id in pose_by_id and target_id in pose_by_id:
            performer = pose_by_id[performer_id]
            target = pose_by_id[target_id]
            attack_slot = attack_slot_by_beat.get(
                beat["id"],
                "humanoid.combat.attack.default",
            )
            exchange = stage_attack_exchange(
                performer,
                target,
                float(beat["start_seconds"]),
                float(beat["duration_seconds"]),
                asset_slot=attack_slot,
                attacker_scale=scale_by_id[performer_id][0],
                target_scale=scale_by_id[target_id][0],
                attacker_available_seconds=pose_tracks[performer_id][-1]["seconds"],
                target_available_seconds=pose_tracks[target_id][-1]["seconds"],
            )

            approach = int(round(exchange["approach_start_seconds"] * FPS))
            target_prepare = int(round(exchange["target_approach_start_seconds"] * FPS))
            ready = start
            target_ready = start
            impact = max(start + 1, int(round(exchange["visual_contact_seconds"] * FPS)))
            recover = max(impact + 1, end)
            linear = unreal.MovieSceneKeyInterpolation.LINEAR

            if approach < ready:
                key_actor(performer_id, approach, performer, linear)
            key_actor(performer_id, ready, exchange["attacker_ready"], linear)
            key_actor(performer_id, impact, exchange["attacker_contact"], linear)
            key_actor(performer_id, recover, exchange["attacker_recover"], linear)

            if target_prepare < target_ready:
                key_actor(target_id, target_prepare, target, linear)
            key_actor(target_id, target_ready, exchange["target_ready"], linear)
            # Do not animate the target away during windup. Contact lands on the
            # held torso; presentation-only knockback begins after that frame.
            key_actor(target_id, impact, exchange["target_contact"], linear)
            key_actor(target_id, recover, exchange["target_recover"], linear)

            pose_by_id[performer_id] = exchange["attacker_recover"]
            pose_by_id[target_id] = exchange["target_recover"]
            exchange["attack_id"] = beat["id"]
            exchange["event_id"] = beat.get("event_id")
            exchange["performer_id"] = performer_id
            exchange["target_id"] = target_id
            exchange["attacker_start_position"] = exchange["attacker_initial"]
            exchange["attacker_ready_position"] = exchange["attacker_ready"]
            exchange["attacker_contact_position"] = exchange["attacker_contact"]
            exchange["target_contact_position"] = exchange["target_contact"]
            exchange["engagement_distance"] = exchange["ready_distance"]
            combat_debug.append(exchange)
'''
    source = _replace_once(
        source,
        old_attack,
        new_attack,
        "Expected attack staging block was not found",
    )

    source = _replace_once(
        source,
        '''def _apply_skeletal_animations(sequence, animation_plan, bindings_by_id, skeletal_actor_ids, slots, diagnostics):
''',
        '''def _apply_skeletal_animations(sequence, animation_plan, combat_debug, bindings_by_id, skeletal_actor_ids, slots, diagnostics):
''',
        "Expected skeletal animation signature was not found",
    )
    source = _replace_once(
        source,
        '''    intents_by_actor = {}
    for intent in animation_plan.get("intents", []):
        intents_by_actor.setdefault(intent["actor_id"], []).append(intent)

    end_frame = int(sequence.get_playback_end())
''',
        '''    intents_by_actor = {}
    for intent in animation_plan.get("intents", []):
        intents_by_actor.setdefault(intent["actor_id"], []).append(intent)
    combat_by_beat = {entry["attack_id"]: entry for entry in combat_debug}
    effective_priority_start_by_intent = {}
    for actor_intents in intents_by_actor.values():
        for planned_intent in actor_intents:
            effective_start = float(planned_intent["start_seconds"])
            planned_exchange = combat_by_beat.get(planned_intent.get("beat_id"))
            if (
                planned_intent.get("role") == "hit_reaction"
                and planned_intent.get("contact_policy") == "react_at_contact"
                and planned_exchange is not None
            ):
                effective_start = float(planned_exchange["reaction_start_seconds"])
            effective_priority_start_by_intent[planned_intent["id"]] = effective_start

    end_frame = int(sequence.get_playback_end())
''',
        "Expected skeletal intent setup block was not found",
    )

    intent_loop_anchor = '''        for intent in sorted(intents_by_actor.get(actor_id, []), key=lambda item: (item["start_seconds"], -item.get("priority", 0), item["id"])):
'''
    approach_loop = '''        # Match approach cadence to the authored 300 cm/s walk cycle. Both
        # participants may close distance when adjacent canonical events leave
        # too little time for one actor to cross the arena without teleporting.
        locomotion_slot = rig.get("locomotion_slot")
        if locomotion_slot:
            locomotion_asset = _load_slot_asset(slots, locomotion_slot, diagnostics)
            if locomotion_asset is not None:
                for exchange in combat_debug:
                    if exchange["performer_id"] == actor_id:
                        prefix = ""
                    elif exchange["target_id"] == actor_id:
                        prefix = "target_"
                    else:
                        continue
                    approach_start = int(round(float(exchange[f"{prefix}approach_start_seconds"]) * FPS))
                    approach_end = int(round(float(exchange["attack_start_seconds"]) * FPS))
                    approach_distance = float(exchange[f"{prefix}approach_distance"])
                    play_rate = float(exchange[f"{prefix}locomotion_play_rate"])
                    if approach_end > approach_start and approach_distance > 1.0:
                        try:
                            _add_animation_section(
                                track,
                                locomotion_asset,
                                approach_start,
                                approach_end,
                                1,
                                play_rate,
                            )
                            section_count += 1
                            active_ranges.append((approach_start, approach_end))
                            exchange[f"{prefix}locomotion_asset"] = locomotion_asset.get_path_name()
                        except Exception as exc:
                            diagnostics["animation_errors"].append(
                                f"{actor_id}:{locomotion_slot}:{prefix}combat_approach:{exc}"
                            )

        for intent in sorted(intents_by_actor.get(actor_id, []), key=lambda item: (item["start_seconds"], -item.get("priority", 0), item["id"])):
'''
    source = _replace_once(
        source,
        intent_loop_anchor,
        approach_loop,
        "Expected skeletal intent loop was not found",
    )

    source = _replace_once(
        source,
        '''            start = int(round(float(intent["start_seconds"]) * FPS))
            end = int(round((float(intent["start_seconds"]) + float(intent["duration_seconds"])) * FPS))
            row = layer_rows.get(intent.get("layer"), 2)
''',
        '''            intent_start = float(intent["start_seconds"])
            intent_duration = float(intent["duration_seconds"])
            play_rate = 1.0
            exchange = combat_by_beat.get(intent.get("beat_id"))
            if intent.get("role") == "attack" and exchange is not None:
                profile_asset_path = exchange["attack_profile"].get("asset_path")
                source_animation_asset = unreal.load_asset(profile_asset_path)
                if source_animation_asset is None:
                    raise RuntimeError(f"Profiled attack asset missing: {profile_asset_path}")
                animation_asset = source_animation_asset
                if exchange["attack_profile"].get("force_root_lock"):
                    animation_asset = _prepare_in_place_animation_asset(animation_asset)
                source_duration = float(source_animation_asset.get_play_length())
                play_rate = float(exchange["attack_animation_play_rate"])
                full_attack_duration = source_duration / play_rate
                future_attack_starts = [
                    effective_priority_start_by_intent[other["id"]]
                    for other in intents_by_actor.get(actor_id, [])
                    if other["id"] != intent["id"]
                    and effective_priority_start_by_intent[other["id"]] > intent_start
                    and int(other.get("priority", 0)) >= 80
                ]
                available_attack_duration = (
                    min(future_attack_starts) - intent_start
                    if future_attack_starts
                    else full_attack_duration
                )
                intent_duration = max(
                    float(exchange["visual_contact_seconds"]) - intent_start + 0.10,
                    min(full_attack_duration, available_attack_duration),
                )
                exchange["attack_asset"] = source_animation_asset.get_path_name()
                exchange["prepared_attack_asset"] = animation_asset.get_path_name()
                exchange["attack_asset_duration_seconds"] = source_duration
                exchange["attack_animation_play_rate"] = play_rate
                exchange["attack_section_duration_seconds"] = intent_duration
            if intent.get("role") == "hit_reaction" and intent.get("contact_policy") == "react_at_contact":
                if exchange is not None:
                    intent_start = float(exchange["reaction_start_seconds"])
                    reaction_severity = exchange["attack_profile"].get(
                        "reaction_severity",
                        "light",
                    )
                    desired_play_rate = {
                        "light": 1.15,
                        "medium": 1.0,
                        "heavy": 0.9,
                    }.get(reaction_severity, 1.0)
                    source_reaction_duration = float(animation_asset.get_play_length())
                    desired_duration = source_reaction_duration / desired_play_rate
                    future_action_starts = [
                        effective_priority_start_by_intent[other["id"]]
                        for other in intents_by_actor.get(actor_id, [])
                        if other["id"] != intent["id"]
                        and effective_priority_start_by_intent[other["id"]] > intent_start
                        and int(other.get("priority", 0)) >= 80
                    ]
                    available_duration = (
                        min(future_action_starts) - intent_start
                        if future_action_starts
                        else desired_duration
                    )
                    intent_duration = max(
                        0.1,
                        min(desired_duration, available_duration),
                    )
                    # Preserve the authored severity cadence. If another
                    # canonical presentation action starts soon, truncate this
                    # reaction at that boundary rather than time-compressing a
                    # heavy recoil into an unreadable twitch.
                    play_rate = desired_play_rate
                    exchange["reaction_asset"] = animation_asset.get_path_name()
                    exchange["reaction_animation_play_rate"] = play_rate
                    exchange["reaction_severity"] = reaction_severity
                    exchange["reaction_duration_seconds"] = intent_duration
            start = int(round(intent_start * FPS))
            end = min(end_frame, int(round((intent_start + intent_duration) * FPS)))
            row = layer_rows.get(intent.get("layer"), 2)
''',
        "Expected animation timing block was not found",
    )
    source = _replace_once(
        source,
        '''            try:
                _add_animation_section(track, animation_asset, start, end, row)
''',
        '''            try:
                _add_animation_section(track, animation_asset, start, end, row, play_rate)
''',
        "Expected animation section creation call was not found",
    )

    source = _replace_once(
        source,
        '''    actor_tracks, bindings_by_id, combat_debug = _animate_actors(
        sequence,
        manifest["actors"],
        world_actors,
        manifest["beats"],
        diagnostics["skeletal_actor_ids"],
    )
''',
        '''    actor_tracks, bindings_by_id, combat_debug = _animate_actors(
        sequence,
        manifest["actors"],
        world_actors,
        manifest["beats"],
        animation_plan,
        diagnostics["skeletal_actor_ids"],
    )
''',
        "Expected actor animation call was not found",
    )
    source = _replace_once(
        source,
        '''    _apply_skeletal_animations(
        sequence,
        animation_plan,
        bindings_by_id,
''',
        '''    _apply_skeletal_animations(
        sequence,
        animation_plan,
        combat_debug,
        bindings_by_id,
''',
        "Expected skeletal animation call was not found",
    )

    return source_path, source


def main():
    source_path, source = _patched_source()
    unreal.log(
        f"[CrawlCameraSafe] Running accepted camera + profiled combat contact staging: {source_path.name}"
    )
    namespace = {
        "__file__": str(source_path),
        "__name__": "__crawl_camera_safe_build__",
    }
    exec(compile(source, str(source_path), "exec"), namespace, namespace)


main()
