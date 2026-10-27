#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""QEMU acceptance for ADR 0010 tier 4: the recovery factor.

Implements the guest evidence for specification section 11 on the
fixture substrate (dedicated fixture images staged from the native
rootfs, disposable state disks, serial console):

  t1 wrong factor denied, attempts counted, lockout persists
  t2 correct factor resets; only the new password authenticates
     after a cold reboot (credential-authority level, via the
     maintenance session's shared ADR 0009 verifier; a graphical
     desktop session login is NOT exercised by this driver)
  t3 cross-installation factors and records denied both directions
  t4 copied STATE credential directory alone (no anchor) denied
  t5 corrupt record variants denied without crash/hang/fallback
  t6 corrupt/missing/foreign anchor denied, nothing initialized
  t7 rotation: old factor denied, new factor verifies, cold reboots
  t8 a factor used in a successful reset is revoked (decision D7)
  t9 audit entries present, no secret material in the log
  t10 serial probes get no shell at any locked stage
  t12 no interface re-displays a factor; factors appear only inside
      their single display window (transcript accounting below)
  t13 all boots run with QEMU networking disabled (-net none)

Section 11 test 11 (DATA partition integrity) lives in
tests/smoke-recovery-factor-ab.py on the A/B substrate.

Factors are generated inside the guest by veil-recovery-enroll /
the maintenance rotate command, captured from the one-time display
in the serial transcript, held in memory only, and never written
to the verdict. Synthetic fixture passwords only.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "recovery-factor-smoke"
BOOT_TIMEOUT = 240
VERIFY_TIMEOUT = 300

_spec = importlib.util.spec_from_file_location(
    "smoke_recovery_maint", ROOT / "tests" / "smoke-recovery-maint.py")
maint_smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(maint_smoke)
SerialBoot = maint_smoke.SerialBoot
probe_locked = maint_smoke.probe_locked
create_state_disk = maint_smoke.create_state_disk

PASSWORD_A = "synveil-factor-fixture-3d7a1c"
PASSWORD_B = "synveil-factor-fixture-9e2b4d"
PASSWORD_NEW = "synveil-factor-fixture-new-5f8c2a"
PASSWORD_NEW2 = "synveil-factor-fixture-new-71bd09"
WRONG_PASSWORD = maint_smoke.WRONG

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
BOOTS = []          # every SerialBoot, for the test-12 accounting
FACTORS = {}        # grouped string -> (origin boot name, display line idx)


# ------------------------------------------------------------------
# Fixture images
# ------------------------------------------------------------------

def build_fixture(case, mode):
    work = ROOT / "build" / "work"
    rootfs = work / "rootfs"
    for binary in ("veil-recovery", "veil-recovery-enroll"):
        if not (rootfs / "usr/sbin" / binary).is_file():
            raise RuntimeError(f"build a native rootfs containing {binary} first")
    staging = OUT / "staging" / case
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    tree = staging / "rootfs"
    shutil.copytree(rootfs, tree, symlinks=True)
    if mode == "enroll":
        debug = tree / "etc/synveil/developer-serial-recovery"
        debug.parent.mkdir(parents=True, exist_ok=True)
        debug.touch(exist_ok=False)
        debug.chmod(0o644)
    else:
        marker = tree / "etc/synveil/auth-desktop"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch(exist_ok=False)
        marker.chmod(0o644)
        debug = tree / "etc/synveil/developer-serial-recovery"
        if debug.exists() or debug.is_symlink():
            raise RuntimeError("unexpected developer recovery marker")
    fixture_out = OUT / "fixtures" / case
    fixture_out.mkdir(parents=True, exist_ok=True)
    with (fixture_out / "synveil-initramfs.cpio").open("wb") as packed:
        subprocess.run(["bash", "-o", "pipefail", "-c",
                        "find . -print0 | sort -z | cpio --null -o "
                        "--format=newc --owner=0:0"],
                       cwd=tree, stdout=packed, check=True)
    env = {**os.environ, "SYNVEIL_OUT_DIR": str(fixture_out),
           "SYNVEIL_WORK_DIR": str(staging / "build"),
           "SYNVEIL_KERNEL_SEED_WORK": str(work)}
    if mode == "maint":
        env["SYNVEIL_KERNEL_TEST_RECOVERY_MAINT"] = "1"
    if mode == "reset":
        env["SYNVEIL_KERNEL_TEST_RECOVERY_RESET"] = "1"
    for name in ("kernel", "image"):
        subprocess.run(["bash", str(ROOT / "build/scripts" / (name + ".sh"))],
                       env=env, check=True)
    identity = {"case": case, "git_commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "artifacts": {}}
    for name in ("synveil-initramfs.cpio", "synveil-x86_64.efi",
                 "synveil-x86_64.img"):
        path = fixture_out / name
        identity["artifacts"][name] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size}
    (fixture_out / "fixture.json").write_text(
        json.dumps(identity, indent=2) + "\n")
    return fixture_out


