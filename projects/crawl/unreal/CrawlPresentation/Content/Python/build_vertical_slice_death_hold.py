"""Slice 28A corpse-hold wrapper over terminal death validation.

Canonical death/defeat remains authoritative. This layer changes only Sequencer
completion behavior: terminal skeletal animation sections keep their final pose
instead of restoring the pre-animated/default pose when the section ends.
"""

from pathlib import Path

import unreal


BASE_WRAPPER = "build_vertical_slice_death.py"


def _replace_once(source, old, new, description):
    if old not in source:
        raise RuntimeError(f"{description}; corpse-hold wrapper needs updating")
    return source.replace(old, new, 1)


def _terminal_source():
    wrapper_path = Path(__file__).with_name(BASE_WRAPPER)
    source = wrapper_path.read_text(encoding="utf-8")
    terminal = "\n\nmain()"
    if not source.rstrip().endswith("main()") or terminal not in source:
        raise RuntimeError("Death-persistence wrapper entrypoint changed")
    namespace = {"__file__": str(wrapper_path), "__name__": "__crawl_death_library__"}
    exec(compile(source.rsplit(terminal, 1)[0], str(wrapper_path), "exec"), namespace, namespace)
    return namespace["_death_source"]()


def _corpse_hold_source():
    source_path, source = _terminal_source()
    source = _replace_once(source, 'SCRIPT_VERSION = "v11"', 'SCRIPT_VERSION = "v12"', "Expected v11 death builder")

    old = '''            try:\n                blend_in = float(intent.get("blend_in_seconds", 0.10))\n                blend_out = float(intent.get("blend_out_seconds", 0.10))\n                _add_animation_section(\n                    track,\n                    animation_asset,\n                    start,\n                    end,\n                    row,\n                    play_rate,\n                    blend_in,\n                    blend_out,\n                )\n                section_count += 1\n                active_ranges.append((start, end))\n'''
    new = '''            try:\n                blend_in = float(intent.get("blend_in_seconds", 0.10))\n                blend_out = float(intent.get("blend_out_seconds", 0.10))\n                created_section = _add_animation_section(\n                    track,\n                    animation_asset,\n                    start,\n                    end,\n                    row,\n                    play_rate,\n                    blend_in,\n                    blend_out,\n                )\n                if intent.get("role") in TERMINAL_ROLES:\n                    # Keep the final authored corpse pose after the death/defeat\n                    # section completes. This prevents Sequencer from restoring\n                    # the actor's pre-animated/default standing pose.\n                    keep_state_applied = False\n                    try:\n                        created_section.set_editor_property(\n                            "completion_mode",\n                            unreal.MovieSceneCompletionMode.KEEP_STATE,\n                        )\n                        keep_state_applied = True\n                    except Exception:\n                        try:\n                            created_section.set_completion_mode(\n                                unreal.MovieSceneCompletionMode.KEEP_STATE\n                            )\n                            keep_state_applied = True\n                        except Exception as exc:\n                            raise RuntimeError(\n                                f"Could not enable terminal KeepState for {actor_id}:{slot}: {exc}"\n                            )\n                    diagnostics.setdefault("terminal_keep_state_sections", []).append({\n                        "actor_id": actor_id,\n                        "asset_slot": slot,\n                        "start_frame": start,\n                        "end_frame": end,\n                        "keep_state": keep_state_applied,\n                    })\n                section_count += 1\n                active_ranges.append((start, end))\n'''
    source = _replace_once(source, old, new, "Animation section creation anchor changed")
    return source_path, source


def main():
    source_path, source = _corpse_hold_source()
    unreal.log(f"[CrawlDeathHold] Running terminal KeepState corpse build: {source_path.name}")
    namespace = {"__file__": str(source_path), "__name__": "__crawl_death_hold_build__"}
    exec(compile(source, str(source_path), "exec"), namespace, namespace)


main()
