// SPDX-License-Identifier: MPL-2.0
//! Offline structural inspection. This does not authenticate journal contents.
use serde_json::{Value, json};
use std::fs::OpenOptions;
use std::io::{self, Read};
use std::os::unix::fs::{MetadataExt, OpenOptionsExt};
use std::os::unix::io::AsRawFd;
use std::path::Path;

const MAX_BYTES: u64 = 4 * 1024 * 1024;
const MAX_LINE: usize = 64 * 1024;
const NOFOLLOW_NONBLOCK: i32 = 0o400000 | 0o4000;
const LOCK_SHARED_NONBLOCK: i32 = 1 | 4;

unsafe extern "C" {
    fn flock(fd: i32, operation: i32) -> i32;
}

fn invalid() -> io::Error {
    io::Error::new(
        io::ErrorKind::InvalidData,
        "invalid audit journal structure",
    )
}

/// Inspect a stable, bounded snapshot without printing event contents or
/// requiring veil-core, the seat broker, a model, or network access.
pub fn inspect(path: &Path) -> io::Result<Value> {
    with_snapshot(path, |_, report| Ok(report))
}

pub(crate) fn with_snapshot<T>(
    path: &Path,
    operation: impl FnOnce(&[u8], Value) -> io::Result<T>,
) -> io::Result<T> {
    with_snapshot_file(path, |_, bytes, report| operation(bytes, report))
}

pub(crate) fn with_snapshot_file<T>(
    path: &Path,
    operation: impl FnOnce(&std::fs::File, &[u8], Value) -> io::Result<T>,
) -> io::Result<T> {
    let _lock = super::audit::directory_lock(path, false)?;
    let file = OpenOptions::new()
        .read(true)
        .custom_flags(NOFOLLOW_NONBLOCK)
        .open(path)?;
    let meta = file.metadata()?;
    if !meta.is_file() || meta.nlink() != 1 || meta.mode() & 0o777 != 0o600 {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "audit journal must be a private singly linked regular file",
        ));
    }
    if unsafe { flock(file.as_raw_fd(), LOCK_SHARED_NONBLOCK) } != 0 {
        return Err(io::Error::last_os_error());
    }
    if file.metadata()?.len() > MAX_BYTES {
        return Err(invalid());
    }
    // Keep the descriptor (and its lock) alive until inspection completes.
    let mut bytes = Vec::new();
    (&file).take(MAX_BYTES + 1).read_to_end(&mut bytes)?;
    let report = inspect_bytes(&bytes)?;
    // Keep both shared locks until the consumer finishes copying/hashing.
    operation(&file, &bytes, report)
}

pub(crate) fn inspect_bytes(bytes: &[u8]) -> io::Result<Value> {
    if bytes.len() as u64 > MAX_BYTES || (!bytes.is_empty() && !bytes.ends_with(b"\n")) {
        return Err(invalid());
    }
    let mut records = 0u64;
    // Phase 2 chain verification (docs/DURABLE_AUDIT_V2_DESIGN.md):
    // every v2 record's record_digest must recompute and its
    // prev_digest must equal the previous record's link hash (a v1
    // record's link hash is SHA-512 of its raw line). The first
    // chained record's prev_digest is reported as the chain anchor:
    // a single file cannot authenticate its own anchor (that is
    // what export anchoring is for), so "authenticated" stays
    // false — but any edit, deletion or reordering inside the file
    // breaks the chain and is refused here.
    let mut link: Option<[u8; 64]> = None;
    let mut chained = 0u64;
    let mut anchor: Option<String> = None;
    for line in bytes.split_inclusive(|byte| *byte == b'\n') {
        if line.len() > MAX_LINE || line.contains(&b'\r') {
            return Err(invalid());
        }
        let value = super::audit_json::decode(line).map_err(|_| invalid())?;
        check_record(&value)?;
        let raw = &line[..line.len() - 1];
        if value["schema"] == super::audit::AUDIT_SCHEMA_V2 {
            let prev = super::audit::digest_from_hex(
                value["prev_digest"].as_str().ok_or_else(invalid)?,
            )
            .ok_or_else(invalid)?;
            if let Some(expected) = link {
                if prev != expected {
                    return Err(invalid());
                }
            } else {
                anchor = Some(value["prev_digest"].as_str().unwrap().to_owned());
            }
            let mut unsigned = value.clone();
            unsigned.as_object_mut().unwrap().remove("record_digest");
            let mut input = prev.to_vec();
            input.extend_from_slice(unsigned.to_string().as_bytes());
            let digest = crate::sha512::sha512(&input);
            if crate::sha256::hex(&digest) != value["record_digest"].as_str().unwrap() {
                return Err(invalid());
            }
            link = Some(digest);
            chained += 1;
        } else {
            link = Some(crate::sha512::sha512(raw));
        }
        records += 1;
    }
    let mut report = json!({
        "schema": "synveil.audit-inspection/v1",
        "record_schema": super::audit::AUDIT_SCHEMA_V1,
        "records": records,
        "bytes": bytes.len(),
        "authenticated": false,
    });
    if chained > 0 {
        report["chain"] = json!({
            "chained_records": chained,
            "anchor": anchor,
            "tail": crate::sha256::hex(&link.unwrap()),
        });
    }
    Ok(report)
}

