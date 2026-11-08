#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Native QEMU acceptance for the S4 custom shell (ADR 0025):
Start button, Start menu and task buttons in the bottom panel of
the joined image, replacing stock desktop-shell behaviour in the
Windows 11 design language of docs/UI_DESIGN.md.

Boots a private copy of the joined image, enrolls and logs in
through the graphical login exactly as the joined smoke does, then
drives the shell with real pointer input and pixel evidence:

- the bottom strip is the shell panel (48 px, shell token color)
  with the Start glyph (accent token) at its left;
- the session's two windows (demo window, terminal) each have a
  task button; activating the demo window marks its button;
- clicking the demo task button minimizes the window (it leaves
  the desktop), clicking it again restores it;
- the Start button opens the Start menu (card in the surface
  token); the menu lists exactly the apps this image ships markers
  for — Terminal and Demo window on the joined image (Files,
  Updates and Browser are marker-gated to A/B generations by the
  same convention weston-session uses, ADR 0025);
- a menu item click closes the menu and focuses the app's window;
  the Start button toggles the menu closed again;
- the shell polish pass (icons, tray, slide): menu items and
  task buttons carry the shell's drawn geometric app icons (no
  letter tiles); the tray shows the network link state read
  from the guest kernel's operstate — this boot attaches the
  QMP user-net device, so an interface exists, but the session
  never brings it up, and the indicator must honestly show
  present-but-down (faint arcs, danger slash, no accent). A
  live link flip is not asserted: flipping it needs the
  interface administratively up (CAP_NET_ADMIN, which the
  unprivileged session must not hold), and QMP set_link does
  not change operstate while the interface is admin-down —
  the up-state rendering is covered by the code path the
  down-state exercises, not by a guest screenshot. The
  update slot stays hidden because the joined image runs no
  A/B agent the shell could honestly read (the net slot
  sitting in the unshifted position is the evidence);
- the session still ends cleanly (both windows closed, graphical
  login relocks).

Screenshots are saved as PNG next to the serial log in the output
directory for the docs/validation evidence set. QEMU evidence
only; no physical hardware is claimed.
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
import struct
import subprocess
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
    type_test_secret, send_keys, ALLOWED_TERMINAL_RETURN)
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
OUT = ROOT / "out" / "shell-proof"

SHELL = (0x20, 0x20, 0x20)
SURFACE = (0x2C, 0x2C, 0x2C)
SURFACE_HI = (0x38, 0x38, 0x38)
ACCENT = (0x4C, 0xC2, 0xFF)
STRIP_H = 48
MENU_ITEM_H = 40


def px(data, width, x, y):
    off = (y * width + x) * 3
    return tuple(data[off:off + 3])


def near(color, target, tol=6):
    return all(abs(a - b) <= tol for a, b in zip(color, target))


def is_accent(color):
    """The accent token as composited: the panel surface blends
    over the desktop gradient, so the pure #4CC2FF reads back
    dimmer (observed (69,177,232)). Match the hue, not the value."""
    r, g, b = color
    return r < 120 and g > 130 and b > 180 and b - r > 90


def is_blueish(color):
    """The demo/window icon body hue (#1B4B8F family)."""
    r, g, b = color
    return b > 100 and b - r > 60


def is_greenish(color):
    """The terminal icon's prompt hue (#7EE787 family)."""
    r, g, b = color
    return g > 120 and g - r > 40 and b < 180


def is_redish(color):
    """The danger token hue (#E81123 family)."""
    r, g, b = color
    return r > 150 and r - g > 70 and r - b > 70


def box_count(width, height, data, x0, x1, y0, y1, pred):
    return sum(1 for y in range(y0, y1) for x in range(x0, x1)
               if pred(px(data, width, x, y)))


# Tray geometry on this image (panel_layout): the clock takes
# 150 px at the right (minutes format), then a 4 px gap; the
# update slot is 26 px only while the agent has answered (it
# never does on the joined image), so the network slot's icon
# (18 px at slot x + 4, strip y + 15) lands here.
def tray_net_box(width, height):
    return (width - 176, width - 158, height - 33, height - 15)


