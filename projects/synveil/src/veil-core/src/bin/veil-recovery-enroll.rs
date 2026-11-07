// SPDX-License-Identifier: MPL-2.0
//! First-owner enrollment of the ADR 0010 tier 4 recovery factor
//! (specification section 6, decisions in ADR 0020).
//!
//! This is a trusted-context, interactive tool: it runs on the
//! local console during first-owner enrollment, after the password
//! has been enrolled, and refuses non-terminal input or output —
//! the factor must be displayed to the owner on this console and
//! confirmed interactively, never piped, scripted, or generated as
//! a side effect of password enrollment.
//!
//! Flow: an explicit proceed choice; generation from operating
//! system entropy; a single display of the grouped key (with a
//! local print action when a local printer device is already
//! present — a direct device write, never a network queue); the
//! owner's confirmation by re-entering the check group and the
//! designated middle group plus an explicit confirmation; and only
//! then the atomic commit of the recovery record and, on first
//! enrollment, the installation anchor. Declining commits nothing
//! and leaves the honest persistent state "no recovery factor
//! enrolled" (decision D5). A factor whose recording is not
//! confirmed is discarded and never committed (section 6 step 5).
//! After a successful commit nothing can display the factor again:
//! only its Argon2id record exists.
//!
//! This tool enrolls the FIRST factor only. Rotation, revocation
//! and re-enrollment after a reset live in the authenticated
//! maintenance session (`veil-recovery`, command `rotate`), under
//! normal authentication, per specification section 7.

use std::io::{self, BufRead, BufReader, IsTerminal, Write};
use std::process::{Command, ExitCode};
use veil_core::credential::{RootCredentialState, root_credential_state};
use veil_core::recovery::{self, AnchorState, RecoveryFactorState};
use veil_core::secret;

const MAX_LINE: usize = 128;
const MAX_DISCARDS: u32 = 8;

fn audit(event: &str, fields: &str) -> Result<(), io::Error> {
    recovery::append_audit(event, fields)
}

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

fn group_matches(line: &[u8], expected: &str) -> bool {
    let folded: Vec<u8> = line
        .iter()
        .copied()
        .filter(|byte| !byte.is_ascii_whitespace())
        .map(|byte| byte.to_ascii_uppercase())
        .collect();
    folded == expected.as_bytes()
}

fn refused(reason: &str) -> ExitCode {
    out(&format!("SYNVEIL_RECOVERY_ENROLL_REFUSED reason={reason}"));
    ExitCode::FAILURE
}

