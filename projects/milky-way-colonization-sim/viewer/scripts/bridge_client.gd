extends RefCounted
## Client for the sim-bridge binary (bridge/ crate).
## (Preloaded rather than class_name-registered, like StarTable, so
## the project parses in a bare headless run with no editor import
## pass.)
##
## Protocol (fixed): invoke
##   sim-bridge --data <stars.bin> --request <req.json> --response <res.json>
## Request is one JSON object with "op"; the response file always
## carries "ok" (bool) and, on failure, "error" (String). All traffic
## is file-based: this client writes the request JSON, runs the
## binary with OS.execute (blocking), and parses the response JSON.
## Any transport failure is reported as
## {"ok": false, "error": "bridge call failed: ..."} — never a crash.
##
## NOTE: the single entry point is call_bridge(), not call() —
## Godot 4.7 treats a Dictionary-argument call() as a mismatched
## override of Object.call() and refuses to compile the script.

var data_path: String = ""
var bridge_path: String = ""
var work_dir: String = ""


## work_dir is a globalized (absolute) path, typically under user://.
func setup(p_data_path: String, p_bridge_path: String, p_work_dir: String) -> void:
	data_path = p_data_path
	bridge_path = p_bridge_path
	work_dir = p_work_dir
	if work_dir != "":
		DirAccess.make_dir_recursive_absolute(work_dir)


## Candidates, in order: the explicit --bridge= path, a bridge binary
## placed next to the project, then the bridge crate's build outputs
## (native release, then the Windows cross build). Returns "" when no
## candidate exists.
func find_bridge(explicit: String) -> String:
	if explicit != "" and FileAccess.file_exists(explicit):
		return explicit
	var project_dir := ProjectSettings.globalize_path("res://")
	var candidates := [
		project_dir + "../sim-bridge.exe",
		project_dir + "../sim-bridge",
		project_dir + "../bridge/target/release/sim-bridge",
		project_dir + "../bridge/target/x86_64-pc-windows-gnu/release/sim-bridge.exe",
		project_dir + "sim-bridge.exe",
		project_dir + "sim-bridge",
	]
	for c in candidates:
		if FileAccess.file_exists(c):
			return c
	return ""


func call_bridge(request: Dictionary) -> Dictionary:
	if bridge_path == "":
		return {"ok": false, "error": "bridge call failed: no bridge binary found"}
	if work_dir == "":
		return {"ok": false, "error": "bridge call failed: client not set up"}
	var req_path := work_dir.path_join("request.json")
	var res_path := work_dir.path_join("response.json")
	var f := FileAccess.open(req_path, FileAccess.WRITE)
	if f == null:
		return {"ok": false, "error": "bridge call failed: cannot write request file %s" % req_path}
	f.store_string(JSON.stringify(request))
	f.close()
	# Remove any stale response so a failed run cannot be mistaken
	# for a fresh one.
	if FileAccess.file_exists(res_path):
		DirAccess.remove_absolute(res_path)
	var output: Array = []
	var code := OS.execute(bridge_path, ["--data", data_path, "--request", req_path, "--response", res_path], output, true)
	if code == -1:
		return {"ok": false, "error": "bridge call failed: could not execute %s" % bridge_path}
	if not FileAccess.file_exists(res_path):
		var detail := ""
		if not output.is_empty():
			detail = ": " + str(output[0]).strip_edges()
		return {"ok": false, "error": "bridge call failed: no response file (exit %d)%s" % [code, detail]}
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(res_path))
	if parsed is Dictionary:
		return parsed
	return {"ok": false, "error": "bridge call failed: unparseable response"}
