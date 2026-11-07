// SPDX-License-Identifier: MPL-2.0

use serde_json::{json, Value};
use std::ffi::{c_char, CString};
use std::fs::{self, OpenOptions};
use std::io::{self, Read, Seek, SeekFrom, Write};
use std::os::unix::ffi::OsStrExt;
use std::os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt};
use std::os::unix::io::AsRawFd;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

pub const AUDIT_SCHEMA_V1: &str = "synveil.audit/v1";
pub const AUDIT_SCHEMA_V2: &str = "synveil.audit/v2";
// Phase 2 durable audit format (docs/DURABLE_AUDIT_V2_DESIGN.md):
// records written to the persistent journal are hash-chained. A v2
// record carries prev_digest (the link hash of the previous
// record) and record_digest = SHA-512(prev_digest_bytes ||
// canonical record bytes without record_digest). The link hash of
// a v1 record is defined as SHA-512 of its raw line bytes, so a
// journal written before the chain existed links seamlessly into
// it. The chain's genesis prev_digest is 64 zero bytes.
pub(crate) const GENESIS_DIGEST: [u8; 64] = [0; 64];
// Prototype protection against unbounded persistent journal growth. A
// production release still requires retention policy and independent integrity.
const MAX_AUDIT_BYTES: u64 = 4 * 1024 * 1024;
const MAX_AUDIT_RECORD_BYTES: usize = 64 * 1024;
const LINUX_LOCK_EX_NONBLOCK: i32 = 2 | 4;

unsafe extern "C" {
    fn flock(fd: i32, operation: i32) -> i32;
    fn renameat2(
        old_dir: i32,
        old: *const c_char,
        new_dir: i32,
        new: *const c_char,
        flags: u32,
    ) -> i32;
}

static SEQUENCE: AtomicU64 = AtomicU64::new(1);
static PERSISTENT_WRITE_ATTEMPTED: AtomicBool = AtomicBool::new(false);
static LAST_PERSISTENT_WRITE_SUCCEEDED: AtomicBool = AtomicBool::new(false);
static PERSISTENT_WRITE_FAILURES: AtomicU64 = AtomicU64::new(0);

pub fn persistent_status() -> veil_protocol::PersistentAuditStatus {
    let configured = std::env::var_os("SYNVEIL_AUDIT_PATH").is_some();
    let state = if !configured {
        "disabled"
    } else if !PERSISTENT_WRITE_ATTEMPTED.load(Ordering::SeqCst) {
        "starting"
    } else if LAST_PERSISTENT_WRITE_SUCCEEDED.load(Ordering::SeqCst) {
        "healthy"
    } else {
        "degraded"
    };
    veil_protocol::PersistentAuditStatus {
        configured,
        state: state.to_owned(),
        failed_writes: PERSISTENT_WRITE_FAILURES.load(Ordering::SeqCst),
    }
}

pub fn record(event: &str, fields: Value) -> Value {
    let unix_time_ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .ok()
        .and_then(|duration| u64::try_from(duration.as_millis()).ok());
    record_at(event, fields, unix_time_ms)
}

fn record_at(event: &str, fields: Value, unix_time_ms: Option<u64>) -> Value {
    json!({
        "schema": AUDIT_SCHEMA_V1,
        "component": "veil-core",
        "pid": std::process::id(),
        "sequence": SEQUENCE.fetch_add(1, Ordering::Relaxed),
        "unix_time_ms": unix_time_ms,
        "version": veil_protocol::BUILD_VERSION,
        "git_revision": veil_protocol::BUILD_REVISION,
        "event": event,
        "fields": fields,
    })
}

pub fn emit(event: &str, fields: Value) {
    let value = record(event, fields);
    // The console mirror prints the record as built; the persistent
    // journal stores its hash-chained v2 form (see append_chained).
    eprintln!("{value}");
    // Opt-in audit journal, only set by bootstrap after /var is mounted.
    // Console logging remains available even if persistent storage fails.
    if let Some(path) = std::env::var_os("SYNVEIL_AUDIT_PATH") {
        match append_chained(Path::new(&path), &value) {
            Ok(()) => {
                LAST_PERSISTENT_WRITE_SUCCEEDED.store(true, Ordering::SeqCst);
                PERSISTENT_WRITE_ATTEMPTED.store(true, Ordering::SeqCst);
            }
            Err(error) => {
                PERSISTENT_WRITE_FAILURES.fetch_add(1, Ordering::SeqCst);
                LAST_PERSISTENT_WRITE_SUCCEEDED.store(false, Ordering::SeqCst);
                PERSISTENT_WRITE_ATTEMPTED.store(true, Ordering::SeqCst);
                eprintln!("[synveil-audit] persistent write failed: {error}");
            }
        }
    }
}

// Linux O_NOFOLLOW and O_NONBLOCK: refuse final symlinks and FIFOs.
const LINUX_O_NOFOLLOW: i32 = 0o400000;
const LINUX_O_NONBLOCK: i32 = 0o4000;

fn unsafe_journal() -> io::Error {
    io::Error::new(io::ErrorKind::PermissionDenied, "unsafe audit journal path")
}

