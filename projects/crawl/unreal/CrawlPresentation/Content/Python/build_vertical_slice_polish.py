"""Slice 28A transition-polish wrapper over the validated camera/contact build.

This keeps the accepted camera and profiled contact solver intact, then adds
presentation-only locomotion facing and short Sequencer crossfades. Canonical
Crawl events/outcomes remain untouched.
"""

from pathlib import Path

import unreal


BASE_WRAPPER = "build_vertical_slice_camera_safe.py"


def _replace_once(source, old, new, description):
    if old not in source:
        raise RuntimeError(f"{description}; transition-polish wrapper needs updating")
    return source.replace(old, new, 1)


def _validated_source():
    wrapper_path = Path(__file__).with_name(BASE_WRAPPER)
    wrapper_source = wrapper_path.read_text(encoding="utf-8")
    terminal = "\n\nmain()"
    if not wrapper_source.rstrip().endswith("main()") or terminal not in wrapper_source:
        raise RuntimeError("Validated camera/contact wrapper entrypoint changed")
    library_source = wrapper_source.rsplit(terminal, 1)[0]
    namespace = {
        "__file__": str(wrapper_path),
        "__name__": "__crawl_validated_wrapper_library__",
    }
    exec(compile(library_source, str(wrapper_path), "exec"), namespace, namespace)
    source_path, source = namespace["_patched_source"]()
    return source_path, source


