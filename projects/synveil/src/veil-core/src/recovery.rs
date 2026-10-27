// SPDX-License-Identifier: MPL-2.0
//! ADR 0010 tier 4 recovery factor — Option A as approved in
//! ADR 0020: a printed 256-bit recovery key whose verifier record is
//! an Argon2id PHC record (ADR 0009 discipline) in a separate slot of
//! the credential store, bound to this installation by a
//! domain-separated verifier input and an anchor in the installation
//! control metadata outside the credential directory
//! (`docs/RECOVERY_FACTOR_SPEC.md` sections 4.1 and 8).
//!
//! The factor itself is never written to any file. The record holds
//! only the PHC string, a generation counter, the installation
//! identifier, a persistent failed-attempt counter, and timestamps.
//! The anchor holds only the installation identifier — no hash, so
//! the anchor alone can never verify a factor.
//!
//! Anchor mechanism chosen under decision D8, and its limits: the
//! anchor is a separate strict record file in `/var/lib/synveil/`
//! beside `ab-control.json` — the same class of storage that holds
//! A/B update control state — under the same file discipline as the
//! credential store (root-owned mode-0700 directory, mode-0600
//! single-link file, symlinks refused). This is a placement and
//! file-discipline mechanism, not a cryptographic integrity proof:
//! it defeats transplantation of a record to another installation
//! and presentation of a copied credential directory alone, because
//! both disagree with the anchor or lack it. It does not defeat an
//! attacker who can rewrite both the credential store and the anchor
//! with self-consistent values; that remains the separately reviewed
//! anchor-integrity problem ADR 0010 reserves, and ultimately the
//! verified-boot gates. Nothing here claims otherwise.

use std::fs::{self, OpenOptions};
use std::io::{self, Read, Write};
use std::os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt};
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::credential::{
    LOCAL_ACCOUNT, has_persistent_state, hash_input_phc, valid_phc_format, verify_input_phc,
    write_record_atomically,
};
use crate::secret;
use crate::sha256::sha256;

pub const RECOVERY_RECORD_PATH: &str = "/var/lib/synveil/auth/recovery.json";
pub const ANCHOR_PATH: &str = "/var/lib/synveil/installation-anchor.json";
/// Same audit store the tier-2 maintenance console writes; the
/// recovery flows append their own event names (specification
/// section 10). Entries never contain secret material.
pub const AUDIT_LOG_PATH: &str = "/var/log/synveil/recovery-maintenance.log";

const RECORD_SCHEMA: &str = "synveil.recovery-record/v1";
const ANCHOR_SCHEMA: &str = "synveil.installation-anchor/v1";
const BINDING_DOMAIN: &[u8] = b"synveil-recovery-v1";
const STATE_BASE: &str = "/var/lib/synveil";
const RECORD_NAME: &str = "recovery.json";
const ANCHOR_NAME: &str = "installation-anchor.json";

pub const FACTOR_BYTES: usize = 32;
/// Persistent failed-verification threshold: at this many recorded
/// failures the reset flow refuses until the factor is rotated under
/// normal authentication. Transcription errors never count
/// (specification section 4.1).
pub const MAX_FAILED_ATTEMPTS: u32 = 5;
/// 0-based index of the designated middle group among the thirteen
/// key groups; the owner re-enters it, with the check group, to
/// confirm recording at enrollment (decision D4).
pub const MIDDLE_GROUP_INDEX: usize = 6;

const MAX_RECORD_BYTES: usize = 2048;
const MAX_ANCHOR_BYTES: usize = 512;
const LINUX_O_NOFOLLOW: i32 = 0o400000;
const LINUX_O_NONBLOCK: i32 = 0o4000;

const CROCKFORD: &[u8; 32] = b"0123456789ABCDEFGHJKMNPQRSTVWXYZ";

// ---------------------------------------------------------------------
// Factor encoding (specification sections 4.1 and 6, decision D2)
// ---------------------------------------------------------------------

/// The one-time display form of a generated factor: fourteen groups
/// of four Crockford Base32 characters — thirteen groups encoding
/// the 256-bit key, plus the non-secret check group.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FactorDisplay {
    pub grouped: String,
    pub check_group: String,
    pub middle_group: String,
}

/// A freshly generated factor. The key bytes live only in memory and
/// are cleared by the caller as soon as the record is committed.
pub struct GeneratedFactor {
    pub key: [u8; FACTOR_BYTES],
    pub display: FactorDisplay,
}

impl GeneratedFactor {
    pub fn clear(&mut self) {
        secret::clear(&mut self.key);
    }
}

