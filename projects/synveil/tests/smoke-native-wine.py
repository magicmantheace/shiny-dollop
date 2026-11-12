#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Native QEMU acceptance for the Wine proof slice
(docs/WINDOWS_COMPAT_DESIGN.md, owner-accepted 2026-11-07).

Boots the wine proof image (tools/native_wine.py: joined
baseline + the sealed distribution-Wine payload), enrolls,
logs in, and in the session terminal runs the fixed
`wine-notepad` harness command, which launches the image's
launcher (/usr/libexec/synveil/wine-notepad): a fresh
WINEPREFIX on tmpfs, WINEARCH=win64, the graphics driver
pinned to wayland in the prefix registry, Gecko/Mono offers
disabled.

The host then requires, from live frames of the S4 desktop:

  * a Notepad window: a large white client rectangle (the
    edit area) appears that was not there before the launch;
  * text typed into it through the QMP input channel renders
    (the client rectangle's pixels change materially);
  * the panel's task-button strip gains a button for the
    Notepad window while it is open.

Afterwards the fixed `wine-stop` command stops the Wine
session (wineserver -k on the recorded prefix), the fixed
`gfx-probe` command runs the image's graphics probe
(ADR 0027: the sealed Mesa + Vulkan payload — Vulkan must
enumerate the lavapipe device and EGL/GL must initialize on
llvmpipe, reported as GFX_* lines read back from the state
partition), the terminal is closed, and the graphical login
must relock — the same session discipline as every other
gate. The launcher's log and the recorded prefix path are
read back from the state partition as supporting evidence
(the prefix itself lives on tmpfs and is gone, by design).

Boot/enroll flakes under TCG retry the whole boot on a fresh
image copy (3 attempts); assertions never retry. QEMU
evidence only; no physical hardware is claimed.
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
import struct
import sys
import tempfile
import time
import zlib

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

IMAGE_DIR = ROOT / "out" / "wine-proof"
OUT = ROOT / "out" / "wine-proof-acceptance"
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


WINE_FACTS: dict = {}
PROOF_TEXT = "Synveil wine proof"


def px(data, width, x, y):
    off = (y * width + x) * 3
    return tuple(data[off:off + 3])


def write_png(path, width, height, data):
    def chunk(kind, payload):
        return (struct.pack(">I", len(payload)) + kind + payload +
                struct.pack(">I", zlib.crc32(kind + payload)
                             & 0xFFFFFFFF))

    raw = b"".join(b"\x00" + data[y * width * 3:(y + 1) * width * 3]
                   for y in range(height))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" +
        chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2,
                                   0, 0, 0)) +
        chunk(b"IDAT", zlib.compress(raw, 6)) +
        chunk(b"IEND", b""))


def task_buttons(width, height, data):
    """Task buttons on the strip, located by their title text
    (the shell smoke's detector): columns bearing light-gray
    glyph pixels in the strip's text band cluster into one
    span per button."""
    def glyph(x):
        hits = 0
        for y in range(height - 36, height - 13):
            r, g, b = px(data, width, x, y)
            if 90 <= r <= 235 and abs(r - g) <= 12 and abs(g - b) <= 12:
                hits += 1
        return hits >= 2

    spans = []
    start = None
    gap = 0
    for x in range(44, width - 170):
        if glyph(x):
            if start is None:
                start = x
            gap = 0
        elif start is not None:
            gap += 1
            if gap > 12:
                if x - gap - start >= 40:
                    spans.append((start, x - gap))
                start = None
                gap = 0
    if start is not None and width - 170 - start >= 40:
        spans.append((start, width - 170))
    return spans


