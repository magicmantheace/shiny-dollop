#!/usr/bin/env python3
"""muse-pc-bridge GUI supervisor — avatar display form of the agent.

Same Supervisor core as supervisor.py (restart, staged self-update
apply with health check and automatic rollback, supervisor-status.json
state file). What changes is only the shell: instead of a console
window, a small floating window shows Muse's avatar, animated
according to what the bridge is actually doing (display_state.py maps
real supervisor/agent signals to the animation — nothing is faked).

Kill-switch semantics are preserved exactly: the floating window IS
the visible indicator, and stopping it (the x control or the
right-click menu) stops the supervisor AND the agent. There is no
hidden background mode.

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


def _agent_dir() -> Path:
    return Path(__file__).resolve().parent


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
    """Cycles the frames of one animated GIF on a Tk label."""

    def __init__(self, label, path: Path):
        self.label = label
        self.frames = []
        self.index = 0
        self._after_id = None
        if path.exists():
            import tkinter as tk
            i = 0
            while True:
                try:
                    self.frames.append(
                        tk.PhotoImage(file=str(path),
                                      format=f"gif -index {i}"))
                    i += 1
                except tk.TclError:
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
    def __init__(self, supervisor: Supervisor, config_path: Path,
                 state_dir: Path):
        import tkinter as tk
        self.tk = tk
        self.supervisor = supervisor
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
        root.configure(bg=BG)

        self.avatar_label = tk.Label(root, bg=BG, bd=0)
        self.avatar_label.pack(side="top")
        self.text_label = tk.Label(root, bg=BG, fg=FG, bd=0,
                                   font=("Segoe UI", 9),
                                   text="Muse PC Bridge — starting")
        self.text_label.pack(side="top", fill="x", pady=(2, 4))
        self.close_label = tk.Label(root, text="✕", bg=BG, fg=FG, bd=0,
                                    font=("Segoe UI", 10, "bold"))
        self.close_label.place(relx=1.0, x=-4, y=2, anchor="ne")
        self.close_label.bind("<Button-1>", lambda _e: self.stop())

        self.menu = tk.Menu(root, tearoff=0)
        self.menu.add_command(label="Stop bridge", command=self.stop)

        for widget in (root, self.avatar_label, self.text_label):
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)
            widget.bind("<Button-3>", self._popup_menu)
        root.protocol("WM_DELETE_WINDOW", self.stop)

        root.update_idletasks()
        w = root.winfo_reqwidth()
        h = root.winfo_reqheight()
        x = root.winfo_screenwidth() - w - 24
        y = root.winfo_screenheight() - h - 48
        root.geometry(f"+{max(x, 0)}+{max(y, 0)}")

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
        """The kill switch: stop supervisor + agent, close the window."""
        if self._stopped:
            return
        self._stopped = True
        try:
            self.supervisor.stop()
        finally:
            self.root.destroy()

    # -- state polling ---------------------------------------------------------

    def _agent_status(self) -> dict | None:
        try:
            cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
            host = str(cfg.get("host", "127.0.0.1"))
            port = int(cfg.get("port", 8765))
            token = str(cfg.get("token", ""))
        except (OSError, json.JSONDecodeError):
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

    def _apply(self, view: dict) -> None:
        art = view["art"]
        if view["state"] != self._current_state:
            self._current_state = view["state"]
            self._state_since = time.time()
            # Publish the display state for other local apps (e.g. a
            # desktop pet) to observe. Read-only, no token material,
            # written beside the supervisor's own status file.
            try:
                bridge_update._write_json(
                    self.state_dir / "display-state.json",
                    {"state": view["state"], "art": art,
                     "label": view["label"],
                     "since": self._state_since,
                     "updated_at": time.time()})
            except OSError:
                pass
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
            else:  # asset missing: stay honest and legible, never crash
                self.avatar_label.configure(image="", text="◐")
            self._current_art = art
        ver = ""
        self.text_label.configure(text=f"Muse — {view['label']}{ver}")
        if view["state"] == "alert":
            self._alert_flash = not self._alert_flash
            bg = BG_ALERT if self._alert_flash else BG
        else:
            bg = BG
        self.root.configure(bg=bg)
        self.avatar_label.configure(bg=bg)
        self.text_label.configure(bg=bg)
        self.close_label.configure(bg=bg)

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
    supervisor = Supervisor(args.install_root, args.config, state_dir)
    thread = threading.Thread(target=supervisor.run, daemon=True,
                              name="bridge-supervisor")
    thread.start()
    window = AvatarWindow(supervisor, args.config, state_dir)
    window.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
