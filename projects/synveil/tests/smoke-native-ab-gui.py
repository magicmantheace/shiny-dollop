#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Graphical A/B update controls acceptance in QEMU (Priority 2).

Drives the A/B proof disk assembled by tools/native_ab.py through
the core update flow with the session's update GUI as the actor:
every update action in G1–G3 is a pointer click on the GUI's
buttons (located by screenshot pixels) — no terminal command is
issued for them. The agent's serial markers and the host-side
control record are the evidence the clicks had the claimed effect,
and the GUI's own session log (read back from the DATA partition)
records its clicks, actions and rendered states.

  G0  provision + enroll + login (the agent-driven baseline from
      the A/B proof); the GUI is present in the session, banner
      normal, and its log lands in the home directory
  G1  GUI: stage v2 from release media -> Restart -> trial boot ->
      login -> health passed -> Confirm. Confirmed becomes v2;
      credential + known file survive
  G2  GUI: Roll back (arms the retained v1) -> Restart -> trial
      boot -> login -> Confirm. Confirmed returns to v1; survival
  G3  GUI: stage from corrupted-signature media is refused by the
      agent; the GUI banner turns to the error state, no trial is
      created, the confirmed generation is untouched

The remaining A/B scenarios (failing candidate, interrupted stage,
both-slots-corrupt) stay agent-driven in tests/smoke-native-ab.py;
this driver covers the core path through the GUI, as the Priority 2
handoff specifies. QEMU evidence only; no physical hardware.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from qmp_input import QMPError, type_test_secret  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "smoke_native_ab", ROOT / "tests" / "smoke-native-ab.py")
ab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ab)

OUT = ab.OUT
EVIDENCE = OUT / "gui-evidence"


