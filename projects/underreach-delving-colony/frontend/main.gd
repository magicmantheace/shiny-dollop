extends Node3D
## Underreach — S4 Godot frontend (prototype).
##
## Presentation only. The Rust sim core owns every rule; this scene
## renders the bridge's view JSON and sends player commands back
## through the same file bridge (see ../sim/src/bin/bridge.rs).
## The view is a depth slice: one layer (sim y) at a time, with
## layer controls — a pragmatic read on a 3D voxel world.
##
## Delver/critter/prop models are byte-for-byte Game Asset Builder
## catalog files (see README.md in this folder for provenance).
## The dedicated delver asset (arm-separation-gated A-pose build)
## replaced the snow-goblin stand-in on 2026-11-11; the dedicated
## gloam-lurker critter asset replaced the ember-dragon stand-in on
## 2026-11-12 (CRITTER_SCENE below; the dragon file is kept, unused).

const DELVER_SCENE := "res://assets/delver.glb"
const CRITTER_SCENE := "res://assets/gloam-lurker.glb"
const CHEST_SCENE := "res://assets/treasure-chest.glb"
const SHROOM_SCENE := "res://assets/mushroom-cluster.glb"
const LANTERN_SCENE := "res://assets/lantern.glb"
const COT_SCENE := "res://assets/cot.glb"

const JOBS := ["Miner", "Hauler", "Farmer", "Herbalist", "Unassigned"]
const MOVING_STATES := ["ToFace", "ToCamp", "ToBed", "ToPlot", "ToPatient", "ToRescue", "Rescuing"]

var bridge_path := ""
var state_path := "user://state.json"
var cmds_path := "user://cmds.json"
var out_path := "user://out.json"

var view: Dictionary = {}
var pending: Array = []
var playing := true
var ticks_per_step := 3
var speeds := [1, 3, 10, 30]
var speed_idx := 1
var layer := 3
var tool := "inspect"

var cam_rig: Node3D
var camera: Camera3D
var cam_yaw := 0.6
var cam_pitch := 0.95
var cam_dist := 18.0
var cam_target := Vector3(6, -3, 4)

var floors_mmi: MultiMeshInstance3D
var rock_mmi: MultiMeshInstance3D
var props_root: Node3D
var delver_nodes := {}
var critter_nodes := {}
var delver_rows := {}
var rows_signature := ""

var tick_label: Label
var stores_label: Label
var layer_label: Label
var pause_btn: Button
var speed_btn: Button
var delver_list_box: VBoxContainer
var ledger_label: Label
var tool_label: Label

var rng := RandomNumberGenerator.new()

func _ready() -> void:
	rng.randomize()
	# The bridge is an external process: it needs real OS paths,
	# not Godot's user:// scheme.
	state_path = ProjectSettings.globalize_path(state_path)
	cmds_path = ProjectSettings.globalize_path(cmds_path)
	out_path = ProjectSettings.globalize_path(out_path)
	bridge_path = find_bridge()
	build_camera()
	build_world_nodes()
	build_ui()
	var verify := false
	for a in OS.get_cmdline_user_args():
		if a == "--underreach-verify":
			verify = true
	if verify:
		run_verify()
		return
	var scenario := OS.get_environment("UNDERREACH_SCENARIO")
	if scenario == "":
		scenario = "s3"
	init_scenario(scenario)
	var timer := Timer.new()
	timer.wait_time = 0.3
	timer.autostart = true
	timer.timeout.connect(_on_step_timer)
	add_child(timer)

func find_bridge() -> String:
	var env := OS.get_environment("UNDERREACH_BRIDGE")
	if env != "":
		return env
	var rel := ProjectSettings.globalize_path("res://../sim/target/release/bridge")
	if FileAccess.file_exists(rel):
		return rel
	return ProjectSettings.globalize_path("res://../sim/target/debug/bridge")

