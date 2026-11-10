"""Generalized procedural vertex-colour painter for the environment pack.
Mirrors the proven pine route (paint_pine_vcolor.py): import the raw builder
shape, decimate to ~45k verts INSIDE Blender, clear custom split normals
BEFORE export (the pine lesson), paint per-vertex colours from position /
normal / noise rules, export a GLB whose "Color" attribute + vertex-colour
material the pipeline's prop stage carries through its own decimation.

Usage: blender -b --python paint_env.py -- <slug> <src.glb> <dst.glb>
"""
import bpy, os, math, sys

argv = sys.argv[sys.argv.index("--") + 1:]
SLUG, SRC, DST = argv[0], argv[1], argv[2]
TARGET_VERTS = 45000

# ---------- noise (copied from the proven pine painter) ----------
def _hash(ix, iy, iz):
    n = (ix * 374761393 + iy * 668265263 + iz * 2147483647) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) & 0xFFFFFFFF
    n = (n * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0

def vnoise(x, y, z):
    ix, iy, iz = math.floor(x), math.floor(y), math.floor(z)
    fx, fy, fz = x - ix, y - iy, z - iz
    sx, sy, sz = fx*fx*(3-2*fx), fy*fy*(3-2*fy), fz*fz*(3-2*fz)
    def L(a, b, t): return a + (b - a) * t
    c000=_hash(ix,iy,iz);   c100=_hash(ix+1,iy,iz)
    c010=_hash(ix,iy+1,iz); c110=_hash(ix+1,iy+1,iz)
    c001=_hash(ix,iy,iz+1); c101=_hash(ix+1,iy,iz+1)
    c011=_hash(ix,iy+1,iz+1); c111=_hash(ix+1,iy+1,iz+1)
    return L(L(L(c000,c100,sx), L(c010,c110,sx), sy),
             L(L(c001,c101,sx), L(c011,c111,sx), sy), sz)

def fbm(x, y, z, octaves=3):
    v, amp, tot = 0.0, 0.5, 0.0
    for _ in range(octaves):
        v += amp * vnoise(x, y, z); tot += amp
        x, y, z = x*2.03+11.3, y*2.03+7.7, z*2.03+5.1; amp *= 0.5
    return v / tot

def lerp3(a, b, t):
    return (a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t, a[2]+(b[2]-a[2])*t)
def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)
def mix_into(col, target, m):
    return lerp3(col, target, max(0.0, min(1.0, m)))

# foliage greens shared with the pine (palette v2 family)
F_LOW  = (0.052, 0.115, 0.038)
F_MID  = (0.085, 0.185, 0.062)
F_TOP  = (0.150, 0.275, 0.105)
F_TIP  = (0.230, 0.360, 0.150)
BARK   = (0.165, 0.108, 0.062)
BARK_D = (0.095, 0.062, 0.038)

def paint_boulder(v, n, D):
    x, y, z = v
    base = lerp3((0.055, 0.058, 0.062), (0.185, 0.192, 0.200),
                 fbm(x*3.1, y*3.1, z*3.1))
    spk = fbm(x*55.0, y*55.0, z*55.0)
    f = 0.72 + 0.56 * spk
    col = (base[0]*f, base[1]*f, base[2]*f)
    col = mix_into(col, (0.030, 0.032, 0.035), 0.55 * smoothstep(0.35, 0.05, D["t"]))
    moss = smoothstep(0.25, 0.55, n[2]) * smoothstep(0.40, 0.62, fbm(x*6.0+9.7, y*6.0, z*6.0))
    col = mix_into(col, lerp3((0.045, 0.095, 0.025), (0.130, 0.200, 0.060),
                              fbm(x*22.0, y*22.0, z*22.0)), 0.9 * moss)
    return col

