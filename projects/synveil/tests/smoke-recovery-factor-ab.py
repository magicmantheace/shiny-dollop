#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""QEMU acceptance for ADR 0010 tier 4, specification section 11
test 11, on the A/B substrate: the DATA partition's contents are
byte-identical across a denied reset attempt, a successful reset,
and a factor rotation.

Uses the A/B proof build (tools/native_ab.py, out/ab-proof), whose
ESP also carries the maintenance and reset UKIs. All work happens
on a disposable copy of the proof disk:

  1. provision   a normal boot provisions the A/B control record
  2. enroll      the synthetic owner password and recovery factor
                 are enrolled onto the disk's STATE partition
                 through the developer fixture image (test-only
                 route, as in smoke-recovery-factor.py)
  3. probe       a known-content owner file is placed on DATA and
                 the DATA partition image is hashed
  4. denied      reset boot (ESP fallback = reset.efi): a wrong
                 factor is denied; DATA hashed again
  5. reset       reset boot: the genuine factor verifies, the owner
                 confirms, the password is replaced; DATA hashed
  6. rotate      maintenance boot (ESP fallback = maintenance.efi):
                 authentication with the NEW password, rotation to
                 generation 2; DATA hashed once more
  7. host checks all DATA hashes equal; the STATE audit log records
                 the reset and the rotation; the record shows
                 generation 3 (enrollment 1, reset revocation 2,
                 rotation 3)

Evidence logs and a verdict JSON are written under
out/recovery-factor-ab/. QEMU evidence only; no hardware claimed.
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
AB_OUT = ROOT / "out" / "ab-proof"
OUT = ROOT / "out" / "recovery-factor-ab"
VERIFY_TIMEOUT = 300


def load(name, filename):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "tests" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ab_smoke = load("smoke_recovery_maint_ab", "smoke-recovery-maint-ab.py")
factor_smoke = load("smoke_recovery_factor", "smoke-recovery-factor.py")
maint_smoke = factor_smoke.maint_smoke
Boot = ab_smoke.Boot
probe_locked = ab_smoke.probe_locked
partition_span = ab_smoke.partition_span
extract_partition = ab_smoke.extract_partition
write_partition = ab_smoke.write_partition
replay_journal = ab_smoke.replay_journal
debugfs_read = ab_smoke.debugfs_read
debugfs_write = ab_smoke.debugfs_write
ovmf_paths = ab_smoke.ovmf_paths
run = ab_smoke.run

PASSWORD = factor_smoke.PASSWORD_A
PASSWORD_NEW = factor_smoke.PASSWORD_NEW


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def esp_swap(disk, uki_path):
    esp = extract_partition(disk, 1, OUT / "esp.img")
    run("mcopy", "-o", "-i", str(esp), str(uki_path),
        "::EFI/BOOT/BOOTX64.EFI")
    write_partition(disk, 1, esp)