# ---------------------------------------------------------------------------
# Bridge plumbing
# ---------------------------------------------------------------------------

func bridge_run(args: Array) -> bool:
	var out: Array = []
	var code := OS.execute(bridge_path, args, out, true)
	if code != 0:
		push_warning("bridge failed (%d): %s" % [code, str(out)])
		return false
	return true

func read_file(path: String) -> String:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return ""
	var t := f.get_as_text()
	f.close()
	return t

func write_file(path: String, text: String) -> void:
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return
	f.store_string(text)
	f.close()

func init_scenario(name: String) -> void:
	if not bridge_run(["init", name, out_path]):
		return
	var text := read_file(out_path)
	write_file(state_path, text)
	var parsed = JSON.parse_string(text)
	if parsed is Dictionary:
		view = parsed.get("view", {})
		apply_view()

func step(ticks: int) -> void:
	write_file(cmds_path, JSON.stringify(pending))
	pending.clear()
	if not bridge_run(["step", state_path, cmds_path, str(ticks), out_path]):
		return
	var text := read_file(out_path)
	write_file(state_path, text)
	var parsed = JSON.parse_string(text)
	if parsed is Dictionary:
		view = parsed.get("view", {})
		apply_view()

func _on_step_timer() -> void:
	if playing:
		step(ticks_per_step)

func queue(cmd: Dictionary) -> void:
	pending.append(cmd)

# ---------------------------------------------------------------------------
# Scene building
# ---------------------------------------------------------------------------

func build_camera() -> void:
	cam_rig = Node3D.new()
	add_child(cam_rig)
	camera = Camera3D.new()
	camera.far = 300.0
	cam_rig.add_child(camera)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, -30, 0)
	sun.light_energy = 0.55
	add_child(sun)
	var amb := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.02, 0.02, 0.045)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.32, 0.34, 0.42)
	env.ambient_light_energy = 0.7
	amb.environment = env
	add_child(amb)

func floor_material() -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.vertex_color_use_as_albedo = true
	m.roughness = 0.95
	return m

func build_world_nodes() -> void:
	var box := BoxMesh.new()
	box.size = Vector3(0.98, 0.18, 0.98)
	floors_mmi = MultiMeshInstance3D.new()
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.mesh = box
	mm.mesh.surface_set_material(0, floor_material())
	floors_mmi.multimesh = mm
	add_child(floors_mmi)

	var cube := BoxMesh.new()
	cube.size = Vector3(1.0, 1.0, 1.0)
	rock_mmi = MultiMeshInstance3D.new()
	var mm2 := MultiMesh.new()
	mm2.transform_format = MultiMesh.TRANSFORM_3D
	mm2.use_colors = true
	mm2.mesh = cube
	mm2.mesh.surface_set_material(0, floor_material())
	rock_mmi.multimesh = mm2
	add_child(rock_mmi)

	props_root = Node3D.new()
	add_child(props_root)

func cell_to_world(c: Array) -> Vector3:
	return Vector3(float(c[0]), -float(c[1]), float(c[2]))

func key_of(c: Array) -> String:
	return "%d,%d,%d" % [int(c[0]), int(c[1]), int(c[2])]

func apply_view() -> void:
	if view.is_empty():
		return
	rebuild_layer()
	sync_entities()
	update_hud()

