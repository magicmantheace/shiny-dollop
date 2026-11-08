extends Node3D
## milky-way-colonization-sim viewer / game frontend (S0 viewer, S2 game).
## (StarTable and BridgeClient are preloaded rather than
## class_name-registered so the project parses in a bare headless run
## with no editor import pass.)

const StarTable = preload("res://scripts/star_table.gd")
const BridgeClient = preload("res://scripts/bridge_client.gd")
##
## Renders the pipeline's star table (data/stars.bin) as 3D points
## coloured by spectral class, sized by absolute magnitude, with an
## orbit/fly camera, a "Go to Sol" action, and click-to-pick inspection.
##
## From S2 this is also the game frontend: all simulation state lives
## in the Rust core and is reached only through the sim-bridge binary
## (see scripts/bridge_client.gd). The UI never invents sim state —
## it renders the last view + inspect responses from the bridge.
##
## Headless verification (this is what TEST_PLAN.md exercises):
##   godot --headless --path viewer -- --verify [--data=PATH]
## prints VERIFY_PASS lines and exits 0, or VERIFY_FAIL and exits 1.
##   godot --headless --path viewer -- --verify-s2 --bridge=PATH
## additionally runs a scripted end-to-end session against the real
## bridge, printing S2_VERIFY_PASS lines.

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

# Speed ladder: days per real second, with the short button label and
# the long label for each rung.
const SPEED_RATES := [0.0, 1.0 / 86400.0, 1.0 / 3600.0, 1.0 / 60.0, 1.0, 10.0]
const SPEED_BUTTON_LABELS := ["❚❚ Pause", "1×", "1/hr", "1/min", "1/sec", "10/sec"]
const SPEED_LABELS := ["Paused", "1× (1 day/day)", "1 day/hour", "1 day/min", "1 day/sec", "10 days/sec"]

const SPEC_IDS := ["industrial", "agricultural", "refinery", "research", "fortress", "trade_hub", "shipyard"]
const SPEC_LABELS := ["Industrial", "Agricultural", "Refinery", "Research", "Fortress", "Trade Hub", "Shipyard"]

const EVENT_TEXT := {
	"campaign_started": "Campaign started",
	"survey_started": "Survey started",
	"survey_completed": "Survey completed",
	"system_claimed": "System claimed",
	"ship_dispatched": "Ship dispatched",
	"ship_arrived": "Ship arrived",
	"ship_stranded": "Ship stranded",
	"ship_refuelled": "Ship refuelled",
	"ship_built": "Ship built",
	"colony_founded": "Colony founded",
	"colony_abandoned": "Colony abandoned",
	"specialization_set": "Specialization set",
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

# ------------------------------------------------------------ game state

var user_args: Dictionary = {}
var data_path: String = ""
var bridge_client = null
var bridge_path: String = ""

var session_active := false
var save_path: String = ""
var view_data: Dictionary = {}
var event_cursor: int = 0
var selected_system: int = -1
var selected_ship: int = -1
var speed_idx: int = 0
var day_accumulator: float = 0.0
var last_bridge_ms: int = 0
var inspect_data: Dictionary = {}
var inspect_warning: String = ""
var event_log_entries: Array = []
var saves_list_data: Array = []

# UI references.
var hud_label: Label
var hud_stats_label: Label
var speed_buttons: Array = []
var message_label: Label
var marker_mi: MeshInstance3D
var range_mi: MeshInstance3D
var ships_box: VBoxContainer
var claim_button: Button
var build_surveyor_button: Button
var build_colony_button: Button
var spec_row: HBoxContainer
var spec_option: OptionButton
var send_survey_button: Button
var send_colonize_button: Button
var send_move_button: Button
var survey_this_button: Button
var found_button: Button
var refuel_button: Button
var menu_overlay: Control
var menu_status_label: Label
var seed_spin: SpinBox
var save_name_edit: LineEdit
var saves_item_list: ItemList
var elapsed_spin: SpinBox
var eventlog_overlay: Control
var eventlog_text: RichTextLabel
var catchup_overlay: Control
var catchup_title: Label
var catchup_body: RichTextLabel
var catchup_events_text: RichTextLabel


func _ready() -> void:
	user_args = _parse_user_args()
	data_path = str(user_args.get("data", _default_data_path()))
	var t0 := Time.get_ticks_msec()
	table = StarTable.new()
	if table.load(data_path) != OK:
		printerr("VERIFY_FAIL load path=%s" % data_path)
		get_tree().quit(1)
		return
	var load_ms := Time.get_ticks_msec() - t0
	table.build_grid()
	_setup_bridge()
	_build_scene()
	_update_camera()
	_show_overview(data_path, load_ms)
	_refresh_saves_list()
	if user_args.has("measure"):
		_run_measure(load_ms)
	elif user_args.has("verify_s2"):
		if _run_verify_checks(data_path, load_ms) > 0:
			get_tree().quit(1)
		else:
			_run_verify_s2()
	elif user_args.has("verify"):
		var failures := _run_verify_checks(data_path, load_ms)
		get_tree().quit(1 if failures > 0 else 0)


func _default_data_path() -> String:
	return ProjectSettings.globalize_path("res://") + "../data/stars.bin"


func _parse_user_args() -> Dictionary:
	var out := {}
	for a in OS.get_cmdline_user_args():
		if a == "--verify":
			out["verify"] = true
		elif a == "--verify-s2":
			out["verify_s2"] = true
		elif a == "--measure":
			out["measure"] = true
		elif a.begins_with("--data="):
			out["data"] = a.trim_prefix("--data=")
		elif a.begins_with("--bridge="):
			out["bridge"] = a.trim_prefix("--bridge=")
	return out


func _setup_bridge() -> void:
	bridge_client = BridgeClient.new()
	var explicit := str(user_args.get("bridge", ""))
	if user_args.has("verify_s2") and explicit != "":
		# Verify mode names the exact binary under test; do not let
		# the candidate search substitute a different one.
		bridge_path = explicit
	else:
		bridge_path = bridge_client.find_bridge(explicit)
	var bridge_data := data_path
	if bridge_data.begins_with("res://"):
		bridge_data = ProjectSettings.globalize_path(bridge_data)
	bridge_client.setup(bridge_data, bridge_path, ProjectSettings.globalize_path("user://bridge/"))


# ------------------------------------------------------------------ scene

func _make_points_instance() -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var mat := ShaderMaterial.new()
	mat.shader = load("res://star_points.gdshader")
	mi.material_override = mat
	mi.custom_aabb = AABB(Vector3(-60000, -60000, -60000), Vector3(120000, 120000, 120000))
	add_child(mi)
	return mi


func _set_points(mi: MeshInstance3D, verts: PackedVector3Array, colors: PackedColorArray) -> void:
	if verts.is_empty():
		mi.mesh = null
		return
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_COLOR] = colors
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_POINTS, arrays)
	mi.mesh = mesh


