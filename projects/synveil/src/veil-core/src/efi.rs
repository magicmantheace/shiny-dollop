// SPDX-License-Identifier: MPL-2.0
//! Minimal UEFI variable access for the A/B updater
//! (docs/AB_UPDATER.md): BootCurrent, BootNext, BootOrder and
//! Boot#### entries over efivarfs. The guest ships no efibootmgr;
//! this module crafts EFI_LOAD_OPTION values directly and is the
//! only code in the guest that touches firmware variables.
//!
//! Variables are written with attributes NV|BS|RT (0x7). Every
//! write is a single file write followed by fsync; efivarfs makes
//! the variable visible to the firmware at the next boot.

use std::fs;
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use std::process::Command;

pub const EFIVARS_DIR: &str = "/sys/firmware/efi/efivars";
pub const GLOBAL_GUID: &str = "8be4df61-93ca-11d2-aa0d-00e098032b8c";
const VARIABLE_ATTRIBUTES: u32 = 0x0000_0007;

/// A GPT partition as the firmware needs to see it in a HardDrive
/// device path node.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct GptPartition {
    pub number: u32,
    pub start_lba: u64,
    pub size_lba: u64,
    /// The 16 partition-GUID bytes in EFI wire order.
    pub guid_bytes: [u8; 16],
}

/// Convert a canonical UUID string to the EFI wire byte order
/// (the first three fields are little-endian in EFI GUIDs).
pub fn guid_bytes(uuid: &str) -> io::Result<[u8; 16]> {
    let hex: String = uuid.chars().filter(|c| *c != '-').collect();
    if hex.len() != 32 || !hex.chars().all(|c| c.is_ascii_hexdigit()) {
        return Err(io::Error::new(io::ErrorKind::InvalidInput, "invalid UUID"));
    }
    let mut raw = [0u8; 16];
    for i in 0..16 {
        raw[i] = u8::from_str_radix(&hex[i * 2..i * 2 + 2], 16)
            .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "invalid UUID"))?;
    }
    Ok([
        raw[3], raw[2], raw[1], raw[0], raw[5], raw[4], raw[7], raw[6], raw[8], raw[9], raw[10],
        raw[11], raw[12], raw[13], raw[14], raw[15],
    ])
}

fn var_path(name: &str) -> PathBuf {
    Path::new(EFIVARS_DIR).join(format!("{name}-{GLOBAL_GUID}"))
}

/// Mount efivarfs if it is not already mounted. Idempotent.
pub fn ensure_efivars() -> io::Result<()> {
    let mounts = fs::read_to_string("/proc/mounts")?;
    if mounts.lines().any(|line| line.contains(" efivarfs ")) {
        return Ok(());
    }
    if !Path::new("/sys/firmware/efi").is_dir() {
        return Err(io::Error::new(
            io::ErrorKind::NotFound,
            "no EFI firmware runtime (not a UEFI boot)",
        ));
    }
    let status = Command::new("/bin/mount")
        .args(["-t", "efivarfs", "efivarfs", EFIVARS_DIR])
        .status()?;
    if !status.success() {
        return Err(io::Error::other("efivarfs mount failed"));
    }
    Ok(())
}

pub fn read_variable(name: &str) -> io::Result<Option<Vec<u8>>> {
    let path = var_path(name);
    let mut file = match fs::File::open(&path) {
        Ok(file) => file,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(error),
    };
    let mut raw = Vec::new();
    file.read_to_end(&mut raw)?;
    if raw.len() < 4 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "short EFI variable",
        ));
    }
    let attributes = u32::from_le_bytes([raw[0], raw[1], raw[2], raw[3]]);
    if attributes & VARIABLE_ATTRIBUTES != VARIABLE_ATTRIBUTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "unexpected EFI variable attributes",
        ));
    }
    Ok(Some(raw[4..].to_vec()))
}

pub fn write_variable(name: &str, payload: &[u8]) -> io::Result<()> {
    let path = var_path(name);
    let mut framed = Vec::with_capacity(4 + payload.len());
    framed.extend_from_slice(&VARIABLE_ATTRIBUTES.to_le_bytes());
    framed.extend_from_slice(payload);
    let mut options = fs::OpenOptions::new();
    options.write(true).create(true).truncate(true);
    let mut file = options.open(&path)?;
    file.write_all(&framed)?;
    file.sync_all()?;
    Ok(())
}

pub fn boot_current() -> io::Result<Option<u16>> {
    match read_variable("BootCurrent")? {
        Some(bytes) if bytes.len() == 2 => Ok(Some(u16::from_le_bytes([bytes[0], bytes[1]]))),
        Some(_) => Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "BootCurrent has an unexpected length",
        )),
        None => Ok(None),
    }
}

pub fn boot_next() -> io::Result<Option<u16>> {
    match read_variable("BootNext")? {
        Some(bytes) if bytes.len() == 2 => Ok(Some(u16::from_le_bytes([bytes[0], bytes[1]]))),
        Some(_) => Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "BootNext has an unexpected length",
        )),
        None => Ok(None),
    }
}

pub fn set_boot_next(entry: u16) -> io::Result<()> {
    write_variable("BootNext", &entry.to_le_bytes())
}

