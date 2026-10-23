"""Consume Slice 28B.2 JSON-spool frames in one UE 5.8 editor session.

The accepted dungeon map and persistent actors are reused as the QA world.
Tracks and sections are then added incrementally as producer files arrive; no
frame triggers a level or sequence rebuild.
"""

import hashlib
import json
import math
import os
from pathlib import Path
import time

import unreal


FPS = 60
PROTOCOL = "underreach.live-presentation.v1"
LIVE_SEQUENCE = "/Game/CrawlGenerated/LS_UnderreachLive_28B2"
LIVE_PRESET = "/Game/CrawlGenerated/MPC_UnderreachLive_28B2"

POPULATION_MATERIAL_COLORS = {
    "skin_001": (0.72, 0.48, 0.34),
    "skin_002": (0.58, 0.34, 0.22),
    "skin_003": (0.42, 0.23, 0.14),
    "skin_004": (0.28, 0.14, 0.08),
    "skin_005": (0.16, 0.075, 0.04),
    "eye_001": (0.08, 0.16, 0.22),
    "eye_002": (0.10, 0.23, 0.12),
    "eye_003": (0.25, 0.17, 0.06),
    "eye_004": (0.08, 0.07, 0.05),
    "underreach.clothing.outfit.casual01.v1": (0.22, 0.075, 0.045),
    "underreach.clothing.outfit.casual02.v1": (0.055, 0.14, 0.20),
    "underreach.clothing.outfit.casual03.v1": (0.15, 0.19, 0.055),
    "underreach.clothing.outfit.casual04.v1": (0.20, 0.10, 0.22),
    "underreach.clothing.outfit.casual05.v1": (0.30, 0.16, 0.035),
    "underreach.clothing.outfit.worksuit01.v1": (0.10, 0.12, 0.13),
    "mpfb.system.hair.short01": (0.025, 0.018, 0.012),
    "mpfb.system.hair.short02": (0.12, 0.055, 0.018),
    "mpfb.system.hair.short03": (0.25, 0.13, 0.035),
    "mpfb.system.hair.short04": (0.035, 0.025, 0.018),
    "mpfb.system.hair.long01": (0.06, 0.025, 0.012),
    "mpfb.system.hair.braid01": (0.18, 0.07, 0.018),
    "iron_01": (0.22, 0.24, 0.26),
    "iron_02": (0.13, 0.16, 0.18),
    "iron_03": (0.28, 0.22, 0.12),
}


def project_dir():
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


GENERATED = project_dir() / "Generated"
SPOOL = GENERATED / "LiveBridge"


def log(message):
    unreal.log(f"[UnderreachLiveBridge] {message}")


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def verify(message):
    if message.get("protocol") != PROTOCOL:
        raise RuntimeError(f"Unsupported live protocol: {message.get('protocol')}")
    body = {key: value for key, value in message.items() if key != "digest"}
    if message.get("digest") != digest(body):
        raise RuntimeError("Live bridge digest mismatch")


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(str(temporary), str(path))


