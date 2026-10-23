"""Headless MPFB authoring/export for the Slice 29A.1 visual proof.

Run inside Blender, not the project Python environment. The input is generated
by scripts/generate-underreach-character-dna.py.
"""

from __future__ import annotations

from hashlib import sha256
import json
import math
import os
from pathlib import Path
import sys
import time

import bpy
from mathutils import Vector

try:
    from bl_ext.blender_org.mpfb.services import HumanService, TargetService
except ImportError as exc:
    raise RuntimeError("MPFB 2.x is unavailable in this Blender profile") from exc


PROTOCOL = "underreach.blender-character-authoring.v1"
VERSION = "29a2.1"
LIVE_IDS = {
    "human_average", "human_short_heavy", "human_tall_thin",
    "dwarf_average", "dwarf_heavy", "dwarf_alt",
}
FACE_TARGETS = (
    "blink_left", "blink_right", "eye_look_left", "eye_look_right", "brow_up", "brow_down",
    "jaw_open", "lip_pucker", "lip_funnel", "lip_stretch", "smile", "frown",
    "viseme_aa", "viseme_ee", "viseme_ih", "viseme_oh", "viseme_ou", "viseme_fv", "viseme_mbp",
)


def args() -> tuple[Path, Path]:
    values = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(values) != 2:
        raise RuntimeError("expected: -- <character_authoring_inputs.json> <output-directory>")
    return Path(values[0]).resolve(), Path(values[1]).resolve()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def asset_root() -> Path:
    root = Path(os.environ["APPDATA"]) / "Blender Foundation" / "Blender" / "5.2" / "extensions" / ".user" / "blender_org" / "mpfb" / "data"
    required = root / "packs" / "makehuman_system_assets.json"
    if not required.exists():
        raise RuntimeError(f"MakeHuman System Assets are unavailable: {required}")
    return root


def clear_scene() -> None:
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.meshes, bpy.data.armatures, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for item in list(collection):
            if item.users == 0:
                collection.remove(item)


def macro_details(dna: dict) -> dict:
    details = TargetService.get_default_macro_info_dict()
    details["gender"] = 0.82
    details["age"] = max(0.28, min(0.78, 0.36 + (dna["age_years"] - 18) / 120.0))
    details["muscle"] = dna["muscularity"]
    details["weight"] = max(0.05, min(0.95, 0.16 + dna["body_fat"] * 1.55))
    details["height"] = max(0.0, min(1.0, (dna["height_cm"] - 118.0) / 87.0))
    details["proportions"] = 0.26 if dna["species"] == "dwarf" else 0.5 + (dna["leg_length"] - 0.5) * 0.55
    details["race"] = {"african": 0.0, "asian": 0.0, "caucasian": 0.0}
    race = ("african", "asian", "caucasian")[dna["face_seed"] % 3]
    details["race"][race] = 1.0
    return details


def apply_baked_proportions(body, rig, dna: dict) -> None:
    """Apply deterministic proportions without invalidating MPFB skin binds.

    MPFB's macro targets already author the limb/torso ratios and fit its game
    skeleton.  Species scale therefore belongs at the shared rig root: every
    skinned mesh, animation, and socket attachment remains in the same space.
    FBX export bakes this transform into the authored Unreal assets.
    """
    source_height = body.dimensions.z
    target = dna["height_cm"] / 100.0
    vertical = target / source_height
    if dna["species"] == "dwarf":
        rig.scale = (vertical * 1.20, vertical * 1.13, vertical)
    else:
        shoulder = 0.96 + dna["shoulder_width"] * 0.08
        rig.scale = (vertical * shoulder, vertical, vertical)
    bpy.context.view_layer.update()
    body["underreach_species"] = dna["species"]
    body["underreach_dna_digest"] = sha256(canonical(dna).encode("utf-8")).hexdigest()


