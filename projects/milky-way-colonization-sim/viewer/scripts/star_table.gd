extends RefCounted
## Reader for the pipeline's binary star table. This mirrors
## pipeline/src/table.rs EXACTLY — the format is the contract between
## the Rust pipeline and this viewer; change both sides together.
##
## Layout: 64-byte header ("MWST", version u32, star_count u32,
## planet_count u32, stars/planets/strings offsets u64), then
## star_count x 48-byte star records, a planets section (u32 reserved,
## then per-host: u32 count + count x 32-byte planet records), and a
## NUL-terminated string table.

const HEADER_LEN := 64
const STAR_LEN := 48
const PLANET_LEN := 32

const FLAG_NAMED := 1
const FLAG_HAS_PLANETS := 2
const FLAG_GENERATED := 4
const FLAG_MULTIPLE := 8
const FLAG_TEMP_DERIVED := 16
const FLAG_MASS_DERIVED := 32
const FLAG_SOURCE_EXOPLANET_ARCHIVE := 64

const SPECTRAL_LETTERS := ["O", "B", "A", "F", "G", "K", "M", "Other", "Unknown"]
const METHOD_NAMES := [
	"Unknown", "Radial Velocity", "Transit", "Imaging", "Microlensing",
	"Transit Timing Variations", "Eclipse Timing Variations",
	"Pulsar Timing", "Pulsation Timing Variations",
	"Orbital Brightness Modulation", "Astrometry", "Disk Kinematics",
]

var star_count: int = 0
var planet_count: int = 0
var positions := PackedVector3Array()
var absmag := PackedFloat32Array()
var bv := PackedFloat32Array()
var teff := PackedFloat32Array()
var mass := PackedFloat32Array()
var spectral := PackedByteArray()
var flags := PackedByteArray()

var _bytes := PackedByteArray()
var _planets_offset: int = 0
var _strings_offset: int = 0
var _name_offsets := PackedInt32Array()
var _planet_offsets := PackedInt32Array()
var _name_index: Dictionary = {}
var _name_index_built := false
var _grid: Dictionary = {}
var _grid_cell: float = 50.0


func load(path: String) -> Error:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		push_error("StarTable: cannot open %s" % path)
		return FileAccess.get_open_error()
	_bytes = f.get_buffer(f.get_length())
	f.close()
	if _bytes.size() < HEADER_LEN or _bytes.slice(0, 4).get_string_from_ascii() != "MWST":
		push_error("StarTable: bad magic in %s" % path)
		return ERR_INVALID_DATA
	var spb := StreamPeerBuffer.new()
	spb.data_array = _bytes
	spb.big_endian = false
	spb.seek(4)
	var version: int = spb.get_u32()
	if version != 1:
		push_error("StarTable: unsupported format version %d" % version)
		return ERR_INVALID_DATA
	star_count = spb.get_u32()
	planet_count = spb.get_u32()
	var stars_offset: int = spb.get_u64()
	_planets_offset = spb.get_u64()
	_strings_offset = spb.get_u64()

	positions.resize(star_count)
	absmag.resize(star_count)
	bv.resize(star_count)
	teff.resize(star_count)
	mass.resize(star_count)
	spectral.resize(star_count)
	flags.resize(star_count)
	_name_offsets.resize(star_count)
	_planet_offsets.resize(star_count)
	for i in star_count:
		var base := stars_offset + i * STAR_LEN
		spb.seek(base + 4)
		positions[i] = Vector3(spb.get_float(), spb.get_float(), spb.get_float())
		absmag[i] = spb.get_float()
		bv[i] = spb.get_float()
		teff[i] = spb.get_float()
		mass[i] = spb.get_float()
		spectral[i] = spb.get_u8()
		flags[i] = spb.get_u8()
		spb.seek(base + 36)
		_planet_offsets[i] = spb.get_u32()
		_name_offsets[i] = spb.get_u32()
	return OK


func get_name(i: int) -> String:
	var start := _strings_offset + _name_offsets[i]
	var end := start
	while end < _bytes.size() and _bytes[end] != 0:
		end += 1
	return _bytes.slice(start, end).get_string_from_utf8()


func spectral_letter(i: int) -> String:
	var code: int = spectral[i]
	if code >= 0 and code < SPECTRAL_LETTERS.size():
		return SPECTRAL_LETTERS[code]
	return "Unknown"


