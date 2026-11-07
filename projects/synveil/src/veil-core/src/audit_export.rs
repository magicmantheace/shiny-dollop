// SPDX-License-Identifier: MPL-2.0
//! Owner-controlled offline copies. Checksums do not authenticate event origin.
use blake2::{Blake2b512, Digest};
use serde_json::{Value, json};
use std::ffi::{CString, c_char};
use std::fs::{self, OpenOptions};
use std::io::{self, Read, Seek, SeekFrom, Write};
use std::os::unix::ffi::OsStrExt;
use std::os::unix::fs::{MetadataExt, OpenOptionsExt};
use std::os::unix::io::{AsRawFd, FromRawFd};
use std::path::Path;

const NOFOLLOW_NONBLOCK: i32 = 0o400000 | 0o4000;

unsafe extern "C" {
    fn geteuid() -> u32;
    fn openat(directory: i32, name: *const c_char, flags: i32, ...) -> i32;
    fn linkat(
        source_directory: i32,
        source: *const c_char,
        directory: i32,
        name: *const c_char,
        flags: i32,
    ) -> i32;
}

pub(crate) fn output_name(output: &Path) -> io::Result<CString> {
    let name = output.file_name().ok_or_else(unsafe_output)?;
    CString::new(name.as_bytes()).map_err(|_| unsafe_output())
}

pub(crate) fn create_output(directory: &fs::File) -> io::Result<fs::File> {
    // Linux O_RDWR | O_TMPFILE | O_CLOEXEC. No pathname exists before publication.
    let flags = 2 | 0o20200000 | 0o2000000;
    let fd = unsafe { openat(directory.as_raw_fd(), c".".as_ptr(), flags, 0o600_u32) };
    if fd < 0 {
        return Err(io::Error::last_os_error());
    }
    // Ownership of this newly allocated descriptor transfers to File once.
    Ok(unsafe { fs::File::from_raw_fd(fd) })
}

