//! HYG v4.4 ingest: parse rows, apply the usable-position filter, and
//! convert catalog rows into game star records (physics derived and
//! flagged per design §1.6).

use crate::astro;
use crate::csv::{col, get, parse_csv, parse_f32, parse_f64, parse_i64};
use crate::derive;
use crate::table::{StarRecord, FLAG_MASS_DERIVED, FLAG_MULTIPLE, FLAG_NAMED, FLAG_TEMP_DERIVED};

/// HYG encodes indeterminate distances as >= 100,000 pc (design §1.1:
/// 10,224 such rows in v4.4). They carry no usable position.
pub const PLACEHOLDER_DIST_PC: f64 = 100_000.0;

#[derive(Debug, Clone)]
pub struct HygRow {
    pub id: i64,
    pub hip: Option<i64>,
    pub hd: Option<i64>,
    pub hr: Option<i64>,
    pub gl: String,
    pub bf: String,
    pub proper: String,
    pub dist_pc: f64,
    pub absmag: Option<f32>,
    pub spect: String,
    pub ci: Option<f32>,
    pub xyz_pc: [f64; 3],
    pub comp_primary: String,
    pub comp: String,
    pub lum: Option<f32>,
}

pub fn parse_hyg(text: &str) -> Vec<HygRow> {
    let rows = parse_csv(text);
    assert!(!rows.is_empty(), "HYG CSV is empty");
    let header = &rows[0];
    let c_id = col(header, "id");
    let c_hip = col(header, "hip");
    let c_hd = col(header, "hd");
    let c_hr = col(header, "hr");
    let c_gl = col(header, "gl");
    let c_bf = col(header, "bf");
    let c_proper = col(header, "proper");
    let c_dist = col(header, "dist");
    let c_absmag = col(header, "absmag");
    let c_spect = col(header, "spect");
    let c_ci = col(header, "ci");
    let c_x = col(header, "x");
    let c_y = col(header, "y");
    let c_z = col(header, "z");
    let c_comp = col(header, "comp");
    let c_comp_primary = col(header, "comp_primary");
    let c_lum = col(header, "lum");

    let mut out = Vec::with_capacity(rows.len());
    for row in &rows[1..] {
        if row.len() < header.len() {
            continue; // tolerate a truncated trailing line
        }
        let dist_pc = match parse_f64(get(row, c_dist)) {
            Some(d) => d,
            None => continue, // no distance at all — not a position
        };
        out.push(HygRow {
            id: parse_i64(get(row, c_id)).unwrap_or(-1),
            hip: parse_i64(get(row, c_hip)),
            hd: parse_i64(get(row, c_hd)),
            hr: parse_i64(get(row, c_hr)),
            gl: get(row, c_gl).trim().to_string(),
            bf: get(row, c_bf).trim().to_string(),
            proper: get(row, c_proper).trim().to_string(),
            dist_pc,
            absmag: parse_f32(get(row, c_absmag)),
            spect: get(row, c_spect).trim().to_string(),
            ci: parse_f32(get(row, c_ci)),
            xyz_pc: [
                parse_f64(get(row, c_x)).unwrap_or(0.0),
                parse_f64(get(row, c_y)).unwrap_or(0.0),
                parse_f64(get(row, c_z)).unwrap_or(0.0),
            ],
            comp_primary: get(row, c_comp_primary).trim().to_string(),
            comp: get(row, c_comp).trim().to_string(),
            lum: parse_f32(get(row, c_lum)),
        });
    }
    out
}

/// The usable-position filter (design §1.1): distance is present and not
/// a placeholder. Sol (dist 0) is kept — it is the origin.
pub fn is_usable(row: &HygRow) -> bool {
    row.dist_pc >= 0.0 && row.dist_pc < PLACEHOLDER_DIST_PC
}

/// Display-name fallback chain: proper name → Bayer/Flamsteed →
/// Gliese → HIP → HD → HR → HYG id.
pub fn display_name(row: &HygRow) -> String {
    if !row.proper.is_empty() {
        return row.proper.clone();
    }
    if !row.bf.is_empty() {
        return row.bf.clone();
    }
    if !row.gl.is_empty() {
        return row.gl.clone();
    }
    if let Some(hip) = row.hip {
        return format!("HIP {hip}");
    }
    if let Some(hd) = row.hd {
        return format!("HD {hd}");
    }
    if let Some(hr) = row.hr {
        return format!("HR {hr}");
    }
    format!("HYG {}", row.id)
}