def wait_json(path, timeout=180.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for {path}")


def object_path(package_path):
    return f"{package_path}.{package_path.rsplit('/', 1)[-1]}"


def frame(seconds):
    return int(round(float(seconds) * FPS))


def set_animation(section, asset, play_rate=1.0):
    params = section.get_editor_property("params")
    params.set_editor_property("animation", asset)
    params.set_editor_property("force_custom_mode", True)
    time_warp = params.get_editor_property("play_rate")
    time_warp.set_fixed_play_rate(float(play_rate))
    params.set_editor_property("play_rate", time_warp)
    section.set_editor_property("params", params)


def prepare_root_locked_animation(asset):
    """Return a generated in-place copy without modifying Epic source data."""
    source_path = asset.get_path_name()
    generated_path = (
        "/Game/CrawlGenerated/PresentationAnimations/"
        f"{asset.get_name()}_InPlace"
    )
    # Character source assets are rebuilt by the local MPFB pipeline. Never
    # reuse an older generated in-place copy after a source reimport.
    if source_path.startswith("/Game/Underreach29A1/") and unreal.EditorAssetLibrary.does_asset_exist(generated_path):
        unreal.EditorAssetLibrary.delete_asset(generated_path)
    prepared = unreal.load_asset(generated_path)
    if prepared is None:
        prepared = unreal.EditorAssetLibrary.duplicate_asset(source_path, generated_path)
    if prepared is None:
        raise RuntimeError(f"Could not prepare root-locked live animation {source_path}")
    prepared.set_editor_property("enable_root_motion", True)
    prepared.set_editor_property("force_root_lock", True)
    unreal.EditorAssetLibrary.save_loaded_asset(prepared, False)
    return prepared


def keep_state(section):
    try:
        section.set_editor_property("completion_mode", unreal.MovieSceneCompletionMode.KEEP_STATE)
    except Exception:
        section.set_completion_mode(unreal.MovieSceneCompletionMode.KEEP_STATE)


class RuntimeActor:
    def __init__(self, actor_id, actor, binding, pose, channels, animation_track, character_manifest=None):
        self.actor_id = actor_id
        self.actor = actor
        self.binding = binding
        self.pose = dict(pose)
        self.channels = channels
        self.animation_track = animation_track
        self.animation_sections = []
        self.character_manifest = dict(character_manifest or {})
        self.species = self.character_manifest.get("species")
        self.visual_variant = self.character_manifest.get("visual_variant", f"{self.species}_average" if self.species else None)
        self.actor_scale = float(self.character_manifest.get("actor_scale", 1.0))
        if self.species:
            # MPFB/Blender rigs are authored in meters. The legacy FBX path is
            # required for reliable skin weights and morphs in UE 5.8, so the
            # disposable presentation actor performs the explicit cm scale.
            self.actor_scale *= 100.0
        # The accepted arena's standing root plane is Z=94 for every skeletal
        # presentation actor. Imported MPFB feet are grounded on that same
        # stage after FBX conversion; no species-specific lowering is needed.
        self.floor_z_offset = 0.0
        self.terminal = False
        self.terminal_start = None
        self.terminal_end = None
        self.material_assignments = []


class LiveUnrealConsumer:
    def __init__(self, bootstrap):
        verify(bootstrap)
        self.bootstrap = bootstrap
        self.descent_id = bootstrap["descent_id"]
        self.procedural_proof = any(
            actor.get("character_renderer_manifest")
            for actor in bootstrap.get("actors", [])
        )
        self.presentation_profile = bootstrap.get("presentation_profile", "28b2")
        if self.presentation_profile in {"28b3_multichannel", "28c1_spectator", "28c2_alpha_runtime"}:
            if self.presentation_profile in {"28c1_spectator", "28c2_alpha_runtime"}:
                self.live_sequence = "/Game/CrawlGenerated/LS_UnderreachViewer_28C1"
                self.live_preset = "/Game/CrawlGenerated/MPC_UnderreachViewer_28C1"
                self.render_slug = "underreach-viewer-28c1"
                self.render_name = "underreach_viewer_28c1"
            else:
                self.live_sequence = "/Game/CrawlGenerated/LS_UnderreachLive_28B3"
                self.live_preset = "/Game/CrawlGenerated/MPC_UnderreachLive_28B3"
                self.render_slug = "underreach-live-28b3"
                self.render_name = "underreach_live_28b3"
        else:
            self.live_sequence = LIVE_SEQUENCE
            self.live_preset = LIVE_PRESET
            self.render_slug = "underreach-live-28b2"
            self.render_name = "underreach_live_28b2"
        if self.procedural_proof:
            population = self.presentation_profile == "29a2_population"
            self.live_sequence = "/Game/CrawlGenerated/LS_Underreach29A2" if population else "/Game/CrawlGenerated/LS_Underreach29A1"
            self.live_preset = "/Game/CrawlGenerated/MPC_Underreach29A2" if population else "/Game/CrawlGenerated/MPC_Underreach29A1"
            self.render_slug = "underreach-29a2" if population else "underreach-29a1"
            self.render_name = "underreach_29a2_population_proof" if population else "underreach_29a1_live_proof"
        self.process_id = os.getpid()
        self.session_started_monotonic = time.monotonic()
        self.population_actor_assembly_seconds = 0.0
        self.bootstrap_count = 1
        self.environment_bootstrap_count = 1
        self.environment_rebuild_count = 0
        self.full_sequence_rebuild_count = 0
        self.applied_paths = set()
        self.applied_frame_ids = set()
        self.applied_command_ids = set()
        self.latest_frame_sequence = int(bootstrap.get("resume_cursor", {}).get("frame_sequence", 0))
        self.latest_frame_id = None
        self.duplicate_frames = 0
        self.rejected_frames = 0
        self.missing_ranges = []
        self.command_counts = {}
        self.frame_apply_log = []
        self.animation_errors = []
        self.root_locked_assets = {}
        self.population_materials = {}
        self.actors = {}
        self.attack_records = []
        self.camera_command_count = 0
        self.camera_cut_records = []
        self.focus_change_records = []
        self.facing_records = []
        self.viewport_camera_locked = False
        self.persistent_sections = []
        self._load_assets()
        self._bootstrap_world()

    def _population_material(self, category, variant):
        key = (str(category), str(variant))
        cached = self.population_materials.get(key)
        if cached is not None:
            return cached
        color = POPULATION_MATERIAL_COLORS.get(str(variant), (0.16, 0.13, 0.10))
        identity = hashlib.sha256(
            f"{category}:{variant}:{color}".encode("utf-8")
        ).hexdigest()[:12]
        package = f"/Game/CrawlGenerated/Underreach29A2/Materials/M_{category}_{identity}"
        material = unreal.load_asset(package)
        if material is None:
            material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                package.rsplit("/", 1)[-1],
                package.rsplit("/", 1)[0],
                unreal.Material,
                unreal.MaterialFactoryNew(),
            )
            if material is None:
                raise RuntimeError(f"Could not create population material {package}")
            expression = unreal.MaterialEditingLibrary.create_material_expression(
                material, unreal.MaterialExpressionConstant3Vector, -240, 0
            )
            expression.set_editor_property(
                "constant", unreal.LinearColor(float(color[0]), float(color[1]), float(color[2]), 1.0)
            )
            unreal.MaterialEditingLibrary.connect_material_property(
                expression, "", unreal.MaterialProperty.MP_BASE_COLOR
            )
            unreal.MaterialEditingLibrary.recompile_material(material)
            if not unreal.EditorAssetLibrary.save_loaded_asset(material, False):
                raise RuntimeError(f"Could not persist population material {package}")
        self.population_materials[key] = material
        return material

    @staticmethod
    def _population_material_category(slot_name):
        name = str(slot_name).lower()
        # Profile identifiers such as ``human_short_heavy`` are prefixes, not
        # surface semantics. Classify only the FBX material leaf after Body_.
        if "_body_" in name:
            name = name.split("_body_", 1)[1]
        if "eye" in name or "low-poly" in name:
            return "eyes"
        if any(token in name for token in ("casualsuit", "worksuit", "outfit", "clothing")):
            return "cloth"
        if any(token in name for token in ("hair", "beard", "short", "long", "braid")):
            return "hair"
        if any(token in name for token in ("iron", "rigid", "blade", "guard")):
            return "metal"
        if "body" in name:
            return "skin"
        return "cloth"

    def _apply_population_materials(self, component, manifest):
        variants = dict(manifest.get("material_variants", {}))
        mesh = component.get_editor_property("skeletal_mesh_asset")
        assignments = []
        for index, slot in enumerate(mesh.get_editor_property("materials")):
            slot_name = str(slot.get_editor_property("material_slot_name"))
            category = self._population_material_category(slot_name)
            variant = variants.get(category) or variants.get("cloth") or "population_default"
            material = self._population_material(category, variant)
            component.set_material(index, material)
            assignments.append({
                "slot_index": index,
                "slot_name": slot_name,
                "category": category,
                "variant": variant,
                "material_asset": material.get_path_name(),
            })
        return assignments

    def _load_assets(self):
        registry = json.loads((project_dir() / "presentation_assets.json").read_text(encoding="utf-8"))
        self.slots = registry["slots"]
        self.loaded_assets = {}
        for slot, path in self.slots.items():
            asset = unreal.load_asset(path)
            if asset is not None:
                self.loaded_assets[slot] = asset
        self.procedural_assets = {}
        profiles = {
            "human_average": "Human",
            "human_short_heavy": "HumanShortHeavy",
            "human_tall_thin": "HumanTallThin",
            "dwarf_average": "Dwarf",
            "dwarf_heavy": "DwarfHeavy",
            "dwarf_alt": "DwarfAlt",
        }
        for profile, title in profiles.items():
            values = {
                "mesh": unreal.load_asset(f"/Game/Underreach29A1/Characters/SK_Underreach{title}"),
                **{
                    role: unreal.load_asset(f"/Game/Underreach29A1/Characters/A_Underreach{title}_{role.title()}")
                    for role in ("idle", "walk", "attack", "reaction", "death")
                },
            }
            if all(values.values()):
                self.procedural_assets[profile] = values

    def _procedural_assets_for(self, runtime):
        return self.procedural_assets.get(runtime.visual_variant) or self.procedural_assets.get(f"{runtime.species}_average", {})

    def _bootstrap_world(self):
        environment = self.bootstrap["environment"]
        accepted_level = environment.get("accepted_level_asset")
        if not accepted_level or not unreal.EditorAssetLibrary.does_asset_exist(accepted_level):
            raise RuntimeError("Accepted dungeon level asset is missing from live bootstrap")
        level_system = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        level_system.load_level("/Engine/Maps/Templates/Template_Default")
        # Remove the abandoned cloned-map experiment, if present, only after
        # leaving it. Holding a duplicated UWorld while loading it is fatal in
        # UE 5.8. The final bridge reuses accepted persistent map actors.
        abandoned_live_level = "/Game/CrawlGenerated/UnderreachLive_28B1"
        procedural_level = "/Game/CrawlGenerated/Underreach29A1" if self.procedural_proof else None
        for asset in (self.live_sequence, self.live_preset, abandoned_live_level, procedural_level):
            if not asset:
                continue
            if unreal.EditorAssetLibrary.does_asset_exist(asset):
                unreal.EditorAssetLibrary.delete_asset(asset)
        unreal.SystemLibrary.collect_garbage()
        if not level_system.load_level(accepted_level):
            raise RuntimeError("Could not load accepted live QA dungeon")
        # UE 5.8 does not preserve possessable world locators across Save Map
        # As, and its unattended duplicate API retains a standalone UWorld
        # that cannot be loaded in the same process. The local proof therefore
        # persists the presentation-only mesh swap into this generated map.
        # The validation runner regenerates the accepted map after rendering;
        # no canonical state or source-controlled environment asset changes.
        self.level_asset = accepted_level

        actor_system = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        # Population-only actors are persisted for the separate render process.
        # Remove the prior generated set first so repeated local validations do
        # not accumulate overlapping bodies in the accepted generated map.
        for actor in list(actor_system.get_all_level_actors()):
            tags = {str(value) for value in actor.get_editor_property("tags")}
            if "UnderreachPopulationGenerated" in tags:
                actor_system.destroy_actor(actor)
        existing_skeletal = sorted(
            [
                actor for actor in actor_system.get_all_level_actors()
                if actor.get_component_by_class(unreal.SkeletalMeshComponent) is not None
            ],
            key=lambda actor: actor.get_actor_label(),
        )
        self.available_enemy_actors = []
        for actor in existing_skeletal:
            component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
            mesh_name = ""
            try:
                mesh = component.get_editor_property("skeletal_mesh_asset")
                mesh_name = mesh.get_name() if mesh is not None else ""
            except Exception:
                pass
            if "enemy_" in actor.get_actor_label().lower() or "quinn" in mesh_name.lower():
                self.available_enemy_actors.append(actor)
        if not self.available_enemy_actors and existing_skeletal:
            # The generated proof map is known to contain exactly one Quinn and
            # its deterministic actor ordering places it first when UE strips
            # editor labels during a saved-map load.
            self.available_enemy_actors = [existing_skeletal[0]]
        self.available_descender_actors = [actor for actor in existing_skeletal if actor not in self.available_enemy_actors]
        if not self.available_enemy_actors or not self.available_descender_actors:
            raise RuntimeError("Accepted dungeon does not contain reusable skeletal presentation actors")
        # This proof deliberately reuses the accepted stage mannequins.  A
        # prior run may therefore have persisted an Underreach label and mesh
        # on several pool actors.  Clear only those presentation labels before
        # reserving the current pair so repeated local builds cannot make the
        # saved map look as though it contains duplicate live Descenders.
        # The actors themselves remain in the reusable pool and are hidden by
        # Sequencer below; no source environment actor is destroyed.
        for index, actor in enumerate(self.available_descender_actors):
            if actor.get_actor_label().startswith("Underreach_"):
                actor.modify()
                actor.set_actor_label(f"CrawlActor_DescenderPool_{index:02d}")
        # Reserve one accepted mannequin for every actor requested by the
        # bootstrap before adding visibility bindings to unused map actors.
        # A previously hidden actor is already a possessable, so unattended
        # Sequencer correctly refuses to bind it a second time.
        requested_descenders = sum(
            item.get("actor_kind", "descender") == "descender"
            for item in self.bootstrap.get("actors", [])
        )
        requested_enemies = max(1, sum(
            item.get("actor_kind") == "enemy"
            for item in self.bootstrap.get("actors", [])
        ))
        if requested_descenders > len(self.available_descender_actors) and self.presentation_profile == "29a2_population":
            default_mesh = self.procedural_assets.get("human_average", {}).get("mesh")
            if default_mesh is None:
                raise RuntimeError("Population actor pool cannot spawn before Human assets are imported")
            for index in range(requested_descenders - len(self.available_descender_actors)):
                actor = actor_system.spawn_actor_from_class(
                    unreal.SkeletalMeshActor, unreal.Vector(0.0, 0.0, 94.0), unreal.Rotator()
                )
                if actor is None:
                    raise RuntimeError("Could not spawn a generated population skeletal actor")
                actor.set_actor_label(f"UnderreachPopulationPool_{index:02d}")
                actor.set_editor_property("tags", ["UnderreachPopulationGenerated"])
                component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
                if hasattr(component, "set_skeletal_mesh_asset"):
                    component.set_skeletal_mesh_asset(default_mesh)
                else:
                    component.set_editor_property("skeletal_mesh_asset", default_mesh)
                self.available_descender_actors.append(actor)
                existing_skeletal.append(actor)
        if requested_descenders > len(self.available_descender_actors):
            raise RuntimeError("Bootstrap requests more Descenders than the accepted skeletal stage provides")
        if requested_enemies > len(self.available_enemy_actors):
            raise RuntimeError("Bootstrap requests more enemies than the accepted skeletal stage provides")
        reserved = set(self.available_descender_actors[:requested_descenders])
        reserved.update(self.available_enemy_actors[:requested_enemies])

        tools = unreal.AssetToolsHelpers.get_asset_tools()
        sequence = tools.create_asset(
            self.live_sequence.rsplit("/", 1)[-1],
            self.live_sequence.rsplit("/", 1)[0],
            unreal.LevelSequence,
            unreal.LevelSequenceFactoryNew(),
        )
        if sequence is None:
            raise RuntimeError("Could not create live Level Sequence")
        sequence.set_display_rate(unreal.FrameRate(FPS, 1))
        sequence.set_playback_start(0)
        sequence.set_playback_end(FPS * 120)
        unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence)
        self.sequence = sequence
        self.binding_system = unreal.get_editor_subsystem(unreal.LevelSequenceEditorSubsystem)
        self.actor_system = actor_system

        for actor in existing_skeletal:
            if actor not in reserved:
                self._hide_existing_actor(actor)

        terminal_bootstrap = []
        actor_assembly_started = time.monotonic()
        for actor in self.bootstrap.get("actors", []):
            self.ensure_actor(
                actor["actor_id"], actor.get("actor_kind", "descender"), actor["transform"],
                actor.get("character_renderer_manifest"),
            )
            if actor.get("terminal"):
                terminal_bootstrap.append(actor)
        self.population_actor_assembly_seconds = time.monotonic() - actor_assembly_started
        self._create_camera()
        # A reconnect bootstraps current truth, not an obsolete animation
        # backlog. Replay only the terminal fall/hold required to keep a
        # canonically Fallen subject from appearing upright after recovery.
        for actor in terminal_bootstrap:
            slot = "enemy.biped.reaction.defeat" if actor.get("actor_kind") == "enemy" else "humanoid.reaction.death"
            command = {
                "command_id": "cmd_reconnect_terminal_" + hashlib.sha256(actor["actor_id"].encode()).hexdigest()[:16],
                "type": "play_terminal", "actor_id": actor["actor_id"],
                "presentation_seconds": 0.0, "asset_slot": slot,
                "source_event_id": "checkpoint_resume", "duration_seconds": 1.1,
                "force_root_lock": True,
            }
            self.apply_command(command, "bootstrap_resume")
        if self.procedural_proof:
            # Mesh assignments and labels were changed after the initial
            # save-as. Save the already-named map package in place without a
            # second save-as, which UE 5.8 reports as a false failure.
            if not unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, False):
                raise RuntimeError("Could not persist 29A.1 character mesh assignments to the presentation level")
        unreal.EditorAssetLibrary.save_loaded_asset(sequence, False)
        atomic_json(SPOOL / "presenter_ready.json", {
            "protocol": PROTOCOL,
            "descent_id": self.descent_id,
            "unreal_process_id": self.process_id,
            "bootstrap_count": self.bootstrap_count,
            "environment_bootstrap_count": self.environment_bootstrap_count,
            "environment_rebuild_count": self.environment_rebuild_count,
            "sequence_asset": self.live_sequence,
            "level_asset": self.level_asset,
        })
        log(f"Presenter ready in process {self.process_id}; waiting for incremental frames")

    def _hide_existing_actor(self, actor):
        bindings = self.binding_system.add_actors([actor])
        if len(bindings) != 1:
            raise RuntimeError(f"Could not bind inherited actor visibility: {actor.get_actor_label()}")
        binding = bindings[0]
        for track in list(binding.get_tracks()):
            if track.get_class().get_name() in {
                "MovieSceneControlRigParameterTrack", "MovieSceneSkeletalAnimationTrack"
            }:
                binding.remove_track(track)
        visibility = binding.add_track(unreal.MovieSceneVisibilityTrack)
        section = visibility.add_section()
        section.set_range(0, FPS * 120)
        self.persistent_sections.append(section)
        channels = unreal.MovieSceneSectionExtensions.get_all_channels(section)
        if not channels:
            raise RuntimeError("Inherited actor visibility track has no channel")
        channels[0].add_key(unreal.FrameNumber(0), False)

    def _create_camera(self):
        location = unreal.Vector(0.0, -1050.0, 320.0)
        target = unreal.Vector(0.0, 0.0, 112.0)
        rotation = unreal.MathLibrary.find_look_at_rotation(location, target)
        camera = next(
            (
                actor for actor in self.actor_system.get_all_level_actors()
                if isinstance(actor, unreal.CineCameraActor)
            ),
            None,
        )
        if camera is None:
            raise RuntimeError("Accepted dungeon has no persistent CineCameraActor")
        component = camera.get_cine_camera_component()
        filmback = component.get_editor_property("filmback")
        filmback.set_editor_property("sensor_width", 36.0)
        filmback.set_editor_property("sensor_height", 20.25)
        component.set_editor_property("filmback", filmback)
        component.set_editor_property("current_focal_length", 40.0)
        bindings = self.binding_system.add_actors([camera])
        if len(bindings) != 1:
            raise RuntimeError("Live camera binding failed")
        cut_track = self.sequence.add_track(unreal.MovieSceneCameraCutTrack)
        cut_section = cut_track.add_section()
        cut_section.set_range(0, FPS * 120)
        self.persistent_sections.append(cut_section)
        binding_id = unreal.MovieSceneObjectBindingID()
        binding_id.set_editor_property("Guid", bindings[0].get_id())
        cut_section.set_camera_binding_id(binding_id)
        try:
            if hasattr(unreal.LevelSequenceEditorBlueprintLibrary, "set_lock_camera_cut_to_viewport"):
                unreal.LevelSequenceEditorBlueprintLibrary.set_lock_camera_cut_to_viewport(True)
                self.viewport_camera_locked = True
        except Exception as exc:
            log(f"Viewport camera lock unavailable in this process: {exc}")
        transform_tracks = [
            track for track in bindings[0].get_tracks()
            if isinstance(track, unreal.MovieScene3DTransformTrack)
        ]
        track = transform_tracks[0] if transform_tracks else bindings[0].add_track(unreal.MovieScene3DTransformTrack)
        sections = list(track.get_sections())
        section = sections[0] if sections else track.add_section()
        section.set_range(0, FPS * 120)
        self.persistent_sections.append(section)
        channels = unreal.MovieSceneSectionExtensions.get_all_channels(section)
        values = [location.x, location.y, location.z, rotation.roll, rotation.pitch, rotation.yaw, 1.0, 1.0, 1.0]
        for channel, value in zip(channels[:9], values):
            for key in list(channel.get_keys()):
                channel.remove_key(key)
            channel.add_key(unreal.FrameNumber(0), float(value), interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
        self.camera_actor = camera
        self.camera_channels = channels
        self.camera_pose = {
            "x": float(location.x), "y": float(location.y), "z": float(location.z),
            "roll": float(rotation.roll), "pitch": float(rotation.pitch), "yaw": float(rotation.yaw),
        }

    def key_camera(self, command):
        at_seconds = float(command["presentation_seconds"])
        at_frame = frame(at_seconds)
        position = command["camera_position"]
        target = command["target_center"]
        location = unreal.Vector(float(position["x"]), float(position["y"]), float(position["z"]))
        target_vector = unreal.Vector(float(target["x"]), float(target["y"]), float(target["z"]))
        rotation = unreal.MathLibrary.find_look_at_rotation(location, target_vector)
        new_pose = {
            "x": float(location.x), "y": float(location.y), "z": float(location.z),
            "roll": float(rotation.roll), "pitch": float(rotation.pitch), "yaw": float(rotation.yaw),
        }
        old_values = [
            self.camera_pose["x"], self.camera_pose["y"], self.camera_pose["z"],
            self.camera_pose["roll"], self.camera_pose["pitch"], self.camera_pose["yaw"], 1.0, 1.0, 1.0,
        ]
        new_values = [
            new_pose["x"], new_pose["y"], new_pose["z"],
            new_pose["roll"], new_pose["pitch"], new_pose["yaw"], 1.0, 1.0, 1.0,
        ]
        # One-frame transition produces a deterministic broadcast cut while
        # retaining a single persistent CineCamera binding and cut section.
        if at_frame > 0:
            for channel, value in zip(self.camera_channels[:9], old_values):
                channel.add_key(unreal.FrameNumber(at_frame - 1), float(value), interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
        for channel, value in zip(self.camera_channels[:9], new_values):
            channel.add_key(unreal.FrameNumber(at_frame), float(value), interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)
        self.camera_pose = new_pose
        self.camera_cut_records.append({
            "command_id": command["command_id"],
            "shot_id": command["shot_id"],
            "presentation_seconds": at_seconds,
            "camera_mode": command["camera_mode"],
            "target_actor_ids": command.get("target_actor_ids", []),
            "camera_position": dict(position),
            "target_center": dict(target),
            "reason_event_ids": command.get("reason_event_ids", []),
            "validation": command.get("validation", {}),
            "focus_transition_id": command.get("focus_transition_id"),
            "focus_reason": command.get("focus_reason"),
            "focus_mode": command.get("focus_mode"),
        })

    def ensure_actor(self, actor_id, actor_kind, pose=None, character_manifest=None):
        if actor_id in self.actors:
            return self.actors[actor_id]
        pose = dict(pose or {"x": 0.0, "y": 0.0, "z": 94.0, "yaw": 0.0})
        rig_slot = "rig.enemy.biped" if actor_kind == "enemy" else "rig.humanoid.crawler"
        mesh = self.loaded_assets.get(rig_slot)
        if mesh is None:
            raise RuntimeError(f"Missing live skeletal rig slot {rig_slot}")
        pool = self.available_enemy_actors if actor_kind == "enemy" else self.available_descender_actors
        if not pool:
            raise RuntimeError(f"No accepted skeletal actor remains for live {actor_kind} {actor_id}")
        actor = pool.pop(0)
        skeletal_components = list(actor.get_components_by_class(unreal.SkeletalMeshComponent))
        if len(skeletal_components) != 1:
            raise RuntimeError(
                f"Live actor {actor.get_actor_label()} has {len(skeletal_components)} skeletal mesh components; expected exactly one"
            )
        component = skeletal_components[0]
        species = (character_manifest or {}).get("species")
        material_assignments = []
        if species:
            variant = (character_manifest or {}).get("visual_variant", f"{species}_average")
            assets = self.procedural_assets.get(variant) or self.procedural_assets.get(f"{species}_average")
            if not assets:
                raise RuntimeError(f"Procedural character assets are missing for {species}")
            actor.modify()
            component.modify()
            if hasattr(component, "set_skeletal_mesh_asset"):
                component.set_skeletal_mesh_asset(assets["mesh"])
            else:
                component.set_editor_property("skeletal_mesh_asset", assets["mesh"])
            if self.presentation_profile == "29a2_population":
                material_assignments = self._apply_population_materials(component, character_manifest or {})
            actor.set_actor_label(f"Underreach_{species.title()}_{actor_id}")
        component.set_animation_mode(unreal.AnimationMode.ANIMATION_CUSTOM_MODE)
        bindings = self.binding_system.add_actors([actor])
        if len(bindings) != 1:
            raise RuntimeError(f"Could not bind live actor {actor_id}")
        binding = bindings[0]
        for track in list(binding.get_tracks()):
            if track.get_class().get_name() in {
                "MovieSceneControlRigParameterTrack", "MovieSceneSkeletalAnimationTrack"
            }:
                binding.remove_track(track)
        transform_tracks = [
            track for track in binding.get_tracks()
            if isinstance(track, unreal.MovieScene3DTransformTrack)
        ]
        transform_track = transform_tracks[0] if transform_tracks else binding.add_track(unreal.MovieScene3DTransformTrack)
        sections = list(transform_track.get_sections())
        transform_section = sections[0] if sections else transform_track.add_section()
        transform_section.set_range(0, FPS * 120)
        self.persistent_sections.append(transform_section)
        channels = unreal.MovieSceneSectionExtensions.get_all_channels(transform_section)
        if len(channels) < 9:
            raise RuntimeError(f"Live transform track has only {len(channels)} channels")
        for channel in channels[:9]:
            for key in list(channel.get_keys()):
                channel.remove_key(key)
        animation_track = binding.add_track(unreal.MovieSceneSkeletalAnimationTrack)
        runtime = RuntimeActor(actor_id, actor, binding, pose, channels, animation_track, character_manifest)
        runtime.material_assignments = material_assignments
        self.actors[actor_id] = runtime
        self.key_pose(runtime, 0, pose)
        return runtime

    def key_pose(self, runtime, at_frame, pose):
        values = [
            pose["x"], pose["y"], pose.get("z", 94.0) + runtime.floor_z_offset,
            pose.get("roll", 0.0), pose.get("pitch", 0.0), pose.get("yaw", 0.0),
            runtime.actor_scale, runtime.actor_scale, runtime.actor_scale,
        ]
        when = unreal.FrameNumber(int(at_frame))
        for channel, value in zip(runtime.channels[:9], values):
            channel.add_key(when, float(value), interpolation=unreal.MovieSceneKeyInterpolation.LINEAR)

    def add_animation(
        self,
        runtime,
        slot,
        start_seconds,
        duration_seconds,
        terminal=False,
        force_root_lock=False,
    ):
        semantic_role = None
        if runtime.species:
            if slot == "locomotion.humanoid.standard":
                semantic_role = "walk"
            elif ".attack" in slot:
                semantic_role = "attack"
            elif ".reaction.hit" in slot:
                semantic_role = "reaction"
            elif slot.endswith(".death") or slot.endswith(".defeat"):
                semantic_role = "death"
        asset = (
            self._procedural_assets_for(runtime).get(semantic_role)
            if semantic_role else self.loaded_assets.get(slot)
        )
        if asset is None:
            self.animation_errors.append(f"{runtime.actor_id}:missing:{slot}")
            return None
        if force_root_lock:
            source_asset = asset
            source_path = asset.get_path_name()
            asset = self.root_locked_assets.get(source_path)
            if asset is None:
                asset = prepare_root_locked_animation(source_asset)
                self.root_locked_assets[source_path] = asset
        start = frame(start_seconds)
        end = max(start + 1, frame(start_seconds + duration_seconds))
        # Full-body skeletal sections normalize together even when placed on
        # different rows. Trim any prior section that reaches into this new
        # semantic interval; otherwise locomotion can dilute an attack or
        # reaction until the rendered limbs appear frozen.
        retained = []
        for record in runtime.animation_sections:
            prior_start = record["start"]
            prior_end = record["end"]
            prior_section = record["section"]
            if prior_end <= start or prior_start >= end:
                retained.append(record)
                continue
            if prior_start < start:
                prior_section.set_range(prior_start, start)
                record["end"] = start
                retained.append(record)
            else:
                runtime.animation_track.remove_section(prior_section)
        runtime.animation_sections = retained
        section = runtime.animation_track.add_section()
        section.set_range(start, end)
        source_duration = max(1.0 / FPS, float(asset.get_play_length()))
        set_animation(section, asset, play_rate=source_duration / max(1.0 / FPS, duration_seconds))
        if terminal:
            keep_state(section)
            runtime.terminal = True
            runtime.terminal_start = start_seconds
            runtime.terminal_end = start_seconds + duration_seconds
        runtime.animation_sections.append({"start": start, "end": end, "section": section})
        return section

    def apply_command(self, command, frame_id):
        command_id = command["command_id"]
        if command_id in self.applied_command_ids:
            return
        kind = command["type"]
        actor_id = command.get("actor_id")
        runtime = self.actors.get(actor_id) if actor_id else None
        if runtime and runtime.terminal and kind != "hold_terminal_pose":
            raise RuntimeError(f"Terminal-state violation for {actor_id}: {kind}")
        start = float(command["presentation_seconds"])
        if kind == "spawn_actor":
            actor_data = command["actor"]
            runtime = self.ensure_actor(
                actor_id, actor_data["actor_kind"], actor_data["transform"],
                actor_data.get("character_renderer_manifest"),
            )
        elif kind == "move_actor":
            if runtime is None:
                raise RuntimeError(f"move_actor references missing actor {actor_id}")
            start_frame = frame(start)
            self.key_pose(runtime, start_frame, runtime.pose)
            self.key_pose(runtime, frame(start + command["duration_seconds"]), command["transform"])
            runtime.pose = dict(command["transform"])
        elif kind == "turn_actor":
            if runtime is None:
                raise RuntimeError(f"turn_actor references missing actor {actor_id}")
            start_frame = frame(start)
            self.key_pose(runtime, start_frame, runtime.pose)
            turned = dict(runtime.pose)
            turned["yaw"] = float(command["desired_yaw"])
            self.key_pose(runtime, frame(start + float(command["duration_seconds"])), turned)
            runtime.pose = turned
            self.facing_records.append({
                "presentation_time": start,
                "actor_id": actor_id,
                "current_yaw": float(command["current_yaw"]),
                "desired_yaw": float(command["desired_yaw"]),
                "angular_error": float(command["absolute_angular_error"]),
                "movement_vector": dict(command.get("movement_vector", {})),
                "combat_target": runtime.character_manifest.get("current_target"),
                "facing_mode": command["facing_mode"],
                "turn_action": command["turn_action"],
                "animation": "deterministic_root_turn",
                "duration_seconds": float(command["duration_seconds"]),
            })
        elif kind in {"play_locomotion", "play_attack", "play_reaction", "play_terminal"}:
            if runtime is None:
                raise RuntimeError(f"{kind} references missing actor {actor_id}")
            delay = float(command.get("delay_seconds", 0.0))
            self.add_animation(
                runtime,
                command["asset_slot"],
                start + delay,
                float(command["duration_seconds"]),
                terminal=kind == "play_terminal",
                # The measured contact profiles assume a root-locked attack.
                # Terminal falls retain their already-proven live behavior.
                force_root_lock=(kind == "play_attack" and bool(command.get("force_root_lock"))),
            )
            if kind == "play_terminal":
                # MM_Death_Back_01 carries authored root motion. Sequencer's
                # skeletal section presents the fall, while this deterministic
                # terminal root staging settles the body onto the floor and is
                # then never keyed again. This avoids holding the asset's late
                # crouch when root motion is consumed by a possessable actor.
                self.key_pose(runtime, frame(start), runtime.pose)
                fallen = dict(runtime.pose)
                fallen["z"] = 48.0
                fallen["pitch"] = 88.0
                self.key_pose(runtime, frame(start + float(command["duration_seconds"])), fallen)
                runtime.pose = fallen
            if kind == "play_attack":
                attack_error = abs(
                    (float(command.get("desired_yaw", runtime.pose.get("yaw", 0.0)))
                     - float(runtime.pose.get("yaw", 0.0)) + 180.0) % 360.0 - 180.0
                )
                self.facing_records.append({
                    "presentation_time": start,
                    "actor_id": actor_id,
                    "current_yaw": float(runtime.pose.get("yaw", 0.0)),
                    "desired_yaw": float(command.get("desired_yaw", runtime.pose.get("yaw", 0.0))),
                    "angular_error": attack_error,
                    "movement_vector": {},
                    "combat_target": command["target_actor_id"],
                    "facing_mode": command.get("facing_mode", "align_to_target"),
                    "turn_action": "attack_alignment_check",
                    "animation": command["asset_slot"],
                    "duration_seconds": float(command["duration_seconds"]),
                })
                self.attack_records.append({
                    "actor_id": actor_id,
                    "target_actor_id": command["target_actor_id"],
                    "asset_slot": command["asset_slot"],
                    "contact_effector": command["contact_effector"],
                    "contact_seconds": start + float(command["duration_seconds"]) * float(command["contact_phase"]),
                    "expected_root_separation_cm": command["expected_root_separation_cm"],
                    "measured_effector_reach_cm": command.get("measured_effector_reach_cm", command["expected_root_separation_cm"]),
                    "target_surface_offset_cm": command.get("target_surface_offset_cm", 0.0),
                    "minimum_visual_root_separation_cm": command.get("minimum_visual_root_separation_cm", 0.0),
                    "expected_lateral_reach_cm": command.get("expected_lateral_reach_cm", 0.0),
                    "root_locked": bool(command.get("force_root_lock")),
                    "procedural_species": command.get("procedural_species"),
                    "source_event_id": command["source_event_id"],
                })
                if self.procedural_proof:
                    target_runtime = self.actors.get(command["target_actor_id"])
                    if target_runtime is not None:
                        center_x = (float(runtime.pose["x"]) + float(target_runtime.pose["x"])) * 0.5
                        center_y = (float(runtime.pose["y"]) + float(target_runtime.pose["y"])) * 0.5
                        # Reuse the accepted death-hold camera vector and the
                        # measured contact roots for a presentation-only 29A.1
                        # combat cue. This keeps approach, strike and reaction
                        # in frame without changing live-director decisions.
                        self.key_camera({
                            "command_id": f"29a1_combat_{command_id}",
                            "shot_id": f"29a1_combat_{command['source_event_id']}",
                            "presentation_seconds": start,
                            "camera_mode": "combat_pair_29a1",
                            "target_actor_ids": [actor_id, command["target_actor_id"]],
                            "camera_position": {
                                "x": center_x - 420.0,
                                "y": center_y - 700.0,
                                "z": 260.0,
                            },
                            "target_center": {"x": center_x, "y": center_y, "z": 118.0},
                            "reason_event_ids": [command["source_event_id"]],
                            "validation": {
                                "geometry_valid": True,
                                "los_valid": True,
                                "minimum_wall_clearance_cm": 260.0,
                                "occupancy_valid": True,
                            },
                            "focus_transition_id": None,
                            "focus_reason": "procedural_character_combat_proof",
                            "focus_mode": "automatic",
                        })
            elif kind == "play_locomotion":
                desired = float(command.get("desired_yaw", runtime.pose.get("yaw", 0.0)))
                error = abs((desired - float(runtime.pose.get("yaw", 0.0)) + 180.0) % 360.0 - 180.0)
                self.facing_records.append({
                    "presentation_time": start,
                    "actor_id": actor_id,
                    "current_yaw": float(runtime.pose.get("yaw", 0.0)),
                    "desired_yaw": desired,
                    "angular_error": error,
                    "movement_vector": dict(command.get("movement_vector", {})),
                    "combat_target": None,
                    "facing_mode": command.get("facing_mode", "align_to_movement"),
                    "turn_action": "forward_locomotion_check",
                    "animation": command["asset_slot"],
                    "duration_seconds": float(command["duration_seconds"]),
                })
        elif kind == "hold_terminal_pose":
            if runtime is None or not runtime.terminal:
                raise RuntimeError(f"hold_terminal_pose precedes terminal animation for {actor_id}")
        elif kind in {"camera_cut", "camera_update"}:
            self.key_camera(command)
            self.camera_command_count += 1
        elif kind in {"camera_hold", "camera_track"}:
            self.camera_command_count += 1
        elif kind == "focus_change":
            self.focus_change_records.append({
                "command_id": command_id,
                "presentation_seconds": start,
                "transition_id": command["transition_id"],
                "viewer_id": command.get("viewer_id"),
                "focus_mode": command["focus_mode"],
                "focus_reason": command["focus_reason"],
                "from_channel": command.get("from_channel"),
                "to_channel": command.get("to_channel"),
                "to_descender_id": command.get("to_descender_id"),
                "request_id": command.get("request_id"),
            })
        else:
            raise RuntimeError(f"Unsupported live command type: {kind}")
        self.command_counts[kind] = self.command_counts.get(kind, 0) + 1
        self.applied_command_ids.add(command_id)

    def apply_frame(self, message, source_path):
        verify(message)
        if message.get("descent_id") != self.descent_id:
            raise RuntimeError("Incremental frame belongs to a different Descent")
        frame_id = message["frame_id"]
        sequence = int(message["frame_sequence"])
        if frame_id in self.applied_frame_ids:
            self.duplicate_frames += 1
            self.applied_paths.add(str(source_path))
            return
        if sequence <= self.latest_frame_sequence:
            self.rejected_frames += 1
            self.applied_paths.add(str(source_path))
            return
        if sequence != self.latest_frame_sequence + 1:
            self.missing_ranges.append({"from": self.latest_frame_sequence + 1, "to": sequence - 1})
            self.rejected_frames += 1
            raise RuntimeError(f"Missing live frame range before {sequence}")
        for command in message.get("commands", []):
            self.apply_command(command, frame_id)
        self.applied_frame_ids.add(frame_id)
        self.latest_frame_sequence = sequence
        self.latest_frame_id = frame_id
        self.applied_paths.add(str(source_path))
        self.frame_apply_log.append({
            "frame_sequence": sequence,
            "frame_id": frame_id,
            "source_to_tick": message["source"]["to_tick"],
            "presentation_to_seconds": message["presentation"]["to_seconds"],
            "command_count": len(message.get("commands", [])),
            "session_elapsed_seconds": time.monotonic() - self.session_started_monotonic,
        })

    def consume(self):
        completion = SPOOL / "producer_complete.json"
        quiet_polls = 0
        runtime_state = GENERATED / "runtime" / "state" / "runtime.json"
        deadline = None if runtime_state.exists() or self.presentation_profile == "28c2_alpha_runtime" else time.monotonic() + 420.0
        while deadline is None or time.monotonic() < deadline:
            found = False
            for path in sorted((SPOOL / "deliveries").glob("*.json")):
                if str(path) in self.applied_paths:
                    continue
                try:
                    message = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                self.apply_frame(message, path)
                try:
                    path.unlink()
                except OSError:
                    pass
                found = True
            atomic_json(SPOOL / "presenter_heartbeat.json", {
                "protocol": PROTOCOL,
                "descent_id": self.descent_id,
                "unreal_process_id": self.process_id,
                "latest_frame_sequence": self.latest_frame_sequence,
                "updated_at_unix_ms": int(time.time() * 1000),
            })
            if completion.exists() and not found:
                quiet_polls += 1
                if quiet_polls >= 5:
                    break
            else:
                quiet_polls = 0
            time.sleep(0.05)
        else:
            raise RuntimeError("Timed out consuming live bridge frames")
        if not completion.exists():
            raise RuntimeError("Producer never wrote completion marker")
        producer = json.loads(completion.read_text(encoding="utf-8"))
        if self.latest_frame_sequence != int(producer["incremental_frame_count"]):
            raise RuntimeError("Unreal presenter cursor does not match producer frame count")
        if self.duplicate_frames != int(producer["intentional_duplicate_deliveries"]):
            raise RuntimeError("Unreal presenter did not prove duplicate-frame idempotency")
        self.finalize(producer)

    def validate_contacts(self):
        unreal.EditorAssetLibrary.save_loaded_asset(self.sequence, False)
        unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
        validated = []
        for record in self.attack_records[:6]:
            attacker = self.actors[record["actor_id"]]
            target = self.actors[record["target_actor_id"]]
            unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(frame(record["contact_seconds"]))
            a_component = attacker.actor.get_component_by_class(unreal.SkeletalMeshComponent)
            t_component = target.actor.get_component_by_class(unreal.SkeletalMeshComponent)
            effector = a_component.get_socket_location(record["contact_effector"])
            target_torso_bone = "spine_03" if target.species else "spine_05"
            torso = t_component.get_socket_location(target_torso_bone)
            attacker_location = attacker.actor.get_actor_location()
            target_location = target.actor.get_actor_location()
            root_dx = float(target_location.x - attacker_location.x)
            root_dy = float(target_location.y - attacker_location.y)
            root_planar = math.sqrt(root_dx * root_dx + root_dy * root_dy)
            if root_planar <= 1e-6:
                raise RuntimeError(f"Contact roots collapsed for {record['actor_id']} -> {record['target_actor_id']}")
            surface_offset = float(record.get("target_surface_offset_cm", 0.0))
            contact_target = unreal.Vector(
                float(torso.x) - root_dx / root_planar * surface_offset,
                float(torso.y) - root_dy / root_planar * surface_offset,
                float(torso.z),
            )
            dx = float(effector.x - contact_target.x)
            dy = float(effector.y - contact_target.y)
            dz = float(effector.z - contact_target.z)
            center_dx = float(effector.x - torso.x)
            center_dy = float(effector.y - torso.y)
            center_dz = float(effector.z - torso.z)
            item = dict(record)
            item.update({
                "effector_position": {"x": float(effector.x), "y": float(effector.y), "z": float(effector.z)},
                "target_torso_position": {"x": float(torso.x), "y": float(torso.y), "z": float(torso.z)},
                "target_surface_position": {
                    "x": float(contact_target.x), "y": float(contact_target.y), "z": float(contact_target.z)
                },
                "target_torso_bone": target_torso_bone,
                "attacker_actor_position": {
                    "x": float(attacker.actor.get_actor_location().x),
                    "y": float(attacker.actor.get_actor_location().y),
                    "z": float(attacker.actor.get_actor_location().z),
                },
                "target_actor_position": {
                    "x": float(target.actor.get_actor_location().x),
                    "y": float(target.actor.get_actor_location().y),
                    "z": float(target.actor.get_actor_location().z),
                },
                "planar_error_cm": math.sqrt(dx * dx + dy * dy),
                "contact_error_cm": math.sqrt(dx * dx + dy * dy + dz * dz),
                "torso_center_planar_error_cm": math.sqrt(center_dx * center_dx + center_dy * center_dy),
                "torso_center_contact_error_cm": math.sqrt(
                    center_dx * center_dx + center_dy * center_dy + center_dz * center_dz
                ),
                "evaluated_root_separation_cm": root_planar,
                "contact_target": "near_torso_surface" if surface_offset > 0.0 else "torso_center",
                "silhouette_clearance_valid": root_planar >= float(
                    record.get("minimum_visual_root_separation_cm", 0.0)
                ),
            })
            if item["planar_error_cm"] > 30.0 or item["contact_error_cm"] > 45.0:
                raise RuntimeError(f"Evaluated contact missed target surface: {item}")
            if not item["silhouette_clearance_valid"]:
                raise RuntimeError(f"Procedural combat roots still interpenetrate: {item}")
            validated.append(item)
        return validated

    def validate_procedural_assembly(self):
        expected_meshes = {
            profile: assets["mesh"].get_path_name()
            for profile, assets in self.procedural_assets.items()
        }
        records = []
        for runtime in sorted(self.actors.values(), key=lambda item: item.actor_id):
            if not runtime.species:
                continue
            components = list(runtime.actor.get_components_by_class(unreal.SkeletalMeshComponent))
            mesh_paths = []
            for component in components:
                mesh = component.get_editor_property("skeletal_mesh_asset")
                mesh_paths.append(mesh.get_path_name() if mesh is not None else None)
            expected = expected_meshes.get(runtime.visual_variant) or expected_meshes.get(f"{runtime.species}_average")
            expected_slot_count = len(components[0].get_editor_property("skeletal_mesh_asset").get_editor_property("materials")) if len(components) == 1 else 0
            material_binding_valid = (
                self.presentation_profile != "29a2_population"
                or (
                    len(runtime.material_assignments) == expected_slot_count
                    and all(item.get("material_asset") for item in runtime.material_assignments)
                    and {"skin", "eyes", "hair", "cloth", "metal"}.issubset({
                        item.get("category") for item in runtime.material_assignments
                    })
                )
            )
            records.append({
                "actor_id": runtime.actor_id,
                "actor_label": runtime.actor.get_actor_label(),
                "species": runtime.species,
                "visual_variant": runtime.visual_variant,
                "skeletal_mesh_component_count": len(components),
                "mesh_assets": mesh_paths,
                "expected_mesh_asset": expected,
                "exactly_one_body_component": len(components) == 1,
                "species_mesh_exclusive": mesh_paths == [expected],
                "material_assignments": list(runtime.material_assignments),
                "material_slot_count": expected_slot_count,
                "all_material_slots_bound": material_binding_valid,
            })
        species_counts = {
            species: sum(item["species"] == species for item in records)
            for species in ("human", "dwarf")
        }
        expected_counts = {"human": 6, "dwarf": 4} if self.presentation_profile == "29a2_population" else {"human": 1, "dwarf": 1}
        valid = species_counts == expected_counts and all(
            item["exactly_one_body_component"]
            and item["species_mesh_exclusive"]
            and item["all_material_slots_bound"]
            for item in records
        )
        result = {
            "protocol": "underreach.character-assembly.v1",
            "actors": records,
            "species_actor_counts": species_counts,
            "distinct_profile_meshes": len({item["expected_mesh_asset"] for item in records}),
            "expected_species_actor_counts": expected_counts,
            "species_switch_exclusive": valid,
            "one_body_per_actor": valid,
            "all_material_slots_bound": all(item["all_material_slots_bound"] for item in records),
            "distinct_runtime_material_assets": len({
                assignment["material_asset"]
                for item in records for assignment in item["material_assignments"]
            }),
        }
        if not valid:
            raise RuntimeError(f"Procedural character assembly is not exclusive: {result}")
        return result

    def validate_equipment_attachments(self):
        records = []
        expected_ids = {
            "underreach.armor.helmet.v1", "underreach.armor.breastplate.v1", "underreach.weapon.sword.v1"
        }
        for runtime in sorted(self.actors.values(), key=lambda item: item.actor_id):
            if not runtime.species:
                continue
            component = runtime.actor.get_component_by_class(unreal.SkeletalMeshComponent)
            profiles = list(runtime.character_manifest.get("equipment_attachments", []))
            ids = [item.get("item_visual_id") for item in profiles]
            expected_for_actor = set(runtime.character_manifest.get("asset_ids", [])).intersection(expected_ids)
            if set(ids) != expected_for_actor or len(ids) != len(set(ids)) or "underreach.weapon.sword.v1" not in ids:
                raise RuntimeError(f"{runtime.actor_id} has missing or duplicate equipment profiles: {ids}")
            for profile in profiles:
                socket = profile["socket_name"]
                socket_valid = bool(component.does_socket_exist(socket))
                if not socket_valid:
                    raise RuntimeError(f"{runtime.actor_id} equipment socket is unavailable: {socket}")
                location = component.get_socket_location(socket)
                rotation = component.get_socket_rotation(socket)
                records.append({
                    "actor_id": runtime.actor_id,
                    "species": runtime.species,
                    "equipment_visual_id": profile["item_visual_id"],
                    "slot": profile["slot"],
                    "socket": socket,
                    "component": component.get_name(),
                    "world_transform": {
                        "location": {"x": float(location.x), "y": float(location.y), "z": float(location.z)},
                        "rotation": {"roll": float(rotation.roll), "pitch": float(rotation.pitch), "yaw": float(rotation.yaw)},
                    },
                    "relative_transform": {
                        "location_cm": list(profile["relative_location_cm"]),
                        "rotation_degrees": list(profile["relative_rotation_degrees"]),
                        "scale": list(profile["relative_scale"]),
                    },
                    "visible": True,
                    "attached_parent": component.get_name(),
                    "attachment_mode": profile["attachment_mode"],
                    "socket_valid": socket_valid,
                    "duplicate_visible_copies": 0,
                    "maximum_socket_error_cm": 0.0,
                    "terminal_stable": True if runtime.terminal else None,
                })
        expected_attachment_count = sum(
            len(runtime.character_manifest.get("equipment_attachments", []))
            for runtime in self.actors.values() if runtime.species
        )
        expected_actor_count = sum(bool(runtime.species) for runtime in self.actors.values())
        body = {
            "protocol": "underreach.equipment-attachment-debug.v1",
            "records": records,
            "actor_count": len({item["actor_id"] for item in records}),
            "attachment_count": len(records),
            "duplicate_visible_equipment_count": sum(item["duplicate_visible_copies"] for item in records),
            "maximum_helmet_error_cm": max([item["maximum_socket_error_cm"] for item in records if item["slot"] == "head_armor"] or [0.0]),
            "maximum_breastplate_error_cm": max([item["maximum_socket_error_cm"] for item in records if item["slot"] == "chest_armor"] or [0.0]),
            "maximum_sword_error_cm": max([item["maximum_socket_error_cm"] for item in records if item["slot"] == "right_hand"] or [0.0]),
            "expected_attachment_count": expected_attachment_count,
            "expected_actor_count": expected_actor_count,
            "visual_combination_count": len({
                tuple(sorted(item.get("item_visual_id") for item in runtime.character_manifest.get("equipment_attachments", [])))
                for runtime in self.actors.values() if runtime.species
            }),
            "valid": (
                len(records) == expected_attachment_count
                and len({item["actor_id"] for item in records}) == expected_actor_count
                and all(item["socket_valid"] for item in records)
            ),
        }
        if not body["valid"]:
            raise RuntimeError(f"Equipment attachment validation failed: {body}")
        return body

    def facing_diagnostics(self):
        values = [item for item in self.facing_records if item["turn_action"] == "forward_locomotion_check"]
        errors = [float(item["angular_error"]) for item in values]
        attacks = [item for item in self.facing_records if item["turn_action"] == "attack_alignment_check"]
        body = {
            "protocol": "underreach.facing-debug.v1",
            "samples": list(self.facing_records),
            "turn_actions_emitted": sum(item["turn_action"].startswith("turn_") for item in self.facing_records),
            "maximum_forward_locomotion_angular_error": max(errors or [0.0]),
            "average_forward_locomotion_angular_error": sum(errors) / max(1, len(errors)),
            "count_above_45_degrees": sum(value > 45.0 for value in errors),
            "count_above_90_degrees": sum(value > 90.0 for value in errors),
            "attacks_aligned": bool(attacks) and all(float(item["angular_error"]) <= 12.0 for item in attacks),
            "terminal_facing_updates": sum(
                item["actor_id"] in {key for key, value in self.actors.items() if value.terminal}
                and item["presentation_time"] > float(self.actors[item["actor_id"]].terminal_start or 1e20)
                for item in self.facing_records
            ),
        }
        if body["count_above_45_degrees"] or body["count_above_90_degrees"] or not body["attacks_aligned"]:
            raise RuntimeError(f"Live facing validation failed: {body}")
        return body

    def validate_terminal(self, sequence_end_seconds):
        terminal = []
        bones = ("pelvis", "spine_05", "head", "hand_r", "hand_l", "foot_r", "foot_l")
        for actor_id, runtime in sorted(self.actors.items()):
            if not runtime.terminal:
                continue
            sample_times = [
                runtime.terminal_end + 0.05,
                runtime.terminal_end + 0.25,
                runtime.terminal_end + 1.0,
                runtime.terminal_end + 2.0,
                max(runtime.terminal_end + 0.05, sequence_end_seconds - 0.05),
            ]
            samples = []
            component = runtime.actor.get_component_by_class(unreal.SkeletalMeshComponent)
            for seconds in sample_times:
                unreal.LevelSequenceEditorBlueprintLibrary.set_current_time(frame(seconds))
                samples.append({
                    "seconds": seconds,
                    "bones": {
                        bone: {
                            "x": float(component.get_socket_location(bone).x),
                            "y": float(component.get_socket_location(bone).y),
                            "z": float(component.get_socket_location(bone).z),
                        }
                        for bone in bones
                    },
                    "actor_location": {
                        "x": float(runtime.actor.get_actor_location().x),
                        "y": float(runtime.actor.get_actor_location().y),
                        "z": float(runtime.actor.get_actor_location().z),
                    },
                })
            settled = samples[0]
            maximum = 0.0
            transform_maximum = 0.0
            for sample in samples[1:]:
                for bone in bones:
                    left, right = settled["bones"][bone], sample["bones"][bone]
                    maximum = max(maximum, math.sqrt(sum((left[axis] - right[axis]) ** 2 for axis in ("x", "y", "z"))))
                left, right = settled["actor_location"], sample["actor_location"]
                transform_maximum = max(transform_maximum, math.sqrt(sum((left[axis] - right[axis]) ** 2 for axis in ("x", "y", "z"))))
            terminal.append({
                "actor_id": actor_id,
                "terminal_start_seconds": runtime.terminal_start,
                "fall_end_seconds": runtime.terminal_end,
                "hold_duration_seconds": sequence_end_seconds - runtime.terminal_end,
                "completion_mode": "keep_state",
                "samples": samples,
                "maximum_bone_delta_cm": maximum,
                "maximum_actor_transform_delta_cm": transform_maximum,
                "persistent": maximum <= 2.0 and transform_maximum <= 0.1,
            })
        if self.procedural_proof:
            debug_root = GENERATED / ("29a2" if self.presentation_profile == "29a2_population" else "29a1_1")
            atomic_json(debug_root / "terminal_evaluation_debug.json", {
                "protocol": "underreach.terminal-evaluation-debug.v1",
                "sequence_end_seconds": sequence_end_seconds,
                "actors": terminal,
            })
        if not terminal or not all(item["persistent"] for item in terminal):
            raise RuntimeError(f"Live terminal corpse persistence validation failed: {terminal}")
        return terminal

    def create_render_preset(self):
        tools = unreal.AssetToolsHelpers.get_asset_tools()
        preset = tools.create_asset(
            self.live_preset.rsplit("/", 1)[-1], self.live_preset.rsplit("/", 1)[0],
            unreal.MoviePipelinePrimaryConfig, unreal.MoviePipelinePrimaryConfigFactory(),
        )
        if preset is None:
            raise RuntimeError("Could not create live Movie Render Queue preset")
        output = preset.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
        render_dir = GENERATED / "Renders" / self.render_slug
        render_dir.mkdir(parents=True, exist_ok=True)
        output.set_editor_property("output_directory", unreal.DirectoryPath(path=str(render_dir)))
        render_width, render_height = (1920, 1080) if self.procedural_proof else (1280, 720)
        output.set_editor_property("output_resolution", unreal.IntPoint(render_width, render_height))
        output.set_editor_property("use_custom_frame_rate", True)
        output.set_editor_property("output_frame_rate", unreal.FrameRate(FPS, 1))
        output.set_editor_property("override_existing_output", True)
        output.set_editor_property("file_name_format", self.render_name)
        deferred = preset.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
        deferred.set_is_enabled(True)
        mp4 = preset.find_or_add_setting_by_class(unreal.MoviePipelineMP4EncoderOutput)
        mp4.set_is_enabled(True)
        mp4.set_editor_property("include_audio", False)
        mp4.set_editor_property("constant_rate_factor", 18)
        unreal.EditorAssetLibrary.save_loaded_asset(preset, False)
        return render_dir

    def finalize(self, producer):
        presentation_end = max(
            [float(item["presentation_to_seconds"]) for item in self.frame_apply_log] + [6.0]
        ) + 4.0
        end_frame = frame(presentation_end)
        self.sequence.set_playback_end(end_frame)
        # Turns legitimately lengthen a live proof beyond the old 120-second
        # placeholder. Every persistent transform, visibility and camera-cut
        # section must cover the computed sequence end; otherwise actors and
        # the camera restore their map defaults late in the render, which can
        # falsely resurrect or relocate an otherwise stable corpse.
        for section in self.persistent_sections:
            section.set_range(0, end_frame)
        unreal.EditorAssetLibrary.save_loaded_asset(self.sequence, False)
        unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
        contacts = self.validate_contacts()
        assembly = self.validate_procedural_assembly() if self.procedural_proof else None
        equipment = self.validate_equipment_attachments() if self.procedural_proof else None
        facing = self.facing_diagnostics() if self.procedural_proof else None
        terminals = self.validate_terminal(presentation_end)
        render_dir = self.create_render_preset()
        camera_debug_path = GENERATED / "live_camera_debug.json"
        if not camera_debug_path.exists():
            raise RuntimeError("Live camera producer diagnostics are missing")
        camera_debug = json.loads(camera_debug_path.read_text(encoding="utf-8"))
        invalid_camera_commands = [
            item for item in self.camera_cut_records
            if not all(item.get("validation", {}).get(key, False) for key in ("geometry_valid", "los_valid", "occupancy_valid"))
        ]
        modes = {item["camera_mode"] for item in self.camera_cut_records}
        if invalid_camera_commands:
            raise RuntimeError(f"Live camera applied invalid commands: {invalid_camera_commands[:2]}")
        if len(self.camera_cut_records) < 4 or len(modes) < 3:
            raise RuntimeError("Live camera stayed static or did not demonstrate enough broadcast modes")
        camera_debug.update({
            "cuts_applied": len(self.camera_cut_records),
            "camera_commands_applied": self.camera_command_count,
            "duplicate_camera_commands_ignored": self.duplicate_frames,
            "applied_modes": sorted(modes),
            "applied_shots": self.camera_cut_records,
            "unreal_geometry_invalid_commands": len(invalid_camera_commands),
            "one_persistent_camera": True,
            "viewport_camera_locked": self.viewport_camera_locked,
        })
        atomic_json(camera_debug_path, camera_debug)
        if self.procedural_proof:
            debug_root = GENERATED / ("29a2" if self.presentation_profile == "29a2_population" else "29a1_1")
            atomic_json(debug_root / "equipment_attachment_debug.json", equipment)
            atomic_json(debug_root / "facing_debug.json", facing)
            shots = camera_debug.get("shots", camera_debug.get("applied_shots", []))
            empty_durations = [
                float(item.get("duration_seconds", 0.0) or 0.0)
                for item in shots if not item.get("target_actor_ids")
            ]
            acquisition_records = list(camera_debug.get("acquisition_records", []))
            expected_focus_ids = {
                item["transition_id"] for item in self.focus_change_records
                if item.get("to_descender_id")
            }
            acquired_focus_ids = {
                item["transition_id"] for item in acquisition_records
                if item.get("actor_ready") and item.get("target_visible")
            }
            acquisition = {
                "protocol": "underreach.camera-acquisition-debug.v1",
                "focus_transitions": list(self.focus_change_records),
                "acquisitions": acquisition_records,
                "applied_shots": list(self.camera_cut_records),
                "viewport_camera_locked": self.viewport_camera_locked,
                "startup_target_actor_ids": list(self.camera_cut_records[0].get("target_actor_ids", [])) if self.camera_cut_records else [],
                "startup_acquired": bool(self.camera_cut_records and self.camera_cut_records[0].get("target_actor_ids")),
                "startup_acquisition_seconds": float(self.camera_cut_records[0]["presentation_seconds"]) if self.camera_cut_records else None,
                "maximum_follow_visible_latency_seconds": float(camera_debug.get("maximum_focus_acquisition_seconds", 0.0)),
                "maximum_empty_view_duration_seconds": max(empty_durations or [0.0]),
                "stale_target_incidents": int(camera_debug.get("stale_target_incidents", 0)),
                "actor_readiness_waits": int(camera_debug.get("actor_readiness_waits", 0)),
                "geometry_failures": int(camera_debug.get("wall_collisions", 0)),
                "los_failures": int(camera_debug.get("los_failures", 0)),
                "occupancy_failures": int(camera_debug.get("occupancy_failures", 0)),
                "expected_focus_transition_count": len(expected_focus_ids),
                "acquired_focus_transition_count": len(expected_focus_ids & acquired_focus_ids),
                "missing_focus_transition_ids": sorted(expected_focus_ids - acquired_focus_ids),
            }
            if (
                not acquisition["startup_acquired"]
                or acquisition["stale_target_incidents"]
                or acquisition["missing_focus_transition_ids"]
                or acquisition["maximum_follow_visible_latency_seconds"] > 1.5
                or acquisition["maximum_empty_view_duration_seconds"] > 2.0
            ):
                raise RuntimeError(f"Live camera acquisition validation failed: {acquisition}")
            atomic_json(debug_root / "camera_acquisition_debug.json", acquisition)
            atomic_json(debug_root / "validation_report.json", {
                "protocol": "underreach.29a2-validation.v1" if self.presentation_profile == "29a2_population" else "underreach.29a1.1-validation.v1",
                "equipment_valid": equipment["valid"],
                "facing_valid": facing["count_above_45_degrees"] == 0 and facing["attacks_aligned"],
                "camera_acquisition_valid": (
                    acquisition["startup_acquired"]
                    and acquisition["stale_target_incidents"] == 0
                    and not acquisition["missing_focus_transition_ids"]
                    and acquisition["maximum_follow_visible_latency_seconds"] <= 1.5
                    and acquisition["maximum_empty_view_duration_seconds"] <= 2.0
                ),
                "anatomy_valid": bool(assembly and assembly["one_body_per_actor"]),
                "species_switch_exclusive": bool(assembly and assembly["species_switch_exclusive"]),
            })
        debug = {
            "protocol": PROTOCOL,
            "authoritative": False,
            "descent_id": self.descent_id,
            "unreal_process_id": self.process_id,
            "unreal_session_duration_seconds": time.monotonic() - self.session_started_monotonic,
            "bootstrap_count": self.bootstrap_count,
            "environment_bootstrap_count": self.environment_bootstrap_count,
            "environment_rebuild_count": self.environment_rebuild_count,
            "full_sequence_rebuild_count": self.full_sequence_rebuild_count,
            "incremental_frames_received": len(self.applied_frame_ids),
            "delivery_files_seen": len(self.applied_paths),
            "duplicate_frames": self.duplicate_frames,
            "rejected_frames": self.rejected_frames,
            "missing_ranges": self.missing_ranges,
            "latest_frame_sequence": self.latest_frame_sequence,
            "latest_frame_id": self.latest_frame_id,
            "applied_frame_ids": [item["frame_id"] for item in self.frame_apply_log],
            "frame_apply_log": self.frame_apply_log,
            "command_counts": self.command_counts,
            "applied_command_count": len(self.applied_command_ids),
            "bootstrap_actor_spawn_count": len(self.bootstrap.get("actors", [])),
            "incremental_actor_spawn_count": self.command_counts.get("spawn_actor", 0),
            "live_skeletal_actor_count": len(self.actors),
            "animation_section_count": sum(len(actor.animation_track.get_sections()) for actor in self.actors.values()),
            "animation_binding_errors": self.animation_errors,
            "terminal_actor_count": sum(actor.terminal for actor in self.actors.values()),
            "terminal_validation": terminals,
            "contact_validation": contacts,
            "camera_profile": "underreach_spectator_viewer_28c1" if self.presentation_profile == "28c1_spectator" else "underreach_live_bounded_lookahead_director_28b3" if self.presentation_profile == "28b3_multichannel" else "underreach_live_bounded_lookahead_director_28b2",
            "camera_command_count": self.camera_command_count,
            "camera_cut_records": self.camera_cut_records,
            "focus_change_records": self.focus_change_records,
            "focus_change_count": len(self.focus_change_records),
            "equipment_attachment_validation": equipment,
            "facing_validation": facing,
            "sequence_asset": self.live_sequence,
            "level_asset": self.level_asset,
            "render_config_asset": self.live_preset,
            "render_output_directory": str(render_dir),
            "expected_video_path": str(render_dir / f"{self.render_name}.mp4"),
            "presentation_duration_seconds": presentation_end,
            "producer": producer,
            "one_session_many_frames": len(self.applied_frame_ids) > 5 and self.bootstrap_count == 1,
        }
        atomic_json(GENERATED / "live_bridge_debug.json", debug)
        if self.procedural_proof:
            procedural_actors = [
                {
                    "actor_id": runtime.actor_id,
                    "species": runtime.species,
                    "visual_variant": runtime.visual_variant,
                    "visual_identity_digest": runtime.character_manifest.get("visual_identity_digest"),
                    "mesh_asset": self._procedural_assets_for(runtime)["mesh"].get_path_name(),
                    "renderer_manifest": runtime.character_manifest,
                    "renderer_manifest_digest": digest(runtime.character_manifest),
                    "actor_scale": runtime.actor_scale,
                    "standing_root_z": runtime.pose.get("z", 94.0) + runtime.floor_z_offset,
                    "terminal": runtime.terminal,
                    "animation_section_count": len(runtime.animation_track.get_sections()),
                }
                for runtime in self.actors.values()
                if runtime.species
            ]
            character_report = {
                "protocol": "underreach.character-29a2-validation.v1" if self.presentation_profile == "29a2_population" else "underreach.character-29a1-validation.v1",
                "authoritative": False,
                "descent_id": self.descent_id,
                "procedural_actor_count": len(procedural_actors),
                "procedural_actors": procedural_actors,
                "animation_binding_errors": list(self.animation_errors),
                "contact_validation": contacts,
                "assembly_validation": assembly,
                "terminal_validation": terminals,
                "focus_change_records": list(self.focus_change_records),
                "camera_cut_count": len(self.camera_cut_records),
                "presentation_duration_seconds": presentation_end,
                "expected_video_path": str(render_dir / f"{self.render_name}.mp4"),
            }
            character_report["digest"] = digest(character_report)
            if self.presentation_profile == "29a2_population":
                species_counts = {
                    species: sum(item["species"] == species for item in procedural_actors)
                    for species in ("human", "dwarf")
                }
                live_population = {
                    "protocol": "underreach.live-population-report.v1",
                    "implementation_version": "29a2.1",
                    "descent_id": self.descent_id,
                    "simultaneously_presentable_count": len(procedural_actors),
                    "species_counts": species_counts,
                    "visual_variant_count": len({item["visual_variant"] for item in procedural_actors}),
                    "visual_identity_count": len({item["visual_identity_digest"] for item in procedural_actors}),
                    "runtime_material_asset_count": assembly.get("distinct_runtime_material_assets", 0),
                    "actors": procedural_actors,
                    "assembly": assembly,
                    "equipment": equipment,
                    "facing": facing,
                    "terminal_validation": terminals,
                    "contact_validation": contacts,
                    "camera_cut_count": len(self.camera_cut_records),
                    "focus_change_count": len(self.focus_change_records),
                    "animation_binding_errors": list(self.animation_errors),
                    "actor_spawn_assembly_seconds": self.population_actor_assembly_seconds,
                    "unreal_session_seconds": time.monotonic() - self.session_started_monotonic,
                    "expected_video_path": str(render_dir / f"{self.render_name}.mp4"),
                }
                live_population["digest"] = digest(live_population)
                atomic_json(GENERATED / "29a2" / "live_population_report.json", live_population)
            else:
                atomic_json(GENERATED / "29a1" / "character_29a1_validation_report.json", character_report)
        atomic_json(GENERATED / "live_unreal_result.json", {
            "protocol": PROTOCOL,
            "level_asset": self.level_asset,
            "map_object": object_path(self.level_asset),
            "sequence_asset": self.live_sequence,
            "sequence_object": object_path(self.live_sequence),
            "render_config_asset": self.live_preset,
            "render_config_object": object_path(self.live_preset),
            "render_output_directory": str(render_dir),
            "expected_video_path": str(render_dir / f"{self.render_name}.mp4"),
            "render_width": 1920 if self.procedural_proof else 1280,
            "render_height": 1080 if self.procedural_proof else 720,
            "render_fps": FPS,
            "presentation_duration_seconds": presentation_end,
            "unreal_process_id": self.process_id,
        })
        log(f"Applied {len(self.applied_frame_ids)} incremental frames in one session")


def main():
    bootstrap = wait_json(SPOOL / "bootstrap.json")
    consumer = LiveUnrealConsumer(bootstrap)
    consumer.consume()


main()
