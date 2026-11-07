//! Save-file envelope around the opaque core payload.
//!
//! Layout (all integers little-endian):
//!   0   magic         4s   "MWSB"
//!   4   version       u32  = 1
//!   8   saved_at_unix u64
//!   16  day           u64  (game day at write)
//!   24  payload_len   u64
//!   32  payload       core `save_bytes()` (carries its own MWSS header)
//!
//! Writes are atomic: the bytes land in `path + ".tmp"` first and are
//! then renamed over `path`.

use std::path::{Path, PathBuf};

use mwcs_sim::Campaign;

pub const MAGIC: &[u8; 4] = b"MWSB";
pub const VERSION: u32 = 1;
pub const HEADER_LEN: usize = 32;

pub fn write_envelope(path: &Path, saved_at_unix: u64, campaign: &Campaign) -> Result<(), String> {
    let payload = campaign.save_bytes();
    let mut bytes = Vec::with_capacity(HEADER_LEN + payload.len());
    bytes.extend_from_slice(MAGIC);
    bytes.extend_from_slice(&VERSION.to_le_bytes());
    bytes.extend_from_slice(&saved_at_unix.to_le_bytes());
    bytes.extend_from_slice(&campaign.day().to_le_bytes());
    bytes.extend_from_slice(&(payload.len() as u64).to_le_bytes());
    bytes.extend_from_slice(&payload);

    let tmp_path = tmp_path_for(path);
    std::fs::write(&tmp_path, &bytes)
        .map_err(|e| format!("failed to write {}: {e}", tmp_path.display()))?;
    std::fs::rename(&tmp_path, path).map_err(|e| {
        format!(
            "failed to rename {} to {}: {e}",
            tmp_path.display(),
            path.display()
        )
    })?;
    Ok(())
}

fn tmp_path_for(path: &Path) -> PathBuf {
    let mut s = path.as_os_str().to_os_string();
    s.push(".tmp");
    PathBuf::from(s)
}

/// Read a full envelope: `(saved_at_unix, day, payload_bytes)`.
pub fn read_envelope(path: &Path) -> Result<(u64, u64, Vec<u8>), String> {
    let bytes = std::fs::read(path)
        .map_err(|e| format!("failed to read save {}: {e}", path.display()))?;
    let (saved_at_unix, day, payload_len) = parse_header(&bytes)?;
    let expected = HEADER_LEN + payload_len;
    if bytes.len() < expected {
        return Err(format!(
            "save {} is truncated: header promises {payload_len} payload bytes, file has {}",
            path.display(),
            bytes.len().saturating_sub(HEADER_LEN)
        ));
    }
    Ok((
        saved_at_unix,
        day,
        bytes[HEADER_LEN..HEADER_LEN + payload_len].to_vec(),
    ))
}

/// Read only the 32-byte header: `(saved_at_unix, day)`.
pub fn read_envelope_header(path: &Path) -> Result<(u64, u64), String> {
    use std::io::Read;
    let mut file = std::fs::File::open(path)
        .map_err(|e| format!("failed to open save {}: {e}", path.display()))?;
    let mut header = [0u8; HEADER_LEN];
    file.read_exact(&mut header)
        .map_err(|e| format!("failed to read header of {}: {e}", path.display()))?;
    let (saved_at_unix, day, _payload_len) = parse_header(&header)?;
    Ok((saved_at_unix, day))
}

fn parse_header(bytes: &[u8]) -> Result<(u64, u64, usize), String> {
    if bytes.len() < HEADER_LEN {
        return Err(format!(
            "envelope truncated: {len} bytes, header needs {HEADER_LEN}",
            len = bytes.len()
        ));
    }
    if &bytes[0..4] != MAGIC {
        return Err("bad magic: not an MWSB envelope".to_string());
    }
    let version = u32::from_le_bytes(bytes[4..8].try_into().map_err(|_| "bad version field")?);
    if version != VERSION {
        return Err(format!("unsupported envelope version {version}"));
    }
    let saved_at_unix =
        u64::from_le_bytes(bytes[8..16].try_into().map_err(|_| "bad saved_at field")?);
    let day = u64::from_le_bytes(bytes[16..24].try_into().map_err(|_| "bad day field")?);
    let payload_len =
        u64::from_le_bytes(bytes[24..32].try_into().map_err(|_| "bad payload_len field")?)
            as usize;
    Ok((saved_at_unix, day, payload_len))
}

#[cfg(test)]
mod tests {
    use super::*;
    use mwcs_pipeline::table::StarRecord;
    use mwcs_sim::Galaxy;

    fn galaxy() -> Galaxy {
        Galaxy::from_star_records(vec![StarRecord {
            id: 0,
            pos_ly: [0.0, 0.0, 0.0],
            absmag: 4.85,
            bv: 0.65,
            teff: 5778.0,
            mass: 1.0,
            spectral: 4,
            flags: 0,
            planets: vec![],
            name: "Sol".into(),
        }])
    }

    fn temp_path(name: &str) -> PathBuf {
        std::env::temp_dir().join(format!(
            "mwcs-envelope-test-{}-{name}",
            std::process::id()
        ))
    }

    #[test]
    fn envelope_round_trip() {
        let galaxy = galaxy();
        let campaign = Campaign::new_default(&galaxy, 7).unwrap();
        let path = temp_path("roundtrip.mwsb");
        write_envelope(&path, 1_700_000_000, &campaign).unwrap();
        let (saved_at, day, payload) = read_envelope(&path).unwrap();
        assert_eq!(saved_at, 1_700_000_000);
        assert_eq!(day, 0);
        assert_eq!(payload, campaign.save_bytes());
        let loaded = Campaign::load_bytes(&galaxy, &payload).unwrap();
        assert_eq!(loaded.state_hash(), campaign.state_hash());
        let (h_saved, h_day) = read_envelope_header(&path).unwrap();
        assert_eq!((h_saved, h_day), (saved_at, day));
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn bad_magic_and_truncation_error() {
        let path = temp_path("bad.mwsb");
        let mut bytes = vec![0u8; HEADER_LEN];
        bytes[0..4].copy_from_slice(b"XXXX");
        std::fs::write(&path, &bytes).unwrap();
        let err = read_envelope(&path).unwrap_err();
        assert!(err.contains("bad magic"), "got: {err}");
        // Truncated file.
        std::fs::write(&path, b"MWS").unwrap();
        let err = read_envelope(&path).unwrap_err();
        assert!(err.contains("truncated"), "got: {err}");
        // Bad version.
        let mut bytes = vec![0u8; HEADER_LEN];
        bytes[0..4].copy_from_slice(MAGIC);
        bytes[4..8].copy_from_slice(&99u32.to_le_bytes());
        std::fs::write(&path, &bytes).unwrap();
        let err = read_envelope(&path).unwrap_err();
        assert!(err.contains("version"), "got: {err}");
        // Missing file.
        let missing = temp_path("does-not-exist.mwsb");
        let _ = std::fs::remove_file(&missing);
        assert!(read_envelope(&missing).is_err());
        let _ = std::fs::remove_file(&path);
    }
}