def apply_identity_face_shape(body, dna: dict) -> dict:
    """Bake conservative DNA-specific facial proportions into the source mesh.

    These are persistent identity offsets, not animation targets. They are
    applied before the standard facial contract keys are authored, so every
    exported expression is relative to the same distinct neutral face.
    """
    xs = [point.co.x for point in body.data.vertices]
    zs = [point.co.z for point in body.data.vertices]
    center_x = (min(xs) + max(xs)) * 0.5
    bottom, top = min(zs), max(zs)
    height = max(0.001, top - bottom)
    changed = 0
    jaw = 0.94 + float(dna["jaw_width"]) * 0.12
    fullness = 0.96 + float(dna["facial_fullness"]) * 0.08
    chin = (float(dna["chin_prominence"]) - 0.5) * 0.018
    nose = (float(dna["nose_scale"]) - 0.5) * 0.025
    brow = (float(dna["brow_prominence"]) - 0.5) * 0.012
    for point in body.data.vertices:
        normalized_z = (point.co.z - bottom) / height
        if normalized_z < 0.79:
            continue
        relative_x = point.co.x - center_x
        if normalized_z < 0.88:
            point.co.x = center_x + relative_x * jaw
            point.co.y *= fullness
            point.co.z += chin * max(0.0, (0.86 - normalized_z) / 0.07)
        if point.co.y < 0.0 and 0.84 <= normalized_z <= 0.92 and abs(relative_x) < 0.045:
            point.co.y -= nose
        if 0.90 <= normalized_z <= 0.95:
            point.co.z += brow
        changed += 1
    body.data.update()
    signature = {
        "face_seed": int(dna["face_seed"]),
        "jaw_scale": round(jaw, 6),
        "fullness_scale": round(fullness, 6),
        "chin_offset_m": round(chin, 6),
        "nose_offset_m": round(nose, 6),
        "brow_offset_m": round(brow, 6),
        "changed_vertex_count": changed,
    }
    body["underreach_identity_face_signature"] = canonical(signature)
    return signature


def add_face_contract(body) -> None:
    basis = body.data.shape_keys.key_blocks[0] if body.data.shape_keys else body.shape_key_add(name="Basis")
    height = max(point.co.z for point in basis.data)
    for name in FACE_TARGETS:
        # New Blender shape keys default to value 1.0.  A sequence of
        # from-mix keys would therefore compound every prior face delta and
        # explode the evaluated mesh.  Author each contract target relative to
        # the untouched Basis and leave it inactive until runtime.
        key = body.shape_key_add(name=name, from_mix=False)
        key.value = 0.0
        for index, point in enumerate(key.data):
            base = basis.data[index].co
            if base.z < height * 0.76 or base.y >= 0.0:
                continue
            if name.startswith("blink") and height * 0.86 < base.z < height * 0.93:
                point.co.z -= 0.008
            elif name.startswith("eye_look") and height * 0.86 < base.z < height * 0.93:
                point.co.x += -0.004 if name.endswith("left") else 0.004
            elif name == "brow_up" and base.z > height * 0.9:
                point.co.z += 0.008
            elif name == "brow_down" and base.z > height * 0.9:
                point.co.z -= 0.006
            elif name == "jaw_open" and height * 0.76 < base.z < height * 0.86:
                point.co.z -= 0.025
                point.co.y -= 0.008
            elif name in {"smile", "lip_stretch", "viseme_ee"} and height * 0.8 < base.z < height * 0.87:
                point.co.x *= 1.035
            elif name in {"frown", "lip_pucker", "lip_funnel", "viseme_ou", "viseme_oh"} and height * 0.8 < base.z < height * 0.87:
                point.co.x *= 0.96
                point.co.y -= 0.005
            elif name.startswith("viseme_") and height * 0.79 < base.z < height * 0.87:
                point.co.z -= 0.008


def material(name: str, color: tuple[float, float, float, float], metallic=0.0, roughness=0.5):
    value = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    value.diffuse_color = color
    value.use_nodes = True
    principled = value.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Metallic"].default_value = metallic
    principled.inputs["Roughness"].default_value = roughness
    return value


def add_system_asset(root: Path, body, category: str, name: str):
    path = root / category / name / f"{name}.mhclo"
    if not path.exists():
        raise RuntimeError(f"required MPFB asset is unavailable: {path}")
    return HumanService.add_mhclo_asset(str(path), body, asset_type=category.title(), subdiv_levels=0, material_type="MAKESKIN")


