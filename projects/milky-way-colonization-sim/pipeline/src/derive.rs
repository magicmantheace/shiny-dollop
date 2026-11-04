//! Derived stellar physics. HYG carries no mass or temperature columns
//! (design §1.1/§1.6), so both are computed here and **flagged `derived`**
//! in the output table — they are estimates, never measured values.

/// Spectral class codes stored in the table (u8).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SpectralClass {
    O = 0,
    B = 1,
    A = 2,
    F = 3,
    G = 4,
    K = 5,
    M = 6,
    /// L, T, Y, W, S, C, R, N and anything else with a letter.
    Other = 7,
    /// No spectral type in the catalog.
    Unknown = 8,
}

pub fn spectral_code(c: SpectralClass) -> u8 {
    c as u8
}

/// Parse a spectral type string ("G2V", "M5Ve", "K0III", "sdM3", …).
/// Returns (class, subclass 0.0–9.9). The class is the first OBAFGKM /
/// other letter found after any leading luminosity-prefix letters.
pub fn parse_spectral(spect: &str) -> (SpectralClass, Option<f32>) {
    let s = spect.trim();
    let bytes = s.as_bytes();
    let mut i = 0;
    // Skip common prefixes that are not the class letter itself.
    while i < bytes.len() {
        let c = bytes[i] as char;
        if c.is_ascii_uppercase() {
            let class = match c {
                'O' => Some(SpectralClass::O),
                'B' => Some(SpectralClass::B),
                'A' => Some(SpectralClass::A),
                'F' => Some(SpectralClass::F),
                'G' => Some(SpectralClass::G),
                'K' => Some(SpectralClass::K),
                'M' => Some(SpectralClass::M),
                'L' | 'T' | 'Y' | 'W' | 'S' | 'C' | 'R' | 'N' => Some(SpectralClass::Other),
                _ => None,
            };
            if let Some(class) = class {
                // Subclass: the digit(s) right after the class letter.
                let rest = &s[i + 1..];
                let mut num = String::new();
                for ch in rest.chars() {
                    if ch.is_ascii_digit() || (ch == '.' && !num.is_empty()) {
                        num.push(ch);
                    } else {
                        break;
                    }
                }
                let subclass = num.parse::<f32>().ok().filter(|v| *v < 20.0);
                return (class, subclass);
            }
        }
        i += 1;
        if i > 3 {
            break; // class letter, if any, is near the front
        }
    }
    (SpectralClass::Unknown, None)
}

/// Main-sequence effective-temperature anchors (K) at subclass 0 of each
/// class, interpolated linearly toward the next class across the
/// subclass range. Approximate by design (design §1.6: O ≈ 30,000 K …
/// M ≈ 2,400 K at the cool end) and always flagged `derived`.
const TEMP_ANCHORS: [(SpectralClass, f32); 7] = [
    (SpectralClass::O, 30000.0),
    (SpectralClass::B, 15000.0),
    (SpectralClass::A, 9000.0),
    (SpectralClass::F, 6800.0),
    (SpectralClass::G, 5800.0),
    (SpectralClass::K, 4600.0),
    (SpectralClass::M, 2900.0),
];
const M_CLASS_FLOOR: f32 = 2400.0; // temperature at M9.9

/// Derive effective temperature (K) from spectral class + subclass.
/// None when the class is Other/Unknown (no honest anchor).
pub fn derive_temp(class: SpectralClass, subclass: Option<f32>) -> Option<f32> {
    let sub = subclass.unwrap_or(5.0).clamp(0.0, 9.9);
    let idx = TEMP_ANCHORS.iter().position(|(c, _)| *c == class)?;
    let t0 = TEMP_ANCHORS[idx].1;
    let t1 = if idx + 1 < TEMP_ANCHORS.len() {
        TEMP_ANCHORS[idx + 1].1
    } else {
        M_CLASS_FLOOR
    };
    Some(t0 + (t1 - t0) * (sub / 10.0))
}

/// Solar absolute magnitude in V used to turn HYG absmag into luminosity
/// when the catalog's own `lum` is missing (Sol: absmag 4.85, lum 1.0).
pub const SOL_ABSMAG_V: f32 = 4.85;

pub fn luminosity_from_absmag(absmag: f32) -> f32 {
    10f32.powf(0.4 * (SOL_ABSMAG_V - absmag))
}

/// Derive mass (solar units) from luminosity via the main-sequence
/// mass–luminosity relation L ∝ M^3.5 (design §1.6). Wrong for giants —
/// that is exactly why the value is flagged `derived`.
pub fn derive_mass_from_luminosity(lum: f32) -> Option<f32> {
    if lum > 0.0 && lum.is_finite() {
        Some(lum.powf(1.0 / 3.5))
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_classes() {
        assert_eq!(parse_spectral("G2V"), (SpectralClass::G, Some(2.0)));
        assert_eq!(parse_spectral("M5Ve"), (SpectralClass::M, Some(5.0)));
        assert_eq!(parse_spectral("K0III"), (SpectralClass::K, Some(0.0)));
        assert_eq!(parse_spectral(""), (SpectralClass::Unknown, None));
        assert_eq!(parse_spectral("sdM3").0, SpectralClass::M);
        assert_eq!(parse_spectral("B9.5V").1, Some(9.5));
    }

    #[test]
    fn sun_like_temp_and_mass() {
        // Sol: G2V, lum 1.0 → mass must come out ≈ 1.0, temp in G range.
        let (class, sub) = parse_spectral("G2V");
        let t = derive_temp(class, sub).unwrap();
        assert!(t > 5000.0 && t < 5800.0, "G2 temp {t}");
        let m = derive_mass_from_luminosity(1.0).unwrap();
        assert!((m - 1.0).abs() < 1e-6);
    }

    #[test]
    fn temp_ordering_and_floor() {
        let o = derive_temp(SpectralClass::O, Some(5.0)).unwrap();
        let m = derive_temp(SpectralClass::M, Some(9.0)).unwrap();
        assert!(o > 20000.0);
        assert!(m > 2400.0 && m < 2900.0, "M9 temp {m}");
        assert_eq!(derive_temp(SpectralClass::Unknown, None), None);
    }

    #[test]
    fn luminosity_roundtrip() {
        assert!((luminosity_from_absmag(4.85) - 1.0).abs() < 1e-6);
        assert!(luminosity_from_absmag(0.0) > 80.0);
    }
}
