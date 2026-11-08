"""Bake-off scoring renderer (Blender 4.2, headless).

Usage: blender -b -noaudio --python score_render.py -- <mesh> <label> <outdir>

Imports one mesh, canonicalizes it (longest bbox axis -> Z, uniform scale to
height 2.0, centered on XY, grounded at Z=0), then renders:
  - silhouette masks (opaque white override, alpha coverage) from
    front/side/back/three-quarter ortho cameras at 4 yaw rotations
    (mask_<view>_yaw<N>.png) so the caller can pick the best-facing yaw;
  - beauty renders with original materials (beauty_<view>.png) at yaw 0.
Writes info.json with the source bbox dims and vertex/face counts.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
mesh_path, label, outdir = argv[0], argv[1], argv[2]
os.makedirs(outdir, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
ext = os.path.splitext(mesh_path)[1].lower()
if ext == ".obj":
    bpy.ops.wm.obj_import(filepath=mesh_path)
elif ext in (".glb", ".gltf"):
    bpy.ops.import_scene.gltf(filepath=mesh_path)
else:
    raise SystemExit(f"unsupported mesh type {ext}")

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    raise SystemExit("no mesh objects imported")
verts = sum(len(o.data.vertices) for o in meshes)
faces = sum(len(o.data.polygons) for o in meshes)

# Join into one object for canonicalization.
bpy.ops.object.select_all(action="DESELECT")
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
obj = bpy.context.view_layer.objects.active

# World-space bbox.
def world_bbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))

(x0, x1), (y0, y1), (z0, z1) = world_bbox(obj)
dims = (x1 - x0, y1 - y0, z1 - z0)
info = {"label": label, "verts": verts, "faces": faces,
        "bbox_dims_raw": [round(d, 4) for d in dims]}

# Canonicalize: trust the importer's up axis (Blender import puts every
# supported format Z-up; a longest-axis rule would tip a winged character
# onto one wingtip, since wingspan > height). Scale to height 2.0 by the
# Z extent, center XY, ground Z. Facing is handled by the caller's yaw
# search; any mesh that arrives genuinely sideways is caught on the
# comparison sheet and re-run with a documented fixed rotation.
#
# CRITICAL: importers may carry the axis conversion as an object rotation.
# Bake rotation + scale into the vertices BEFORE the yaw loop — setting
# absolute rotation_euler values there would otherwise wipe the import
# conversion and render the mesh in its raw file orientation (this bug
# invalidated the first scoring pass: Pip rendered lying on his back).
bpy.context.view_layer.objects.active = obj
(x0, x1), (y0, y1), (z0, z1) = world_bbox(obj)
height = z1 - z0
s = 2.0 / height
obj.scale = (s, s, s)
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
(x0, x1), (y0, y1), (z0, z1) = world_bbox(obj)
obj.location.x -= (x0 + x1) / 2
obj.location.y -= (y0 + y1) / 2
obj.location.z -= z0
bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

# Scene: Cycles CPU (this VM has no EGL/OpenGL for EEVEE), transparent film.
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 48
scene.cycles.use_denoising = False
scene.render.resolution_x = scene.render.resolution_y = 512
scene.render.film_transparent = True
scene.render.image_settings.file_format = "PNG"
world = bpy.data.worlds.new("W")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[1].default_value = 0.6

cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = 2.5
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
sun_data = bpy.data.lights.new("sun", "SUN")
sun_data.energy = 3.0
sun = bpy.data.objects.new("sun", sun_data)
sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
scene.collection.objects.link(sun)

VIEWS = {
    "front": ((0, -4, 1.0), (0, 0, 1.0)),
    "side": ((4, 0, 1.0), (0, 0, 1.0)),
    "back": ((0, 4, 1.0), (0, 0, 1.0)),
    "threeq": ((2.6, -2.6, 1.7), (0, 0, 0.95)),
}

def point_cam(pos, target):
    cam.location = pos
    d = Vector(target) - Vector(pos)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

def orbited(view, yaw):
    # Yaw is orbited by the CAMERA around the view target's Z axis, never
    # by rotating the object: some importers leave objects in quaternion
    # rotation mode, where writing rotation_euler silently does nothing
    # (this invalidated the GLB candidates' first scoring pass — every
    # yaw rendered identically). Camera orbit yields identical
    # silhouettes; lights stay world-fixed, which only shifts beauty
    # highlights slightly and does not affect masks.
    pos, tgt = VIEWS[view]
    a = math.radians(-yaw)
    dx, dy = pos[0] - tgt[0], pos[1] - tgt[1]
    return ((tgt[0] + dx * math.cos(a) - dy * math.sin(a),
             tgt[1] + dx * math.sin(a) + dy * math.cos(a), pos[2]), tgt)

def render(name):
    scene.render.filepath = os.path.join(outdir, name)
    bpy.ops.render.render(write_still=True)

# Beauty pass first (original materials), front + three-quarter per yaw so
# the caller can present each mesh from its best-facing yaw.
for yaw in (0, 90, 180, 270):
    for view in ("front", "threeq"):
        pos, tgt = orbited(view, yaw)
        point_cam(pos, tgt)
        render(f"beauty_{view}_yaw{yaw}.png")

# Silhouette pass: single opaque white material everywhere (mask comes from
# the alpha channel; 1 sample is enough).
scene.cycles.samples = 1
white = bpy.data.materials.new("maskwhite")
white.use_nodes = True
white.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1, 1, 1, 1)
for slot in range(len(obj.data.materials)):
    obj.data.materials[slot] = white

for yaw in (0, 90, 180, 270):
    for view in VIEWS:
        pos, tgt = orbited(view, yaw)
        point_cam(pos, tgt)
        render(f"mask_{view}_yaw{yaw}.png")

with open(os.path.join(outdir, "info.json"), "w") as f:
    json.dump(info, f, indent=1)
print("SCORE_RENDER_OK", label)