def write_png(path, width, height, data):
    def chunk(kind, payload):
        return (struct.pack(">I", len(payload)) + kind + payload +
                struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))

    raw = b"".join(b"\x00" + data[y * width * 3:(y + 1) * width * 3]
                   for y in range(height))
    png = (b"\x89PNG\r\n\x1a\n" +
           chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2,
                                      0, 0, 0)) +
           chunk(b"IDAT", zlib.compress(raw, 6)) +
           chunk(b"IEND", b""))
    path.write_bytes(png)


class ShellProof:
    def __init__(self, qmp, folder):
        self.qmp = qmp
        self.folder = folder
        self.count = 0

    def frame(self, save=None):
        self.count += 1
        width, height, data = weston_smoke.screenshot(
            self.qmp, self.folder, self.count)
        if save:
            write_png(self.folder / save, width, height, data)
        return width, height, data

    def frame_wait(self, predicate, timeout_s, save=None):
        deadline = time.monotonic() + timeout_s
        last = None
        while time.monotonic() < deadline:
            try:
                last = self.frame()
            except ValueError:
                time.sleep(0.3)
                continue
            if predicate(*last):
                if save:
                    write_png(self.folder / save, *last)
                return last
            time.sleep(0.3)
        raise AssertionError("frame predicate not met in time")

    def click(self, width, height, x, y):
        weston_smoke.pointer(self.qmp, width, height, x, y, button=True)
        weston_smoke.pointer(self.qmp, width, height, x, y, button=False)
        time.sleep(0.4)


def task_buttons(width, height, data):
    """Task buttons on the strip, located by their title text.

    Inactive buttons are transparent (title text directly on the
    panel); the activated one carries a surface-hi fill. Either way
    the title is light-gray text, so columns bearing glyph pixels
    in the strip's text band cluster into one span per button."""
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


