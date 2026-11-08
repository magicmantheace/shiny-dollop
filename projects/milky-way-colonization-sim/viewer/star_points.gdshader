shader_type spatial;
// Star points: unshaded, coloured per star via the COLOR attribute
// (vertex colour). The colour's alpha channel carries the point-size
// class computed from absolute magnitude in main.gd; it is not used
// for blending (points are opaque).
render_mode unshaded, cull_disabled, depth_draw_opaque;

void vertex() {
	// VERTEX is in view space here; its length is the eye distance.
	float eye_dist = max(length(VERTEX), 1.0);
	POINT_SIZE = clamp(COLOR.a * 900.0 / eye_dist, 1.0, 16.0);
}

void fragment() {
	ALBEDO = COLOR.rgb;
}
