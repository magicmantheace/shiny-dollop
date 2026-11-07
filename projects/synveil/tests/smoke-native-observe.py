#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Native QEMU validation for the Phase 3 observer (docs/OBSERVER.md):
the memory/pressure (PSI) slice shipped with producer-side parsing
and host unit tests only, and ROADMAP.md requires host/guest
validation of it. This gate closes that gap against the joined
image:

- boots a private copy of the joined image, enrolls and logs in
  through the graphical login exactly as the joined smoke does;
- in the session terminal, runs the one fixed harness command
  `observe` (tools/qmp_input.py allowlist): the system core's
  socket is root-only and the image has no root shell, so a
  user-level `veil-core --socket … --once` fixture serves one
  connection in the background and the guest's real
  `/usr/bin/synctl --json observe` queries it on the same
  line — the real compiled code reading the real guest /proc
  end to end — with stdout and stderr captured to /var/tmp
  (the state partition, the joined image's persistent
  world-writable directory);
- ends the session (graphical login relocks), then reads the
  captured files back from the state partition and requires:
  synctl's stderr empty (the client validates the response
  itself), the `synveil.observe/v1` schema, a ready CPU
  utilization window, a non-empty process snapshot, and a
  `pressure` object whose cpu/memory/io entries are all
  `ready` with in-range stall averages and counters (the guest
  kernel is built with CONFIG_PSI=y, so the ready path — not
  just the unavailable path — is exercised natively).

The gate also covers the observer history slice (ADR 0026):
in the same session it runs the fixed `observe-history`
harness command, which starts a second fixture core with the
lifecycle sampler enabled by policy, snapshots the event
ring, starts a known `sleep 12` probe process (recording its
pid), snapshots again while the probe is alive, and once
more after it exits. The host requires the probe's
`process_started` event in the second snapshot and its
`process_exited` event — same pid, same start_time_ticks,
later sequence — in the third.

