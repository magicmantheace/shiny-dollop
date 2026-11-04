extends Node3D
## Minimal renderer/protocol proof. Procedural stand-ins, no real rig, no AI/TTS.

## Wire constants; SCHEMA_VERSION must match VERSION in studio/schema.py
## and OPS must match its OPS set (guarded by tests/test_conformance.py).
const SCHEMA_VERSION := "1.0.0"
const VALID_OPS := ["spawn", "move", "speak", "emote", "camera"]

## Director-to-engine IPC (F2.4, studio/ipc.py): the runtime slot may carry
## a versioned envelope {ipc_version, kind: "scene", payload} instead of a
## bare scene. IPC_VERSION mirrors IPC_VERSION in studio/ipc.py (parity
## guarded by tests/test_ipc.py). Enveloped loads are acknowledged with a
## result document at RESULT_PATH; bare scenes keep the pre-IPC behavior
## exactly (no result file).
const IPC_VERSION := "1.0.0"
const RESULT_PATH := "res://data/scene_result.json"

## Speak timing (ADR-009): changeable variables, not constants. A scene may
## override them with a top-level "timing" object; the defaults mirror
## studio/timing.py (parity guarded by tests/test_timing.py).
@export var speak_chars_per_second: float = 15.0
@export var speak_min_hold_ms: int = 800
@export var speak_max_hold_ms: int = 15000

## Gaze (F4.1, docs/SCENE_PROTOCOL.md): during a speak/emote/move event's
## look_at window the actor's head bone turns toward the target. The clamps
## are hard limits on yaw/pitch relative to the actor's facing.
const GAZE_MAX_YAW_DEG := 60.0
const GAZE_MAX_PITCH_DEG := 30.0
const GAZE_HEAD_BONE := "Head"

## Upper-body bone set for the gesture overlay layer (F4.1): the
## studio_humanoid_v1 bones at/above the pelvis from docs/RIG_CONTRACT.md —
## spine chain, neck, head, arms and fingers (finger chains matched by
## prefix: index_/middle_/pinky_/ring_/thumb_). Pelvis, legs and the model
## root stay exclusively on the base layer, so a gesture can never move
## the legs or the actor root.
const UPPER_BODY_BONES := ["spine_01", "spine_02", "spine_03", "neck_01", "Head", "clavicle_l", "clavicle_r", "upperarm_l", "upperarm_r", "lowerarm_l", "lowerarm_r", "hand_l", "hand_r"]
const UPPER_BODY_PREFIXES := ["index_", "middle_", "pinky_", "ring_", "thumb_"]

var actors: Dictionary = {}
var events: Array = []
var schedule: Array = []
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
    # IPC envelope (F2.4): a document carrying ipc_version/kind is treated
    # as an envelope and unwrapped; anything else is a legacy bare scene.
    var enveloped: bool = parsed.has("ipc_version") or parsed.has("kind")
    var scene_doc: Dictionary = parsed
    if enveloped:
        var problem := _ipc_envelope_problem(parsed)
        if problem != "":
            push_error("IPC envelope rejected (" + problem + "): " + source)
            _write_result(_envelope_scene_id(parsed), false, problem)
            return
        scene_doc = parsed["payload"]
    # Cheap re-validation at load: parsed JSON is not trusted input.
    # This mirrors the fail-closed wire subset of studio/schema.py that the
    # preview executes; full semantic validation stays on the Python side.
    if String(scene_doc.get("schema_version", "")) != SCHEMA_VERSION:
        _reject_load(source, "Unsupported schema_version (expected " + SCHEMA_VERSION + ")", enveloped, scene_doc)
        return
    var raw_actors: Variant = scene_doc.get("actors")
    var raw_events: Variant = scene_doc.get("events")
    if typeof(raw_actors) != TYPE_ARRAY or typeof(raw_events) != TYPE_ARRAY:
        _reject_load(source, "Scene actors/events must be arrays", enveloped, scene_doc)
        return
    for actor in raw_actors:
        if typeof(actor) != TYPE_DICTIONARY:
            _reject_load(source, "Actor entry is not an object; scene rejected", enveloped, scene_doc)
            return
        actors[actor.get("id", "")] = {"color": actor.get("color", "#dddddd"), "node": null, "recipe_id": String(actor.get("recipe_id", "")), "anim": null, "anim_overlay": null, "skeleton": null, "head_bone": -1, "gaze": {}}
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
    _apply_timing(scene_doc)
    _build_schedule()
    print("AI Animation Studio preview: ", scene_doc.get("scene_id", "<unnamed>"))
    if enveloped:
        _write_result(String(scene_doc.get("scene_id", "")), true,
            "scene accepted and scheduled (" + str(events.size()) + " events)")