/// Convert a usable HYG row into a game star record (planets attached
/// later by the merge step). `new_id` is the table index.
pub fn to_star_record(row: &HygRow, new_id: u32) -> StarRecord {
    let gal_ly = astro::eq_pc_to_gal_ly(row.xyz_pc);
    let (class, subclass) = derive::parse_spectral(&row.spect);
    let mut flags = 0u8;
    if !row.proper.is_empty() {
        flags |= FLAG_NAMED;
    }
    // Multiple-system heuristic: the catalog links components via
    // comp_primary; a row whose primary is another row, or that lists
    // more than one component, is part of a multiple system.
    if (!row.comp_primary.is_empty() && row.comp_primary != row.id.to_string())
        || (!row.comp.is_empty() && row.comp != "1")
    {
        flags |= FLAG_MULTIPLE;
    }
    let teff = derive::derive_temp(class, subclass).unwrap_or(0.0);
    if teff > 0.0 {
        flags |= FLAG_TEMP_DERIVED;
    }
    let lum = row
        .lum
        .filter(|l| *l > 0.0)
        .or_else(|| row.absmag.map(derive::luminosity_from_absmag));
    let mass = lum.and_then(derive::derive_mass_from_luminosity).unwrap_or(0.0);
    if mass > 0.0 {
        flags |= FLAG_MASS_DERIVED;
    }
    StarRecord {
        id: new_id,
        pos_ly: [gal_ly[0] as f32, gal_ly[1] as f32, gal_ly[2] as f32],
        absmag: row.absmag.unwrap_or(0.0),
        bv: row.ci.unwrap_or(0.0),
        teff,
        mass,
        spectral: derive::spectral_code(class),
        flags,
        planets: Vec::new(),
        name: display_name(row),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const FIXTURE_HEADER: &str = "id,hip,hd,hr,gl,bf,proper,ra,dec,dist,pmra,pmdec,rv,mag,absmag,spect,ci,x,y,z,vx,vy,vz,rarad,decrad,pmrarad,pmdecrad,bayer,flam,con,comp,comp_primary,base,lum,var,var_min,var_max";

    fn row_line(fields: &[&str]) -> String {
        fields.join(",")
    }

    #[test]
    fn filter_drops_placeholders_keeps_sol() {
        let mut text = String::from(FIXTURE_HEADER);
        text.push('\n');
        // Sol: dist 0
        text.push_str(&row_line(&[
            "0", "", "", "", "", "", "Sol", "0", "0", "0.0", "0", "0", "0", "-26.7", "4.85",
            "G2V", "0.656", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "", "", "", "1",
            "0", "", "1.0", "", "", "",
        ]));
        text.push('\n');
        // Placeholder star: dist 100000
        text.push_str(&row_line(&[
            "999", "", "", "", "", "", "", "0", "0", "100000.0", "0", "0", "0", "10", "5",
            "K0", "1.0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "", "", "", "1", "0",
            "", "", "", "", "",
        ]));
        let rows = parse_hyg(&text);
        assert_eq!(rows.len(), 2);
        let usable: Vec<_> = rows.iter().filter(|r| is_usable(r)).collect();
        assert_eq!(usable.len(), 1);
        assert_eq!(usable[0].proper, "Sol");
    }

    #[test]
    fn name_fallback_chain() {
        let base = HygRow {
            id: 42,
            hip: Some(1234),
            hd: Some(5678),
            hr: None,
            gl: String::new(),
            bf: String::new(),
            proper: String::new(),
            dist_pc: 10.0,
            absmag: None,
            spect: String::new(),
            ci: None,
            xyz_pc: [0.0; 3],
            comp_primary: String::new(),
            comp: String::new(),
            lum: None,
        };
        assert_eq!(display_name(&base), "HIP 1234");
        let mut r = base.clone();
        r.gl = "Gl 999".into();
        assert_eq!(display_name(&r), "Gl 999");
        r.bf = "Alp Cen".into();
        assert_eq!(display_name(&r), "Alp Cen");
        r.proper = "Named Star".into();
        assert_eq!(display_name(&r), "Named Star");
    }

    #[test]
    fn sol_record() {
        let row = HygRow {
            id: 0,
            hip: None,
            hd: None,
            hr: None,
            gl: String::new(),
            bf: String::new(),
            proper: "Sol".into(),
            dist_pc: 0.0,
            absmag: Some(4.85),
            spect: "G2V".into(),
            ci: Some(0.656),
            xyz_pc: [0.0; 3],
            comp_primary: "0".into(),
            comp: "1".into(),
            lum: Some(1.0),
        };
        let rec = to_star_record(&row, 0);
        assert_eq!(rec.name, "Sol");
        assert_eq!(rec.pos_ly, [0.0, 0.0, 0.0]);
        assert!((rec.mass - 1.0).abs() < 1e-6);
        assert!(rec.flags & FLAG_NAMED != 0);
        assert!(rec.flags & FLAG_TEMP_DERIVED != 0);
        assert!(rec.flags & FLAG_MASS_DERIVED != 0);
    }
}
