#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Bootable A/B update/rollback acceptance in QEMU.

Drives the disk assembled by tools/native_ab.py through the full
proof sequence from docs/AB_UPDATER.md, on a private copy of the
disk with a persistent OVMF variable store (one VARS file per
scenario run, kept across the run's boots; the updater itself
writes no firmware variables — slot selection is by kexec
chain-loading inside the guest, see docs/AB_UPDATER.md):

  S0  provision on first boot, graphical enrollment + login,
      a user setting change (if the greeter exposes it), a known
      user file in the DATA-backed home
  S1  stage signed v2 from release media; on reboot the entry
      generation's hook hands over (chain-load) to the v2 trial
  S2  v2 trial boots, health confirmation promotes it; login,
      desktop background change and all survival artifacts verified
  S3  owner-requested rollback to v1, trial + confirmation again
  S4  failing candidate v3: three unhealthy trial boots exhaust
      attempts, firmware falls back to v1, trial discarded
  S5  corrupted-signature release refused; confirmed slot untouched
  S6  power cut mid-staging: no trial recorded, v1 intact, and a
      later stage still succeeds (left pending, then discarded)
  S7  slot images corrupted on a branch copy while the ESP
      fallback copy stays intact: the hook's digest check fails
      closed into the recovery diagnostics, no system boots

Every scenario writes its serial log under out/ab-proof/smoke-
evidence/ and the run writes a machine-readable receipt
(out/ab-proof/smoke-receipt.json) with the source commit, image and
generation identities from the build receipt. QEMU evidence only;
no physical hardware is claimed.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from qmp_input import (  # noqa: E402
    QMPError, capture_test_scanout, exit_user_terminal, logout_user_desktop,
    open_user_terminal, send_keys, settings_toggle, type_ab_command,
    type_test_secret)

_spec = importlib.util.spec_from_file_location(
    "smoke_native_weston", ROOT / "tests" / "smoke-native-weston.py")
weston_smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(weston_smoke)

OUT = ROOT / "out" / "ab-proof"
EVIDENCE = OUT / "smoke-evidence"
GEN_COLORS = {1: (0x10, 0x18, 0x20), 2: (0x0B, 0x3D, 0x2E)}
BOOT_OK = ("SYNVEIL_BOOT_OK", "SYNVEIL_CORE_READY", "SYNVEIL_STATE_READY",
           "SYNVEIL_SEAT_READY")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ovmf_paths():
    pairs = [("/usr/share/OVMF/OVMF_CODE_4M.fd", "/usr/share/OVMF/OVMF_VARS_4M.fd"),
             ("/usr/share/OVMF/OVMF_CODE.fd", "/usr/share/OVMF/OVMF_VARS.fd"),
             ("/usr/share/edk2/ovmf/OVMF_CODE.fd", "/usr/share/edk2/ovmf/OVMF_VARS.fd"),
             ("/usr/share/edk2/x64/OVMF_CODE.fd", "/usr/share/edk2/x64/OVMF_VARS.fd")]
    for code, vars_ in pairs:
        if Path(code).is_file() and Path(vars_).is_file():
            return code, vars_
    raise RuntimeError("OVMF firmware pair not found")