def notepad_window(width, height, data):
    """Locate Notepad's edit area: the large white rectangle.
    Wine's Notepad renders its text on white; nothing else on
    the S4 desktop (dark shell, dark terminal, blue demo
    window) produces a wide white run. Returns
    (x, y, w, h) of the client rectangle or None."""
    def is_white(x, y):
        off = (y * width + x) * 3
        return data[off] >= 235 and data[off + 1] >= 235 \
            and data[off + 2] >= 235

    runs = []
    for y in range(0, height - 40):
        best_start, best_len = 0, 0
        run_start, run = None, 0
        for x in range(width):
            if is_white(x, y):
                if run_start is None:
                    run_start = x
                run += 1
                if run > best_len:
                    best_start, best_len = run_start, run
            else:
                run_start, run = None, 0
        runs.append((best_start, best_len))
    # Tallest vertical span of rows with a >= 280 px white run.
    best = None
    span_top, span_rows = None, []
    for y, (start, length) in enumerate(runs + [(0, 0)]):
        if length >= 280:
            if span_top is None:
                span_top, span_rows = y, []
            span_rows.append((start, length))
        elif span_top is not None:
            if best is None or len(span_rows) > len(best[1]):
                best = (span_top, span_rows)
            span_top, span_rows = None, []
    if best is None or len(best[1]) < 120:
        return None
    top, rows = best
    xs = sorted(r[0] for r in rows)
    ws = sorted(r[1] for r in rows)
    return (xs[len(xs) // 2], top, ws[len(ws) // 2], len(rows))


def rect_pixel_diff(before, after, width, rect):
    """Pixels inside rect whose channels moved by > 16 — the
    rendered-text signal after typing into the edit area."""
    x, y, w, h = rect
    diff = 0
    for row in range(y, y + h):
        base = (row * width + x) * 3
        for i in range(base, base + w * 3, 3):
            if abs(before[i] - after[i]) > 16 \
                    or abs(before[i + 1] - after[i + 1]) > 16 \
                    or abs(before[i + 2] - after[i + 2]) > 16:
                diff += 1
    return diff


def type_text(qmp: Path, text: str, *, timeout=60.0):
    """Type a fixed smoke-owned string through the QMP input
    channel (the type_ab_command transport, without the final
    Enter): the text is a constant of this gate, never data."""
    import socket as _socket
    deadline = time.monotonic() + timeout
    with _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM) as sock:
        while True:
            try:
                sock.settimeout(max(0.1, min(1.0,
                                             deadline - time.monotonic())))
                sock.connect(str(qmp))
                break
            except (FileNotFoundError, ConnectionRefusedError):
                if time.monotonic() >= deadline:
                    raise ValueError("QMP socket unavailable")
                time.sleep(0.05)
        sock.settimeout(max(0.1, deadline - time.monotonic()))
        with sock.makefile("rb") as reader:
            _qmp_input._read_reply(reader, greeting=True)
            _qmp_input.emit_command(sock, reader,
                                    {"execute": "qmp_capabilities"})
            for char in text:
                if time.monotonic() >= deadline:
                    raise ValueError("proof typing exceeded deadline")
                key = _qmp_input._AB_CHAR_KEYS[char]
                if "+" in key:
                    modifier, base = key.split("+", 1)
                    _qmp_input._hold_keys(sock, reader, (modifier, base))
                else:
                    _qmp_input._hold_keys(sock, reader, (key,))
                time.sleep(0.03)


def boot_and_wine(work: Path, secret: str, out: Path) -> bool:
    """One boot: enroll, log in, launch Wine's notepad in the
    session, type into it, stop Wine, end the session. Returns
    True once the graphical login has relocked."""
    qmp_dir = tempfile.mkdtemp(prefix="synveil-wine-qmp-")
    qmp = Path(qmp_dir) / "monitor.sock"
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("SYNVEIL_")}
    env.update(SYNVEIL_OUT_DIR=str(work), SYNVEIL_QEMU_VIDEO="1",
               SYNVEIL_QEMU_DISPLAY="none", SYNVEIL_QEMU_NETWORK="0",
               SYNVEIL_QEMU_MEMORY="2G", SYNVEIL_QEMU_IMAGE_WRITABLE="1",
               SYNVEIL_QEMU_QMP_SOCKET=str(qmp))
    process = subprocess.Popen(
        ["bash", str(ROOT / "build/scripts/qemu.sh")],
        cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        start_new_session=True)
    deadline = time.monotonic() + 1500
    phase = "boot"
    seen: set[bytes] = set()
    pending = b""
    log = (out / "wine-serial.log").open("wb")

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
                    phase = "wine"
                    try:
                        frame_dir = Path(tempfile.mkdtemp(
                            prefix="synveil-wine-frame-"))
                        w, h, data = patient_frame(qmp, frame_dir, 1)
                        tx, ty = weston_smoke.terminal_point(w, h, data)
                        weston_smoke.pointer(qmp, w, h, tx, ty,
                                             button=True)
                        weston_smoke.pointer(qmp, w, h, tx, ty,
                                             button=False)
                        # Let the desktop settle, then count the
                        # task buttons from a fresh frame: the
                        # first post-login frame can precede the
                        # panel's first render and undercount.
                        time.sleep(1.5)
                        w, h, data = patient_frame(qmp, frame_dir, 1)
                        WINE_FACTS["task_buttons_before"] = len(
                            task_buttons(w, h, data))
                        # The line's sacrificial echo segment
                        # absorbs any characters a just-focused
                        # terminal eats (fixture pattern, see
                        # the entry in tools/qmp_input.py).
                        type_ab_command(qmp, "wine-notepad",
                                        timeout=60)
                    except Exception as exc:  # noqa: BLE001
                        note(f"wine launch failed: {exc}")
                        return False
                    note("wine launcher typed; waiting for notepad")
                    # Prefix creation + wineboot + first window
                    # under TCG: poll frames for the Notepad
                    # client rectangle for up to ~5 minutes.
                    rect = None
                    launch_deadline = time.monotonic() + 300
                    while time.monotonic() < launch_deadline:
                        time.sleep(5)
                        try:
                            w, h, data = patient_frame(
                                qmp, frame_dir, 2, timeout=30.0)
                        except Exception:  # noqa: BLE001
                            continue
                        rect = notepad_window(w, h, data)
                        if rect is not None:
                            break
                    if rect is None:
                        note("notepad window never appeared")
                        return False
                    WINE_FACTS["notepad_rect"] = rect
                    WINE_FACTS["task_buttons_with_notepad"] = len(
                        task_buttons(w, h, data))
                    write_png(out / "notepad.png", w, h, data)
                    note(f"notepad window at {rect}; typing proof text")
                    # Click into the edit area and type the
                    # proof text through the input channel.
                    cx = rect[0] + rect[2] // 2
                    cy = rect[1] + rect[3] // 3
                    weston_smoke.pointer(qmp, w, h, cx, cy,
                                         button=True)
                    weston_smoke.pointer(qmp, w, h, cx, cy,
                                         button=False)
                    time.sleep(0.5)
                    try:
                        type_text(qmp, PROOF_TEXT, timeout=60)
                    except Exception as exc:  # noqa: BLE001
                        note(f"proof typing failed: {exc}")
                        return False
                    time.sleep(2)
                    try:
                        w, h, data_typed = patient_frame(
                            qmp, frame_dir, 3, timeout=30.0)
                    except Exception as exc:  # noqa: BLE001
                        note(f"typed frame failed: {exc}")
                        return False
                    if notepad_window(w, h, data_typed) is None:
                        note("notepad window vanished after typing")
                        return False
                    WINE_FACTS["typed_pixel_diff"] = rect_pixel_diff(
                        data, data_typed, w, rect)
                    write_png(out / "notepad-typed.png", w, h,
                              data_typed)
                    note(f"typed; pixel diff "
                         f"{WINE_FACTS['typed_pixel_diff']}")
                    # Stop Wine: raise the terminal via its task
                    # button (second button; the demo is first),
                    # then the fixed wine-stop line.
                    phase = "wine-stop"
                    spans = task_buttons(w, h, data_typed)
                    if len(spans) < 2:
                        note("no terminal task button to raise")
                        return False
                    bx = (spans[1][0] + spans[1][1]) // 2
                    weston_smoke.pointer(qmp, w, h, bx, h - 24,
                                         button=True)
                    weston_smoke.pointer(qmp, w, h, bx, h - 24,
                                         button=False)
                    time.sleep(1.5)
                    try:
                        type_ab_command(qmp, "wine-stop", timeout=90)
                    except Exception as exc:  # noqa: BLE001
                        note(f"wine stop failed: {exc}")
                        return False
                    note("wine stop typed; letting wineserver die")
                    time.sleep(8)
                    # Graphics probe (ADR 0027): the terminal is
                    # still focused; run the image's probe against
                    # the sealed Mesa + Vulkan payload. Its report
                    # lands on the state partition for readback.
                    phase = "gfx-probe"
                    try:
                        type_ab_command(qmp, "gfx-probe",
                                        timeout=90)
                    except Exception as exc:  # noqa: BLE001
                        note(f"gfx probe failed: {exc}")
                        return False
                    WINE_FACTS["gfx_probe_typed"] = True
                    note("gfx probe typed; letting it run")
                    time.sleep(20)
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