def bake_body_visibility_masks(body, clothing_name: str) -> dict:
    """Bake MPFB's helper/garment masks before morph-preserving FBX export.

    MPFB previews hide the body below a garment with a ``Delete.<garment>``
    Mask modifier.  The legacy FBX export must set ``use_mesh_modifiers=False``
    so UE receives face shape keys, which otherwise exports both the hidden body
    arms and the garment sleeves.  Apply only the garment mask before creating
    the face contract; the deleted vertices no longer reach FBX while the later
    face shape keys remain intact.
    """
    expected_names = {"Hide helpers", f"Delete.{clothing_name}"}
    candidates = [modifier for modifier in body.modifiers if modifier.type == "MASK"]
    if not expected_names.issubset({modifier.name for modifier in candidates}):
        raise RuntimeError(
            f"Expected MPFB visibility masks {sorted(expected_names)}, got {[modifier.name for modifier in candidates]}"
        )
    before = len(body.data.vertices)
    applied = []
    for modifier in candidates:
        group = body.vertex_groups.get(modifier.vertex_group)
        if group is None:
            raise RuntimeError(f"MPFB mask {modifier.name} has no vertex group {modifier.vertex_group}")
        members = set()
        for vertex in body.data.vertices:
            try:
                if group.weight(vertex.index) > float(modifier.threshold):
                    members.add(vertex.index)
            except RuntimeError:
                pass
        remove_indices = (
            members if modifier.invert_vertex_group
            else {vertex.index for vertex in body.data.vertices}.difference(members)
        )
        if not remove_indices:
            raise RuntimeError(f"MPFB visibility mask {modifier.name} removed no vertices")
        bpy.ops.object.select_all(action="DESELECT")
        body.select_set(True)
        bpy.context.view_layer.objects.active = body
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="DESELECT")
        bpy.ops.object.mode_set(mode="OBJECT")
        for index in remove_indices:
            body.data.vertices[index].select = True
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.delete(type="VERT")
        bpy.ops.object.mode_set(mode="OBJECT")
        applied.append({"modifier": modifier.name, "removed_vertex_count": len(remove_indices)})
        body.modifiers.remove(modifier)
    after = len(body.data.vertices)
    if after >= before:
        raise RuntimeError("MPFB visibility masks removed no hidden body geometry")
    result = {
        "mechanism": "bake_mpfb_visibility_masks_before_underreach_shape_keys",
        "applied_masks": applied,
        "body_vertex_count_before": before,
        "body_vertex_count_after": after,
        "removed_hidden_body_vertex_count": before - after,
        "visible_arm_geometry_layers_per_side": 1,
    }
    body["underreach_body_visibility_masks"] = json.dumps(result, sort_keys=True)
    return result


def bind_rigid_to_bone(obj, rig, bone_name):
    """Skin a rigid proxy 100% to one bone without rubber-stretching it."""
    group = obj.vertex_groups.new(name=bone_name)
    group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    modifier = obj.modifiers.new("Underreach rigid bone bind", "ARMATURE")
    modifier.object = rig
    obj["underreach_fit"] = "single_bone_rigid_attachment"
    obj["underreach_attachment_bone"] = bone_name
    return obj


def add_rigid_box(name, dimensions, location, material_value, rig, bone_name, bevel=0.05):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    modifier = obj.modifiers.new("Rigid bevel", "BEVEL")
    modifier.width = bevel
    modifier.segments = 3
    obj.data.materials.append(material_value)
    return bind_rigid_to_bone(obj, rig, bone_name)


def _bone_anchor(rig, bone_name: str, fraction: float) -> Vector:
    bone = rig.data.bones.get(bone_name)
    if bone is None:
        raise RuntimeError(f"attachment socket bone is missing: {bone_name}")
    return rig.matrix_world @ bone.head_local.lerp(bone.tail_local, float(fraction))


def _offset(anchor: Vector, values) -> Vector:
    return anchor + Vector(tuple(float(value) / 100.0 for value in values))


def apply_attachment_transform(obj, profile):
    obj.rotation_euler = tuple(
        math.radians(float(value)) for value in profile["relative_rotation_degrees"]
    )
    obj.scale = tuple(float(value) for value in profile["relative_scale"])
    return obj