def paint_bush(v, n, D):
    x, y, z = v
    base = lerp3(F_LOW, F_MID, smoothstep(0.05, 0.55, D["t"]))
    base = lerp3(base, F_TOP, smoothstep(0.55, 0.97, D["t"]))
    nb = fbm(x*5.2+3.1, y*5.2, z*5.2)
    nf = fbm(x*40.0, y*40.0+9.2, z*40.0)
    f = (0.80 + 0.40 * nb) * (0.90 + 0.20 * nf)
    f *= 0.62 + 0.38 * D["outside"]          # dark interior, lit shell
    if n[2] < -0.15: f *= 0.85
    col = (base[0]*f, base[1]*f, base[2]*f)
    twig = (1.0 - smoothstep(0.10, 0.30, D["t"])) * (1.0 - smoothstep(0.25, 0.45, D["outside"]))
    col = mix_into(col, lerp3(BARK_D, BARK, nf), twig)
    return col

def paint_fern(v, n, D):
    base = lerp3(F_LOW, F_MID, smoothstep(0.0, 0.45, D["reach"]))
    base = lerp3(base, F_TOP, smoothstep(0.45, 0.85, D["reach"]))
    base = lerp3(base, F_TIP, smoothstep(0.85, 1.05, D["reach"]))
    nf = fbm(v[0]*34.0, v[1]*34.0+4.4, v[2]*34.0)
    f = 0.82 + 0.36 * nf
    if n[2] < 0: f *= 0.78                    # frond undersides darker
    return (base[0]*f, base[1]*f, base[2]*f)

def paint_mushrooms(v, n, D):
    x, y, z = v
    stem = lerp3((0.420, 0.385, 0.330), (0.520, 0.485, 0.420), fbm(x*18.0, y*18.0, z*18.0))
    cap = lerp3((0.015, 0.300, 0.285), (0.045, 0.480, 0.440), smoothstep(0.35, 0.95, D["t"]))
    cap = lerp3(cap, (0.150, 0.720, 0.640), smoothstep(0.80, 1.0, D["t"]) * 0.55)
    capm = D.get("caps", smoothstep(0.25, 0.55, n[2]))
    col = mix_into(stem, cap, capm)
    under = smoothstep(-0.55, -0.15, n[2]) * (1.0 - capm)
    col = mix_into(col, (0.300, 0.270, 0.225), 0.5 * under * smoothstep(0.25, 0.6, D["t"]))
    basem = 1.0 - smoothstep(0.05, 0.16, D["t"])
    col = mix_into(col, lerp3((0.075, 0.095, 0.038), (0.140, 0.165, 0.070),
                              fbm(x*24.0, y*24.0, z*24.0)), basem)
    return col

def _bark_col(x, y, z, along, perp_a, perp_b):
    streak = fbm(along*5.0, perp_a*46.0, perp_b*46.0)
    col = lerp3(BARK_D, BARK, streak)
    f = 0.85 + 0.30 * fbm(x*60.0, y*60.0, z*60.0)
    return (col[0]*f, col[1]*f, col[2]*f)

def paint_fallen_log(v, n, D):
    # bark with lengthwise streaks: noise stretched along the log axis
    streak = fbm(D["a"]*4.0, D["p1"]*42.0, D["p2"]*42.0)
    col = lerp3((0.038, 0.025, 0.015), (0.118, 0.078, 0.044), streak)
    f = 0.78 + 0.44 * fbm(v[0]*60.0, v[1]*60.0, v[2]*60.0)
    col = (col[0]*f, col[1]*f, col[2]*f)
    # pale cut/broken ends with rings
    endm = max(1.0 - smoothstep(0.0, 0.05, D["a01"]), smoothstep(0.95, 1.0, D["a01"]))
    endm *= smoothstep(0.45, 0.75, abs(D["an"]))
    if endm > 0.0:
        ring = 0.70 + 0.52 * (0.5 + 0.5 * math.sin(D["rad"] * 46.0))
        pale = (0.420*ring, 0.330*ring, 0.210*ring)
        col = mix_into(col, pale, endm)
    # moss on top
    moss = smoothstep(0.45, 0.75, n[2]) * smoothstep(0.48, 0.72, fbm(v[0]*7.0+2.2, v[1]*7.0, v[2]*7.0))
    col = mix_into(col, (0.052, 0.102, 0.028), 0.85 * moss)
    return col