fn main() -> ExitCode {
    let mut args = std::env::args_os().skip(1);
    if args.next().is_some() {
        eprintln!("usage: veil-recovery-enroll (no arguments; interactive local console only)");
        return ExitCode::FAILURE;
    }
    if !io::stdin().is_terminal() || !io::stdout().is_terminal() {
        eprintln!("[synveil-recovery-enroll] refusing non-terminal session");
        return ExitCode::FAILURE;
    }
    out("SYNVEIL_RECOVERY_ENROLL_V1");
    // The factor step slots in after password enrollment (section
    // 6) and only ever creates the first factor.
    match root_credential_state() {
        RootCredentialState::Present => {}
        RootCredentialState::NoState => return refused("no-state"),
        RootCredentialState::Absent => return refused("no-credential"),
        RootCredentialState::Invalid => return refused("corrupt-credential"),
    }
    // Settle a reset journal left by an interrupted reset before
    // judging the factor state: completion turns the consumed
    // factor's record into its tombstone, and an unsettleable
    // journal refuses enrollment outright (fail closed).
    match recovery::settle_pending_reset(recovery::now_unix()) {
        Ok(recovery::ResetSettleOutcome::NoJournal) => {}
        Ok(recovery::ResetSettleOutcome::Completed { factor_generation }) => {
            let _ = audit(
                "reset-journal-completed",
                &format!("factor_generation={factor_generation}"),
            );
        }
        Err(_) => {
            let _ = audit("reset-journal-unresolved", "");
            return refused("reset-incomplete");
        }
    }
    match recovery::recovery_factor_state() {
        RecoveryFactorState::Absent => {}
        RecoveryFactorState::NoState => return refused("no-state"),
        RecoveryFactorState::Invalid => return refused("corrupt-record"),
        RecoveryFactorState::Active { .. } | RecoveryFactorState::Revoked { .. } => {
            return refused("already-enrolled");
        }
    }
    let (anchor_id, anchor_pending) = match recovery::anchor_state() {
        AnchorState::Present(id) => (id, false),
        AnchorState::Absent => match recovery::random_installation_id() {
            Ok(id) => (id, true),
            Err(_) => return refused("entropy"),
        },
        _ => return refused("anchor-state"),
    };

    let mut reader = BufReader::new(io::stdin());
    out("A recovery key is about to be created for this installation.");
    out("It will be shown exactly once. It is the only way to reset a");
    out("forgotten password; Synveil cannot show it again or replace");
    out("it while you are locked out. Record it on paper and keep it");
    out("with your other physical recovery material.");
    out("SYNVEIL_RECOVERY_ENROLL_PROCEED_PROMPT");
    match read_line(&mut reader, MAX_LINE) {
        Line::Text(line) if line.as_slice() == b"enroll" => {}
        Line::Eof => return ExitCode::SUCCESS,
        _ => {
            let _ = audit("factor-enrollment-declined", "");
            out("SYNVEIL_RECOVERY_ENROLL_DECLINED");
            out("SYNVEIL_RECOVERY_FACTOR_NOT_ENROLLED");
            return ExitCode::SUCCESS;
        }
    }

    let mut discards = 0u32;
    loop {
        let mut factor = match recovery::generate_factor() {
            Ok(factor) => factor,
            Err(_) => return refused("entropy"),
        };
        out("SYNVEIL_RECOVERY_FACTOR_DISPLAY_BEGIN");
        out(&factor.display.grouped);
        out("SYNVEIL_RECOVERY_FACTOR_DISPLAY_END");
        offer_print(&mut reader, &factor.display.grouped);
        if !set_echo(false) {
            factor.clear();
            out("SYNVEIL_RECOVERY_ENROLL_UNAVAILABLE");
            return ExitCode::FAILURE;
        }
        out("SYNVEIL_RECOVERY_ENROLL_CHECK_GROUP_PROMPT");
        let check = read_line(&mut reader, MAX_LINE);
        out("SYNVEIL_RECOVERY_ENROLL_MIDDLE_GROUP_PROMPT");
        let middle = read_line(&mut reader, MAX_LINE);
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
        let confirmed = if groups_ok {
            out("SYNVEIL_RECOVERY_ENROLL_CONFIRM_PROMPT");
            match read_line(&mut reader, MAX_LINE) {
                Line::Text(line) => line.as_slice() == b"confirm",
                _ => false,
            }
        } else {
            out("SYNVEIL_RECOVERY_ENROLL_CONFIRMATION_FAILED");
            false
        };
        if !confirmed {
            factor.clear();
            discards += 1;
            let _ = audit("factor-discarded", &format!("count={discards}"));
            out("SYNVEIL_RECOVERY_ENROLL_DISCARDED");
            if discards >= MAX_DISCARDS {
                out("SYNVEIL_RECOVERY_FACTOR_NOT_ENROLLED");
                return ExitCode::SUCCESS;
            }
            out("SYNVEIL_RECOVERY_ENROLL_AGAIN_PROMPT");
            match read_line(&mut reader, MAX_LINE) {
                Line::Text(line) if line.as_slice() == b"again" => continue,
                _ => {
                    out("SYNVEIL_RECOVERY_FACTOR_NOT_ENROLLED");
                    return ExitCode::SUCCESS;
                }
            }
        }
        // The confirmation audit entry is written before the record
        // exists; if the audit store refuses it, nothing is
        // committed (specification section 10's discipline).
        if audit("factor-enrollment-confirmed", "generation=1").is_err() {
            factor.clear();
            return refused("audit");
        }
        if anchor_pending && recovery::write_anchor(&anchor_id, recovery::now_unix()).is_err() {
            factor.clear();
            let _ = audit("factor-enrollment-failed", "stage=anchor-write");
            return refused("anchor-write");
        }
        let committed = recovery::commit_factor(&factor.key, &anchor_id, 1, recovery::now_unix());
        factor.clear();
        if committed.is_err() {
            let _ = audit("factor-enrollment-failed", "stage=record-write");
            return refused("record-write");
        }
        out("SYNVEIL_RECOVERY_ENROLL_OK generation=1");
        return ExitCode::SUCCESS;
    }
}

/// Offer the section 6 print action only when a local printer
/// device is already present; the key text is written directly to
/// the device. There is no spooler in the enrollment environment
/// and a network printer queue is never used (decision D3).
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
    match read_line(reader, MAX_LINE) {
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