func _action_button(text: String, handler: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.visible = false
	b.pressed.connect(handler)
	return b


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

	# Game markers (surveyed / claimed / colonized systems) and the
	# selected ship's reachable-range layer reuse the same shader.
	marker_mi = _make_points_instance()
	range_mi = _make_points_instance()

	var layer := CanvasLayer.new()
	add_child(layer)

	_build_hud(layer)
	_build_system_panel(layer)
	_build_ships_panel(layer)

	count_label = Label.new()
	count_label.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	count_label.position = Vector2(-260, 52)
	count_label.size = Vector2(248, 24)
	count_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	layer.add_child(count_label)

	message_label = Label.new()
	message_label.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	message_label.position = Vector2(12, -84)
	message_label.size = Vector2(1100, 24)
	message_label.add_theme_color_override("font_color", Color(1.0, 0.95, 0.75))
	layer.add_child(message_label)

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

	_build_menu(layer)
	_build_event_log(layer)
	_build_catchup(layer)


func _build_hud(layer: CanvasLayer) -> void:
	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_TOP_WIDE)
	panel.offset_bottom = 44
	layer.add_child(panel)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	panel.add_child(row)

	hud_label = Label.new()
	hud_label.text = "—"
	row.add_child(hud_label)
	hud_stats_label = Label.new()
	hud_stats_label.text = ""
	row.add_child(hud_stats_label)

	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(spacer)

	var speed_caption := Label.new()
	speed_caption.text = "Speed:"
	row.add_child(speed_caption)
	speed_buttons.clear()
	for i in SPEED_BUTTON_LABELS.size():
		var b := Button.new()
		b.text = SPEED_BUTTON_LABELS[i]
		b.toggle_mode = true
		b.tooltip_text = SPEED_LABELS[i]
		b.pressed.connect(_on_speed_pressed.bind(i))
		row.add_child(b)
		speed_buttons.append(b)

	var save_button := Button.new()
	save_button.text = "Save"
	save_button.pressed.connect(_on_save_pressed)
	row.add_child(save_button)
	var log_button := Button.new()
	log_button.text = "Event Log"
	log_button.pressed.connect(_on_event_log_pressed)
	row.add_child(log_button)
	var menu_button := Button.new()
	menu_button.text = "Menu"
	menu_button.pressed.connect(_on_menu_pressed)
	row.add_child(menu_button)
	_update_speed_buttons()


func _build_system_panel(layer: CanvasLayer) -> void:
	var panel := PanelContainer.new()
	panel.position = Vector2(12, 56)
	panel.custom_minimum_size = Vector2(340, 0)
	layer.add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 4)
	panel.add_child(box)
	info_label = RichTextLabel.new()
	info_label.fit_content = true
	info_label.custom_minimum_size = Vector2(340, 120)
	info_label.add_theme_color_override("default_color", Color(0.9, 0.92, 1.0))
	box.add_child(info_label)

	claim_button = _action_button("Claim System — 25 cr", _on_claim_pressed)
	box.add_child(claim_button)
	build_surveyor_button = _action_button("Build Surveyor", _on_build_surveyor_pressed)
	box.add_child(build_surveyor_button)
	build_colony_button = _action_button("Build Colony Ship", _on_build_colony_pressed)
	box.add_child(build_colony_button)

	spec_row = HBoxContainer.new()
	spec_row.visible = false
	spec_option = OptionButton.new()
	for i in SPEC_IDS.size():
		spec_option.add_item(SPEC_LABELS[i], i)
	spec_option.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	spec_row.add_child(spec_option)
	var spec_button := Button.new()
	spec_button.text = "Set Specialization"
	spec_button.pressed.connect(_on_specialize_pressed)
	spec_row.add_child(spec_button)
	box.add_child(spec_row)

	send_survey_button = _action_button("Send Ship Here — Survey", _on_send_survey_pressed)
	box.add_child(send_survey_button)
	send_colonize_button = _action_button("Send Ship Here — Colonize", _on_send_colonize_pressed)
	box.add_child(send_colonize_button)
	send_move_button = _action_button("Send Ship Here — Move", _on_send_move_pressed)
	box.add_child(send_move_button)
	survey_this_button = _action_button("Survey This System", _on_survey_this_pressed)
	box.add_child(survey_this_button)
	found_button = _action_button("Found Colony Here", _on_found_pressed)
	box.add_child(found_button)
	refuel_button = _action_button("Refuel Ship Here", _on_refuel_pressed)
	box.add_child(refuel_button)


func _build_ships_panel(layer: CanvasLayer) -> void:
	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	panel.position = Vector2(-372, 84)
	panel.size = Vector2(360, 260)
	panel.custom_minimum_size = Vector2(360, 0)
	layer.add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 4)
	panel.add_child(box)
	var title := Label.new()
	title.text = "Ships"
	title.add_theme_font_size_override("font_size", 18)
	box.add_child(title)
	ships_box = VBoxContainer.new()
	ships_box.add_theme_constant_override("separation", 2)
	box.add_child(ships_box)
	var hint := Label.new()
	hint.text = "Select a ship, click a star, then use the order buttons in the system panel."
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(hint)


func _overlay_base(layer: CanvasLayer) -> Control:
	var overlay := Control.new()
	overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.65)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	overlay.add_child(dim)
	layer.add_child(overlay)
	return overlay


func _build_menu(layer: CanvasLayer) -> void:
	menu_overlay = _overlay_base(layer)
	var centre := CenterContainer.new()
	centre.set_anchors_preset(Control.PRESET_FULL_RECT)
	menu_overlay.add_child(centre)
	var panel := PanelContainer.new()
	centre.add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 8)
	box.custom_minimum_size = Vector2(460, 0)
	panel.add_child(box)

	var title := Label.new()
	title.text = "Milky Way Colonization Sim"
	title.add_theme_font_size_override("font_size", 28)
	box.add_child(title)

	var seed_row := HBoxContainer.new()
	var seed_caption := Label.new()
	seed_caption.text = "Seed"
	seed_row.add_child(seed_caption)
	seed_spin = SpinBox.new()
	seed_spin.min_value = 0
	seed_spin.max_value = 999999
	seed_spin.step = 1
	seed_spin.value = 42
	seed_spin.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	seed_row.add_child(seed_spin)
	box.add_child(seed_row)

	var name_row := HBoxContainer.new()
	var name_caption := Label.new()
	name_caption.text = "Save name"
	name_row.add_child(name_caption)
	save_name_edit = LineEdit.new()
	save_name_edit.text = "campaign1"
	save_name_edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_row.add_child(save_name_edit)
	box.add_child(name_row)

	var new_button := Button.new()
	new_button.text = "New Campaign"
	new_button.pressed.connect(_on_new_campaign_pressed)
	box.add_child(new_button)

	var saves_caption := Label.new()
	saves_caption.text = "Saved campaigns"
	box.add_child(saves_caption)
	saves_item_list = ItemList.new()
	saves_item_list.custom_minimum_size = Vector2(460, 120)
	box.add_child(saves_item_list)
	var load_button := Button.new()
	load_button.text = "Load Selected"
	load_button.pressed.connect(_on_load_pressed)
	box.add_child(load_button)

	var elapsed_row := HBoxContainer.new()
	var elapsed_caption := Label.new()
	elapsed_caption.text = "Debug: pretend N days passed on load"
	elapsed_row.add_child(elapsed_caption)
	elapsed_spin = SpinBox.new()
	elapsed_spin.min_value = 0
	elapsed_spin.max_value = 3650
	elapsed_spin.step = 1
	elapsed_spin.value = 0
	elapsed_row.add_child(elapsed_spin)
	box.add_child(elapsed_row)

	menu_status_label = Label.new()
	menu_status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	menu_status_label.add_theme_color_override("font_color", Color(1.0, 0.8, 0.7))
	box.add_child(menu_status_label)
	if bridge_path == "":
		menu_status_label.text = "Bridge binary not found — campaigns are unavailable. The star viewer still works."
	menu_overlay.visible = true