pub(crate) fn publish_output(
    file: &fs::File,
    directory: &fs::File,
    name: &CString,
) -> io::Result<()> {
    // The procfs descriptor link permits unprivileged publication of O_TMPFILE.
    // linkat creates the destination atomically and refuses every existing entry.
    let source = CString::new(format!("/proc/self/fd/{}", file.as_raw_fd())).unwrap();
    if unsafe {
        linkat(
            -100,
            source.as_ptr(),
            directory.as_raw_fd(),
            name.as_ptr(),
            0x400,
        )
    } < 0
    {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

pub(crate) fn checksum(bytes: &[u8]) -> String {
    format!("{:x}", Blake2b512::digest(bytes))
}

fn receipt(bytes: &[u8], inspected: &Value, schema: &str) -> Value {
    let mut receipt = json!({
        "schema": schema,
        "record_schema": super::audit::AUDIT_SCHEMA_V1,
        "bytes": bytes.len(),
        "records": inspected["records"],
        "algorithm": "blake2b-512",
        "digest": checksum(bytes),
        "authenticated": false,
    });
    // Slice 2 anchoring (docs/DURABLE_AUDIT_V2_DESIGN.md): for a
    // chained (v2) journal the receipt additionally pins the chain
    // segment the export covers — the anchor it chains from, the
    // head digest it ends at, and the head's position (chained
    // record count within the export's total record count). A
    // retained receipt therefore detects tail truncation of the
    // source journal on any later comparison, which the snapshot
    // digest alone cannot do.
    if let Some(chain) = inspected.get("chain") {
        receipt["chain"] = json!({
            "anchor": chain["anchor"],
            "head_digest": chain["tail"],
            "chained_records": chain["chained_records"],
            "records": inspected["records"],
        });
    }
    receipt
}

/// Copy a validated, bounded snapshot while holding the inspector's locks.
/// Output must be new and in a separate, private directory owned by the caller.
pub fn export(source: &Path, output: &Path) -> io::Result<Value> {
    super::audit_check::with_snapshot(source, |bytes, inspected| {
        let parent = output.parent().ok_or_else(unsafe_output)?;
        if !output.is_absolute() || output.file_name().is_none() {
            return Err(unsafe_output());
        }
        let directory = OpenOptions::new()
            .read(true)
            .custom_flags(NOFOLLOW_NONBLOCK)
            .open(parent)?;
        let meta = directory.metadata()?;
        let source_parent = fs::metadata(source.parent().unwrap_or(Path::new(".")))?;
        if !meta.is_dir()
            || meta.uid() != unsafe { geteuid() }
            || meta.mode() & 0o777 != 0o700
            || (meta.dev(), meta.ino()) == (source_parent.dev(), source_parent.ino())
        {
            return Err(unsafe_output());
        }
        let name = output_name(output)?;
        let mut file = create_output(&directory)?;
        let created = file.metadata()?;
        if !created.is_file()
            || created.uid() != meta.uid()
            || created.nlink() != 0
            || created.mode() & 0o777 != 0o600
        {
            return Err(unsafe_output());
        }
        file.write_all(bytes)?;
        file.sync_all()?;
        file.seek(SeekFrom::Start(0))?;
        let mut copied = Vec::new();
        (&file)
            .take(bytes.len() as u64 + 1)
            .read_to_end(&mut copied)?;
        if copied.as_slice() != bytes {
            return Err(io::Error::new(io::ErrorKind::InvalidData, "copy mismatch"));
        }
        // Validate the parent before publication as well as afterward.
        let parent_before = fs::symlink_metadata(parent)?;
        if (parent_before.dev(), parent_before.ino()) != (meta.dev(), meta.ino())
            || parent_before.mode() & 0o777 != 0o700
        {
            return Err(unsafe_output());
        }
        publish_output(&file, &directory, &name)?;
        directory.sync_all()?;
        let now = fs::symlink_metadata(output)?;
        let parent_now = fs::symlink_metadata(parent)?;
        if (now.dev(), now.ino()) != (created.dev(), created.ino())
            || (parent_now.dev(), parent_now.ino()) != (meta.dev(), meta.ino())
            || now.nlink() != 1
            || now.mode() & 0o777 != 0o600
            || now.len() != bytes.len() as u64
            || parent_now.mode() & 0o777 != 0o700
        {
            return Err(unsafe_output());
        }
        // After publication, an error may leave the complete copy. Never unlink
        // by pathname: another process could have replaced that entry.
        Ok(receipt(bytes, &inspected, "synveil.audit-export/v1"))
    })
}

fn unsafe_output() -> io::Error {
    io::Error::new(
        io::ErrorKind::PermissionDenied,
        "unsafe audit export output",
    )
}

fn digest_text(value: &Value) -> bool {
    value.as_str().is_some_and(|text| {
        text.len() == 128
            && text
                .bytes()
                .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    })
}

fn receipt_mismatch() -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, "receipt mismatch")
}