func rebuild_layer() -> void:
	var carved: Array = view.get("carved", [])
	var lit_set := {}
	for c in view.get("lit", []):
		lit_set[key_of(c)] = true
	var carved_set := {}
	for c in carved:
		carved_set[key_of(c)] = true

	var floors: Array = [] # [Transform3D, Color]
	var rocks: Array = []
	var face_by_key := {}
	for f in view.get("faces", []):
		face_by_key[key_of(f["rock"])] = f

	for c in carved:
		if int(c[1]) != layer:
			continue
		var p := cell_to_world(c)
		var col := Color(0.5, 0.42, 0.32) if lit_set.has(key_of(c)) else Color(0.07, 0.08, 0.13)
		floors.append([Transform3D(Basis(), p + Vector3(0, -0.09, 0)), col])
		# Rock rim: solid in-layer neighbours of open cells.
		for d in [[1, 0], [-1, 0], [0, 1], [0, -1]]:
			var n := [int(c[0]) + d[0], layer, int(c[2]) + d[1]]
			if not carved_set.has(key_of(n)):
				var rp := Vector3(float(n[0]), -float(layer), float(n[2]))
				var rc := Color(0.16, 0.14, 0.13)
				if face_by_key.has(key_of(n)):
					var y = face_by_key[key_of(n)]["yield"]
					rc = Color(0.6, 0.38, 0.16) if y == "Ore" else Color(0.2, 0.55, 0.42)
				rocks.append([Transform3D(Basis(), rp), rc])

	fill_multimesh(floors_mmi, floors)
	fill_multimesh(rock_mmi, rocks)
	rebuild_props()
	cam_target = Vector3(cam_target.x, -float(layer), cam_target.z)

func fill_multimesh(mmi: MultiMeshInstance3D, items: Array) -> void:
	var mm := mmi.multimesh
	mm.instance_count = items.size()
	for i in items.size():
		mm.set_instance_transform(i, items[i][0])
		mm.set_instance_color(i, items[i][1])

func make_lantern_node(tier: int) -> Node3D:
	var root := Node3D.new()
	# Visible prop: the builder's Tier-1 lantern GLB (untextured
	# vertex-colour prop), scaled to ~0.6 units tall. The OmniLight
	# below is what actually lights the network; the prop is unlit
	# geometry, so a small emissive marker stays at the flame point
	# to keep placed lanterns readable in the dark.
	var prop := instantiate_scaled(LANTERN_SCENE, 0.6)
	root.add_child(prop)
	call_deferred("measure_and_scale", prop)
	var glow := MeshInstance3D.new()
	var glow_sphere := SphereMesh.new()
	glow_sphere.radius = 0.05
	glow_sphere.height = 0.1
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(1.0, 0.72, 0.3)
	mat.emission_enabled = true
	mat.emission = Color(1.0, 0.62, 0.2)
	mat.emission_energy_multiplier = 2.4
	glow_sphere.material = mat
	glow.mesh = glow_sphere
	glow.position = Vector3(0, 0.42, 0)
	root.add_child(glow)
	var light := OmniLight3D.new()
	light.light_color = Color(1.0, 0.7, 0.35)
	light.light_energy = 1.1
	light.omni_range = 3.0 + float(tier)
	light.position = Vector3(0, 0.5, 0)
	root.add_child(light)
	return root

func instantiate_scaled(path: String, target_h: float) -> Node3D:
	var packed: PackedScene = load(path)
	var node: Node3D = packed.instantiate()
	node.set_meta("target_h", target_h)
	node.set_meta("needs_scale", true)
	return node

func measure_and_scale(node: Node3D) -> void:
	if not node.has_meta("needs_scale"):
		return
	node.remove_meta("needs_scale")
	var target_h: float = node.get_meta("target_h")
	var aabb := AABB()
	var first := true
	var inv := node.global_transform.affine_inverse()
	for mi in node.find_children("*", "MeshInstance3D", true, false):
		var m := mi as MeshInstance3D
		var box := inv * m.global_transform * m.get_aabb()
		if first:
			aabb = box
			first = false
		else:
			aabb = aabb.merge(box)
	if first or aabb.size.y <= 0.01:
		return
	var s := target_h / aabb.size.y
	node.scale = Vector3.ONE * s

