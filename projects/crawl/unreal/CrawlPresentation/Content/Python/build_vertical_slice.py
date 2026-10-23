import json
import math
import os
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).parent))
from camera_planning import HORIZONTAL_FOV_DEGREES, plan_master_camera

FPS = 60
ARENA_HALF_SIZE = 650.0
SCRIPT_VERSION = "v6"
STAGE_PROTOCOL = "crawl.presentation-stage.v1"
ANIMATION_PROTOCOL = "crawl.presentation-animation.v1"
ASSET_PROTOCOL = "crawl.presentation-assets.v1"


def _log(message):
    unreal.log(f"[CrawlVerticalSlice] {message}")


def _warn(message):
    unreal.log_warning(f"[CrawlVerticalSlice] {message}")


def _project_dir():
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def _manifest_path():
    override = os.environ.get("CRAWL_STAGE_MANIFEST")
    if override:
        return Path(override)
    return _project_dir() / "Generated" / "stage_manifest.json"


def _animation_plan_path():
    override = os.environ.get("CRAWL_ANIMATION_PLAN")
    if override:
        return Path(override)
    return _project_dir() / "Generated" / "animation_plan.json"


def _asset_registry_path():
    override = os.environ.get("CRAWL_PRESENTATION_ASSETS")
    if override:
        return Path(override)
    return _project_dir() / "presentation_assets.json"