def data_hashes(disk, tag):
    """(whole-partition sha256, probe-file sha256) for DATA (p5).

    The partition hash is taken from the RAW extraction: replaying
    the journal with e2fsck stamps the extracted copy's superblock
    timestamps (s_mtime/s_wtime/s_lastcheck), which would make the
    measurement differ by itself. DATA is never mounted by the
    recovery boots (its superblock mount count stays 0), so no
    journal is pending and the raw bytes are the guest-visible
    bytes; the probe read still goes through the replayed copy.
    """
    data = extract_partition(disk, 5, OUT / f"data-{tag}.img")
    partition_hash = sha256_bytes(data.read_bytes())
    replay_journal(data)
    probe = debugfs_read(data, "/owner-probe.txt")
    return partition_hash, sha256_bytes(probe or b"")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    maint_smoke.OUT = OUT
    ab_smoke.OUT = OUT
    factor_smoke.OUT = OUT
    receipt = json.loads((AB_OUT / "build-receipt.json").read_text())
    results = {}
    disk = OUT / "work-disk.img"
    shutil.copyfile(receipt["disk"]["path"], disk)
    vars_file = OUT / "vars.fd"
    _code, vars_template = ovmf_paths()
    shutil.copyfile(vars_template, vars_file)

    # 1. Provision the A/B control record on a normal boot.
    instance = Boot("provision", disk, vars_file)
    ok = instance.wait("SYNVEIL_AB_PROVISIONED slot=A version=1")
    time.sleep(10)
    instance.stop()
    results["provision"] = ok

    # 2. Enroll password + factor onto this disk's STATE partition.
    enroll_out = factor_smoke.OUT / "fixtures" / "enroll"
    if not (enroll_out / "synveil-x86_64.img").is_file():
        enroll_out = factor_smoke.build_fixture("enroll", "enroll")
    instance = maint_smoke.SerialBoot("enroll-ab-factor", enroll_out, disk)
    ok = factor_smoke.enroll_password(instance, PASSWORD)
    factor = factor_smoke.enroll_factor(instance) if ok else None
    ok = ok and factor is not None
    factor_smoke.poweroff(instance)
    results["enroll"] = ok
    if factor is None:
        raise RuntimeError("factor enrollment failed; cannot continue")

    # 3. DATA probe file + baseline hashes.
    probe_content = (b"synveil owner data probe: tier-4 flows must "
                     b"not touch this file\n")
    probe_file = OUT / "owner-probe.txt"
    probe_file.write_bytes(probe_content)
    data = extract_partition(disk, 5, OUT / "data-setup.img")
    replay_journal(data)
    debugfs_write(data, probe_file, "/owner-probe.txt")
    write_partition(disk, 5, data)
    base_partition, base_probe = data_hashes(disk, "base")
    results["probe-placed"] = base_probe == sha256_bytes(probe_content)

    # 4. Denied reset attempt (wrong factor, valid format).
    esp_swap(disk, receipt["reset"]["uki"])
    instance = Boot("reset-denied", disk, vars_file)
    ok = instance.wait("SYNVEIL_RECOVERY_RESET_FACTOR_PROMPT")
    wrong = factor_smoke.wrong_factor()
    for n in (1, 2, 3):
        instance.send(wrong)
        ok = ok and instance.wait(
            f"SYNVEIL_RECOVERY_RESET_ATTEMPT_DENIED attempt={n}",
            VERIFY_TIMEOUT)
    ok = ok and instance.wait("SYNVEIL_SERIAL_RECOVERY_LOCKED")
    ok = ok and probe_locked(instance)
    instance.stop()
    results["reset-denied"] = ok
    after_denied = data_hashes(disk, "denied")
    results["data-after-denied"] = after_denied == (base_partition,
                                                    base_probe)

    # 5. Successful reset with the genuine factor.
    instance = Boot("reset-ok", disk, vars_file)
    ok = instance.wait("SYNVEIL_RECOVERY_RESET_FACTOR_PROMPT")
    instance.send(factor)
    ok = ok and instance.wait("SYNVEIL_RECOVERY_RESET_VERIFIED",
                              VERIFY_TIMEOUT)
    ok = ok and instance.wait("SYNVEIL_RECOVERY_RESET_CONFIRM_PROMPT", 60)
    instance.send("confirm")
    ok = ok and instance.wait("SYNVEIL_RECOVERY_RESET_PASSWORD_PROMPT", 60)
    instance.send(PASSWORD_NEW)
    ok = ok and instance.wait(
        "SYNVEIL_RECOVERY_RESET_PASSWORD_CONFIRM_PROMPT", 60)
    instance.send(PASSWORD_NEW)
    ok = ok and instance.wait("SYNVEIL_RECOVERY_RESET_OK", VERIFY_TIMEOUT)
    ok = ok and instance.wait("SYNVEIL_SERIAL_RECOVERY_LOCKED")
    ok = ok and probe_locked(instance)
    instance.stop()
    results["reset-ok"] = ok
    after_reset = data_hashes(disk, "reset")
    results["data-after-reset"] = after_reset == (base_partition,
                                                   base_probe)

    # 6. Rotation under the new password.
    esp_swap(disk, receipt["maintenance"]["uki"])
    instance = Boot("rotate", disk, vars_file)
    ok = instance.wait("SYNVEIL_RECOVERY_MAINT_PASSWORD_PROMPT")
    instance.send(PASSWORD_NEW)
    ok = ok and instance.wait("SYNVEIL_RECOVERY_MAINT_AUTH_OK",
                              VERIFY_TIMEOUT)
    new_factor, flow_ok = factor_smoke.rotate_flow(instance, "confirm")
    ok = ok and flow_ok and new_factor is not None
    # Revision sequence on this disk: enrollment wrote generation 1,
    # the successful reset's automatic revocation wrote revision 2,
    # so this rotation commits generation 3.
    ok = ok and instance.wait("SYNVEIL_RECOVERY_ROTATE_OK generation=3",
                              VERIFY_TIMEOUT)
    instance.send("exit")
    ok = ok and instance.wait("SYNVEIL_RECOVERY_MAINT_DONE", 60)
    ok = ok and instance.wait("SYNVEIL_SERIAL_RECOVERY_LOCKED")
    ok = ok and probe_locked(instance)
    instance.stop()
    results["rotate"] = ok
    after_rotate = data_hashes(disk, "rotate")
    results["data-after-rotate"] = after_rotate == (base_partition,
                                                     base_probe)
    results["t11-data-identical"] = (
        results["data-after-denied"] and results["data-after-reset"]
        and results["data-after-rotate"])

    # 7. STATE-side evidence: record generation + audit events.
    state = extract_partition(disk, 4, OUT / "state-after.img")
    replay_journal(state)
    record = debugfs_read(
        state, "/lib/synveil/auth/recovery.json").decode("utf-8", "replace")
    results["record-generation-3"] = '"generation": 3' in record \
        or '"generation":3' in record
    audit_log = debugfs_read(
        state, "/log/synveil/recovery-maintenance.log").decode(
            "utf-8", "replace")
    (OUT / "recovery-maintenance.log").write_text(audit_log)
    results["audit-events"] = all(
        f"event={event}" in audit_log for event in (
            "factor-enrollment-confirmed", "reset-completed",
            "factor-rotation-completed"))
    results["audit-no-secrets"] = (
        factor not in audit_log and new_factor not in audit_log
        and PASSWORD not in audit_log and PASSWORD_NEW not in audit_log)

    verdict = {"schema": "synveil.recovery-factor-ab-smoke/v1",
               "source_commit": receipt["source_commit"],
               "disk_sha256": receipt["disk"]["sha256"],
               "cases": results,
               "data_partition_sha256": base_partition,
               "data_probe_sha256": base_probe,
               "factors_redacted": True,
               "physical_hardware_tested": False}
    (OUT / "verdict.json").write_text(json.dumps(verdict, indent=2) + "\n")
    for name, result in results.items():
        print(f"RECOVERY_FACTOR_AB_CASE {name}={'PASS' if result else 'FAIL'}")
    passed = all(results.values())
    print("SYNVEIL_RECOVERY_FACTOR_AB_SMOKE_PASS" if passed
          else "SYNVEIL_RECOVERY_FACTOR_AB_SMOKE_FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