def paint_stump(v, n, D):
    x, y, z = v
    streak = fbm(x*44.0, y*44.0, z*5.0)
    col = lerp3((0.038, 0.025, 0.015), (0.115, 0.076, 0.043), streak)
    f = 0.78 + 0.44 * fbm(x*58.0, y*58.0, z*58.0)
    col = (col[0]*f, col[1]*f, col[2]*f)
    topm = smoothstep(0.55, 0.8, n[2]) * smoothstep(0.62, 0.8, D["t"])
    if topm > 0.0:
        ring = 0.72 + 0.50 * (0.5 + 0.5 * math.sin(D["rad"] * 52.0))
        pale = (0.430*ring, 0.340*ring, 0.218*ring)
        col = mix_into(col, pale, topm)
    col = mix_into(col, (0.060, 0.045, 0.030), 0.5 * (1.0 - smoothstep(0.0, 0.18, D["t"])))
    moss = smoothstep(0.3, 0.6, n[2]) * smoothstep(0.5, 0.75, fbm(x*8.0+6.1, y*8.0, z*8.0))
    col = mix_into(col, (0.052, 0.102, 0.028), 0.8 * moss)
    return col

PAINTERS = {"boulder": paint_boulder, "bush": paint_bush, "fern": paint_fern,
            "mushroom-cluster": paint_mushrooms, "fallen-log": paint_fallen_log,
            "stump": paint_stump}
ROUGH = {"boulder": 0.95, "bush": 0.92, "fern": 0.90, "mushroom-cluster": 0.55,
         "fallen-log": 0.94, "stump": 0.94}

# ---------- load, decimate, paint, export ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
bpy.ops.object.select_all(action="DESELECT")
for o in objs: o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
if len(objs) > 1:
    bpy.ops.object.join()
o = bpy.context.view_layer.objects.active
me = o.data
n0 = len(me.vertices)
print(f"[paint_env] {SLUG}: imported verts={n0}")