## Case-insensitive exact-name lookup; builds the full name index on
## first call (one scan of the string table).
func find_by_name(target: String) -> int:
	if not _name_index_built:
		_name_index_built = true
		for i in star_count:
			_name_index[get_name(i).to_lower()] = i
	var key := target.to_lower()
	if _name_index.has(key):
		return int(_name_index[key])
	return -1


func get_planets(i: int) -> Array:
	var result: Array = []
	var off := _planet_offsets[i]
	if off == 0:
		return result
	var spb := StreamPeerBuffer.new()
	spb.data_array = _bytes
	spb.big_endian = false
	var base := _planets_offset + off
	spb.seek(base)
	var count: int = spb.get_u32()
	for j in count:
		var pb := base + 4 + j * PLANET_LEN
		spb.seek(pb)
		var name_off: int = spb.get_u32()
		var planet := {
			"name": _string_at(name_off),
			"period_days": spb.get_float(),
			"semimajor_au": spb.get_float(),
			"radius_earth": spb.get_float(),
			"mass_earth": spb.get_float(),
			"eq_temp": spb.get_float(),
		}
		planet["disc_year"] = spb.get_u16()
		var method_code: int = spb.get_u8()
		planet["method"] = METHOD_NAMES[method_code] if method_code < METHOD_NAMES.size() else "Unknown"
		planet["flags"] = spb.get_u8()
		result.append(planet)
	return result


func _string_at(offset: int) -> String:
	var start := _strings_offset + offset
	var end := start
	while end < _bytes.size() and _bytes[end] != 0:
		end += 1
	return _bytes.slice(start, end).get_string_from_utf8()


func build_grid(cell: float = 50.0) -> void:
	_grid_cell = cell
	_grid.clear()
	for i in star_count:
		var key := _cell_of(positions[i])
		if not _grid.has(key):
			_grid[key] = []
		(_grid[key] as Array).append(i)


func _cell_of(p: Vector3) -> Vector3i:
	return Vector3i(
		int(floor(p.x / _grid_cell)),
		int(floor(p.y / _grid_cell)),
		int(floor(p.z / _grid_cell))
	)


## Nearest star to a 3D point (expanding cell shells). Returns the star
## index or -1.
func nearest_to_point(p: Vector3, max_radius: float = 100000.0) -> int:
	if _grid.is_empty():
		build_grid()
	var centre := _cell_of(p)
	var best := -1
	var best_d := INF
	var shell := 0
	while shell * _grid_cell <= max_radius + _grid_cell:
		for dx in range(-shell, shell + 1):
			for dy in range(-shell, shell + 1):
				for dz in range(-shell, shell + 1):
					if maxi(maxi(absi(dx), absi(dy)), absi(dz)) != shell:
						continue
					var key := centre + Vector3i(dx, dy, dz)
					if _grid.has(key):
						for i in _grid[key]:
							var d := positions[i].distance_squared_to(p)
							if d < best_d:
								best_d = d
								best = i
		if best >= 0 and sqrt(best_d) < shell * _grid_cell:
			break
		shell += 1
	return best


## Nearest star to a ray within max_perp (ly), or -1. Walks the grid
## along the ray so a click stays fast even with 100k+ stars.
func nearest_to_ray(origin: Vector3, dir: Vector3, max_dist: float, max_perp: float) -> int:
	if _grid.is_empty():
		build_grid()
	var best := -1
	var best_perp := max_perp
	var best_t := INF
	var step := _grid_cell
	var t := 0.0
	while t <= max_dist:
		var p := origin + dir * t
		var centre := _cell_of(p)
		for dx in range(-1, 2):
			for dy in range(-1, 2):
				for dz in range(-1, 2):
					var key := centre + Vector3i(dx, dy, dz)
					if _grid.has(key):
						for i in _grid[key]:
							var rel := positions[i] - origin
							var along := rel.dot(dir)
							if along < 0.0 or along > max_dist:
								continue
							var perp := (rel - dir * along).length()
							if perp < best_perp or (perp == best_perp and along < best_t):
								best_perp = perp
								best_t = along
								best = i
		if best >= 0 and t > best_t + step * 2.0:
			break
		t += step
	return best
