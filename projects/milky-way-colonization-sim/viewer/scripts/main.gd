extends Node3D
## milky-way-colonization-sim S0 viewer.
## (StarTable is preloaded rather than class_name-registered so the
## project parses in a bare headless run with no editor import pass.)

const StarTable = preload("res://scripts/star_table.gd")
##
## Renders the pipeline's star table (data/stars.bin) as 3D points
## coloured by spectral class, sized by absolute magnitude, with an
## orbit/fly camera, a "Go to Sol" action, and click-to-pick inspection.
##
## Headless verification (this is what TEST_PLAN.md exercises):
##   godot --headless --path viewer -- --verify [--data=PATH]
## prints VERIFY_PASS lines and exits 0, or VERIFY_FAIL and exits 1.

const SPECTRAL_COLORS := {
	0: Color(0.62, 0.71, 1.0),    # O — blue
	1: Color(0.67, 0.75, 1.0),    # B — blue-white
	2: Color(0.79, 0.85, 1.0),    # A — white-blue
	3: Color(0.97, 0.97, 1.0),    # F — white
	4: Color(1.0, 0.96, 0.91),    # G — warm white (Sol)
	5: Color(1.0, 0.82, 0.63),    # K — orange
	6: Color(1.0, 0.58, 0.34),    # M — red-orange
	7: Color(0.78, 0.78, 0.78),   # Other
	8: Color(0.55, 0.55, 0.55),   # Unknown
}

var table: StarTable
var camera: Camera3D
var info_label: RichTextLabel
var count_label: Label

# Orbit/fly camera state.
var target := Vector3.ZERO
var yaw := 0.6
var pitch := 0.45
var dist := 5200.0
var _dragging := false
var _drag_moved := 0.0
var _last_mouse := Vector2.ZERO


func _ready() -> void:
	var args := _parse_user_args()
	var data_path: String = args.get("data", _default_data_path())
	var t0 := Time.get_ticks_msec()
	table = StarTable.new()
	if table.load(data_path) != OK:
		printerr("VERIFY_FAIL load path=%s" % data_path)
		get_tree().quit(1)
		return
	var load_ms := Time.get_ticks_msec() - t0
	table.build_grid()
	_build_scene()
	_update_camera()
	_show_overview(data_path, load_ms)
	if args.has("measure"):
		_run_measure(load_ms)
	elif args.has("verify"):
		_run_verify(data_path, load_ms)


func _default_data_path() -> String:
	return ProjectSettings.globalize_path("res://") + "../data/stars.bin"


func _parse_user_args() -> Dictionary:
	var out := {}
	for a in OS.get_cmdline_user_args():
		if a == "--verify":
			out["verify"] = true
		elif a == "--measure":
			out["measure"] = true
		elif a.begins_with("--data="):
			out["data"] = a.trim_prefix("--data=")
	return out


func _build_scene() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.01, 0.01, 0.03)
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)

	camera = Camera3D.new()
	camera.near = 0.1
	camera.far = 500000.0
	camera.current = true
	add_child(camera)

	# Star points: one ArrayMesh, PRIMITIVE_POINTS, per-star colour;
	# point size class rides in the colour alpha channel (see shader).
	var verts = table.positions
	var colors := PackedColorArray()
	colors.resize(table.star_count)
	for i in table.star_count:
		var c: Color = SPECTRAL_COLORS.get(int(table.spectral[i]), Color(0.7, 0.7, 0.7))
		c.a = _point_size_base(table.absmag[i])
		colors[i] = c
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_COLOR] = colors
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_POINTS, arrays)
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	var mat := ShaderMaterial.new()
	mat.shader = load("res://star_points.gdshader")
	mi.material_override = mat
	# The point cloud spans the whole local bubble; never frustum-cull it.
	mi.custom_aabb = AABB(Vector3(-60000, -60000, -60000), Vector3(120000, 120000, 120000))
	add_child(mi)

	var layer := CanvasLayer.new()
	add_child(layer)

	var panel := PanelContainer.new()
	panel.position = Vector2(12, 12)
	panel.custom_minimum_size = Vector2(340, 0)
	layer.add_child(panel)
	info_label = RichTextLabel.new()
	info_label.fit_content = true
	info_label.custom_minimum_size = Vector2(340, 120)
	info_label.add_theme_color_override("default_color", Color(0.9, 0.92, 1.0))
	panel.add_child(info_label)

	count_label = Label.new()
	count_label.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	count_label.position = Vector2(-260, 12)
	count_label.size = Vector2(248, 24)
	count_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	layer.add_child(count_label)

	var help := Label.new()
	help.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	help.position = Vector2(12, -56)
	help.size = Vector2(900, 48)
	help.text = "Drag: orbit · Wheel: zoom · WASD/QE: fly · F or button: Go to Sol · Click a star: inspect"
	layer.add_child(help)

	var sol_button := Button.new()
	sol_button.text = "Go to Sol"
	sol_button.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	sol_button.position = Vector2(-120, -52)
	sol_button.size = Vector2(108, 36)
	sol_button.pressed.connect(go_to_sol)
	layer.add_child(sol_button)