def add_equipment(rig, body, profiles):
    armor = material("Underreach_Rigid_Iron", (0.11, 0.13, 0.15, 1), metallic=0.78, roughness=0.29)
    leather = material("Underreach_Leather", (0.12, 0.045, 0.018, 1), metallic=0.05, roughness=0.72)
    by_id = {item["item_visual_id"]: item for item in profiles}
    expected = {
        "underreach.armor.helmet.v1", "underreach.armor.breastplate.v1", "underreach.weapon.sword.v1"
    }
    if not set(by_id).issubset(expected) or "underreach.weapon.sword.v1" not in by_id:
        raise RuntimeError(f"equipment attachment profile set is incomplete: {sorted(by_id)}")
    applied = []
    objects = []
    object_map = {}

    if "underreach.armor.breastplate.v1" in by_id:
        chest_profile = by_id["underreach.armor.breastplate.v1"]
        chest_geometry = chest_profile["geometry"]
        chest_anchor = _bone_anchor(rig, chest_profile["socket_name"], chest_profile["anchor_fraction"])
        chest_location = _offset(chest_anchor, chest_profile["relative_location_cm"])
        chest = add_rigid_box(
            "Breastplate_Proxy",
            tuple(float(chest_geometry[key]) / 100.0 for key in ("width_cm", "depth_cm", "height_cm")),
            chest_location, armor, rig, chest_profile["socket_name"], bevel=0.015,
        )
        apply_attachment_transform(chest, chest_profile)
        chest["controlled_scale"] = round(float(chest_geometry["width_cm"]), 6)
        object_map["underreach.armor.breastplate.v1"] = [chest]
        objects.append(chest)

    if "underreach.armor.helmet.v1" in by_id:
        helmet_profile = by_id["underreach.armor.helmet.v1"]
        helmet_geometry = helmet_profile["geometry"]
        helmet_anchor = _bone_anchor(rig, helmet_profile["socket_name"], helmet_profile["anchor_fraction"])
        helmet_location = _offset(helmet_anchor, helmet_profile["relative_location_cm"])
        bpy.ops.mesh.primitive_cone_add(
            vertices=32,
            radius1=float(helmet_geometry["radius_cm"]) / 100.0,
            radius2=float(helmet_geometry["radius_cm"]) * 0.82 / 100.0,
            depth=float(helmet_geometry["depth_cm"]) / 100.0,
            location=helmet_location,
        )
        helmet = bpy.context.object
        helmet.name = "Helmet_Proxy"
        helmet.data.materials.append(armor)
        apply_attachment_transform(helmet, helmet_profile)
        bind_rigid_to_bone(helmet, rig, helmet_profile["socket_name"])
        object_map["underreach.armor.helmet.v1"] = [helmet]
        objects.append(helmet)

    sword_profile = by_id["underreach.weapon.sword.v1"]
    sword_geometry = sword_profile["geometry"]
    hand = _bone_anchor(rig, sword_profile["socket_name"], sword_profile["anchor_fraction"])
    blade_length = float(sword_geometry["blade_length_cm"]) / 100.0
    handle_length = float(sword_geometry["handle_length_cm"]) / 100.0
    # The profile anchor is the center of the gripping hand, not the guard.
    # Place the guard half a handle below it so the palm encloses the handle
    # instead of merely touching the crossguard.
    sword_origin = _offset(hand, sword_profile["relative_location_cm"])
    sword_origin.z -= handle_length * 0.5
    bpy.ops.mesh.primitive_cone_add(
        vertices=4,
        radius1=float(sword_geometry["blade_base_radius_cm"]) / 100.0,
        radius2=float(sword_geometry["blade_tip_radius_cm"]) / 100.0,
        depth=blade_length,
        location=(sword_origin.x, sword_origin.y, sword_origin.z - blade_length * 0.5),
        rotation=(0.0, 0.0, math.radians(45.0)),
    )
    blade = bpy.context.object
    blade.name = "Sword_Blade"
    blade.data.materials.append(armor)
    apply_attachment_transform(blade, sword_profile)
    bind_rigid_to_bone(blade, rig, sword_profile["socket_name"])
    guard = add_rigid_box(
        "Sword_Guard", (float(sword_geometry["guard_width_cm"]) / 100.0, 0.025, 0.025),
        sword_origin, leather, rig, sword_profile["socket_name"], bevel=0.006,
    )
    apply_attachment_transform(guard, sword_profile)
    handle = add_rigid_box(
        "Sword_Handle", (0.028, 0.028, handle_length),
        (sword_origin.x, sword_origin.y, sword_origin.z + handle_length * 0.5),
        leather, rig, sword_profile["socket_name"], bevel=0.005,
    )
    apply_attachment_transform(handle, sword_profile)
    object_map["underreach.weapon.sword.v1"] = [blade, guard, handle]
    objects.extend([blade, guard, handle])
    for profile in profiles:
        anchor = _bone_anchor(rig, profile["socket_name"], profile["anchor_fraction"])
        record = {
            **profile,
            "component_names": [obj.name for obj in object_map[profile["item_visual_id"]]],
            "anchor_world_m": [round(float(value), 6) for value in anchor],
            "expected_socket_error_cm": 0.0,
            "duplicate_visible_copies": 0,
        }
        for obj in object_map[profile["item_visual_id"]]:
            obj["underreach_attachment_profile"] = json.dumps(record, sort_keys=True)
        applied.append(record)
    return objects, applied