func _build_event_log(layer: CanvasLayer) -> void:
	eventlog_overlay = _overlay_base(layer)
	var centre := CenterContainer.new()
	centre.set_anchors_preset(Control.PRESET_FULL_RECT)
	eventlog_overlay.add_child(centre)
	var panel := PanelContainer.new()
	centre.add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	box.custom_minimum_size = Vector2(620, 420)
	panel.add_child(box)
	var title := Label.new()
	title.text = "Event Log"
	title.add_theme_font_size_override("font_size", 20)
	box.add_child(title)
	eventlog_text = RichTextLabel.new()
	eventlog_text.fit_content = false
	eventlog_text.custom_minimum_size = Vector2(600, 330)
	eventlog_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	box.add_child(eventlog_text)
	var close_button := Button.new()
	close_button.text = "Close"
	close_button.pressed.connect(_on_event_log_close_pressed)
	box.add_child(close_button)
	eventlog_overlay.visible = false


func _build_catchup(layer: CanvasLayer) -> void:
	catchup_overlay = _overlay_base(layer)
	var centre := CenterContainer.new()
	centre.set_anchors_preset(Control.PRESET_FULL_RECT)
	catchup_overlay.add_child(centre)
	var panel := PanelContainer.new()
	centre.add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	box.custom_minimum_size = Vector2(560, 0)
	panel.add_child(box)
	catchup_title = Label.new()
	catchup_title.add_theme_font_size_override("font_size", 20)
	box.add_child(catchup_title)
	catchup_body = RichTextLabel.new()
	catchup_body.fit_content = true
	catchup_body.custom_minimum_size = Vector2(560, 80)
	box.add_child(catchup_body)
	catchup_events_text = RichTextLabel.new()
	catchup_events_text.fit_content = false
	catchup_events_text.custom_minimum_size = Vector2(560, 160)
	box.add_child(catchup_events_text)
	var begin_button := Button.new()
	begin_button.text = "Begin"
	begin_button.pressed.connect(_on_catchup_begin_pressed)
	box.add_child(begin_button)
	catchup_overlay.visible = false


# ------------------------------------------------------------- formatting

func _fmt_thousands(value: float, decimals: int = 0) -> String:
	var neg := value < 0.0
	var fmt := "%." + str(decimals) + "f"
	var raw := fmt % absf(value)
	var int_part := raw
	var frac_part := ""
	var dot := raw.find(".")
	if dot >= 0:
		int_part = raw.substr(0, dot)
		frac_part = raw.substr(dot)
	var grouped := ""
	while int_part.length() > 3:
		grouped = "," + int_part.substr(int_part.length() - 3) + grouped
		int_part = int_part.substr(0, int_part.length() - 3)
	grouped = int_part + grouped
	return ("-" if neg else "") + grouped + frac_part


func _fmt_signed(value: float, decimals: int = 0) -> String:
	if value >= 0.0:
		return "+" + _fmt_thousands(value, decimals)
	return _fmt_thousands(value, decimals)


func _set_message(text: String) -> void:
	if message_label != null:
		message_label.text = text
	if menu_overlay != null and menu_overlay.visible and menu_status_label != null:
		menu_status_label.text = text


# ------------------------------------------------------------ view lookup

func _view_systems() -> Array:
	if view_data.get("systems") is Array:
		return view_data["systems"]
	return []


func _view_ships() -> Array:
	if view_data.get("ships") is Array:
		return view_data["ships"]
	return []


func _view_designs() -> Array:
	if view_data.get("designs") is Array:
		return view_data["designs"]
	return []


func _find_ship(ship_id: int) -> Dictionary:
	for s in _view_ships():
		if s is Dictionary and int(s.get("id", -1)) == ship_id:
			return s
	return {}


func _selected_ship_dict() -> Dictionary:
	if selected_ship < 0:
		return {}
	return _find_ship(selected_ship)


func _find_design_by_kind(kind: String) -> Dictionary:
	for d in _view_designs():
		if d is Dictionary and str(d.get("kind", "")) == kind:
			return d
	return {}


func _find_design_by_idx(idx: int) -> Dictionary:
	for d in _view_designs():
		if d is Dictionary and int(d.get("idx", -1)) == idx:
			return d
	return {}


func _system_entry_by_id(sys_id: int) -> Dictionary:
	for s in _view_systems():
		if s is Dictionary and int(s.get("id", -1)) == sys_id:
			return s
	return {}


func _system_name(sys_id: int) -> String:
	var entry := _system_entry_by_id(sys_id)
	if not entry.is_empty():
		return str(entry.get("name", "System %d" % sys_id))
	# Fall back to the star table (star id == table index for the
	# shipped table); this covers en-route destinations that have no
	# sim state yet and so do not appear in the view.
	if sys_id >= 0 and sys_id < table.star_count:
		return table.get_name(sys_id)
	return "System %d" % sys_id


func _ship_current_system(ship: Dictionary) -> int:
	var state = ship.get("state", {})
	if state is Dictionary:
		var t := str(state.get("type", ""))
		if t == "at_system" or t == "surveying" or t == "stranded_at_system":
			return int(state.get("system", -1))
	return -1


# ----------------------------------------------------------------- events

func _event_human(e: Dictionary) -> String:
	var kind := str(e.get("kind", ""))
	var text := str(EVENT_TEXT.get(kind, kind.replace("_", " ").capitalize()))
	var sys_name = e.get("system_name", null)
	if sys_name != null and str(sys_name) != "":
		text += " — " + str(sys_name)
	if e.get("ship", null) != null:
		text += " (ship #%d)" % int(e["ship"])
	return text


func _event_log_line(e: Dictionary) -> String:
	return "Day %d · %s" % [int(e.get("day", 0)), _event_human(e)]


## Appends bridge events to the in-session log (capped at 300).
## Returns true when an interrupting event (colony abandoned, ship
## stranded) was among them.
func _append_events(events, flash: bool = true) -> bool:
	if not events is Array:
		return false
	var interrupt := false
	var last_text := ""
	for e in events:
		if not e is Dictionary:
			continue
		event_log_entries.append(e)
		while event_log_entries.size() > 300:
			event_log_entries.pop_front()
		var kind := str(e.get("kind", ""))
		if kind == "colony_abandoned" or kind == "ship_stranded":
			interrupt = true
		last_text = _event_human(e)
	if flash and last_text != "":
		_set_message(last_text)
	_refresh_event_log_text()
	return interrupt


