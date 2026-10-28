// SPDX-License-Identifier: MPL-2.0
//! Local text-mode authenticated maintenance (ADR 0010 tier 2) and
//! forgotten-password reset (tier 4, Option A per ADR 0020).
//!
//! Runs only when the kernel command line carries
//! `synveil.recovery=maint` or `synveil.recovery=reset` (see
//! build/rootfs/init): after the state mount, before core, seat,
//! network or desktop start. The boot entries are the ESP's
//! `EFI/synveil/maintenance.efi` and `EFI/synveil/reset.efi`, owner
//! firmware-menu picks, exactly like the tier-1 recovery entry.
//!
//! Maintenance authentication reuses the separately audited ADR 0009
//! verifier (`credential::verify_root_credential`) directly. It does
//! NOT go through the graphical seat broker, and it never starts
//! one. The credential store's coarse state (no state / absent /
//! invalid / present) is reported with fixed markers; a wrong
//! password against a present store is an ordinary denial.
//!
//! After authentication the operator gets a fixed set of enumerated
//! commands, matched exactly, one per line:
//!
//!   status   bounded A/B status and recovery-factor state (read-only)
//!   restore  restore the known-good generation via veil-ab's
//!            rollback machinery (typed action, verified postcondition)
//!   rotate   enroll or rotate the tier-4 recovery factor through
//!            the section 6 custody flow (this session's password
//!            authentication is the normal authentication section 7
//!            requires)
//!   reboot   reboot the machine
//!   exit     end the session; init then locks the console
//!
//! Reset mode (`synveil.recovery=reset`) is the specification
//! section 9 flow: the record/anchor binding is checked before any
//! input is accepted, the printed recovery factor is verified
//! against its Argon2id record with persistent throttling, and only
//! after a separate explicit confirmation is the password record
//! atomically replaced through the same credential authority. The
//! used factor is then revoked (decision D7). A transcription error
//! (bad check group) is rejected without consuming an attempt and
//! without running the verifier.
//!
//! The replacement and the revocation are one crash-consistent
//! transaction (see `recovery::execute_reset_transaction`): a
//! durable journal entry naming the consumed factor generation is
//! written before the credential changes, success is reported only
//! when both writes are durable, and every entry into either mode
//! of this program settles a journal left by an interrupted or
//! partially failed reset before anything else proceeds. A journal
//! that cannot be settled denies all factor use (fail closed).
//!
//! Input is never interpreted as shell text, never passed to a shell,
//! and no other program is executed except /bin/stty with fixed
//! arguments to switch console echo off while secrets are read.
//! Bounds: 3 password attempts, 16 commands per session, 1024-byte
//! password lines, 64-byte command lines, 8 factor entries and 3
//! factor verification attempts per reset session. Every
//! authentication outcome and action is appended to an audit log on
//! the state volume; passwords and credential material are never
//! logged.

use std::fs::OpenOptions;
use std::io::{self, BufRead, BufReader, Write};
use std::process::{Command, ExitCode};
use std::time::{SystemTime, UNIX_EPOCH};
use veil_core::ab;
use veil_core::credential::{
    LOCAL_ACCOUNT, RootCredentialState, replace_root_credential, root_credential_state,
    verify_root_credential,
};
use veil_core::recovery::{self, AnchorState, FactorParse, RecoveryFactorState};
use veil_core::secret;

const MAX_ATTEMPTS: u32 = 3;
const MAX_COMMANDS: u32 = 16;
const MAX_PASSWORD_LINE: usize = 1024;
const MAX_COMMAND_LINE: usize = 64;
const MAX_FACTOR_LINE: usize = 128;
const MAX_FACTOR_ENTRIES: u32 = 8;
// veil_core::recovery::AUDIT_LOG_PATH names the same store; the
// tier-2 host contract pins this constant's spelling here.
const AUDIT_LOG_PATH: &str = "/var/log/synveil/recovery-maintenance.log";

fn audit(event: &str, fields: &str) {
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    if let Some(parent) = std::path::Path::new(AUDIT_LOG_PATH).parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    if let Ok(mut file) = OpenOptions::new()
        .create(true)
        .append(true)
        .open(AUDIT_LOG_PATH)
    {
        let _ = writeln!(file, "t={secs} event={event} {fields}");
        let _ = file.sync_all();
    }
}