func _ipc_envelope_problem(env: Dictionary) -> String:
    # Returns "" when env is a well-formed scene envelope for IPC_VERSION,
    # otherwise the named rejection reason (mirrors studio/ipc.py).
    if String(env.get("ipc_version", "")) != IPC_VERSION:
        return "unsupported ipc_version '" + String(env.get("ipc_version", "")) + "' (expected " + IPC_VERSION + ")"
    if String(env.get("kind", "")) != "scene":
        return "unknown kind '" + String(env.get("kind", "")) + "' (expected 'scene')"
    if typeof(env.get("payload")) != TYPE_DICTIONARY:
        return "envelope payload is not an object"
    return ""

func _envelope_scene_id(env: Dictionary) -> String:
    var payload: Variant = env.get("payload")
    if typeof(payload) == TYPE_DICTIONARY:
        return String(payload.get("scene_id", ""))
    return ""

func _reject_load(source: String, reason: String, enveloped: bool, scene_doc: Dictionary) -> void:
    push_error(reason + ": " + source)
    if enveloped:
        _write_result(String(scene_doc.get("scene_id", "")), false, reason)

func _write_result(scene_id: String, accepted: bool, detail: String) -> void:
    # IPC acknowledgement (F2.4): the result document the director reads
    # back; shape mirrors studio/ipc.py result documents.
    var doc := {
        "ipc_version": IPC_VERSION,
        "kind": "result",
        "scene_id": scene_id,
        "accepted": accepted,
        "detail": detail,
    }
    var f := FileAccess.open(RESULT_PATH, FileAccess.WRITE)
    if f == null:
        push_warning("Could not write IPC result file: " + RESULT_PATH)
        return
    f.store_string(JSON.stringify(doc, "  ") + "\n")
    f.close()

func _apply_timing(scene: Dictionary) -> void:
    # Scene-level "timing" object overrides the exported settings above.
    # Out-of-range values are named and ignored (fail-soft per key), the
    # Python validator remains the fail-closed gate for authored scenes.
    var source := "preview settings"
    var raw: Variant = scene.get("timing")
    if typeof(raw) == TYPE_DICTIONARY:
        source = "scene"
        var t: Dictionary = raw
        if t.has("speak_chars_per_second"):
            var r: Variant = t["speak_chars_per_second"]
            if (typeof(r) == TYPE_INT or typeof(r) == TYPE_FLOAT) and float(r) > 0.0 and float(r) <= 100.0:
                speak_chars_per_second = float(r)
            else:
                push_warning("timing.speak_chars_per_second invalid; keeping " + str(speak_chars_per_second))
        if t.has("speak_min_hold_ms"):
            var v: Variant = _as_int(t["speak_min_hold_ms"])
            if v != null and int(v) >= 0 and int(v) <= 60000:
                speak_min_hold_ms = int(v)
            else:
                push_warning("timing.speak_min_hold_ms invalid; keeping " + str(speak_min_hold_ms))
        if t.has("speak_max_hold_ms"):
            var w: Variant = _as_int(t["speak_max_hold_ms"])
            if w != null and int(w) >= 0 and int(w) <= 60000:
                speak_max_hold_ms = int(w)
            else:
                push_warning("timing.speak_max_hold_ms invalid; keeping " + str(speak_max_hold_ms))
        if speak_min_hold_ms > speak_max_hold_ms:
            push_warning("timing clamps inverted (min > max); swapping")
            var tmp := speak_min_hold_ms
            speak_min_hold_ms = speak_max_hold_ms
            speak_max_hold_ms = tmp
    print("Timing: rate ", speak_chars_per_second, " chars/s, speak hold clamp ", speak_min_hold_ms, "..", speak_max_hold_ms, " ms (source: ", source, ")")