func _refresh_event_log_text() -> void:
	if eventlog_text == null:
		return
	var lines := PackedStringArray()
	for e in event_log_entries:
		if e is Dictionary:
			lines.append(_event_log_line(e))
	eventlog_text.text = "\n".join(lines)


# --------------------------------------------------------- bridge/session

func _saves_dir_global() -> String:
	var dir := ProjectSettings.globalize_path("user://saves/")
	DirAccess.make_dir_recursive_absolute(dir)
	return dir


func _refresh_saves_list() -> void:
	saves_list_data.clear()
	if saves_item_list != null:
		saves_item_list.clear()
	if bridge_client == null or bridge_path == "":
		return
	var resp: Dictionary = bridge_client.call_bridge({"op": "list_saves", "dir": _saves_dir_global()})
	if not bool(resp.get("ok", false)):
		return
	var saves = resp.get("saves", [])
	if not saves is Array:
		return
	for s in saves:
		if not s is Dictionary:
			continue
		saves_list_data.append(s)
		var when := Time.get_datetime_string_from_unix_time(int(s.get("saved_at_unix", 0)))
		saves_item_list.add_item("%s · Day %d · saved %s" % [str(s.get("name", "?")), int(s.get("day", 0)), when])


func _on_new_campaign_pressed() -> void:
	if bridge_client == null or bridge_path == "":
		_set_message("Bridge binary not found — cannot start a campaign.")
		return
	var name := save_name_edit.text.strip_edges()
	if name == "":
		name = "campaign1"
	if not name.ends_with(".mwsb"):
		name += ".mwsb"
	save_path = _saves_dir_global().path_join(name)
	var resp: Dictionary = bridge_client.call_bridge({"op": "new", "save": save_path, "seed": int(seed_spin.value)})
	last_bridge_ms = Time.get_ticks_msec()
	if not bool(resp.get("ok", false)):
		_set_message("New campaign failed: %s" % str(resp.get("error", "unknown error")))
		return
	_enter_session(resp)
	_set_message("Campaign started at Sol — day 0.")


func _on_load_pressed() -> void:
	if bridge_client == null or bridge_path == "":
		_set_message("Bridge binary not found — cannot load a campaign.")
		return
	var selected := saves_item_list.get_selected_items()
	if selected.is_empty():
		_set_message("Select a saved campaign first.")
		return
	var entry: Dictionary = saves_list_data[selected[0]]
	save_path = str(entry.get("path", ""))
	if save_path == "":
		_set_message("Selected save has no path.")
		return
	var req := {"op": "load", "save": save_path}
	var elapsed := int(elapsed_spin.value)
	if elapsed > 0:
		req["elapsed_override_days"] = elapsed
	var resp: Dictionary = bridge_client.call_bridge(req)
	last_bridge_ms = Time.get_ticks_msec()
	if not bool(resp.get("ok", false)):
		_set_message("Load failed: %s" % str(resp.get("error", "unknown error")))
		return
	_enter_session(resp)
	var catchup = resp.get("catchup", null)
	if catchup is Dictionary:
		_append_events(catchup.get("events", []), false)
		if int(catchup.get("days", 0)) > 0:
			_open_catchup(catchup)


func _enter_session(resp: Dictionary) -> void:
	session_active = true
	view_data = resp.get("view", {}) if resp.get("view", {}) is Dictionary else {}
	event_cursor = int(view_data.get("events_total", 0))
	selected_ship = -1
	day_accumulator = 0.0
	speed_idx = 0
	_update_speed_buttons()
	menu_overlay.visible = false
	_refresh_hud()
	_refresh_ships_panel()
	_rebuild_markers()
	_rebuild_range_layer()
	var home := int(view_data.get("home_system", 0))
	if home >= 0 and home < table.star_count:
		_select_system(home)
	else:
		_render_system_panel()


## Applies an exec response: refreshes the view, appends events and
## surfaces the first command failure. Returns true on full success.
func _apply_exec_response(resp: Dictionary, success_message: String = "", quiet: bool = false) -> bool:
	last_bridge_ms = Time.get_ticks_msec()
	if resp.get("view", null) is Dictionary:
		view_data = resp["view"]
	var interrupt := false
	if resp.has("events"):
		interrupt = _append_events(resp.get("events", []), not quiet)
	if resp.has("event_cursor"):
		event_cursor = int(resp["event_cursor"])
	var ok := bool(resp.get("ok", false))
	var first_error := str(resp.get("error", ""))
	var results = resp.get("results", [])
	if results is Array:
		for r in results:
			if r is Dictionary and not bool(r.get("ok", true)):
				ok = false
				if first_error == "":
					first_error = str(r.get("error", "command failed"))
	_refresh_hud()
	_refresh_ships_panel()
	_rebuild_markers()
	_rebuild_range_layer()
	if session_active and selected_system >= 0:
		# Re-inspect so the panel reflects post-command state; this
		# does not recurse into exec, only into a read-only inspect.
		var keep := selected_system
		_select_system(keep)
	if not ok:
		_set_message("Error: %s" % (first_error if first_error != "" else "command failed"))
	elif interrupt:
		speed_idx = 0
		_update_speed_buttons()
		_set_message("Paused — interrupting event (colony abandoned or ship stranded). See Event Log.")
	elif success_message != "":
		_set_message(success_message)
	return ok


func _exec_commands(commands: Array, success_message: String = "", quiet: bool = false) -> Dictionary:
	if not session_active or bridge_client == null:
		return {"ok": false, "error": "no active session"}
	var req := {"op": "exec", "save": save_path, "commands": commands, "event_cursor": event_cursor}
	var resp: Dictionary = bridge_client.call_bridge(req)
	_apply_exec_response(resp, success_message, quiet)
	return resp


# -------------------------------------------------------------------- HUD

func _refresh_hud() -> void:
	if hud_label == null:
		return
	if not session_active or view_data.is_empty():
		hud_label.text = "No campaign loaded"
		hud_stats_label.text = ""
		return
	hud_label.text = "Year %d · Day %d (day %d)" % [int(view_data.get("year", 0)), int(view_data.get("day_of_year", 0)), int(view_data.get("day", 0))]
	var counts: Dictionary = view_data.get("counts", {}) if view_data.get("counts", {}) is Dictionary else {}
	hud_stats_label.text = "Credits %s · Surveyed %d · Claimed %d · Colonized %d · Pop %.1f M · Fuel %s" % [
		_fmt_thousands(float(view_data.get("credits", 0.0)), 0),
		int(counts.get("surveyed", 0)), int(counts.get("claimed", 0)), int(counts.get("colonized", 0)),
		float(view_data.get("total_population_millions", 0.0)),
		_fmt_thousands(float(view_data.get("total_fuel_stock", 0.0)), 0),
	]


func _update_speed_buttons() -> void:
	for i in speed_buttons.size():
		(speed_buttons[i] as Button).button_pressed = i == speed_idx


func _on_speed_pressed(idx: int) -> void:
	speed_idx = idx
	_update_speed_buttons()
	_set_message("Speed: %s" % SPEED_LABELS[idx])


func _on_save_pressed() -> void:
	if not session_active:
		_set_message("No active session to save.")
		return
	var resp := _exec_commands([], "")
	if bool(resp.get("ok", false)):
		_set_message("Saved — day %d" % int(view_data.get("day", 0)))
		_refresh_saves_list()