pub fn boot_order() -> io::Result<Vec<u16>> {
    match read_variable("BootOrder")? {
        Some(bytes) => {
            if bytes.len() % 2 != 0 {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "BootOrder has an odd length",
                ));
            }
            Ok(bytes
                .as_chunks::<2>()
                .0
                .iter()
                .map(|chunk| u16::from_le_bytes(*chunk))
                .collect())
        }
        None => Ok(Vec::new()),
    }
}

pub fn set_boot_order(entries: &[u16]) -> io::Result<()> {
    let mut payload = Vec::with_capacity(entries.len() * 2);
    for entry in entries {
        payload.extend_from_slice(&entry.to_le_bytes());
    }
    write_variable("BootOrder", &payload)
}

/// Ids of the Boot#### variables currently present.
pub fn existing_boot_entries() -> io::Result<Vec<u16>> {
    let mut ids = Vec::new();
    for entry in fs::read_dir(EFIVARS_DIR)? {
        let entry = entry?;
        let name = entry.file_name();
        let Some(name) = name.to_str() else { continue };
        let Some(rest) = name.strip_prefix("Boot") else {
            continue;
        };
        let Some((digits, _)) = rest.split_once('-') else {
            continue;
        };
        if digits.len() == 4
            && let Ok(id) = u16::from_str_radix(digits, 16)
        {
            ids.push(id);
        }
    }
    ids.sort_unstable();
    Ok(ids)
}

/// Build an EFI_LOAD_OPTION for a file on a GPT partition.
pub fn load_option(description: &str, partition: &GptPartition, file_path: &str) -> Vec<u8> {
    let mut device_path = Vec::new();
    // HardDrive device path (type 4, subtype 1).
    device_path.extend_from_slice(&[4, 1]);
    device_path.extend_from_slice(&42u16.to_le_bytes());
    device_path.extend_from_slice(&partition.number.to_le_bytes());
    device_path.extend_from_slice(&partition.start_lba.to_le_bytes());
    device_path.extend_from_slice(&partition.size_lba.to_le_bytes());
    device_path.extend_from_slice(&partition.guid_bytes);
    device_path.push(2); // MBR type: GPT
    device_path.push(2); // signature type: GUID
    // File device path (type 4, subtype 4): UTF-16LE, NUL-terminated.
    let utf16: Vec<u16> = file_path.encode_utf16().collect();
    device_path.extend_from_slice(&[4, 4]);
    device_path.extend_from_slice(&((4 + (utf16.len() + 1) * 2) as u16).to_le_bytes());
    for unit in utf16 {
        device_path.extend_from_slice(&unit.to_le_bytes());
    }
    device_path.extend_from_slice(&0u16.to_le_bytes());
    // End of device path (type 0x7f, subtype 0xff).
    device_path.extend_from_slice(&[0x7f, 0xff, 4, 0]);

    let mut out = Vec::new();
    out.extend_from_slice(&1u32.to_le_bytes()); // LOAD_OPTION_ACTIVE
    out.extend_from_slice(&(device_path.len() as u16).to_le_bytes());
    for unit in description.encode_utf16() {
        out.extend_from_slice(&unit.to_le_bytes());
    }
    out.extend_from_slice(&0u16.to_le_bytes());
    out.extend_from_slice(&device_path);
    out
}

pub fn write_boot_entry(id: u16, option: &[u8]) -> io::Result<()> {
    write_variable(&format!("Boot{id:04X}"), option)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn guid_wire_order() {
        let bytes = guid_bytes("7c9e2d41-8b3a-4f5e-a6d1-2e8c4b7f9053").unwrap();
        assert_eq!(bytes[..4], [0x41, 0x2d, 0x9e, 0x7c]);
        assert_eq!(bytes[4..6], [0x3a, 0x8b]);
        assert_eq!(bytes[6..8], [0x5e, 0x4f]);
        assert_eq!(bytes[8..], [0xa6, 0xd1, 0x2e, 0x8c, 0x4b, 0x7f, 0x90, 0x53]);
        assert!(guid_bytes("not-a-uuid").is_err());
    }

    #[test]
    fn load_option_layout() {
        let partition = GptPartition {
            number: 2,
            start_lba: 4096,
            size_lba: 1000,
            guid_bytes: guid_bytes("ab000000-0000-4000-8000-00000000000a").unwrap(),
        };
        let option = load_option("Synveil A", &partition, "\\EFI\\synveil\\gen.efi");
        // Attributes + path-list length.
        assert_eq!(u32::from_le_bytes(option[0..4].try_into().unwrap()), 1);
        let list_len = u16::from_le_bytes(option[4..6].try_into().unwrap()) as usize;
        // Description "Synveil A" is 9 UTF-16 units + NUL.
        let desc_bytes = 20;
        assert_eq!(option.len(), 6 + desc_bytes + list_len);
        let dp = &option[6 + desc_bytes..];
        assert_eq!(dp[0], 4);
        assert_eq!(dp[1], 1);
        assert_eq!(u16::from_le_bytes(dp[2..4].try_into().unwrap()), 42);
        assert_eq!(u32::from_le_bytes(dp[4..8].try_into().unwrap()), 2);
        assert_eq!(u64::from_le_bytes(dp[8..16].try_into().unwrap()), 4096);
        // File node follows, then the end node closes the list.
        let file_node = 42;
        assert_eq!(dp[file_node], 4);
        assert_eq!(dp[file_node + 1], 4);
        assert_eq!(&dp[list_len - 4..list_len], &[0x7f, 0xff, 4, 0]);
    }
}
