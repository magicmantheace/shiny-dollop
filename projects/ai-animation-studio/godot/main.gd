extends Node3D
## Minimal renderer/protocol proof. Procedural stand-ins, no real rig, no AI/TTS.

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
    events = parsed.get("events", [])
    for actor in parsed.get("actors", []):
        actors[actor.get("id", "")] = {"color": actor.get("color", "#dddddd"), "node": null}
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

func _vec3(v: Array) -> Vector3:
    return Vector3(float(v[0]), float(v[1]), float(v[2]))

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