if n0 > TARGET_VERTS:
    mod = o.modifiers.new("pack_decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = TARGET_VERTS / n0
    bpy.ops.object.modifier_apply(modifier=mod.name)
    print(f"[paint_env] decimated to {len(me.vertices)}")

# the pine lesson, enforced: glTF exports of these meshes split every
# vertex unless coincident verts are welded and split normals cleared.
# Do both UNCONDITIONALLY (the has_custom_normals check lied on the
# boulder: export came out as 89,955 disconnected triangles).
import bmesh
bm = bmesh.new(); bm.from_mesh(me)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
bm.to_mesh(me); bm.free()
print(f"[paint_env] welded -> {len(me.vertices)} verts")
try:
    bpy.ops.mesh.customdata_custom_splitnormals_clear()
    print("[paint_env] cleared custom split normals")
except Exception as e:
    print("[paint_env] split-normal clear skipped:", e)
FLAT = set()  # flat shading splits glTF verts; keep welded smooth exports
for p in me.polygons:
    p.use_smooth = SLUG not in FLAT

vs = [v.co for v in me.vertices]
xs = [c.x for c in vs]; ys = [c.y for c in vs]; zs = [c.z for c in vs]
xmin, xmax, ymin, ymax, zmin, zmax = min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)
cx, cy, cz = (xmin+xmax)/2, (ymin+ymax)/2, (zmin+zmax)/2
span = max(xmax-xmin, ymax-ymin, zmax-zmin) or 1.0
# log axis = longest horizontal dimension
axis_is_x = (xmax-xmin) >= (ymax-ymin)
amin, amax = (xmin, xmax) if axis_is_x else (ymin, ymax)
base_pts = sorted(vs, key=lambda c: c.z)[:max(8, len(vs)//20)]
bx = sum(c.x for c in base_pts)/len(base_pts); by = sum(c.y for c in base_pts)/len(base_pts)
maxreach = max(math.hypot(c.x-bx, c.y-by) + (c.z-zmin)*0.35 for c in vs) or 1.0
maxrad = max(math.hypot(c.x-cx, c.y-cy) for c in vs) or 1.0

# mushroom caps: a raw normal/height score relaxed over mesh edges so the
# cap colour wraps the whole cap instead of dusting only its top
CAP_SCORE = None
if SLUG == "mushroom-cluster":
    raw = []
    for v in me.vertices:
        t = (v.co.z - zmin) / ((zmax - zmin) or 1.0)
        raw.append(max(smoothstep(0.05, 0.40, v.normal.z),
                       0.85 * smoothstep(0.52, 0.78, t)))
    adj = [[] for _ in raw]
    for e in me.edges:
        a, b = e.vertices[0], e.vertices[1]
        adj[a].append(b); adj[b].append(a)
    for _ in range(5):
        raw = [max(s, 0.82 * (sum(raw[j] for j in adj[i]) / max(1, len(adj[i]))))
               if adj[i] else s for i, s in enumerate(raw)]
    CAP_SCORE = raw
    print("[paint_env] mushroom cap field relaxed")

ca = me.color_attributes.new(name="Color", type="FLOAT_COLOR", domain="POINT")
data = ca.data
painter = PAINTERS[SLUG]
for i, v in enumerate(me.vertices):
    x, y, z = v.co.x, v.co.y, v.co.z
    nrm = v.normal
    a = x if axis_is_x else y
    p1, p2 = (y, z) if axis_is_x else (x, z)
    D = {
        "t": (z - zmin) / ((zmax - zmin) or 1.0),
        "rad": math.hypot(x - cx, y - cy) / maxrad,
        "outside": min(1.0, math.sqrt((x-cx)**2 + (y-cy)**2 + (z-cz)**2) / (span * 0.5)),
        "reach": min(1.2, (math.hypot(x-bx, y-by) + (z-zmin)*0.35) / maxreach),
        "a01": (a - amin) / ((amax - amin) or 1.0),
        "a": a, "p1": p1, "p2": p2,
        "an": nrm.x if axis_is_x else nrm.y,
        "caps": CAP_SCORE[i] if CAP_SCORE is not None else None,
    }
    col = painter((x, y, z), (nrm.x, nrm.y, nrm.z), D)
    data[i].color = (col[0], col[1], col[2], 1.0)

mat = bpy.data.materials.new(SLUG + "_procedural")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
vc = mat.node_tree.nodes.new("ShaderNodeVertexColor")
vc.layer_name = "Color"
mat.node_tree.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = ROUGH[SLUG]
me.materials.clear()
me.materials.append(mat)
bpy.ops.export_scene.gltf(filepath=DST, export_format="GLB")
print("[paint_env] exported", DST, os.path.getsize(DST))

# verify the exported file itself (verts + connected components)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=DST)
o2 = [x for x in bpy.context.scene.objects if x.type == "MESH"][0]
me2 = o2.data
parent = list(range(len(me2.vertices)))
def find(a):
    while parent[a] != a:
        parent[a] = parent[parent[a]]; a = parent[a]
    return a
for e in me2.edges:
    ra, rb = find(e.vertices[0]), find(e.vertices[1])
    if ra != rb: parent[ra] = rb
comps = len({find(i) for i in range(len(me2.vertices))})
print(f"[paint_env] verify {SLUG}: verts={len(me2.vertices)} polys={len(me2.polygons)} components={comps} color_attrs={[c.name for c in me2.color_attributes]}")