func _as_int(v: Variant) -> Variant:
    # JSON numbers arrive as floats; accept integral values of either type.
    if typeof(v) == TYPE_INT:
        return int(v)
    if typeof(v) == TYPE_FLOAT and float(v) == floor(float(v)):
        return int(v)
    return null

func _speak_hold_ms(e: Dictionary) -> int:
    # Mirrors studio/timing.py speak_hold_ms: explicit duration wins,
    # otherwise derive from the line at the configured rate and clamp.
    if e.has("duration_ms"):
        var d: Variant = _as_int(e["duration_ms"])
        if d != null and int(d) >= 100 and int(d) <= 60000:
            return int(d)
        push_warning("speak duration_ms invalid; deriving hold from line")
    var line := String(e.get("line", ""))
    var derived := int(ceil(float(line.length()) * 1000.0 / speak_chars_per_second))
    return clampi(derived, speak_min_hold_ms, speak_max_hold_ms)

func _event_duration_ms(e: Dictionary) -> int:
    var d: Variant = _as_int(e.get("duration_ms", 1000))
    if d == null:
        return 1000
    return int(d)

func _dispatch_priority(op: String) -> int:
    # Dispatch order at equal effective times (F3.3, docs/SCENE_PROTOCOL.md):
    # camera first, then spawn, then the rest in scene index order. Mirrors
    # DISPATCH_PRIORITY in studio/timing.py.
    if op == "camera":
        return 0
    if op == "spawn":
        return 1
    return 2

func _build_schedule() -> void:
    # Precompute effective dispatch times (ADR-009 + F3.3 dialogue runtime):
    # a speak hold gates only later events for the SAME actor; camera is
    # never gated; spawn starts a fresh actor and is never gated. A speak
    # with "interrupt": true is never gated either — it starts at its at_ms
    # and truncates the actor's current hold window when that window
    # contains the start. This mirrors compute_schedule in studio/timing.py,
    # the single source of truth for the window computation. Dispatch order
    # is (effective, priority, index) — see _dispatch_priority.
    var hold_until: Dictionary = {}
    var open_speak: Dictionary = {}
    schedule.clear()
    for i in events.size():
        var e: Dictionary = events[i]
        var at := int(e.get("at_ms", 0))
        var op := String(e.get("op", ""))
        var eff := at
        var hold := 0
        e["_interrupted"] = false
        e["_interrupts"] = -1
        e["_window_start_ms"] = -1
        e["_window_end_ms"] = -1
        e["_gaze_start_ms"] = -1
        e["_gaze_end_ms"] = -1
        if op != "camera":
            var id := String(e.get("actor_id", ""))
            var flag: Variant = e.get("interrupt", false)
            var interrupting: bool = op == "speak" and typeof(flag) == TYPE_BOOL and bool(flag)
            if op != "spawn":
                if interrupting:
                    if open_speak.has(id):
                        var current: Dictionary = open_speak[id]
                        var w_start := int(current["_window_start_ms"])
                        var w_end := int(current["_window_end_ms"])
                        if w_start <= at and at < w_end:
                            current["_window_end_ms"] = at
                            current["_interrupted"] = true
                            e["_interrupts"] = int(current["_index"])
                            print("Speak interrupted for ", id, " at ", at, " ms")
                            print("Truncated speak hold for ", id, ": window ", w_start, "..", w_end, " -> ", w_start, "..", at, " ms")
                elif hold_until.has(id):
                    eff = maxi(at, int(hold_until[id]))
            if op == "speak":
                hold = _speak_hold_ms(e)
                hold_until[id] = eff + hold
                e["_window_start_ms"] = eff
                e["_window_end_ms"] = eff + hold
                open_speak[id] = e
        e["_index"] = i
        e["_effective_ms"] = eff
        e["_hold_ms"] = hold
        e["_priority"] = _dispatch_priority(op)
        if eff != at:
            print("Delayed ", op, " for ", String(e.get("actor_id", "")), ": at_ms ", at, " -> ", eff, " (speak hold)")
        schedule.append(e)
    # Gaze windows (F4.1): the gaze finalization in compute_schedule
    # (studio/timing.py) mirrored — a speak's gaze window is its occupancy
    # window after any truncation, a move's is its duration window, and an
    # emote's runs from its effective time until the same actor's next
    # event dispatches (or the end of the schedule). Gaze never changes
    # any scheduling value computed above.
    var scene_end := 0
    for e in events:
        var end := int(e["_effective_ms"])
        if int(e["_window_end_ms"]) >= 0:
            end = maxi(end, int(e["_window_end_ms"]))
        if String(e.get("op", "")) == "move":
            end = maxi(end, int(e["_effective_ms"]) + _event_duration_ms(e))
        scene_end = maxi(scene_end, end)
    var pending_emote: Dictionary = {}
    for e in events:
        var op := String(e.get("op", ""))
        var id := String(e.get("actor_id", ""))
        if pending_emote.has(id):
            var pending: Dictionary = pending_emote[id]
            pending["_gaze_end_ms"] = int(e["_effective_ms"])
            pending_emote.erase(id)
        if typeof(e.get("look_at")) != TYPE_DICTIONARY:
            continue
        if op == "speak":
            e["_gaze_start_ms"] = int(e["_window_start_ms"])
            e["_gaze_end_ms"] = int(e["_window_end_ms"])
        elif op == "move":
            e["_gaze_start_ms"] = int(e["_effective_ms"])
            e["_gaze_end_ms"] = int(e["_effective_ms"]) + _event_duration_ms(e)
        elif op == "emote":
            e["_gaze_start_ms"] = int(e["_effective_ms"])
            pending_emote[id] = e
    for pid in pending_emote:
        var pending: Dictionary = pending_emote[pid]
        pending["_gaze_end_ms"] = scene_end
    schedule.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
        var ea := int(a["_effective_ms"])
        var eb := int(b["_effective_ms"])
        if ea != eb:
            return ea < eb
        var pa := int(a["_priority"])
        var pb := int(b["_priority"])
        if pa != pb:
            return pa < pb
        return int(a["_index"]) < int(b["_index"])
    )