Boot/enroll flakes under TCG retry the whole boot on a fresh
image copy (the audit-v2 smoke's pattern); the assertions never
retry. QEMU evidence only; no physical hardware is claimed.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

_spec = importlib.util.spec_from_file_location(
    "smoke_native_joined", ROOT / "tests" / "smoke-native-joined.py")
joined = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(joined)
weston_smoke = joined.weston_smoke

from qmp_input import (  # noqa: E402
    type_test_secret, type_ab_command, send_keys,
    ALLOWED_TERMINAL_RETURN)
import qmp_input as _qmp_input  # noqa: E402
import time as _time  # noqa: E402


def _patient_hold_keys(sock, reader, keys):
    """Same 200 ms key hold as the audit-v2 smoke: under TCG a
    75 ms press can fall inside one guest poll window and vanish."""
    def edge(down):
        ordered = keys if down else reversed(keys)
        events = [{"type": "key", "data": {"down": down,
                   "key": {"type": "qcode", "data": key}}}
                  for key in ordered]
        return {"execute": "input-send-event",
                "arguments": {"events": events}}

    try:
        _qmp_input.emit_command(sock, reader, edge(True))
        _time.sleep(0.2)
    finally:
        _qmp_input.emit_command(sock, reader, edge(False))


_qmp_input._hold_keys = _patient_hold_keys

IMAGE_DIR = ROOT / "out" / "native-joined"
OUT = ROOT / "out" / "observe-proof"
STATE_PARTUUID = "7c9e2d41-8b3a-4f5e-a6d1-2e8c4b7f9053"


def state_partition(image: Path) -> tuple[int, int]:
    """(byte offset, byte size) of the state partition (GPT #2)."""
    info = subprocess.check_output(
        ["sgdisk", "-i", "2", str(image)], text=True)
    first = last = None
    for line in info.splitlines():
        if "First sector:" in line:
            first = int(line.split(":")[1].split()[0])
        if "Last sector:" in line:
            last = int(line.split(":")[1].split()[0])
    if first is None or last is None:
        raise ValueError("state partition bounds not found")
    return first * 512, (last - first + 1) * 512


def extract_state(image: Path, dest: Path) -> None:
    offset, size = state_partition(image)
    with image.open("rb") as source, dest.open("wb") as target:
        source.seek(offset)
        remaining = size
        while remaining:
            chunk = source.read(min(1 << 20, remaining))
            if not chunk:
                raise ValueError("short read on state partition")
            target.write(chunk)
            remaining -= len(chunk)


def replay_journal(state: Path) -> None:
    """Replay the ext4 journal on the extracted scratch copy
    (QEMU exits by emulator kill — a power cut — so guest writes
    are not checkpointed; e2fsck performs the replay a mounting
    kernel would). Exit codes 0-2 are success-with-corrections."""
    result = subprocess.run(["/usr/sbin/e2fsck", "-y", str(state)],
                            capture_output=True)
    if result.returncode >= 4:
        raise ValueError("e2fsck journal replay failed")


def debugfs(state: Path, commands: list[str]) -> str:
    script = "\n".join(commands) + "\n"
    result = subprocess.run(
        ["/usr/sbin/debugfs", "-f", "-", str(state)],
        input=script.encode(), capture_output=True)
    if result.returncode != 0:
        raise ValueError(
            "debugfs failed: " + result.stderr.decode(errors="replace"))
    return result.stdout.decode(errors="replace")


def dump_state_file(state: Path, candidates: list[str],
                    dest: Path) -> str | None:
    """Dump the first existing candidate path; return its path."""
    listing = debugfs(state, ["ls -l /"])
    for candidate in candidates:
        probe = debugfs(state, [f"ls -l {candidate.rsplit('/', 1)[0]}"])
        if candidate.rsplit('/', 1)[1] in probe:
            debugfs(state, [f"dump {candidate} {dest}"])
            return candidate
    print("[synveil] state root listing:\n" + listing)
    return None


def patient_frame(qmp: Path, folder: Path, number: int,
                  timeout: float = 180.0):
    """weston_smoke.screenshot with the A/B harness's patience:
    the serial AUTH_ACTIVE marker can precede the greeter's
    first presented frame by minutes under load, and a blank
    scanout is rejected — retry until a real frame lands."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            return weston_smoke.screenshot(qmp, folder, number)
        except (ValueError, OSError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(2.0)


def ctrl_c(qmp: Path) -> None:
    """One Ctrl+C chord through the QMP input channel (the
    switch_to_login_vt pattern): interrupts a foreground fixture
    process so its terminal returns to a prompt."""
    import socket as _socket
    with _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM) as sock:
        sock.settimeout(5.0)
        sock.connect(str(qmp))
        with sock.makefile("rb") as reader:
            _qmp_input._read_reply(reader, greeting=True)
            _qmp_input.emit_command(
                sock, reader, {"execute": "qmp_capabilities"})
            _qmp_input._hold_keys(sock, reader, ("ctrl", "c"))


def boot_and_observe(work: Path, secret: str, out: Path) -> bool:
    """One boot: enroll, log in, capture the observe response in
    the session terminal, end the session. Returns True once the
    graphical login has relocked with the capture issued."""
    qmp_dir = tempfile.mkdtemp(prefix="synveil-observe-qmp-")
    qmp = Path(qmp_dir) / "monitor.sock"
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("SYNVEIL_")}
    env.update(SYNVEIL_OUT_DIR=str(work), SYNVEIL_QEMU_VIDEO="1",
               SYNVEIL_QEMU_DISPLAY="none", SYNVEIL_QEMU_NETWORK="0",
               SYNVEIL_QEMU_MEMORY="768M", SYNVEIL_QEMU_IMAGE_WRITABLE="1",
               SYNVEIL_QEMU_QMP_SOCKET=str(qmp))
    process = subprocess.Popen(
        ["bash", str(ROOT / "build/scripts/qemu.sh")],
        cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        start_new_session=True)
    deadline = time.monotonic() + 900
    phase = "boot"
    seen: set[bytes] = set()
    pending = b""
    log = (out / "observe-serial.log").open("wb")

    def note(text: str) -> None:
        print(f"[synveil] {text}")
        log.write(f"[synveil] {text}\n".encode())
        log.flush()

    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while time.monotonic() < deadline:
                events = selector.select(0.2)
                if not events:
                    if process.poll() is not None:
                        break
                    continue
                data = os.read(process.stdout.fileno(), 65536)
                if not data:
                    break
                pending += data
                if len(pending) > 65536:
                    note("serial buffer overflow")
                    return False
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    line = line.rstrip(b"\r")
                    log.write(line.replace(secret.encode(),
                                           b"[REDACTED]") + b"\n")
                    log.flush()
                    if b"Recovery/bootstrap shell" in line:
                        note("recovery shell reached")
                        return False
                    if line.startswith(b"SYNVEIL_"):
                        seen.add(line)
                if seen & joined.DENIED:
                    note("denied marker seen")
                    return False
                if phase == "boot" and joined.BOOT <= seen:
                    if b"SYNVEIL_ENROLL_READY" not in seen:
                        continue
                    try:
                        type_test_secret(qmp, secret, timeout=45)
                    except Exception as exc:  # noqa: BLE001
                        note(f"enroll type failed: {exc}")
                        return False
                    phase = "first-password"
                if (phase == "first-password" and
                        b"SYNVEIL_ENROLL_CONFIRM_READY" in seen):
                    seen.discard(b"SYNVEIL_ENROLL_CONFIRM_READY")
                    incorrect = secret[:-1] + ("0" if secret[-1] != "0"
                                               else "1")
                    try:
                        type_test_secret(qmp, incorrect, timeout=45)
                    except Exception as exc:  # noqa: BLE001
                        note(f"mismatch type failed: {exc}")
                        return False
                    phase = "waiting-mismatch-rejection"
                if (phase == "waiting-mismatch-rejection" and
                        b"SYNVEIL_ENROLL_FAILED" in seen):
                    seen.discard(b"SYNVEIL_ENROLL_FAILED")
                    try:
                        type_test_secret(qmp, secret, timeout=45)
                    except Exception as exc:  # noqa: BLE001
                        note(f"retry type failed: {exc}")
                        return False
                    phase = "retry-first-password"
                if (phase == "retry-first-password" and
                        b"SYNVEIL_ENROLL_CONFIRM_READY" in seen):
                    try:
                        type_test_secret(qmp, secret, timeout=45)
                    except Exception as exc:  # noqa: BLE001
                        note(f"confirm type failed: {exc}")
                        return False
                    phase = "confirmation"
                if (phase == "confirmation" and
                        b"SYNVEIL_ENROLL_COMPLETED" in seen and
                        b"SYNVEIL_LOGIN_READY" in seen):
                    try:
                        type_test_secret(qmp, secret, timeout=45)
                    except Exception as exc:  # noqa: BLE001
                        note(f"login type failed: {exc}")
                        return False
                    phase = "logging-in"
                if (phase == "logging-in" and
                        b"SYNVEIL_GRAPHICAL_AUTH_DENIED" in seen):
                    note("graphical auth denied")
                    return False
                if (phase == "logging-in" and
                        b"SYNVEIL_GRAPHICAL_AUTH_ACTIVE" in seen):
                    time.sleep(0.6)
                    phase = "observe"
                    try:
                        frame_dir = Path(tempfile.mkdtemp(
                            prefix="synveil-observe-frame-"))
                        w, h, data = patient_frame(qmp, frame_dir, 1)
                        tx, ty = weston_smoke.terminal_point(w, h, data)
                        weston_smoke.pointer(qmp, w, h, tx, ty,
                                             button=True)
                        weston_smoke.pointer(qmp, w, h, tx, ty,
                                             button=False)
                        time.sleep(0.5)
                        # Fixture pattern (see the observe entry
                        # in tools/qmp_input.py): one line starts
                        # a user-level veil-core in the background
                        # and queries it with synctl. The line's
                        # sacrificial echo segment absorbs any
                        # characters a just-focused terminal eats.
                        type_ab_command(qmp, "observe", timeout=60)
                    except Exception as exc:  # noqa: BLE001
                        note(f"observe capture failed: {exc}")
                        return False
                    note("observe command typed; letting synctl run")
                    # synctl samples CPU over >=100 ms and scans
                    # /proc; under TCG give it generous wall time
                    # before ending the session.
                    time.sleep(20)
                    phase = "history"
                    try:
                        w, h, data = patient_frame(
                            qmp, frame_dir, 3, timeout=30.0)
                        tx, ty = weston_smoke.terminal_point(w, h, data)
                        if tx is None:
                            note("terminal not found for history")
                            return False
                        weston_smoke.pointer(qmp, w, h, tx, ty,
                                             button=True)
                        weston_smoke.pointer(qmp, w, h, tx, ty,
                                             button=False)
                        time.sleep(0.5)
                        # The line is ~560 characters at the
                        # patient 200 ms hold — minutes of
                        # typing — hence the long timeout.
                        type_ab_command(qmp, "observe-history",
                                        timeout=300)
                    except Exception as exc:  # noqa: BLE001
                        note(f"history capture failed: {exc}")
                        return False
                    note("history command typed; sampler running")
                    # The line takes ~35 s of guest time: three
                    # ring snapshots around a 12 s probe process
                    # against the sampler's 5 s cadence, plus
                    # synctl runs under TCG.
                    time.sleep(55)
                    phase = "closing"
                    for _ in range(10):
                        try:
                            w, h, data = patient_frame(
                                qmp, frame_dir, 2, timeout=30.0)
                            tx, ty = weston_smoke.terminal_point(
                                w, h, data)
                        except Exception:  # noqa: BLE001
                            tx = None
                        if tx is not None:
                            weston_smoke.pointer(qmp, w, h, tx, ty,
                                                 button=True)
                            weston_smoke.pointer(qmp, w, h, tx, ty,
                                                 button=False)
                            time.sleep(0.4)
                            # Ctrl+C first: if this terminal is
                            # the fixture core's, `exit` would
                            # queue in its tty buffer forever;
                            # the interrupt returns it to a
                            # prompt (and merely clears the line
                            # at a prompt).
                            try:
                                ctrl_c(qmp)
                            except Exception:  # noqa: BLE001
                                pass
                            time.sleep(0.4)
                            send_keys(qmp, ("e", "x", "i", "t", "ret"),
                                      timeout=5,
                                      allowed=ALLOWED_TERMINAL_RETURN)
                            time.sleep(1.0)
                            continue
                        window = weston_smoke.original_window(
                            w, h, data)
                        if window:
                            x, y, _w, _h = window
                            weston_smoke.pointer(qmp, w, h, x + 30,
                                                 y + 14, button=True)
                            weston_smoke.pointer(qmp, w, h, x + 30,
                                                 y + 14, button=False)
                            time.sleep(0.4)
                            send_keys(qmp, ("esc",), timeout=5)
                            time.sleep(1.0)
                            continue
                        break
                    phase = "awaiting-relock"
                if (phase == "awaiting-relock" and
                        b"SYNVEIL_LOGIN_RELOCKED" in seen):
                    note("session ended; graphical login relocked")
                    return True
            note(f"incomplete: {phase}")
            return False
    finally:
        log.close()
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


def check_pressure_entry(entry, *, require_full: bool,
                         label: str) -> str | None:
    if not isinstance(entry, dict):
        return f"pressure.{label} is not an object"
    if entry.get("status") != "ready":
        return (f"pressure.{label} status is "
                f"{entry.get('status')!r}, expected 'ready'")
    for part_name in ("some", "full"):
        part = entry.get(part_name)
        if part is None:
            if part_name == "full" and not require_full:
                continue
            return f"pressure.{label}.{part_name} missing"
        for field in ("avg10_pct", "avg60_pct", "avg300_pct"):
            value = part.get(field)
            if (not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not 0.0 <= value <= 100.0):
                return (f"pressure.{label}.{part_name}.{field} "
                        f"out of range: {value!r}")
        total = part.get("total_stall_us")
        if not isinstance(total, int) or isinstance(total, bool) \
                or total < 0:
            return (f"pressure.{label}.{part_name}.total_stall_us "
                    f"invalid: {total!r}")
    return None


def check_observe(doc, err_bytes: bytes) -> list[str]:
    failures: list[str] = []
    if err_bytes.strip():
        failures.append(
            "synctl wrote to stderr (client refused the response): "
            + err_bytes.decode(errors="replace")[:200])
    if not isinstance(doc, dict):
        return failures + ["observe response is not a JSON object"]
    # synctl --json prints the full protocol response envelope;
    # the observe document is its result.
    if doc.get("ok") is not True:
        failures.append("response envelope is not ok")
    doc = doc.get("result")
    if not isinstance(doc, dict):
        return failures + ["observe result is not a JSON object"]
    if doc.get("schema") != "synveil.observe/v1":
        failures.append(f"schema is {doc.get('schema')!r}")
    cpu = doc.get("cpu") or {}
    utilization = cpu.get("utilization") or {}
    if utilization.get("status") != "ready":
        failures.append("cpu.utilization is not ready")
    else:
        busy = utilization.get("busy_basis_points")
        if not isinstance(busy, int) or not 0 <= busy <= 10_000:
            failures.append(f"busy_basis_points invalid: {busy!r}")
        window = utilization.get("sample_window_ms")
        if not isinstance(window, int) or window < 100:
            failures.append(f"sample_window_ms invalid: {window!r}")
    memory = doc.get("memory") or {}
    total = memory.get("total_bytes")
    available = memory.get("available_bytes")
    if not isinstance(total, int) or total <= 0:
        failures.append(f"memory.total_bytes invalid: {total!r}")
    elif not isinstance(available, int) or not 0 <= available <= total:
        failures.append(
            f"memory.available_bytes invalid: {available!r}")
    processes = doc.get("processes") or {}
    if processes.get("status") not in ("ready", "partial",
                                       "truncated"):
        failures.append(
            f"processes.status is {processes.get('status')!r}")
    if not processes.get("records"):
        failures.append("processes.records is empty")
    utilization = processes.get("utilization")
    if not isinstance(utilization, dict):
        failures.append("processes.utilization missing")
    else:
        pu_status = utilization.get("status")
        if pu_status not in ("ready", "partial", "truncated"):
            failures.append(
                f"processes.utilization.status is {pu_status!r}")
        window = utilization.get("sample_window_ms")
        if not isinstance(window, int) or window < 100:
            failures.append(
                "processes.utilization.sample_window_ms "
                f"invalid: {window!r}")
        rated = utilization.get("records")
        if not isinstance(rated, list) or not rated:
            failures.append(
                "processes.utilization.records invalid")
        else:
            total_bp = 0
            for entry in rated:
                points = entry.get("busy_basis_points") \
                    if isinstance(entry, dict) else None
                if not isinstance(points, int) \
                        or isinstance(points, bool) \
                        or not 0 <= points <= 10_000:
                    failures.append(
                        "processes.utilization "
                        f"busy_basis_points invalid: {points!r}")
                else:
                    total_bp += points
            # Rated processes can never exceed the whole
            # machine's busy share by more than per-record
            # rounding slack (at most 1 bp each, <=128
            # records).
            if total_bp > 10_000 + 128:
                failures.append(
                    "processes.utilization rates sum above "
                    f"10000 bp + slack: {total_bp}")
    pressure = doc.get("pressure")
    if not isinstance(pressure, dict):
        failures.append("pressure object missing")
    else:
        for label, require_full in (("cpu", False),
                                    ("memory", True),
                                    ("io", True)):
            problem = check_pressure_entry(
                pressure.get(label), require_full=require_full,
                label=label)
            if problem:
                failures.append(problem)
    disk = doc.get("disk")
    if not isinstance(disk, dict):
        failures.append("disk object missing")
    else:
        if disk.get("status") not in ("ready", "truncated"):
            failures.append(
                f"disk.status is {disk.get('status')!r}")
        throughput = disk.get("throughput")
        if not isinstance(throughput, dict):
            failures.append("disk.throughput missing")
        else:
            tp_status = throughput.get("status")
            if tp_status not in ("ready", "partial", "truncated"):
                failures.append(
                    f"disk.throughput.status is {tp_status!r}")
            window = throughput.get("sample_window_ms")
            if not isinstance(window, int) or window < 100:
                failures.append(
                    f"disk.throughput.sample_window_ms "
                    f"invalid: {window!r}")
            devices = throughput.get("devices")
            if not isinstance(devices, list) or not devices:
                failures.append("disk.throughput.devices invalid")
            else:
                for device in devices:
                    if not isinstance(device, dict) \
                            or not device.get("name"):
                        failures.append(
                            "disk.throughput device lacks a name")
                        continue
                    for key in ("read_bytes_per_sec",
                                "write_bytes_per_sec"):
                        value = device.get(key)
                        if not isinstance(value, int) \
                                or isinstance(value, bool) \
                                or value < 0:
                            failures.append(
                                f"disk.throughput {key} invalid: "
                                f"{value!r}")
    network = doc.get("network")
    if not isinstance(network, dict):
        failures.append("network object missing")
    else:
        if network.get("status") not in ("ready", "truncated"):
            failures.append(
                f"network.status is {network.get('status')!r}")
        bandwidth = network.get("bandwidth")
        if not isinstance(bandwidth, dict):
            failures.append("network.bandwidth missing")
        else:
            bw_status = bandwidth.get("status")
            if bw_status not in ("ready", "partial", "truncated"):
                failures.append(
                    f"network.bandwidth.status is {bw_status!r}")
            window = bandwidth.get("sample_window_ms")
            if not isinstance(window, int) or window < 100:
                failures.append(
                    f"network.bandwidth.sample_window_ms "
                    f"invalid: {window!r}")
            interfaces = bandwidth.get("interfaces")
            if not isinstance(interfaces, list) or not interfaces:
                failures.append("network.bandwidth.interfaces "
                                "invalid")
            else:
                for interface in interfaces:
                    if not isinstance(interface, dict) \
                            or not interface.get("name"):
                        failures.append(
                            "network.bandwidth interface lacks "
                            "a name")
                        continue
                    for key in ("rx_bytes_per_sec",
                                "tx_bytes_per_sec"):
                        value = interface.get(key)
                        if not isinstance(value, int) \
                                or isinstance(value, bool) \
                                or value < 0:
                            failures.append(
                                f"network.bandwidth {key} "
                                f"invalid: {value!r}")
    energy = doc.get("energy")
    if not isinstance(energy, dict):
        failures.append("energy object missing")
    else:
        power = energy.get("power")
        if power is None:
            # Legitimate only when the powercap source could
            # not be scanned at all (this guest has no
            # powercap sysfs, so the bare unavailable form is
            # the expected shape here).
            if energy.get("status") not in ("unavailable",
                                            "invalid"):
                failures.append(
                    "energy.power absent but energy.status is "
                    f"{energy.get('status')!r}")
        elif not isinstance(power, dict):
            failures.append("energy.power is not an object")
        else:
            pw_status = power.get("status")
            if pw_status not in ("ready", "partial",
                                 "truncated", "unavailable"):
                failures.append(
                    f"energy.power.status is {pw_status!r}")
            zones = power.get("zones")
            if not isinstance(zones, list):
                failures.append("energy.power.zones invalid")
            else:
                for zone in zones:
                    rate = zone.get("avg_power_uw") \
                        if isinstance(zone, dict) else None
                    if not isinstance(rate, int) \
                            or isinstance(rate, bool) or rate < 0:
                        failures.append(
                            f"energy.power avg_power_uw "
                            f"invalid: {rate!r}")
            if pw_status in ("ready", "partial"):
                window = power.get("sample_window_ms")
                if not isinstance(window, int) or window < 100 \
                        or not zones:
                    failures.append(
                        "energy.power rated without a window "
                        "or zones")
    return failures


def check_history(docs: dict, errs: dict,
                  probe_pid: int | None) -> tuple[list[str], dict]:
    """Assert the ADR 0026 lifecycle proof: the sampler was
    enabled, and the known probe process produced a started
    event (visible while it was alive) and an exited event
    (visible after it exited), same identity, in order."""
    failures: list[str] = []
    info: dict = {"probe_pid": probe_pid}
    for name in ("h0", "h1", "h2"):
        if errs.get(name, b"").strip():
            failures.append(
                f"synctl wrote to stderr for {name} "
                "(client refused the history response): "
                + errs[name].decode(errors="replace")[:200])
        doc = docs.get(name)
        if not isinstance(doc, dict):
            failures.append(f"{name} history capture missing")
            continue
        if doc.get("ok") is not True:
            failures.append(f"{name} response envelope is not ok")
            continue
        result = doc.get("result")
        if not isinstance(result, dict):
            failures.append(f"{name} result is not a JSON object")
            continue
        if result.get("schema") != "synveil.observe-history/v1":
            failures.append(f"{name} schema is {result.get('schema')!r}")
        sampler = result.get("sampler") or {}
        if sampler.get("enabled") is not True:
            failures.append(f"{name} sampler is not enabled")
        if sampler.get("cadence_ms") != 5000:
            failures.append(
                f"{name} cadence_ms is {sampler.get('cadence_ms')!r}")
        if sampler.get("ring_capacity") != 1024:
            failures.append(
                f"{name} ring_capacity is "
                f"{sampler.get('ring_capacity')!r}")
        for event in result.get("events") or []:
            if not isinstance(event, dict) \
                    or event.get("schema") != "synveil.observe-event/v1":
                failures.append(f"{name} carries a non-event record")
                break
    if failures:
        return failures, info
    if probe_pid is None or probe_pid <= 0:
        return failures + ["probe pid was not recorded"], info

    def find(doc, kind):
        result = doc.get("result") or {}
        for event in result.get("events") or []:
            process = ((event.get("fields") or {}).get("process")
                       or {})
            if event.get("event") == kind \
                    and process.get("pid") == probe_pid:
                return event
        return None

    started = find(docs["h1"], "process_started")
    if started is None:
        failures.append(
            "no process_started event for the probe in h1")
        return failures, info
    started_process = (started.get("fields") or {}).get("process") or {}
    info["started_sequence"] = started.get("sequence")
    info["probe_start_time_ticks"] = started_process.get(
        "start_time_ticks")
    # The ring retains the started event in the later snapshot.
    if find(docs["h2"], "process_started") is None:
        failures.append("started event not retained in h2")
    exited = find(docs["h2"], "process_exited")
    if exited is None:
        failures.append(
            "no process_exited event for the probe in h2")
        return failures, info
    exited_process = (exited.get("fields") or {}).get("process") or {}
    info["exited_sequence"] = exited.get("sequence")
    if exited_process.get("start_time_ticks") \
            != started_process.get("start_time_ticks"):
        failures.append(
            "exited event start_time_ticks does not match the "
            "started event (identity mismatch)")
    if not isinstance(exited.get("sequence"), int) \
            or not isinstance(started.get("sequence"), int) \
            or exited["sequence"] <= started["sequence"]:
        failures.append("exited event does not follow the started event")
    for key in ("user_ticks", "system_ticks"):
        value = exited_process.get(key)
        if not isinstance(value, int) or isinstance(value, bool) \
                or value < 0:
            failures.append(f"exited event {key} invalid: {value!r}")
    return failures, info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("observe smoke requires a non-root runner")
    proof = json.loads((IMAGE_DIR / "validation.json").read_text())
    source_image = IMAGE_DIR / "synveil-x86_64.img"
    if (proof.get("schema") != "synveil.native-joined-image/v1"
            or proof.get("state_partuuid") != STATE_PARTUUID
            or source_image.is_symlink() or not source_image.is_file()
            or hashlib.sha256(source_image.read_bytes()).hexdigest()
            != proof.get("image_sha256")):
        parser.error("joined image missing or changed since build")
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_hex(16)

    doc = None
    err_bytes = b""
    attempts = 0
    failures: list[str] = []
    history_info: dict = {}
    for attempt in range(1, 4):
        attempts = attempt
        with tempfile.TemporaryDirectory(
                prefix="synveil-observe-") as temp:
            work = Path(temp)
            image = work / "synveil-x86_64.img"
            shutil.copyfile(source_image, image)
            if not boot_and_observe(work, secret, out):
                print(f"[synveil] attempt {attempt}: boot failed")
                continue
            state = work / "state.img"
            extract_state(image, state)
            replay_journal(state)
            raw = work / "observe.json"
            found = dump_state_file(
                state, ["tmp/observe.json"], raw)
            if found is None:
                print(f"[synveil] attempt {attempt}: "
                      "observe.json not found in state partition")
                continue
            err_raw = work / "observe.err"
            dump_state_file(
                state, ["tmp/observe.err"], err_raw)
            err_bytes = (err_raw.read_bytes()
                         if err_raw.exists() else b"")
            try:
                doc = json.loads(raw.read_bytes())
            except (ValueError, UnicodeDecodeError) as exc:
                # Preserve the raw capture and synctl's stderr:
                # an empty .json with a non-empty .err is synctl
                # refusing (socket, validation), and the .err
                # text is the diagnosis.
                shutil.copyfile(raw, out / "observe.json")
                (out / "observe.err").write_bytes(err_bytes)
                failures = [f"observe.json does not parse: {exc}"]
                doc = None
                break
            shutil.copyfile(raw, out / "observe.json")
            (out / "observe.err").write_bytes(err_bytes)
            failures = check_observe(doc, err_bytes)
            # History slice (ADR 0026): the same boot ran the
            # observe-history harness line; read its captures
            # back and assert the probe's lifecycle events.
            history_docs: dict = {}
            history_errs: dict = {}
            history_broken = False
            for name in ("h0", "h1", "h2"):
                raw_h = work / f"{name}.json"
                if dump_state_file(
                        state, [f"tmp/{name}.json"], raw_h) is None:
                    failures.append(
                        f"{name}.json not found in state partition")
                    history_broken = True
                    break
                err_h = work / f"{name}.err"
                dump_state_file(state, [f"tmp/{name}.err"], err_h)
                history_errs[name] = (
                    err_h.read_bytes() if err_h.exists() else b"")
                shutil.copyfile(raw_h, out / f"{name}.json")
                (out / f"{name}.err").write_bytes(history_errs[name])
                try:
                    history_docs[name] = json.loads(raw_h.read_bytes())
                except (ValueError, UnicodeDecodeError) as exc:
                    failures.append(f"{name}.json does not parse: {exc}")
                    history_broken = True
                    break
            if not history_broken:
                probe_raw = work / "p.pid"
                probe_pid = None
                if dump_state_file(
                        state, ["tmp/p.pid"], probe_raw) is not None:
                    shutil.copyfile(probe_raw, out / "p.pid")
                    try:
                        probe_pid = int(
                            probe_raw.read_text().strip())
                    except ValueError:
                        probe_pid = None
                history_failures, history_info = check_history(
                    history_docs, history_errs, probe_pid)
                failures += history_failures
            break
    if doc is None and not failures:
        failures = ["no boot attempt produced an observe capture"]
    pressure = (((doc or {}).get("result") or {}).get("pressure")
                or {})
    receipt = {
        "schema": "synveil.observe-acceptance/v1",
        "image_sha256": proof["image_sha256"],
        "passed": not failures,
        "physical_hardware_tested": False,
        "attempts": attempts,
        "pressure_status": {
            label: (pressure.get(label) or {}).get("status")
            for label in ("cpu", "memory", "io")},
        "history": history_info,
        "failures": failures,
    }
    (out / "result.json").write_text(
        json.dumps(receipt, indent=2) + "\n")
    for failure in failures:
        print(f"[synveil] FAIL: {failure}")
    if failures:
        print("[synveil] observe acceptance FAILED")
        return 1
    print("SYNVEIL_OBSERVE_QEMU_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