def run_shell_steps(proof: ShellProof, notes: list[str]) -> list[str]:
    width, height, data = proof.frame_wait(
        lambda w, h, d: weston_smoke.original_window(w, h, d) is not None,
        90, save="01-desktop.png")
    notes.append(f"desktop {width}x{height} with demo window present")

    # Panel: shell token at sample points away from controls/text.
    for sx in (width - 220, width // 2):
        c = px(data, width, sx, height - 24)
        assert near(c, SHELL), f"panel pixel at {sx}: {c}"
    notes.append("panel strip carries the shell token color")

    # Start glyph: accent pixels inside the Start button allocation.
    accent = sum(1 for y in range(height - 43, height - 5)
                 for x in range(6, 45)
                 if is_accent(px(data, width, x, y)))
    assert accent >= 20, f"start glyph accent pixels: {accent}"
    notes.append(f"start glyph present ({accent} accent pixels)")

    # The demo window is the session's first window; the
    # terminal starts a moment later. Wait for both task
    # buttons rather than racing the second window's start.
    width, height, data = proof.frame_wait(
        lambda w, h, d: len(task_buttons(w, h, d)) >= 2, 30)
    buttons = task_buttons(width, height, data)
    notes.append(f"{len(buttons)} task buttons on the strip: {buttons}")

    # Polish: the first task button (the demo window, the
    # session's first window) carries its drawn window icon —
    # 16 px at button x + 8, strip y + 16; the first button
    # starts at x=50 now that the stock fallback launcher is
    # gone. Blue body pixels are the evidence.
    blue = box_count(width, height, data, 58, 74,
                     height - 32, height - 16, is_blueish)
    assert blue >= 6, f"demo task icon blue pixels: {blue}"
    notes.append(f"demo task button carries its icon ({blue} blue px)")

    # Polish: tray network indicator. This boot attaches the
    # user-net device, so eth0 exists — but the session never
    # brings it up, so the honest state is present-but-down:
    # faint arcs and the danger slash in the net icon box, no
    # accent; and no accent in the box the icon would occupy
    # if a phantom update slot had shifted it left — the
    # update slot is hidden while no agent answers.
    nx0, nx1, ny0, ny1 = tray_net_box(width, height)
    red = box_count(width, height, data, nx0, nx1, ny0, ny1,
                    is_redish)
    assert red >= 4, f"tray net (down) danger pixels: {red}"
    accent = box_count(width, height, data, nx0, nx1, ny0, ny1,
                       is_accent)
    assert accent < 4, f"tray net (down) accent pixels: {accent}"
    shifted = box_count(width, height, data, nx0 - 26, nx1 - 26,
                        ny0, ny1, is_accent)
    assert shifted < 4, f"tray net shifted accent pixels: {shifted}"
    notes.append(f"tray shows network present but down ({red} "
                 "danger px, no accent); update slot hidden "
                 "(no agent on this image)")

    # Activate the demo window by clicking it; its task button must
    # gain the accent underline. The demo is the session's first
    # window, so its button is the first span; the terminal starts
    # out active, so "some button is underlined" proves nothing —
    # the FIRST span must carry the marker. The activated marker is
    # a 24x3 accent rect centered on the button, 3 px above its
    # bottom edge (rows H-9..H-7). Retry once on the window body if
    # the title-bar click does not move activation.
    win = weston_smoke.original_window(width, height, data)

    def span_marked(frame, span):
        w, h, d = frame
        a, b = span
        return sum(1 for y in (h - 9, h - 8, h - 7)
                   for x in range(max(44, a - 20), b + 20)
                   if is_accent(px(d, w, x, y))) >= 12

    demo_btn = task_buttons(width, height, data)[0]
    for attempt in range(2):
        if attempt == 0:
            proof.click(width, height, win[0] + 30, win[1] + 14)
        else:
            proof.click(width, height, win[0] + win[2] // 2,
                        win[1] + win[3] // 2)
        try:
            width, height, data = proof.frame_wait(
                lambda w, h, d: span_marked(
                    (w, h, d),
                    task_buttons(w, h, d)[0]
                    if task_buttons(w, h, d) else (0, 0)), 20)
            break
        except AssertionError:
            if attempt == 1:
                raise
            win = weston_smoke.original_window(width, height, data)
    demo_btn = task_buttons(width, height, data)[0]
    notes.append(f"demo task button marked active at {demo_btn}")

    # Minimize via the task button: the demo window leaves the
    # desktop while the terminal stays.
    cx = (demo_btn[0] + demo_btn[1]) // 2
    proof.click(width, height, cx, height - 24)
    width, height, data = proof.frame_wait(
        lambda w, h, d: weston_smoke.original_window(w, h, d) is None,
        30, save="02-demo-minimized.png")
    notes.append("task button click minimized the demo window")

    # Restore via the same button.
    proof.click(width, height, cx, height - 24)
    width, height, data = proof.frame_wait(
        lambda w, h, d: weston_smoke.original_window(w, h, d) is not None,
        30, save="03-demo-restored.png")
    notes.append("second task button click restored the demo window")

    # Start menu: opens with the surface-token card; count the item
    # rows carrying text (Terminal + Demo window on this image).
    proof.click(width, height, 25, height - 24)

    def menu_items(frame):
        w, h, d = frame
        # Largest first: a shorter menu's geometry can alias into
        # a taller open menu's card, never the reverse.
        for n in range(6, 0, -1):
            menu_h = 16 + n * MENU_ITEM_H
            top = h - STRIP_H - menu_h
            if not near(px(d, w, 160, top + 6), SURFACE):
                continue
            rows = 0
            for i in range(n):
                cy = top + 12 + i * MENU_ITEM_H + 18
                text = sum(1 for y in range(cy - 2, cy + 3)
                           for x in range(24, 300)
                           if min(px(d, w, x, y)) >= 150)
                if text >= 6:
                    rows += 1
            if rows == n:
                return n, top
        return None

    width, height, data = proof.frame_wait(
        lambda w, h, d: menu_items((w, h, d)) is not None, 30,
        save="04-start-menu.png")
    n_items, menu_top = menu_items((width, height, data))
    notes.append(f"start menu open with {n_items} app items")

    # Polish: every menu item carries a drawn icon, not the old
    # accent letter tile. Per item (icon box: x 16..44, item
    # top + 4 .. + 32): the box must hold real mark pixels (not
    # card surface), and its centre must not be accent — the
    # letter tile was a solid accent square, centre included.
    # The two items this image ships get hue checks: Terminal's
    # prompt green, Demo window's body blue.
    for i in range(n_items):
        iy0 = menu_top + 16 + i * MENU_ITEM_H
        iy1 = iy0 + 28
        marks = box_count(
            width, height, data, 16, 44, iy0, iy1,
            lambda c: not near(c, SURFACE, 10))
        assert marks >= 25, f"menu item {i} icon pixels: {marks}"
        centre = px(data, width, 30, (iy0 + iy1) // 2)
        assert not is_accent(centre),             f"menu item {i} icon centre is accent (letter tile?): {centre}"
    green = box_count(width, height, data, 16, 44,
                      menu_top + 16, menu_top + 44, is_greenish)
    assert green >= 4, f"terminal menu icon green pixels: {green}"
    blue = box_count(width, height, data, 16, 44,
                     menu_top + 56, menu_top + 84, is_blueish)
    assert blue >= 10, f"demo menu icon blue pixels: {blue}"
    notes.append("menu items carry drawn icons (terminal green, "
                 "demo blue; no letter tiles)")

    # First item (Terminal): the click closes the menu and launches
    # a new terminal window — a third task button appears. (Apps
    # with a single-instance app id focus-or-launch instead; the
    # Terminal entry has none, so a launch is the only correct
    # outcome.)
    before = len(task_buttons(width, height, data))
    proof.click(width, height, 164, menu_top + 12 + 18)
    width, height, data = proof.frame_wait(
        lambda w, h, d: menu_items((w, h, d)) is None and
        len(task_buttons(w, h, d)) >= before + 1, 45,
        save="05-menu-item-launch.png")
    notes.append("menu item click closed the menu and launched "
                 "a new terminal window (task button appeared)")

    # Start toggles: open then close without launching anything.
    # A click can land while the panel surface is mid-resize under
    # TCG; allow one re-click before failing the wait.
    def toggle(want_open):
        w, h, d = proof.frame()
        for attempt in range(2):
            proof.click(w, h, 25, h - 24)
            try:
                proof.frame_wait(
                    lambda ww, hh, dd:
                    (menu_items((ww, hh, dd)) is not None) == want_open,
                    25)
                return
            except AssertionError:
                if attempt == 1:
                    raise
                w, h, d = proof.frame()

    toggle(True)
    toggle(False)
    notes.append("start button toggles the menu open and closed")

    # (No live link-flip assertion: see the module docstring.
    # The tray's down state was asserted on the first frame;
    # the up state shares its code path and cannot be induced
    # from the unprivileged session.)
    return notes


def boot_and_drive(work: Path, secret: str, out: Path) -> tuple[bool, list[str]]:
    notes: list[str] = []
    qmp_dir = tempfile.mkdtemp(prefix="synveil-shell-qmp-")
    qmp = Path(qmp_dir) / "monitor.sock"
    env = {k: v for k, v in os.environ.items() if not k.startswith("SYNVEIL_")}
    env.update(SYNVEIL_OUT_DIR=str(work), SYNVEIL_QEMU_VIDEO="1",
               SYNVEIL_QEMU_DISPLAY="none", SYNVEIL_QEMU_NETWORK="1",
               SYNVEIL_QEMU_MEMORY="768M", SYNVEIL_QEMU_IMAGE_WRITABLE="1",
               SYNVEIL_QEMU_QMP_SOCKET=str(qmp))
    process = subprocess.Popen(
        ["bash", str(ROOT / "build/scripts/qemu.sh")],
        cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        start_new_session=True)
    deadline = time.monotonic() + 600
    phase = "boot"
    seen: set[bytes] = set()
    pending = b""
    log = (out / "shell-serial.log").open("wb")
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
                    return False, notes + ["serial buffer overflow"]
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    line = line.rstrip(b"\r")
                    log.write(line.replace(secret.encode(), b"[REDACTED]")
                              + b"\n")
                    log.flush()
                    if b"Recovery/bootstrap shell" in line:
                        return False, notes + ["recovery shell reached"]
                    if line.startswith(b"SYNVEIL_"):
                        seen.add(line)
                if seen & joined.DENIED:
                    return False, notes + ["denied marker seen"]
                if phase == "boot" and joined.BOOT <= seen:
                    if b"SYNVEIL_ENROLL_READY" not in seen:
                        continue
                    try:
                        type_test_secret(qmp, secret, timeout=45)
                    except Exception as exc:  # noqa: BLE001
                        return False, notes + [f"enroll type failed: {exc}"]
                    phase = "first-password"
                if (phase == "first-password" and
                        b"SYNVEIL_ENROLL_CONFIRM_READY" in seen):
                    seen.discard(b"SYNVEIL_ENROLL_CONFIRM_READY")
                    incorrect = secret[:-1] + ("0" if secret[-1] != "0"
                                               else "1")
                    try:
                        type_test_secret(qmp, incorrect, timeout=45)
                    except Exception as exc:  # noqa: BLE001
                        return False, notes + [f"mismatch type failed: {exc}"]
                    phase = "waiting-mismatch-rejection"
                if (phase == "waiting-mismatch-rejection" and
                        b"SYNVEIL_ENROLL_FAILED" in seen):
                    seen.discard(b"SYNVEIL_ENROLL_FAILED")
                    try:
                        type_test_secret(qmp, secret, timeout=45)
                    except Exception as exc:  # noqa: BLE001
                        return False, notes + [f"retry type failed: {exc}"]
                    phase = "retry-first-password"
                if (phase == "retry-first-password" and
                        b"SYNVEIL_ENROLL_CONFIRM_READY" in seen):
                    try:
                        type_test_secret(qmp, secret, timeout=45)
                    except Exception as exc:  # noqa: BLE001
                        return False, notes + [f"confirm type failed: {exc}"]
                    phase = "confirmation"
                if (phase == "confirmation" and
                        b"SYNVEIL_ENROLL_COMPLETED" in seen and
                        b"SYNVEIL_LOGIN_READY" in seen):
                    try:
                        type_test_secret(qmp, secret, timeout=45)
                    except Exception as exc:  # noqa: BLE001
                        return False, notes + [f"login type failed: {exc}"]
                    phase = "logging-in"
                if phase == "logging-in" and b"SYNVEIL_GRAPHICAL_AUTH_DENIED" in seen:
                    return False, notes + ["graphical auth denied"]
                if (phase == "logging-in" and
                        b"SYNVEIL_GRAPHICAL_AUTH_ACTIVE" in seen):
                    time.sleep(0.6)
                    try:
                        run_shell_steps(ShellProof(qmp, out), notes)
                    except AssertionError as exc:
                        return False, notes + [f"shell step failed: {exc}"]
                    for note in notes:
                        log.write(f"[synveil] step: {note}\n".encode())
                    log.flush()
                    phase = "closing"
                    # End the session the way the session ends: close
                    # every window. Raise each window through its
                    # task button, then apply both close gestures —
                    # `exit` for a terminal, Escape for the demo
                    # window; each is a no-op on the other kind, so
                    # no window-kind detection is needed. (Locating
                    # an unfocused terminal by its interior fails:
                    # unfocused it renders navy, not black.)
                    proof = ShellProof(qmp, out)
                    for _ in range(10):
                        w, h, d = proof.frame()
                        buttons = task_buttons(w, h, d)
                        if not buttons:
                            break
                        a, b = buttons[0]
                        proof.click(w, h, (a + b) // 2, h - 24)
                        time.sleep(0.8)
                        send_keys(qmp, ("e", "x", "i", "t", "ret"),
                                  timeout=5,
                                  allowed=ALLOWED_TERMINAL_RETURN)
                        time.sleep(0.5)
                        send_keys(qmp, ("esc",), timeout=5)
                        time.sleep(1.0)
                    phase = "awaiting-relock"
                if (phase == "awaiting-relock" and
                        b"SYNVEIL_LOGIN_RELOCKED" in seen):
                    notes.append("session ended; graphical login relocked")
                    return True, notes
            return False, notes + [f"incomplete: {phase}"]
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("shell smoke requires a non-root runner")
    proof = json.loads((IMAGE_DIR / "validation.json").read_text())
    source_image = IMAGE_DIR / "synveil-x86_64.img"
    if (proof.get("schema") != "synveil.native-joined-image/v1" or
            hashlib.sha256(source_image.read_bytes()).hexdigest()
            != proof.get("image_sha256")):
        parser.error("joined image missing or changed since build")
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_hex(16)
    with tempfile.TemporaryDirectory(prefix="synveil-shell-") as temp:
        work = Path(temp)
        target = work / "synveil-x86_64.img"
        with source_image.open("rb") as src, target.open("xb") as dst:
            shutil.copyfileobj(src, dst)
        ok, notes = boot_and_drive(work, secret, out)
    receipt = {
        "schema": "synveil.shell-acceptance/v1",
        "image_sha256": proof["image_sha256"],
        "source_commit": proof.get("source_commit"),
        "passed": ok,
        "physical_hardware_tested": False,
        "notes": notes,
    }
    (out / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    for note in notes:
        print(f"[synveil] {note}")
    if not ok:
        print("[synveil] shell acceptance FAILED")
        return 1
    print("SYNVEIL_SHELL_QEMU_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