def _polished_source():
    source_path, source = _validated_source()

    source = _replace_once(
        source,
        "from combat_staging import stage_attack_exchange\n",
        "from combat_staging import stage_attack_exchange\n"
        "from animation_transitions import blend_frames, orient_pose_for_travel\n",
        "Validated combat import anchor changed",
    )
    source = _replace_once(
        source,
        'SCRIPT_VERSION = "v9"',
        'SCRIPT_VERSION = "v10"',
        "Expected validated v9 builder",
    )

    old_retreat = '''        elif action == "retreat" and performer_id in pose_by_id:
            performer = pose_by_id[performer_id]
            length = max(1.0, math.sqrt(performer["x"] ** 2 + performer["y"] ** 2))
            retreat = _copy_pose(performer)
            retreat["x"] = performer["x"] / length * 560.0
            retreat["y"] = performer["y"] / length * 560.0
            key_actor(performer_id, start, performer)
            key_actor(performer_id, end, retreat)
            pose_by_id[performer_id] = retreat
'''
    new_retreat = '''        elif action == "retreat" and performer_id in pose_by_id:
            performer = pose_by_id[performer_id]
            length = max(1.0, math.sqrt(performer["x"] ** 2 + performer["y"] ** 2))
            retreat = _copy_pose(performer)
            retreat["x"] = performer["x"] / length * 560.0
            retreat["y"] = performer["y"] / length * 560.0
            retreat = orient_pose_for_travel(performer, retreat)
            travel_start = _copy_pose(performer)
            travel_start["yaw"] = retreat["yaw"]
            key_actor(performer_id, start, travel_start)
            key_actor(performer_id, end, retreat)
            pose_by_id[performer_id] = retreat
'''
    source = _replace_once(source, old_retreat, new_retreat, "Retreat staging block changed")

    old_move = '''        elif action == "move" and performer_id in pose_by_id:
            performer = pose_by_id[performer_id]
            moved = _copy_pose(performer)
            angle = math.radians(performer.get("yaw", 0.0))
            moved["x"] += math.cos(angle) * 140.0
            moved["y"] += math.sin(angle) * 140.0
            key_actor(performer_id, start, performer)
            key_actor(performer_id, end, moved)
            pose_by_id[performer_id] = moved
'''
    new_move = '''        elif action == "move" and performer_id in pose_by_id:
            performer = pose_by_id[performer_id]
            moved = _copy_pose(performer)
            # Preserve the existing canonical/presentation travel choice, but make
            # the mannequin's authored +Y locomotion face that actual vector.
            angle = math.radians(performer.get("yaw", 0.0))
            moved["x"] += math.cos(angle) * 140.0
            moved["y"] += math.sin(angle) * 140.0
            moved = orient_pose_for_travel(performer, moved)
            travel_start = _copy_pose(performer)
            travel_start["yaw"] = moved["yaw"]
            key_actor(performer_id, start, travel_start)
            key_actor(performer_id, end, moved)
            pose_by_id[performer_id] = moved
'''
    source = _replace_once(source, old_move, new_move, "Move staging block changed")

    old_section = '''def _add_animation_section(track, animation_asset, start_frame, end_frame, row_index, play_rate=1.0):
    section = track.add_section()
    section.set_range(start_frame, max(start_frame + 1, end_frame))
    if hasattr(section, "set_row_index"):
        section.set_row_index(row_index)
    else:
        try:
            section.set_editor_property("row_index", row_index)
        except Exception:
            pass
    _set_animation_on_section(section, animation_asset, play_rate)
    return section
'''
    new_section = '''def _add_animation_section(
    track,
    animation_asset,
    start_frame,
    end_frame,
    row_index,
    play_rate=1.0,
    blend_in_seconds=0.0,
    blend_out_seconds=0.0,
):
    section = track.add_section()
    resolved_end = max(start_frame + 1, end_frame)
    section.set_range(start_frame, resolved_end)
    if hasattr(section, "set_row_index"):
        section.set_row_index(row_index)
    else:
        try:
            section.set_editor_property("row_index", row_index)
        except Exception:
            pass
    _set_animation_on_section(section, animation_asset, play_rate)
    duration_seconds = (resolved_end - start_frame) / float(FPS)
    ease_in_frames = blend_frames(FPS, blend_in_seconds, duration_seconds) if blend_in_seconds else 0
    ease_out_frames = blend_frames(FPS, blend_out_seconds, duration_seconds) if blend_out_seconds else 0
    try:
        if ease_in_frames and hasattr(section, "set_ease_in_duration"):
            section.set_ease_in_duration(unreal.FrameNumber(ease_in_frames))
        if ease_out_frames and hasattr(section, "set_ease_out_duration"):
            section.set_ease_out_duration(unreal.FrameNumber(ease_out_frames))
    except Exception as exc:
        _warn(f"Could not apply animation easing to {animation_asset.get_name()}: {exc}")
    return section
'''
    source = _replace_once(source, old_section, new_section, "Animation section helper changed")

    old_approach = '''                            _add_animation_section(
                                track,
                                locomotion_asset,
                                approach_start,
                                approach_end,
                                1,
                                play_rate,
                            )
                            section_count += 1
                            active_ranges.append((approach_start, approach_end))
'''
    new_approach = '''                            approach_duration = (approach_end - approach_start) / float(FPS)
                            approach_blend_frames = blend_frames(FPS, 0.10, approach_duration)
                            approach_section_end = min(end_frame, approach_end + approach_blend_frames)
                            _add_animation_section(
                                track,
                                locomotion_asset,
                                approach_start,
                                approach_section_end,
                                1,
                                play_rate,
                                0.08,
                                0.10,
                            )
                            section_count += 1
                            active_ranges.append((approach_start, approach_section_end))
                            exchange[f"{prefix}transition_blend_frames"] = approach_blend_frames
'''
    source = _replace_once(source, old_approach, new_approach, "Combat approach section changed")

    old_intent_call = '''            try:
                _add_animation_section(track, animation_asset, start, end, row, play_rate)
                section_count += 1
                active_ranges.append((start, end))
'''
    new_intent_call = '''            try:
                blend_in = float(intent.get("blend_in_seconds", 0.10))
                blend_out = float(intent.get("blend_out_seconds", 0.10))
                _add_animation_section(
                    track,
                    animation_asset,
                    start,
                    end,
                    row,
                    play_rate,
                    blend_in,
                    blend_out,
                )
                section_count += 1
                active_ranges.append((start, end))
'''
    source = _replace_once(source, old_intent_call, new_intent_call, "Intent animation call changed")

    old_idle_ranges = '''            cursor = 0
            idle_ranges = []
            for range_start, range_end in merged:
                if range_start > cursor:
                    idle_ranges.append((cursor, range_start))
                cursor = max(cursor, range_end)
            if cursor < end_frame:
                idle_ranges.append((cursor, end_frame))
'''
    new_idle_ranges = '''            cursor = 0
            idle_ranges = []
            idle_overlap = blend_frames(FPS, 0.08, 1.0)
            for range_start, range_end in merged:
                if range_start > cursor:
                    idle_ranges.append((cursor, min(end_frame, range_start + idle_overlap)))
                cursor = max(cursor, max(range_start, range_end - idle_overlap))
            if cursor < end_frame:
                idle_ranges.append((cursor, end_frame))
'''
    source = _replace_once(source, old_idle_ranges, new_idle_ranges, "Idle gap blending block changed")

    old_idle_call = '''                    _add_animation_section(track, idle_asset, idle_start, idle_end, 0)
'''
    new_idle_call = '''                    _add_animation_section(
                        track,
                        idle_asset,
                        idle_start,
                        idle_end,
                        0,
                        1.0,
                        0.08,
                        0.08,
                    )
'''
    source = _replace_once(source, old_idle_call, new_idle_call, "Idle animation section call changed")

    return source_path, source


def main():
    source_path, source = _polished_source()
    unreal.log(
        f"[CrawlPresentationPolish] Running validated camera/contact + locomotion-facing/crossfade polish: {source_path.name}"
    )
    namespace = {
        "__file__": str(source_path),
        "__name__": "__crawl_transition_polish_build__",
    }
    exec(compile(source, str(source_path), "exec"), namespace, namespace)


main()