// All rotating writers and inspectors acquire this stable inode before opening
// a journal. A per-journal flock alone cannot serialize writers across rename.
pub(crate) fn directory_lock(path: &Path, write: bool) -> io::Result<Option<fs::File>> {
    let parent = path
        .parent()
        .filter(|value| !value.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    let lock_path = parent.join(".audit-lock");
    if path.file_name() == lock_path.file_name() {
        return Err(unsafe_journal());
    }
    if !write {
        match fs::symlink_metadata(&lock_path) {
            Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(None),
            Err(error) => return Err(error),
            Ok(_) => {}
        }
    }
    let directory = fs::symlink_metadata(parent)?;
    if !directory.is_dir() || directory.mode() & 0o022 != 0 {
        return Err(unsafe_journal());
    }
    let lock = OpenOptions::new()
        .read(true)
        .write(write)
        .create(write)
        .truncate(false)
        .mode(0o600)
        .custom_flags(LINUX_O_NOFOLLOW | LINUX_O_NONBLOCK)
        .open(lock_path)?;
    let meta = lock.metadata()?;
    if !meta.is_file()
        || meta.uid() != directory.uid()
        || meta.nlink() != 1
        || meta.mode() & 0o777 != 0o600
        || meta.len() != 0
    {
        return Err(unsafe_journal());
    }
    let operation = if write { LINUX_LOCK_EX_NONBLOCK } else { 1 | 4 };
    if unsafe { flock(lock.as_raw_fd(), operation) } != 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(Some(lock))
}

/// The writer's lock acquisition: retry contention for a bounded
/// window instead of dropping the record. At native startup the
/// supervisor and its supervised core append concurrently, and a
/// critical section includes file + directory fsyncs, which on
/// slow storage can outlast an instant try by orders of
/// magnitude; the 2026-11-06 QEMU acceptance boot lost a startup
/// record to exactly this (`persistent write failed: Resource
/// temporarily unavailable`). The lock is taken before any write,
/// so waiting is safe: a contended attempt has written nothing.
/// Only WouldBlock waits; every other error fails immediately,
/// and inspection/retention keep the fail-fast `directory_lock`.
fn directory_lock_writer(path: &Path) -> io::Result<Option<fs::File>> {
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(10);
    loop {
        match directory_lock(path, true) {
            Err(error)
                if error.kind() == io::ErrorKind::WouldBlock
                    && std::time::Instant::now() < deadline =>
            {
                std::thread::sleep(std::time::Duration::from_millis(10));
            }
            result => return result,
        }
    }
}

fn archive_path(path: &Path) -> io::Result<PathBuf> {
    let mut name = path.file_name().ok_or_else(unsafe_journal)?.to_os_string();
    name.push(".1");
    Ok(path.with_file_name(name))
}

fn preserve_archive(path: &Path) -> io::Result<()> {
    let old = CString::new(path.as_os_str().as_bytes()).map_err(|_| unsafe_journal())?;
    let archive = archive_path(path)?;
    let new = CString::new(archive.as_os_str().as_bytes()).map_err(|_| unsafe_journal())?;
    // Linux RENAME_NOREPLACE is atomic; files, symlinks and directories at the
    // archive destination are never replaced. Unsupported kernels fail closed.
    if unsafe { renameat2(-100, old.as_ptr(), -100, new.as_ptr(), 1) } != 0 {
        let error = io::Error::last_os_error();
        return Err(if error.kind() == io::ErrorKind::AlreadyExists {
            io::Error::new(
                error.kind(),
                "audit archive exists; retention capacity reached",
            )
        } else {
            error
        });
    }
    Ok(())
}

fn open_journal(path: &Path, directory: &fs::Metadata) -> io::Result<fs::File> {
    let file = OpenOptions::new()
        .create(true)
        .read(true)
        .append(true)
        .mode(0o600)
        .custom_flags(LINUX_O_NOFOLLOW | LINUX_O_NONBLOCK)
        .open(path)?;
    let meta = file.metadata()?;
    if !meta.is_file()
        || meta.uid() != directory.uid()
        || meta.nlink() != 1
        || meta.permissions().mode() & 0o777 != 0o600
    {
        return Err(unsafe_journal());
    }
    if unsafe { flock(file.as_raw_fd(), LINUX_LOCK_EX_NONBLOCK) } != 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(file)
}

fn sync_directory(parent: &Path, directory: &fs::Metadata) -> io::Result<()> {
    let opened = OpenOptions::new()
        .read(true)
        .custom_flags(LINUX_O_NOFOLLOW | LINUX_O_NONBLOCK)
        .open(parent)?;
    let meta = opened.metadata()?;
    if !meta.is_dir() || meta.dev() != directory.dev() || meta.ino() != directory.ino() {
        return Err(unsafe_journal());
    }
    opened.sync_all()
}

// Keep storage operations statically dispatched so tests can inject I/O
// errors at each boundary without adding runtime environment-driven failpoints.
trait JournalIo {
    fn write(&mut self, file: &mut fs::File, bytes: &[u8]) -> io::Result<()> {
        file.write_all(bytes)
    }

    fn sync_file(&mut self, file: &fs::File) -> io::Result<()> {
        file.sync_all()
    }

    fn archive(&mut self, path: &Path) -> io::Result<()> {
        preserve_archive(path)
    }

    fn sync_parent(&mut self, parent: &Path, directory: &fs::Metadata) -> io::Result<()> {
        sync_directory(parent, directory)
    }
}

struct FilesystemIo;
impl JournalIo for FilesystemIo {}

/// Decode a 64-byte digest from its 128-char lowercase hex form.
pub(crate) fn digest_from_hex(text: &str) -> Option<[u8; 64]> {
    if text.len() != 128 {
        return None;
    }
    let mut out = [0u8; 64];
    for (index, byte) in out.iter_mut().enumerate() {
        *byte = u8::from_str_radix(text.get(index * 2..index * 2 + 2)?, 16).ok()?;
    }
    Some(out)
}

/// The chain link hash of one stored journal line (without its
/// trailing newline): a v2 record's committed record_digest, or —
/// for a v1 record — SHA-512 of the raw line bytes.
pub(crate) fn link_hash_of_line(line: &[u8]) -> io::Result<[u8; 64]> {
    let value = super::audit_json::decode(line).map_err(|_| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            "audit journal line is not valid JSON",
        )
    })?;
    if let Some(text) = value["record_digest"].as_str() {
        return digest_from_hex(text).ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidData,
                "audit record_digest is malformed",
            )
        });
    }
    Ok(crate::sha512::sha512(line))
}

/// Extract the final line (without trailing newline) from the tail
/// of an opened journal-like file of length `current`.
fn final_line(file: &mut fs::File, current: u64) -> io::Result<Vec<u8>> {
    let window = current.min(MAX_AUDIT_RECORD_BYTES as u64 + 2);
    let mut tail = vec![0u8; window as usize];
    file.seek(SeekFrom::Start(current - window))?;
    file.read_exact(&mut tail)?;
    if tail.last() == Some(&b'\n') {
        tail.pop();
    }
    let start = tail
        .iter()
        .rposition(|byte| *byte == b'\n')
        .map(|index| index + 1)
        .unwrap_or(0);
    Ok(tail[start..].to_vec())
}

/// The link hash the next record must chain from: the active
/// file's last record, or — for an empty/absent active file — the
/// `.1` archive's last record, or genesis when neither exists.
fn tail_link_hash(path: &Path, file: &mut fs::File, current: u64) -> io::Result<[u8; 64]> {
    if current != 0 {
        return link_hash_of_line(&final_line(file, current)?);
    }
    let archive = archive_path(path)?;
    let mut archive_file = match OpenOptions::new().read(true).open(&archive) {
        Ok(file) => file,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(GENESIS_DIGEST),
        Err(error) => return Err(error),
    };
    let archive_len = archive_file.metadata()?.len();
    if archive_len == 0 {
        return Ok(GENESIS_DIGEST);
    }
    link_hash_of_line(&final_line(&mut archive_file, archive_len)?)
}

/// Produce the stored v2 form of a record: schema upgraded,
/// prev_digest inserted, record_digest computed over
/// prev_digest_bytes || canonical bytes (record without
/// record_digest), both digests as lowercase hex.
pub(crate) fn chain_record(record: &Value, prev: &[u8; 64]) -> io::Result<(String, [u8; 64])> {
    let mut value = record.clone();
    {
        let object = value.as_object_mut().ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::InvalidInput,
                "audit record must be an object",
            )
        })?;
        object.insert("schema".to_owned(), json!(AUDIT_SCHEMA_V2));
        object.insert("prev_digest".to_owned(), json!(crate::sha256::hex(prev)));
    }
    let canonical = value.to_string();
    let mut input = prev.to_vec();
    input.extend_from_slice(canonical.as_bytes());
    let digest = crate::sha512::sha512(&input);
    value.as_object_mut().unwrap().insert(
        "record_digest".to_owned(),
        json!(crate::sha256::hex(&digest)),
    );
    Ok((value.to_string(), digest))
}

// The unchained line append is retained for the test suite (the
// v1 journal form and the rollover/crash gates are exercised
// through it); production writes go through append_chained.
#[cfg(test)]
fn append_record(path: &Path, line: &str) -> io::Result<()> {
    append_record_with_io(path, line, &mut FilesystemIo)
}

fn append_chained(path: &Path, record: &Value) -> io::Result<()> {
    append_chained_with_io(path, record, &mut FilesystemIo)
}

fn append_chained_with_io(
    path: &Path,
    record: &Value,
    storage: &mut impl JournalIo,
) -> io::Result<()> {
    append_prepared_with_io(path, storage, |file, current, path| {
        let prev = tail_link_hash(path, file, current)?;
        let (line, _digest) = chain_record(record, &prev)?;
        Ok(line.into_bytes())
    })
}

#[cfg(test)]
fn append_record_with_io(path: &Path, line: &str, storage: &mut impl JournalIo) -> io::Result<()> {
    // A record must remain one bounded line even if an internal caller errs.
    if line.is_empty() || line.contains(['\n', '\r']) || line.len() >= MAX_AUDIT_RECORD_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "audit event must be one bounded nonempty line",
        ));
    }
    let owned = line.as_bytes().to_vec();
    append_prepared_with_io(path, storage, move |_, _, _| Ok(owned))
}