fn check_group(key: &[u8; FACTOR_BYTES]) -> String {
    // Non-secret transcription checksum: the first 20 bits of the
    // key's SHA-256 digest, as four Crockford characters. Error
    // detection only; it contributes no entropy, and it is never
    // stored anywhere.
    let digest = sha256(key);
    let value: u32 =
        ((digest[0] as u32) << 12) | ((digest[1] as u32) << 4) | ((digest[2] as u32) >> 4);
    let mut out = String::with_capacity(4);
    for shift in [15, 10, 5, 0] {
        out.push(CROCKFORD[((value >> shift) & 0x1f) as usize] as char);
    }
    out
}

pub fn encode_factor(key: &[u8; FACTOR_BYTES]) -> FactorDisplay {
    let mut chars: Vec<u8> = Vec::with_capacity(52);
    let mut acc: u32 = 0;
    let mut nbits: u32 = 0;
    for &byte in key.iter() {
        acc = (acc << 8) | u32::from(byte);
        nbits += 8;
        while nbits >= 5 {
            nbits -= 5;
            chars.push(CROCKFORD[((acc >> nbits) & 0x1f) as usize]);
        }
        acc &= (1u32 << nbits) - 1;
    }
    if nbits > 0 {
        // 256 = 51*5 + 1: the 52nd character carries the final bit in
        // its high position; its low four bits are zero padding.
        chars.push(CROCKFORD[((acc << (5 - nbits)) & 0x1f) as usize]);
    }
    debug_assert_eq!(chars.len(), 52);
    let mut groups: Vec<String> = chars
        .chunks(4)
        .map(|chunk| String::from_utf8(chunk.to_vec()).expect("alphabet is ASCII"))
        .collect();
    let middle_group = groups[MIDDLE_GROUP_INDEX].clone();
    let check = check_group(key);
    groups.push(check.clone());
    FactorDisplay {
        grouped: groups.join("-"),
        check_group: check,
        middle_group,
    }
}

fn crockford_value(byte: u8) -> Option<u32> {
    CROCKFORD
        .iter()
        .position(|&symbol| symbol == byte)
        .map(|index| index as u32)
}

/// Outcome of parsing an owner-entered factor.
#[derive(Debug)]
pub enum FactorParse {
    /// A complete factor whose check group matches its key.
    Key([u8; FACTOR_BYTES]),
    /// The structure is right but the check group does not match the
    /// decoded key: a transcription slip, not a guess. The reset
    /// flow rejects it without consuming an attempt and without
    /// running the verifier.
    Transcription,
    /// Anything else: wrong length, characters outside the
    /// alphabet, or non-canonical padding bits.
    Malformed,
}

pub fn parse_entered_factor(text: &[u8]) -> FactorParse {
    let Ok(text) = std::str::from_utf8(text) else {
        return FactorParse::Malformed;
    };
    let cleaned: Vec<u8> = text
        .bytes()
        .filter(|byte| !matches!(byte, b'-' | b' ' | b'\t'))
        .map(|byte| byte.to_ascii_uppercase())
        .collect();
    if cleaned.len() != 56 {
        return FactorParse::Malformed;
    }
    let (key_chars, check_chars) = cleaned.split_at(52);
    let mut key = [0u8; FACTOR_BYTES];
    if !decode_key_chars(key_chars, &mut key) {
        return FactorParse::Malformed;
    }
    if check_chars != check_group(&key).as_bytes() {
        return FactorParse::Transcription;
    }
    FactorParse::Key(key)
}

fn decode_key_chars(chars: &[u8], key: &mut [u8; FACTOR_BYTES]) -> bool {
    if chars.len() != 52 {
        return false;
    }
    let mut acc: u32 = 0;
    let mut nbits: u32 = 0;
    let mut out = 0usize;
    for (index, &symbol) in chars.iter().enumerate() {
        let Some(value) = crockford_value(symbol) else {
            return false;
        };
        // The final character carries one key bit; its low four bits
        // are padding and must be zero, so each key has exactly one
        // canonical encoding.
        if index == 51 && value & 0x0f != 0 {
            return false;
        }
        acc = (acc << 5) | value;
        nbits += 5;
        if nbits >= 8 {
            nbits -= 8;
            key[out] = ((acc >> nbits) & 0xff) as u8;
            out += 1;
            acc &= (1u32 << nbits) - 1;
        }
    }
    out == FACTOR_BYTES
}

pub fn generate_factor() -> io::Result<GeneratedFactor> {
    let mut key = [0u8; FACTOR_BYTES];
    fs::File::open("/dev/urandom")?.read_exact(&mut key)?;
    let display = encode_factor(&key);
    Ok(GeneratedFactor { key, display })
}