def add_beard(rig, body, dna):
    if not dna["appearance"].get("facial_hair_asset"):
        return None
    height = body.dimensions.z
    hair = material("Underreach_Beard", (0.035, 0.014, 0.006, 1), roughness=0.85)
    beard_depth = height * (0.11 if dna["species"] == "dwarf" else 0.07)
    bpy.ops.mesh.primitive_cone_add(
        vertices=24, radius1=body.dimensions.x * 0.085,
        radius2=body.dimensions.x * 0.055, depth=beard_depth,
        location=(0, -body.dimensions.y * 0.34, height * 0.83),
    )
    beard = bpy.context.object
    beard.name = "Beard_Proxy"
    beard.rotation_euler[0] = math.radians(-8)
    beard.data.materials.append(hair)
    return bind_rigid_to_bone(beard, rig, "head")


def create_actions(rig, species: str):
    actions = {}
    bpy.context.scene.render.fps = 30

    def action(name, duration, poses):
        value = bpy.data.actions.new(f"A_{species.title()}_{name}")
        rig.animation_data_create()
        rig.animation_data.action = value
        for bone in rig.pose.bones:
            bone.matrix_basis = __import__("mathutils").Matrix.Identity(4)
        for frame, values in poses:
            for bone in rig.pose.bones:
                bone.rotation_mode = "XYZ"
                bone.rotation_euler = (0.0, 0.0, 0.0)
                bone.location = (0.0, 0.0, 0.0)
                bone.scale = (1.0, 1.0, 1.0)
            for bone_name, rotation, location in values:
                bone = rig.pose.bones.get(bone_name)
                if not bone:
                    continue
                bone.rotation_mode = "XYZ"
                bone.rotation_euler = tuple(math.radians(x) for x in rotation)
                bone.location = location
            for bone in rig.pose.bones:
                bone.keyframe_insert("rotation_euler", frame=frame, group=bone.name)
                bone.keyframe_insert("location", frame=frame, group=bone.name)
                bone.keyframe_insert("scale", frame=frame, group=bone.name)
        value.use_fake_user = True
        actions[name.lower()] = value
        return value

    neutral = [("pelvis", (0, 0, 0), (0, 0, 0)), ("spine_03", (0, 0, 0), (0, 0, 0))]
    action("Idle", 60, [(0, neutral), (30, [("spine_03", (1.5, 0, 0), (0, 0, 0))]), (60, neutral)])
    action("Walk", 30, [
        (0, [("thigh_l", (28, 0, 0), (0, 0, 0)), ("thigh_r", (-28, 0, 0), (0, 0, 0)), ("upperarm_l", (-24, 0, 0), (0, 0, 0)), ("upperarm_r", (24, 0, 0), (0, 0, 0))]),
        (15, [("thigh_l", (-28, 0, 0), (0, 0, 0)), ("thigh_r", (28, 0, 0), (0, 0, 0)), ("upperarm_l", (24, 0, 0), (0, 0, 0)), ("upperarm_r", (-24, 0, 0), (0, 0, 0))]),
        (30, [("thigh_l", (28, 0, 0), (0, 0, 0)), ("thigh_r", (-28, 0, 0), (0, 0, 0)), ("upperarm_l", (-24, 0, 0), (0, 0, 0)), ("upperarm_r", (24, 0, 0), (0, 0, 0))]),
    ])
    action("Attack", 45, [
        (0, neutral),
        (14, [("spine_03", (0, 0, -22), (0, 0, 0)), ("upperarm_r", (-35, 20, -55), (0, 0, 0)), ("lowerarm_r", (-45, 0, 0), (0, 0, 0))]),
        (25, [("spine_03", (0, 0, 28), (0, 0, 0)), ("upperarm_r", (72, -18, 52), (0, 0, 0)), ("lowerarm_r", (-8, 0, 0), (0, 0, 0))]),
        (45, neutral),
    ])
    action("Reaction", 30, [(0, neutral), (8, [("spine_03", (-20, 0, 12), (0, 0, 0)), ("upperarm_l", (-30, 0, -22), (0, 0, 0)), ("upperarm_r", (-30, 0, 22), (0, 0, 0))]), (30, neutral)])
    action("Death", 45, [(0, neutral), (18, [("pelvis", (0, 0, 24), (0, 0, 0)), ("spine_03", (-32, 0, 0), (0, 0, 0))]), (45, [("Root", (82, 0, 15), (0, 0, 0.1)), ("pelvis", (-15, 0, 22), (0, 0, 0))])])
    for bone in rig.pose.bones:
        bone.matrix_basis = __import__("mathutils").Matrix.Identity(4)
    rig.animation_data.action = actions["idle"]
    bpy.context.scene.frame_set(0)
    bpy.context.view_layer.update()
    return actions