func _point_size_base(m: float) -> float:
	# Absolute magnitude → point-size class. absmag 0 means "unknown"
	# (inserted archive hosts carry no photometry) — use a neutral size,
	# never the brightest-star size.
	if m == 0.0:
		return 2.0
	return clampf(6.5 - (m - 4.85) * 0.4, 1.0, 6.5)


func _show_overview(data_path: String, load_ms: int) -> void:
	count_label.text = "%d stars · %d known planets" % [table.star_count, table.planet_count]
	info_label.text = "Milky Way Colonization Sim — S0 data viewer\n%s\nLoaded in %d ms.\nClick any star to inspect it." % [data_path, load_ms]


func _update_camera() -> void:
	var rot := Basis.from_euler(Vector3(pitch, yaw, 0.0))
	camera.global_transform = Transform3D(rot, target + rot * Vector3(0, 0, dist))


func go_to_sol() -> void:
	target = Vector3.ZERO
	dist = 60.0
	_update_camera()
	var sol = table.find_by_name("Sol")
	if sol >= 0:
		show_star_info(sol)


func show_star_info(i: int) -> void:
	var name = table.get_name(i)
	var d = table.positions[i].length()
	var lines := PackedStringArray()
	lines.append("[b]%s[/b]" % name)
	lines.append("Spectral class: %s" % table.spectral_letter(i))
	lines.append("Distance from Sol: %.2f ly" % d)
	if table.teff[i] > 0.0:
		var tflag := " (derived)" if table.flags[i] & StarTable.FLAG_TEMP_DERIVED else ""
		lines.append("Temperature: %.0f K%s" % [table.teff[i], tflag])
	if table.mass[i] > 0.0:
		var mflag := " (derived)" if table.flags[i] & StarTable.FLAG_MASS_DERIVED else ""
		lines.append("Mass: %.2f M☉%s" % [table.mass[i], mflag])
	if table.flags[i] & StarTable.FLAG_SOURCE_EXOPLANET_ARCHIVE:
		lines.append("Host inserted from the NASA Exoplanet Archive (not in HYG).")
	var planets = table.get_planets(i)
	if not planets.is_empty():
		lines.append("\nPlanets (%d):" % planets.size())
		for p in planets:
			var bits := PackedStringArray()
			if float(p["period_days"]) > 0.0:
				bits.append("%.1f d orbit" % float(p["period_days"]))
			if float(p["radius_earth"]) > 0.0:
				bits.append("%.2f R⊕" % float(p["radius_earth"]))
			if float(p["mass_earth"]) > 0.0:
				bits.append("%.1f M⊕" % float(p["mass_earth"]))
			lines.append("· %s — %s (%s, %d)" % [p["name"], ", ".join(bits), p["method"], int(p["disc_year"])])
	info_label.text = "\n".join(lines)


func pick_at_screen_pos(screen_pos: Vector2, max_perp_ly: float) -> int:
	var origin := camera.project_ray_origin(screen_pos)
	var dir := camera.project_ray_normal(screen_pos)
	return table.nearest_to_ray(origin, dir, dist * 4.0 + 20000.0, max_perp_ly)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_WHEEL_UP and mb.pressed:
			dist = clampf(dist * 0.85, 0.5, 80000.0)
			_update_camera()
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN and mb.pressed:
			dist = clampf(dist * 1.18, 0.5, 80000.0)
			_update_camera()
		elif mb.button_index == MOUSE_BUTTON_LEFT:
			if mb.pressed:
				_dragging = true
				_drag_moved = 0.0
				_last_mouse = mb.position
			else:
				if _dragging and _drag_moved < 5.0:
					var perp := clampf(dist * 0.004, 0.5, 25.0)
					var hit := pick_at_screen_pos(mb.position, perp)
					if hit >= 0:
						show_star_info(hit)
				_dragging = false
	elif event is InputEventMouseMotion and _dragging:
		var mm := event as InputEventMouseMotion
		_drag_moved += mm.relative.length()
		yaw -= mm.relative.x * 0.005
		pitch = clampf(pitch - mm.relative.y * 0.005, -1.5, 1.5)
		_update_camera()
	elif event is InputEventKey and event.pressed and not event.echo:
		if (event as InputEventKey).keycode == KEY_F:
			go_to_sol()