/// Shared append flow: validate the destination, take the
/// directory lock, open the journal, refuse an incomplete final
/// record, let `prepare` produce the record bytes from the opened
/// file (the chained writer reads the tail here, inside the
/// lock), roll over at capacity, then write and sync.
fn append_prepared_with_io(
    path: &Path,
    storage: &mut impl JournalIo,
    prepare: impl FnOnce(&mut fs::File, u64, &Path) -> io::Result<Vec<u8>>,
) -> io::Result<()> {
    let parent = path.parent().ok_or_else(unsafe_journal)?;
    let directory = fs::symlink_metadata(parent)?;
    if !directory.file_type().is_dir() || directory.mode() & 0o022 != 0 {
        return Err(unsafe_journal());
    }
    let _lock = directory_lock_writer(path)?;
    // Refuse existing suspicious objects, then validate the opened inode.
    match fs::symlink_metadata(path) {
        Ok(meta) if !meta.file_type().is_file() => return Err(unsafe_journal()),
        Ok(_) => {}
        Err(error) if error.kind() == io::ErrorKind::NotFound => {}
        Err(error) => return Err(error),
    }
    let mut file = open_journal(path, &directory)?;
    let current = file.metadata()?.len();
    if current > MAX_AUDIT_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "audit journal exceeds capacity",
        ));
    }
    if current != 0 {
        // A crash or failed write may leave an incomplete final record. Never
        // concatenate the next event onto it or silently discard evidence.
        file.seek(SeekFrom::End(-1))?;
        let mut last = [0];
        file.read_exact(&mut last)?;
        if last[0] != b'\n' {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "persistent audit journal has an incomplete final record",
            ));
        }
    }
    let mut bytes = prepare(&mut file, current, path)?;
    bytes.push(b'\n');
    if bytes.len() as u64 > MAX_AUDIT_BYTES {
        return Err(io::Error::other("audit event exceeds journal limit"));
    }
    if current
        .checked_add(bytes.len() as u64)
        .is_none_or(|next| next > MAX_AUDIT_BYTES)
    {
        storage.sync_file(&file)?;
        storage.archive(path)?;
        // Commit the archive rename before creating the next active journal.
        storage.sync_parent(parent, &directory)?;
        eprintln!("[synveil-audit] full journal preserved in .1 archive");
        file = open_journal(path, &directory)?;
    }
    storage.write(&mut file, &bytes)?;
    storage.sync_file(&file)?;
    // File synchronization alone does not persist a newly created directory
    // entry. Repeat this after every append, including retries after failure.
    storage.sync_parent(parent, &directory)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn records_build_process_and_event_identity() {
        let value = record_at(
            "request_rejected",
            json!({ "code": "malformed_message" }),
            Some(123),
        );
        assert_eq!(value["schema"], AUDIT_SCHEMA_V1);
        assert_eq!(value["component"], "veil-core");
        assert_eq!(value["pid"], std::process::id());
        assert_eq!(value["version"], veil_protocol::BUILD_VERSION);
        assert_eq!(value["event"], "request_rejected");
        assert_eq!(value["fields"]["code"], "malformed_message");
        assert_eq!(value["unix_time_ms"], 123);
    }

    #[test]
    fn sequences_increase_within_process() {
        let first = record("start", json!({}))["sequence"].as_u64().unwrap();
        let second = record("shutdown", json!({}))["sequence"].as_u64().unwrap();
        assert!(first > 0 && second > first);
    }

    #[test]
    fn unavailable_clock_is_explicit() {
        assert!(record_at("start", json!({}), None)["unix_time_ms"].is_null());
    }

    fn journal_lines(path: &Path) -> Vec<Value> {
        fs::read_to_string(path)
            .unwrap()
            .lines()
            .map(|line| crate::audit_json::decode(line.as_bytes()).unwrap())
            .collect()
    }

    #[test]
    fn chained_records_link_from_genesis_and_verify() {
        let dir = test_dir("chain");
        let journal = dir.join("journal");
        for event in ["chain-a", "chain-b", "chain-c"] {
            append_chained(&journal, &record(event, json!({}))).unwrap();
        }
        let lines = journal_lines(&journal);
        assert_eq!(lines.len(), 3);
        let genesis = crate::sha256::hex(&GENESIS_DIGEST);
        assert_eq!(lines[0]["schema"], AUDIT_SCHEMA_V2);
        assert_eq!(lines[0]["prev_digest"], genesis);
        assert_eq!(lines[1]["prev_digest"], lines[0]["record_digest"]);
        assert_eq!(lines[2]["prev_digest"], lines[1]["record_digest"]);
        // Each append re-read the tail from disk (no in-process
        // chain state), and the offline checker verifies the file.
        let report = super::super::audit_check::inspect(&journal).unwrap();
        assert_eq!(report["records"], 3);
        assert_eq!(report["chain"]["chained_records"], 3);
        assert_eq!(report["chain"]["anchor"], genesis);
        assert_eq!(
            report["chain"]["tail"],
            lines[2]["record_digest"].as_str().unwrap()
        );
    }

    #[test]
    fn chained_append_waits_out_a_slow_lock_holder() {
        // Regression test for the native-startup record loss:
        // a competing writer holding the journal lock for ~1.5 s
        // must delay the append, not drop the record.
        let dir = test_dir("chain-lock-wait");
        let journal = dir.join("journal");
        let held = directory_lock(&journal, true).unwrap().unwrap();
        let release = std::thread::spawn(move || {
            std::thread::sleep(std::time::Duration::from_millis(1500));
            assert_eq!(unsafe { flock(held.as_raw_fd(), 8) }, 0);
            held
        });
        let started = std::time::Instant::now();
        append_chained(&journal, &record("patient", json!({}))).unwrap();
        assert!(started.elapsed() >= std::time::Duration::from_millis(1500));
        release.join().unwrap();
        let lines = journal_lines(&journal);
        assert_eq!(lines.len(), 1);
        assert_eq!(lines[0]["event"], "patient");
        assert!(super::super::audit_check::inspect(&journal).is_ok());
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn chained_append_after_v1_records_links_by_line_hash() {
        let dir = test_dir("chain-upgrade");
        let journal = dir.join("journal");
        let v1_line = record("legacy", json!({})).to_string();
        append_record(&journal, &v1_line).unwrap();
        append_chained(&journal, &record("chained", json!({}))).unwrap();
        let lines = journal_lines(&journal);
        assert_eq!(lines.len(), 2);
        assert_eq!(lines[0]["schema"], AUDIT_SCHEMA_V1);
        let expected = crate::sha256::hex(&crate::sha512::sha512(v1_line.as_bytes()));
        assert_eq!(lines[1]["prev_digest"], expected);
        assert!(super::super::audit_check::inspect(&journal).is_ok());
    }

    /// Append with a bounded retry on lock contention. Under
    /// parallel test load the crash-worker tests spawn child
    /// processes; a child forked while this test holds the
    /// directory lock inherits the locked open file description
    /// until exec, so a following append can transiently see
    /// WouldBlock even though no live writer holds the journal
    /// (verified by strace: the failing flock is on this test's
    /// own lock file, touched by no other thread). The lock is
    /// taken before any write, so a contended attempt wrote
    /// nothing and retrying the same record is safe.
    fn append_chained_patient(path: &Path, value: &Value) {
        for attempt in 0..100 {
            match append_chained(path, value) {
                Ok(()) => return,
                Err(error) if error.kind() == io::ErrorKind::WouldBlock && attempt < 99 => {
                    std::thread::sleep(std::time::Duration::from_millis(10));
                }
                Err(error) => panic!("chained append failed: {error}"),
            }
        }
    }

    #[test]
    fn chained_rollover_continues_chain_from_archive() {
        let dir = test_dir("chain-rollover");
        let journal = dir.join("journal");
        let archive = archive_path(&journal).unwrap();
        // ~60 KiB records: the journal fills in tens of appends.
        let blob = "x".repeat(60_000);
        // Fill past capacity so the writer rolls over exactly once;
        // the archive slot is single, so stop soon after.
        let mut appends = 0;
        while !archive.exists() && appends < 3000 {
            append_chained_patient(&journal, &record("fill", json!({ "blob": blob })));
            appends += 1;
        }
        assert!(archive.exists(), "rollover never happened");
        append_chained_patient(&journal, &record("after", json!({})));
        let archived = journal_lines(&archive);
        let active = journal_lines(&journal);
        assert!(!archived.is_empty() && !active.is_empty());
        // The chain crosses the rollover boundary: the first active
        // record chains from the archived file's last record.
        assert_eq!(
            active[0]["prev_digest"],
            archived[archived.len() - 1]["record_digest"]
        );
        assert!(super::super::audit_check::inspect(&journal).is_ok());
        assert!(super::super::audit_check::inspect(&archive).is_ok());
    }

    fn test_dir(label: &str) -> std::path::PathBuf {
        let path = std::env::temp_dir().join(format!(
            "synveil-audit-{label}-{}-{}",
            std::process::id(),
            SEQUENCE.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&path).unwrap();
        // The journal writer correctly refuses a group/world-writable parent
        // directory. Pin the private mode the fixture intends instead of
        // inheriting the ambient umask (0777 & ~umask), which under a umask
        // such as 0007 yields 0770 and fails every append for environmental
        // reasons only.
        fs::set_permissions(&path, fs::Permissions::from_mode(0o700)).unwrap();
        path
    }

    #[test]
    fn symlinks_are_rejected_without_touching_target() {
        let dir = test_dir("link");
        let target = dir.join("target");
        fs::write(&target, b"original").unwrap();
        let journal = dir.join("journal");
        std::os::unix::fs::symlink(&target, &journal).unwrap();
        assert_eq!(
            append_record(&journal, "injected").unwrap_err().kind(),
            io::ErrorKind::PermissionDenied
        );
        assert_eq!(fs::read(&target).unwrap(), b"original");
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn hardlinks_and_permissive_journals_are_rejected() {
        let dir = test_dir("hardlink");
        let original = dir.join("original");
        fs::write(&original, b"unchanged").unwrap();
        fs::set_permissions(&original, fs::Permissions::from_mode(0o600)).unwrap();
        let journal = dir.join("journal");
        fs::hard_link(&original, &journal).unwrap();
        assert_eq!(
            append_record(&journal, "injected").unwrap_err().kind(),
            io::ErrorKind::PermissionDenied
        );
        fs::remove_file(&journal).unwrap();
        fs::set_permissions(&original, fs::Permissions::from_mode(0o644)).unwrap();
        assert_eq!(
            append_record(&original, "injected").unwrap_err().kind(),
            io::ErrorKind::PermissionDenied
        );
        assert_eq!(fs::read(&original).unwrap(), b"unchanged");
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn private_append_succeeds_but_unsafe_parent_refuses_write() {
        let dir = test_dir("parent");
        let journal = dir.join("journal");
        append_fixture(&journal, "first").unwrap();
        append_fixture(&journal, "second").unwrap();
        assert_eq!(fs::read_to_string(&journal).unwrap(), "first\nsecond\n");
        fs::set_permissions(&dir, fs::Permissions::from_mode(0o777)).unwrap();
        assert_eq!(
            append_record(&journal, "third").unwrap_err().kind(),
            io::ErrorKind::PermissionDenied
        );
        assert_eq!(fs::read_to_string(&journal).unwrap(), "first\nsecond\n");
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn bounded_audit_journal_refuses_growth_before_disk_exhaustion() {
        let dir = test_dir("capacity");
        let journal = dir.join("journal");
        let initial = vec![b'x'; (MAX_AUDIT_BYTES - 3) as usize];
        fs::write(&journal, &initial).unwrap();
        // The capacity fixture represents a complete existing record.
        let mut file = OpenOptions::new().append(true).open(&journal).unwrap();
        file.write_all(b"\n").unwrap();
        fs::set_permissions(&journal, fs::Permissions::from_mode(0o600)).unwrap();
        append_fixture(&journal, "x").unwrap();
        assert_eq!(fs::metadata(&journal).unwrap().len(), MAX_AUDIT_BYTES);
        // Exhausted retention never overwrites an existing archive.
        fs::write(archive_path(&journal).unwrap(), b"retained archive").unwrap();
        assert!(append_record(&journal, "more").is_err());
        assert_eq!(fs::metadata(&journal).unwrap().len(), MAX_AUDIT_BYTES);
        assert_eq!(fs::read(&journal).unwrap().last(), Some(&b'\n'));
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn incomplete_tail_is_preserved_and_refuses_future_appends() {
        let dir = test_dir("torn-tail");
        let journal = dir.join("journal");
        append_fixture(&journal, "complete").unwrap();
        let mut file = OpenOptions::new().append(true).open(&journal).unwrap();
        file.write_all(b"partial").unwrap();
        assert_eq!(
            append_record(&journal, "next").unwrap_err().kind(),
            io::ErrorKind::InvalidData
        );
        assert_eq!(fs::read(&journal).unwrap(), b"complete\npartial");
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn malformed_or_oversized_events_leave_journal_unchanged() {
        let dir = test_dir("invalid-event");
        let journal = dir.join("journal");
        append_fixture(&journal, "original").unwrap();
        for line in [
            "",
            "one\ntwo",
            "one\rtwo",
            &"x".repeat(MAX_AUDIT_RECORD_BYTES),
        ] {
            assert_eq!(
                append_record(&journal, line).unwrap_err().kind(),
                io::ErrorKind::InvalidInput
            );
        }
        assert_eq!(fs::read(&journal).unwrap(), b"original\n");
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn writer_lock_contention_refuses_without_mutation_and_recovers() {
        let dir = test_dir("locked");
        let journal = dir.join("journal");
        // Seed without a transient append lock: another parallel test may fork
        // while that descriptor is open, inheriting its flock until exec.
        fs::write(&journal, b"original\n").unwrap();
        fs::set_permissions(&journal, fs::Permissions::from_mode(0o600)).unwrap();
        let held = OpenOptions::new().append(true).open(&journal).unwrap();
        assert_eq!(
            unsafe { flock(held.as_raw_fd(), LINUX_LOCK_EX_NONBLOCK) },
            0
        );
        assert_eq!(
            append_record(&journal, "blocked").unwrap_err().kind(),
            io::ErrorKind::WouldBlock
        );
        assert_eq!(fs::read(&journal).unwrap(), b"original\n");
        // Release the shared open-file-description lock even if a concurrent
        // fork briefly inherited this descriptor before its close-on-exec.
        assert_eq!(unsafe { flock(held.as_raw_fd(), 8) }, 0);
        drop(held);
        append_fixture(&journal, "recovered").unwrap();
        assert_eq!(fs::read(&journal).unwrap(), b"original\nrecovered\n");
        fs::remove_dir_all(dir).unwrap();
    }

    fn seed_full_journal(path: &Path) -> Vec<u8> {
        let line = format!(
            "{}\n",
            record("padding", json!({"padding": "x".repeat(4096)}))
        );
        let bytes = line
            .repeat(MAX_AUDIT_BYTES as usize / line.len())
            .into_bytes();
        fs::write(path, &bytes).unwrap();
        fs::set_permissions(path, fs::Permissions::from_mode(0o600)).unwrap();
        bytes
    }

    #[test]
    fn rotation_preserves_archive_and_resumes_with_inspectable_records() {
        let dir = test_dir("rotation");
        let journal = dir.join("journal");
        let previous = seed_full_journal(&journal);
        let next = record("after_rotation", json!({"padding": "y".repeat(8192)})).to_string();
        append_fixture(&journal, &next).unwrap();
        let archive = archive_path(&journal).unwrap();
        assert_eq!(fs::read(&archive).unwrap(), previous);
        assert_eq!(fs::read_to_string(&journal).unwrap(), format!("{next}\n"));
        assert_eq!(fs::metadata(&archive).unwrap().mode() & 0o777, 0o600);
        inspect_fixture(&archive).unwrap();
        append_fixture(&journal, &record("restart", json!({})).to_string()).unwrap();
        assert_eq!(inspect_fixture(&journal).unwrap()["records"], 2);
        assert_eq!(fs::read(&archive).unwrap(), previous);
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn archive_collision_and_incomplete_tail_never_erase_evidence() {
        let dir = test_dir("archive-collision");
        let journal = dir.join("journal");
        let previous = seed_full_journal(&journal);
        let archive = archive_path(&journal).unwrap();
        fs::write(&archive, b"existing history").unwrap();
        let next = record("next", json!({"padding": "y".repeat(8192)})).to_string();
        assert_eq!(
            append_record(&journal, &next).unwrap_err().kind(),
            io::ErrorKind::AlreadyExists
        );
        assert_eq!(fs::read(&journal).unwrap(), previous);
        assert_eq!(fs::read(&archive).unwrap(), b"existing history");
        fs::remove_file(&archive).unwrap();
        let mut torn = previous.clone();
        torn.pop();
        fs::write(&journal, &torn).unwrap();
        assert_eq!(
            append_record(&journal, &next).unwrap_err().kind(),
            io::ErrorKind::InvalidData
        );
        assert!(!archive.exists());
        assert_eq!(fs::read(&journal).unwrap(), torn);
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn stable_directory_lock_blocks_readers_and_writers_without_mutation() {
        let dir = test_dir("stable-lock");
        let journal = dir.join("journal");
        let original = record("start", json!({})).to_string();
        append_fixture(&journal, &original).unwrap();
        let held = retry_fixture(|| directory_lock(&journal, true)).unwrap();
        assert_eq!(
            append_record(&journal, "blocked").unwrap_err().kind(),
            io::ErrorKind::WouldBlock
        );
        assert_eq!(
            super::super::audit_check::inspect(&journal)
                .unwrap_err()
                .kind(),
            io::ErrorKind::WouldBlock
        );
        assert_eq!(
            fs::read_to_string(&journal).unwrap(),
            format!("{original}\n")
        );
        drop(held);
        inspect_fixture(&journal).unwrap();
        let reader = retry_fixture(|| directory_lock(&journal, false)).unwrap();
        assert_eq!(
            append_record(&journal, "blocked").unwrap_err().kind(),
            io::ErrorKind::WouldBlock
        );
        drop(reader);
        let lock_path = dir.join(".audit-lock");
        fs::write(&lock_path, b"unsafe lock content").unwrap();
        assert_eq!(
            append_record(&journal, "blocked").unwrap_err().kind(),
            io::ErrorKind::PermissionDenied
        );
        assert_eq!(
            fs::read_to_string(&journal).unwrap(),
            format!("{original}\n")
        );
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn restart_after_archive_rename_creates_new_journal_without_touching_archive() {
        let dir = test_dir("rename-restart");
        let journal = dir.join("journal");
        let previous = seed_full_journal(&journal);
        preserve_archive(&journal).unwrap();
        let next = record("restart", json!({})).to_string();
        append_fixture(&journal, &next).unwrap();
        assert_eq!(fs::read(archive_path(&journal).unwrap()).unwrap(), previous);
        assert_eq!(fs::read_to_string(&journal).unwrap(), format!("{next}\n"));
        fs::remove_dir_all(dir).unwrap();
    }

    struct FaultingIo {
        fail_at: usize,
        calls: Vec<&'static str>,
        partial_write: bool,
    }

    impl FaultingIo {
        fn new(fail_at: usize) -> Self {
            Self {
                fail_at,
                calls: Vec::new(),
                partial_write: false,
            }
        }

        fn step(&mut self, operation: &'static str) -> io::Result<()> {
            self.calls.push(operation);
            if self.calls.len() == self.fail_at {
                return Err(io::Error::from_raw_os_error(5)); // Linux EIO
            }
            Ok(())
        }
    }

    impl JournalIo for FaultingIo {
        fn write(&mut self, file: &mut fs::File, bytes: &[u8]) -> io::Result<()> {
            if let Err(error) = self.step("write") {
                if self.partial_write {
                    file.write_all(&bytes[..17])?;
                }
                return Err(error);
            }
            FilesystemIo.write(file, bytes)
        }

        fn sync_file(&mut self, file: &fs::File) -> io::Result<()> {
            self.step("sync_file")?;
            FilesystemIo.sync_file(file)
        }

        fn archive(&mut self, path: &Path) -> io::Result<()> {
            self.step("archive")?;
            FilesystemIo.archive(path)
        }

        fn sync_parent(&mut self, parent: &Path, directory: &fs::Metadata) -> io::Result<()> {
            self.step("sync_parent")?;
            FilesystemIo.sync_parent(parent, directory)
        }
    }

    // Forked test processes can inherit an open flock until exec. Retry only
    // that pre-write contention for fixture operations whose intended result
    // is not lock contention.
    // Production callers and tests asserting contention still fail immediately.
    fn append_fixture(path: &Path, line: &str) -> io::Result<()> {
        retry_fixture(|| append_record(path, line))
    }

    fn retry_fixture<T>(mut operation: impl FnMut() -> io::Result<T>) -> io::Result<T> {
        for _ in 0..100 {
            match operation() {
                Err(error) if error.kind() == io::ErrorKind::WouldBlock => {
                    std::thread::sleep(std::time::Duration::from_millis(10));
                }
                result => return result,
            }
        }
        operation()
    }

    fn inspect_fixture(path: &Path) -> io::Result<Value> {
        // Parallel seat tests fork while audit descriptors can be open. A
        // child can briefly inherit their flock until exec closes the fd.
        // Wait only for WouldBlock; malformed data and all other errors fail
        // immediately. Production inspection remains strictly nonblocking.
        for _ in 0..100 {
            match super::super::audit_check::inspect(path) {
                Err(error) if error.kind() == io::ErrorKind::WouldBlock => {
                    eprintln!("[audit-fixture] waiting for inherited lock: {error}");
                    std::thread::sleep(std::time::Duration::from_millis(10));
                }
                result => return result,
            }
        }
        super::super::audit_check::inspect(path)
    }

    #[test]
    fn fixture_append_waits_for_contention_without_repeating_records() {
        let dir = test_dir("fixture-append");
        let journal = dir.join("journal");
        let first = record("original", json!({})).to_string();
        append_fixture(&journal, &first).unwrap();
        let held = directory_lock(&journal, true).unwrap().unwrap();
        let next = record("after_lock", json!({})).to_string();
        assert_eq!(
            append_record(&journal, &next).unwrap_err().kind(),
            io::ErrorKind::WouldBlock
        );
        let release = std::thread::spawn(move || {
            std::thread::sleep(std::time::Duration::from_millis(30));
            assert_eq!(unsafe { flock(held.as_raw_fd(), 8) }, 0);
        });
        append_fixture(&journal, &next).unwrap();
        release.join().unwrap();
        assert_eq!(
            fs::read_to_string(&journal).unwrap(),
            format!("{first}\n{next}\n")
        );
        assert_eq!(inspect_fixture(&journal).unwrap()["records"], 2);
        fs::write(&journal, b"partial").unwrap();
        assert_eq!(
            append_fixture(&journal, &next).unwrap_err().kind(),
            io::ErrorKind::InvalidData
        );
        assert_eq!(fs::read(&journal).unwrap(), b"partial");
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn fixture_inspection_waits_for_contention_but_rejects_invalid_data() {
        let dir = test_dir("fixture-inspection");
        let journal = dir.join("journal");
        append_fixture(&journal, &record("original", json!({})).to_string()).unwrap();
        let held = directory_lock(&journal, true).unwrap().unwrap();
        assert_eq!(
            super::super::audit_check::inspect(&journal)
                .unwrap_err()
                .kind(),
            io::ErrorKind::WouldBlock
        );
        let release = std::thread::spawn(move || {
            std::thread::sleep(std::time::Duration::from_millis(30));
            assert_eq!(unsafe { flock(held.as_raw_fd(), 8) }, 0);
        });
        assert_eq!(inspect_fixture(&journal).unwrap()["records"], 1);
        release.join().unwrap();
        fs::write(&journal, b"partial").unwrap();
        assert_eq!(
            inspect_fixture(&journal).unwrap_err().kind(),
            io::ErrorKind::InvalidData
        );
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn append_io_errors_preserve_history_report_failure_and_allow_retry() {
        let operations = ["write", "sync_file", "sync_parent"];
        for fail_at in 1..=operations.len() {
            let dir = test_dir("append-io");
            let journal = dir.join("journal");
            let original = record("original", json!({})).to_string();
            append_fixture(&journal, &original).unwrap();
            let next = record("unacknowledged", json!({})).to_string();
            let mut storage = FaultingIo::new(fail_at);
            let error = append_record_with_io(&journal, &next, &mut storage).unwrap_err();
            assert_eq!(error.raw_os_error(), Some(5));
            assert_eq!(storage.calls, operations[..fail_at]);
            // A failed sync can leave a complete but unacknowledged record.
            let expected = if fail_at == 1 {
                format!("{original}\n")
            } else {
                format!("{original}\n{next}\n")
            };
            assert_eq!(fs::read_to_string(&journal).unwrap(), expected);
            assert!(!archive_path(&journal).unwrap().exists());
            let retry = record("retry", json!({})).to_string();
            append_fixture(&journal, &retry).unwrap();
            assert_eq!(
                fs::read_to_string(&journal).unwrap(),
                format!("{expected}{retry}\n")
            );
            inspect_fixture(&journal).unwrap();
            fs::remove_dir_all(dir).unwrap();
        }
    }

    #[test]
    fn rotation_io_errors_preserve_all_history_and_recover_without_overwrite() {
        let operations = [
            "sync_file",
            "archive",
            "sync_parent",
            "write",
            "sync_file",
            "sync_parent",
        ];
        for fail_at in 1..=operations.len() {
            let dir = test_dir("rotation-io");
            let journal = dir.join("journal");
            let previous = seed_full_journal(&journal);
            let original_inode = fs::metadata(&journal).unwrap().ino();
            let archive = archive_path(&journal).unwrap();
            let next = record("next", json!({"padding": "y".repeat(8192)})).to_string();
            let mut storage = FaultingIo::new(fail_at);
            let error = append_record_with_io(&journal, &next, &mut storage).unwrap_err();
            assert_eq!(error.raw_os_error(), Some(5));
            assert_eq!(storage.calls, operations[..fail_at]);
            if fail_at <= 2 {
                assert_eq!(fs::read(&journal).unwrap(), previous);
                assert!(!archive.exists());
            } else {
                assert_eq!(fs::read(&archive).unwrap(), previous);
                if fail_at == 3 {
                    assert!(!journal.exists());
                } else {
                    let expected = if fail_at == 4 {
                        String::new()
                    } else {
                        format!("{next}\n")
                    };
                    assert_eq!(fs::read_to_string(&journal).unwrap(), expected);
                }
            }
            // Use a new event: a returned error does not imply zero bytes wrote
            // and does not grant exactly-once semantics to an automatic retry.
            let retry = record("retry", json!({"padding": "z".repeat(8192)})).to_string();
            append_fixture(&journal, &retry).unwrap();
            assert_eq!(fs::read(&archive).unwrap(), previous);
            assert_eq!(fs::metadata(&archive).unwrap().ino(), original_inode);
            let expected = if fail_at >= 5 {
                format!("{next}\n{retry}\n")
            } else {
                format!("{retry}\n")
            };
            assert_eq!(fs::read_to_string(&journal).unwrap(), expected);
            inspect_fixture(&archive).unwrap();
            inspect_fixture(&journal).unwrap();
            fs::remove_dir_all(dir).unwrap();
        }
    }

    #[test]
    fn partial_write_error_preserves_tail_and_refuses_retry_without_touching_archive() {
        let dir = test_dir("partial-write-io");
        let journal = dir.join("journal");
        let original = record("original", json!({})).to_string();
        append_fixture(&journal, &original).unwrap();
        let archive = archive_path(&journal).unwrap();
        fs::write(&archive, b"retained history\n").unwrap();
        fs::set_permissions(&archive, fs::Permissions::from_mode(0o600)).unwrap();
        let next = record("partial", json!({})).to_string();
        let mut storage = FaultingIo::new(1);
        storage.partial_write = true;
        assert_eq!(
            retry_fixture(|| append_record_with_io(&journal, &next, &mut storage))
                .unwrap_err()
                .raw_os_error(),
            Some(5)
        );
        let expected = format!("{original}\n{}", &next[..17]);
        assert_eq!(fs::read_to_string(&journal).unwrap(), expected);
        assert_eq!(
            retry_fixture(|| append_record(&journal, "retry"))
                .unwrap_err()
                .kind(),
            io::ErrorKind::InvalidData
        );
        assert_eq!(fs::read_to_string(&journal).unwrap(), expected);
        assert_eq!(fs::read(&archive).unwrap(), b"retained history\n");
        assert_eq!(
            inspect_fixture(&journal).unwrap_err().kind(),
            io::ErrorKind::InvalidData
        );
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn partial_write_after_rotation_preserves_archive_and_refuses_incomplete_active() {
        let dir = test_dir("rotation-partial-io");
        let journal = dir.join("journal");
        let previous = seed_full_journal(&journal);
        let archive = archive_path(&journal).unwrap();
        let next = record("partial", json!({"padding": "y".repeat(8192)})).to_string();
        let mut storage = FaultingIo::new(4);
        storage.partial_write = true;
        assert_eq!(
            append_record_with_io(&journal, &next, &mut storage)
                .unwrap_err()
                .raw_os_error(),
            Some(5)
        );
        assert_eq!(fs::read(&archive).unwrap(), previous);
        assert_eq!(fs::read(&journal).unwrap(), next.as_bytes()[..17]);
        assert_eq!(
            append_record(&journal, "retry").unwrap_err().kind(),
            io::ErrorKind::InvalidData
        );
        assert_eq!(fs::read(&archive).unwrap(), previous);
        assert_eq!(fs::read(&journal).unwrap(), next.as_bytes()[..17]);
        inspect_fixture(&archive).unwrap();
        assert_eq!(
            inspect_fixture(&journal).unwrap_err().kind(),
            io::ErrorKind::InvalidData
        );
        fs::remove_dir_all(dir).unwrap();
    }

    struct ReplacedActiveIo {
        journal: PathBuf,
        target: PathBuf,
        kind: &'static str,
        installed: bool,
        installed_inode: Option<u64>,
        writes: usize,
    }

    impl JournalIo for ReplacedActiveIo {
        fn sync_parent(&mut self, parent: &Path, directory: &fs::Metadata) -> io::Result<()> {
            FilesystemIo.sync_parent(parent, directory)?;
            assert!(!self.installed);
            assert!(archive_path(&self.journal)?.exists());
            assert!(!self.journal.exists());
            match self.kind {
                "symlink" => std::os::unix::fs::symlink(&self.target, &self.journal)?,
                "hardlink" => fs::hard_link(&self.target, &self.journal)?,
                "directory" => fs::create_dir(&self.journal)?,
                "fifo" => {
                    unsafe extern "C" {
                        fn mkfifo(path: *const c_char, mode: u32) -> i32;
                    }
                    let path = CString::new(self.journal.as_os_str().as_bytes()).unwrap();
                    if unsafe { mkfifo(path.as_ptr(), 0o600) } != 0 {
                        return Err(io::Error::last_os_error());
                    }
                }
                _ => unreachable!(),
            }
            self.installed_inode = Some(fs::symlink_metadata(&self.journal)?.ino());
            self.installed = true;
            Ok(())
        }

        fn write(&mut self, file: &mut fs::File, bytes: &[u8]) -> io::Result<()> {
            self.writes += 1;
            FilesystemIo.write(file, bytes)
        }
    }

    #[test]
    fn unsafe_active_replacement_after_rotation_preserves_archive_and_other_file() {
        for kind in ["symlink", "hardlink", "directory", "fifo"] {
            let dir = test_dir("rotation-replacement");
            let journal = dir.join("journal");
            let previous = seed_full_journal(&journal);
            let original_inode = fs::metadata(&journal).unwrap().ino();
            let archive = archive_path(&journal).unwrap();
            let target = dir.join("unrelated");
            fs::write(&target, b"unrelated private data\n").unwrap();
            fs::set_permissions(&target, fs::Permissions::from_mode(0o600)).unwrap();
            let target_inode = fs::metadata(&target).unwrap().ino();
            let mut storage = ReplacedActiveIo {
                journal: journal.clone(),
                target: target.clone(),
                kind,
                installed: false,
                installed_inode: None,
                writes: 0,
            };
            let next = record("next", json!({"padding": "y".repeat(8192)})).to_string();
            assert!(append_record_with_io(&journal, &next, &mut storage).is_err());
            assert!(
                storage.installed,
                "replacement boundary was not reached: {kind}"
            );
            assert_eq!(storage.writes, 0, "attempted write through {kind}");
            let refused = fs::symlink_metadata(&journal).unwrap();
            assert_eq!(refused.ino(), storage.installed_inode.unwrap());
            match kind {
                "symlink" => {
                    assert!(refused.file_type().is_symlink());
                    assert_eq!(fs::read_link(&journal).unwrap(), target);
                }
                "hardlink" => {
                    assert!(refused.is_file());
                    assert_eq!(refused.ino(), target_inode);
                    assert_eq!(refused.nlink(), 2);
                }
                "directory" => assert!(refused.is_dir()),
                "fifo" => {
                    use std::os::unix::fs::FileTypeExt;
                    assert!(refused.file_type().is_fifo());
                }
                _ => unreachable!(),
            }
            assert_eq!(fs::read(&target).unwrap(), b"unrelated private data\n");
            assert_eq!(fs::metadata(&target).unwrap().ino(), target_inode);
            assert_eq!(fs::read(&archive).unwrap(), previous);
            assert_eq!(fs::metadata(&archive).unwrap().ino(), original_inode);
            inspect_fixture(&archive).unwrap();
            // Only the fixture operator removes its injected object. The
            // audit writer itself must never unlink or repair that path.
            if kind == "directory" {
                fs::remove_dir(&journal).unwrap();
            } else {
                fs::remove_file(&journal).unwrap();
            }
            append_fixture(&journal, &next).unwrap();
            assert_eq!(fs::read_to_string(&journal).unwrap(), format!("{next}\n"));
            assert_eq!(fs::read(&archive).unwrap(), previous);
            assert_eq!(fs::metadata(&archive).unwrap().ino(), original_inode);
            assert_eq!(fs::read(&target).unwrap(), b"unrelated private data\n");
            assert_eq!(fs::metadata(&target).unwrap().nlink(), 1);
            inspect_fixture(&journal).unwrap();
            fs::remove_dir_all(dir).unwrap();
        }
    }

    fn kill_crash_worker() -> ! {
        unsafe extern "C" {
            fn raise(signal: i32) -> i32;
        }
        // SIGKILL runs no Rust destructors or graceful audit shutdown.
        unsafe { raise(9) };
        panic!("crash worker survived SIGKILL");
    }

    const CRASH_PHASES: [&str; 7] = [
        "renamed",
        "directory-synced",
        "empty-active",
        "partial-active",
        "written",
        "file-synced",
        "append-synced",
    ];

    struct ProcessCrashIo {
        phase: String,
        parent_syncs: usize,
        wrote: bool,
    }

    impl JournalIo for ProcessCrashIo {
        fn archive(&mut self, path: &Path) -> io::Result<()> {
            FilesystemIo.archive(path)?;
            if self.phase == "renamed" {
                kill_crash_worker();
            }
            Ok(())
        }

        fn sync_parent(&mut self, parent: &Path, directory: &fs::Metadata) -> io::Result<()> {
            FilesystemIo.sync_parent(parent, directory)?;
            self.parent_syncs += 1;
            if self.parent_syncs == 1 && self.phase == "directory-synced" {
                kill_crash_worker();
            }
            if self.wrote && self.phase == "append-synced" {
                kill_crash_worker();
            }
            Ok(())
        }

        fn sync_file(&mut self, file: &fs::File) -> io::Result<()> {
            FilesystemIo.sync_file(file)?;
            if self.wrote && self.phase == "file-synced" {
                kill_crash_worker();
            }
            Ok(())
        }

        fn write(&mut self, file: &mut fs::File, bytes: &[u8]) -> io::Result<()> {
            if self.phase == "empty-active" {
                kill_crash_worker();
            }
            if self.phase == "partial-active" {
                file.write_all(&bytes[..17])?;
                kill_crash_worker();
            }
            FilesystemIo.write(file, bytes)?;
            self.wrote = true;
            if self.phase == "written" {
                kill_crash_worker();
            }
            Ok(())
        }
    }

    #[test]
    fn process_crash_worker() {
        // Entry point only in the test executable; no production fault flags.
        let Some(root) = std::env::var_os("SYNVEIL_TEST_CRASH_ROOT") else {
            return;
        };
        let root = PathBuf::from(root);
        assert_eq!(root.parent().unwrap(), std::env::temp_dir());
        assert!(root
            .file_name()
            .unwrap()
            .to_str()
            .unwrap()
            .starts_with("synveil-audit-process-crash-"));
        let metadata = fs::symlink_metadata(&root).unwrap();
        assert!(metadata.is_dir());
        assert_eq!(metadata.mode() & 0o777, 0o700);
        let phase = std::env::var("SYNVEIL_TEST_CRASH_PHASE").unwrap();
        assert!(CRASH_PHASES.contains(&phase.as_str()));
        let next = std::env::var("SYNVEIL_TEST_CRASH_RECORD").unwrap();
        let mut storage = ProcessCrashIo {
            phase,
            parent_syncs: 0,
            wrote: false,
        };
        append_record_with_io(&root.join("journal"), &next, &mut storage).unwrap();
        panic!("crash boundary was not reached");
    }

    fn run_crash_worker(dir: &Path, phase: &str, next: &str) {
        use std::os::unix::process::ExitStatusExt;
        use std::process::{Command, Stdio};
        use std::time::{Duration, Instant};

        let mut child = Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "audit::tests::process_crash_worker",
                "--test-threads=1",
            ])
            .env("SYNVEIL_TEST_CRASH_ROOT", dir)
            .env("SYNVEIL_TEST_CRASH_PHASE", phase)
            .env("SYNVEIL_TEST_CRASH_RECORD", next)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        let deadline = Instant::now() + Duration::from_secs(5);
        let status = loop {
            if let Some(status) = child.try_wait().unwrap() {
                break status;
            }
            if Instant::now() >= deadline {
                child.kill().unwrap();
                child.wait().unwrap();
                panic!("crash worker timed out at {phase}");
            }
            std::thread::sleep(Duration::from_millis(10));
        };
        let mut diagnostic = String::new();
        child
            .stderr
            .take()
            .unwrap()
            .read_to_string(&mut diagnostic)
            .unwrap();
        assert_eq!(status.signal(), Some(9), "{phase}: {diagnostic}");
    }

    #[test]
    fn process_loss_during_rotation_preserves_history_and_releases_locks() {
        for phase in CRASH_PHASES {
            let dir = test_dir("process-crash");
            fs::set_permissions(&dir, fs::Permissions::from_mode(0o700)).unwrap();
            let journal = dir.join("journal");
            let previous = seed_full_journal(&journal);
            let original_inode = fs::metadata(&journal).unwrap().ino();
            // Establish a synchronized seed before the child starts. No sync
            // or cleanup follows the child's interrupted operations.
            fs::File::open(&journal).unwrap().sync_all().unwrap();
            sync_directory(&dir, &fs::metadata(&dir).unwrap()).unwrap();
            let next = record("interrupted", json!({"padding": "y".repeat(8192)})).to_string();
            run_crash_worker(&dir, phase, &next);
            let archive = archive_path(&journal).unwrap();
            assert_eq!(fs::read(&archive).unwrap(), previous);
            assert_eq!(fs::metadata(&archive).unwrap().ino(), original_inode);
            // A killed child must not leave either advisory lock held.
            inspect_fixture(&archive).unwrap();
            if phase == "renamed" || phase == "directory-synced" {
                assert!(!journal.exists());
            } else if phase == "empty-active" {
                assert!(fs::read(&journal).unwrap().is_empty());
            } else if phase == "partial-active" {
                assert_eq!(fs::read(&journal).unwrap(), next.as_bytes()[..17]);
                assert_eq!(
                    inspect_fixture(&journal).unwrap_err().kind(),
                    io::ErrorKind::InvalidData
                );
            } else {
                assert_eq!(fs::read_to_string(&journal).unwrap(), format!("{next}\n"));
                assert_eq!(inspect_fixture(&journal).unwrap()["records"], 1);
            }
            let retry = record("restart", json!({})).to_string();
            if phase == "partial-active" {
                assert_eq!(
                    append_record(&journal, &retry).unwrap_err().kind(),
                    io::ErrorKind::InvalidData
                );
                assert_eq!(fs::read(&journal).unwrap(), next.as_bytes()[..17]);
            } else {
                append_fixture(&journal, &retry).unwrap();
                let expected = if ["written", "file-synced", "append-synced"].contains(&phase) {
                    format!("{next}\n{retry}\n")
                } else {
                    format!("{retry}\n")
                };
                assert_eq!(fs::read_to_string(&journal).unwrap(), expected);
                inspect_fixture(&journal).unwrap();
            }
            assert_eq!(fs::read(&archive).unwrap(), previous);
            assert_eq!(fs::metadata(&archive).unwrap().ino(), original_inode);
            fs::remove_dir_all(dir).unwrap();
        }
    }

    #[test]
    fn process_loss_during_first_or_existing_append_preserves_unacknowledged_bytes() {
        for existing in [false, true] {
            for phase in &CRASH_PHASES[2..] {
                let dir = test_dir("process-crash");
                fs::set_permissions(&dir, fs::Permissions::from_mode(0o700)).unwrap();
                let journal = dir.join("journal");
                let original = record("original", json!({})).to_string();
                let previous = if existing {
                    append_fixture(&journal, &original).unwrap();
                    format!("{original}\n")
                } else {
                    String::new()
                };
                let original_inode = fs::metadata(&journal).ok().map(|meta| meta.ino());
                sync_directory(&dir, &fs::metadata(&dir).unwrap()).unwrap();
                let next = record("unacknowledged", json!({})).to_string();
                run_crash_worker(&dir, phase, &next);
                let suffix = match *phase {
                    "empty-active" => String::new(),
                    "partial-active" => next[..17].to_string(),
                    _ => format!("{next}\n"),
                };
                let expected = format!("{previous}{suffix}");
                assert_eq!(fs::read_to_string(&journal).unwrap(), expected);
                assert!(!archive_path(&journal).unwrap().exists());
                let metadata = fs::metadata(&journal).unwrap();
                assert_eq!(metadata.mode() & 0o777, 0o600);
                assert_eq!(metadata.nlink(), 1);
                if let Some(inode) = original_inode {
                    assert_eq!(metadata.ino(), inode);
                }
                let retry = record("restart", json!({})).to_string();
                if *phase == "partial-active" {
                    assert_eq!(
                        inspect_fixture(&journal).unwrap_err().kind(),
                        io::ErrorKind::InvalidData
                    );
                    assert_eq!(
                        append_record(&journal, &retry).unwrap_err().kind(),
                        io::ErrorKind::InvalidData
                    );
                    assert_eq!(fs::read_to_string(&journal).unwrap(), expected);
                } else {
                    // A distinct restart event preserves a complete record
                    // even though its caller never received acknowledgement.
                    append_fixture(&journal, &retry).unwrap();
                    assert_eq!(
                        fs::read_to_string(&journal).unwrap(),
                        format!("{expected}{retry}\n")
                    );
                    let records = usize::from(existing) + usize::from(!suffix.is_empty()) + 1;
                    assert_eq!(inspect_fixture(&journal).unwrap()["records"], records);
                }
                assert_eq!(fs::metadata(&journal).unwrap().ino(), metadata.ino());
                assert!(!archive_path(&journal).unwrap().exists());
                fs::remove_dir_all(dir).unwrap();
            }
        }
    }

    #[test]
    fn verified_archive_release_allows_next_rotation_without_losing_copy() {
        let dir = test_dir("retention-recovery");
        fs::set_permissions(&dir, fs::Permissions::from_mode(0o700)).unwrap();
        let journal = dir.join("journal");
        let old = seed_full_journal(&journal);
        let next = record("after_rotation", json!({"padding": "y".repeat(8192)})).to_string();
        append_fixture(&journal, &next).unwrap();
        let copies = dir.join("copies");
        fs::create_dir(&copies).unwrap();
        fs::set_permissions(&copies, fs::Permissions::from_mode(0o700)).unwrap();
        let archive = archive_path(&journal).unwrap();
        let snapshot = copies.join("snapshot");
        let exported =
            retry_fixture(|| super::super::audit_export::export(&archive, &snapshot)).unwrap();
        retry_fixture(|| {
            super::super::audit_retention::release_archive(
                &journal,
                &snapshot,
                &copies.join("release.json"),
                exported["digest"].as_str().unwrap(),
            )
        })
        .unwrap();
        assert!(!archive.exists());
        assert_eq!(fs::read(&snapshot).unwrap(), old);
        let newer = seed_full_journal(&journal);
        append_fixture(&journal, &next).unwrap();
        assert_eq!(fs::read(&archive).unwrap(), newer);
        assert_eq!(fs::read(&snapshot).unwrap(), old);
        assert_eq!(fs::read_to_string(&journal).unwrap(), format!("{next}\n"));
        inspect_fixture(&journal).unwrap();
        inspect_fixture(&archive).unwrap();
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn unsafe_lock_objects_cannot_modify_journal_or_link_target() {
        let dir = test_dir("unsafe-lock");
        let journal = dir.join("journal");
        append_fixture(&journal, "original").unwrap();
        let lock = dir.join(".audit-lock");
        fs::remove_file(&lock).unwrap();
        let target = dir.join("target");
        fs::write(&target, b"private target").unwrap();
        fs::set_permissions(&target, fs::Permissions::from_mode(0o600)).unwrap();
        std::os::unix::fs::symlink(&target, &lock).unwrap();
        assert!(append_record(&journal, "blocked").is_err());
        fs::remove_file(&lock).unwrap();
        fs::hard_link(&target, &lock).unwrap();
        assert!(append_record(&journal, "blocked").is_err());
        fs::remove_file(&lock).unwrap();
        fs::write(&lock, b"").unwrap();
        fs::set_permissions(&lock, fs::Permissions::from_mode(0o644)).unwrap();
        assert!(append_record(&journal, "blocked").is_err());
        fs::remove_file(&lock).unwrap();
        assert!(std::process::Command::new("mkfifo")
            .arg(&lock)
            .status()
            .unwrap()
            .success());
        assert!(append_record(&journal, "blocked").is_err());
        assert_eq!(fs::read(&journal).unwrap(), b"original\n");
        assert_eq!(fs::read(&target).unwrap(), b"private target");
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn untrusted_fields_cannot_inject_record_lines() {
        let value = record("request", json!({ "id": "one\ntwo\r\nthree" }));
        let encoded = serde_json::to_string(&value).unwrap();
        assert!(!encoded.contains('\n') && !encoded.contains('\r'));
        assert_eq!(serde_json::from_str::<Value>(&encoded).unwrap(), value);
    }
}