func _on_event_log_pressed() -> void:
	_refresh_event_log_text()
	eventlog_overlay.visible = true


func _on_event_log_close_pressed() -> void:
	eventlog_overlay.visible = false


func _on_menu_pressed() -> void:
	speed_idx = 0
	_update_speed_buttons()
	_refresh_saves_list()
	menu_overlay.visible = true


func _any_overlay_open() -> bool:
	return (menu_overlay != null and menu_overlay.visible) \
		or (catchup_overlay != null and catchup_overlay.visible) \
		or (eventlog_overlay != null and eventlog_overlay.visible)


# ---------------------------------------------------------------- markers

func _rebuild_markers() -> void:
	if marker_mi == null:
		return
	var verts := PackedVector3Array()
	var colors := PackedColorArray()
	if session_active:
		for s in _view_systems():
			if not s is Dictionary:
				continue
			var idx := int(s.get("index", -1))
			if idx < 0 or idx >= table.star_count:
				continue
			var colony = s.get("colony", null)
			var c: Color
			if colony is Dictionary:
				c = Color(0.25, 0.95, 0.45)
			elif s.get("claimed_by", null) != null:
				c = Color(1.0, 0.85, 0.25)
			elif str(s.get("survey", "")) == "surveyed":
				c = Color(0.85, 0.9, 1.0)
			else:
				continue
			# Alpha is the point-size class: 6.5 is the shader's
			# maximum class (see _point_size_base), so markers draw
			# at the largest point size.
			c.a = 6.5
			verts.append(table.positions[idx])
			colors.append(c)
	_set_points(marker_mi, verts, colors)


func _rebuild_range_layer() -> void:
	if range_mi == null:
		return
	var verts := PackedVector3Array()
	var colors := PackedColorArray()
	var ship := _selected_ship_dict()
	if session_active and not ship.is_empty():
		var origin_sys := _ship_current_system(ship)
		if origin_sys >= 0 and origin_sys < table.star_count:
			var design := _find_design_by_idx(int(ship.get("design_idx", -1)))
			var fuel_per_ly := float(design.get("fuel_per_ly", 0.0))
			var reach := float(ship.get("range_ly", 0.0))
			if fuel_per_ly > 0.0:
				reach = minf(reach, float(ship.get("fuel", 0.0)) / fuel_per_ly)
			var origin: Vector3 = table.positions[origin_sys]
			var c := Color(1.0, 0.35, 0.9)
			c.a = 4.0
			for i in table.star_count:
				if table.positions[i].distance_to(origin) <= reach:
					verts.append(table.positions[i])
					colors.append(c)
	_set_points(range_mi, verts, colors)


# ------------------------------------------------------------ ships panel

func _ship_status_text(ship: Dictionary) -> String:
	var state = ship.get("state", {})
	if not state is Dictionary:
		return "Unknown"
	match str(state.get("type", "")):
		"at_system":
			return "At %s" % _system_name(int(state.get("system", -1)))
		"surveying":
			return "Surveying %s (%d d)" % [_system_name(int(state.get("system", -1))), int(state.get("days_remaining", 0))]
		"en_route":
			return "En route %s → %s (%.1f/%.1f ly)" % [
				_system_name(int(state.get("from", -1))), _system_name(int(state.get("to", -1))),
				float(state.get("progress_ly", 0.0)), float(state.get("distance_ly", 0.0))]
		"stranded_en_route":
			return "Stranded en route %s → %s (%.1f/%.1f ly)" % [
				_system_name(int(state.get("from", -1))), _system_name(int(state.get("to", -1))),
				float(state.get("progress_ly", 0.0)), float(state.get("distance_ly", 0.0))]
		"stranded_at_system":
			return "Stranded at %s" % _system_name(int(state.get("system", -1)))
	return "Unknown"


func _refresh_ships_panel() -> void:
	if ships_box == null:
		return
	for child in ships_box.get_children():
		ships_box.remove_child(child)
		child.queue_free()
	if not session_active:
		var none_label := Label.new()
		none_label.text = "No campaign loaded."
		ships_box.add_child(none_label)
		return
	for s in _view_ships():
		if not s is Dictionary:
			continue
		var ship_id := int(s.get("id", -1))
		var b := Button.new()
		var prefix := "▸ " if ship_id == selected_ship else ""
		b.text = "%s%s #%d — %s · fuel %.0f/%.0f" % [
			prefix, str(s.get("design_name", "Ship")), ship_id, _ship_status_text(s),
			float(s.get("fuel", 0.0)), float(s.get("tank_capacity", 0.0))]
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		if ship_id == selected_ship:
			b.modulate = Color(1.0, 0.95, 0.65)
		b.pressed.connect(_on_ship_pressed.bind(ship_id))
		ships_box.add_child(b)


func _on_ship_pressed(ship_id: int) -> void:
	selected_ship = ship_id
	_refresh_ships_panel()
	_rebuild_range_layer()
	var ship := _find_ship(ship_id)
	var sys := _ship_current_system(ship)
	if sys >= 0 and sys < table.star_count:
		_select_system(sys)
	else:
		_render_system_panel()


# ----------------------------------------------------------- system panel

func _select_system(idx: int) -> void:
	if idx < 0 or idx >= table.star_count:
		return
	selected_system = idx
	inspect_data = {}
	inspect_warning = ""
	if session_active and bridge_client != null and bridge_path != "":
		# Star id is assumed equal to the table index for the shipped
		# table; the response's name is cross-checked below.
		var resp: Dictionary = bridge_client.call_bridge({"op": "inspect", "save": save_path, "system": idx})
		last_bridge_ms = Time.get_ticks_msec()
		if bool(resp.get("ok", false)) and resp.get("system", null) is Dictionary:
			inspect_data = resp["system"]
			var returned_name := str(inspect_data.get("name", ""))
			if returned_name != table.get_name(idx):
				inspect_warning = "Warning: inspect name mismatch — bridge says '%s', table index %d is '%s'." % [returned_name, idx, table.get_name(idx)]
				_set_message(inspect_warning)
		else:
			_set_message("Inspect failed: %s" % str(resp.get("error", "unknown error")))
	_render_system_panel()
	_rebuild_range_layer()