/// Switch console echo off/on with a fixed-program, fixed-argument
/// stty call. stty operates on its standard input, which init has
/// already attached to /dev/console; the operator's input is never
/// part of the arguments. (A positional device operand is not
/// accepted by the rootfs stty and must not be passed.)
fn set_echo(on: bool) -> bool {
    let setting = if on { "echo" } else { "-echo" };
    Command::new("/bin/stty")
        .args([setting])
        .stdin(std::process::Stdio::inherit())
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
}

enum Line {
    Text(Vec<u8>),
    TooLong,
    Eof,
}

/// Read one line byte-wise with a hard cap, so an unbounded input
/// stream can never grow memory. A too-long line is drained to its
/// newline and reported as `TooLong`.
fn read_line(reader: &mut BufReader<io::Stdin>, max: usize) -> Line {
    let mut buf: Vec<u8> = Vec::new();
    let mut too_long = false;
    loop {
        let available = match reader.fill_buf() {
            Ok(chunk) => chunk,
            Err(_) => return Line::Eof,
        };
        if available.is_empty() {
            if buf.is_empty() && !too_long {
                return Line::Eof;
            }
            break;
        }
        let byte = available[0];
        reader.consume(1);
        if byte == b'\n' {
            break;
        }
        if buf.len() < max {
            buf.push(byte);
        } else {
            too_long = true;
        }
    }
    if too_long {
        return Line::TooLong;
    }
    if buf.last() == Some(&b'\r') {
        buf.pop();
    }
    Line::Text(buf)
}

fn out(text: &str) {
    let stdout = io::stdout();
    let mut lock = stdout.lock();
    let _ = writeln!(lock, "{text}");
    let _ = lock.flush();
}

fn kernel_cmdline_has(word: &str) -> bool {
    std::fs::read_to_string("/proc/cmdline")
        .map(|cmdline| cmdline.split_whitespace().any(|entry| entry == word))
        .unwrap_or(false)
}

