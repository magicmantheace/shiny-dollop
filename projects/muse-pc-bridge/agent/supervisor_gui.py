#!/usr/bin/env python3
"""muse-pc-bridge GUI supervisor — avatar display form of the agent.

Same Supervisor core as supervisor.py (restart, staged self-update
apply with health check and automatic rollback, supervisor-status.json
state file). What changes is only the shell: instead of a console
window, a small floating window shows Muse's avatar, animated
according to what the bridge is actually doing (display_state.py maps
real supervisor/agent signals to the animation — nothing is faked).

The avatar GIFs have their backdrop keyed out, and on Windows the
window itself is colour-key transparent: only the character (and the
small status line) is visible against the desktop, and clicks pass
through the transparent parts. Platforms without colour-key support
fall back to the plain dark window.

Kill-switch semantics for the form this process owns: the floating
window IS the visible indicator, and stopping it (the x control or
the right-click menu) stops the supervisor AND the agent.

Attach mode (v1.1): if a bridge core is already running — the
headless boot form (supervisor.py --headless under the boot task) or
any other healthy agent — this window ATTACHES display-only: it
shows the same resolved state but owns no supervisor, and closing it
leaves the bridge running (the menu says so: "Close avatar (bridge
keeps running)"). The core's kill switches are its own (task
controls / scripts/bridge-core.ps1 -Action stop). If something that
is NOT a muse-pc-bridge agent answers on the configured port, the
window refuses to start rather than fight over it.

Usage:
  pythonw supervisor_gui.py [--config C:\\path\\config.json]
                            [--install-root C:\\path\\projects\\muse-pc-bridge]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bridge_update  # noqa: E402
import display_state  # noqa: E402
from supervisor import Supervisor  # noqa: E402

POLL_MS = 600
FRAME_MS = 100
ASSET_DIR = Path(__file__).resolve().parent / "assets" / "avatar"
BG = "#202020"
BG_ALERT = "#5a1216"
FG = "#f2f2f2"
# Colour-key for window transparency: the avatar art contains no
# magenta, so keying this colour out leaves only the character.
KEY = "#ff00ff"


def _agent_dir() -> Path:
    return Path(__file__).resolve().parent


# Supervisor states that mean a core may be mid-start/restart: worth
# a short wait for the agent to answer before falling back to
# starting a supervisor of our own (the logon/boot race).
_CORE_TRANSIENT_STATES = {"starting", "restarting", "update_applied",
                          "update_healthy", "running_after_rollback"}


def fetch_agent_status(config_path: Path) -> dict | None:
    """The agent's /v1/status body, or None when unreachable."""
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        host = str(cfg.get("host", "127.0.0.1"))
        port = int(cfg.get("port", 8765))
        token = str(cfg.get("token", ""))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    req = urllib.request.Request(
        f"http://{host}:{port}/v1/status",
        headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return None
    return None


def is_bridge_agent(status: dict | None) -> bool:
    return bool(status) and status.get("agent") == "muse-pc-bridge"


def choose_gui_mode(config_path: Path, state_dir: Path, *,
                    fetch=fetch_agent_status, attempts: int = 20,
                    interval_s: float = 0.5,
                    sleep=time.sleep) -> tuple[str, dict | None]:
    """Decide how this window should run.

    Returns ("attach", status) when a muse-pc-bridge agent already
    answers, ("foreign", status) when something else answers on the
    port, or ("own", None) when nothing answers and no core looks
    mid-start — the historical behaviour of running our own
    supervisor. While a core reports a transient supervisor state
    (starting/restarting/updating), the probe retries briefly: at
    logon the boot core may simply not be up yet.
    """
    status = fetch(config_path)
    if status is not None:
        return ("attach", status) if is_bridge_agent(status) \
            else ("foreign", status)
    sup = bridge_update._read_json(
        state_dir / "supervisor-status.json") or {}
    if sup.get("state") in _CORE_TRANSIENT_STATES:
        for _ in range(attempts):
            sleep(interval_s)
            status = fetch(config_path)
            if status is not None:
                return ("attach", status) if is_bridge_agent(status) \
                    else ("foreign", status)
    return ("own", None)


def _enable_dpi_awareness() -> None:
    """Windows: keep the window true-size on scaled displays (250%)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass  # cosmetic only; never block startup on it


def _quiet_stdio(state_dir: Path) -> None:
    """Under pythonw there is no console; give the supervisor's prints
    a home (a log beside the state files) instead of a None stream."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        log = open(state_dir / "supervisor-gui.log", "a",
                   encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = log
        if sys.stderr is None:
            sys.stderr = log
    except OSError:
        if sys.stdout is None:
            sys.stdout = io.StringIO()
        if sys.stderr is None:
            sys.stderr = io.StringIO()


class GifPlayer:
    """Cycles the frames of one animated GIF on a Tk label.

    Loading is lazy and chunked: Tk re-scans a GIF from the top for
    every -index frame, so loading 80 frames synchronously would
    freeze the window for many seconds. Frame 0 loads immediately;
    the rest stream in via load_more() driven by the window's pump,
    and playback cycles whatever frames have arrived.
    """

    LOAD_CHUNK = 6

    def __init__(self, label, path: Path):
        self.label = label
        self.frames = []
        self.index = 0
        self.complete = False
        self._after_id = None
        self._path = path
        self._next = 0
        if path.exists():
            self.load_more()

    def load_more(self) -> None:
        if self.complete or not self._path.exists():
            self.complete = True
            return
        import tkinter as tk
        loaded = 0
        while loaded < self.LOAD_CHUNK:
            try:
                self.frames.append(
                    tk.PhotoImage(file=str(self._path),
                                  format=f"gif -index {self._next}"))
                self._next += 1
                loaded += 1
            except tk.TclError:
                self.complete = True
                break

    @property
    def ok(self) -> bool:
        return bool(self.frames)

    def start(self) -> None:
        if self.frames:
            self._tick()

    def stop(self) -> None:
        if self._after_id is not None:
            try:
                self.label.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _tick(self) -> None:
        self.label.configure(image=self.frames[self.index])
        self.index = (self.index + 1) % len(self.frames)
        self._after_id = self.label.after(FRAME_MS, self._tick)


class AvatarWindow:
    def __init__(self, supervisor: Supervisor | None, config_path: Path,
                 state_dir: Path):
        import tkinter as tk
        self.tk = tk
        # supervisor is None in attach mode: a core elsewhere owns
        # the agent and this window is display-only.
        self.supervisor = supervisor
        self._attached = supervisor is None
        self.config_path = config_path
        self.state_dir = state_dir
        self._down_since: float | None = None
        self._players: dict[str, GifPlayer] = {}
        self._current_art: str | None = None
        self._current_state: str | None = None
        self._state_since: float = time.time()
        self._alert_flash = False
        self._stopped = False

        _enable_dpi_awareness()
        root = tk.Tk()
        self.root = root
        root.title("Muse PC Bridge")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        self._transparent = False
        try:
            root.wm_attributes("-transparentcolor", KEY)
            self._transparent = True
        except tk.TclError:
            pass  # no colour-key support: plain dark window fallback
        root.configure(bg=KEY if self._transparent else BG)

        self.avatar_label = tk.Label(
            root, bg=KEY if self._transparent else BG, bd=0)
        self.avatar_label.pack(side="top")
        self.text_label = tk.Label(
            root, bg=KEY if self._transparent else BG, fg=FG, bd=0,
            font=("Segoe UI", 9),
            text="Muse PC Bridge — starting")
        self.text_label.pack(side="top", fill="x", pady=(2, 4))
        self.close_label = tk.Label(
            root, text="✕",
            bg=KEY if self._transparent else BG, fg=FG, bd=0,
            font=("Segoe UI", 10, "bold"))
        self.close_label.place(relx=1.0, x=-4, y=2, anchor="ne")
        self.close_label.bind("<Button-1>", lambda _e: self.stop())

        self.menu = tk.Menu(root, tearoff=0)
        if self._attached:
            self.menu.add_command(
                label="Close avatar (bridge keeps running)",
                command=self.stop)
        else:
            self.menu.add_command(label="Stop bridge", command=self.stop)

        for widget in (root, self.avatar_label, self.text_label):
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)
            widget.bind("<Button-3>", self._popup_menu)
        root.protocol("WM_DELETE_WINDOW", self.stop)

        # Stay hidden until the first animation is applied: the
        # window's real size is only known once an image is in the
        # label, and placing it before that pushes it off-screen.
        self._placed = False
        root.withdraw()

    # -- window behaviour ----------------------------------------------------

    def _drag_start(self, event) -> None:
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()

    def _drag_move(self, event) -> None:
        self.root.geometry(
            f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def _popup_menu(self, event) -> None:
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def stop(self) -> None:
        """Own form: the kill switch — stop supervisor + agent, close
        the window. Attach mode: close the window only; the core
        keeps running (the menu label says exactly that)."""
        if self._stopped:
            return
        self._stopped = True
        try:
            if self.supervisor is not None:
                self.supervisor.stop()
        finally:
            self.root.destroy()

    # -- state polling ---------------------------------------------------------

    def _agent_status(self) -> dict | None:
        return fetch_agent_status(self.config_path)

    def _poll(self) -> None:
        if self._stopped:
            return
        sup_status = bridge_update._read_json(
            self.state_dir / "supervisor-status.json")
        agent = self._agent_status()
        if agent is None:
            if self._down_since is None:
                self._down_since = time.time()
        else:
            self._down_since = None
        update = bridge_update.update_status(self.state_dir)
        view = display_state.resolve_display(
            sup_status, agent, update, down_since=self._down_since)
        self._apply(view)
        self.root.after(POLL_MS, self._poll)

    def _pump_loads(self) -> None:
        """Stream in the current animation's remaining frames."""
        if self._stopped:
            return
        player = self._players.get(self._current_art or "")
        if player is not None and not player.complete:
            player.load_more()
            self.root.after(25, self._pump_loads)

    def _apply(self, view: dict) -> None:
        art = view["art"]
        if view["state"] != self._current_state:
            self._current_state = view["state"]
            self._state_since = time.time()
            # display-state.json (read by local apps such as a
            # desktop pet) is published by the supervisor core since
            # v1.1, in every form — this window only displays. That
            # keeps the file fresh when no window is open (boot core)
            # and identical when one is (either GUI form).
        if art != self._current_art:
            if self._current_art in self._players:
                self._players[self._current_art].stop()
            player = self._players.get(art)
            if player is None:
                player = GifPlayer(self.avatar_label,
                                   ASSET_DIR / f"{art}.gif")
                self._players[art] = player
            if player.ok:
                self.avatar_label.configure(image=player.frames[0],
                                            text="")
                player.start()
                self.root.after(25, self._pump_loads)
            else:  # asset missing: stay honest and legible, never crash
                self.avatar_label.configure(image="", text="◐")
            self._current_art = art
        ver = ""
        self.text_label.configure(text=f"Muse — {view['label']}{ver}")
        if view["state"] == "alert":
            self._alert_flash = not self._alert_flash
        else:
            self._alert_flash = False
        if self._transparent:
            # Only the status strip flashes now: flashing the window
            # background would defeat the colour-key transparency.
            self.text_label.configure(
                bg=BG_ALERT if self._alert_flash else KEY)
        else:
            bg = BG_ALERT if self._alert_flash else BG
            self.root.configure(bg=bg)
            self.avatar_label.configure(bg=bg)
            self.text_label.configure(bg=bg)
            self.close_label.configure(bg=bg)
        if not self._placed:
            self._placed = True
            self.root.update_idletasks()
            w = self.root.winfo_reqwidth()
            h = self.root.winfo_reqheight()
            x = self.root.winfo_screenwidth() - w - 24
            y = self.root.winfo_screenheight() - h - 48
            self.root.geometry(f"+{max(x, 0)}+{max(y, 0)}")
            self.root.deiconify()

    def run(self) -> None:
        self.root.after(300, self._poll)
        self.root.mainloop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="muse-pc-bridge GUI supervisor")
    parser.add_argument("--config", type=Path,
                        default=_agent_dir() / "config.json")
    parser.add_argument("--install-root", type=Path,
                        default=_agent_dir().parent)
    args = parser.parse_args(argv)

    if not args.config.exists():
        print(f"[supervisor-gui] No agent config at {args.config}. "
              f"Run bridge_agent.py --init first.", file=sys.stderr)
        return 1
    try:
        cfg = json.loads(args.config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[supervisor-gui] Could not read agent config: {exc}",
              file=sys.stderr)
        return 1
    state_value = str(cfg.get("state_dir", "./state"))
    state_dir = Path(state_value)
    if not state_dir.is_absolute():
        state_dir = (args.config.resolve().parent / state_dir).resolve()

    _quiet_stdio(state_dir)
    mode, found = choose_gui_mode(args.config, state_dir)
    if mode == "foreign":
        print(f"[supervisor-gui] Something that is not a muse-pc-bridge "
              f"agent is answering on the configured address "
              f"({found.get('agent')!r}); refusing to start. Free the "
              f"port or fix the config.", file=sys.stderr)
        return 2
    if mode == "attach":
        # A core (boot form or another supervisor) already owns the
        # agent: display-only. Closing the window leaves it running.
        print("[supervisor-gui] Attaching to the running bridge core; "
              "this window is display-only.", flush=True)
        window = AvatarWindow(None, args.config, state_dir)
        window.run()
        return 0
    supervisor = Supervisor(args.install_root, args.config, state_dir)
    thread = threading.Thread(target=supervisor.run, daemon=True,
                              name="bridge-supervisor")
    thread.start()
    window = AvatarWindow(supervisor, args.config, state_dir)
    window.run()
    # The window is gone; give the supervisor thread a few seconds to
    # record its final "stopped" state before the process exits, so
    # the status file never claims a dead bridge is still running.
    thread.join(timeout=6.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