/// Verify an exported snapshot against its retained export receipt.
///
/// The receipt is owner-supplied input and is validated strictly:
/// it must be one of the two receipt schemas this tool emits, carry
/// `authenticated: false`, and name the snapshot's exact byte count,
/// record count and BLAKE2b-512 digest. When the receipt carries a
/// chain block (a v2 export), the snapshot's chain must match the
/// receipt's anchor, head digest and head position exactly — so a
/// mutated record, a receipt naming the wrong anchor, and a
/// truncated export all fail here even where the truncated bytes
/// would still form an internally valid chain.
pub fn verify_receipt(path: &Path, expected: &Value) -> io::Result<Value> {
    let schema_ok = expected["schema"] == "synveil.audit-export/v1"
        || expected["schema"] == "synveil.audit-verification/v1";
    if !expected.is_object()
        || !schema_ok
        || expected["algorithm"] != "blake2b-512"
        || expected["authenticated"] != false
        || !digest_text(&expected["digest"])
        || expected["bytes"].as_u64().is_none()
        || expected["records"].as_u64().is_none()
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid receipt",
        ));
    }
    if let Some(chain) = expected.get("chain")
        && (!chain.is_object()
            || !digest_text(&chain["anchor"])
            || !digest_text(&chain["head_digest"])
            || chain["chained_records"].as_u64().is_none()
            || chain["records"].as_u64().is_none())
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid receipt",
        ));
    }
    super::audit_check::with_snapshot(path, |bytes, inspected| {
        let report = receipt(bytes, &inspected, "synveil.audit-verification/v1");
        if report["digest"] != expected["digest"]
            || report["bytes"] != expected["bytes"]
            || report["records"] != expected["records"]
        {
            return Err(receipt_mismatch());
        }
        if let Some(chain) = expected.get("chain") {
            let actual = report.get("chain").ok_or_else(receipt_mismatch)?;
            if actual["anchor"] != chain["anchor"]
                || actual["head_digest"] != chain["head_digest"]
                || actual["chained_records"] != chain["chained_records"]
                || actual["records"] != chain["records"]
            {
                return Err(receipt_mismatch());
            }
        }
        Ok(report)
    })
}

/// Verify a snapshot against a receipt read from a separate file.
///
/// The receipt file is bounded and decoded with the strict audit
/// JSON decoder (duplicate keys and trailing input are refused),
/// mirroring how the retention tooling treats owner-supplied
/// receipts. Nothing about the receipt is echoed in errors.
pub fn verify_receipt_file(path: &Path, receipt_path: &Path) -> io::Result<Value> {
    const MAX_RECEIPT_BYTES: u64 = 8192;
    let file = OpenOptions::new()
        .read(true)
        .custom_flags(NOFOLLOW_NONBLOCK)
        .open(receipt_path)?;
    let meta = file.metadata()?;
    if !meta.is_file() || meta.len() > MAX_RECEIPT_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid receipt",
        ));
    }
    let mut bytes = Vec::new();
    (&file)
        .take(MAX_RECEIPT_BYTES + 1)
        .read_to_end(&mut bytes)?;
    if bytes.len() as u64 > MAX_RECEIPT_BYTES || bytes.contains(&b'\r') {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid receipt",
        ));
    }
    if bytes.last() == Some(&b'\n') {
        bytes.pop();
    }
    let expected = super::audit_json::decode(&bytes)
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "invalid receipt"))?;
    verify_receipt(path, &expected)
}

