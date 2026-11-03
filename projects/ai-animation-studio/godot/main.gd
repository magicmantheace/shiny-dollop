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

## F1 asset resolution: examples/asset_manifest.json (copied next to the
## scene by `python -m studio demo`) maps recipe_id -> local GLB files under
## an asset store outside git, resolved through an environment variable.
## The demo export attaches library approval state (per-asset status,
## pinned version, SHA-256) from the SQLite catalog; the preview resolves
## ONLY approved, version-pinned files whose on-disk SHA-256 matches the
## approved record. Any mismatch is named in the log and the actor falls
## back to a capsule. When the manifest or the store is absent, actors
## fall back to capsules and the in-git demo behaves exactly as before.
var manifest: Dictionary = {}
var asset_root := ""
var clip_by_name: Dictionary = {}

func _ready() -> void:
    _load_manifest()
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
        actors[actor.get("id", "")] = {"color": actor.get("color", "#dddddd"), "node": null, "recipe_id": String(actor.get("recipe_id", "")), "anim": null}
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
        actor.add_child(_make_visual(id, state))
        actor.position = _vec3(e.get("position", [0, 0, 0]))
        state["node"] = actor
        actors[id] = state
        if state["anim"] != null:
            _play_tag(id, "idle")
    elif state["node"] == null:
        push_warning("Actor not spawned: " + id)
    elif op == "move":
        var duration: float = max(0.1, float(e.get("duration_ms", 1000)) / 1000.0)
        var tween := create_tween()
        tween.tween_property(state["node"], "position", _vec3(e.get("target", [0, 0, 0])), duration)
        if state["anim"] != null:
            _play_tag(id, "walk")
            tween.tween_callback(_play_tag.bind(id, "idle"))
    elif op == "speak":
        print(id, ": ", e.get("line", ""))
        if state["anim"] != null:
            _play_tag(id, "speak")
            var entry: Dictionary = (manifest.get("clips", {}) as Dictionary).get("speak", {})
            var hold_s: float = float(entry.get("duration_s", 2.0))
            get_tree().create_timer(hold_s).timeout.connect(_end_speak.bind(id))
    elif op == "emote":
        print(id, " emotion: ", e.get("emotion", "neutral"), " intensity: ", e.get("intensity", 0.0))

func _load_manifest() -> void:
    var path := "res://data/asset_manifest.json"
    if not FileAccess.file_exists(path):
        return
    var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
    if typeof(parsed) != TYPE_DICTIONARY:
        push_error("Invalid asset manifest JSON: " + path)
        return
    if String(parsed.get("schema_version", "")) != SCHEMA_VERSION:
        push_error("Unsupported asset manifest schema_version (expected " + SCHEMA_VERSION + ")")
        return
    manifest = parsed
    var clips: Dictionary = manifest.get("clips", {})
    for tag in clips:
        var entry: Dictionary = clips[tag]
        clip_by_name[String(entry.get("clip", ""))] = entry
    var env_name := String(manifest.get("asset_root_env", "AI_ANIMATION_ASSET_ROOT"))
    asset_root = OS.get_environment(env_name)
    if asset_root == "":
        print("Asset manifest loaded but ", env_name, " is not set; capsule fallback active")

func _load_gltf(path: String) -> Node:
    var doc := GLTFDocument.new()
    var state := GLTFState.new()
    if doc.append_from_file(path, state) != OK:
        push_warning("Could not load glTF: " + path)
        return null
    return doc.generate_scene(state)

func _sha256_of_file(path: String) -> String:
    var file := FileAccess.open(path, FileAccess.READ)
    if file == null:
        return ""
    var ctx := HashingContext.new()
    if ctx.start(HashingContext.HASH_SHA256) != OK:
        return ""
    while not file.eof_reached():
        ctx.update(file.get_buffer(65536))
    return ctx.finish().hex_encode()

func _verify_recipe_file(pin: Dictionary) -> String:
    # Returns "" when the pin agrees with the exported library state and
    # the file on disk hashes to the approved record; otherwise a named
    # rejection reason. Resolution is approved-only and version-pinned.
    var uri := String(pin.get("uri", ""))
    var assets: Dictionary = manifest.get("assets", {})
    if not assets.has(uri):
        return "no library state exported for " + uri
    var record: Dictionary = assets[uri]
    if String(record.get("status", "")) != "approved":
        return uri + " status is '" + String(record.get("status", "")) + "' (approved required)"
    if String(pin.get("status", "")) != "approved":
        return uri + " pin status is '" + String(pin.get("status", "")) + "' (approved required)"
    if String(pin.get("version", "")) != String(record.get("version", "")):
        return uri + " version mismatch (pin " + String(pin.get("version", "")) + " vs library " + String(record.get("version", "")) + ")"
    var pin_hash := String(pin.get("sha256", ""))
    if pin_hash == "" or pin_hash != String(record.get("sha256", "")):
        return uri + " catalog hash mismatch (pin vs library record)"
    if _sha256_of_file(asset_root.path_join(uri)) != pin_hash:
        return uri + " sha256 mismatch (file does not match the approved record)"
    return ""