// ---------------------------------------------------------------------
// Records (specification sections 2, 4.1 and 8)
// ---------------------------------------------------------------------

/// A strictly validated recovery record.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RecoveryRecord {
    pub generation: u64,
    pub installation_id: [u8; FACTOR_BYTES],
    pub failed_attempts: u32,
    pub enrolled_unix: u64,
    pub updated_unix: u64,
    /// The Argon2id PHC string; empty exactly when `revoked`.
    pub phc: String,
    pub revoked: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RecoveryFactorState {
    /// No designated state partition is mounted at /var.
    NoState,
    /// No recovery record exists (never enrolled, or declined).
    Absent,
    /// Something exists at the record path but strict loading
    /// rejected it (corrupt, wrong ownership/mode, symlink, extra
    /// link). Every flow treats it exactly as a denial.
    Invalid,
    /// The factor was revoked (used in a reset, or rotated away)
    /// and no new factor has been enrolled since.
    Revoked { generation: u64 },
    /// A factor is enrolled and can be presented in the reset flow.
    Active {
        generation: u64,
        enrolled_unix: u64,
        failed_attempts: u32,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AnchorState {
    NoState,
    Absent,
    Invalid,
    Present([u8; FACTOR_BYTES]),
}

enum Loaded<T> {
    Absent,
    Invalid,
    Value(T),
}

fn unsafe_path() -> io::Error {
    io::Error::new(
        io::ErrorKind::PermissionDenied,
        "untrusted recovery storage",
    )
}

fn private_directory(dir: &Path, uid: u32) -> bool {
    fs::symlink_metadata(dir).is_ok_and(|meta| {
        meta.file_type().is_dir() && meta.uid() == uid && meta.permissions().mode() & 0o777 == 0o700
    })
}

/// Strict record read with the credential store's discipline: the
/// parent directory (and, for records inside it, the credential
/// directory's parent) must be root-owned mode 0700; the file must be
/// a regular, owner-only, single-link file, opened without following
/// symlinks, and size-capped.
fn read_strict_file(
    path: &Path,
    uid: u32,
    max_bytes: usize,
    check_parent: bool,
) -> Option<Vec<u8>> {
    let dir = path.parent()?;
    if !private_directory(dir, uid) {
        return None;
    }
    if check_parent && !private_directory(dir.parent()?, uid) {
        return None;
    }
    let file = OpenOptions::new()
        .read(true)
        .custom_flags(LINUX_O_NOFOLLOW | LINUX_O_NONBLOCK)
        .open(path)
        .ok()?;
    let meta = file.metadata().ok()?;
    if !meta.file_type().is_file()
        || meta.uid() != uid
        || meta.permissions().mode() & 0o777 != 0o600
        || meta.nlink() != 1
    {
        return None;
    }
    let mut bytes = Vec::new();
    file.take((max_bytes + 1) as u64)
        .read_to_end(&mut bytes)
        .ok()?;
    if bytes.len() > max_bytes {
        return None;
    }
    Some(bytes)
}

fn hex_encode(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        out.push_str(&format!("{byte:02x}"));
    }
    out
}

fn hex_decode_32(text: &str) -> Option<[u8; FACTOR_BYTES]> {
    if text.len() != 64
        || !text
            .bytes()
            .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
    {
        return None;
    }
    let mut out = [0u8; FACTOR_BYTES];
    for (index, slot) in out.iter_mut().enumerate() {
        *slot = u8::from_str_radix(&text[2 * index..2 * index + 2], 16).ok()?;
    }
    Some(out)
}

fn exact_keys(value: &serde_json::Value, expected: &[&str]) -> bool {
    let Some(object) = value.as_object() else {
        return false;
    };
    object.len() == expected.len() && expected.iter().all(|key| object.contains_key(*key))
}

fn parse_record(bytes: &[u8]) -> Option<RecoveryRecord> {
    let value: serde_json::Value = serde_json::from_slice(bytes).ok()?;
    if !exact_keys(
        &value,
        &[
            "schema",
            "state",
            "phc",
            "generation",
            "installation_id",
            "failed_attempts",
            "enrolled_unix",
            "updated_unix",
        ],
    ) {
        return None;
    }
    if value.get("schema")?.as_str()? != RECORD_SCHEMA {
        return None;
    }
    let state = value.get("state")?.as_str()?;
    let phc = value.get("phc")?.as_str()?;
    let generation = value.get("generation")?.as_u64()?;
    let installation_id = hex_decode_32(value.get("installation_id")?.as_str()?)?;
    let failed_attempts = u32::try_from(value.get("failed_attempts")?.as_u64()?).ok()?;
    let enrolled_unix = value.get("enrolled_unix")?.as_u64()?;
    let updated_unix = value.get("updated_unix")?.as_u64()?;
    if generation == 0 || failed_attempts > 1_000_000 {
        return None;
    }
    let revoked = match state {
        "active" => {
            if !valid_phc_format(phc) {
                return None;
            }
            false
        }
        "revoked" => {
            if !phc.is_empty() {
                return None;
            }
            true
        }
        _ => return None,
    };
    Some(RecoveryRecord {
        generation,
        installation_id,
        failed_attempts,
        enrolled_unix,
        updated_unix,
        phc: phc.to_string(),
        revoked,
    })
}

fn record_json(record: &RecoveryRecord) -> String {
    format!(
        "{{\"schema\":\"{RECORD_SCHEMA}\",\"state\":\"{}\",\"phc\":\"{}\",\
         \"generation\":{},\"installation_id\":\"{}\",\"failed_attempts\":{},\
         \"enrolled_unix\":{},\"updated_unix\":{}}}\n",
        if record.revoked { "revoked" } else { "active" },
        record.phc,
        record.generation,
        hex_encode(&record.installation_id),
        record.failed_attempts,
        record.enrolled_unix,
        record.updated_unix,
    )
}

fn load_record_at(base: &Path, uid: u32) -> Loaded<RecoveryRecord> {
    let path = base.join("auth").join(RECORD_NAME);
    match read_strict_file(&path, uid, MAX_RECORD_BYTES, true) {
        Some(bytes) => match parse_record(&bytes) {
            Some(record) => Loaded::Value(record),
            None => Loaded::Invalid,
        },
        None => {
            if fs::symlink_metadata(&path).is_ok() {
                Loaded::Invalid
            } else {
                Loaded::Absent
            }
        }
    }
}

fn factor_state_at(base: &Path, uid: u32) -> RecoveryFactorState {
    match load_record_at(base, uid) {
        Loaded::Value(record) => {
            if record.revoked {
                RecoveryFactorState::Revoked {
                    generation: record.generation,
                }
            } else {
                RecoveryFactorState::Active {
                    generation: record.generation,
                    enrolled_unix: record.enrolled_unix,
                    failed_attempts: record.failed_attempts,
                }
            }
        }
        Loaded::Invalid => RecoveryFactorState::Invalid,
        Loaded::Absent => RecoveryFactorState::Absent,
    }
}

fn parse_anchor(bytes: &[u8]) -> Option<[u8; FACTOR_BYTES]> {
    let value: serde_json::Value = serde_json::from_slice(bytes).ok()?;
    if !exact_keys(&value, &["schema", "installation_id", "created_unix"]) {
        return None;
    }
    if value.get("schema")?.as_str()? != ANCHOR_SCHEMA {
        return None;
    }
    value.get("created_unix")?.as_u64()?;
    hex_decode_32(value.get("installation_id")?.as_str()?)
}

fn load_anchor_at(base: &Path, uid: u32) -> Loaded<[u8; FACTOR_BYTES]> {
    let path = base.join(ANCHOR_NAME);
    match read_strict_file(&path, uid, MAX_ANCHOR_BYTES, false) {
        Some(bytes) => match parse_anchor(&bytes) {
            Some(id) => Loaded::Value(id),
            None => Loaded::Invalid,
        },
        None => {
            if fs::symlink_metadata(&path).is_ok() {
                Loaded::Invalid
            } else {
                Loaded::Absent
            }
        }
    }
}

fn anchor_state_at(base: &Path, uid: u32) -> AnchorState {
    match load_anchor_at(base, uid) {
        Loaded::Value(id) => AnchorState::Present(id),
        Loaded::Invalid => AnchorState::Invalid,
        Loaded::Absent => AnchorState::Absent,
    }
}

/// Coarse recovery-factor state for status surfaces (specification
/// section 6 step 6: enrollment state, generation and dates only —
/// never the factor).
pub fn recovery_factor_state() -> RecoveryFactorState {
    if !has_persistent_state() {
        return RecoveryFactorState::NoState;
    }
    factor_state_at(Path::new(STATE_BASE), 0)
}

pub fn anchor_state() -> AnchorState {
    if !has_persistent_state() {
        return AnchorState::NoState;
    }
    anchor_state_at(Path::new(STATE_BASE), 0)
}

/// The strictly validated active record, for the reset flow.
pub fn load_active_record() -> Option<RecoveryRecord> {
    match load_record_at(Path::new(STATE_BASE), 0) {
        Loaded::Value(record) if !record.revoked => Some(record),
        _ => None,
    }
}

fn write_anchor_at(base: &Path, uid: u32, id: &[u8; FACTOR_BYTES], now: u64) -> io::Result<()> {
    if !private_directory(base, uid) {
        return Err(unsafe_path());
    }
    let path = base.join(ANCHOR_NAME);
    // The anchor is written exactly once, at the installation's
    // first factor enrollment. Replacing it would re-bind every
    // existing record, so any existing anchor name — file, symlink,
    // anything — is a refusal.
    if fs::symlink_metadata(&path).is_ok() {
        return Err(io::Error::new(
            io::ErrorKind::AlreadyExists,
            "installation anchor already exists",
        ));
    }
    let body = format!(
        "{{\"schema\":\"{ANCHOR_SCHEMA}\",\"installation_id\":\"{}\",\"created_unix\":{now}}}\n",
        hex_encode(id)
    );
    let mut out = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .custom_flags(LINUX_O_NOFOLLOW | LINUX_O_NONBLOCK)
        .open(&path)?;
    let result = (|| {
        out.write_all(body.as_bytes())?;
        out.sync_all()?;
        drop(out);
        fs::File::open(base)?.sync_all()
    })();
    if result.is_err() {
        let _ = fs::remove_file(&path);
    }
    result
}

pub fn write_anchor(id: &[u8; FACTOR_BYTES], now: u64) -> io::Result<()> {
    if !has_persistent_state() {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "persistent state unavailable",
        ));
    }
    write_anchor_at(Path::new(STATE_BASE), 0, id, now)
}