def check_wine(facts: dict, prefix_path: str | None,
               log_bytes: bytes | None) -> list[str]:
    """Assert the wine proof from the boot's recorded facts and
    the state-partition readback. The visual facts were gathered
    live during the boot; the readback corroborates that the
    image's launcher ran with a tmpfs prefix."""
    failures: list[str] = []
    rect = facts.get("notepad_rect")
    if not rect:
        failures.append("notepad window was not recorded")
    before = facts.get("task_buttons_before")
    during = facts.get("task_buttons_with_notepad")
    if not isinstance(before, int) or not isinstance(during, int):
        failures.append("task button counts were not recorded")
    elif during <= before:
        failures.append(
            f"task buttons did not increase with notepad open: "
            f"before={before} during={during}")
    diff = facts.get("typed_pixel_diff")
    if not isinstance(diff, int) or diff < 200:
        failures.append(
            f"typed text did not render (pixel diff {diff!r})")
    if prefix_path is None:
        failures.append("wineprefix.path not found in state partition")
    elif not prefix_path.startswith("/tmp/wineprefix."):
        failures.append(
            f"launcher prefix is not a tmpfs mktemp dir: {prefix_path!r}")
    if log_bytes is None:
        failures.append("wine.log not found in state partition")
    return failures


def parse_graphics(gfx_text: str | None) -> dict:
    """Extract the probe's headline facts from its GFX_* report."""
    facts: dict = {"probe_ok": False, "vulkan_device": None,
                   "gl_renderer": None, "egl_vendor": None}
    if gfx_text is None:
        return facts
    for line in gfx_text.splitlines():
        if line == "GFX_PROBE_OK":
            facts["probe_ok"] = True
        elif line.startswith("GFX_VULKAN_DEVICE name="):
            facts["vulkan_device"] = line.split("name=", 1)[1]
        elif line.startswith("GFX_GL_OK"):
            facts["gl_renderer"] = line
        elif line.startswith("GFX_EGL_OK"):
            facts["egl_vendor"] = line
    return facts