func _process(delta: float) -> void:
	var move := Vector3.ZERO
	if Input.is_key_pressed(KEY_W):
		move.z -= 1.0
	if Input.is_key_pressed(KEY_S):
		move.z += 1.0
	if Input.is_key_pressed(KEY_A):
		move.x -= 1.0
	if Input.is_key_pressed(KEY_D):
		move.x += 1.0
	if Input.is_key_pressed(KEY_Q):
		move.y -= 1.0
	if Input.is_key_pressed(KEY_E):
		move.y += 1.0
	if move != Vector3.ZERO:
		var rot := Basis.from_euler(Vector3(pitch, yaw, 0.0))
		target += rot * move.normalized() * dist * 0.6 * delta
		_update_camera()


# ---------------------------------------------------------------- measure

## Load/scale measurement only (used for the ~1M-star extended table):
## reports load time and memory, no anchor assertions, exits 0.
func _run_measure(load_ms: int) -> void:
	var mem_mb := float(Performance.get_monitor(Performance.MEMORY_STATIC)) / 1048576.0
	print("MEASURE load_ms=%d stars=%d planets=%d mem_static_mb=%.1f" % [load_ms, table.star_count, table.planet_count, mem_mb])
	print("MEASURE_DONE")
	get_tree().quit(0)


# ---------------------------------------------------------------- verify

func _run_verify(data_path: String, load_ms: int) -> void:
	var failures := 0
	# 1) Star count matches the pipeline manifest.
	var manifest_path := data_path.get_base_dir() + "/manifest.json"
	var expected := -1
	if FileAccess.file_exists(manifest_path):
		var parsed = JSON.parse_string(FileAccess.get_file_as_string(manifest_path))
		if parsed is Dictionary:
			expected = int(parsed["table"]["stars"])
	if expected > 0 and table.star_count == expected:
		print("VERIFY_PASS star_count=%d matches manifest" % table.star_count)
	else:
		printerr("VERIFY_FAIL star_count table=%d manifest=%d" % [table.star_count, expected])
		failures += 1

	# 2) Sol sits at the origin (heliocentric frame).
	var sol = table.find_by_name("Sol")
	if sol >= 0:
		var d = table.positions[sol].length()
		if d < 0.05:
			print("VERIFY_PASS sol_at_origin dist_ly=%.4f" % d)
		else:
			printerr("VERIFY_FAIL sol dist_ly=%.4f" % d)
			failures += 1
	else:
		printerr("VERIFY_FAIL sol not found")
		failures += 1

	# 3) TRAPPIST-1 (an inserted archive host) carries exactly 7 planets.
	var trap = table.find_by_name("TRAPPIST-1")
	if trap >= 0:
		var planets = table.get_planets(trap)
		if planets.size() == 7:
			var names := PackedStringArray()
			for p in planets:
				names.append(p["name"])
			print("VERIFY_PASS trappist1_planets=7 names=%s" % ", ".join(names))
		else:
			printerr("VERIFY_FAIL trappist1 planet count=%d" % planets.size())
			failures += 1
	else:
		printerr("VERIFY_FAIL TRAPPIST-1 not found")
		failures += 1

	# 4) Programmatic pick: aim the real camera at Sol, project it to
	# the screen, and run the click-pick code path on that position.
	target = Vector3.ZERO
	dist = 300.0
	yaw = 0.6
	pitch = 0.45
	_update_camera()
	if sol >= 0:
		var screen_pos := camera.unproject_position(table.positions[sol])
		var hit := pick_at_screen_pos(screen_pos, 2.0)
		if hit == sol:
			print("VERIFY_PASS pick_sol index=%d" % hit)
		else:
			printerr("VERIFY_FAIL pick_sol hit=%d expected=%d" % [hit, sol])
			failures += 1

	var mem_mb := float(Performance.get_monitor(Performance.MEMORY_STATIC)) / 1048576.0
	print("MEASURE load_ms=%d stars=%d planets=%d mem_static_mb=%.1f" % [load_ms, table.star_count, table.planet_count, mem_mb])
	if failures > 0:
		printerr("VERIFY_FAIL failures=%d" % failures)
		get_tree().quit(1)
	else:
		print("VERIFY_PASS all")
		get_tree().quit(0)
