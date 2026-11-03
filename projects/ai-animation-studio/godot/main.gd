extends Node3D
## Minimal renderer/protocol proof. Procedural stand-ins, no real rig, no AI/TTS.

## Wire constants; SCHEMA_VERSION must match VERSION in studio/schema.py
## and OPS must match its OPS set (guarded by tests/test_conformance.py).
const SCHEMA_VERSION := "1.0.0"
const VALID_OPS := ["spawn", "move", "speak", "emote", "camera"]

var actors: Dictionary = {}
var events: Array = []
var next_event: int = 0
var clock_ms: float = 0.0

func _ready() -> void:
    _build_stage()
    var source := "res://data/demo_scene.json"
    if FileAccess.file_exists("res://data/scene_runtime.json"):
        source = "res://data/scene_runtime.json"
    var parsed = JSON.parse_string(FileAccess.get_file_as_string(source))
    if typeof(parsed) != TYPE_DICTIONARY:
        push_error("Invalid scene JSON: " + source)
        return
    # Cheap re-validation at load: parsed JSON is not trusted input.
    # This mirrors the fail-closed wire subset of studio/schema.py that the
    # preview executes; full semantic validation stays on the Python side.
    if String(parsed.get("schema_version", "")) != SCHEMA_VERSION:
        push_error("Unsupported schema_version (expected " + SCHEMA_VERSION + "): " + source)
        return
    var raw_actors: Variant = parsed.get("actors")
    var raw_events: Variant = parsed.get("events")
    if typeof(raw_actors) != TYPE_ARRAY or typeof(raw_events) != TYPE_ARRAY:
        push_error("Scene actors/events must be arrays: " + source)
        return
    for actor in raw_actors:
        if typeof(actor) != TYPE_DICTIONARY:
            push_error("Actor entry is not an object; scene rejected: " + source)
            return
        actors[actor.get("id", "")] = {"color": actor.get("color", "#dddddd"), "node": null}
    for i in raw_events.size():
        var e: Variant = raw_events[i]
        if typeof(e) != TYPE_DICTIONARY:
            push_error("events[" + str(i) + "]: not an object; event skipped")
            continue
        var op := String(e.get("op", ""))
        if op not in VALID_OPS:
            push_error("events[" + str(i) + "]: unknown op '" + op + "'; event skipped")
            continue
        if op == "spawn" and _parse_vec3(e.get("position")) == null:
            push_error("events[" + str(i) + "]: spawn position is not an array of exactly 3 numbers; event skipped")
            continue
        if op == "move" and _parse_vec3(e.get("target")) == null:
            push_error("events[" + str(i) + "]: move target is not an array of exactly 3 numbers; event skipped")
            continue
        events.append(e)
    print("AI Animation Studio preview: ", parsed.get("scene_id", "<unnamed>"))

func _process(delta: float) -> void:
    clock_ms += delta * 1000.0
    while next_event < events.size() and float(events[next_event].get("at_ms", 0)) <= clock_ms:
        _dispatch(events[next_event])
        next_event += 1

func _dispatch(e: Dictionary) -> void:
    var op := String(e.get("op", ""))
    if op == "camera":
        print("Camera request: ", e.get("shot", "wide"))
        return
    var id := String(e.get("actor_id", ""))
    if not actors.has(id):
        push_warning("Unknown actor: " + id)
        return
    var state: Dictionary = actors[id]
    if op == "spawn":
        if state["node"] != null:
            return
        var actor := Node3D.new()
        actor.name = id
        add_child(actor)
        var mesh := MeshInstance3D.new()
        var capsule := CapsuleMesh.new()
        capsule.radius = 0.35
        capsule.height = 1.7
        mesh.mesh = capsule
        var mat := StandardMaterial3D.new()
        mat.albedo_color = Color.from_string(String(state["color"]), Color.WHITE)
        mesh.material_override = mat
        mesh.position.y = 0.85
        actor.add_child(mesh)
        actor.position = _vec3(e.get("position", [0, 0, 0]))
        state["node"] = actor
        actors[id] = state
    elif state["node"] == null:
        push_warning("Actor not spawned: " + id)
    elif op == "move":
        var duration: float = max(0.1, float(e.get("duration_ms", 1000)) / 1000.0)
        create_tween().tween_property(state["node"], "position", _vec3(e.get("target", [0, 0, 0])), duration)
    elif op == "speak":
        print(id, ": ", e.get("line", ""))
    elif op == "emote":
        print(id, " emotion: ", e.get("emotion", "neutral"), " intensity: ", e.get("intensity", 0.0))

func _parse_vec3(v: Variant) -> Variant:
    # Returns a Vector3, or null when v is not an array of exactly 3 numbers.
    if typeof(v) != TYPE_ARRAY or v.size() != 3:
        return null
    for n in v:
        if typeof(n) != TYPE_INT and typeof(n) != TYPE_FLOAT:
            return null
    return Vector3(float(v[0]), float(v[1]), float(v[2]))

func _vec3(v: Variant) -> Vector3:
    var parsed: Variant = _parse_vec3(v)
    if parsed == null:
        push_error("Invalid 3-vector value; using origin")
        return Vector3.ZERO
    return parsed

func _build_stage() -> void:
    var floor_mesh := MeshInstance3D.new()
    var box := BoxMesh.new()
    box.size = Vector3(12, 0.15, 8)
    floor_mesh.mesh = box
    floor_mesh.position.y = -0.1
    add_child(floor_mesh)
    var light := DirectionalLight3D.new()
    light.rotation_degrees = Vector3(-55, -25, 0)
    add_child(light)
    var camera := Camera3D.new()
    camera.position = Vector3(0, 3.0, 10)
    add_child(camera)
    camera.look_at(Vector3(0, 1, 0), Vector3.UP)
    camera.current = true
    var world := WorldEnvironment.new()
    var environment := Environment.new()
    environment.background_mode = Environment.BG_COLOR
    environment.background_color = Color(0.13, 0.17, 0.23)
    environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
    environment.ambient_light_color = Color(0.85, 0.85, 0.9)
    world.environment = environment
    add_child(world)