def measure_semantic_contact(rig, action, contact_frame=25):
    """Record authored contact geometry in armature-local centimeters."""
    rig.animation_data.action = action
    bpy.context.scene.frame_set(contact_frame)
    bpy.context.view_layer.update()
    values = {}
    for name in ("Root", "hand_r", "spine_03"):
        bone = rig.pose.bones.get(name)
        if bone is None:
            raise RuntimeError(f"29A.1 contact contract bone is missing: {name}")
        point = bone.head
        values[name] = {axis: round(float(value) * 100.0, 6) for axis, value in zip(("x", "y", "z"), point)}
    values["hand_to_torso_delta_cm"] = {
        axis: round(values["hand_r"][axis] - values["spine_03"][axis], 6)
        for axis in ("x", "y", "z")
    }
    values["contact_frame"] = contact_frame
    values["contact_phase"] = round(contact_frame / 45.0, 6)
    return values


def look_at(obj, target: Vector):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def setup_render(body, descender_id: str, output: Path, *, close=False):
    scene = bpy.context.scene
    hidden = []
    if close:
        for obj in scene.objects:
            if obj.get("underreach_fit"):
                hidden.append((obj, obj.hide_render))
                obj.hide_render = True
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 720 if close else 960
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.color = (0.012, 0.015, 0.02)
    bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, 0))
    floor = bpy.context.object
    floor.name = "QA_Floor"
    floor.data.materials.append(material("QA_Floor_Mat", (0.035, 0.04, 0.045, 1), roughness=0.82))
    bpy.ops.object.light_add(type="AREA", location=(3.5, -4.5, 5.2))
    key = bpy.context.object
    key.data.energy = 1100
    key.data.shape = "DISK"
    key.data.size = 4.0
    look_at(key, Vector((0, 0, body.dimensions.z * 0.58)))
    bpy.ops.object.light_add(type="AREA", location=(-3.0, 0.5, 3.1))
    fill = bpy.context.object
    fill.data.energy = 680
    fill.data.size = 3.0
    look_at(fill, Vector((0, 0, body.dimensions.z * 0.56)))
    bpy.ops.object.camera_add(location=(0.0, -2.2 if close else -4.3, body.dimensions.z * (0.86 if close else 0.62)))
    camera = bpy.context.object
    camera.data.lens = 72 if close else 58
    look_at(camera, Vector((0, 0, body.dimensions.z * (0.86 if close else 0.52))))
    scene.camera = camera
    path = output / (f"{descender_id}_close_face.png" if close else f"{descender_id}.png")
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    for obj, prior in hidden:
        obj.hide_render = prior
    return path, [floor, key, fill, camera]