func _render_system_panel() -> void:
	if info_label == null:
		return
	if selected_system < 0:
		_refresh_system_buttons()
		return
	if not session_active or inspect_data.is_empty():
		show_star_info(selected_system)
		_refresh_system_buttons()
		return
	var i := selected_system
	var lines := PackedStringArray()
	lines.append("[b][font_size=22]%s[/font_size][/b]" % str(inspect_data.get("name", table.get_name(i))))
	lines.append("Spectral class: %s" % table.spectral_letter(i))
	lines.append("Distance from Sol: %.2f ly" % float(inspect_data.get("distance_from_sol_ly", table.positions[i].length())))
	lines.append("Distance from home: %.2f ly" % float(inspect_data.get("distance_from_home_ly", 0.0)))
	if inspect_warning != "":
		lines.append(inspect_warning)
	var colony = inspect_data.get("colony", null)
	var survey := str(inspect_data.get("survey", "unknown"))
	if colony is Dictionary:
		lines.append("Survey: Surveyed · Colonized (founded day %d)" % int(colony.get("founded_day", 0)))
	elif survey == "surveyed":
		lines.append("Survey: Surveyed")
	elif survey == "unknown":
		lines.append("Survey: Unknown — in range of a known system, not yet surveyed")
	else:
		lines.append("Survey: Unsurveyed")
	# Catalog facts (S0 formatting, derived flags preserved).
	if float(inspect_data.get("teff_k", 0.0)) > 0.0:
		var tflag := " (derived)" if bool(inspect_data.get("temp_derived", false)) else ""
		lines.append("Temperature: %.0f K%s" % [float(inspect_data.get("teff_k", 0.0)), tflag])
	if float(inspect_data.get("mass_solar", 0.0)) > 0.0:
		var mflag := " (derived)" if bool(inspect_data.get("mass_derived", false)) else ""
		lines.append("Mass: %.2f M☉%s" % [float(inspect_data.get("mass_solar", 0.0)), mflag])
	if bool(inspect_data.get("source_exoplanet_archive", false)):
		lines.append("Host inserted from the NASA Exoplanet Archive (not in HYG).")
	var catalog = inspect_data.get("catalog_planets", [])
	if catalog is Array and not catalog.is_empty():
		lines.append("\nCatalog planets (%d):" % catalog.size())
		for p in catalog:
			if p is Dictionary:
				lines.append("· %s" % str(p.get("name", "?")))
	# Survey profile.
	var profile = inspect_data.get("profile", null)
	if profile is Dictionary:
		lines.append("\nSurvey profile:")
		lines.append("Habitability: %d%%" % int(profile.get("habitability_percent", 0)))
		lines.append("Traits — fuel %d · industry %d · exotics %d" % [
			int(profile.get("fuel_trait", 0)), int(profile.get("industry_trait", 0)), int(profile.get("exotics_trait", 0))])
		var planets = profile.get("planets", [])
		if planets is Array and not planets.is_empty():
			lines.append("Planets (%d):" % planets.size())
			for p in planets:
				if not p is Dictionary:
					continue
				var source := str(p.get("source", ""))
				var source_label := source
				if source == "real_catalog":
					source_label = "real — catalog"
				elif source == "generated":
					source_label = "generated from star + seed"
				elif source == "homeworld_setup":
					source_label = "homeworld"
				lines.append("· %s — habitability %d%% (%s)" % [
					str(p.get("name", "?")), int(p.get("habitability_percent", 0)), source_label])
	# Colony block.
	if colony is Dictionary:
		lines.append("\nColony:")
		lines.append("Population: %.2f M · Development: %d" % [
			float(colony.get("population_millions", 0.0)), int(colony.get("development", 0))])
		var spec_value = colony.get("specialization", null)
		lines.append("Specialization: %s" % (str(spec_value) if spec_value != null else "none"))
		if bool(colony.get("supplied", false)):
			lines.append("Supplied: yes")
		else:
			lines.append("Supplied: NO — unsupplied for %d month(s)" % int(colony.get("unsupplied_months", 0)))
		lines.append("Stocks — fuel %.1f · supplies %.1f · alloys %.1f · electronics %.1f · exotics %.1f" % [
			float(colony.get("fuel_stock", 0.0)), float(colony.get("supplies_stock", 0.0)),
			float(colony.get("alloys_stock", 0.0)), float(colony.get("electronics_stock", 0.0)),
			float(colony.get("exotics_stock", 0.0))])
		lines.append("Energy: %.1f generated / %.1f consumed" % [
			float(colony.get("energy_generation", 0.0)), float(colony.get("energy_consumption", 0.0))])
		var queue = colony.get("construction_queue", [])
		if queue is Array and not queue.is_empty():
			lines.append("Construction queue:")
			for q in queue:
				if q is Dictionary:
					var d := _find_design_by_idx(int(q.get("design_idx", -1)))
					lines.append("· %s — %d/%d days" % [
						str(d.get("name", "Design %d" % int(q.get("design_idx", -1)))),
						int(q.get("total_days", 0)) - int(q.get("days_remaining", 0)),
						int(q.get("total_days", 0))])
	# Ships present.
	var present = inspect_data.get("ships_present", [])
	if present is Array and not present.is_empty():
		var names := PackedStringArray()
		for sid in present:
			var ship := _find_ship(int(sid))
			if not ship.is_empty():
				names.append("%s #%d" % [str(ship.get("design_name", "Ship")), int(sid)])
			else:
				names.append("Ship #%d" % int(sid))
		lines.append("\nShips present: %s" % ", ".join(names))
	info_label.text = "\n".join(lines)
	_refresh_system_buttons()


func _refresh_system_buttons() -> void:
	if claim_button == null:
		return
	claim_button.visible = false
	build_surveyor_button.visible = false
	build_colony_button.visible = false
	spec_row.visible = false
	send_survey_button.visible = false
	send_colonize_button.visible = false
	send_move_button.visible = false
	survey_this_button.visible = false
	found_button.visible = false
	refuel_button.visible = false
	if not session_active or inspect_data.is_empty():
		return
	var colony = inspect_data.get("colony", null)
	var survey := str(inspect_data.get("survey", ""))
	if survey == "surveyed" and inspect_data.get("claimed_by", null) == null:
		claim_button.visible = true
	if colony is Dictionary:
		var sd := _find_design_by_kind("surveyor")
		if not sd.is_empty():
			build_surveyor_button.text = "Build Surveyor — %s cr / %s alloys" % [
				_fmt_thousands(float(sd.get("credits_cost", 0.0)), 0), _fmt_thousands(float(sd.get("alloys_cost", 0.0)), 0)]
			build_surveyor_button.visible = true
		var cd := _find_design_by_kind("colony")
		if not cd.is_empty():
			build_colony_button.text = "Build Colony Ship — %s cr / %s alloys" % [
				_fmt_thousands(float(cd.get("credits_cost", 0.0)), 0), _fmt_thousands(float(cd.get("alloys_cost", 0.0)), 0)]
			build_colony_button.visible = true
		if int(colony.get("development", 0)) >= 3 and colony.get("specialization", null) == null:
			spec_row.visible = true
	# Orders for the selected ship targeting this system.
	var ship := _selected_ship_dict()
	if ship.is_empty():
		return
	var target_id := int(inspect_data.get("id", selected_system))
	var ship_sys := _ship_current_system(ship)
	var state = ship.get("state", {})
	var state_type := str(state.get("type", "")) if state is Dictionary else ""
	var kind := str(ship.get("kind", ""))
	if ship_sys >= 0 and ship_sys != target_id and state_type == "at_system":
		if kind == "surveyor":
			send_survey_button.visible = true
		if kind == "colony":
			send_colonize_button.visible = true
		send_move_button.visible = true
	if ship_sys == target_id and (state_type == "at_system" or state_type == "stranded_at_system"):
		if kind == "surveyor" and state_type == "at_system" and survey != "surveyed":
			survey_this_button.visible = true
		if kind == "colony" and state_type == "at_system":
			found_button.visible = true
		refuel_button.visible = true