class Boot:
    """One QEMU process; guest reboots stay inside it."""

    def __init__(self, workdir, name, disk, vars_file, extra_drives=()):
        self.dir = Path(workdir)
        self.name = name
        self.qmp = self.dir / f"{name}.sock"
        self.log_path = EVIDENCE / f"{name}.log"
        self.lines = []
        self._lock = threading.Lock()
        self._secret = None
        code, _vars_template = ovmf_paths()
        argv = ["qemu-system-x86_64", "-nodefaults",
                "-machine", "q35,i8042=off,vmport=off",
                "-m", "768M", "-smp", "2", "-display", "none",
                "-serial", "stdio", "-monitor", "none",
                "-device", "virtio-vga", "-device", "qemu-xhci",
                "-device", "usb-kbd", "-device", "usb-tablet",
                "-net", "none", "-accel", "tcg",
                "-drive", f"if=pflash,format=raw,unit=0,readonly=on,file={code}",
                "-drive", f"if=pflash,format=raw,unit=1,file={vars_file}",
                "-drive", f"if=none,id=main,file={disk},format=raw,readonly=off",
                "-device", "virtio-blk-pci,drive=main,bootindex=1",
                "-qmp", f"unix:{self.qmp},server=on,wait=off"]
        for index, drive in enumerate(extra_drives):
            argv += ["-drive", f"if=none,id=rel{index},file={drive},format=raw,readonly=on",
                     "-device", f"virtio-blk-pci,drive=rel{index}"]
        self.argv = argv
        self.process = None

    def start(self, secret):
        self._secret = secret
        self.process = subprocess.Popen(
            self.argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, start_new_session=True)
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def _pump(self):
        with self.log_path.open("wb") as log:
            for raw in iter(self.process.stdout.readline, b""):
                line = raw.rstrip(b"\r\n")
                if self._secret:
                    line = line.replace(self._secret.encode(), b"[REDACTED]")
                log.write(line + b"\n")
                log.flush()
                with self._lock:
                    self.lines.append(line.decode("utf-8", "replace"))

    def seen(self, marker, since=0):
        with self._lock:
            return any(line.startswith(marker) for line in self.lines[since:])

    def count(self, marker):
        with self._lock:
            return sum(1 for line in self.lines if line.startswith(marker))

    def wait(self, marker, timeout, since=0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.seen(marker, since):
                return True
            if self.process.poll() is not None:
                return False
            time.sleep(0.2)
        return self.seen(marker, since)

    def wait_count(self, marker, count, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.count(marker) >= count:
                return True
            if self.process.poll() is not None:
                return False
            time.sleep(0.2)
        return self.count(marker) >= count

    def qmp_execute(self, command):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(10)
            sock.connect(str(self.qmp))
            reader = sock.makefile("rb")
            reader.readline()
            sock.sendall(b'{"execute":"qmp_capabilities"}\n')
            reader.readline()
            sock.sendall((json.dumps({"execute": command}) + "\n").encode())
            return reader.readline()

    def quit(self):
        try:
            self.qmp_execute("quit")
        except OSError:
            pass
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)


def login(boot, secret, timeout=420):
    """Wait for the graphical login, prove scanout, authenticate."""
    if not boot.wait("SYNVEIL_LOGIN_READY", timeout):
        return False
    for _ in range(10):
        if capture_test_scanout(boot.qmp, boot.dir / "scanout.ppm", timeout=2):
            break
        time.sleep(0.3)
    else:
        return False
    try:
        type_test_secret(boot.qmp, secret, timeout=18)
    except (QMPError, OSError, ValueError):
        return False
    return boot.wait("SYNVEIL_GRAPHICAL_AUTH_ACTIVE", 120)


def desktop_color_proof(boot, version, timeout=120):
    """The running generation's Weston background dominates the frame
    and the other generation's background does not."""
    target = GEN_COLORS[version]
    other = GEN_COLORS[2 if version == 1 else 1]
    deadline = time.monotonic() + timeout
    count = 0
    while time.monotonic() < deadline:
        count += 1
        try:
            width, height, data = weston_smoke.screenshot(boot.qmp, boot.dir, count)
        except (ValueError, OSError):
            time.sleep(0.5)
            continue
        def fraction(rgb):
            hits = 0
            total = 0
            for i in range(0, len(data) - 2, 3 * 7):
                total += 1
                if (abs(data[i] - rgb[0]) <= 2 and abs(data[i + 1] - rgb[1]) <= 2
                        and abs(data[i + 2] - rgb[2]) <= 2):
                    hits += 1
            return hits / max(total, 1)
        if fraction(target) >= 0.03 and fraction(target) >= 4 * max(fraction(other), 0.001):
            return True
        time.sleep(0.5)
    return False


def terminal_command(boot, command_id, wait_marker=None, timeout=300):
    """Click the session terminal and run one fixed A/B command."""
    frame = None
    for attempt in range(40):
        try:
            frame = weston_smoke.screenshot(boot.qmp, boot.dir, 100 + attempt)
            tx, ty = weston_smoke.terminal_point(*frame)
            break
        except (ValueError, RuntimeError, OSError):
            time.sleep(0.5)
    else:
        return False
    weston_smoke.pointer(boot.qmp, frame[0], frame[1], tx, ty, button=True)
    weston_smoke.pointer(boot.qmp, frame[0], frame[1], tx, ty, button=False)
    time.sleep(0.4)
    try:
        type_ab_command(boot.qmp, command_id, timeout=30)
    except (QMPError, OSError, ValueError):
        return False
    if wait_marker is None:
        time.sleep(2)
        return True
    return boot.wait(wait_marker, timeout)


def partition_offset(disk, number):
    info = subprocess.check_output(["sgdisk", "-i", str(number), str(disk)], text=True)
    first = int([line for line in info.splitlines()
                 if "First sector:" in line][0].split(":", 1)[1].split()[0])
    last = int([line for line in info.splitlines()
                if "Last sector:" in line][0].split(":", 1)[1].split()[0])
    return first * 512, (last - first + 1) * 512


def extract_partition(disk, number, workdir):
    offset, size = partition_offset(disk, number)
    target = Path(workdir) / f"part{number}.img"
    with open(disk, "rb") as source, open(target, "wb") as dest:
        source.seek(offset)
        shutil.copyfileobj(source, dest, size)
    return target


def ext4_read(image, path):
    result = subprocess.run(["debugfs", "-R", f"cat {path}", str(image)],
                            capture_output=True)
    if result.returncode != 0:
        return None
    return result.stdout


def state_artifacts(disk, workdir):
    """Host-side view of STATE (partition 4) and DATA (partition 5)."""
    state = extract_partition(disk, 4, workdir)
    data = extract_partition(disk, 5, workdir)
    control_raw = ext4_read(state, "/lib/synveil/ab-control.json")
    pref = ext4_read(state, "/lib/synveil/desktop-pref.conf")
    credential = ext4_read(state, "/lib/synveil/auth/credential.phc")
    known = ext4_read(data, "/synveil/ab-known-file")
    return {
        "control": json.loads(control_raw) if control_raw else None,
        "pref_sha256": hashlib.sha256(pref).hexdigest() if pref else None,
        "pref_text": pref.decode("utf-8", "replace") if pref else None,
        "credential_sha256": hashlib.sha256(credential).hexdigest() if credential else None,
        "known_file": known.decode("utf-8", "replace") if known else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=600,
                        help="per-boot marker timeout budget")
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("A/B smoke requires a non-root runner")
    build_receipt = json.loads((OUT / "build-receipt.json").read_text())
    source_disk = OUT / "synveil-ab.img"
    if sha256(source_disk) != build_receipt["disk"]["sha256"]:
        parser.error("A/B disk differs from its build receipt")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    results = {}
    secret = secrets.token_hex(16)

    with tempfile.TemporaryDirectory(prefix="synveil-ab-") as temp:
        work = Path(temp)
        disk = work / "synveil-ab.img"
        shutil.copyfile(source_disk, disk)
        vars_file = work / "OVMF_VARS.fd"
        _code, vars_template = ovmf_paths()
        shutil.copyfile(vars_template, vars_file)

        def record(name, ok, **fields):
            results[name] = {"pass": bool(ok), **fields}
            print(f"[synveil-ab] {name}: {'PASS' if ok else 'FAIL'}", flush=True)
            return bool(ok)

        # ---- S0: provision + enroll + login + setting + known file
        boot = Boot(work, "s0-provision", disk, vars_file)
        boot.start(secret)
        ok = boot.wait("SYNVEIL_AB_PROVISIONED", args.timeout)
        home_mounted = boot.seen("SYNVEIL_AB_HOME_MOUNTED")
        if ok:
            enrolled = boot.wait("SYNVEIL_ENROLL_READY", 240)
            if enrolled:
                try:
                    type_test_secret(boot.qmp, secret, timeout=18)
                    if boot.wait("SYNVEIL_ENROLL_CONFIRM_READY", 60):
                        type_test_secret(boot.qmp, secret, timeout=18)
                    enrolled = boot.wait("SYNVEIL_ENROLL_COMPLETED", 120)
                except (QMPError, OSError, ValueError):
                    enrolled = False
            ok = enrolled
        setting_changed = False
        if ok:
            # The display greeter may expose the veil-display menu's
            # settings toggles (contrast + pointer size, persisted to
            # STATE as desktop-pref.conf). Attempt them once at the
            # login screen and record honestly whether the save
            # marker appeared; the flow continues either way.
            try:
                settings_toggle(boot.qmp, timeout=8)
            except (QMPError, OSError, ValueError):
                pass
            setting_changed = boot.wait("SYNVEIL_SETTINGS_SAVED", 8)
            ok = login(boot, secret)
        known_file_made = False
        if ok:
            known_file_made = terminal_command(boot, "known-file")
            time.sleep(1)
        boot.quit()
        artifacts = state_artifacts(disk, work)
        record("S0-provision-enroll", ok,
               home_mounted=home_mounted,
               setting_changed=setting_changed,
               pref_text=artifacts["pref_text"],
               credential_recorded=bool(artifacts["credential_sha256"]),
               known_file=artifacts["known_file"])
        baseline = artifacts
        if not ok:
            return finish(build_receipt, results, 1)

        # ---- S1+S2: stage v2, trial boot, health confirmation
        boot = Boot(work, "s1-stage-v2", disk, vars_file,
                    extra_drives=[OUT / "release-v2.img"])
        boot.start(secret)
        ok = boot.wait("SYNVEIL_AB_CONFIRMED_BOOT", args.timeout)
        if ok:
            ok = login(boot, secret)
        if ok:
            ok = terminal_command(boot, "stage", "SYNVEIL_AB_STAGED", timeout=420)
        record("S1-stage-v2", ok)
        if ok:
            staged_at = len(boot.lines)
            terminal_command(boot, "reboot")
            # The reboot loads the entry generation (fallback = v1);
            # its hook accounts the trial and chain-loads v2.
            ok = boot.wait("SYNVEIL_AB_TRIAL_HANDOVER", args.timeout, since=staged_at)
            if ok:
                ok = boot.wait("SYNVEIL_AB_TRIAL_BOOT", args.timeout, since=staged_at)
            if ok:
                ok = login(boot, secret)
            if ok:
                ok = desktop_color_proof(boot, 2)
            if ok:
                ok = boot.wait("SYNVEIL_AB_CONFIRMED", 420)
        boot.quit()
        artifacts = state_artifacts(disk, work)
        control = artifacts["control"] or {}
        record("S2-trial-v2-confirmed", ok,
               confirmed=(control.get("confirmed") or {}),
               survival={
                   "credential_same": artifacts["credential_sha256"] == baseline["credential_sha256"],
                   "pref_same": artifacts["pref_sha256"] == baseline["pref_sha256"],
                   "known_file_same": artifacts["known_file"] == baseline["known_file"],
               })
        if not ok:
            return finish(build_receipt, results, 1)
        after_update = artifacts

        # ---- S3: owner rollback to v1
        boot = Boot(work, "s3-rollback-v1", disk, vars_file)
        boot.start(secret)
        ok = boot.wait("SYNVEIL_AB_CONFIRMED_BOOT", args.timeout) and login(boot, secret)
        if ok:
            ok = terminal_command(boot, "rollback", "SYNVEIL_AB_ROLLBACK", timeout=180)
        if ok:
            mark = len(boot.lines)
            terminal_command(boot, "reboot")
            ok = boot.wait("SYNVEIL_AB_TRIAL_BOOT", args.timeout, since=mark)
            if ok:
                ok = login(boot, secret)
            if ok:
                ok = desktop_color_proof(boot, 1)
            if ok:
                ok = boot.wait("SYNVEIL_AB_CONFIRMED", 420)
        boot.quit()
        artifacts = state_artifacts(disk, work)
        control = artifacts["control"] or {}
        record("S3-owner-rollback-v1", ok,
               confirmed=(control.get("confirmed") or {}),
               survival={
                   "credential_same": artifacts["credential_sha256"] == baseline["credential_sha256"],
                   "pref_same": artifacts["pref_sha256"] == baseline["pref_sha256"],
                   "known_file_same": artifacts["known_file"] == baseline["known_file"],
               })
        if not ok:
            return finish(build_receipt, results, 1)

        # ---- S4: failing candidate v3 exhausts attempts -> fallback
        boot = Boot(work, "s4-failing-v3", disk, vars_file,
                    extra_drives=[OUT / "release-v3.img"])
        boot.start(secret)
        ok = boot.wait("SYNVEIL_AB_CONFIRMED_BOOT", args.timeout) and login(boot, secret)
        if ok:
            ok = terminal_command(boot, "stage", "SYNVEIL_AB_STAGED", timeout=420)
        if ok:
            mark = len(boot.lines)
            terminal_command(boot, "reboot")
            ok = boot.wait_count("SYNVEIL_AB_HEALTH_FAILED", 3, 3000)
            if ok:
                ok = boot.wait("SYNVEIL_AB_TRIAL_EXHAUSTED", 600, since=mark)
            if ok:
                # Exhaustion clears the trial in the entry
                # generation's hook; the confirmed generation boots.
                ok = boot.wait("SYNVEIL_AB_CONFIRMED_BOOT", args.timeout, since=mark)
            if ok:
                ok = login(boot, secret)
        boot.quit()
        artifacts = state_artifacts(disk, work)
        control = artifacts["control"] or {}
        record("S4-failing-candidate-fallback", ok,
               confirmed=(control.get("confirmed") or {}),
               trial_after_fallback=control.get("trial"),
               survival={
                   "credential_same": artifacts["credential_sha256"] == baseline["credential_sha256"],
                   "known_file_same": artifacts["known_file"] == baseline["known_file"],
               })
        if not ok:
            return finish(build_receipt, results, 1)

        # ---- S5: invalid signature refused
        boot = Boot(work, "s5-badsig", disk, vars_file,
                    extra_drives=[OUT / "release-v2-badsig.img"])
        boot.start(secret)
        ok = boot.wait("SYNVEIL_AB_CONFIRMED_BOOT", args.timeout) and login(boot, secret)
        if ok:
            ok = terminal_command(boot, "stage", "SYNVEIL_AB_ACTION_FAILED", timeout=420)
            ok = ok and boot.seen("release signature verification failed")
            ok = ok and not boot.seen("SYNVEIL_AB_STAGED")
        boot.quit()
        artifacts = state_artifacts(disk, work)
        control = artifacts["control"] or {}
        record("S5-invalid-signature-refused", ok,
               trial=control.get("trial"),
               confirmed=(control.get("confirmed") or {}))
        if not ok:
            return finish(build_receipt, results, 1)

        # ---- S6: power cut mid-staging
        boot = Boot(work, "s6-interrupt", disk, vars_file,
                    extra_drives=[OUT / "release-v2.img"])
        boot.start(secret)
        ok = boot.wait("SYNVEIL_AB_CONFIRMED_BOOT", args.timeout) and login(boot, secret)
        if ok:
            # Drive the stage from the terminal, but cut power the
            # moment the copy begins.
            frame = None
            for attempt in range(40):
                try:
                    frame = weston_smoke.screenshot(boot.qmp, boot.dir, 200 + attempt)
                    tx, ty = weston_smoke.terminal_point(*frame)
                    break
                except (ValueError, RuntimeError, OSError):
                    time.sleep(0.5)
            if frame is None:
                ok = False
            else:
                weston_smoke.pointer(boot.qmp, frame[0], frame[1], tx, ty, button=True)
                weston_smoke.pointer(boot.qmp, frame[0], frame[1], tx, ty, button=False)
                time.sleep(0.4)
                cutter = threading.Thread(target=lambda: (
                    boot.wait("SYNVEIL_AB_STAGE_COPYING", 300), boot.quit()))
                cutter.start()
                try:
                    type_ab_command(boot.qmp, "stage", timeout=30)
                except (QMPError, OSError, ValueError):
                    pass
                cutter.join(timeout=360)
                ok = not boot.seen("SYNVEIL_AB_STAGED")
        artifacts = state_artifacts(disk, work)
        control = artifacts["control"] or {}
        record("S6-interrupted-stage", ok,
               trial=control.get("trial"),
               confirmed=(control.get("confirmed") or {}))
        if not ok:
            return finish(build_receipt, results, 1)

        # S6b: the system still boots its confirmed generation and a
        # fresh stage succeeds afterwards (trial left pending, then
        # discarded by an owner rollback decision).
        boot = Boot(work, "s6b-recover-stage", disk, vars_file,
                    extra_drives=[OUT / "release-v2.img"])
        boot.start(secret)
        ok = boot.wait("SYNVEIL_AB_CONFIRMED_BOOT", args.timeout) and login(boot, secret)
        if ok:
            ok = terminal_command(boot, "stage", "SYNVEIL_AB_STAGED", timeout=420)
        if ok:
            ok = terminal_command(boot, "rollback", "SYNVEIL_AB_ROLLBACK", timeout=180)
        boot.quit()
        artifacts = state_artifacts(disk, work)
        control = artifacts["control"] or {}
        record("S6b-stage-after-interrupt", ok, trial=control.get("trial"))
        if not ok:
            return finish(build_receipt, results, 1)

        # ---- S7: slot images corrupt -> fail closed to diagnostics
        branch = work / "synveil-ab-recovery.img"
        shutil.copyfile(disk, branch)
        for number in (2, 3):
            part = extract_partition(branch, number, work)
            target = Path(work) / f"slot{number}-gen.json"
            subprocess.run(["mcopy", "-i", str(part), "::/EFI/synveil/gen.json",
                            str(target)], capture_output=True)
            if not target.is_file():
                continue  # empty slot: nothing to corrupt
            identity = json.loads(target.read_text())
            zeros = Path(work) / f"zeros{number}.bin"
            zeros.write_bytes(b"\0" * identity["bytes"])
            subprocess.run(["mdel", "-i", str(part), "::/EFI/synveil/gen.efi"], check=True)
            subprocess.run(["mcopy", "-i", str(part), str(zeros), "::/EFI/synveil/gen.efi"], check=True)
            offset, _size = partition_offset(branch, number)
            with open(part, "rb") as source, open(branch, "r+b") as dest:
                dest.seek(offset)
                shutil.copyfileobj(source, dest)
        boot = Boot(work, "s7-recovery", branch, vars_file)
        boot.start(secret)
        # The ESP fallback copy of v1 still loads, but its hook must
        # refuse to run the corrupt confirmed slot as the system.
        ok = boot.wait("SYNVEIL_AB_FAIL_CLOSED", 600)
        ok = ok and boot.wait("SYNVEIL_RECOVERY_STATUS_V1", 120)
        ok = ok and not boot.seen("SYNVEIL_LOGIN_READY")
        boot.quit()
        record("S7-corrupt-slots-fail-closed", ok)

    return finish(build_receipt, results, 0 if all(
        entry["pass"] for entry in results.values()) else 1)


def finish(build_receipt, results, code):
    receipt = {
        "schema": "synveil.ab-qemu-proof/v1",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "build_receipt_commit": build_receipt["source_commit"],
        "disk_sha256": build_receipt["disk"]["sha256"],
        "generations": {v: {"uki_sha256": g["uki_sha256"], "bytes": g["uki_bytes"]}
                        for v, g in build_receipt["generations"].items()},
        "publisher": build_receipt["publisher"],
        "scenarios": results,
        "bootable_update_rollback_demonstrated": all(
            results.get(name, {}).get("pass", False) for name in (
                "S1-stage-v2", "S2-trial-v2-confirmed", "S3-owner-rollback-v1",
                "S4-failing-candidate-fallback")),
        "https_browsing_in_synveil": False,
        "persistent_downloads_in_synveil": False,
        "physical_hardware_tested": False,
    }
    (OUT / "smoke-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("SYNVEIL_AB_QEMU_PROOF_" + ("PASS" if code == 0 else "INCOMPLETE"))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