func rebuild_props() -> void:
	for child in props_root.get_children():
		child.queue_free()
	for l in view.get("lanterns", []):
		if int(l["pos"][1]) != layer:
			continue
		var n := make_lantern_node(int(l["tier"]))
		n.position = cell_to_world(l["pos"])
		props_root.add_child(n)
	var stock: Array = view.get("stockpile", [])
	if not stock.is_empty() and int(stock[1]) == layer:
		var chest := instantiate_scaled(CHEST_SCENE, 0.62)
		chest.position = cell_to_world(stock) + Vector3(0, 0.02, 0)
		props_root.add_child(chest)
		call_deferred("measure_and_scale", chest)
	for p in view.get("plots", []):
		if int(p["pos"][1]) != layer:
			continue
		var sh := instantiate_scaled(SHROOM_SCENE, 0.5)
		sh.position = cell_to_world(p["pos"]) + Vector3(0, 0.02, 0)
		props_root.add_child(sh)
		call_deferred("measure_and_scale", sh)
	for b in view.get("beds", []):
		if int(b[1]) != layer:
			continue
		# Builder cot prop. Its natural proportions are ~6.1 long ×
		# 2.0 high, so a height target of 0.31 scales it to ~0.95
		# long — the footprint of the plain box it replaces.
		var bed := instantiate_scaled(COT_SCENE, 0.31)
		bed.position = cell_to_world(b) + Vector3(0, 0.02, 0)
		props_root.add_child(bed)
		call_deferred("measure_and_scale", bed)

# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------

func find_anim(node: Node3D) -> AnimationPlayer:
	for c in node.find_children("*", "AnimationPlayer", true, false):
		return c as AnimationPlayer
	return null

func pick_anim(anim: AnimationPlayer, state: String, moving: bool) -> void:
	if anim == null:
		return
	var names := anim.get_animation_list()
	if names.is_empty():
		return
	var want := ""
	var pref := "walk" if moving else "idle"
	for n in names:
		if n.to_lower().contains(pref):
			want = n
			break
	if want == "":
		want = names[0]
	if anim.current_animation != want:
		anim.play(want)

func sync_entities() -> void:
	var seen := {}
	for d in view.get("delvers", []):
		var id := int(d["id"])
		seen[id] = true
		if not delver_nodes.has(id):
			var node := instantiate_scaled(DELVER_SCENE, 0.95)
			var label := Label3D.new()
			label.text = d["name"]
			label.font_size = 48
			label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
			label.position = Vector3(0, 1.25, 0)
			label.modulate = Color(0.95, 0.9, 0.8)
			node.add_child(label)
			add_child(node)
			node.position = cell_to_world(d["pos"])
			call_deferred("measure_and_scale", node)
			delver_nodes[id] = {
				"root": node, "anim": find_anim(node), "label": label,
				"target": cell_to_world(d["pos"]), "state": str(d["state"]),
			}
		var rec: Dictionary = delver_nodes[id]
		rec["target"] = cell_to_world(d["pos"])
		rec["state"] = str(d["state"])
		var node: Node3D = rec["root"]
		node.visible = int(d["pos"][1]) == layer
		var label: Label3D = rec["label"]
		if str(d["state"]) == "Downed":
			label.modulate = Color(1.0, 0.35, 0.3)
			node.rotation_degrees = Vector3(0, node.rotation_degrees.y, 78)
		else:
			label.modulate = Color(0.95, 0.9, 0.8)
			node.rotation_degrees = Vector3(0, node.rotation_degrees.y, 0)
	for id in delver_nodes.keys():
		if not seen.has(id):
			delver_nodes[id]["root"].queue_free()
			delver_nodes.erase(id)

	var seen_c := {}
	for c in view.get("critters", []):
		var id := int(c["id"])
		seen_c[id] = true
		if not critter_nodes.has(id):
			var node := instantiate_scaled(CRITTER_SCENE, 1.05)
			tint_dark(node)
			add_child(node)
			node.position = cell_to_world(c["pos"])
			call_deferred("measure_and_scale", node)
			critter_nodes[id] = {
				"root": node, "anim": find_anim(node),
				"target": cell_to_world(c["pos"]),
			}
		var rec: Dictionary = critter_nodes[id]
		rec["target"] = cell_to_world(c["pos"])
		rec["root"].visible = int(c["pos"][1]) == layer
	for id in critter_nodes.keys():
		if not seen_c.has(id):
			critter_nodes[id]["root"].queue_free()
			critter_nodes.erase(id)