/// Settle a reset journal left by an interrupted or partially
/// failed reset transaction, before any other operation in either
/// mode of this program. Returns true when a journal exists but
/// could not be settled: factor use is then denied (fail closed)
/// and factor state is reported as reset-incomplete, while
/// password-authenticated operations that do not touch the factor
/// remain available.
fn settle_reset_journal() -> bool {
    match recovery::settle_pending_reset(recovery::now_unix()) {
        Ok(recovery::ResetSettleOutcome::NoJournal) => false,
        Ok(recovery::ResetSettleOutcome::Completed { factor_generation }) => {
            let _ = recovery::append_audit(
                "reset-journal-completed",
                &format!("factor_generation={factor_generation}"),
            );
            false
        }
        Err(_) => {
            let _ = recovery::append_audit("reset-journal-unresolved", "");
            true
        }
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if !args.is_empty() {
        eprintln!("usage: veil-recovery (no arguments; kernel cmdline selects this mode)");
        return ExitCode::FAILURE;
    }
    if kernel_cmdline_has("synveil.recovery=reset") {
        return run_reset();
    }
    run_maint()
}

fn run_maint() -> ExitCode {
    out("SYNVEIL_RECOVERY_MAINT_V1");
    audit("session-start", "");
    // An interrupted reset is completed before anything else; if
    // it cannot be completed, factor operations stay denied.
    let journal_blocked = settle_reset_journal();

    // Store-state denials happen before any prompt: there is nothing
    // a password could authenticate against.
    match root_credential_state() {
        RootCredentialState::NoState => {
            out("SYNVEIL_RECOVERY_MAINT_DENIED reason=no-state");
            audit("auth-denied", "reason=no-state");
            return ExitCode::FAILURE;
        }
        RootCredentialState::Absent => {
            out("SYNVEIL_RECOVERY_MAINT_DENIED reason=no-credential");
            audit("auth-denied", "reason=no-credential");
            return ExitCode::FAILURE;
        }
        RootCredentialState::Invalid => {
            out("SYNVEIL_RECOVERY_MAINT_DENIED reason=corrupt-credential");
            audit("auth-denied", "reason=corrupt-credential");
            return ExitCode::FAILURE;
        }
        RootCredentialState::Present => {}
    }

    if !set_echo(false) {
        out("SYNVEIL_RECOVERY_MAINT_UNAVAILABLE");
        audit("unavailable", "reason=echo-control");
        return ExitCode::FAILURE;
    }
    let mut reader = BufReader::new(io::stdin());
    let mut authenticated = false;
    for attempt in 1..=MAX_ATTEMPTS {
        out("SYNVEIL_RECOVERY_MAINT_PASSWORD_PROMPT");
        match read_line(&mut reader, MAX_PASSWORD_LINE) {
            Line::Text(mut password) => {
                let ok = verify_root_credential(LOCAL_ACCOUNT, &password);
                secret::clear(&mut password);
                if ok {
                    authenticated = true;
                    break;
                }
                out(&format!("SYNVEIL_RECOVERY_MAINT_DENIED attempt={attempt}"));
                audit("auth-denied", &format!("attempt={attempt}"));
            }
            Line::TooLong => {
                out(&format!("SYNVEIL_RECOVERY_MAINT_DENIED attempt={attempt}"));
                audit("auth-denied", &format!("attempt={attempt} reason=oversize"));
            }
            Line::Eof => break,
        }
    }
    let _ = set_echo(true);
    if !authenticated {
        audit("session-end", "result=denied");
        return ExitCode::FAILURE;
    }
    out("SYNVEIL_RECOVERY_MAINT_AUTH_OK");
    audit("auth-ok", "");
    out("SYNVEIL_RECOVERY_MAINT_READY");

    for _ in 0..MAX_COMMANDS {
        match read_line(&mut reader, MAX_COMMAND_LINE) {
            Line::Text(line) => {
                let Ok(command) = std::str::from_utf8(&line) else {
                    out("SYNVEIL_RECOVERY_MAINT_REJECTED");
                    audit("command-rejected", "reason=non-utf8");
                    continue;
                };
                match command {
                    "status" => action_status(journal_blocked),
                    "restore" => action_restore(),
                    "rotate" => action_rotate(&mut reader, journal_blocked),
                    "reboot" => {
                        out("SYNVEIL_RECOVERY_MAINT_REBOOT");
                        audit("action", "name=reboot result=initiated");
                        io::stdout().flush().ok();
                        ab::reboot_now();
                    }
                    "exit" => {
                        out("SYNVEIL_RECOVERY_MAINT_DONE");
                        audit("session-end", "result=exit");
                        return ExitCode::SUCCESS;
                    }
                    _ => {
                        out("SYNVEIL_RECOVERY_MAINT_REJECTED");
                        audit("command-rejected", "reason=unknown");
                    }
                }
            }
            Line::TooLong => {
                out("SYNVEIL_RECOVERY_MAINT_REJECTED");
                audit("command-rejected", "reason=oversize");
            }
            Line::Eof => {
                audit("session-end", "result=eof");
                return ExitCode::SUCCESS;
            }
        }
    }
    out("SYNVEIL_RECOVERY_MAINT_DONE");
    audit("session-end", "result=command-limit");
    ExitCode::SUCCESS
}

/// Bounded read-only status: the fixed state lines plus the A/B
/// agent's own status value (control record contents are size-capped
/// by the A/B schema: history is capped at 32 entries).
fn action_status(journal_blocked: bool) {
    out("SYNVEIL_RECOVERY_MAINT_STATUS_BEGIN");
    out("SYNVEIL_RECOVERY_STATE_MOUNTED");
    match ab::status() {
        Ok(value) => {
            let confirmed = value.get("confirmed");
            let slot = confirmed
                .and_then(|c| c.get("slot"))
                .and_then(|v| v.as_str())
                .unwrap_or("none");
            let version = confirmed
                .and_then(|c| c.get("version"))
                .and_then(|v| v.as_u64())
                .unwrap_or(0);
            out(&format!(
                "SYNVEIL_RECOVERY_MAINT_AB confirmed_slot={slot} confirmed_version={version}"
            ));
            match value.get("trial") {
                Some(trial) if !trial.is_null() => {
                    let tslot = trial.get("slot").and_then(|v| v.as_str()).unwrap_or("none");
                    let tversion = trial.get("version").and_then(|v| v.as_u64()).unwrap_or(0);
                    out(&format!(
                        "SYNVEIL_RECOVERY_MAINT_AB trial_slot={tslot} trial_version={tversion}"
                    ));
                }
                _ => out("SYNVEIL_RECOVERY_MAINT_AB trial=none"),
            }
            out(&format!(
                "SYNVEIL_RECOVERY_MAINT_AB_JSON {}",
                serde_json::to_string(&value).unwrap_or_else(|_| "{}".into())
            ));
        }
        Err(_) => out("SYNVEIL_RECOVERY_MAINT_AB_UNAVAILABLE"),
    }
    // Recovery-factor state, bounded exactly as specification
    // section 6 step 6 allows: enrollment state, generation and
    // enrollment date only — never the factor or its record. An
    // unsettled reset journal is reported as what it is: the
    // factor's state cannot be honestly summarized until the
    // journal is resolved under normal authentication.
    if journal_blocked {
        out("SYNVEIL_RECOVERY_MAINT_FACTOR state=reset-incomplete");
        out("SYNVEIL_RECOVERY_MAINT_STATUS_END");
        audit("action", "name=status result=ok");
        return;
    }
    match recovery::recovery_factor_state() {
        RecoveryFactorState::Active {
            generation,
            enrolled_unix,
            ..
        } => out(&format!(
            "SYNVEIL_RECOVERY_MAINT_FACTOR state=active generation={generation} enrolled_unix={enrolled_unix}"
        )),
        RecoveryFactorState::Revoked { generation } => out(&format!(
            "SYNVEIL_RECOVERY_MAINT_FACTOR state=revoked generation={generation}"
        )),
        RecoveryFactorState::Absent => out("SYNVEIL_RECOVERY_MAINT_FACTOR state=not-enrolled"),
        RecoveryFactorState::Invalid => out("SYNVEIL_RECOVERY_MAINT_FACTOR state=invalid"),
        RecoveryFactorState::NoState => out("SYNVEIL_RECOVERY_MAINT_FACTOR state=unavailable"),
    }
    out("SYNVEIL_RECOVERY_MAINT_STATUS_END");
    audit("action", "name=status result=ok");
}

/// Restore the known-good generation. Preconditions and the mutation
/// itself are veil-ab's typed rollback action: a pending trial is
/// discarded, otherwise the retained generation in the other slot is
/// digest-verified against the control record and armed as a fresh
/// trial. Postcondition checked here: the reloaded control record
/// must show exactly the state the action reported.
fn action_restore() {
    match ab::rollback() {
        Ok(result) => {
            let verified = verify_restore_postcondition(&result);
            match (result.get("reason").and_then(|v| v.as_str()), verified) {
                (Some("pending-trial-discarded"), true) => {
                    out("SYNVEIL_RECOVERY_MAINT_RESTORE_DISCARDED");
                    audit("action", "name=restore result=trial-discarded");
                }
                (_, true) => {
                    let slot = result
                        .get("selected_slot")
                        .and_then(|v| v.as_str())
                        .unwrap_or("none");
                    let version = result.get("version").and_then(|v| v.as_u64()).unwrap_or(0);
                    out(&format!(
                        "SYNVEIL_RECOVERY_MAINT_RESTORE_OK slot={slot} version={version}"
                    ));
                    audit(
                        "action",
                        &format!("name=restore result=armed slot={slot} version={version}"),
                    );
                }
                _ => {
                    out("SYNVEIL_RECOVERY_MAINT_RESTORE_REFUSED");
                    audit("action", "name=restore result=postcondition-failed");
                }
            }
        }
        Err(_) => {
            out("SYNVEIL_RECOVERY_MAINT_RESTORE_REFUSED");
            audit("action", "name=restore result=refused");
        }
    }
}

/// Compare an entered confirmation group (bytes, any case, stray
/// whitespace ignored) against a displayed group.
/// The section 6 print offer, shared by enrollment and rotation:
/// only when a local printer device is already present, the key
/// text may be written directly to the device. Never a spooler,
/// never a network queue (decision D3).
fn offer_print(reader: &mut BufReader<io::Stdin>, grouped: &str) {
    let device = ["/dev/lp0", "/dev/usb/lp0"]
        .into_iter()
        .find(|path| std::path::Path::new(path).exists());
    let Some(device) = device else {
        out("SYNVEIL_RECOVERY_FACTOR_PRINT_UNAVAILABLE");
        return;
    };
    out("SYNVEIL_RECOVERY_FACTOR_PRINT_AVAILABLE");
    out("SYNVEIL_RECOVERY_FACTOR_PRINT_PROMPT");
    match read_line(reader, MAX_FACTOR_LINE) {
        Line::Text(line) if line.as_slice() == b"print" => {
            let written = std::fs::OpenOptions::new()
                .write(true)
                .open(device)
                .and_then(|mut file| {
                    writeln!(
                        file,
                        "Synveil recovery key (keep with your recovery material):"
                    )?;
                    writeln!(file, "{grouped}")?;
                    writeln!(file, "\u{c}")
                });
            match written {
                Ok(()) => out("SYNVEIL_RECOVERY_FACTOR_PRINTED"),
                Err(_) => out("SYNVEIL_RECOVERY_FACTOR_PRINT_FAILED"),
            }
        }
        _ => out("SYNVEIL_RECOVERY_FACTOR_PRINT_SKIPPED"),
    }
}

fn group_matches(line: &[u8], expected: &str) -> bool {
    let folded: Vec<u8> = line
        .iter()
        .copied()
        .filter(|byte| !byte.is_ascii_whitespace())
        .map(|byte| byte.to_ascii_uppercase())
        .collect();
    folded == expected.as_bytes()
}

/// Enroll or rotate the tier-4 recovery factor (specification
/// sections 6 and 7). This session is authenticated through the
/// ordinary password verifier, which is the normal authentication
/// section 7 requires; the factor itself can never authorize its own
/// replacement. The custody interaction is the section 6 one: the
/// new factor is displayed exactly once, the owner re-enters the
/// check group and the designated middle group, then confirms
/// explicitly — and only then is the new record committed, so an
/// abandoned rotation leaves the previous factor in force.
fn action_rotate(reader: &mut BufReader<io::Stdin>, journal_blocked: bool) {
    if journal_blocked {
        // Rotating over an unsettled reset journal would orphan
        // it; the journal must be resolved first (entry settling
        // retries on every boot of this program).
        out("SYNVEIL_RECOVERY_ROTATE_REFUSED");
        audit("factor-rotation-refused", "reason=reset-incomplete");
        return;
    }
    let (prior_generation, new_generation) = match recovery::recovery_factor_state() {
        RecoveryFactorState::Active { generation, .. }
        | RecoveryFactorState::Revoked { generation } => {
            let Some(next) = generation.checked_add(1) else {
                out("SYNVEIL_RECOVERY_ROTATE_REFUSED");
                audit("factor-rotation-refused", "reason=generation-overflow");
                return;
            };
            (Some(generation), next)
        }
        RecoveryFactorState::Absent => (None, 1),
        _ => {
            out("SYNVEIL_RECOVERY_ROTATE_REFUSED");
            audit("factor-rotation-refused", "reason=factor-state");
            return;
        }
    };
    let (anchor_id, anchor_pending) = match recovery::anchor_state() {
        AnchorState::Present(id) => (id, false),
        AnchorState::Absent => match recovery::random_installation_id() {
            Ok(id) => (id, true),
            Err(_) => {
                out("SYNVEIL_RECOVERY_ROTATE_REFUSED");
                audit("factor-rotation-refused", "reason=entropy");
                return;
            }
        },
        _ => {
            out("SYNVEIL_RECOVERY_ROTATE_REFUSED");
            audit("factor-rotation-refused", "reason=anchor-state");
            return;
        }
    };
    audit(
        "factor-rotation-requested",
        &format!(
            "prior_generation={} new_generation={new_generation}",
            prior_generation
                .map(|generation| generation.to_string())
                .unwrap_or_else(|| "none".to_string())
        ),
    );
    let mut factor = match recovery::generate_factor() {
        Ok(factor) => factor,
        Err(_) => {
            out("SYNVEIL_RECOVERY_ROTATE_REFUSED");
            audit("factor-rotation-refused", "reason=entropy");
            return;
        }
    };
    out("SYNVEIL_RECOVERY_ROTATE_DISPLAY_BEGIN");
    out(&factor.display.grouped);
    out("SYNVEIL_RECOVERY_ROTATE_DISPLAY_END");
    offer_print(reader, &factor.display.grouped);
    if !set_echo(false) {
        factor.clear();
        out("SYNVEIL_RECOVERY_ROTATE_REFUSED");
        audit("factor-rotation-refused", "reason=echo-control");
        return;
    }
    out("SYNVEIL_RECOVERY_ROTATE_CHECK_GROUP_PROMPT");
    let check = read_line(reader, MAX_FACTOR_LINE);
    out("SYNVEIL_RECOVERY_ROTATE_MIDDLE_GROUP_PROMPT");
    let middle = read_line(reader, MAX_FACTOR_LINE);
    let _ = set_echo(true);
    let groups_ok = match (&check, &middle) {
        (Line::Text(check_line), Line::Text(middle_line)) => {
            group_matches(check_line, &factor.display.check_group)
                && group_matches(middle_line, &factor.display.middle_group)
        }
        _ => false,
    };
    if let Line::Text(mut line) = check {
        secret::clear(&mut line);
    }
    if let Line::Text(mut line) = middle {
        secret::clear(&mut line);
    }
    if !groups_ok {
        factor.clear();
        out("SYNVEIL_RECOVERY_ROTATE_CONFIRMATION_FAILED");
        audit("factor-rotation-aborted", "reason=confirmation-groups");
        return;
    }
    out("SYNVEIL_RECOVERY_ROTATE_CONFIRM_PROMPT");
    let confirmed = match read_line(reader, MAX_COMMAND_LINE) {
        Line::Text(line) => line.as_slice() == b"confirm",
        _ => false,
    };
    if !confirmed {
        factor.clear();
        out("SYNVEIL_RECOVERY_ROTATE_ABORTED");
        audit("factor-rotation-aborted", "reason=not-confirmed");
        return;
    }
    audit(
        "factor-rotation-confirmed",
        &format!("generation={new_generation}"),
    );
    if anchor_pending && recovery::write_anchor(&anchor_id, recovery::now_unix()).is_err() {
        factor.clear();
        out("SYNVEIL_RECOVERY_ROTATE_REFUSED");
        audit("factor-rotation-failed", "reason=anchor-write");
        return;
    }
    let committed = recovery::commit_factor(
        &factor.key,
        &anchor_id,
        new_generation,
        recovery::now_unix(),
    );
    factor.clear();
    if committed.is_err() {
        out("SYNVEIL_RECOVERY_ROTATE_REFUSED");
        audit("factor-rotation-failed", "reason=record-write");
        return;
    }
    audit(
        "factor-rotation-completed",
        &format!("generation={new_generation}"),
    );
    out(&format!(
        "SYNVEIL_RECOVERY_ROTATE_OK generation={new_generation}"
    ));
}

/// Tier-4 reset denial before (or without) factor entry. The audit
/// entry distinguishes categories, never factor-dependent detail
/// (specification section 10).
fn reset_denied(reason: &str, category: &str) -> ExitCode {
    out(&format!("SYNVEIL_RECOVERY_RESET_DENIED reason={reason}"));
    let _ = recovery::append_audit("reset-denied", &format!("category={category}"));
    ExitCode::FAILURE
}

/// The specification section 9 reset flow, entered only via the
/// explicit `synveil.recovery=reset` boot entry. Binding agreement
/// is established before any input is accepted; the reset itself is
/// gated on the audit write that records the owner's confirmation,
/// so a flow that cannot write its audit entries never mutates the
/// credential (section 10).
fn run_reset() -> ExitCode {
    out("SYNVEIL_RECOVERY_RESET_V1");
    let _ = recovery::append_audit("reset-session-start", "");
    // A journaled reset from an earlier boot is completed before
    // any factor is accepted; one that cannot be completed denies
    // this session outright. After a successful completion the
    // record checks below see the consumed factor as revoked,
    // which is the honest answer for its presenter.
    if settle_reset_journal() {
        return reset_denied("reset-incomplete", "journal-unresolved");
    }
    let record = match recovery::recovery_factor_state() {
        RecoveryFactorState::NoState => return reset_denied("no-state", "no-state"),
        RecoveryFactorState::Absent => {
            return reset_denied("no-recovery-factor", "no-factor");
        }
        RecoveryFactorState::Invalid => return reset_denied("corrupt-record", "corrupt-record"),
        RecoveryFactorState::Revoked { .. } => {
            return reset_denied("factor-revoked", "revoked");
        }
        RecoveryFactorState::Active { .. } => match recovery::load_active_record() {
            Some(record) => record,
            None => return reset_denied("corrupt-record", "corrupt-record"),
        },
    };
    let anchor_id = match recovery::anchor_state() {
        AnchorState::Present(id) => id,
        AnchorState::Absent => return reset_denied("no-anchor", "anchor-absent"),
        AnchorState::Invalid => return reset_denied("anchor-invalid", "anchor-invalid"),
        AnchorState::NoState => return reset_denied("no-state", "no-state"),
    };
    if record.installation_id != anchor_id {
        return reset_denied("anchor-mismatch", "binding-mismatch");
    }
    if record.failed_attempts >= recovery::MAX_FAILED_ATTEMPTS {
        return reset_denied("throttled", "lockout");
    }
    if !set_echo(false) {
        out("SYNVEIL_RECOVERY_RESET_UNAVAILABLE");
        return ExitCode::FAILURE;
    }
    let mut reader = BufReader::new(io::stdin());
    let mut verified = false;
    let mut entries = 0u32;
    let mut guesses = 0u32;
    while entries < MAX_FACTOR_ENTRIES && guesses < MAX_ATTEMPTS {
        entries += 1;
        out("SYNVEIL_RECOVERY_RESET_FACTOR_PROMPT");
        match read_line(&mut reader, MAX_FACTOR_LINE) {
            Line::Text(mut line) => {
                match recovery::parse_entered_factor(&line) {
                    FactorParse::Key(mut key) => {
                        guesses += 1;
                        if recovery::verify_factor(&key, &record, &anchor_id) {
                            secret::clear(&mut key);
                            verified = true;
                        } else {
                            secret::clear(&mut key);
                            match recovery::record_failed_attempt(recovery::now_unix()) {
                                Ok(count) => {
                                    out(&format!(
                                        "SYNVEIL_RECOVERY_RESET_ATTEMPT_DENIED attempt={guesses}"
                                    ));
                                    let _ = recovery::append_audit(
                                        "factor-verification-denied",
                                        &format!("category=mismatch failed_attempts={count}"),
                                    );
                                }
                                Err(_) => {
                                    out("SYNVEIL_RECOVERY_RESET_UNAVAILABLE");
                                    let _ = set_echo(true);
                                    secret::clear(&mut line);
                                    return ExitCode::FAILURE;
                                }
                            }
                        }
                    }
                    FactorParse::Transcription => {
                        out("SYNVEIL_RECOVERY_RESET_TRANSCRIPTION");
                    }
                    FactorParse::Malformed => {
                        out("SYNVEIL_RECOVERY_RESET_REJECTED");
                    }
                }
                secret::clear(&mut line);
                if verified {
                    break;
                }
            }
            Line::TooLong => out("SYNVEIL_RECOVERY_RESET_REJECTED"),
            Line::Eof => break,
        }
    }
    if !verified {
        let _ = set_echo(true);
        let _ = recovery::append_audit("reset-session-end", "result=denied");
        return ExitCode::FAILURE;
    }
    out("SYNVEIL_RECOVERY_RESET_VERIFIED");
    let _ = recovery::append_audit(
        "factor-verification-verified",
        &format!("generation={}", record.generation),
    );
    let _ = set_echo(true);
    out("SYNVEIL_RECOVERY_RESET_WILL_REPLACE_PASSWORD");
    out("SYNVEIL_RECOVERY_RESET_DATA_UNTOUCHED");
    out("SYNVEIL_RECOVERY_RESET_CONFIRM_PROMPT");
    let confirmed = match read_line(&mut reader, MAX_COMMAND_LINE) {
        Line::Text(line) => line.as_slice() == b"confirm",
        _ => false,
    };
    if !confirmed {
        out("SYNVEIL_RECOVERY_RESET_ABORTED");
        let _ = recovery::append_audit("reset-session-end", "result=aborted");
        return ExitCode::SUCCESS;
    }
    if !set_echo(false) {
        out("SYNVEIL_RECOVERY_RESET_UNAVAILABLE");
        return ExitCode::FAILURE;
    }
    out("SYNVEIL_RECOVERY_RESET_PASSWORD_PROMPT");
    let first = read_line(&mut reader, MAX_PASSWORD_LINE);
    out("SYNVEIL_RECOVERY_RESET_PASSWORD_CONFIRM_PROMPT");
    let second = read_line(&mut reader, MAX_PASSWORD_LINE);
    let _ = set_echo(true);
    let (Line::Text(mut password), Line::Text(mut repeated)) = (first, second) else {
        out("SYNVEIL_RECOVERY_RESET_PASSWORD_REJECTED");
        let _ = recovery::append_audit("reset-session-end", "result=password-rejected");
        return ExitCode::SUCCESS;
    };
    if password != repeated || password.len() < 8 || password.len() > MAX_PASSWORD_LINE {
        secret::clear(&mut password);
        secret::clear(&mut repeated);
        out("SYNVEIL_RECOVERY_RESET_PASSWORD_REJECTED");
        let _ = recovery::append_audit("reset-session-end", "result=password-rejected");
        return ExitCode::SUCCESS;
    }
    secret::clear(&mut repeated);
    // The confirmation audit entry gates the mutation (section 10):
    // if it cannot be written, nothing changes.
    if recovery::append_audit(
        "reset-confirmed",
        &format!("generation={}", record.generation),
    )
    .is_err()
    {
        secret::clear(&mut password);
        out("SYNVEIL_RECOVERY_RESET_UNAVAILABLE");
        return ExitCode::FAILURE;
    }
    // The crash-consistent reset transaction (journal, replacement,
    // revocation — see veil_core::recovery). Decision D7: the used
    // factor is revoked; re-enrollment happens in the new session
    // under normal authentication. Success is reported only when
    // the replacement AND the revocation are both durable.
    let outcome = recovery::execute_reset_transaction(recovery::now_unix(), || {
        replace_root_credential(&password)
    });
    secret::clear(&mut password);
    match outcome {
        Ok(recovery::ResetTransactionOutcome::Completed { revoked_generation }) => {
            let _ = recovery::append_audit("password-replaced", "");
            let _ = recovery::append_audit(
                "factor-revoked",
                &format!("generation={revoked_generation}"),
            );
            let _ = recovery::append_audit("reset-completed", "");
            out("SYNVEIL_RECOVERY_RESET_OK");
            out("SYNVEIL_RECOVERY_RESET_DONE");
            ExitCode::SUCCESS
        }
        Ok(recovery::ResetTransactionOutcome::Aborted) => {
            // The replacement failed atomically; nothing changed
            // and the factor remains valid.
            out("SYNVEIL_RECOVERY_RESET_FAILED");
            let _ = recovery::append_audit("reset-failed", "stage=password-replace");
            ExitCode::FAILURE
        }
        Ok(recovery::ResetTransactionOutcome::Incomplete) => {
            // The password WAS replaced; the revocation could not
            // be made durable in this session. The journal remains
            // and keeps the used factor dead; the next entry into
            // this program completes the revocation. This is a
            // failure outcome, never a success.
            let _ = recovery::append_audit("password-replaced", "");
            let _ = recovery::append_audit("reset-incomplete", "stage=revocation");
            out("SYNVEIL_RECOVERY_RESET_INCOMPLETE");
            ExitCode::FAILURE
        }
        Err(_) => {
            // The transaction could not even be journaled (or its
            // preconditions no longer hold): nothing was mutated.
            out("SYNVEIL_RECOVERY_RESET_UNAVAILABLE");
            let _ = recovery::append_audit("reset-failed", "stage=journal");
            ExitCode::FAILURE
        }
    }
}

fn verify_restore_postcondition(result: &serde_json::Value) -> bool {
    let Ok(layout) = ab::Layout::load() else {
        return false;
    };
    let Ok(control) = ab::load_control(&layout) else {
        return false;
    };
    match result.get("reason").and_then(|v| v.as_str()) {
        Some("pending-trial-discarded") => control.trial.is_none(),
        _ => {
            let Some(trial) = control.trial.as_ref() else {
                return false;
            };
            let generation = trial.generation();
            Some(generation.slot.as_str()) == result.get("selected_slot").and_then(|v| v.as_str())
                && Some(generation.version) == result.get("version").and_then(|v| v.as_u64())
                && trial.attempts == ab::TRIAL_ATTEMPTS
        }
    }
}