func _make_visual(id: String, state: Dictionary) -> Node:
    # GLB character when the manifest resolves this actor's recipe through
    # the approved, hash-verified path and the asset store is present;
    # otherwise the procedural capsule stand-in.
    var recipes: Dictionary = manifest.get("recipes", {})
    var recipe: Dictionary = recipes.get(String(state.get("recipe_id", "")), {})
    if not recipe.is_empty() and asset_root != "":
        var body_path := asset_root.path_join(String(recipe.get("body", "")))
        var files: Array = recipe.get("files", [])
        if files.is_empty():
            print("Capsule fallback for ", id, ": manifest carries no approval state for recipe ", String(state.get("recipe_id", "")))
        elif not FileAccess.file_exists(body_path):
            print("Capsule fallback for ", id, ": model unavailable at ", body_path)
        else:
            var rejection := ""
            for pin in files:
                var uri := String(pin.get("uri", ""))
                if not FileAccess.file_exists(asset_root.path_join(uri)):
                    rejection = uri + " missing from asset store"
                    break
                rejection = _verify_recipe_file(pin)
                if rejection != "":
                    break
            if rejection != "":
                print("Capsule fallback for ", id, ": asset rejected — ", rejection)
            else:
                var model := _load_gltf(body_path)
                if model != null:
                    var player := AnimationPlayer.new()
                    model.add_child(player)
                    var lib := AnimationLibrary.new()
                    player.add_animation_library("", lib)
                    for anim_uri in recipe.get("animations", []):
                        var anim_scene := _load_gltf(asset_root.path_join(String(anim_uri)))
                        if anim_scene == null:
                            continue
                        var src_player := anim_scene.find_child("AnimationPlayer", true, false) as AnimationPlayer
                        if src_player != null and src_player.has_animation_library(""):
                            var src_lib := src_player.get_animation_library("")
                            for clip_name in src_lib.get_animation_list():
                                if lib.has_animation(clip_name):
                                    continue
                                var anim := src_lib.get_animation(clip_name).duplicate() as Animation
                                var info: Dictionary = clip_by_name.get(clip_name, {})
                                if info.has("loop"):
                                    anim.loop_mode = Animation.LOOP_LINEAR if bool(info["loop"]) else Animation.LOOP_NONE
                                lib.add_animation(clip_name, anim)
                        anim_scene.free()
                    state["anim"] = player
                    print("Loaded character model for ", id, ": ", body_path)
                    return model
                print("Capsule fallback for ", id, ": model failed to load at ", body_path)
    var mesh := MeshInstance3D.new()
    var capsule := CapsuleMesh.new()
    capsule.radius = 0.35
    capsule.height = 1.7
    mesh.mesh = capsule
    var mat := StandardMaterial3D.new()
    mat.albedo_color = Color.from_string(String(state["color"]), Color.WHITE)
    mesh.material_override = mat
    mesh.position.y = 0.85
    return mesh

func _play_tag(id: String, tag: String) -> void:
    var state: Dictionary = actors.get(id, {})
    var player: AnimationPlayer = state.get("anim")
    if player == null:
        return
    var clips: Dictionary = manifest.get("clips", {})
    var entry: Dictionary = clips.get(tag, {})
    var clip := String(entry.get("clip", ""))
    if clip == "" or not player.has_animation(clip):
        push_warning("No clip mapped for tag '" + tag + "' (actor " + id + ")")
        return
    player.play(clip)
    print(id, " animation ", tag, " -> ", clip)

func _end_speak(id: String) -> void:
    var state: Dictionary = actors.get(id, {})
    var player: AnimationPlayer = state.get("anim")
    if player == null:
        return
    var entry: Dictionary = (manifest.get("clips", {}) as Dictionary).get("speak", {})
    if player.current_animation == String(entry.get("clip", "")):
        _play_tag(id, "idle")

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

func _place_furniture(piece: Dictionary) -> void:
    # Stage pieces load through the same approved, hash-verified path as
    # characters; any failure skips the piece and leaves the bare stage.
    var file := String(piece.get("file", ""))
    var label := file.get_file()
    var path := asset_root.path_join(file)
    if not FileAccess.file_exists(path):
        print("Furniture skipped: ", label, " (file unavailable at ", path, ")")
        return
    if String(piece.get("status", "")) != "approved":
        print("Furniture skipped: ", label, " (asset rejected: status is '", String(piece.get("status", "")), "', approved required)")
        return
    var expected := String(piece.get("sha256", ""))
    if expected == "" or _sha256_of_file(path) != expected:
        print("Furniture skipped: ", label, " (asset rejected: sha256 mismatch)")
        return
    var node := _load_gltf(path)
    if node == null:
        print("Furniture skipped: ", label, " (glTF load failed)")
        return
    node.position = _vec3(piece.get("position", [0, 0, 0]))
    node.rotation_degrees.y = float(piece.get("rotation_y_deg", 0))
    add_child(node)
    print("Placed furniture: ", label, " at ", node.position)

func _build_stage() -> void:
    var floor_mesh := MeshInstance3D.new()
    var box := BoxMesh.new()
    box.size = Vector3(12, 0.15, 8)
    floor_mesh.mesh = box
    floor_mesh.position.y = -0.1
    add_child(floor_mesh)
    var stage: Dictionary = manifest.get("stage", {})
    if not stage.is_empty() and asset_root != "":
        for piece in stage.get("pieces", []):
            _place_furniture(piece)
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