func _target_system_id() -> int:
	if not inspect_data.is_empty():
		return int(inspect_data.get("id", selected_system))
	return selected_system


func _on_claim_pressed() -> void:
	_exec_commands([{"cmd": "claim", "system": _target_system_id()}], "System claimed.")


func _on_build_surveyor_pressed() -> void:
	var d := _find_design_by_kind("surveyor")
	if not d.is_empty():
		_exec_commands([{"cmd": "build", "system": _target_system_id(), "design": int(d.get("idx", 0))}], "Surveyor construction started.")


func _on_build_colony_pressed() -> void:
	var d := _find_design_by_kind("colony")
	if not d.is_empty():
		_exec_commands([{"cmd": "build", "system": _target_system_id(), "design": int(d.get("idx", 0))}], "Colony ship construction started.")


func _on_specialize_pressed() -> void:
	var idx := spec_option.selected
	if idx >= 0 and idx < SPEC_IDS.size():
		_exec_commands([{"cmd": "specialize", "system": _target_system_id(), "spec": SPEC_IDS[idx]}], "Specialization set.")


func _dispatch_selected(purpose: String) -> void:
	if selected_ship < 0:
		_set_message("Select a ship first.")
		return
	_exec_commands([{"cmd": "dispatch", "ship": selected_ship, "to": _target_system_id(), "purpose": purpose}], "Ship dispatched.")


func _on_send_survey_pressed() -> void:
	_dispatch_selected("survey")


func _on_send_colonize_pressed() -> void:
	_dispatch_selected("colonize")


func _on_send_move_pressed() -> void:
	_dispatch_selected("relocate")


func _on_survey_this_pressed() -> void:
	if selected_ship >= 0:
		_exec_commands([{"cmd": "survey", "ship": selected_ship}], "Survey started.")


func _on_found_pressed() -> void:
	if selected_ship >= 0:
		_exec_commands([{"cmd": "found", "ship": selected_ship}], "Colony founded.")


func _on_refuel_pressed() -> void:
	if selected_ship >= 0:
		_exec_commands([{"cmd": "refuel", "ship": selected_ship}], "Ship refuelled.")


# -------------------------------------------------------------- catch-up

func _catchup_delta_line(label: String, before: Dictionary, after: Dictionary, key: String, decimals: int) -> String:
	var b := float(before.get(key, 0.0))
	var a := float(after.get(key, 0.0))
	return "%s %s → %s (Δ %s)" % [label, _fmt_thousands(b, decimals), _fmt_thousands(a, decimals), _fmt_signed(a - b, decimals)]


func _open_catchup(catchup: Dictionary) -> void:
	var days := int(catchup.get("days", 0))
	catchup_title.text = "While you were away — %d days passed" % days
	var before: Dictionary = catchup.get("before", {}) if catchup.get("before", {}) is Dictionary else {}
	var after: Dictionary = catchup.get("after", {}) if catchup.get("after", {}) is Dictionary else {}
	var lines := PackedStringArray()
	lines.append("Monthly settlements: %d" % int(catchup.get("months_settled", 0)))
	lines.append(_catchup_delta_line("Credits", before, after, "credits", 2))
	lines.append(_catchup_delta_line("Population (M)", before, after, "total_population_millions", 3))
	lines.append(_catchup_delta_line("Surveyed", before, after, "surveyed", 0))
	lines.append(_catchup_delta_line("Claimed", before, after, "claimed", 0))
	lines.append(_catchup_delta_line("Colonized", before, after, "colonized", 0))
	lines.append(_catchup_delta_line("Fuel stock", before, after, "total_fuel_stock", 1))
	var events = catchup.get("events", [])
	if events is Array and events.is_empty():
		lines.append("\nNo ship or colony events — the galaxy ticked quietly (economy settled monthly).")
	catchup_body.text = "\n".join(lines)
	var event_lines := PackedStringArray()
	if events is Array:
		for e in events:
			if e is Dictionary:
				event_lines.append(_event_log_line(e))
	catchup_events_text.text = "\n".join(event_lines)
	# The game stays paused after dismissal until a speed is picked.
	speed_idx = 0
	_update_speed_buttons()
	catchup_overlay.visible = true


func _on_catchup_begin_pressed() -> void:
	catchup_overlay.visible = false


# ------------------------------------------------------------ S0 viewer

func _point_size_base(m: float) -> float:
	# Absolute magnitude → point-size class. absmag 0 means "unknown"
	# (inserted archive hosts carry no photometry) — use a neutral size,
	# never the brightest-star size.
	if m == 0.0:
		return 2.0
	return clampf(6.5 - (m - 4.85) * 0.4, 1.0, 6.5)


func _show_overview(data_path_arg: String, load_ms: int) -> void:
	count_label.text = "%d stars · %d known planets" % [table.star_count, table.planet_count]
	info_label.text = "Milky Way Colonization Sim — S0 data viewer\n%s\nLoaded in %d ms.\nClick any star to inspect it." % [data_path_arg, load_ms]


func _update_camera() -> void:
	var rot := Basis.from_euler(Vector3(pitch, yaw, 0.0))
	camera.global_transform = Transform3D(rot, target + rot * Vector3(0, 0, dist))


func go_to_sol() -> void:
	target = Vector3.ZERO
	dist = 60.0
	_update_camera()
	var sol = table.find_by_name("Sol")
	if sol >= 0:
		_select_system(sol)


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
						_select_system(hit)
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
	# Game clock: advance whole days through the bridge, throttled to
	# at most one bridge call per 0.25 s.
	if session_active and not _any_overlay_open() and speed_idx > 0 and speed_idx < SPEED_RATES.size():
		day_accumulator += delta * float(SPEED_RATES[speed_idx])
		if day_accumulator >= 1.0 and Time.get_ticks_msec() - last_bridge_ms >= 250:
			var days := int(day_accumulator)
			day_accumulator -= float(days)
			_exec_commands([{"cmd": "advance", "days": days}], "", false)
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

## The S0 checks, unchanged. Returns the failure count; prints the
## VERIFY_PASS lines (including "VERIFY_PASS all" on success).
func _run_verify_checks(data_path_arg: String, load_ms: int) -> int:
	var failures := 0
	# 1) Star count matches the pipeline manifest.
	var manifest_path := data_path_arg.get_base_dir() + "/manifest.json"
	var expected := -1
	if FileAccess.file_exists(manifest_path):
		var parsed = JSON.parse_string(FileAccess.get_file_as_string(manifest_path))
		if parsed is Dictionary and parsed.get("table", null) is Dictionary:
			expected = int(parsed["table"].get("stars", -1))
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
	else:
		print("VERIFY_PASS all")
	return failures


# ------------------------------------------------------------- verify S2

var _s2_events: Array = []
var _s2_cursor: int = 0


func _s2_exec(save: String, commands: Array) -> Dictionary:
	var resp: Dictionary = bridge_client.call_bridge({"op": "exec", "save": save, "commands": commands, "event_cursor": _s2_cursor})
	if resp.get("events", null) is Array:
		for e in resp["events"]:
			_s2_events.append(e)
	if resp.has("event_cursor"):
		_s2_cursor = int(resp["event_cursor"])
	return resp