func _process(delta: float) -> void:
    clock_ms += delta * 1000.0
    while next_event < schedule.size() and float(schedule[next_event].get("_effective_ms", 0)) <= clock_ms:
        _dispatch(schedule[next_event])
        next_event += 1
    _advance_animation(delta)
    _update_gaze(delta)

func _advance_animation(delta: float) -> void:
    # Layered playback (F4.1): both players run in manual callback mode,
    # so the layer composition order is fixed here every frame — base
    # (full body) first, then the upper-body overlay — and _update_gaze
    # reads the resulting pose. Manual mode is what makes that order
    # deterministic; with automatic callbacks the two players' processing
    # order relative to this script would be engine-scheduled.
    for id in actors:
        var state: Dictionary = actors[id]
        var base: AnimationPlayer = state.get("anim") as AnimationPlayer
        if base != null:
            base.advance(delta)
        var overlay: AnimationPlayer = state.get("anim_overlay") as AnimationPlayer
        if overlay != null:
            overlay.advance(delta)

func _begin_gaze(id: String, state: Dictionary, e: Dictionary) -> void:
    # Gaze engagement (F4.1): an event with look_at opens its gaze window
    # at dispatch — dispatch time is the window start for speak, emote and
    # move alike. Actors without a skeleton (capsule fallback) log the
    # skip once per window and carry on; gaze is presentation only.
    var node: Node3D = state.get("node") as Node3D
    if node == null:
        return
    var look: Dictionary = e["look_at"]
    var start := int(e.get("_gaze_start_ms", -1))
    var end := int(e.get("_gaze_end_ms", -1))
    if end <= start:
        return
    var desc := ""
    var target_actor := ""
    var target_point := Vector3.ZERO
    if look.has("actor_id"):
        target_actor = String(look.get("actor_id", ""))
        desc = target_actor
    elif look.has("position"):
        var p: Variant = _parse_vec3(look.get("position"))
        if p == null:
            return
        target_point = p
        desc = "position " + str(target_point)
    else:
        return
    var skeleton: Skeleton3D = state.get("skeleton") as Skeleton3D
    if skeleton == null or int(state.get("head_bone", -1)) < 0:
        print("Gaze skipped: ", id, " -> ", desc, " (no skeleton)")
        return
    if target_actor != "":
        var target_state: Dictionary = actors.get(target_actor, {})
        if (target_state.get("node") as Node3D) == null:
            print("Gaze skipped: ", id, " -> ", desc, " (target not spawned)")
            return
    state["gaze"] = {
        "target_actor": target_actor,
        "target_point": target_point,
        "end_ms": end,
        "yaw": 0.0,
        "pitch": 0.0,
    }
    var angles := _gaze_angles(state, state["gaze"])
    print("Gaze: ", id, " -> ", desc, " (yaw ", snappedf(rad_to_deg(float(angles["yaw"])), 0.1), ", pitch ", snappedf(rad_to_deg(float(angles["pitch"])), 0.1), ")")

