#!/usr/bin/env python3
"""Display-state resolution for the muse-pc-bridge GUI supervisor.

Pure logic, no I/O and no tkinter: given the supervisor's status-file
contents, the agent's /v1/status body (or None when unreachable), and
bridge_update.update_status() output, decide what the floating avatar
window should show. Every input is a real signal published by the
supervisor or the agent — the display never invents activity.

States (art key -> meaning):
  idle      agent reachable, nothing running
  working   a job or tracked process is running
  session   an interactive session is open
  connecting  transitional: supervisor starting/restarting, an update
            applying, or the agent briefly unreachable
  celebrate an update applied cleanly, shown briefly
  alert     something needs the owner's eye: apply/rollback failure,
            a completed rollback, or the agent down too long
"""

from __future__ import annotations

import time

CELEBRATE_WINDOW_S = 25.0
ROLLBACK_NOTICE_S = 30.0
DOWN_ALERT_S = 20.0

_ALERT_SUPERVISOR_STATES = {"update_apply_failed",
                            "update_unhealthy_rolling_back"}
_TRANSITION_SUPERVISOR_STATES = {"starting", "restarting",
                                 "update_applied"}


def _result_age_s(result: dict | None, now: float) -> float | None:
    if not result:
        return None
    at = result.get("at")
    if not isinstance(at, (int, float)):
        return None
    return now - float(at)


def resolve_display(supervisor: dict | None,
                    agent: dict | None,
                    update: dict | None, *,
                    now: float | None = None,
                    down_since: float | None = None) -> dict:
    """Return {"state", "art", "label"} for the avatar window."""
    now = time.time() if now is None else now
    sup_state = (supervisor or {}).get("state")
    update = update or {}
    staged = update.get("staged")
    result = update.get("last_result") or {}
    outcome = result.get("outcome")
    age = _result_age_s(result, now)

    # -- alert: failures first, they outrank everything else ---------------
    if sup_state in _ALERT_SUPERVISOR_STATES:
        return {"state": "alert", "art": "alert",
                "label": "Needs attention"}
    if outcome in ("apply_failed", "rollback_failed"):
        return {"state": "alert", "art": "alert",
                "label": "Update failed"}
    if "rolled_back_version" in result and age is not None \
            and age <= ROLLBACK_NOTICE_S:
        return {"state": "alert", "art": "alert",
                "label": "Update rolled back"}

    # -- agent unreachable: transition or trouble ---------------------------
    if agent is None:
        if sup_state in _TRANSITION_SUPERVISOR_STATES or staged:
            return {"state": "connecting", "art": "connecting",
                    "label": "Restarting…"}
        if down_since is not None and now - down_since > DOWN_ALERT_S:
            return {"state": "alert", "art": "alert",
                    "label": "Agent not responding"}
        return {"state": "connecting", "art": "connecting",
                "label": "Connecting…"}

    # -- celebrate a clean apply, briefly ------------------------------------
    if outcome == "applied_ok" and age is not None and age <= CELEBRATE_WINDOW_S:
        return {"state": "celebrate", "art": "celebrate",
                "label": "Update applied"}

    # -- an update is waiting for its restart boundary -----------------------
    if staged:
        return {"state": "connecting", "art": "connecting",
                "label": "Update staged"}

    # -- live activity --------------------------------------------------------
    if int(agent.get("sessions_open") or 0) > 0:
        return {"state": "session", "art": "session",
                "label": "Session open"}
    if int(agent.get("jobs_running") or 0) > 0 \
            or int(agent.get("processes_alive") or 0) > 0:
        return {"state": "working", "art": "working",
                "label": "Working"}
    return {"state": "idle", "art": "idle", "label": "Idle"}