fn commit_factor_at(
    base: &Path,
    uid: u32,
    key: &[u8; FACTOR_BYTES],
    installation_id: &[u8; FACTOR_BYTES],
    generation: u64,
    now: u64,
) -> io::Result<()> {
    if !private_directory(base, uid) {
        return Err(unsafe_path());
    }
    let auth = base.join("auth");
    if !private_directory(&auth, uid) {
        return Err(unsafe_path());
    }
    // A corrupt existing record is never silently overwritten: the
    // flows refuse and a normally authenticated owner resolves it.
    // A valid record (active or revoked) contributes its original
    // enrollment time; the generation is the caller's decision.
    let enrolled_unix = match load_record_at(base, uid) {
        Loaded::Value(prior) => prior.enrolled_unix,
        Loaded::Absent => now,
        Loaded::Invalid => return Err(unsafe_path()),
    };
    let mut salt = [0u8; 16];
    fs::File::open("/dev/urandom")?.read_exact(&mut salt)?;
    let phc =
        hash_input_phc(&binding_input(installation_id, key), &salt).ok_or_else(unsafe_path)?;
    let record = RecoveryRecord {
        generation,
        installation_id: *installation_id,
        failed_attempts: 0,
        enrolled_unix,
        updated_unix: now,
        phc,
        revoked: false,
    };
    write_record_atomically(
        &auth,
        &auth.join(RECORD_NAME),
        record_json(&record).as_bytes(),
    )
}