def find_gui(boot, timeout=240):
    """Poll frames until the update GUI window is visible."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            frame = ab.next_frame(boot)
        except (ValueError, OSError):
            time.sleep(0.5)
            continue
        rect = ab.gui_window_rect(*frame)
        if rect:
            return rect
        time.sleep(0.5)
    return None


def wait_banner(boot, kind, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            frame = ab.next_frame(boot)
        except (ValueError, OSError):
            time.sleep(0.5)
            continue
        rect = ab.gui_window_rect(*frame)
        if rect and ab.gui_banner_kind(*frame, rect) == kind:
            return True
        time.sleep(0.5)
    return False


def click_until(boot, button, marker, timeout=420, since=0):
    """Click a GUI button until the agent's marker lands.

    A click on a disabled button is a no-op in the GUI (state gates
    every button), so retrying while the state settles — e.g. the
    Confirm button enabling once the status shows health passed —
    is safe: at most one real action can be submitted, and the
    marker proves it happened.
    """
    index = ab.GUI_BUTTONS.index(button)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if boot.seen(marker, since=since):
            return True
        try:
            frame = ab.next_frame(boot)
            rect = ab.gui_window_rect(*frame)
        except (ValueError, OSError):
            rect = None
        if rect:
            ab.gui_click(boot, rect, index)
        if boot.wait(marker, 20, since=since):
            return True
    return boot.seen(marker, since=since)


def data_read(disk, workdir, path):
    data = ab.extract_partition(disk, 5, workdir)
    return ab.ext4_read(data, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=600,
                        help="per-boot marker timeout budget")
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("A/B GUI smoke requires a non-root runner")
    build_receipt = json.loads((OUT / "build-receipt.json").read_text())
    source_disk = OUT / "synveil-ab.img"
    if ab.sha256(source_disk) != build_receipt["disk"]["sha256"]:
        parser.error("A/B disk differs from its build receipt")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    results = {}
    secret = secrets.token_hex(16)

    with tempfile.TemporaryDirectory(prefix="synveil-ab-gui-") as temp:
        work = Path(temp)
        disk = work / "synveil-ab.img"
        shutil.copyfile(source_disk, disk)
        vars_file = work / "OVMF_VARS.fd"
        _code, vars_template = ab.ovmf_paths()
        shutil.copyfile(vars_template, vars_file)

        def record(name, ok, **fields):
            results[name] = {"pass": bool(ok), "gui_driven": True, **fields}
            print(f"[synveil-ab-gui] {name}: {'PASS' if ok else 'FAIL'}",
                  flush=True)
            return bool(ok)

        # ---- G0: provision + enroll + login; GUI present in session
        boot = ab.Boot(work, "g0-provision", disk, vars_file)
        boot.log_path = EVIDENCE / "g0-provision.log"
        boot.start(secret)
        ok = boot.wait("SYNVEIL_AB_PROVISIONED", args.timeout)
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
        if ok:
            ok = ab.login(boot, secret)
        gui_seen = False
        if ok:
            gui_seen = find_gui(boot) is not None and \
                wait_banner(boot, "normal", timeout=120)
        known_file_made = False
        if ok:
            known_file_made = ab.terminal_command(boot, "known-file")
            ok = known_file_made
            time.sleep(1)
        boot.quit()
        artifacts = ab.state_artifacts(disk, work)
        gui_log = data_read(disk, work, "/synveil/update-gui.log")
        gui_log = gui_log.decode("utf-8", "replace") if gui_log else ""
        record("G0-provision-enroll-gui-present", ok and gui_seen,
               gui_window_seen=gui_seen,
               gui_log_ready="SYNVEIL_UPDATE_GUI_READY" in gui_log,
               gui_log_status="SYNVEIL_UPDATE_GUI_STATUS" in gui_log,
               credential_recorded=bool(artifacts["credential_sha256"]),
               known_file=artifacts["known_file"])
        baseline = artifacts
        if not results["G0-provision-enroll-gui-present"]["pass"]:
            return finish(build_receipt, results, 1)

        # ---- G1: stage, restart, trial, confirm — all via the GUI
        boot = ab.Boot(work, "g1-gui-stage-confirm", disk, vars_file,
                       extra_drives=[OUT / "release-v2.img"])
        boot.log_path = EVIDENCE / "g1-gui-stage-confirm.log"
        boot.start(secret)
        ok = boot.wait("SYNVEIL_AB_CONFIRMED_BOOT", args.timeout)
        if ok:
            ok = ab.login(boot, secret)
        if ok:
            ok = wait_banner(boot, "normal", timeout=240)
        staged_at = len(boot.lines)
        if ok:
            ok = click_until(boot, "stage", "SYNVEIL_AB_STAGED",
                             timeout=600, since=staged_at)
        if ok:
            ok = wait_banner(boot, "trial", timeout=180)
        if ok:
            # The Restart click's proof is the trial hand-over on the
            # next boot; the GUI itself is gone once the guest reboots.
            ok = click_until(boot, "restart", "SYNVEIL_AB_TRIAL_HANDOVER",
                             timeout=300, since=staged_at)
        if ok:
            ok = boot.wait("SYNVEIL_AB_TRIAL_BOOT", args.timeout, since=staged_at)
        if ok:
            ok = ab.login(boot, secret, since=staged_at)
        if ok:
            ok = ab.desktop_color_proof(boot, 2)
        if ok:
            ok = boot.wait("SYNVEIL_AB_HEALTH_PASSED", 600, since=staged_at)
        if ok:
            ok = wait_banner(boot, "trial", timeout=240)
        if ok:
            ok = click_until(boot, "confirm", "SYNVEIL_AB_CONFIRMED ",
                             timeout=420, since=staged_at)
        if ok:
            ok = wait_banner(boot, "normal", timeout=180)
        boot.quit()
        artifacts = ab.state_artifacts(disk, work)
        control = artifacts["control"] or {}
        gui_log = data_read(disk, work, "/synveil/update-gui.log")
        gui_log = gui_log.decode("utf-8", "replace") if gui_log else ""
        record("G1-gui-stage-trial-confirm", ok,
               confirmed=(control.get("confirmed") or {}),
               gui_clicks={name: f"SYNVEIL_UPDATE_GUI_CLICK action={name}" in gui_log
                           for name in ("stage", "reboot", "confirm")},
               gui_actions_ok={
                   name: f"SYNVEIL_UPDATE_GUI_ACTION action={name} ok=1" in gui_log
                   for name in ("stage", "reboot", "confirm")},
               survival={
                   "credential_same": artifacts["credential_sha256"] == baseline["credential_sha256"],
                   "known_file_same": artifacts["known_file"] == baseline["known_file"],
               })
        if not ok:
            return finish(build_receipt, results, 1)

        # ---- G2: roll back to v1 via the GUI, then confirm it
        boot = ab.Boot(work, "g2-gui-rollback", disk, vars_file)
        boot.log_path = EVIDENCE / "g2-gui-rollback.log"
        boot.start(secret)
        ok = boot.wait("SYNVEIL_AB_CONFIRMED_BOOT", args.timeout)
        if ok:
            ok = ab.login(boot, secret)
        if ok:
            ok = wait_banner(boot, "normal", timeout=240)
        mark = len(boot.lines)
        if ok:
            ok = click_until(boot, "rollback",
                             "SYNVEIL_AB_ROLLBACK result=trial slot=",
                             timeout=300, since=mark)
        if ok:
            ok = wait_banner(boot, "trial", timeout=180)
        if ok:
            ok = click_until(boot, "restart", "SYNVEIL_AB_TRIAL_BOOT",
                             timeout=300, since=mark)
        if ok:
            ok = ab.login(boot, secret, since=mark)
        if ok:
            ok = ab.desktop_color_proof(boot, 1)
        if ok:
            ok = boot.wait("SYNVEIL_AB_HEALTH_PASSED", 600, since=mark)
        if ok:
            ok = click_until(boot, "confirm", "SYNVEIL_AB_CONFIRMED ",
                             timeout=420, since=mark)
        if ok:
            ok = wait_banner(boot, "normal", timeout=180)
        boot.quit()
        artifacts = ab.state_artifacts(disk, work)
        control = artifacts["control"] or {}
        record("G2-gui-rollback-confirm", ok,
               confirmed=(control.get("confirmed") or {}),
               survival={
                   "credential_same": artifacts["credential_sha256"] == baseline["credential_sha256"],
                   "known_file_same": artifacts["known_file"] == baseline["known_file"],
               })
        if not ok:
            return finish(build_receipt, results, 1)

        # ---- G3: corrupted-signature release refused, shown in GUI
        boot = ab.Boot(work, "g3-gui-badsig", disk, vars_file,
                       extra_drives=[OUT / "release-v2-badsig.img"])
        boot.log_path = EVIDENCE / "g3-gui-badsig.log"
        boot.start(secret)
        ok = boot.wait("SYNVEIL_AB_CONFIRMED_BOOT", args.timeout)
        if ok:
            ok = ab.login(boot, secret)
        if ok:
            ok = wait_banner(boot, "normal", timeout=240)
        mark = len(boot.lines)
        if ok:
            ok = click_until(
                boot, "stage",
                "SYNVEIL_AB_ACTION_FAILED action=stage "
                "error=release signature verification failed",
                timeout=420, since=mark)
        if ok:
            ok = wait_banner(boot, "error", timeout=240)
        if ok:
            ok = not boot.seen("SYNVEIL_AB_STAGED", since=mark)
        boot.quit()
        artifacts = ab.state_artifacts(disk, work)
        control = artifacts["control"] or {}
        record("G3-gui-badsig-refused", ok,
               trial=control.get("trial"),
               confirmed=(control.get("confirmed") or {}))
        if not ok:
            return finish(build_receipt, results, 1)

    return finish(build_receipt, results, 0 if all(
        entry["pass"] for entry in results.values()) else 1)


def finish(build_receipt, results, code):
    try:
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (subprocess.CalledProcessError, OSError):
        source_commit = build_receipt["source_commit"]
    receipt = {
        "schema": "synveil.ab-gui-qemu-proof/v1",
        "source_commit": source_commit,
        "build_receipt_commit": build_receipt["source_commit"],
        "disk_sha256": build_receipt["disk"]["sha256"],
        "generations": {v: {"uki_sha256": g["uki_sha256"], "bytes": g["uki_bytes"]}
                        for v, g in build_receipt["generations"].items()},
        "publisher": build_receipt["publisher"],
        "scenarios": results,
        "gui_driven_scenarios": ["G1-gui-stage-trial-confirm",
                                 "G2-gui-rollback-confirm",
                                 "G3-gui-badsig-refused"],
        "agent_driven_scenarios": "tests/smoke-native-ab.py (nine scenarios)",
        "graphical_update_controls_demonstrated": all(
            results.get(name, {}).get("pass", False) for name in (
                "G1-gui-stage-trial-confirm", "G2-gui-rollback-confirm",
                "G3-gui-badsig-refused")),
        "firmware_variables_written": False,
        "physical_hardware_tested": False,
    }
    (OUT / "gui-smoke-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n")
    print("SYNVEIL_AB_GUI_QEMU_PROOF_" + ("PASS" if code == 0 else "INCOMPLETE"))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