def boot(name, fixture, disk=None):
    instance = SerialBoot(name, fixture, disk)
    BOOTS.append(instance)
    return instance


# ------------------------------------------------------------------
# Host-side state filesystem surgery (standalone state disk, GPT
# partition 1). The journal is always replayed before host edits:
# unreplayed journals silently discard them (2026-10-27 lesson).
# ------------------------------------------------------------------

def run(*argv, **kwargs):
    return subprocess.run(argv, check=True, capture_output=True,
                          text=True, **kwargs)


def partition_span(disk, number):
    info = run("sgdisk", "-i", str(number), str(disk)).stdout
    first = size = None
    for line in info.splitlines():
        if "First sector:" in line:
            first = int(line.split(":", 1)[1].split()[0])
        if "Partition size:" in line:
            size = int(line.split(":", 1)[1].split()[0])
    if first is None or size is None:
        raise RuntimeError(f"partition {number} span not found")
    return first, size


def extract_partition(disk, number, dest):
    first, size = partition_span(disk, number)
    run("dd", f"if={disk}", f"of={dest}", "bs=512", f"skip={first}",
        f"count={size}", "conv=notrunc", "status=none")
    return dest


def write_partition(disk, number, image):
    first, _size = partition_span(disk, number)
    run("dd", f"if={image}", f"of={disk}", "bs=512", f"seek={first}",
        "conv=notrunc", "status=none")


def replay_journal(image):
    result = subprocess.run(["e2fsck", "-fy", str(image)],
                            capture_output=True, text=True)
    if result.returncode not in (0, 1, 2):
        raise RuntimeError(f"e2fsck {image}: {result.stdout} {result.stderr}")


def state_image(disk, tag):
    img = OUT / f"statefs-{tag}.img"
    extract_partition(disk, 1, img)
    replay_journal(img)
    return img


def debugfs_read(image, guest_path):
    result = subprocess.run(["debugfs", "-R", f"cat {guest_path}",
                             str(image)], capture_output=True)
    if result.returncode != 0:
        return None
    return result.stdout


def state_read(disk, tag, guest_path):
    return debugfs_read(state_image(disk, tag), guest_path)


def state_write_file(disk, tag, guest_path, data):
    img = state_image(disk, tag)
    tmp = OUT / f"tmp-{tag}.bin"
    tmp.write_bytes(data)
    subprocess.run(["debugfs", "-w", "-R", f"rm {guest_path}", str(img)],
                   capture_output=True)
    run("debugfs", "-w", "-R", f"write {tmp} {guest_path}", str(img))
    # debugfs write copies the host file's permissions; the guest's
    # strict readers demand 0600, so pin it explicitly — a case must
    # fail for its own reason, never for a host-side artifact.
    run("debugfs", "-w", "-R", f"sif {guest_path} mode 0100600", str(img))
    write_partition(disk, 1, img)


def state_delete(disk, tag, guest_path):
    img = state_image(disk, tag)
    run("debugfs", "-w", "-R", f"rm {guest_path}", str(img))
    write_partition(disk, 1, img)


def state_chmod(disk, tag, guest_path, mode):
    img = state_image(disk, tag)
    run("debugfs", "-w", "-R", f"sif {guest_path} mode {mode}", str(img))
    write_partition(disk, 1, img)


def state_symlink(disk, tag, guest_path, target):
    img = state_image(disk, tag)
    run("debugfs", "-w", "-R", f"rm {guest_path}", str(img))
    run("debugfs", "-w", "-R", f"symlink {guest_path} {target}", str(img))
    write_partition(disk, 1, img)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------
# Factor arithmetic (mirror of veil-core recovery.rs encoding)
# ------------------------------------------------------------------