/// Commit a freshly confirmed factor (specification section 6 step
/// 3, or rotation under section 7). `generation` continues the
/// record's counter: 1 for a first enrollment, prior + 1 otherwise.
pub fn commit_factor(
    key: &[u8; FACTOR_BYTES],
    installation_id: &[u8; FACTOR_BYTES],
    generation: u64,
    now: u64,
) -> io::Result<()> {
    if !has_persistent_state() {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "persistent state unavailable",
        ));
    }
    commit_factor_at(
        Path::new(STATE_BASE),
        0,
        key,
        installation_id,
        generation,
        now,
    )
}

fn rewrite_record_at(base: &Path, uid: u32, record: &RecoveryRecord) -> io::Result<()> {
    let auth = base.join("auth");
    if !private_directory(base, uid) || !private_directory(&auth, uid) {
        return Err(unsafe_path());
    }
    write_record_atomically(
        &auth,
        &auth.join(RECORD_NAME),
        record_json(record).as_bytes(),
    )
}

/// Record one failed verification against the active record
/// (persistent throttling, specification section 4.1). Returns the
/// new counter value.
pub fn record_failed_attempt(now: u64) -> io::Result<u32> {
    let base = Path::new(STATE_BASE);
    let Loaded::Value(mut record) = load_record_at(base, 0) else {
        return Err(unsafe_path());
    };
    if record.revoked {
        return Err(unsafe_path());
    }
    record.failed_attempts = record
        .failed_attempts
        .checked_add(1)
        .ok_or_else(unsafe_path)?;
    record.updated_unix = now;
    rewrite_record_at(base, 0, &record)?;
    Ok(record.failed_attempts)
}

