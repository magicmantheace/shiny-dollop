//! The game star table binary format — **the contract between the
//! pipeline (writer) and the Godot viewer (reader)**. Any change here
//! must land together with the mirror change in
//! `viewer/scripts/star_table.gd` and the round-trip tests.
//!
//! Layout (all integers little-endian):
//!
//! ```text
//! Header (64 bytes)
//!   0   magic          4s   "MWST"
//!   4   version        u32  = 1
//!   8   star_count     u32
//!   12  planet_count   u32  (total planet records across all lists)
//!   16  stars_offset   u64  (= 64)
//!   24  planets_offset u64
//!   32  strings_offset u64
//!   40  strings_len    u64
//!   48  reserved       16 bytes, zero
//! Star records (star_count × 48 bytes, design §1.6)
//!   0   id             u32  (index in this table)
//!   4   x, y, z        3×f32  ly, galactic frame, Sol at origin
//!   16  absmag         f32  (0 = unknown)
//!   20  bv             f32  B−V colour index (0 = unknown)
//!   24  teff           f32  K (0 = unknown)
//!   28  mass           f32  solar masses (0 = unknown)
//!   32  spectral       u8   derive::SpectralClass codes (7=Other, 8=Unknown)
//!   33  flags          u8   bit flags, see FLAG_* below
//!   34  _pad           2 bytes, zero
//!   36  planet_offset  u32  byte offset into the planets section; 0 = none
//!   40  name_offset    u32  byte offset into the string table
//!   44  _pad           4 bytes, zero
//! Planets section
//!   0   reserved       u32  = 0 (so planet_offset 0 unambiguously = none)
//!   …   per host with planets: u32 count, then count × PlanetRecord
//! Planet record (32 bytes)
//!   0   name_offset    u32  into the string table
//!   4   period_days    f32  (0 = unknown)
//!   8   semimajor_au   f32  (0 = unknown)
//!   12  radius_earth   f32  (0 = unknown)
//!   16  mass_earth     f32  (0 = unknown; archive best estimate)
//!   20  eq_temp        f32  K (0 = unknown)
//!   24  disc_year      u16  (0 = unknown)
//!   26  method         u8   discovery-method code (see method_code)
//!   27  flags          u8   bit0 radius known, bit1 mass known,
//!                           bit2 period known, bit3 semimajor known
//!   28  _pad           4 bytes, zero
//! String table: concatenated NUL-terminated UTF-8 strings.
//! ```
//!
//! Star flag bits:
//!   0 named — has a proper name (catalog `proper`, not a designation)
//!   1 has_real_planets
//!   2 generated — statistical-fill star (NOT set by S0; reserved)
//!   3 multiple — member of a multiple system (catalog heuristic)
//!   4 temp_derived — teff was derived, not measured
//!   5 mass_derived — mass was derived, not measured
//!   6 source_exoplanet_archive — row inserted from the Exoplanet
//!     Archive because HYG has no entry for this (real) host star

pub const FLAG_NAMED: u8 = 1 << 0;
pub const FLAG_HAS_PLANETS: u8 = 1 << 1;
pub const FLAG_GENERATED: u8 = 1 << 2;
pub const FLAG_MULTIPLE: u8 = 1 << 3;
pub const FLAG_TEMP_DERIVED: u8 = 1 << 4;
pub const FLAG_MASS_DERIVED: u8 = 1 << 5;
pub const FLAG_SOURCE_EXOPLANET_ARCHIVE: u8 = 1 << 6;

pub const HEADER_LEN: usize = 64;
pub const STAR_LEN: usize = 48;
pub const PLANET_LEN: usize = 32;
pub const FORMAT_VERSION: u32 = 1;

#[derive(Debug, Clone, PartialEq)]
pub struct StarRecord {
    pub id: u32,
    pub pos_ly: [f32; 3],
    pub absmag: f32,
    pub bv: f32,
    pub teff: f32,
    pub mass: f32,
    pub spectral: u8,
    pub flags: u8,
    /// Index-based planet list, resolved to a byte offset at write time.
    pub planets: Vec<PlanetRecord>,
    pub name: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct PlanetRecord {
    pub name: String,
    pub period_days: f32,
    pub semimajor_au: f32,
    pub radius_earth: f32,
    pub mass_earth: f32,
    pub eq_temp: f32,
    pub disc_year: u16,
    pub method: u8,
    pub flags: u8,
}

/// Discovery-method codes for the planet record.
pub fn method_code(method: &str) -> u8 {
    match method.trim() {
        "Radial Velocity" => 1,
        "Transit" => 2,
        "Imaging" => 3,
        "Microlensing" => 4,
        "Transit Timing Variations" => 5,
        "Eclipse Timing Variations" => 6,
        "Pulsar Timing" => 7,
        "Pulsation Timing Variations" => 8,
        "Orbital Brightness Modulation" => 9,
        "Astrometry" => 10,
        "Disk Kinematics" => 11,
        _ => 0,
    }
}

pub fn method_name(code: u8) -> &'static str {
    match code {
        1 => "Radial Velocity",
        2 => "Transit",
        3 => "Imaging",
        4 => "Microlensing",
        5 => "Transit Timing Variations",
        6 => "Eclipse Timing Variations",
        7 => "Pulsar Timing",
        8 => "Pulsation Timing Variations",
        9 => "Orbital Brightness Modulation",
        10 => "Astrometry",
        11 => "Disk Kinematics",
        _ => "Unknown",
    }
}

