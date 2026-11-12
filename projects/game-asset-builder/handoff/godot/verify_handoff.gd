extends SceneTree
## Playback verification for Game Asset Builder hand-off packages
## (Godot 4). See project.godot in this folder for the run commands.
##
## Reads res://verify-spec.json:
##   {"assets": [{"slug": ..., "rigged": bool,
##                "bones": [...], "actions": [...]}]}
## For every asset it instances res://assets/<slug>/<slug>.tscn and:
##   rigged — the Skeleton3D bone set must equal the spec's, every
##            expected clip must exist with length > 0, and sampling
##            bone global poses at t=0 vs mid-clip must show motion
##            (max component delta > 0.0005, in metres/radians).
##   prop   — no skeleton, no animations, at least one mesh.
## Prints GODOT_VERIFY <json> per asset and GODOT_VERIFY_DONE <json>;
## exit code 0 only when every asset passed.

func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var spec: Dictionary = JSON.parse_string(
		FileAccess.get_file_as_string("res://verify-spec.json"))
	var all_ok := true
	for asset in spec.get("assets", []):
		var result: Dictionary = await _verify_asset(asset)
		if not result.get("ok", false):
			all_ok = false
		print("GODOT_VERIFY " + JSON.stringify(result))
	print("GODOT_VERIFY_DONE " + JSON.stringify({"ok": all_ok}))
	quit(0 if all_ok else 1)


func _sample_poses(skel: Skeleton3D) -> Array:
	var poses: Array = []
	skel.force_update_all_bone_transforms()
	for i in skel.get_bone_count():
		var t: Transform3D = skel.get_bone_global_pose(i)
		poses.append([t.origin, t.basis.x, t.basis.y, t.basis.z])
	return poses


func _max_delta(a: Array, b: Array) -> float:
	var m := 0.0
	for i in mini(a.size(), b.size()):
		for j in 4:
			m = maxf(m, (a[i][j] as Vector3).distance_to(b[i][j]))
	return m


func _find_anim(player: AnimationPlayer, wanted: String) -> String:
	for anim_name in player.get_animation_list():
		if anim_name == wanted or anim_name.ends_with("/" + wanted):
			return anim_name
	return ""


## find_child() matches node NAMES, not types — the glTF importer
## happens to name its AnimationPlayer/Skeleton3D nodes after their
## types, but mesh nodes carry the asset's own node names, so type
## checks must walk the tree explicitly.
func _find_by_type(node: Node, type_name: String) -> Node:
	for child in node.get_children():
		if child.is_class(type_name):
			return child
		var found := _find_by_type(child, type_name)
		if found != null:
			return found
	return null


func _verify_asset(asset: Dictionary) -> Dictionary:
	var slug: String = asset["slug"]
	var r: Dictionary = {"slug": slug, "ok": false, "clips": {}}
	var packed: PackedScene = load(
		"res://assets/%s/%s.tscn" % [slug, slug])
	if packed == null:
		r["error"] = "wrapper scene failed to load"
		return r
	var inst: Node = packed.instantiate()
	root.add_child(inst)
	await process_frame
	await process_frame
	var player := _find_by_type(inst, "AnimationPlayer") as AnimationPlayer
	var skel := _find_by_type(inst, "Skeleton3D") as Skeleton3D
	if not asset.get("rigged", false):
		var animations: Array = [] if player == null \
			else player.get_animation_list()
		r["bones"] = 0 if skel == null else skel.get_bone_count()
		r["animations"] = animations
		r["ok"] = _find_by_type(inst, "MeshInstance3D") != null \
			and r["bones"] == 0 and animations.is_empty()
		inst.queue_free()
		return r
	if player == null or skel == null:
		r["error"] = "rigged asset missing AnimationPlayer or Skeleton3D"
		inst.queue_free()
		return r
	var want_bones: Array = asset.get("bones", [])
	var got_bones: Array = []
	for i in skel.get_bone_count():
		got_bones.append(skel.get_bone_name(i))
	var sorted_got := got_bones.duplicate()
	sorted_got.sort()
	var sorted_want := want_bones.duplicate()
	sorted_want.sort()
	r["bones"] = skel.get_bone_count()
	r["bone_names_match"] = sorted_got == sorted_want
	var ok: bool = r["bone_names_match"] \
		and skel.get_bone_count() == want_bones.size()
	for action in asset.get("actions", []):
		var found := _find_anim(player, action)
		if found == "":
			r["clips"][action] = {"found": false}
			ok = false
			continue
		var anim := player.get_animation(found)
		player.play(found)
		player.seek(0.0, true)
		var p0 := _sample_poses(skel)
		player.seek(maxf(anim.length * 0.5, 0.01), true)
		var p1 := _sample_poses(skel)
		var delta := _max_delta(p0, p1)
		# P4 follow-up (additive reporting; pass criteria unchanged):
		# quarter-cycle delta counters the documented mid-cycle blind
		# spot for anti-phase gaits, and loop_mode records how the
		# engine imported the clip (0 none, 1 linear, 2 pingpong).
		player.seek(maxf(anim.length * 0.25, 0.01), true)
		var pq := _sample_poses(skel)
		var delta_q := _max_delta(p0, pq)
		var clip_ok: bool = anim.length > 0.0 and delta > 0.0005
		r["clips"][action] = {"found": true, "length_s": anim.length,
			"max_bone_delta": delta, "max_bone_delta_quarter": delta_q,
			"loop_mode": anim.loop_mode, "ok": clip_ok}
		ok = ok and clip_ok
	r["ok"] = ok
	inst.queue_free()
	return r