func _gaze_angles(state: Dictionary, gaze: Dictionary) -> Dictionary:
    # Clamped yaw/pitch (radians) aiming the actor's head at the gaze
    # target, in the actor's facing frame (forward is -Z). Recomputed
    # from current positions on every call — targets may move.
    var skeleton: Skeleton3D = state.get("skeleton") as Skeleton3D
    var head_bone := int(state.get("head_bone", -1))
    var node: Node3D = state.get("node") as Node3D
    var head_pos := skeleton.global_transform * skeleton.get_bone_global_pose(head_bone).origin
    var target_pos := Vector3.ZERO
    var target_actor := String(gaze.get("target_actor", ""))
    if target_actor != "":
        var target_state: Dictionary = actors.get(target_actor, {})
        var target_node: Node3D = target_state.get("node") as Node3D
        var target_skeleton: Skeleton3D = target_state.get("skeleton") as Skeleton3D
        var target_head := int(target_state.get("head_bone", -1))
        if target_skeleton != null and target_head >= 0:
            target_pos = target_skeleton.global_transform * target_skeleton.get_bone_global_pose(target_head).origin
        elif target_node != null:
            target_pos = target_node.global_position + Vector3(0.0, 1.5, 0.0)
    else:
        target_pos = gaze.get("target_point", Vector3.ZERO)
    var dir := target_pos - head_pos
    if dir.length() < 0.0001:
        return {"yaw": 0.0, "pitch": 0.0}
    var local := node.global_transform.basis.inverse() * dir.normalized()
    var yaw := clampf(atan2(-local.x, -local.z), -deg_to_rad(GAZE_MAX_YAW_DEG), deg_to_rad(GAZE_MAX_YAW_DEG))
    var pitch := clampf(asin(clampf(local.y, -1.0, 1.0)), -deg_to_rad(GAZE_MAX_PITCH_DEG), deg_to_rad(GAZE_MAX_PITCH_DEG))
    return {"yaw": yaw, "pitch": pitch}

func _update_gaze(delta: float) -> void:
    # Per-frame gaze (F4.1): while the window is open, ease the head
    # toward the clamped aim (recomputed each frame — moving targets are
    # tracked); once the window closes, ease back to the animated pose.
    # The pose read here is animation-only: the base layer always carries
    # a looping full-body clip (idle/walk), which re-applies the Head
    # track on every advance, and the overlay advances before this runs.
    for id in actors:
        var state: Dictionary = actors[id]
        var gaze: Dictionary = state.get("gaze", {})
        if gaze.is_empty():
            continue
        var skeleton: Skeleton3D = state.get("skeleton") as Skeleton3D
        if skeleton == null:
            continue
        var goal_yaw := 0.0
        var goal_pitch := 0.0
        var open: bool = clock_ms < float(int(gaze.get("end_ms", 0)))
        if open:
            var angles := _gaze_angles(state, gaze)
            goal_yaw = float(angles["yaw"])
            goal_pitch = float(angles["pitch"])
        var blend := 1.0 - exp(-10.0 * delta)
        var yaw := lerpf(float(gaze.get("yaw", 0.0)), goal_yaw, blend)
        var pitch := lerpf(float(gaze.get("pitch", 0.0)), goal_pitch, blend)
        gaze["yaw"] = yaw
        gaze["pitch"] = pitch
        if not open and absf(yaw) < 0.001 and absf(pitch) < 0.001:
            state["gaze"] = {}
            continue
        state["gaze"] = gaze
        _apply_gaze(state, yaw, pitch)

