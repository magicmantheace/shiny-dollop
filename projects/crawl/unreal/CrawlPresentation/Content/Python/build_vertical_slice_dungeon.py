"""Slice 28A.5 deterministic dungeon wrapper over the proven corpse build."""

from pathlib import Path

import unreal


BASE_WRAPPER = "build_vertical_slice_death_hold.py"


def _replace_once(source, old, new, description):
    if old not in source:
        raise RuntimeError(f"{description}; dungeon wrapper needs updating")
    return source.replace(old, new, 1)


def _corpse_source():
    wrapper_path = Path(__file__).with_name(BASE_WRAPPER)
    source = wrapper_path.read_text(encoding="utf-8")
    terminal = "\n\nmain()"
    if not source.rstrip().endswith("main()") or terminal not in source:
        raise RuntimeError("Corpse-hold wrapper entrypoint changed")
    namespace = {"__file__": str(wrapper_path), "__name__": "__crawl_corpse_library__"}
    exec(compile(source.rsplit(terminal, 1)[0], str(wrapper_path), "exec"), namespace, namespace)
    return namespace["_corpse_hold_source"]()


def _dungeon_source():
    source_path, source = _corpse_source()
    source = _replace_once(source, 'SCRIPT_VERSION = "v12"', 'SCRIPT_VERSION = "v13"', "Expected v12 corpse builder")
    source = _replace_once(
        source,
        "from camera_planning import HORIZONTAL_FOV_DEGREES\n",
        "from camera_planning import HORIZONTAL_FOV_DEGREES, configure_environment\n"
        "from dungeon_environment_unreal import load_environment_manifest, spawn_dungeon_environment, finalize_environment_debug\n",
        "Camera import anchor changed",
    )
    source = _replace_once(
        source,
        "    _spawn_environment(actor_subsystem)\n",
        "    environment_manifest_path, environment_manifest = load_environment_manifest()\n"
        "    configure_environment(environment_manifest)\n"
        "    environment_spawn_debug = spawn_dungeon_environment(\n"
        "        actor_subsystem, environment_manifest_path, environment_manifest, slots\n"
        "    )\n",
        "Environment spawn anchor changed",
    )
    source = _replace_once(
        source,
        '''    component.set_editor_property("current_focal_length", 35.0)
    return component
''',
        '''    component.set_editor_property("current_focal_length", 35.0)
    # Dungeon-specific grade: retain the accepted camera optics while
    # countering the cold default sky contribution and protecting warm stone.
    post = component.get_editor_property("post_process_settings")
    post.set_editor_property("override_color_gain", True)
    post.set_editor_property("color_gain", unreal.Vector4(1.06, 0.98, 0.88, 1.0))
    post.set_editor_property("override_auto_exposure_bias", True)
    post.set_editor_property("auto_exposure_bias", -1.0)
    component.set_editor_property("post_process_settings", post)
    component.set_editor_property("post_process_blend_weight", 1.0)
    return component
''',
        "CineCamera grade anchor changed",
    )
    camera_anchor = '''    camera_debug = _animate_camera(
        sequence,
        actor_tracks,
        actor_visual_profiles,
        manifest["beats"],
        manifest["duration_seconds"],
        manifest.get("camera_cues", []),
        camera_debug_path,
    )
'''
    camera_replacement = camera_anchor + '''    environment_debug = finalize_environment_debug(
        environment_manifest,
        environment_spawn_debug,
        camera_debug,
        manifest,
        death_debug,
    )
    camera_debug["environment_validation"] = environment_debug["camera_obstruction_checks"]
    camera_debug["environment_room_id"] = environment_manifest["room_id"]
    camera_debug_path.write_text(json.dumps(camera_debug, indent=2), encoding="utf-8")
    environment_debug_path = _project_dir() / "Generated" / "environment_debug.json"
    environment_debug_path.write_text(json.dumps(environment_debug, indent=2), encoding="utf-8")
'''
    source = _replace_once(source, camera_anchor, camera_replacement, "Camera diagnostics anchor changed")
    source = _replace_once(
        source,
        '        "death_debug": str(death_debug_path),\n',
        '        "death_debug": str(death_debug_path),\n'
        '        "environment_manifest": str(environment_manifest_path),\n'
        '        "environment_digest": environment_manifest["digest"],\n'
        '        "environment_debug": str(environment_debug_path),\n'
        '        "environment_protocol": environment_manifest["protocol"],\n'
        '        "environment_room_id": environment_manifest["room_id"],\n',
        "Build metadata anchor changed",
    )
    return source_path, source


def main():
    source_path, source = _dungeon_source()
    unreal.log(f"[CrawlDungeon] Running Slice 28A.5 dungeon build: {source_path.name}")
    namespace = {"__file__": str(source_path), "__name__": "__crawl_dungeon_build__"}
    exec(compile(source, str(source_path), "exec"), namespace, namespace)


main()