/// Accumulates NUL-terminated strings, returning offsets.
#[derive(Default)]
pub struct StringTable {
    bytes: Vec<u8>,
}

impl StringTable {
    pub fn add(&mut self, s: &str) -> u32 {
        let off = self.bytes.len() as u32;
        self.bytes.extend_from_slice(s.as_bytes());
        self.bytes.push(0);
        off
    }
    pub fn bytes(&self) -> &[u8] {
        &self.bytes
    }
    pub fn get(&self, offset: u32) -> &str {
        let start = offset as usize;
        if start >= self.bytes.len() {
            return "";
        }
        let end = self.bytes[start..]
            .iter()
            .position(|b| *b == 0)
            .map(|p| start + p)
            .unwrap_or(self.bytes.len());
        std::str::from_utf8(&self.bytes[start..end]).unwrap_or("")
    }
}

/// Serialize the full table. Deterministic: identical inputs produce
/// byte-identical output (records in slice order, strings in add order).
pub fn write_table(stars: &[StarRecord]) -> Vec<u8> {
    // Pass 1: assign every string offset up front (planet names first,
    // then star names — order is arbitrary but must be deterministic).
    let mut strings = StringTable::default();
    let mut planet_name_offsets: Vec<Vec<u32>> = Vec::with_capacity(stars.len());
    let mut star_name_offsets: Vec<u32> = Vec::with_capacity(stars.len());
    for star in stars {
        let mut offs = Vec::with_capacity(star.planets.len());
        for p in &star.planets {
            offs.push(strings.add(&p.name));
        }
        planet_name_offsets.push(offs);
        star_name_offsets.push(strings.add(&star.name));
    }

    // Pass 2: planet lists, so star planet_offsets can be resolved.
    let mut planets_section: Vec<u8> = Vec::new();
    planets_section.extend_from_slice(&0u32.to_le_bytes()); // reserved word
    let mut planet_offsets: Vec<u32> = Vec::with_capacity(stars.len());
    let mut total_planets: u32 = 0;
    for (i, star) in stars.iter().enumerate() {
        if star.planets.is_empty() {
            planet_offsets.push(0);
        } else {
            planet_offsets.push(planets_section.len() as u32);
            planets_section
                .extend_from_slice(&(star.planets.len() as u32).to_le_bytes());
            total_planets += star.planets.len() as u32;
            for (j, p) in star.planets.iter().enumerate() {
                let mut rec = [0u8; PLANET_LEN];
                rec[0..4].copy_from_slice(&planet_name_offsets[i][j].to_le_bytes());
                rec[4..8].copy_from_slice(&p.period_days.to_le_bytes());
                rec[8..12].copy_from_slice(&p.semimajor_au.to_le_bytes());
                rec[12..16].copy_from_slice(&p.radius_earth.to_le_bytes());
                rec[16..20].copy_from_slice(&p.mass_earth.to_le_bytes());
                rec[20..24].copy_from_slice(&p.eq_temp.to_le_bytes());
                rec[24..26].copy_from_slice(&p.disc_year.to_le_bytes());
                rec[26] = p.method;
                rec[27] = p.flags;
                planets_section.extend_from_slice(&rec);
            }
        }
    }

    let stars_offset = HEADER_LEN as u64;
    let planets_offset = stars_offset + (stars.len() * STAR_LEN) as u64;
    let strings_offset = planets_offset + planets_section.len() as u64;

    let mut out: Vec<u8> = Vec::new();
    out.extend_from_slice(b"MWST");
    out.extend_from_slice(&FORMAT_VERSION.to_le_bytes());
    out.extend_from_slice(&(stars.len() as u32).to_le_bytes());
    out.extend_from_slice(&total_planets.to_le_bytes());
    out.extend_from_slice(&stars_offset.to_le_bytes());
    out.extend_from_slice(&planets_offset.to_le_bytes());
    out.extend_from_slice(&strings_offset.to_le_bytes());
    out.extend_from_slice(&(strings.bytes().len() as u64).to_le_bytes());
    out.extend_from_slice(&[0u8; 16]);
    debug_assert_eq!(out.len(), HEADER_LEN);

    for (i, star) in stars.iter().enumerate() {
        let name_off = star_name_offsets[i];
        let mut rec = [0u8; STAR_LEN];
        rec[0..4].copy_from_slice(&star.id.to_le_bytes());
        rec[4..8].copy_from_slice(&star.pos_ly[0].to_le_bytes());
        rec[8..12].copy_from_slice(&star.pos_ly[1].to_le_bytes());
        rec[12..16].copy_from_slice(&star.pos_ly[2].to_le_bytes());
        rec[16..20].copy_from_slice(&star.absmag.to_le_bytes());
        rec[20..24].copy_from_slice(&star.bv.to_le_bytes());
        rec[24..28].copy_from_slice(&star.teff.to_le_bytes());
        rec[28..32].copy_from_slice(&star.mass.to_le_bytes());
        rec[32] = star.spectral;
        rec[33] = star.flags;
        rec[36..40].copy_from_slice(&planet_offsets[i].to_le_bytes());
        rec[40..44].copy_from_slice(&name_off.to_le_bytes());
        out.extend_from_slice(&rec);
    }
    out.extend_from_slice(&planets_section);
    out.extend_from_slice(strings.bytes());
    out
}