func tint_dark(node: Node3D) -> void:
	for mi in node.find_children("*", "MeshInstance3D", true, false):
		var m := mi as MeshInstance3D
		for s in m.get_surface_override_material_count():
			pass
		var mat := m.get_active_material(0)
		if mat is BaseMaterial3D:
			var dup := mat.duplicate() as BaseMaterial3D
			dup.albedo_color = Color(0.32, 0.28, 0.42) * dup.albedo_color
			m.set_surface_override_material(0, dup)

func _process(delta: float) -> void:
	# Camera rig.
	var off := Vector3(
		sin(cam_yaw) * cos(cam_pitch), sin(cam_pitch), cos(cam_yaw) * cos(cam_pitch)
	) * cam_dist
	camera.global_position = cam_target + off
	camera.look_at(cam_target, Vector3.UP)
	# Entities glide toward their sim cells and animate.
	for id in delver_nodes:
		var rec: Dictionary = delver_nodes[id]
		var node: Node3D = rec["root"]
		if not node.visible:
			continue
		var target: Vector3 = rec["target"]
		var before := node.position
		node.position = node.position.lerp(target, minf(1.0, delta * 6.0))
		var moved := node.position.distance_to(before) > 0.002
		if moved:
			var dir := target - node.position
			dir.y = 0
			if dir.length() > 0.05:
				var goal := atan2(dir.x, dir.z)
				node.rotation.y = lerp_angle(node.rotation.y, goal, minf(1.0, delta * 8.0))
		pick_anim(rec["anim"], rec["state"], moved or MOVING_STATES.has(rec["state"]))
	for id in critter_nodes:
		var rec: Dictionary = critter_nodes[id]
		var node: Node3D = rec["root"]
		if not node.visible:
			continue
		var target: Vector3 = rec["target"]
		node.position = node.position.lerp(target, minf(1.0, delta * 5.0))
		pick_anim(rec["anim"], "", node.position.distance_to(target) > 0.05)

# ---------------------------------------------------------------------------
# Input / picking
# ---------------------------------------------------------------------------

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_WHEEL_UP and mb.pressed:
			cam_dist = clampf(cam_dist - 1.5, 6.0, 42.0)
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN and mb.pressed:
			cam_dist = clampf(cam_dist + 1.5, 6.0, 42.0)
		elif mb.button_index == MOUSE_BUTTON_LEFT and mb.pressed and tool != "inspect":
			apply_tool_at_mouse(mb.position)
	if event is InputEventMouseMotion:
		var mm := event as InputEventMouseMotion
		if (mm.button_mask & MOUSE_BUTTON_MASK_RIGHT) != 0 or (mm.button_mask & MOUSE_BUTTON_MASK_MIDDLE) != 0:
			cam_yaw -= mm.relative.x * 0.005
			cam_pitch = clampf(cam_pitch + mm.relative.y * 0.005, 0.15, 1.35)
	if event is InputEventKey:
		var k := event as InputEventKey
		if k.pressed:
			match k.keycode:
				KEY_Q: cam_target.x -= 1.0
				KEY_E: cam_target.x += 1.0
				KEY_W: cam_target.z -= 1.0
				KEY_S: cam_target.z += 1.0