def encode_factor(key):
    chars = []
    acc = 0
    nbits = 0
    for byte in key:
        acc = (acc << 8) | byte
        nbits += 8
        while nbits >= 5:
            nbits -= 5
            chars.append(CROCKFORD[(acc >> nbits) & 0x1F])
        acc &= (1 << nbits) - 1
    if nbits > 0:
        chars.append(CROCKFORD[(acc << (5 - nbits)) & 0x1F])
    digest = hashlib.sha256(key).digest()
    value = (digest[0] << 12) | (digest[1] << 4) | (digest[2] >> 4)
    check = "".join(CROCKFORD[(value >> shift) & 0x1F]
                    for shift in (15, 10, 5, 0))
    groups = ["".join(chars[i:i + 4]) for i in range(0, 52, 4)]
    return "-".join(groups + [check])


def wrong_factor():
    return encode_factor(os.urandom(32))


def transcription_variant(grouped):
    chars = list(grouped)
    # Group 2 (chars 10..13 in the hyphenated form): outside the
    # check group, inside the key, canonical padding untouched.
    chars[10] = "A" if chars[10] != "A" else "B"
    return "".join(chars)


def alter_group(group):
    return ("A" if group[0] != "A" else "B") + group[1:]


# ------------------------------------------------------------------
# Serial interaction helpers
# ------------------------------------------------------------------

def capture_display(instance, begin_marker, end_marker):
    """Return (grouped, line_index) of the factor display, or None."""
    deadline = time.monotonic() + BOOT_TIMEOUT
    while time.monotonic() < deadline:
        with instance._lock:
            lines = list(instance.lines)
        for i, line in enumerate(lines):
            if begin_marker in line and i + 1 < len(lines):
                grouped = lines[i + 1].strip()
                groups = grouped.split("-")
                if (len(groups) == 14
                        and all(len(g) == 4 for g in groups)
                        and all(c in CROCKFORD for g in groups for c in g)):
                    return grouped, i + 1
        if instance.process.poll() is not None:
            return None
        time.sleep(0.2)
    return None


def register_factor(grouped, instance, line_index):
    FACTORS[grouped] = (instance.name, line_index)


def handle_print_offer(instance):
    """Answer the local-print offer if one is made (fixture QEMU
    normally has no printer device, so the offer is unavailable)."""
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if instance.seen("SYNVEIL_RECOVERY_FACTOR_PRINT_PROMPT"):
            instance.send("skip")
            return
        if instance.seen("SYNVEIL_RECOVERY_FACTOR_PRINT_UNAVAILABLE"):
            return
        if instance.seen("SYNVEIL_RECOVERY_FACTOR_PRINT_SKIPPED"):
            return
        time.sleep(0.2)


def enroll_password(instance, password):
    if not instance.wait("Recovery/bootstrap shell"):
        return False
    instance.send("stty -echo")
    time.sleep(1)
    instance.send(f"printf '%s' '{password}' | "
                  "/usr/sbin/veil-enroll --password-stdin")
    ok = instance.wait("SYNVEIL_CREDENTIAL_ENROLLED", 180)
    instance.send("stty echo")
    time.sleep(1)
    return ok


def enroll_factor(instance):
    """Drive veil-recovery-enroll to a committed factor; return the
    grouped factor string, or None."""
    instance.send("/usr/sbin/veil-recovery-enroll")
    if not instance.wait("SYNVEIL_RECOVERY_ENROLL_PROCEED_PROMPT", 120):
        return None
    instance.send("enroll")
    captured = capture_display(
        instance, "SYNVEIL_RECOVERY_FACTOR_DISPLAY_BEGIN",
        "SYNVEIL_RECOVERY_FACTOR_DISPLAY_END")
    if captured is None:
        return None
    grouped, line_index = captured
    groups = grouped.split("-")
    handle_print_offer(instance)
    if not instance.wait("SYNVEIL_RECOVERY_ENROLL_CHECK_GROUP_PROMPT", 60):
        return None
    instance.send(groups[13])
    if not instance.wait("SYNVEIL_RECOVERY_ENROLL_MIDDLE_GROUP_PROMPT", 60):
        return None
    instance.send(groups[6])
    if not instance.wait("SYNVEIL_RECOVERY_ENROLL_CONFIRM_PROMPT", 60):
        return None
    instance.send("confirm")
    if not instance.wait("SYNVEIL_RECOVERY_ENROLL_OK generation=1",
                         VERIFY_TIMEOUT):
        return None
    register_factor(grouped, instance, line_index)
    return grouped


def poweroff(instance):
    instance.send("poweroff -f")
    time.sleep(3)
    instance.stop()