def _read_json(path, description):
    if not path.exists():
        raise RuntimeError(f"{description} not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_manifest():
    path = _manifest_path()
    payload = _read_json(path, "Crawl staging manifest")
    if payload.get("protocol") != STAGE_PROTOCOL:
        raise RuntimeError(f"Unsupported staging protocol: {payload.get('protocol')}")
    if payload.get("authoritative") is not False:
        raise RuntimeError("Unreal only accepts presentation-only staging manifests")
    return path, payload


def _load_animation_plan(manifest):
    path = _animation_plan_path()
    payload = _read_json(path, "Crawl animation plan")
    if payload.get("protocol") != ANIMATION_PROTOCOL:
        raise RuntimeError(f"Unsupported animation protocol: {payload.get('protocol')}")
    if payload.get("authoritative") is not False:
        raise RuntimeError("Unreal only accepts presentation-only animation plans")
    if payload.get("source_staging_digest") != manifest.get("digest"):
        raise RuntimeError("Animation plan does not match the loaded staging manifest")
    if payload.get("source_event_ids") != manifest.get("source_event_ids"):
        raise RuntimeError("Animation plan source events do not match the staging manifest")
    return path, payload


def _load_asset_registry():
    path = _asset_registry_path()
    if not path.exists():
        _warn(f"No local presentation asset registry at {path}; primitives will be used as safe fallback.")
        return path, {"protocol": ASSET_PROTOCOL, "authoritative": False, "slots": {}}
    payload = _read_json(path, "Crawl presentation asset registry")
    if payload.get("protocol") != ASSET_PROTOCOL:
        raise RuntimeError(f"Unsupported presentation asset protocol: {payload.get('protocol')}")
    if payload.get("authoritative") is not False:
        raise RuntimeError("Presentation asset registry must be non-authoritative")
    if not isinstance(payload.get("slots", {}), dict):
        raise RuntimeError("Presentation asset registry slots must be an object")
    return path, payload


def _slot_path(slots, slot):
    value = slots.get(slot)
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        path = value.get("asset") or value.get("path")
        if isinstance(path, str) and path.strip():
            return path.strip()
    return None


def _load_slot_asset(slots, slot, diagnostics):
    path = _slot_path(slots, slot)
    if not path:
        diagnostics["missing_slots"].add(slot)
        return None
    asset = unreal.load_asset(path)
    if asset is None:
        diagnostics["missing_assets"].add(f"{slot}={path}")
        return None
    diagnostics["resolved_slots"].add(slot)
    return asset


def _prepare_in_place_animation_asset(animation_asset):
    """Duplicate a root-motion clip into generated content and lock its root.

    The source Epic animation stays untouched. Generated sequences can then use
    the authored body/limb motion without translating the skeleton away from the
    deterministic actor transform track or snapping when the section ends.
    """
    source_path = animation_asset.get_path_name()
    generated_path = (
        "/Game/CrawlGenerated/PresentationAnimations/"
        f"{animation_asset.get_name()}_InPlace"
    )
    prepared = unreal.load_asset(generated_path)
    if prepared is None:
        prepared = unreal.EditorAssetLibrary.duplicate_asset(source_path, generated_path)
    if prepared is None:
        raise RuntimeError(f"Could not create in-place animation duplicate for {source_path}")
    prepared.set_editor_property("enable_root_motion", True)
    prepared.set_editor_property("force_root_lock", True)
    unreal.EditorAssetLibrary.save_loaded_asset(prepared, False)
    return prepared


def _vector(transform):
    return unreal.Vector(float(transform["x"]), float(transform["y"]), float(transform.get("z", 90.0)))


def _spawn_mesh(actor_subsystem, mesh_path, location, rotation, scale, label):
    actor = actor_subsystem.spawn_actor_from_class(unreal.StaticMeshActor, location, rotation, False)
    actor.set_actor_label(label)
    mesh = unreal.load_asset(mesh_path)
    if mesh is None:
        raise RuntimeError(f"Required engine mesh missing: {mesh_path}")
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    component.set_static_mesh(mesh)
    actor.set_actor_scale3d(scale)
    return actor


def _spawn_skeletal_actor(actor_subsystem, skeletal_mesh, location, rotation, scale, label):
    actor = actor_subsystem.spawn_actor_from_class(unreal.SkeletalMeshActor, location, rotation, False)
    if actor is None:
        return None
    actor.set_actor_label(label)
    component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    if component is None:
        actor_subsystem.destroy_actor(actor)
        return None
    try:
        if hasattr(component, "set_skeletal_mesh_asset"):
            component.set_skeletal_mesh_asset(skeletal_mesh)
        elif hasattr(component, "set_skeletal_mesh"):
            component.set_skeletal_mesh(skeletal_mesh)
        else:
            component.set_editor_property("skeletal_mesh_asset", skeletal_mesh)
    except Exception as exc:
        _warn(f"Could not bind skeletal mesh {skeletal_mesh.get_path_name()}: {exc}")
        actor_subsystem.destroy_actor(actor)
        return None
    # Generated SkeletalMeshActors can otherwise retain a mode that leaves
    # Sequencer's animation nodes unevaluated while transform tracks still move.
    component.set_animation_mode(unreal.AnimationMode.ANIMATION_CUSTOM_MODE)
    actor.set_actor_scale3d(scale)
    return actor


def _capture_actor_visual_profiles(world_actors):
    """Capture rendered mesh bounds relative to each presentation root.

    The staged mannequin variants do not share a common root-to-body offset;
    fitting their roots alone can put an entire visible body outside the frame.
    """
    profiles = {}
    for actor_id, actor in world_actors.items():
        root = actor.get_actor_location()
        rotation = actor.get_actor_rotation()
        bounds_origin, bounds_extent = actor.get_actor_bounds(False, True)
        profiles[actor_id] = {
            "center_offset": {
                "x": float(bounds_origin.x - root.x),
                "y": float(bounds_origin.y - root.y),
                "z": float(bounds_origin.z - root.z),
            },
            "extent": {
                "x": float(bounds_extent.x),
                "y": float(bounds_extent.y),
                "z": float(bounds_extent.z),
            },
            "root_yaw": float(rotation.yaw),
        }
    return profiles


def _spawn_environment(actor_subsystem):
    floor = _spawn_mesh(
        actor_subsystem,
        "/Engine/BasicShapes/Cube.Cube",
        unreal.Vector(0.0, 0.0, -35.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        unreal.Vector(14.0, 14.0, 0.5),
        "Crawl_ArenaFloor",
    )
    floor.set_folder_path("Crawl/Environment")

    wall_specs = [
        (unreal.Vector(0.0, ARENA_HALF_SIZE, 160.0), unreal.Vector(14.0, 0.35, 3.2)),
        (unreal.Vector(0.0, -ARENA_HALF_SIZE, 160.0), unreal.Vector(14.0, 0.35, 3.2)),
        (unreal.Vector(ARENA_HALF_SIZE, 0.0, 160.0), unreal.Vector(0.35, 14.0, 3.2)),
        (unreal.Vector(-ARENA_HALF_SIZE, 0.0, 160.0), unreal.Vector(0.35, 14.0, 3.2)),
    ]
    for index, (location, scale) in enumerate(wall_specs):
        wall = _spawn_mesh(
            actor_subsystem,
            "/Engine/BasicShapes/Cube.Cube",
            location,
            unreal.Rotator(0.0, 0.0, 0.0),
            scale,
            f"Crawl_ArenaWall_{index}",
        )
        wall.set_folder_path("Crawl/Environment")
        # These are simulation-space guides, not presentation scenery. Keeping
        # them hidden guarantees that a valid camera cannot render an opaque wall.
        wall.set_actor_hidden_in_game(True)

    directional = actor_subsystem.spawn_actor_from_class(
        unreal.DirectionalLight,
        unreal.Vector(0.0, 0.0, 500.0),
        unreal.Rotator(-42.0, -35.0, 0.0),
        False,
    )
    directional.set_actor_label("Crawl_KeyLight")
    directional.set_folder_path("Crawl/Lighting")
    direction_component = directional.get_component_by_class(unreal.DirectionalLightComponent)
    if direction_component:
        direction_component.set_editor_property("intensity", 7.0)

    skylight = actor_subsystem.spawn_actor_from_class(
        unreal.SkyLight,
        unreal.Vector(0.0, 0.0, 300.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        False,
    )
    skylight.set_actor_label("Crawl_FillLight")
    skylight.set_folder_path("Crawl/Lighting")
    sky_component = skylight.get_component_by_class(unreal.SkyLightComponent)
    if sky_component:
        sky_component.set_editor_property("intensity", 1.2)


def _actor_visual(actor_subsystem, actor_payload, rig_slot, slots, diagnostics):
    transform = actor_payload["initial_transform"]
    location = _vector(transform)
    rotation = unreal.Rotator(0.0, float(transform.get("yaw", 0.0)), 0.0)
    scale = float(actor_payload.get("scale", 1.0))
    label = f"CrawlActor_{actor_payload['actor_id']}"

    skeletal_mesh = _load_slot_asset(slots, rig_slot, diagnostics) if rig_slot else None
    if skeletal_mesh is not None:
        skeletal = _spawn_skeletal_actor(
            actor_subsystem,
            skeletal_mesh,
            location,
            rotation,
            unreal.Vector(scale, scale, scale),
            label,
        )
        if skeletal is not None:
            skeletal.set_folder_path("Crawl/Actors")
            diagnostics["skeletal_actor_ids"].add(actor_payload["actor_id"])
            return skeletal, True
        diagnostics["failed_skeletal_slots"].add(rig_slot)

    if actor_payload.get("actor_kind") == "enemy":
        mesh_path = "/Engine/BasicShapes/Cube.Cube"
        actor_scale = unreal.Vector(1.15 * scale, 1.15 * scale, 1.45 * scale)
    else:
        mesh_path = "/Engine/BasicShapes/Cylinder.Cylinder"
        actor_scale = unreal.Vector(0.52 * scale, 0.52 * scale, 1.75 * scale)
    actor = _spawn_mesh(actor_subsystem, mesh_path, location, rotation, actor_scale, label)
    actor.set_folder_path("Crawl/Actors")
    diagnostics["fallback_actor_ids"].add(actor_payload["actor_id"])
    return actor, False


def _frame(seconds):
    return unreal.FrameNumber(int(round(float(seconds) * FPS)))


def _ensure_transform_track(binding, end_frame):
    # Sequencer actor binding helpers may seed a transform track. Reuse it: two
    # transform tracks on one binding are ambiguous and Movie Render Queue can
    # evaluate the empty seeded track instead of the keyed presentation track.
    transform_tracks = [
        track for track in binding.get_tracks()
        if isinstance(track, unreal.MovieScene3DTransformTrack)
    ]
    track = transform_tracks[0] if transform_tracks else binding.add_track(unreal.MovieScene3DTransformTrack)
    sections = list(track.get_sections())
    section = sections[0] if sections else track.add_section()
    section.set_range(0, end_frame)
    channels = unreal.MovieSceneSectionExtensions.get_all_channels(section)
    if len(channels) < 9:
        raise RuntimeError(f"Expected at least 9 transform channels, got {len(channels)}")
    for channel in channels[:9]:
        for key in list(channel.get_keys()):
            channel.remove_key(key)
    return channels


def _key_pose(channels, frame, pose, scale, interpolation=None):
    values = [
        pose["x"], pose["y"], pose["z"],
        pose.get("roll", 0.0), pose.get("pitch", 0.0), pose.get("yaw", 0.0),
        scale[0], scale[1], scale[2],
    ]
    time = unreal.FrameNumber(int(frame))
    key_interpolation = interpolation or unreal.MovieSceneKeyInterpolation.AUTO
    for channel, value in zip(channels[:9], values):
        channel.add_key(time, float(value), interpolation=key_interpolation)


def _copy_pose(pose):
    return dict(pose)


def _distance_direction(source, target):
    dx = target["x"] - source["x"]
    dy = target["y"] - source["y"]
    length = max(1.0, math.sqrt(dx * dx + dy * dy))
    return dx / length, dy / length


def _face(source, target):
    return math.degrees(math.atan2(target["y"] - source["y"], target["x"] - source["x"]))


def _match_bindings(world_actors, bindings):
    result = {}
    actor_ids = list(world_actors)
    for actor_id, actor in world_actors.items():
        for candidate in bindings:
            name = candidate.get_name()
            if name == actor.get_actor_label() or actor_id in name:
                result[actor_id] = candidate
                break
        if actor_id not in result:
            result[actor_id] = bindings[actor_ids.index(actor_id)]
    return result


def _animate_actors(sequence, actor_payloads, world_actors, beats, skeletal_actor_ids):
    ls_system = unreal.get_editor_subsystem(unreal.LevelSequenceEditorSubsystem)
    end_frame = int(sequence.get_playback_end())
    pose_by_id = {}
    scale_by_id = {}
    channels_by_id = {}
    pose_tracks = {}
    combat_debug = []

    def key_actor(actor_id, frame, pose, interpolation=None):
        _key_pose(
            channels_by_id[actor_id],
            frame,
            pose,
            scale_by_id[actor_id],
            interpolation,
        )
        pose_tracks[actor_id].append({
            "seconds": float(frame) / FPS,
            "pose": _copy_pose(pose),
        })

    bindings = ls_system.add_actors(list(world_actors.values()))
    bindings_by_id = _match_bindings(world_actors, bindings)
    # UE's actor-binding editor hook can auto-create a full-body Control Rig
    # and a blank skeletal track. Both override the presentation sections with
    # a held pose, making transform-driven actors slide with frozen limbs.
    # Retain the transform track and remove only those auto-created pose tracks;
    # _apply_skeletal_animations adds the single intentional animation track.
    for binding in bindings:
        for track in list(binding.get_tracks()):
            if track.get_class().get_name() in {
                "MovieSceneControlRigParameterTrack",
                "MovieSceneSkeletalAnimationTrack",
            }:
                binding.remove_track(track)

    for actor_payload in actor_payloads:
        actor_id = actor_payload["actor_id"]
        actor = world_actors[actor_id]
        channels = _ensure_transform_track(bindings_by_id[actor_id], end_frame)
        t = actor_payload["initial_transform"]
        pose = {
            "x": float(t["x"]), "y": float(t["y"]), "z": float(t.get("z", 90.0)),
            "roll": 0.0, "pitch": 0.0, "yaw": float(t.get("yaw", 0.0)),
        }
        actor_scale = actor.get_actor_scale3d()
        scale = (actor_scale.x, actor_scale.y, actor_scale.z)
        pose_by_id[actor_id] = pose
        scale_by_id[actor_id] = scale
        channels_by_id[actor_id] = channels
        pose_tracks[actor_id] = []
        key_actor(actor_id, 0, pose)

    for beat in beats:
        action = beat.get("action", "observe")
        performer_id = beat.get("performer_id")
        target_id = beat.get("target_id")
        start = int(round(float(beat["start_seconds"]) * FPS))
        end = int(round((float(beat["start_seconds"]) + float(beat["duration_seconds"])) * FPS))
        mid = (start + end) // 2

        if action == "attack_hit" and performer_id in pose_by_id and target_id in pose_by_id:
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

        elif action in {"defeat", "death"} and target_id in pose_by_id:
            if target_id not in skeletal_actor_ids:
                target = pose_by_id[target_id]
                fallen = _copy_pose(target)
                fallen["z"] = 40.0
                fallen["pitch"] = 88.0
                key_actor(target_id, start, target)
                key_actor(target_id, end, fallen)
                pose_by_id[target_id] = fallen

        elif action in {"injury_reaction", "near_death"} and target_id in pose_by_id:
            if target_id not in skeletal_actor_ids:
                target = pose_by_id[target_id]
                react = _copy_pose(target)
                react["z"] = max(45.0, target["z"] - 28.0)
                react["pitch"] = -16.0
                key_actor(target_id, start, target)
                key_actor(target_id, mid, react)
                if action == "injury_reaction":
                    key_actor(target_id, end, target)
                else:
                    key_actor(target_id, end, react)
                    pose_by_id[target_id] = react

        elif action == "retreat" and performer_id in pose_by_id:
            performer = pose_by_id[performer_id]
            length = max(1.0, math.sqrt(performer["x"] ** 2 + performer["y"] ** 2))
            retreat = _copy_pose(performer)
            retreat["x"] = performer["x"] / length * 560.0
            retreat["y"] = performer["y"] / length * 560.0
            key_actor(performer_id, start, performer)
            key_actor(performer_id, end, retreat)
            pose_by_id[performer_id] = retreat

        elif action == "rescue" and performer_id in pose_by_id and target_id in pose_by_id:
            performer = pose_by_id[performer_id]
            target = pose_by_id[target_id]
            dx, dy = _distance_direction(performer, target)
            rescue = _copy_pose(performer)
            rescue["x"] = target["x"] - dx * 125.0
            rescue["y"] = target["y"] - dy * 125.0
            rescue["yaw"] = _face(rescue, target)
            key_actor(performer_id, start, performer)
            key_actor(performer_id, end, rescue)
            pose_by_id[performer_id] = rescue

        elif action == "move" and performer_id in pose_by_id:
            performer = pose_by_id[performer_id]
            moved = _copy_pose(performer)
            angle = math.radians(performer.get("yaw", 0.0))
            moved["x"] += math.cos(angle) * 140.0
            moved["y"] += math.sin(angle) * 140.0
            key_actor(performer_id, start, performer)
            key_actor(performer_id, end, moved)
            pose_by_id[performer_id] = moved

    for actor_id, pose in pose_by_id.items():
        key_actor(actor_id, end_frame, pose)

    return pose_tracks, bindings_by_id, combat_debug


def _set_animation_on_section(section, animation_asset, play_rate=1.0):
    params = section.get_editor_property("params")
    params.set_editor_property("animation", animation_asset)
    params.set_editor_property("force_custom_mode", True)
    time_warp = params.get_editor_property("play_rate")
    time_warp.set_fixed_play_rate(float(play_rate))
    params.set_editor_property("play_rate", time_warp)
    section.set_editor_property("params", params)


def _add_animation_section(track, animation_asset, start_frame, end_frame, row_index, play_rate=1.0):
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


def _apply_skeletal_animations(sequence, animation_plan, bindings_by_id, skeletal_actor_ids, slots, diagnostics):
    rig_by_id = {rig["actor_id"]: rig for rig in animation_plan.get("rigs", [])}
    intents_by_actor = {}
    for intent in animation_plan.get("intents", []):
        intents_by_actor.setdefault(intent["actor_id"], []).append(intent)

    end_frame = int(sequence.get_playback_end())
    section_count = 0
    layer_rows = {"locomotion": 1, "action": 2, "reaction": 3, "additive": 4}

    for actor_id in sorted(skeletal_actor_ids):
        binding = bindings_by_id.get(actor_id)
        if binding is None:
            diagnostics["animation_errors"].append(f"No Sequencer binding for skeletal actor {actor_id}")
            continue
        track = binding.add_track(unreal.MovieSceneSkeletalAnimationTrack)
        rig = rig_by_id.get(actor_id, {})
        active_ranges = []

        idle_slot = rig.get("idle_slot")
        idle_asset = None
        if idle_slot:
            idle_asset = _load_slot_asset(slots, idle_slot, diagnostics)

        for intent in sorted(intents_by_actor.get(actor_id, []), key=lambda item: (item["start_seconds"], -item.get("priority", 0), item["id"])):
            slot = intent.get("asset_slot")
            if not slot:
                continue
            animation_asset = _load_slot_asset(slots, slot, diagnostics)
            if animation_asset is None:
                continue
            start = int(round(float(intent["start_seconds"]) * FPS))
            end = int(round((float(intent["start_seconds"]) + float(intent["duration_seconds"])) * FPS))
            row = layer_rows.get(intent.get("layer"), 2)
            try:
                _add_animation_section(track, animation_asset, start, end, row)
                section_count += 1
                active_ranges.append((start, end))
            except Exception as exc:
                diagnostics["animation_errors"].append(f"{actor_id}:{slot}:{exc}")

        # Full-body Sequencer sections normalize together. A single idle section
        # spanning the complete timeline would dilute every walk, attack, and
        # reaction pose. Fill only genuine gaps so active clips retain full reach.
        if idle_asset is not None:
            merged = []
            for range_start, range_end in sorted(active_ranges):
                if not merged or range_start > merged[-1][1]:
                    merged.append([range_start, range_end])
                else:
                    merged[-1][1] = max(merged[-1][1], range_end)
            cursor = 0
            idle_ranges = []
            for range_start, range_end in merged:
                if range_start > cursor:
                    idle_ranges.append((cursor, range_start))
                cursor = max(cursor, range_end)
            if cursor < end_frame:
                idle_ranges.append((cursor, end_frame))
            for idle_start, idle_end in idle_ranges:
                try:
                    _add_animation_section(track, idle_asset, idle_start, idle_end, 0)
                    section_count += 1
                except Exception as exc:
                    diagnostics["animation_errors"].append(
                        f"{actor_id}:{idle_slot}:gap:{idle_start}-{idle_end}:{exc}"
                    )

    diagnostics["animation_section_count"] = section_count
    return section_count


def _capture_evaluated_combat_contacts(sequence, world_actors, combat_debug):
    """Validate contact against the skeletal pose Sequencer actually evaluates."""
    if not combat_debug:
        return
    unreal.EditorAssetLibrary.save_loaded_asset(sequence, False)
    unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
    for exchange in combat_debug:
        frame = int(round(float(exchange["visual_contact_seconds"]) * FPS))
        unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(frame)
        performer = world_actors[exchange["performer_id"]]
        target = world_actors[exchange["target_id"]]
        performer_component = performer.get_component_by_class(unreal.SkeletalMeshComponent)
        target_component = target.get_component_by_class(unreal.SkeletalMeshComponent)
        effector_name = exchange["attack_profile"]["contact_effector"]
        effector = performer_component.get_socket_location(effector_name)
        torso = target_component.get_socket_location("spine_05")
        dx = float(effector.x - torso.x)
        dy = float(effector.y - torso.y)
        dz = float(effector.z - torso.z)
        planar_error = math.sqrt(dx * dx + dy * dy)
        exchange["evaluated_contact_frame"] = frame
        exchange["evaluated_contact_effector"] = {
            "bone": effector_name,
            "x": float(effector.x),
            "y": float(effector.y),
            "z": float(effector.z),
        }
        exchange["evaluated_target_torso"] = {
            "bone": "spine_05",
            "x": float(torso.x),
            "y": float(torso.y),
            "z": float(torso.z),
        }
        exchange["evaluated_contact_planar_error_cm"] = planar_error
        exchange["evaluated_contact_vertical_error_cm"] = dz
        contact_error = math.sqrt(dx * dx + dy * dy + dz * dz)
        exchange["evaluated_contact_error_cm"] = contact_error
        maximum_planar_error = float(
            exchange["attack_profile"]["maximum_evaluated_planar_error_cm"]
        )
        maximum_contact_error = float(
            exchange["attack_profile"]["maximum_evaluated_contact_error_cm"]
        )
        exchange["maximum_evaluated_planar_error_cm"] = maximum_planar_error
        exchange["maximum_evaluated_contact_error_cm"] = maximum_contact_error
        if planar_error > maximum_planar_error or contact_error > maximum_contact_error:
            raise RuntimeError(
                f"Evaluated combat contact is too far from target torso: "
                f"{exchange['attack_id']} planar_error={planar_error:.2f}cm "
                f"contact_error={contact_error:.2f}cm"
            )


def _configure_camera_component(camera_actor):
    component = camera_actor.get_cine_camera_component()
    if component is None:
        raise RuntimeError("Generated level camera has no CineCameraComponent")
    # Fix the level camera to a 16:9 filmback and 35mm lens. Camera planning
    # deliberately assumes only 38 degrees horizontally, leaving additional
    # safety margin beneath the configured lens's roughly 54-degree field.
    filmback = component.get_editor_property("filmback")
    filmback.set_editor_property("sensor_width", 36.0)
    filmback.set_editor_property("sensor_height", 20.25)
    component.set_editor_property("filmback", filmback)
    component.set_editor_property("current_focal_length", 35.0)
    return component


def _animate_camera(sequence, actor_tracks, actor_visual_profiles, beats, duration_seconds, cues, debug_path):
    camera_debug = plan_master_camera(
        actor_tracks, beats, duration_seconds, cues, actor_visual_profiles
    )
    ls_system = unreal.get_editor_subsystem(unreal.LevelSequenceEditorSubsystem)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    first_shot = camera_debug["camera_shots"][0]
    first_position = first_shot["camera_position"]
    first_rotation = first_shot["camera_rotation"]
    # Persist a real CineCameraActor in the generated map. UE 5.8's
    # create_camera(False) produces a replaceable custom binding but does not
    # save an actor for Movie Render Queue to resolve on its first evaluation.
    camera_actor = actor_subsystem.spawn_actor_from_class(
        unreal.CineCameraActor,
        unreal.Vector(first_position["x"], first_position["y"], first_position["z"]),
        unreal.Rotator(first_rotation["pitch"], first_rotation["yaw"], first_rotation["roll"]),
        False,
    )
    if camera_actor is None:
        raise RuntimeError("Could not spawn persistent Crawl master camera")
    camera_actor.set_actor_label("Crawl_MasterCamera")
    camera_actor.set_folder_path("Crawl/Camera")
    component = _configure_camera_component(camera_actor)
    camera_bindings = ls_system.add_actors([camera_actor])
    if len(camera_bindings) != 1:
        raise RuntimeError(f"Expected one persistent camera binding, got {len(camera_bindings)}")
    camera_binding = camera_bindings[0]
    camera_cut_track = sequence.add_track(unreal.MovieSceneCameraCutTrack)
    camera_cut_section = camera_cut_track.add_section()
    camera_cut_section.set_range(0, int(sequence.get_playback_end()))
    camera_binding_id = unreal.MovieSceneObjectBindingID()
    camera_binding_id.set_editor_property("Guid", camera_binding.get_id())
    camera_cut_section.set_camera_binding_id(camera_binding_id)
    channels = _ensure_transform_track(camera_binding, int(sequence.get_playback_end()))
    camera_scale = (1.0, 1.0, 1.0)
    for shot in camera_debug["camera_shots"]:
        location = shot["camera_position"]
        target = shot["target_center"]
        rotation = unreal.MathLibrary.find_look_at_rotation(
            unreal.Vector(location["x"], location["y"], location["z"]),
            unreal.Vector(target["x"], target["y"], target["z"]),
        )
        pose = {
            "x": location["x"], "y": location["y"], "z": location["z"],
            "roll": float(rotation.roll), "pitch": float(rotation.pitch), "yaw": float(rotation.yaw),
        }
        shot["camera_rotation"] = {
            "roll": pose["roll"], "pitch": pose["pitch"], "yaw": pose["yaw"],
        }
        _key_pose(
            channels,
            int(round(float(shot["seconds"]) * FPS)),
            pose,
            camera_scale,
            unreal.MovieSceneKeyInterpolation.LINEAR,
        )

    focal_length = float(component.get_editor_property("current_focal_length"))
    filmback = component.get_editor_property("filmback")
    sensor_width = float(filmback.get_editor_property("sensor_width"))
    camera_debug["camera_actor"] = camera_actor.get_name()
    camera_debug["current_focal_length_mm"] = focal_length
    camera_debug["sensor_width_mm"] = sensor_width
    camera_debug["configured_horizontal_fov_degrees"] = math.degrees(
        2.0 * math.atan(sensor_width / (2.0 * focal_length))
    )
    debug_path.parent.mkdir(parents=True, exist_ok=True)
    debug_path.write_text(json.dumps(camera_debug, indent=2), encoding="utf-8")
    return camera_debug


def _generated_package_path(asset_path, suffix):
    relative = asset_path.removeprefix("/Game/")
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())) / f"{relative}{suffix}"


def _delete_generated_package(asset_path, suffix):
    package_path = _generated_package_path(asset_path, suffix)
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        unreal.EditorAssetLibrary.delete_asset(asset_path)
    if package_path.exists():
        package_path.unlink()
    # UE 5.8 can retain a stale in-memory registry entry until the next tick even
    # after delete_asset removed the package. The on-disk package is the rebuild
    # gate; create_asset refreshes the registry entry immediately afterward.
    return not package_path.exists()


def _clean_generated_assets(level_asset, sequence_asset):
    level_file = _generated_package_path(level_asset, ".umap")
    sequence_file = _generated_package_path(sequence_asset, ".uasset")
    level_present = unreal.EditorAssetLibrary.does_asset_exist(level_asset) or level_file.exists()
    sequence_present = unreal.EditorAssetLibrary.does_asset_exist(sequence_asset) or sequence_file.exists()
    if not level_present and not sequence_present:
        return
    _log("Removing previous generated Unreal output before deterministic rebuild.")
    # Unreal may restore the last generated map on startup. An in-use world
    # package cannot be deleted, so move to the engine's neutral template first.
    if level_present:
        level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if not level_subsystem.load_level("/Engine/Maps/Templates/Template_Default"):
            raise RuntimeError("Failed to leave the generated level before rebuilding it")
    if sequence_present and not _delete_generated_package(sequence_asset, ".uasset"):
        raise RuntimeError(f"Failed to remove previous generated sequence {sequence_asset}")
    if level_present and not _delete_generated_package(level_asset, ".umap"):
        raise RuntimeError(f"Failed to remove previous generated level {level_asset}")
    # Force-destroy deleted world packages before reusing their deterministic
    # names; otherwise NewLevel can still see the pending-kill UObject in UE 5.8.
    unreal.SystemLibrary.collect_garbage()


def _jsonable_diagnostics(diagnostics):
    return {
        key: sorted(value) if isinstance(value, set) else value
        for key, value in diagnostics.items()
    }


def build():
    manifest_path, manifest = _load_manifest()
    animation_plan_path, animation_plan = _load_animation_plan(manifest)
    asset_registry_path, asset_registry = _load_asset_registry()
    slots = asset_registry.get("slots", {})

    diagnostics = {
        "resolved_slots": set(),
        "missing_slots": set(),
        "missing_assets": set(),
        "failed_skeletal_slots": set(),
        "skeletal_actor_ids": set(),
        "fallback_actor_ids": set(),
        "animation_errors": [],
        "animation_section_count": 0,
    }

    digest = manifest["digest"][:10]
    level_asset = f"/Game/CrawlGenerated/CrawlVerticalSlice_{SCRIPT_VERSION}_{digest}"
    sequence_name = f"LS_CrawlVerticalSlice_{SCRIPT_VERSION}_{digest}"
    sequence_asset = f"/Game/CrawlGenerated/{sequence_name}"

    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    _clean_generated_assets(level_asset, sequence_asset)

    if not level_subsystem.new_level(level_asset, False):
        raise RuntimeError(f"Failed to create generated level {level_asset}")

    _spawn_environment(actor_subsystem)

    rig_by_actor = {rig["actor_id"]: rig for rig in animation_plan.get("rigs", [])}
    world_actors = {}
    for actor_payload in manifest["actors"]:
        actor_id = actor_payload["actor_id"]
        rig_slot = rig_by_actor.get(actor_id, {}).get("rig_slot")
        world_actors[actor_id], _ = _actor_visual(actor_subsystem, actor_payload, rig_slot, slots, diagnostics)
    actor_visual_profiles = _capture_actor_visual_profiles(world_actors)

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    sequence = asset_tools.create_asset(
        sequence_name,
        "/Game/CrawlGenerated",
        unreal.LevelSequence,
        unreal.LevelSequenceFactoryNew(),
    )
    if sequence is None:
        raise RuntimeError("Failed to create Level Sequence")
    sequence.set_display_rate(unreal.FrameRate(FPS, 1))
    sequence.set_playback_start(0)
    sequence.set_playback_end(int(math.ceil(float(manifest["duration_seconds"]) * FPS)))
    unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence)

    actor_tracks, bindings_by_id, combat_debug = _animate_actors(
        sequence,
        manifest["actors"],
        world_actors,
        manifest["beats"],
        diagnostics["skeletal_actor_ids"],
    )
    _apply_skeletal_animations(
        sequence,
        animation_plan,
        bindings_by_id,
        diagnostics["skeletal_actor_ids"],
        slots,
        diagnostics,
    )
    _capture_evaluated_combat_contacts(sequence, world_actors, combat_debug)
    combat_debug_path = _project_dir() / "Generated" / "combat_debug.json"
    combat_debug_path.parent.mkdir(parents=True, exist_ok=True)
    combat_debug_path.write_text(
        json.dumps({
            "protocol": "crawl.presentation-combat-debug.v1",
            "authoritative": False,
            "attack_count": len(combat_debug),
            "attacks": combat_debug,
        }, indent=2),
        encoding="utf-8",
    )
    camera_debug_path = _project_dir() / "Generated" / "camera_debug.json"
    camera_debug = _animate_camera(
        sequence,
        actor_tracks,
        actor_visual_profiles,
        manifest["beats"],
        manifest["duration_seconds"],
        manifest.get("camera_cues", []),
        camera_debug_path,
    )

    unreal.EditorAssetLibrary.save_loaded_asset(sequence, False)
    level_subsystem.save_current_level()
    unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()

    result_path = _project_dir() / "Generated" / "unreal_build_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "manifest": str(manifest_path),
        "manifest_digest": manifest["digest"],
        "animation_plan": str(animation_plan_path),
        "animation_plan_digest": animation_plan["digest"],
        "asset_registry": str(asset_registry_path),
        "level_asset": level_asset,
        "sequence_asset": sequence_asset,
        "fps": FPS,
        "duration_seconds": manifest["duration_seconds"],
        "actor_count": len(manifest["actors"]),
        "beat_count": len(manifest["beats"]),
        "animation_intent_count": len(animation_plan.get("intents", [])),
        "presentation_assets": _jsonable_diagnostics(diagnostics),
        "camera_debug": str(camera_debug_path),
        "combat_debug": str(combat_debug_path),
        "camera_architecture": camera_debug["architecture"],
        "camera_sample_count": camera_debug["validation"]["sample_count"],
    }
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    _log(f"Generated level: {level_asset}")
    _log(f"Generated sequence: {sequence_asset}")
    _log(f"Source staging manifest: {manifest_path}")
    _log(f"Source animation plan: {animation_plan_path}")
    if diagnostics["skeletal_actor_ids"]:
        _log(f"Skeletal actors: {len(diagnostics['skeletal_actor_ids'])}")
    if diagnostics["fallback_actor_ids"]:
        _warn(f"Primitive fallback actors: {len(diagnostics['fallback_actor_ids'])}")
    if diagnostics["animation_errors"]:
        _warn(f"Animation binding errors recorded: {len(diagnostics['animation_errors'])}")
    _log("Open Sequencer and press Play. Assets and animation are presentation-only and cannot change Crawl truth.")
    return level_asset, sequence_asset


build()