func _apply_gaze(state: Dictionary, yaw: float, pitch: float) -> void:
    # Compose the gaze rotation onto the head bone's animated pose: the
    # yaw/pitch pair (actor facing frame) becomes a world-space spin
    # about the head, converted back into the bone's pose rotation.
    var skeleton: Skeleton3D = state.get("skeleton") as Skeleton3D
    var head_bone := int(state.get("head_bone", -1))
    var node: Node3D = state.get("node") as Node3D
    if skeleton == null or head_bone < 0 or node == null:
        return
    var skel_q := skeleton.global_transform.basis.get_rotation_quaternion()
    var head_global := skeleton.get_bone_global_pose(head_bone).basis.get_rotation_quaternion()
    var parent_global := Quaternion.IDENTITY
    var parent := skeleton.get_bone_parent(head_bone)
    if parent >= 0:
        parent_global = skeleton.get_bone_global_pose(parent).basis.get_rotation_quaternion()
    var frame_q := node.global_transform.basis.get_rotation_quaternion()
    var gaze_q := Quaternion(Vector3.UP, yaw) * Quaternion(Vector3.RIGHT, pitch)
    var world_spin := frame_q * gaze_q * frame_q.inverse()
    var desired := skel_q.inverse() * (world_spin * (skel_q * head_global))
    var rest_q := skeleton.get_bone_rest(head_bone).basis.get_rotation_quaternion()
    skeleton.set_bone_pose_rotation(head_bone, rest_q.inverse() * (parent_global.inverse() * desired))

func _dispatch(e: Dictionary) -> void:
    var op := String(e.get("op", ""))
    if op == "camera":
        print("Camera request: ", e.get("shot", "wide"))
        return
    var id := String(e.get("actor_id", ""))
    if not actors.has(id):
        # Queue safety (F3.3): unreachable after load validation; skip the
        # event with a named error and keep the queue moving — no crash,
        # no stall. This is a thin dispatch guard, not a second validator.
        push_error("Dispatch skipped: event " + str(int(e.get("_index", -1))) + " references unknown actor '" + id + "' (op " + op + ")")
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
        push_error("Dispatch skipped: actor '" + id + "' has no spawned node (event " + str(int(e.get("_index", -1))) + ", op " + op + ")")
    elif op == "move":
        var duration: float = max(0.1, float(e.get("duration_ms", 1000)) / 1000.0)
        var tween := create_tween()
        tween.tween_property(state["node"], "position", _vec3(e.get("target", [0, 0, 0])), duration)
        if state["anim"] != null:
            _play_tag(id, "walk")
            tween.tween_callback(_play_tag.bind(id, "idle"))
    elif op == "speak":
        print(id, ": ", e.get("line", ""))
        var hold_ms := int(e.get("_hold_ms", 0))
        var occupied_ms := hold_ms
        var w_end := int(e.get("_window_end_ms", -1))
        if w_end >= 0:
            # The actor occupies the window, not the authored hold: an
            # interrupted speak hands the floor over at the truncation.
            occupied_ms = w_end - int(e.get("_effective_ms", 0))
        var explicit := false
        if e.has("duration_ms"):
            var d: Variant = _as_int(e["duration_ms"])
            explicit = d != null and int(d) >= 100 and int(d) <= 60000
        print("Speak hold for ", id, ": ", occupied_ms, " ms (", "explicit" if explicit else "derived", ")")
        if state["anim"] != null or state["anim_overlay"] != null:
            _play_overlay_tag(id, "speak")
            get_tree().create_timer(maxf(0.05, float(occupied_ms) / 1000.0)).timeout.connect(_end_speak.bind(id))
    elif op == "emote":
        print(id, " emotion: ", e.get("emotion", "neutral"), " intensity: ", e.get("intensity", 0.0))
    if op in ["speak", "emote", "move"] and typeof(e.get("look_at")) == TYPE_DICTIONARY:
        _begin_gaze(id, state, e)

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
                    player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
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
                    # F4.1 layering: a second player carries upper-body-only
                    # copies of the same clips (the gesture channel — speak
                    # today, emotes when they gain clip dispatch). It is
                    # advanced after the base player every frame (see
                    # _advance_animation), so its tracks win on upper-body
                    # bones while the base keeps the pelvis, legs and root.
                    var overlay := AnimationPlayer.new()
                    overlay.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
                    model.add_child(overlay)
                    var overlay_lib := AnimationLibrary.new()
                    overlay.add_animation_library("", overlay_lib)
                    var overlay_clips := 0
                    for clip_name in lib.get_animation_list():
                        var filtered := _upper_body_clip(lib.get_animation(clip_name))
                        if filtered.get_track_count() > 0:
                            overlay_lib.add_animation(clip_name, filtered)
                            overlay_clips += 1
                    if overlay_clips > 0:
                        state["anim_overlay"] = overlay
                        print("Layered animation for ", id, ": base player + upper-body overlay (", overlay_clips, " clips)")
                    else:
                        overlay.free()
                    var found := model.find_children("*", "Skeleton3D", true, false)
                    if not found.is_empty():
                        var skeleton: Skeleton3D = found[0] as Skeleton3D
                        state["skeleton"] = skeleton
                        state["head_bone"] = skeleton.find_bone(GAZE_HEAD_BONE)
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