/// Revoke the active factor (decision D7, after a successful reset;
/// the tombstone keeps the generation counter so a later
/// re-enrollment continues it). Returns the tombstone generation.
pub fn revoke_factor(now: u64) -> io::Result<u64> {
    let base = Path::new(STATE_BASE);
    let Loaded::Value(mut record) = load_record_at(base, 0) else {
        return Err(unsafe_path());
    };
    if record.revoked {
        return Err(unsafe_path());
    }
    record.revoked = true;
    record.phc = String::new();
    record.failed_attempts = 0;
    record.generation = record.generation.checked_add(1).ok_or_else(unsafe_path)?;
    record.updated_unix = now;
    let generation = record.generation;
    rewrite_record_at(base, 0, &record)?;
    Ok(generation)
}

// ---------------------------------------------------------------------
// Verification (specification sections 4.1, 8 and 9)
// ---------------------------------------------------------------------

/// The domain-separated verifier input of specification section 8:
/// `synveil-recovery-v1` ‖ installation identifier ‖ account
/// identity ‖ normalized key. A record verified under another
/// installation's identifier cannot verify here, even if every other
/// field is intact.
pub fn binding_input(installation_id: &[u8; FACTOR_BYTES], key: &[u8; FACTOR_BYTES]) -> Vec<u8> {
    let mut input = Vec::with_capacity(BINDING_DOMAIN.len() + 32 + LOCAL_ACCOUNT.len() + 32);
    input.extend_from_slice(BINDING_DOMAIN);
    input.extend_from_slice(installation_id);
    input.extend_from_slice(LOCAL_ACCOUNT.as_bytes());
    input.extend_from_slice(key);
    input
}

/// Verify a presented factor against the active record and the
/// anchor-agreed installation identifier. The caller establishes
/// anchor agreement first; this function additionally refuses any
/// disagreement it is handed.
pub fn verify_factor(
    key: &[u8; FACTOR_BYTES],
    record: &RecoveryRecord,
    anchor_id: &[u8; FACTOR_BYTES],
) -> bool {
    if record.revoked || record.installation_id != *anchor_id {
        return false;
    }
    verify_input_phc(&binding_input(anchor_id, key), &record.phc)
}

// ---------------------------------------------------------------------
// Audit (specification section 10)
// ---------------------------------------------------------------------

/// Append one recovery audit entry in the tier-2 audit store's
/// format. Entries carry event names, categories, generations and
/// timestamps only — never the factor, a password, a hash, or a
/// salt. Flows that must not proceed without an audit trail (the
/// reset flow) treat an error here as fatal.
pub fn append_audit(event: &str, fields: &str) -> io::Result<()> {
    if let Some(parent) = Path::new(AUDIT_LOG_PATH).parent() {
        fs::create_dir_all(parent)?;
    }
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(AUDIT_LOG_PATH)?;
    writeln!(file, "t={} event={event} {fields}", now_unix())?;
    file.sync_all()
}

pub fn now_unix() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or(0)
}