func apply_tool_at_mouse(mouse_pos: Vector2) -> void:
	var origin := camera.project_ray_origin(mouse_pos)
	var dir := camera.project_ray_normal(mouse_pos)
	if absf(dir.y) < 0.0001:
		return
	var plane_y := -float(layer)
	var t := (plane_y - origin.y) / dir.y
	if t < 0:
		return
	var hit := origin + dir * t
	var cx := int(round(hit.x))
	var cz := int(round(hit.z))
	var dims: Array = view.get("dims", [0, 0, 0])
	if cx < 0 or cz < 0 or cx >= int(dims[0]) or cz >= int(dims[2]):
		return
	match tool:
		"carve":
			queue({"cmd": "carve", "pos": [cx, layer, cz]})
		"lantern":
			queue({"cmd": "lantern", "pos": [cx, layer, cz], "tier": 1})
		"plant":
			queue({"cmd": "plant", "pos": [cx, layer, cz]})

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

func make_button(text: String, fn_ref: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.pressed.connect(fn_ref)
	return b

func build_ui() -> void:
	var canvas := CanvasLayer.new()
	add_child(canvas)

	var top := HBoxContainer.new()
	top.set_anchors_preset(Control.PRESET_TOP_WIDE)
	top.add_theme_constant_override("separation", 10)
	canvas.add_child(top)
	tick_label = Label.new()
	stores_label = Label.new()
	top.add_child(tick_label)
	top.add_child(stores_label)
	pause_btn = make_button("Pause", func() -> void:
		playing = not playing
		pause_btn.text = "Play" if not playing else "Pause"
	)
	top.add_child(pause_btn)
	speed_btn = make_button("Speed ×%d" % ticks_per_step, func() -> void:
		speed_idx = (speed_idx + 1) % speeds.size()
		ticks_per_step = speeds[speed_idx]
		speed_btn.text = "Speed ×%d" % ticks_per_step
	)
	top.add_child(speed_btn)
	layer_label = Label.new()
	top.add_child(make_button("Layer −", func() -> void: set_layer(layer - 1)))
	top.add_child(layer_label)
	top.add_child(make_button("Layer +", func() -> void: set_layer(layer + 1)))

	var left := VBoxContainer.new()
	left.set_anchors_preset(Control.PRESET_LEFT_WIDE)
	left.position = Vector2(8, 44)
	left.add_theme_constant_override("separation", 4)
	canvas.add_child(left)
	left.add_child(Label.new())
	var scen_label := Label.new()
	scen_label.text = "Scenario"
	left.add_child(scen_label)
	for s in ["s1", "s2", "s3", "s5"]:
		var sn: String = s
		left.add_child(make_button(sn.to_upper(), func() -> void: init_scenario(sn)))
	var tool_head := Label.new()
	tool_head.text = "Tool (click a cell)"
	left.add_child(tool_head)
	for t in ["inspect", "carve", "lantern", "plant"]:
		var tn: String = t
		left.add_child(make_button(tn.capitalize(), func() -> void:
			tool = tn
			tool_label.text = "Tool: " + tn
		))
	tool_label = Label.new()
	tool_label.text = "Tool: inspect"
	left.add_child(tool_label)
	var act := Label.new()
	act.text = "Colony"
	left.add_child(act)
	left.add_child(make_button("Light the way", func() -> void: queue({"cmd": "light_the_way"})))
	left.add_child(make_button("Light the deep (S5)", func() -> void: queue({"cmd": "light_the_deep"})))
	left.add_child(make_button("Craft mask (2 goods)", func() -> void: queue({"cmd": "craft_mask"})))

	var right := PanelContainer.new()
	right.set_anchors_preset(Control.PRESET_RIGHT_WIDE)
	right.offset_left = -300
	canvas.add_child(right)
	delver_list_box = VBoxContainer.new()
	right.add_child(delver_list_box)

	var bottom := PanelContainer.new()
	bottom.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	bottom.offset_top = -118
	canvas.add_child(bottom)
	ledger_label = Label.new()
	ledger_label.autowrap_mode = TextServer.AUTOWRAP_OFF
	bottom.add_child(ledger_label)

func set_layer(l: int) -> void:
	var dims: Array = view.get("dims", [0, 12, 0])
	layer = clampi(l, 0, int(dims[1]) - 1)
	apply_view()

func update_hud() -> void:
	var st: Dictionary = view.get("stores", {})
	tick_label.text = "Tick %d" % int(view.get("tick", 0))
	stores_label.text = "Ore %d · Goods %d · Food %d · Oil %d · Masks %d · Delvers %d · Critters %d" % [
		int(st.get("ore", 0)), int(st.get("goods", 0)), int(st.get("food", 0)),
		int(st.get("fungal_oil", 0)), int(st.get("masks", 0)),
		(view.get("delvers", []) as Array).size(), (view.get("critters", []) as Array).size(),
	]
	layer_label.text = "Depth %d" % layer
	update_delver_panel()
	var lines: Array = []
	var led: Array = view.get("ledger", [])
	for i in mini(7, led.size()):
		var e: Dictionary = led[led.size() - 1 - i]
		lines.append("[%d] %s" % [int(e["tick"]), str(e["detail"])])
	ledger_label.text = "\n".join(lines)

func update_delver_panel() -> void:
	var delvers: Array = view.get("delvers", [])
	var sig_parts: Array = []
	for d in delvers:
		sig_parts.append("%d:%s" % [int(d["id"]), str(d["job"])])
	var sig := "|".join(sig_parts)
	if sig != rows_signature:
		rows_signature = sig
		for c in delver_list_box.get_children():
			c.queue_free()
		delver_rows.clear()
		for d in delvers:
			var id := int(d["id"])
			var box := VBoxContainer.new()
			var name_label := Label.new()
			name_label.text = str(d["name"])
			box.add_child(name_label)
			var opt := OptionButton.new()
			for j in JOBS:
				opt.add_item(j)
			opt.selected = maxi(0, JOBS.find(str(d["job"])))
			var did := id
			opt.item_selected.connect(func(idx: int) -> void:
				queue({"cmd": "job", "id": did, "job": JOBS[idx]})
			)
			box.add_child(opt)
			var info := Label.new()
			info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			box.add_child(info)
			delver_list_box.add_child(box)
			delver_rows[id] = info
	for d in delvers:
		var id := int(d["id"])
		if delver_rows.has(id):
			var info: Label = delver_rows[id]
			var clock := ""
			if d.get("dark_clock") != null:
				clock = " · CLOCK %d" % int(d["dark_clock"])
			info.text = "%s · HP %.0f · E %.0f · F %.0f · M %.0f%s%s" % [
				str(d["state"]), float(d["hp"]), float(d["energy"]), float(d["hunger"]),
				float(d["morale"]), (" · spore %.0f" % float(d["spore"])) if float(d["spore"]) > 0.0 else "",
				clock,
			]

# ---------------------------------------------------------------------------
# Headless verification (--underreach-verify)
# ---------------------------------------------------------------------------

func run_verify() -> void:
	playing = false
	init_scenario("s3")
	if view.is_empty():
		print("UNDERREACH_VERIFY_FAIL no view from bridge")
		get_tree().quit(1)
		return
	queue({"cmd": "light_the_way"})
	for i in 40:
		step(100)
	var goods := int(view.get("stores", {}).get("goods", 0))
	var floors := floors_mmi.multimesh.instance_count
	var ok := goods >= 1 and floors > 0 and delver_nodes.size() == (view.get("delvers", []) as Array).size()
	if ok:
		print("UNDERREACH_VERIFY_PASS goods=%d delvers=%d floor_instances=%d tick=%d" % [
			goods, delver_nodes.size(), floors, int(view.get("tick", 0))])
		get_tree().quit(0)
	else:
		print("UNDERREACH_VERIFY_FAIL goods=%d floors=%d nodes=%d" % [goods, floors, delver_nodes.size()])
		get_tree().quit(1)