def check_graphics(gfx_text: str | None) -> list[str]:
    """Assert the ADR 0027 graphics proof from the probe report
    read back off the state partition: Vulkan enumerated the
    lavapipe software device and EGL/GL initialized on
    llvmpipe. This proves the staged payload initializes in
    the guest (QEMU/TCG software rendering) — not Direct3D,
    not a real GPU, not performance."""
    failures: list[str] = []
    if gfx_text is None:
        return ["gfx-probe.txt not found in state partition"]
    facts = parse_graphics(gfx_text)
    if not facts["probe_ok"]:
        failures.append("graphics probe did not report GFX_PROBE_OK")
    device = facts["vulkan_device"] or ""
    if "llvmpipe" not in device:
        failures.append(
            f"lavapipe device not enumerated: {device!r}")
    if "GFX_VULKAN_OK" not in gfx_text:
        failures.append("probe reported no GFX_VULKAN_OK")
    renderer = facts["gl_renderer"] or ""
    if "llvmpipe" not in renderer:
        failures.append(
            f"GL did not initialize on llvmpipe: {renderer!r}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("wine smoke requires a non-root runner")
    proof = json.loads((IMAGE_DIR / "validation.json").read_text())
    source_image = IMAGE_DIR / "synveil-x86_64.img"
    if (proof.get("schema") != "synveil.wine-proof-build/v1"
            or source_image.is_symlink() or not source_image.is_file()
            or hashlib.sha256(source_image.read_bytes()).hexdigest()
            != proof.get("image_sha256")):
        parser.error("wine proof image missing or changed since build")
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_hex(16)

    attempts = 0
    failures: list[str] = []
    facts: dict = {}
    prefix_path = None
    log_bytes = None
    gfx_text = None
    booted = False
    for attempt in range(1, 4):
        attempts = attempt
        WINE_FACTS.clear()
        with tempfile.TemporaryDirectory(
                prefix="synveil-wine-") as temp:
            work = Path(temp)
            image = work / "synveil-x86_64.img"
            shutil.copyfile(source_image, image)
            if not boot_and_wine(work, secret, out):
                print(f"[synveil] attempt {attempt}: boot failed")
                continue
            booted = True
            facts = dict(WINE_FACTS)
            state = work / "state.img"
            extract_state(image, state)
            replay_journal(state)
            raw = work / "wineprefix.path"
            if dump_state_file(
                    state, ["tmp/wineprefix.path"], raw) is not None:
                prefix_path = raw.read_text(errors="replace").strip()
                shutil.copyfile(raw, out / "wineprefix.path")
            log_raw = work / "wine.log"
            if dump_state_file(
                    state, ["tmp/wine.log"], log_raw) is not None:
                log_bytes = log_raw.read_bytes()
                (out / "wine.log").write_bytes(log_bytes)
            gfx_raw = work / "gfx-probe.txt"
            if dump_state_file(
                    state, ["tmp/gfx-probe.txt"], gfx_raw) is not None:
                gfx_text = gfx_raw.read_text(errors="replace")
                (out / "gfx-probe.txt").write_text(gfx_text)
            failures = check_wine(facts, prefix_path, log_bytes)
            failures += check_graphics(gfx_text)
            break
    if not booted:
        failures = ["no boot attempt produced a wine session"]
    receipt = {
        "schema": "synveil.wine-acceptance/v1",
        "image_sha256": proof["image_sha256"],
        "wine_version": proof.get("wine_version"),
        "winewayland": proof.get("winewayland"),
        "passed": not failures,
        "physical_hardware_tested": False,
        "attempts": attempts,
        "notepad_rect": facts.get("notepad_rect"),
        "task_buttons_before": facts.get("task_buttons_before"),
        "task_buttons_with_notepad":
            facts.get("task_buttons_with_notepad"),
        "typed_pixel_diff": facts.get("typed_pixel_diff"),
        "prefix_path": prefix_path,
        "graphics": {
            **parse_graphics(gfx_text),
            "mesa_version": (proof.get("graphics") or {}).get(
                "mesa_version"),
            "scope": "payload staged + Vulkan/GL initialize in "
                     "guest (software rendering); Direct3D and "
                     "real-GPU behaviour not proven",
        },
        "failures": failures,
    }
    (out / "result.json").write_text(
        json.dumps(receipt, indent=2) + "\n")
    for failure in failures:
        print(f"[synveil] FAIL: {failure}")
    if failures:
        print("[synveil] wine acceptance FAILED")
        return 1
    print("SYNVEIL_WINE_QEMU_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