func _is_upper_body_bone(bone: String) -> bool:
    if bone in UPPER_BODY_BONES:
        return true
    for prefix in UPPER_BODY_PREFIXES:
        if bone.begins_with(prefix):
            return true
    return false

func _upper_body_clip(anim: Animation) -> Animation:
    # Upper-body-only copy of a full-body clip for the overlay layer:
    # tracks targeting an upper-body bone (docs/RIG_CONTRACT.md set) are
    # kept verbatim; root/lower-body tracks are dropped, so a gesture can
    # never move the pelvis, legs or actor root.
    var out := Animation.new()
    out.length = anim.length
    out.loop_mode = anim.loop_mode
    for i in anim.get_track_count():
        var path := anim.track_get_path(i)
        if path.get_subname_count() == 0:
            continue
        if not _is_upper_body_bone(String(path.get_subname(0))):
            continue
        var nt := out.add_track(anim.track_get_type(i))
        out.track_set_path(nt, path)
        out.track_set_interpolation_type(nt, anim.track_get_interpolation_type(i))
        for k in anim.track_get_key_count(i):
            out.track_insert_key(nt, anim.track_get_key_time(i, k), anim.track_get_key_value(i, k), anim.track_get_key_transition(i, k))
    return out

func _play_tag(id: String, tag: String) -> void:
    var state: Dictionary = actors.get(id, {})
    _play_tag_on(state.get("anim") as AnimationPlayer, id, tag)

func _play_overlay_tag(id: String, tag: String) -> void:
    # Gesture channel (F4.1): gestures play on the upper-body overlay so
    # the base layer keeps its clip (idle, or a walk already in flight).
    # Without an overlay — no upper-body tracks in the actor's clips —
    # this is exactly the pre-F4.1 single-player behavior.
    var state: Dictionary = actors.get(id, {})
    var overlay: AnimationPlayer = state.get("anim_overlay") as AnimationPlayer
    if overlay == null:
        _play_tag(id, tag)
        return
    _play_tag_on(overlay, id, tag)
    var base: AnimationPlayer = state.get("anim") as AnimationPlayer
    if base != null and base.current_animation != "":
        var entry: Dictionary = (manifest.get("clips", {}) as Dictionary).get(tag, {})
        print("Layered: ", id, " base ", base.current_animation, " + overlay ", String(entry.get("clip", "")))

func _play_tag_on(player: AnimationPlayer, id: String, tag: String) -> void:
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
    var entry: Dictionary = (manifest.get("clips", {}) as Dictionary).get("speak", {})
    var overlay: AnimationPlayer = state.get("anim_overlay") as AnimationPlayer
    if overlay != null:
        # Layered path: the gesture ends by stopping the overlay; the
        # base layer's clip (idle/walk) was never interrupted.
        if overlay.current_animation == String(entry.get("clip", "")):
            overlay.stop()
        return
    var player: AnimationPlayer = state.get("anim")
    if player == null:
        return
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
