import bpy, sys, math
import mathutils
argv = sys.argv[sys.argv.index("--")+1:]
src, dst = argv[0], argv[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
o = [x for x in bpy.context.scene.objects if x.type=="MESH"][0]
bb = [o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
cx = sum(v.x for v in bb)/8; cy = sum(v.y for v in bb)/8; cz = sum(v.z for v in bb)/8
r = max((v - mathutils.Vector((cx,cy,cz))).length for v in bb)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
bpy.context.scene.collection.objects.link(cam)
cam.location = (cx + r*1.9, cy - r*2.4, cz + r*1.1)
d = mathutils.Vector((cx,cy,cz)) - cam.location
cam.rotation_euler = d.to_track_quat('-Z','Y').to_euler()
bpy.context.scene.camera = cam
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun","SUN"))
bpy.context.scene.collection.objects.link(sun)
sun.data.energy = 3.0; sun.rotation_euler = (math.radians(50), 0, math.radians(35))
w = bpy.data.worlds.new("w"); bpy.context.scene.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[1].default_value = 0.5
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.samples = 24
sc.render.resolution_x = 640; sc.render.resolution_y = 640
sc.render.filepath = dst
bpy.ops.render.render(write_still=True)
print("rendered", dst)