pub fn random_installation_id() -> io::Result<[u8; FACTOR_BYTES]> {
    let mut id = [0u8; FACTOR_BYTES];
    fs::File::open("/dev/urandom")?.read_exact(&mut id)?;
    Ok(id)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::DirBuilderExt;
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicU64, Ordering};

    static IDS: AtomicU64 = AtomicU64::new(1);

    fn fixture_key() -> [u8; FACTOR_BYTES] {
        let mut key = [0u8; FACTOR_BYTES];
        for (index, byte) in key.iter_mut().enumerate() {
            *byte = (index as u8).wrapping_mul(7).wrapping_add(3);
        }
        key
    }

    fn private_base() -> (PathBuf, u32) {
        let path = std::env::temp_dir().join(format!(
            "synveil-recovery-{}-{}",
            std::process::id(),
            IDS.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&path).unwrap();
        fs::set_permissions(&path, fs::Permissions::from_mode(0o700)).unwrap();
        let auth = path.join("auth");
        fs::DirBuilder::new().mode(0o700).create(&auth).unwrap();
        let uid = fs::metadata(&path).unwrap().uid();
        (path, uid)
    }

    #[test]
    fn factor_display_shape_and_roundtrip() {
        let key = fixture_key();
        let display = encode_factor(&key);
        let groups: Vec<&str> = display.grouped.split('-').collect();
        assert_eq!(groups.len(), 14);
        assert!(groups.iter().all(|group| group.len() == 4));
        assert_eq!(groups[13], display.check_group);
        assert_eq!(groups[MIDDLE_GROUP_INDEX], display.middle_group);
        // The final key character carries one bit: '0' or 'G' only.
        assert!(matches!(groups[12].chars().last(), Some('0' | 'G')));
        match parse_entered_factor(display.grouped.as_bytes()) {
            FactorParse::Key(parsed) => assert_eq!(parsed, key),
            other => panic!("roundtrip failed: {other:?}"),
        }
        // Separators and case are presentation, not content.
        let bare = display.grouped.replace('-', "").to_lowercase();
        match parse_entered_factor(bare.as_bytes()) {
            FactorParse::Key(parsed) => assert_eq!(parsed, key),
            other => panic!("normalized parse failed: {other:?}"),
        }
    }

    #[test]
    fn factor_parse_distinguishes_transcription_from_malformed() {
        let key = fixture_key();
        let display = encode_factor(&key);
        // One character changed in a key group: the decoded key no
        // longer matches the check group.
        let mut mutated: Vec<u8> = display.grouped.bytes().collect();
        mutated[0] = if mutated[0] == b'0' { b'1' } else { b'0' };
        assert!(matches!(
            parse_entered_factor(&mutated),
            FactorParse::Transcription
        ));
        // Wrong total length and out-of-alphabet input are malformed.
        assert!(matches!(
            parse_entered_factor(b"ABCD"),
            FactorParse::Malformed
        ));
        let mut bad_char: Vec<u8> = display.grouped.bytes().collect();
        bad_char[0] = b'!';
        assert!(matches!(
            parse_entered_factor(&bad_char),
            FactorParse::Malformed
        ));
        // Non-canonical padding bits in the final key character.
        let mut padding: Vec<u8> = display.grouped.replace('-', "").bytes().collect();
        padding[51] = b'1';
        assert!(matches!(
            parse_entered_factor(&padding),
            FactorParse::Malformed
        ));
    }

    #[test]
    fn binding_input_layout_is_domain_separated() {
        let id = [9u8; FACTOR_BYTES];
        let key = fixture_key();
        let input = binding_input(&id, &key);
        assert!(input.starts_with(b"synveil-recovery-v1"));
        assert_eq!(&input[19..51], &[9u8; 32]);
        assert_eq!(&input[51..58], b"synveil");
        assert_eq!(&input[58..], &key);
    }

    #[test]
    fn record_lifecycle_binds_verification_to_the_anchor() {
        let (base, uid) = private_base();
        let id = [4u8; FACTOR_BYTES];
        let other_id = [5u8; FACTOR_BYTES];
        let key = fixture_key();
        write_anchor_at(&base, uid, &id, 100).unwrap();
        // The anchor is written exactly once.
        assert_eq!(
            write_anchor_at(&base, uid, &id, 100).unwrap_err().kind(),
            io::ErrorKind::AlreadyExists
        );
        assert_eq!(anchor_state_at(&base, uid), AnchorState::Present(id));
        commit_factor_at(&base, uid, &key, &id, 1, 100).unwrap();
        assert_eq!(
            factor_state_at(&base, uid),
            RecoveryFactorState::Active {
                generation: 1,
                enrolled_unix: 100,
                failed_attempts: 0
            }
        );
        let record = match load_record_at(&base, uid) {
            Loaded::Value(record) => record,
            _ => panic!("record did not load"),
        };
        assert!(verify_factor(&key, &record, &id));
        // The same record and key under another installation's
        // anchor are denied: transplantation fails (spec section 8).
        assert!(!verify_factor(&key, &record, &other_id));
        let mut wrong = key;
        wrong[0] ^= 1;
        assert!(!verify_factor(&wrong, &record, &id));
        // Record file discipline: 0600, single link, no temp left.
        let record_path = base.join("auth").join(RECORD_NAME);
        let meta = fs::metadata(&record_path).unwrap();
        assert_eq!(meta.permissions().mode() & 0o777, 0o600);
        assert_eq!(meta.nlink(), 1);
        assert!(!base.join("auth").join(".recovery.json.new").exists());
        fs::remove_dir_all(base).unwrap();
    }

    #[test]
    fn failed_attempts_persist_and_revocation_tombstones() {
        let (base, uid) = private_base();
        let id = [6u8; FACTOR_BYTES];
        let key = fixture_key();
        write_anchor_at(&base, uid, &id, 100).unwrap();
        commit_factor_at(&base, uid, &key, &id, 1, 100).unwrap();
        // Drive the counter through the base-parameterized rewrite
        // the public wrapper uses.
        let Loaded::Value(mut record) = load_record_at(&base, uid) else {
            panic!("record did not load");
        };
        record.failed_attempts += 1;
        rewrite_record_at(&base, uid, &record).unwrap();
        assert_eq!(
            factor_state_at(&base, uid),
            RecoveryFactorState::Active {
                generation: 1,
                enrolled_unix: 100,
                failed_attempts: 1
            }
        );
        // Revocation: tombstone at generation + 1, no PHC, and the
        // used factor no longer verifies.
        let Loaded::Value(mut record) = load_record_at(&base, uid) else {
            panic!("record did not load");
        };
        record.revoked = true;
        record.phc = String::new();
        record.generation += 1;
        rewrite_record_at(&base, uid, &record).unwrap();
        assert_eq!(
            factor_state_at(&base, uid),
            RecoveryFactorState::Revoked { generation: 2 }
        );
        let Loaded::Value(tombstone) = load_record_at(&base, uid) else {
            panic!("tombstone did not load");
        };
        assert!(!verify_factor(&key, &tombstone, &id));
        // Re-enrollment continues the generation counter and keeps
        // the original enrollment timestamp.
        commit_factor_at(&base, uid, &key, &id, 3, 200).unwrap();
        assert_eq!(
            factor_state_at(&base, uid),
            RecoveryFactorState::Active {
                generation: 3,
                enrolled_unix: 100,
                failed_attempts: 0
            }
        );
        fs::remove_dir_all(base).unwrap();
    }

    fn replaced(haystack: &[u8], needle: &[u8], replacement: &[u8]) -> Vec<u8> {
        let pos = haystack
            .windows(needle.len())
            .position(|window| window == needle)
            .expect("needle present");
        let mut out = haystack[..pos].to_vec();
        out.extend_from_slice(replacement);
        out.extend_from_slice(&haystack[pos + needle.len()..]);
        out
    }

    #[test]
    fn corrupt_records_and_anchors_fail_closed() {
        let (base, uid) = private_base();
        let id = [8u8; FACTOR_BYTES];
        let key = fixture_key();
        write_anchor_at(&base, uid, &id, 100).unwrap();
        commit_factor_at(&base, uid, &key, &id, 1, 100).unwrap();
        let record_path = base.join("auth").join(RECORD_NAME);
        let good = fs::read(&record_path).unwrap();
        for corrupt in [
            b"{\"schema\":\"synveil.recovery-record/v1\"}".to_vec(),
            replaced(
                &good,
                b"synveil.recovery-record/v1",
                b"synveil.recovery-record/v9",
            ),
            replaced(
                &good,
                b"\"state\":\"active\"",
                b"\"state\":\"active\",\"extra\":1",
            ),
            {
                // Bit flip inside the PHC tag: still parses as JSON,
                // but the record must not verify the genuine key.
                let mut flipped = good.clone();
                let pos = flipped
                    .windows(4)
                    .position(|w| w == b"$AAA")
                    .unwrap_or(flipped.len() - 10);
                flipped[pos] = if flipped[pos] == b'A' { b'B' } else { b'A' };
                flipped
            },
        ] {
            fs::write(&record_path, &corrupt).unwrap();
            fs::set_permissions(&record_path, fs::Permissions::from_mode(0o600)).unwrap();
            match load_record_at(&base, uid) {
                Loaded::Value(record) => {
                    assert!(
                        !verify_factor(&key, &record, &id),
                        "corrupt record verified"
                    )
                }
                Loaded::Invalid | Loaded::Absent => {}
            }
        }
        // Wrong permissions alone make the record invalid.
        fs::write(&record_path, &good).unwrap();
        fs::set_permissions(&record_path, fs::Permissions::from_mode(0o644)).unwrap();
        assert_eq!(factor_state_at(&base, uid), RecoveryFactorState::Invalid);
        fs::set_permissions(&record_path, fs::Permissions::from_mode(0o600)).unwrap();
        // A symlinked record is invalid, never followed.
        fs::remove_file(&record_path).unwrap();
        std::os::unix::fs::symlink("/nonexistent", &record_path).unwrap();
        assert_eq!(factor_state_at(&base, uid), RecoveryFactorState::Invalid);
        fs::remove_file(&record_path).unwrap();
        // A corrupt anchor is invalid too.
        let anchor_path = base.join(ANCHOR_NAME);
        fs::write(&anchor_path, b"{}").unwrap();
        fs::set_permissions(&anchor_path, fs::Permissions::from_mode(0o600)).unwrap();
        assert_eq!(anchor_state_at(&base, uid), AnchorState::Invalid);
        fs::remove_dir_all(base).unwrap();
    }
}
