//! Coordinate and unit conversions.
//!
//! Frame decision (design §1.6): positions are stored **heliocentric**
//! (Sol at the origin) in the **galactic** frame — HYG's equatorial
//! Cartesian coordinates are rotated with the standard J2000
//! equatorial→galactic rotation matrix, then converted pc → ly.

/// Parsecs → light-years (exact IAU-consistent factor used by the design).
pub const PC_TO_LY: f64 = 3.26156;

/// J2000 equatorial → galactic rotation matrix (Hipparcos / Perryman et
/// al. 1997), row-major. Maps equatorial (x toward vernal equinox, z
/// toward north celestial pole) to galactic (X toward the galactic
/// centre, Y toward galactic rotation, Z toward the north galactic pole).
pub const EQ_TO_GAL: [[f64; 3]; 3] = [
    [-0.0548755604162154, -0.8734370902348850, -0.4838350155487132],
    [0.4941094278755837, -0.4448296299600112, 0.7469822444972189],
    [-0.8676661490190047, -0.1980763734312015, 0.4559837761750669],
];

pub fn rotate_eq_to_gal(v: [f64; 3]) -> [f64; 3] {
    let m = EQ_TO_GAL;
    [
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    ]
}

/// Equatorial Cartesian (pc) → galactic Cartesian (ly).
pub fn eq_pc_to_gal_ly(v: [f64; 3]) -> [f64; 3] {
    let g = rotate_eq_to_gal(v);
    [g[0] * PC_TO_LY, g[1] * PC_TO_LY, g[2] * PC_TO_LY]
}

/// RA/Dec (degrees) + distance (pc) → equatorial Cartesian (pc).
/// Used for Exoplanet Archive hosts, which publish no Cartesian coords.
pub fn radec_dist_to_eq_pc(ra_deg: f64, dec_deg: f64, dist_pc: f64) -> [f64; 3] {
    let ra = ra_deg.to_radians();
    let dec = dec_deg.to_radians();
    [
        dist_pc * dec.cos() * ra.cos(),
        dist_pc * dec.cos() * ra.sin(),
        dist_pc * dec.sin(),
    ]
}

pub fn norm(v: [f64; 3]) -> f64 {
    (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]).sqrt()
}

pub fn dist(a: [f64; 3], b: [f64; 3]) -> f64 {
    norm([a[0] - b[0], a[1] - b[1], a[2] - b[2]])
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pc_to_ly() {
        // Proxima Centauri in HYG v4.4: dist 1.2959 pc.
        let ly = 1.2959 * PC_TO_LY;
        assert!((ly - 4.2264).abs() < 0.001, "got {ly}");
    }

    #[test]
    fn rotation_preserves_distance() {
        // Proxima equatorial xyz (pc) from HYG v4.4.
        let eq = [-0.472264, -0.361451, -1.151219];
        let gal = rotate_eq_to_gal(eq);
        assert!((norm(eq) - norm(gal)).abs() < 1e-9);
        assert!((norm(gal) - 1.2959).abs() < 0.001);
    }

    #[test]
    fn galactic_centre_direction_maps_to_plus_x() {
        // A point toward the galactic centre (RA ≈ 266.405°, Dec ≈ −28.936°)
        // must come out mostly +X in the galactic frame.
        let eq = radec_dist_to_eq_pc(266.405, -28.936, 100.0);
        let gal = rotate_eq_to_gal(eq);
        assert!(gal[0] > 99.0, "galactic X should dominate, got {gal:?}");
        assert!(gal[1].abs() < 5.0 && gal[2].abs() < 5.0, "got {gal:?}");
    }

    #[test]
    fn radec_roundtrip_distance() {
        let eq = radec_dist_to_eq_pc(133.1468373, 28.3298154, 12.5855);
        assert!((norm(eq) - 12.5855).abs() < 1e-9);
    }
}