def locked_and_probed(instance):
    ok = instance.wait("SYNVEIL_SERIAL_RECOVERY_LOCKED")
    ok = ok and probe_locked(instance)
    instance.stop()
    return ok


# ------------------------------------------------------------------
# Case helpers
# ------------------------------------------------------------------

RECORD_PATH = "/lib/synveil/auth/recovery.json"
CREDENTIAL_PATH = "/lib/synveil/auth/credential.phc"
ANCHOR_PATH = "/lib/synveil/installation-anchor.json"
AUDIT_PATH = "/log/synveil/recovery-maintenance.log"


def fresh_disk(name):
    disk = OUT / f"{name}.img"
    disk.unlink(missing_ok=True)
    create_state_disk(disk, 128)
    return disk


def clone(base, name):
    disk = OUT / f"{name}.img"
    shutil.copyfile(base, disk)
    return disk


def reset_denied_preinput(name, fixture, disk, reason):
    """Boot the reset entry expecting refusal before any prompt."""
    instance = boot(name, fixture, disk)
    ok = instance.wait(f"SYNVEIL_RECOVERY_RESET_DENIED reason={reason}")
    transcript = instance.transcript()
    ok = ok and "SYNVEIL_RECOVERY_RESET_FACTOR_PROMPT" not in transcript
    ok = ok and "SYNVEIL_RECOVERY_RESET_VERIFIED" not in transcript
    ok = ok and locked_and_probed(instance)
    return ok


def maint_auth(instance, password):
    ok = instance.wait("SYNVEIL_RECOVERY_MAINT_PASSWORD_PROMPT")
    instance.send(password)
    ok = ok and instance.wait("SYNVEIL_RECOVERY_MAINT_AUTH_OK", VERIFY_TIMEOUT)
    ok = ok and instance.wait("SYNVEIL_RECOVERY_MAINT_READY", 60)
    return ok