/// Verify exact bytes against a separately retained owner-supplied digest.
pub fn verify(path: &Path, expected: &str) -> io::Result<Value> {
    if expected.len() != 128
        || !expected
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid digest",
        ));
    }
    super::audit_check::with_snapshot(path, |bytes, inspected| {
        let report = receipt(bytes, &inspected, "synveil.audit-verification/v1");
        if report["digest"] != expected {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "digest mismatch",
            ));
        }
        Ok(report)
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::DirBuilderExt;
    use std::sync::atomic::{AtomicU64, Ordering};

    static NEXT: AtomicU64 = AtomicU64::new(0);

    fn fixture() -> (std::path::PathBuf, std::path::PathBuf, std::path::PathBuf) {
        let root = std::env::temp_dir().join(format!(
            "synveil-export-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::DirBuilder::new().mode(0o700).create(&root).unwrap();
        let dest = root.join("copies");
        fs::DirBuilder::new().mode(0o700).create(&dest).unwrap();
        let source = root.join("journal");
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(&source)
            .unwrap();
        writeln!(
            file,
            "{}",
            super::super::audit::record("request", json!({"private": "secret"}))
        )
        .unwrap();
        (root, source, dest.join("snapshot"))
    }

    #[test]
    fn copy_is_private_exact_and_verifiable_without_disclosing_fields() {
        let (root, source, output) = fixture();
        let original = fs::read(&source).unwrap();
        let report = export(&source, &output).unwrap();
        assert_eq!(fs::read(&output).unwrap(), original);
        assert_eq!(fs::read(&source).unwrap(), original);
        assert_eq!(fs::metadata(&output).unwrap().mode() & 0o777, 0o600);
        assert_eq!(report["authenticated"], false);
        assert!(!report.to_string().contains("secret"));
        verify(&output, report["digest"].as_str().unwrap()).unwrap();
        fs::remove_dir_all(root).unwrap();
    }

    fn chained_fixture() -> (
        std::path::PathBuf,
        std::path::PathBuf,
        std::path::PathBuf,
        String,
    ) {
        let (root, _v1_source, _v1_output) = fixture();
        let source = root.join("chained-journal");
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(&source)
            .unwrap();
        let mut prev = super::super::audit::GENESIS_DIGEST;
        let mut head = String::new();
        for _ in 0..3 {
            let (line, digest) = super::super::audit::chain_record(
                &super::super::audit::record("request", json!({"private": "secret"})),
                &prev,
            )
            .unwrap();
            writeln!(file, "{line}").unwrap();
            head = crate::sha256::hex(&digest);
            prev = digest;
        }
        drop(file);
        let dest = root.join("copies").join("chained-snapshot");
        (root, source, dest, head)
    }

    #[test]
    fn v2_export_receipt_anchors_the_chain_and_verifies() {
        let (root, source, output, head) = chained_fixture();
        let report = export(&source, &output).unwrap();
        let chain = &report["chain"];
        assert_eq!(
            chain["anchor"],
            crate::sha256::hex(&super::super::audit::GENESIS_DIGEST)
        );
        assert_eq!(chain["head_digest"], head);
        assert_eq!(chain["chained_records"], 3);
        assert_eq!(chain["records"], 3);
        assert!(!report.to_string().contains("secret"));
        // The receipt verifies the export exactly, and the legacy
        // digest path still works on the same snapshot.
        verify_receipt(&output, &report).unwrap();
        verify(&output, report["digest"].as_str().unwrap()).unwrap();
        // A v1 export carries no chain block, exactly as before.
        let (v1_root, v1_source, v1_output) = fixture();
        let v1_report = export(&v1_source, &v1_output).unwrap();
        assert!(v1_report.get("chain").is_none());
        verify_receipt(&v1_output, &v1_report).unwrap();
        fs::remove_dir_all(v1_root).unwrap();
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn receipt_verification_refuses_mutation_wrong_anchor_and_truncation() {
        let (root, source, output, _head) = chained_fixture();
        let report = export(&source, &output).unwrap();
        let original = fs::read(&output).unwrap();

        // A well-formed edit inside a record breaks the chain/digest.
        let edited = String::from_utf8(original.clone())
            .unwrap()
            .replace("secret", "edited");
        fs::write(&output, edited).unwrap();
        assert_eq!(
            verify_receipt(&output, &report).unwrap_err().kind(),
            io::ErrorKind::InvalidData
        );

        // Truncating the export's tail record leaves an internally
        // valid shorter chain; the retained receipt still refuses it.
        let text = String::from_utf8(original.clone()).unwrap();
        let truncated = text
            .lines()
            .take(2)
            .map(|line| format!("{line}\n"))
            .collect::<String>();
        fs::write(&output, truncated).unwrap();
        assert_eq!(
            verify_receipt(&output, &report).unwrap_err().kind(),
            io::ErrorKind::InvalidData
        );
        fs::write(&output, original).unwrap();

        // A receipt naming the wrong anchor or head is refused even
        // against the untouched snapshot.
        for key in ["anchor", "head_digest"] {
            let mut wrong = report.clone();
            wrong["chain"][key] = json!("1".repeat(128));
            assert_eq!(
                verify_receipt(&output, &wrong).unwrap_err().kind(),
                io::ErrorKind::InvalidData,
                "accepted wrong {key}"
            );
        }
        // A chained receipt presented for an unchained journal fails.
        let (v1_root, v1_source, _v1_output) = fixture();
        assert!(verify_receipt(&v1_source, &report).is_err());
        fs::remove_dir_all(v1_root).unwrap();
        // Malformed receipts are refused as invalid input.
        for bad in [
            json!({"schema": "synveil.audit-export/v1", "algorithm": "blake2b-512",
                   "authenticated": true, "digest": "0".repeat(128),
                   "bytes": 1, "records": 1}),
            json!({"schema": "other/v1", "algorithm": "blake2b-512",
                   "authenticated": false, "digest": "0".repeat(128),
                   "bytes": 1, "records": 1}),
            json!({"schema": "synveil.audit-export/v1", "algorithm": "blake2b-512",
                   "authenticated": false, "digest": "0".repeat(128),
                   "bytes": 1, "records": 1,
                   "chain": {"anchor": "x", "head_digest": "0".repeat(128),
                             "chained_records": 1, "records": 1}}),
        ] {
            assert_eq!(
                verify_receipt(&output, &bad).unwrap_err().kind(),
                io::ErrorKind::InvalidInput
            );
        }
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn receipt_file_round_trip_and_refusals() {
        let (root, source, output, _head) = chained_fixture();
        let report = export(&source, &output).unwrap();
        let receipt_path = root.join("receipt.json");
        fs::write(&receipt_path, format!("{report}\n")).unwrap();
        verify_receipt_file(&output, &receipt_path).unwrap();
        // Garbage, oversized and missing receipt files are refused.
        fs::write(&receipt_path, b"not json").unwrap();
        assert_eq!(
            verify_receipt_file(&output, &receipt_path)
                .unwrap_err()
                .kind(),
            io::ErrorKind::InvalidInput
        );
        fs::write(&receipt_path, vec![b' '; 8193]).unwrap();
        assert!(verify_receipt_file(&output, &receipt_path).is_err());
        assert!(verify_receipt_file(&output, &root.join("absent.json")).is_err());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn well_formed_tampering_is_detected() {
        let (root, source, output) = fixture();
        let report = export(&source, &output).unwrap();
        let text = fs::read_to_string(&output)
            .unwrap()
            .replace("secret", "edited");
        fs::write(&output, text).unwrap();
        assert!(super::super::audit_check::inspect(&output).is_ok());
        assert_eq!(
            verify(&output, report["digest"].as_str().unwrap())
                .unwrap_err()
                .kind(),
            io::ErrorKind::InvalidData
        );
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn existing_outputs_symlinks_and_source_directory_are_refused() {
        let (root, source, output) = fixture();
        fs::write(&output, b"existing").unwrap();
        assert!(export(&source, &output).is_err());
        assert_eq!(fs::read(&output).unwrap(), b"existing");
        fs::remove_file(&output).unwrap();
        std::os::unix::fs::symlink(&source, &output).unwrap();
        assert!(export(&source, &output).is_err());
        assert!(export(&source, &root.join("another-journal")).is_err());
        assert!(!root.join("another-journal").exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn invalid_source_and_unsafe_destination_create_nothing() {
        use std::os::unix::fs::PermissionsExt;
        let (root, source, output) = fixture();
        fs::set_permissions(output.parent().unwrap(), fs::Permissions::from_mode(0o755)).unwrap();
        assert!(export(&source, &output).is_err());
        fs::set_permissions(output.parent().unwrap(), fs::Permissions::from_mode(0o700)).unwrap();
        fs::write(&source, b"incomplete").unwrap();
        assert!(export(&source, &output).is_err());
        assert!(!output.exists());
        assert_eq!(fs::read(&source).unwrap(), b"incomplete");
        for digest in ["", "../bad", &"A".repeat(128)] {
            assert_eq!(
                verify(&source, digest).unwrap_err().kind(),
                io::ErrorKind::InvalidInput
            );
        }
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn blake2b_digest_matches_published_vector() {
        assert_eq!(
            checksum(b"hello world"),
            concat!(
                "021ced8799296ceca557832ab941a50b4a11f83478cf141f51f933f653ab9fbc",
                "c05a037cddbed06e309bf334942c4e58cdf1a46e237911ccd7fcf9787cbc7fd0"
            )
        );
    }

    #[test]
    fn busy_source_refuses_export_without_creating_output() {
        use std::os::unix::io::AsRawFd;
        unsafe extern "C" {
            fn flock(fd: i32, operation: i32) -> i32;
        }
        let (root, source, output) = fixture();
        let held = super::super::audit::directory_lock(&source, true)
            .unwrap()
            .unwrap();
        assert_eq!(
            export(&source, &output).unwrap_err().kind(),
            io::ErrorKind::WouldBlock
        );
        assert!(!output.exists());
        assert_eq!(unsafe { flock(held.as_raw_fd(), 8) }, 0);
        drop(held);
        export(&source, &output).unwrap();
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn publication_stays_in_open_directory_after_path_substitution() {
        let (root, _source, output) = fixture();
        let parent = output.parent().unwrap();
        let directory = fs::File::open(parent).unwrap();
        let moved = root.join("moved");
        let unrelated = root.join("unrelated");
        fs::DirBuilder::new()
            .mode(0o700)
            .create(&unrelated)
            .unwrap();
        let mut copy = create_output(&directory).unwrap();
        copy.write_all(b"private snapshot").unwrap();
        assert!(!output.exists());
        assert_eq!(copy.metadata().unwrap().nlink(), 0);
        fs::rename(parent, &moved).unwrap();
        std::os::unix::fs::symlink(&unrelated, parent).unwrap();
        publish_output(&copy, &directory, &output_name(&output).unwrap()).unwrap();
        assert_eq!(
            fs::read(moved.join("snapshot")).unwrap(),
            b"private snapshot"
        );
        assert!(!unrelated.join("snapshot").exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn failed_publication_and_drop_preserve_replacement_and_symlink() {
        let (root, _source, output) = fixture();
        let directory = fs::File::open(output.parent().unwrap()).unwrap();
        let name = output_name(&output).unwrap();
        let mut copy = create_output(&directory).unwrap();
        copy.write_all(b"partial").unwrap();
        fs::write(&output, b"replacement").unwrap();
        assert_eq!(
            publish_output(&copy, &directory, &name).unwrap_err().kind(),
            io::ErrorKind::AlreadyExists
        );
        drop(copy);
        assert_eq!(fs::read(&output).unwrap(), b"replacement");
        fs::remove_file(&output).unwrap();
        let target = root.join("target");
        fs::write(&target, b"unrelated").unwrap();
        std::os::unix::fs::symlink(&target, &output).unwrap();
        let copy = create_output(&directory).unwrap();
        assert_eq!(
            publish_output(&copy, &directory, &name).unwrap_err().kind(),
            io::ErrorKind::AlreadyExists
        );
        drop(copy);
        assert!(
            fs::symlink_metadata(&output)
                .unwrap()
                .file_type()
                .is_symlink()
        );
        assert_eq!(fs::read(target).unwrap(), b"unrelated");
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn dropping_failed_copy_creates_no_directory_entry() {
        let (root, _source, output) = fixture();
        let directory = fs::File::open(output.parent().unwrap()).unwrap();
        let mut copy = create_output(&directory).unwrap();
        copy.write_all(b"partial").unwrap();
        drop(copy);
        assert!(!output.exists());
        assert_eq!(fs::read_dir(output.parent().unwrap()).unwrap().count(), 0);
        fs::remove_dir_all(root).unwrap();
    }
}