func _s2_result_ok(resp: Dictionary) -> bool:
	var results = resp.get("results", [])
	if results is Array and not results.is_empty() and results[0] is Dictionary:
		return bool(results[0].get("ok", false))
	return false


func _s2_counts(resp: Dictionary) -> Dictionary:
	var v = resp.get("view", {})
	if v is Dictionary and v.get("counts", null) is Dictionary:
		return v["counts"]
	return {}


func _s2_ships(resp: Dictionary) -> Array:
	var v = resp.get("view", {})
	if v is Dictionary and v.get("ships", null) is Array:
		return v["ships"]
	return []


func _s2_find_ship(resp: Dictionary, kind: String) -> Dictionary:
	for s in _s2_ships(resp):
		if s is Dictionary and str(s.get("kind", "")) == kind:
			return s
	return {}


func _run_verify_s2() -> void:
	# S0 lines have already been printed by _run_verify_checks.
	if not user_args.has("bridge") or str(user_args.get("bridge", "")) == "":
		printerr("S2_VERIFY_FAIL bridge not specified")
		get_tree().quit(1)
		return
	if bridge_client == null or bridge_path == "":
		printerr("S2_VERIFY_FAIL bridge not found")
		get_tree().quit(1)
		return
	var verify_dir := ProjectSettings.globalize_path("user://verify-s2/")
	DirAccess.make_dir_recursive_absolute(verify_dir)
	var save := verify_dir.path_join("verify.mwsb")
	if FileAccess.file_exists(save):
		DirAccess.remove_absolute(save)
	_s2_events.clear()
	_s2_cursor = 0

	# a) New campaign, seed 42.
	var resp: Dictionary = bridge_client.call_bridge({"op": "new", "save": save, "seed": 42})
	var v = resp.get("view", {})
	if not bool(resp.get("ok", false)) or not v is Dictionary \
			or int(v.get("day", -1)) != 0 \
			or int(_s2_counts(resp).get("colonized", -1)) != 1 \
			or _s2_ships(resp).size() != 2:
		printerr("S2_VERIFY_FAIL new resp=%s" % str(resp).substr(0, 400))
		get_tree().quit(1)
		return
	print("S2_VERIFY_PASS new day=0 colonized=1 ships=2")

	# b) Nearest table star to Sol, excluding index 0.
	var target_idx := -1
	var target_dist := INF
	for i in table.star_count:
		if i == 0:
			continue
		var d := table.positions[i].length()
		if d < target_dist:
			target_dist = d
			target_idx = i
	if target_idx < 0 or not target_dist < 75.0:
		printerr("S2_VERIFY_FAIL target index=%d dist=%f" % [target_idx, target_dist])
		get_tree().quit(1)
		return
	print("S2_VERIFY_PASS target index=%d name=%s dist_ly=%.4f" % [target_idx, table.get_name(target_idx), target_dist])

	# c) Dispatch the surveyor to the target, purpose "survey".
	var surveyor := _s2_find_ship(resp, "surveyor")
	if surveyor.is_empty():
		printerr("S2_VERIFY_FAIL dispatch_surveyor no surveyor in view")
		get_tree().quit(1)
		return
	resp = _s2_exec(save, [{"cmd": "dispatch", "ship": int(surveyor.get("id", -1)), "to": target_idx, "purpose": "survey"}])
	if not _s2_result_ok(resp):
		printerr("S2_VERIFY_FAIL dispatch_surveyor resp=%s" % str(resp).substr(0, 400))
		get_tree().quit(1)
		return
	print("S2_VERIFY_PASS dispatch_surveyor ship=%d to=%d" % [int(surveyor.get("id", -1)), target_idx])

	# d) Advance 200 days: the target must be surveyed.
	resp = _s2_exec(save, [{"cmd": "advance", "days": 200}])
	if int(_s2_counts(resp).get("surveyed", -1)) != 2:
		printerr("S2_VERIFY_FAIL advance_survey surveyed=%d resp=%s" % [int(_s2_counts(resp).get("surveyed", -1)), str(resp).substr(0, 400)])
		get_tree().quit(1)
		return
	print("S2_VERIFY_PASS advance_survey surveyed=2")

	# e) Claim the target, then dispatch the colony ship to colonize.
	resp = _s2_exec(save, [{"cmd": "claim", "system": target_idx}])
	if not _s2_result_ok(resp):
		printerr("S2_VERIFY_FAIL claim resp=%s" % str(resp).substr(0, 400))
		get_tree().quit(1)
		return
	var colony_ship := _s2_find_ship(resp, "colony")
	if colony_ship.is_empty():
		printerr("S2_VERIFY_FAIL dispatch_colony no colony ship in view")
		get_tree().quit(1)
		return
	resp = _s2_exec(save, [{"cmd": "dispatch", "ship": int(colony_ship.get("id", -1)), "to": target_idx, "purpose": "colonize"}])
	if not _s2_result_ok(resp):
		printerr("S2_VERIFY_FAIL dispatch_colony resp=%s" % str(resp).substr(0, 400))
		get_tree().quit(1)
		return
	print("S2_VERIFY_PASS claim_and_dispatch_colony ship=%d to=%d" % [int(colony_ship.get("id", -1)), target_idx])

	# f) Advance 400 days: a second colony, and a colony_founded event
	# for the target among the events accumulated since cursor 0.
	resp = _s2_exec(save, [{"cmd": "advance", "days": 400}])
	var founded := false
	for e in _s2_events:
		if e is Dictionary and str(e.get("kind", "")) == "colony_founded" and e.get("system", null) != null and int(e["system"]) == target_idx:
			founded = true
	if int(_s2_counts(resp).get("colonized", -1)) != 2 or not founded:
		printerr("S2_VERIFY_FAIL advance_colonize colonized=%d founded_event=%s" % [int(_s2_counts(resp).get("colonized", -1)), str(founded)])
		get_tree().quit(1)
		return
	print("S2_VERIFY_PASS advance_colonize colonized=2 colony_founded_event=true")

	# g) Offline catch-up on load: exactly the overridden 30 days.
	var day_before := -1
	var v2 = resp.get("view", {})
	if v2 is Dictionary:
		day_before = int(v2.get("day", -1))
	resp = bridge_client.call_bridge({"op": "load", "save": save, "elapsed_override_days": 30})
	var catchup = resp.get("catchup", null)
	var v3 = resp.get("view", {})
	var day_after := -1
	if v3 is Dictionary:
		day_after = int(v3.get("day", -1))
	if not bool(resp.get("ok", false)) or not catchup is Dictionary \
			or int(catchup.get("days", -1)) != 30 or day_after != day_before + 30:
		printerr("S2_VERIFY_FAIL load_catchup days=%s day_before=%d day_after=%d" % [
			str(catchup.get("days", "?")) if catchup is Dictionary else "null", day_before, day_after])
		get_tree().quit(1)
		return
	print("S2_VERIFY_PASS load_catchup days=30 day=%d->%d" % [day_before, day_after])
	print("S2_VERIFY_PASS all")
	get_tree().quit(0)