def rotate_flow(instance, confirm_line):
    """Drive the rotate command; return (grouped, ok-so-far)."""
    instance.send("rotate")
    captured = capture_display(
        instance, "SYNVEIL_RECOVERY_ROTATE_DISPLAY_BEGIN",
        "SYNVEIL_RECOVERY_ROTATE_DISPLAY_END")
    if captured is None:
        return None, False
    grouped, line_index = captured
    register_factor(grouped, instance, line_index)
    groups = grouped.split("-")
    handle_print_offer(instance)
    ok = instance.wait("SYNVEIL_RECOVERY_ROTATE_CHECK_GROUP_PROMPT", 60)
    instance.send(groups[13])
    ok = ok and instance.wait(
        "SYNVEIL_RECOVERY_ROTATE_MIDDLE_GROUP_PROMPT", 60)
    instance.send(groups[6])
    ok = ok and instance.wait("SYNVEIL_RECOVERY_ROTATE_CONFIRM_PROMPT", 60)
    instance.send(confirm_line)
    return grouped, ok


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    maint_smoke.OUT = OUT
    os.environ.pop("SYNVEIL_QEMU_NETWORK", None)
    results = {}
    fx_enroll = build_fixture("enroll", "enroll")
    fx_maint = build_fixture("maint", "maint")
    fx_reset = build_fixture("reset", "reset")

    # ---- Section 6 decline + discard paths (decision D5) ----
    disk = fresh_disk("decline")
    b = boot("decline", fx_enroll, disk)
    ok = enroll_password(b, PASSWORD_A)
    b.send("/usr/sbin/veil-recovery-enroll")
    ok = ok and b.wait("SYNVEIL_RECOVERY_ENROLL_PROCEED_PROMPT", 120)
    b.send("later")
    ok = ok and b.wait("SYNVEIL_RECOVERY_ENROLL_DECLINED", 60)
    ok = ok and b.wait("SYNVEIL_RECOVERY_FACTOR_NOT_ENROLLED", 60)
    b.send("/usr/sbin/veil-recovery-enroll")
    ok = ok and b.wait("SYNVEIL_RECOVERY_ENROLL_PROCEED_PROMPT", 120)
    b.send("enroll")
    captured = capture_display(
        b, "SYNVEIL_RECOVERY_FACTOR_DISPLAY_BEGIN",
        "SYNVEIL_RECOVERY_FACTOR_DISPLAY_END")
    if captured is None:
        ok = False
    else:
        grouped_d, line_index = captured
        register_factor(grouped_d, b, line_index)
        groups = grouped_d.split("-")
        handle_print_offer(b)
        ok = ok and b.wait("SYNVEIL_RECOVERY_ENROLL_CHECK_GROUP_PROMPT", 60)
        b.send(alter_group(groups[13]))
        ok = ok and b.wait("SYNVEIL_RECOVERY_ENROLL_MIDDLE_GROUP_PROMPT", 60)
        b.send(alter_group(groups[6]))
        ok = ok and b.wait("SYNVEIL_RECOVERY_ENROLL_CONFIRMATION_FAILED", 60)
        ok = ok and b.wait("SYNVEIL_RECOVERY_ENROLL_DISCARDED", 60)
        ok = ok and b.wait("SYNVEIL_RECOVERY_ENROLL_AGAIN_PROMPT", 60)
        b.send("stop")
        ok = ok and b.wait("SYNVEIL_RECOVERY_FACTOR_NOT_ENROLLED", 60)
    poweroff(b)
    ok = ok and state_read(disk, "decline", RECORD_PATH) is None
    ok = ok and state_read(disk, "decline", ANCHOR_PATH) is None
    results["s6-decline-and-discard"] = ok

    # ---- Installation 1: password + factor, pristine snapshot ----
    disk1 = fresh_disk("install1")
    b = boot("enroll-install1", fx_enroll, disk1)
    ok = enroll_password(b, PASSWORD_A)
    f1 = enroll_factor(b) if ok else None
    ok = ok and f1 is not None
    if ok:
        b.send("cat /var/lib/synveil/auth/recovery.json; "
               "echo SYNVEIL_RECORD_SHOWN")
        ok = ok and b.wait("SYNVEIL_RECORD_SHOWN", 60)
        ok = ok and "synveil.recovery-record/v1" in b.transcript()
        b.send("cat /var/log/synveil/recovery-maintenance.log; "
               "echo SYNVEIL_AUDIT_SHOWN")
        ok = ok and b.wait("SYNVEIL_AUDIT_SHOWN", 60)
        ok = ok and "event=factor-enrollment-confirmed" in b.transcript()
    poweroff(b)
    results["enroll-install1"] = ok
    base1 = OUT / "install1-base.img"
    shutil.copyfile(disk1, base1)

    # ---- Installation 2: independent password + factor ----
    disk2 = fresh_disk("install2")
    b = boot("enroll-install2", fx_enroll, disk2)
    ok = enroll_password(b, PASSWORD_B)
    f3 = enroll_factor(b) if ok else None
    ok = ok and f3 is not None
    poweroff(b)
    results["enroll-install2"] = ok
    base2 = OUT / "install2-base.img"
    shutil.copyfile(disk2, base2)
    if f1 is None or f3 is None:
        raise RuntimeError("enrollment failed; cannot continue")

    # ---- Test 3a: installation 2's factor presented to 1 ----
    d = clone(base1, "cross-factor-1")
    b = boot("cross-factor-1", fx_reset, d)
    ok = b.wait("SYNVEIL_RECOVERY_RESET_FACTOR_PROMPT")
    b.send(f3)
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_ATTEMPT_DENIED attempt=1",
                       VERIFY_TIMEOUT)
    b.send(f3)
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_ATTEMPT_DENIED attempt=2",
                       VERIFY_TIMEOUT)
    b.send(f1)
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_VERIFIED", VERIFY_TIMEOUT)
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_CONFIRM_PROMPT", 60)
    b.send("abort")
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_ABORTED", 60)
    ok = ok and locked_and_probed(b)
    results["t3-cross-factor-a"] = ok

    # ---- Test 3b: installation 1's factor presented to 2 ----
    d = clone(base2, "cross-factor-2")
    b = boot("cross-factor-2", fx_reset, d)
    ok = b.wait("SYNVEIL_RECOVERY_RESET_FACTOR_PROMPT")
    for n in (1, 2, 3):
        b.send(f1)
        ok = ok and b.wait(
            f"SYNVEIL_RECOVERY_RESET_ATTEMPT_DENIED attempt={n}",
            VERIFY_TIMEOUT)
    ok = ok and "SYNVEIL_RECOVERY_RESET_VERIFIED" not in b.transcript()
    ok = ok and locked_and_probed(b)
    results["t3-cross-factor-b"] = ok

    # ---- Test 3c/3d: transplanted records denied pre-input ----
    rec1 = state_read(base1, "xrec1", RECORD_PATH)
    rec2 = state_read(base2, "xrec2", RECORD_PATH)
    d = clone(base1, "cross-record-1")
    state_write_file(d, "cross-record-1", RECORD_PATH, rec2)
    results["t3-cross-record-a"] = reset_denied_preinput(
        "cross-record-1", fx_reset, d, "anchor-mismatch")
    d = clone(base2, "cross-record-2")
    state_write_file(d, "cross-record-2", RECORD_PATH, rec1)
    results["t3-cross-record-b"] = reset_denied_preinput(
        "cross-record-2", fx_reset, d, "anchor-mismatch")

    # ---- Test 4: copied STATE directory alone (anchor removed) ----
    d = clone(base1, "copied-state")
    before_rec = sha256_bytes(state_read(d, "cs-before", RECORD_PATH))
    before_cred = sha256_bytes(state_read(d, "cs-before", CREDENTIAL_PATH))
    state_delete(d, "copied-state", ANCHOR_PATH)
    results["t4-copied-state-no-anchor"] = reset_denied_preinput(
        "copied-state", fx_reset, d, "no-anchor")
    ok = state_read(d, "cs-after", ANCHOR_PATH) is None
    ok = ok and sha256_bytes(
        state_read(d, "cs-after", RECORD_PATH)) == before_rec
    ok = ok and sha256_bytes(
        state_read(d, "cs-after", CREDENTIAL_PATH)) == before_cred
    results["t4-nothing-initialized"] = ok

    # ---- Test 5: corrupt record variants ----
    raw = rec1
    flip = raw.rfind(b"$")
    v_tagflip = (raw[:flip + 1]
                 + (b"A" if raw[flip + 1:flip + 2] != b"A" else b"B")
                 + raw[flip + 2:])
    v_cost = raw.replace(b"m=65536", b"m=999999999")
    phc_start = raw.index(b"$argon2id")
    phc_end = raw.index(b'"', phc_start)
    v_truncated = raw[:phc_start + 20] + raw[phc_end:]
    d = clone(base1, "corrupt-tagflip")
    state_write_file(d, "ctag", RECORD_PATH, v_tagflip)
    b = boot("corrupt-tagflip", fx_reset, d)
    ok = b.wait("SYNVEIL_RECOVERY_RESET_FACTOR_PROMPT")
    for n in (1, 2, 3):
        b.send(f1)
        ok = ok and b.wait(
            f"SYNVEIL_RECOVERY_RESET_ATTEMPT_DENIED attempt={n}",
            VERIFY_TIMEOUT)
    ok = ok and "SYNVEIL_RECOVERY_RESET_VERIFIED" not in b.transcript()
    ok = ok and locked_and_probed(b)
    results["t5-tag-flip"] = ok
    for name, data in (("corrupt-cost", v_cost),
                       ("corrupt-truncated", v_truncated)):
        d = clone(base1, name)
        state_write_file(d, name, RECORD_PATH, data)
        results[f"t5-{name}"] = reset_denied_preinput(
            name, fx_reset, d, "corrupt-record")
    d = clone(base1, "corrupt-perms")
    state_chmod(d, "cperms", RECORD_PATH, "0100644")
    results["t5-permissions"] = reset_denied_preinput(
        "corrupt-perms", fx_reset, d, "corrupt-record")
    d = clone(base1, "corrupt-symlink")
    state_symlink(d, "csym", RECORD_PATH, CREDENTIAL_PATH)
    results["t5-symlink"] = reset_denied_preinput(
        "corrupt-symlink", fx_reset, d, "corrupt-record")

    # ---- Test 6: anchor attacks ----
    anchor2 = state_read(base2, "xa2", ANCHOR_PATH)
    for name, data, reason in (
            ("anchor-corrupt", b"not an anchor\n", "anchor-invalid"),
            ("anchor-foreign", anchor2, "anchor-mismatch")):
        d = clone(base1, name)
        rec_before = sha256_bytes(state_read(d, name + "-b", RECORD_PATH))
        cred_before = sha256_bytes(
            state_read(d, name + "-b", CREDENTIAL_PATH))
        state_write_file(d, name, ANCHOR_PATH, data)
        results[f"t6-{name}"] = reset_denied_preinput(
            name, fx_reset, d, reason)
        ok = sha256_bytes(state_read(d, name + "-a", RECORD_PATH)) \
            == rec_before
        ok = ok and sha256_bytes(
            state_read(d, name + "-a", CREDENTIAL_PATH)) == cred_before
        results[f"t6-{name}-state-untouched"] = ok

    # ---- Test 1: wrong factor denied, counted, locked out ----
    disk = fresh_disk("throttle")
    b = boot("enroll-throttle", fx_enroll, disk)
    ok = enroll_password(b, PASSWORD_A)
    f2 = enroll_factor(b) if ok else None
    ok = ok and f2 is not None
    poweroff(b)
    wrong = wrong_factor()
    b = boot("throttle-1", fx_reset, disk)
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_FACTOR_PROMPT")
    b.send(transcription_variant(f2))
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_TRANSCRIPTION", 120)
    for n in (1, 2, 3):
        b.send(wrong)
        ok = ok and b.wait(
            f"SYNVEIL_RECOVERY_RESET_ATTEMPT_DENIED attempt={n}",
            VERIFY_TIMEOUT)
    ok = ok and locked_and_probed(b)
    b = boot("throttle-2", fx_reset, disk)
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_FACTOR_PROMPT")
    for n in (1, 2, 3):
        b.send(wrong)
        ok = ok and b.wait(
            f"SYNVEIL_RECOVERY_RESET_ATTEMPT_DENIED attempt={n}",
            VERIFY_TIMEOUT)
    ok = ok and locked_and_probed(b)
    results["t1-throttled-after-five"] = reset_denied_preinput(
        "throttle-3", fx_reset, disk, "throttled") and ok

    # ---- Tests 2 + 8: successful reset, D7 revocation, audit ----
    d = clone(base1, "reset-ok")
    b = boot("reset-ok", fx_reset, d)
    ok = b.wait("SYNVEIL_RECOVERY_RESET_FACTOR_PROMPT")
    b.send(f1)
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_VERIFIED", VERIFY_TIMEOUT)
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_CONFIRM_PROMPT", 60)
    b.send("confirm")
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_PASSWORD_PROMPT", 60)
    b.send(PASSWORD_NEW)
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_PASSWORD_CONFIRM_PROMPT", 60)
    b.send(PASSWORD_NEW)
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_OK", VERIFY_TIMEOUT)
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_DONE", 60)
    ok = ok and locked_and_probed(b)
    results["t2-reset"] = ok
    b = boot("reset-ok-maint", fx_maint, d)
    ok = maint_auth(b, PASSWORD_NEW)
    b.send("status")
    status_ok = b.wait(
        "SYNVEIL_RECOVERY_MAINT_FACTOR state=revoked generation=1", 60)
    b.send("exit")
    ok = ok and b.wait("SYNVEIL_RECOVERY_MAINT_DONE", 60)
    ok = ok and locked_and_probed(b)
    results["t2-new-password-authenticates"] = ok
    results["t8-revoked-in-status"] = status_ok
    b = boot("reset-ok-oldpw", fx_maint, d)
    ok = b.wait("SYNVEIL_RECOVERY_MAINT_PASSWORD_PROMPT")
    for n in (1, 2, 3):
        b.send(PASSWORD_A)
        ok = ok and b.wait(f"SYNVEIL_RECOVERY_MAINT_DENIED attempt={n}",
                           VERIFY_TIMEOUT)
    ok = ok and "SYNVEIL_RECOVERY_MAINT_AUTH_OK" not in b.transcript()
    ok = ok and locked_and_probed(b)
    results["t2-old-password-denied"] = ok
    results["t8-used-factor-denied"] = reset_denied_preinput(
        "reset-ok-reused", fx_reset, d, "factor-revoked")
    audit_log = state_read(d, "reset-ok-audit", AUDIT_PATH).decode(
        "utf-8", "replace")
    (OUT / "reset-ok-audit.log").write_text(audit_log)
    ok = all(f"event={event}" in audit_log for event in (
        "factor-enrollment-confirmed", "factor-verification-verified",
        "reset-confirmed", "password-replaced", "factor-revoked",
        "reset-completed", "reset-denied"))
    ok = ok and f1 not in audit_log
    ok = ok and PASSWORD_NEW not in audit_log
    ok = ok and PASSWORD_A not in audit_log
    results["t9-audit-log"] = ok

    # ---- Test 7: rotation ----
    d = clone(base1, "rotation-abort")
    b = boot("rotation-abort", fx_maint, d)
    ok = maint_auth(b, PASSWORD_A)
    _discarded, flow_ok = rotate_flow(b, "no")
    ok = ok and flow_ok
    ok = ok and b.wait("SYNVEIL_RECOVERY_ROTATE_ABORTED", 60)
    b.send("exit")
    ok = ok and b.wait("SYNVEIL_RECOVERY_MAINT_DONE", 60)
    ok = ok and locked_and_probed(b)
    b = boot("rotation-abort-reset", fx_reset, d)
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_FACTOR_PROMPT")
    b.send(f1)
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_VERIFIED", VERIFY_TIMEOUT)
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_CONFIRM_PROMPT", 60)
    b.send("abort")
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_ABORTED", 60)
    ok = ok and locked_and_probed(b)
    results["t7-rotation-abort-keeps-old"] = ok

    d = clone(base1, "rotation")
    b = boot("rotation", fx_maint, d)
    ok = maint_auth(b, PASSWORD_A)
    b.send("status")
    ok = ok and b.wait(
        "SYNVEIL_RECOVERY_MAINT_FACTOR state=active generation=1", 60)
    f_new, flow_ok = rotate_flow(b, "confirm")
    ok = ok and flow_ok and f_new is not None
    ok = ok and b.wait("SYNVEIL_RECOVERY_ROTATE_OK generation=2",
                       VERIFY_TIMEOUT)
    b.send("exit")
    ok = ok and b.wait("SYNVEIL_RECOVERY_MAINT_DONE", 60)
    ok = ok and locked_and_probed(b)
    b = boot("rotation-status", fx_maint, d)
    ok2 = maint_auth(b, PASSWORD_A)
    b.send("status")
    ok2 = ok2 and b.wait(
        "SYNVEIL_RECOVERY_MAINT_FACTOR state=active generation=2", 60)
    b.send("exit")
    ok2 = ok2 and b.wait("SYNVEIL_RECOVERY_MAINT_DONE", 60)
    ok2 = ok2 and locked_and_probed(b)
    results["t7-rotation-committed"] = ok and ok2
    b = boot("rotation-reset", fx_reset, d)
    ok = b.wait("SYNVEIL_RECOVERY_RESET_FACTOR_PROMPT")
    b.send(f1)
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_ATTEMPT_DENIED attempt=1",
                       VERIFY_TIMEOUT)
    b.send(f_new)
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_VERIFIED", VERIFY_TIMEOUT)
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_CONFIRM_PROMPT", 60)
    b.send("confirm")
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_PASSWORD_PROMPT", 60)
    b.send(PASSWORD_NEW2)
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_PASSWORD_CONFIRM_PROMPT", 60)
    b.send(PASSWORD_NEW2)
    ok = ok and b.wait("SYNVEIL_RECOVERY_RESET_OK", VERIFY_TIMEOUT)
    ok = ok and locked_and_probed(b)
    results["t7-old-denied-new-verifies"] = ok

    # ---- Test 12: factor/password appearance accounting ----
    ok = True
    for grouped, (origin, line_index) in FACTORS.items():
        bare = grouped.replace("-", "")
        for instance in BOOTS:
            with instance._lock:
                lines = list(instance.lines)
            for i, line in enumerate(lines):
                if grouped in line or bare in line:
                    if not (instance.name == origin and i == line_index):
                        ok = False
    results["t12-factor-hygiene"] = ok
    ok = all(password not in instance.transcript()
             for password in (PASSWORD_A, PASSWORD_B, PASSWORD_NEW,
                              PASSWORD_NEW2)
             for instance in BOOTS)
    results["t12-password-hygiene"] = ok

    # ---- Test 13: fixture boots run with networking disabled ----
    qemu_script = (ROOT / "build/scripts/qemu.sh").read_text()
    results["t13-network-absent"] = (
        "-net none" in qemu_script
        and "SYNVEIL_QEMU_NETWORK" not in os.environ)

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                     cwd=ROOT, text=True).strip()
    verdict = {"schema": "synveil.recovery-factor-smoke/v1",
               "source_commit": commit,
               "cases": results,
               "factors_redacted": True,
               "secret_in_image": False,
               "physical_hardware_tested": False}
    (OUT / "verdict.json").write_text(json.dumps(verdict, indent=2) + "\n")
    for name, result in results.items():
        print(f"RECOVERY_FACTOR_CASE {name}={'PASS' if result else 'FAIL'}")
    passed = all(results.values())
    print("SYNVEIL_RECOVERY_FACTOR_SMOKE_PASS" if passed
          else "SYNVEIL_RECOVERY_FACTOR_SMOKE_FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