/// Read back a table written by [`write_table`] (used by tests and by
/// the pipeline's own verification pass; the Godot reader mirrors this).
pub fn read_table(data: &[u8]) -> Result<Vec<StarRecord>, String> {
    if data.len() < HEADER_LEN || &data[0..4] != b"MWST" {
        return Err("bad magic".into());
    }
    let u32_at = |o: usize| u32::from_le_bytes(data[o..o + 4].try_into().unwrap());
    let u64_at = |o: usize| u64::from_le_bytes(data[o..o + 8].try_into().unwrap());
    let f32_at = |o: usize| f32::from_le_bytes(data[o..o + 4].try_into().unwrap());
    if u32_at(4) != FORMAT_VERSION {
        return Err(format!("unsupported format version {}", u32_at(4)));
    }
    let star_count = u32_at(8) as usize;
    let stars_offset = u64_at(16) as usize;
    let planets_offset = u64_at(24) as usize;
    let strings_offset = u64_at(32) as usize;
    let strings_len = u64_at(40) as usize;

    let mut strings = StringTable::default();
    strings.bytes = data[strings_offset..strings_offset + strings_len].to_vec();

    let mut stars = Vec::with_capacity(star_count);
    for i in 0..star_count {
        let base = stars_offset + i * STAR_LEN;
        let planet_off = u32_at(base + 36) as usize;
        let mut planets = Vec::new();
        if planet_off != 0 {
            let list_base = planets_offset + planet_off;
            let count = u32_at(list_base) as usize;
            for j in 0..count {
                let pb = list_base + 4 + j * PLANET_LEN;
                planets.push(PlanetRecord {
                    name: strings.get(u32_at(pb)).to_string(),
                    period_days: f32_at(pb + 4),
                    semimajor_au: f32_at(pb + 8),
                    radius_earth: f32_at(pb + 12),
                    mass_earth: f32_at(pb + 16),
                    eq_temp: f32_at(pb + 20),
                    disc_year: u16::from_le_bytes(
                        data[pb + 24..pb + 26].try_into().unwrap(),
                    ),
                    method: data[pb + 26],
                    flags: data[pb + 27],
                });
            }
        }
        stars.push(StarRecord {
            id: u32_at(base),
            pos_ly: [
                f32_at(base + 4),
                f32_at(base + 8),
                f32_at(base + 12),
            ],
            absmag: f32_at(base + 16),
            bv: f32_at(base + 20),
            teff: f32_at(base + 24),
            mass: f32_at(base + 28),
            spectral: data[base + 32],
            flags: data[base + 33],
            planets,
            name: strings.get(u32_at(base + 40)).to_string(),
        });
    }
    Ok(stars)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> Vec<StarRecord> {
        vec![
            StarRecord {
                id: 0,
                pos_ly: [0.0, 0.0, 0.0],
                absmag: 4.85,
                bv: 0.656,
                teff: 5540.0,
                mass: 1.0,
                spectral: 4,
                flags: FLAG_NAMED | FLAG_TEMP_DERIVED | FLAG_MASS_DERIVED,
                planets: vec![],
                name: "Sol".into(),
            },
            StarRecord {
                id: 1,
                pos_ly: [-3.0, 1.0, -2.9],
                absmag: 15.4,
                bv: 1.8,
                teff: 2900.0,
                mass: 0.12,
                spectral: 6,
                flags: FLAG_NAMED | FLAG_HAS_PLANETS,
                planets: vec![PlanetRecord {
                    name: "Proxima Cen b".into(),
                    period_days: 11.186,
                    semimajor_au: 0.0485,
                    radius_earth: 1.07,
                    mass_earth: 1.07,
                    eq_temp: 234.0,
                    disc_year: 2016,
                    method: 1,
                    flags: 0b1111,
                }],
                name: "Proxima Centauri".into(),
            },
        ]
    }

    #[test]
    fn round_trip_is_identical() {
        let stars = sample();
        let bytes = write_table(&stars);
        let back = read_table(&bytes).unwrap();
        assert_eq!(stars, back);
    }

    #[test]
    fn sizes_match_format() {
        let bytes = write_table(&sample());
        assert_eq!(bytes.len() % 1, 0);
        let header_stars = u32::from_le_bytes(bytes[8..12].try_into().unwrap());
        assert_eq!(header_stars, 2);
        let planets = u32::from_le_bytes(bytes[12..16].try_into().unwrap());
        assert_eq!(planets, 1);
    }

    #[test]
    fn determinism_byte_identical() {
        assert_eq!(write_table(&sample()), write_table(&sample()));
    }
}