fn bounded_text(value: &Value) -> bool {
    value
        .as_str()
        .is_some_and(|text| !text.is_empty() && text.len() <= 128)
}

fn digest_text(value: &Value) -> bool {
    value.as_str().is_some_and(|text| {
        text.len() == 128
            && text.bytes().all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    })
}

fn check_record(value: &Value) -> io::Result<()> {
    let keys = [
        "schema",
        "component",
        "pid",
        "sequence",
        "unix_time_ms",
        "version",
        "git_revision",
        "event",
        "fields",
    ];
    // A record is either the v1 shape (exactly the envelope keys)
    // or the v2 shape (the envelope plus the two chain digests,
    // with the v2 schema string).
    let v1_shape = value.as_object().is_some_and(|object| {
        object.len() == keys.len() && keys.iter().all(|key| object.contains_key(*key))
    }) && value["schema"] == super::audit::AUDIT_SCHEMA_V1;
    let v2_shape = value.as_object().is_some_and(|object| {
        object.len() == keys.len() + 2
            && keys.iter().all(|key| object.contains_key(*key))
            && object.contains_key("prev_digest")
            && object.contains_key("record_digest")
    }) && value["schema"] == super::audit::AUDIT_SCHEMA_V2
        && digest_text(&value["prev_digest"])
        && digest_text(&value["record_digest"]);
    let shape = v1_shape || v2_shape;
    let valid = shape
        && value["component"] == "veil-core"
        && value["pid"]
            .as_u64()
            .is_some_and(|pid| pid > 0 && pid <= u32::MAX as u64)
        && value["sequence"]
            .as_u64()
            .is_some_and(|sequence| sequence > 0)
        && (value["unix_time_ms"].is_null() || value["unix_time_ms"].as_u64().is_some())
        && bounded_text(&value["version"])
        && (value["git_revision"].is_null() || bounded_text(&value["git_revision"]))
        && bounded_text(&value["event"])
        && value["fields"].is_object();
    if valid { Ok(()) } else { Err(invalid()) }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn record() -> Value {
        super::super::audit::record("request", json!({"id": "private-value"}))
    }

    #[test]
    fn inspection_counts_records_without_disclosing_event_fields() {
        let line = format!("{}\n", record());
        let report = inspect_bytes(line.repeat(2).as_bytes()).unwrap();
        assert_eq!(report["records"], 2);
        assert_eq!(report["authenticated"], false);
        assert!(!report.to_string().contains("private-value"));
        assert_eq!(inspect_bytes(b"").unwrap()["records"], 0);
    }

    #[test]
    fn malformed_truncated_and_oversized_input_is_refused() {
        for bytes in [b"\n".as_slice(), b"{}\n", b"{", b"\xff\n", b"{}\r\n"] {
            assert!(inspect_bytes(bytes).is_err());
        }
        assert!(inspect_bytes(&vec![b' '; MAX_LINE + 1]).is_err());
        assert!(inspect_bytes(&vec![b'\n'; MAX_BYTES as usize + 1]).is_err());
        let mut line = record().to_string().into_bytes();
        assert!(inspect_bytes(&line).is_err());
        line.push(b'\n');
        assert!(inspect_bytes(&line).is_ok());
    }

    #[test]
    fn all_required_fields_and_supported_schema_are_enforced() {
        let original = record();
        for key in original.as_object().unwrap().keys() {
            let mut value = original.clone();
            value.as_object_mut().unwrap().remove(key);
            assert!(check_record(&value).is_err(), "accepted missing {key}");
        }
        for (key, wrong) in [
            ("schema", json!("synveil.audit/v99")),
            ("component", json!("planner")),
            ("pid", json!(0)),
            ("sequence", json!(-1)),
            ("unix_time_ms", json!("yesterday")),
            ("version", json!("")),
            ("git_revision", json!(false)),
            ("event", json!("x".repeat(129))),
            ("fields", json!([])),
        ] {
            let mut value = original.clone();
            value[key] = wrong;
            assert!(check_record(&value).is_err(), "accepted invalid {key}");
        }
    }

    fn chained_bytes(count: usize) -> Vec<u8> {
        let mut prev = super::super::audit::GENESIS_DIGEST;
        let mut out = Vec::new();
        for _ in 0..count {
            let (line, digest) =
                super::super::audit::chain_record(&record(), &prev).unwrap();
            out.extend_from_slice(line.as_bytes());
            out.push(b'\n');
            prev = digest;
        }
        out
    }

    #[test]
    fn chained_journal_verifies_and_reports_its_anchor() {
        let report = inspect_bytes(&chained_bytes(3)).unwrap();
        assert_eq!(report["records"], 3);
        assert_eq!(report["chain"]["chained_records"], 3);
        assert_eq!(
            report["chain"]["anchor"],
            crate::sha256::hex(&super::super::audit::GENESIS_DIGEST)
        );
        // A v1-only journal reports no chain, exactly as before.
        let line = format!("{}\n", record());
        let report = inspect_bytes(line.as_bytes()).unwrap();
        assert!(report.get("chain").is_none());
    }

    #[test]
    fn chain_detects_edit_deletion_and_reordering() {
        let bytes = chained_bytes(3);
        let text = String::from_utf8(bytes).unwrap();
        // Edit inside the first record's fields.
        let edited = text.replacen("private-value", "private-valuf", 1);
        assert!(inspect_bytes(edited.as_bytes()).is_err());
        // Delete the middle record: the third record's prev_digest
        // no longer matches the first record's link hash.
        let mut lines: Vec<&str> = text.lines().collect();
        lines.remove(1);
        let deleted = lines.join("\n") + "\n";
        assert!(inspect_bytes(deleted.as_bytes()).is_err());
        // Reorder two records.
        let mut lines: Vec<&str> = text.lines().collect();
        lines.swap(0, 1);
        let reordered = lines.join("\n") + "\n";
        assert!(inspect_bytes(reordered.as_bytes()).is_err());
        // Forge a record_digest: shape stays valid, digest fails.
        let mut value = super::super::audit_json::decode(lines[0].as_bytes()).unwrap();
        value["record_digest"] = json!("0".repeat(128));
        let forged = format!("{value}\n");
        assert!(inspect_bytes(forged.as_bytes()).is_err());
    }

    #[test]
    fn chain_links_across_the_v1_v2_boundary() {
        let v1 = record().to_string();
        let prev = crate::sha512::sha512(v1.as_bytes());
        let (v2, _digest) = super::super::audit::chain_record(&record(), &prev).unwrap();
        let bytes = format!("{v1}\n{v2}\n");
        let report = inspect_bytes(bytes.as_bytes()).unwrap();
        assert_eq!(report["records"], 2);
        assert_eq!(report["chain"]["chained_records"], 1);
        // The same v2 record anchored anywhere else is refused.
        let (orphan, _digest) =
            super::super::audit::chain_record(&record(), &super::super::audit::GENESIS_DIGEST)
                .unwrap();
        let bytes = format!("{v1}\n{orphan}\n");
        assert!(inspect_bytes(bytes.as_bytes()).is_err());
    }

    #[test]
    fn duplicate_envelope_and_nested_field_keys_are_refused() {
        let original = record().to_string();
        for key in ["pid", "\\u0070id"] {
            let line = format!("{{\"{key}\":123,{}\n", &original[1..]);
            assert!(inspect_bytes(line.as_bytes()).is_err());
        }
        let mut value = record();
        value["fields"] = json!({"nested": [{"x": 1}]});
        let line = format!("{value}\n").replace("\"x\":1", "\"x\":1,\"\\u0078\":2");
        assert!(inspect_bytes(line.as_bytes()).is_err());
    }
}