def selected_character_objects(rig):
    values = [rig]
    values.extend(obj for obj in bpy.data.objects if obj.parent == rig or any(mod.type == "ARMATURE" and mod.object == rig for mod in obj.modifiers))
    return list(dict.fromkeys(values))


def export_character(output: Path, descender_id: str, rig, actions):
    exports = []
    objects = selected_character_objects(rig)
    body = next(obj for obj in objects if obj.type == "MESH" and obj.name.endswith("_Body"))
    # UE's legacy FBX importer preserves blendshapes only when the skeletal
    # character arrives as one mesh node. Joining after visual QA retains
    # materials and vertex groups; rigid pieces remain 100% single-bone
    # weighted while only body vertices carry facial deltas.
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        if obj.type == "MESH":
            obj.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    body.name = f"SK_{descender_id}_Assembled"
    objects = [rig, body]
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.hide_render = False
        obj.hide_viewport = False
        obj.select_set(True)
    bpy.context.view_layer.objects.active = rig
    rig.animation_data.action = actions["idle"]
    mesh_path = output / "fbx" / f"SK_{descender_id}.fbx"
    mesh_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=str(mesh_path), use_selection=True, object_types={"ARMATURE", "MESH"},
        add_leaf_bones=False, use_armature_deform_only=True, bake_anim=False,
        apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Y", axis_up="Z",
        # Applying modifiers causes Blender's FBX exporter to discard shape
        # keys.  Keep the armature modifier as skin data so UE receives the
        # standardized face morph contract.
        use_mesh_modifiers=False, use_tspace=True,
    )
    exports.append(mesh_path)
    for role, action in actions.items():
        rig.animation_data.action = action
        # FBX otherwise bakes Blender's default 1..250 scene range for every
        # action.  Keep each semantic clip at its authored duration so Unreal
        # does not receive several seconds of duplicated terminal pose.
        scene = bpy.context.scene
        scene.frame_start = int(action.frame_range[0])
        scene.frame_end = int(action.frame_range[1])
        scene.frame_set(scene.frame_start)
        bpy.ops.object.select_all(action="DESELECT")
        rig.select_set(True)
        body.select_set(True)
        bpy.context.view_layer.objects.active = rig
        path = output / "fbx" / f"A_{descender_id}_{role}.fbx"
        bpy.ops.export_scene.fbx(
            filepath=str(path), use_selection=True, object_types={"ARMATURE", "MESH"}, add_leaf_bones=False,
            bake_anim=True, bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False,
            bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True,
            apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Y", axis_up="Z",
        )
        exports.append(path)
    return exports


def build_character(spec: dict, output: Path, root: Path):
    started = time.perf_counter()
    clear_scene()
    dna = spec["dna"]
    body = HumanService.create_human(
        mask_helpers=True, detailed_helpers=True, extra_vertex_groups=True,
        feet_on_ground=True, scale=0.1, macro_detail_dict=macro_details(dna),
    )
    # UE's legacy combined skeletal importer uses the alphabetically first mesh
    # node as its morph-bearing primary geometry. Keep the MPFB body first so
    # rigid proxy nodes cannot eclipse the face blendshape channels.
    body.name = f"A_SK_{spec['descender_id']}_Body"
    skin_names = ("young_caucasian_male", "young_asian_male", "young_african_male", "middleage_caucasian_male", "middleage_african_male")
    skin_name = skin_names[(int(dna["skin_variant"].split("_")[-1]) - 1) % len(skin_names)]
    HumanService.set_character_skin(str(root / "skins" / skin_name / f"{skin_name}.mhmat"), body, skin_type="MAKESKIN", material_instances=False)
    rig = HumanService.add_builtin_rig(body, "game_engine")
    rig.name = f"RIG_{spec['descender_id']}"
    outfit_id = dna["appearance"]["clothing_asset_ids"][0]
    outfit_name = outfit_id.split(".outfit.", 1)[-1].rsplit(".v1", 1)[0]
    clothes_name = (
        "male_worksuit01" if outfit_name == "worksuit01"
        else f"male_casualsuit{outfit_name.replace('casual', '')}"
    )
    if not (root / "clothes" / clothes_name / f"{clothes_name}.mhclo").exists():
        clothes_name = "male_casualsuit01"
    clothing = add_system_asset(root, body, "clothes", clothes_name)
    clothing.name = f"{spec['descender_id']}_ConformingClothing"
    hair_name = dna["appearance"]["current_hair_asset"].split(".")[-1]
    hair = add_system_asset(root, body, "hair", hair_name)
    hair.name = f"{spec['descender_id']}_Hair"
    eyes = add_system_asset(root, body, "eyes", "low-poly")
    eyes.name = f"{spec['descender_id']}_Eyes"
    apply_baked_proportions(body, rig, dna)
    # Asset fitting relies on the untouched MPFB base topology. Bake its
    # preview-only masks only after clothing, hair, and eyes are conformed.
    body_visibility_masks = bake_body_visibility_masks(body, clothes_name)
    face_identity = apply_identity_face_shape(body, dna)
    add_face_contract(body)
    add_beard(rig, body, dna)
    equipment, equipment_attachments = add_equipment(
        rig, body, spec["renderer_manifest"]["equipment_attachments"]
    )
    actions = create_actions(rig, dna["species"])
    semantic_contact = measure_semantic_contact(rig, actions["attack"])
    screenshot, qa_objects = setup_render(body, spec["descender_id"], output)
    close = None
    if spec["descender_id"] in LIVE_IDS:
        for obj in qa_objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        close, qa_objects = setup_render(body, spec["descender_id"], output, close=True)
    for obj in qa_objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    record_values = {
        "dna_digest": body["underreach_dna_digest"],
        "body_dimensions_m": [round(float(value), 6) for value in body.dimensions],
        "vertex_count": len(body.data.vertices),
        "conforming_clothing": clothing.name,
        "body_visibility_masks": body_visibility_masks,
        "face_identity": face_identity,
        "eye_asset": eyes.name,
        "rigid_equipment": [obj.name for obj in equipment],
        "equipment_attachments": equipment_attachments,
    }
    exported = export_character(output, spec["descender_id"], rig, actions) if spec["descender_id"] in LIVE_IDS else []
    blend_path = output / "blend" / ("%s.blend" % spec["descender_id"])
    blend_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), check_existing=False)
    files = [screenshot, blend_path, *exported]
    if close:
        files.append(close)
    return {
        "descender_id": spec["descender_id"],
        "species": dna["species"],
        "dna_digest": record_values["dna_digest"],
        "renderer_manifest_digest": spec["renderer_manifest_digest"],
        "body_dimensions_m": record_values["body_dimensions_m"],
        "vertex_count": record_values["vertex_count"],
        "bone_count": len(rig.data.bones),
        "face_targets": list(FACE_TARGETS),
        "conforming_clothing": record_values["conforming_clothing"],
        "body_visibility_masks": record_values["body_visibility_masks"],
        "face_identity": record_values["face_identity"],
        "eye_asset": record_values["eye_asset"],
        "rigid_equipment": record_values["rigid_equipment"],
        "equipment_attachments": record_values["equipment_attachments"],
        "semantic_attack_contact": semantic_contact,
        "generation_seconds": round(time.perf_counter() - started, 6),
        "files": [{"path": str(path), "sha256": digest_file(path), "size_bytes": path.stat().st_size} for path in files],
    }


def main():
    input_path, output = args()
    output.mkdir(parents=True, exist_ok=True)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if payload.get("protocol") != "underreach.character-authoring-inputs.v1":
        raise RuntimeError("unsupported Character authoring input protocol")
    root = asset_root()
    records = [build_character(spec, output, root) for spec in payload["characters"]]
    manifest = {
        "protocol": PROTOCOL,
        "version": VERSION,
        "blender_version": bpy.app.version_string,
        "mpfb_version": "2.0.17",
        "mpfb_build": "20260722",
        "system_assets_manifest": str(root / "packs" / "makehuman_system_assets.json"),
        "source_input_digest": digest_file(input_path),
        "characters": records,
    }
    manifest["digest"] = sha256(canonical(manifest).encode("utf-8")).hexdigest()
    write_json(output / "blender_character_export_manifest.json", manifest)
    print(json.dumps({"characters": len(records), "manifest_digest": manifest["digest"], "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
