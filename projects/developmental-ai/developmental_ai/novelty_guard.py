"""Simulation-only, read-only out-of-bank sensor-surprise guard.

A whole-trajectory train-namespace reference distribution calibrates a maximum
prefix surprise statistic; the guard never learns/installs models or issues acts.
Expected false-alarm rates are empirical for the calibration sensor process,
NOT a confidence or deployment-safety guarantee under distribution shift.
"""
from __future__ import annotations

import copy
import math
import json
import sqlite3
from pathlib import Path

from developmental_ai.adaptive_dynamics import canonical
from developmental_ai.switching_belief import (
    SwitchingBelief, _bank, _calibration_stream, _digest, MAX_STEPS,
)

SCHEMA = "novelty-guard/v1"
MIN_STEPS = 4
MAX_REFERENCE = 300


def _bounded_stream(record):
    _calibration_stream(record)
    if len(record["observations"]) > 55:
        raise ValueError("guard limits to a 55-step navigation episode")


def _profile(models, record, hazard):
    """One full ordinary-sensor stream; no hidden positions or regime labels."""
    _bounded_stream(record)
    nav = SwitchingBelief(record["initial"], record["goal"], record["n"], models, hazard=hazard)
    maximum = 0.0
    for action, observed in record["observations"]:
        nav.advance(action, observed)
        if nav.steps >= MIN_STEPS:
            maximum = max(maximum, -nav.log_evidence / nav.steps)
    if len(record["observations"]) < MIN_STEPS:
        raise ValueError("four observations required for calibration")
    return maximum


def calibrate_guard(models, streams, *, hazard=0.0, alpha=.10):
    """Train-only upper-tail quantile of MAX prefix mean surprise per episode.

    k = ceil((n+1)*(1-alpha)) is a conservative split-reference rank under
    exchangeability. If k exceeds n, calibration fails rather than claiming a
    finite threshold. Action policies and regimes must match deployment for
    any empirical false-alarm interpretation.
    """
    fingerprint = _bank(models)
    if (type(streams) not in (tuple, list) or not 20 <= len(streams) <= MAX_REFERENCE or
            type(alpha) not in (float, int) or not math.isfinite(alpha) or not .02 <= alpha <= .25 or
            type(hazard) not in (float, int) or not math.isfinite(hazard) or not 0 <= hazard <= .3):
        raise ValueError("invalid novelty calibration setup")
    # This constructor also binds the hazard and validates model types.
    scores, hashes = [], []
    for stream in streams:
        hashes.append(_digest(stream))
        scores.append(_profile(models, stream, hazard))
    if len(set(hashes)) != len(hashes):
        raise ValueError("duplicate calibration histories")
    rank = math.ceil((len(scores) + 1) * (1-alpha))
    if rank > len(scores):
        raise ValueError("insufficient calibration examples for tail cutoff")
    threshold = sorted(scores)[rank-1]
    state = {"schema": SCHEMA, "bank": fingerprint, "hazard": float(hazard),
             "alpha": float(alpha), "n_reference": len(scores), "min_steps": MIN_STEPS,
             "threshold": threshold, "calibration_digest": _digest(sorted(hashes))}
    return {"state": state, "sha256": _digest(state)}


def verify_guard(receipt, models):
    if (type(receipt) is not dict or set(receipt) != {"state", "sha256"} or
            type(receipt["state"]) is not dict or type(receipt["sha256"]) is not str or
            receipt["sha256"] != _digest(receipt["state"])):
        raise ValueError("invalid guard receipt checksum")
    s = receipt["state"]
    if (set(s) != {"schema", "bank", "hazard", "alpha", "n_reference", "min_steps",
                   "threshold", "calibration_digest"} or s["schema"] != SCHEMA or
            s["bank"] != _bank(models) or s["min_steps"] != MIN_STEPS or
            type(s["n_reference"]) is not int or not 20 <= s["n_reference"] <= MAX_REFERENCE or
            type(s["alpha"]) not in (float, int) or not math.isfinite(s["alpha"]) or
            not .02 <= s["alpha"] <= .25 or math.ceil((s["n_reference"]+1)*(1-s["alpha"])) > s["n_reference"] or
            type(s["hazard"]) not in (float, int) or not math.isfinite(s["hazard"]) or not 0 <= s["hazard"] <= .3 or
            type(s["threshold"]) not in (float, int) or not math.isfinite(s["threshold"]) or s["threshold"] < 0 or
            type(s["calibration_digest"]) is not str or len(s["calibration_digest"]) != 64 or
            any(c not in "0123456789abcdef" for c in s["calibration_digest"])):
        raise ValueError("incompatible or malformed guard calibration")
    return s


class NoveltyGuard:
    """Read-only surprise monitor; alert latches until a new bounded session."""
    def __init__(self, initial, goal, n, models, receipt):
        s = verify_guard(receipt, models)
        self.models = copy.deepcopy(models)
        self.receipt = copy.deepcopy(receipt)
        self.nav = SwitchingBelief(initial, goal, n, self.models, hazard=s["hazard"])
        self.alarm = False
        self.max_surprise = 0.0
        self.log = []

    def advance(self, action, observation):
        if _bank(self.models) != self.nav.fingerprints or len(self.log) >= 55:
            raise ValueError("invalid or exhausted guard bank")
        surprise = self.nav.advance(action, observation)
        self.log.append([action, dict(observation)])
        if self.nav.steps >= MIN_STEPS:
            self.max_surprise = max(self.max_surprise, -self.nav.log_evidence/self.nav.steps)
            self.alarm = self.alarm or self.max_surprise > self.receipt["state"]["threshold"]
        return {"status": "unknown" if self.alarm else "observing" if self.nav.steps < MIN_STEPS else "within_reference",
                "alarm": self.alarm, "max_prefix_surprise": self.max_surprise,
                "threshold": self.receipt["state"]["threshold"], "steps": self.nav.steps}

    def snapshot(self):
        state = {"schema": SCHEMA, "receipt_digest": _digest(self.receipt), "navigator": self.nav.snapshot(),
                 "log": self.log, "alarm": self.alarm, "max_surprise": self.max_surprise}
        return {"state": state, "sha256": _digest(state)}

    @classmethod
    def restore(cls, record, models, receipt):
        if (type(record) is not dict or set(record) != {"state", "sha256"} or
                type(record["state"]) is not dict or _digest(record["state"]) != record["sha256"]):
            raise ValueError("invalid novelty checkpoint")
        s = record["state"]
        if (set(s) != {"schema", "receipt_digest", "navigator", "log", "alarm", "max_surprise"} or
                s["schema"] != SCHEMA or s["receipt_digest"] != _digest(receipt) or
                type(s["log"]) is not list or len(s["log"]) > 55 or
                type(s["alarm"]) is not bool or type(s["max_surprise"]) not in (int,float) or
                not math.isfinite(s["max_surprise"]) or s["max_surprise"] < 0 or
                type(s["navigator"]) is not dict or type(s["navigator"].get("state")) is not dict):
            raise ValueError("invalid novelty checkpoint state")
        b = s["navigator"]["state"]
        try:
            guard = cls(b["initial"], b["goal"], b["n"], models, receipt)
            for event in s["log"]:
                if type(event) is not list or len(event) != 2:
                    raise ValueError("invalid novelty event")
                guard.advance(event[0], event[1])
        except (KeyError, TypeError, IndexError) as exc:
            raise ValueError("invalid novelty replay") from exc
        if (guard.alarm != s["alarm"] or guard.max_surprise != s["max_surprise"] or
                canonical(guard.nav.snapshot()) != canonical(s["navigator"])):
            raise ValueError("novelty history replay failed")
        return guard


class GuardedNavigation:
    """Optional bounded, fail-closed adapter for the existing simulation loop.

    An unfamiliar reading PAUSES further action suggestions; the wrapper never
    emits a replacement action or authorizes real-world controls. It is not the
    default and is not an authenticated owner policy.
    """
    def __init__(self, proposal, hazard_receipt, guard_receipt, initial, goal, n):
        from developmental_ai.closed_loop_adaptation import NavigationSession, models_from_proposal
        self.session = NavigationSession(proposal, initial, goal, n, hazard_receipt, mode="switching")
        self.guard = NoveltyGuard(initial, goal, n, models_from_proposal(proposal), guard_receipt)
        if (self.session.nav.fingerprints != self.guard.nav.fingerprints or
                self.session.nav.hazard != self.guard.nav.hazard):
            raise ValueError("incompatible model or hazard receipts")

    def select_action(self):
        if self.guard.alarm:
            return None  # explicit operator-visible pause, not a new act
        return self.session.select_action()

    def advance(self, action, observation, *, done=False):
        if self.guard.alarm:
            raise ValueError("session paused: no more actions may be requested")
        outcome=self.session.advance(action,observation,done=done)
        warning=self.guard.advance(action,observation)
        return {**outcome,"trust":warning}

    def snapshot(self):
        state={"schema":"guarded-navigation/v1", "session":self.session.snapshot(),
               "guard":self.guard.snapshot()}
        return {"state":state,"sha256":_digest(state)}

    @classmethod
    def restore(cls, record, proposal, hazard_receipt, guard_receipt):
        from developmental_ai.closed_loop_adaptation import NavigationSession
        if (type(record) is not dict or set(record) != {"state","sha256"} or
                type(record["state"]) is not dict or _digest(record["state"]) != record["sha256"]):
            raise ValueError("invalid combined checkpoint")
        state=record["state"]
        if set(state) != {"schema","session","guard"} or state["schema"] != "guarded-navigation/v1":
            raise ValueError("invalid guarded schema")
        session=NavigationSession.restore(state["session"],proposal,hazard_receipt)
        nav=session.nav
        obj=cls(proposal,hazard_receipt,guard_receipt,nav.initial,nav.goal,nav.n)
        obj.guard=NoveltyGuard.restore(state["guard"],obj.guard.models,guard_receipt)
        if (obj.guard.nav.fingerprints != nav.fingerprints or
                obj.guard.nav.hazard != nav.hazard or
                (obj.guard.nav.initial,obj.guard.nav.goal,obj.guard.nav.n) != (nav.initial,nav.goal,nav.n) or
                len(obj.guard.log) != len(session.log) or
                any((a != step["action"] or ob != step["observation"])
                    for (a,ob),step in zip(obj.guard.log,session.log))):
            raise ValueError("guard/session evidence or model mismatch")
        obj.session=session
        return obj


class GuardedCheckpoint:
    """Atomic SQLite storage for both frozen navigation and guard histories."""
    def __init__(self, path):
        path=Path(path)
        path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS guarded_state (id INTEGER PRIMARY KEY CHECK(id=1), record TEXT NOT NULL)")

    def save(self, session):
        if not isinstance(session,GuardedNavigation):
            raise ValueError("not a guarded navigation session")
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO guarded_state(id,record) VALUES (1,?)",
                            (canonical(session.snapshot()),))

    def load(self, proposal, hazard_receipt, guard_receipt):
        row=self.db.execute("SELECT record FROM guarded_state WHERE id=1").fetchone()
        if row is None:return None
        try:
            return GuardedNavigation.restore(json.loads(row[0]),proposal,hazard_receipt,guard_receipt)
        except (TypeError,KeyError,json.JSONDecodeError) as exc:
            raise ValueError("invalid guarded checkpoint record") from exc

    def close(self):self.db.close()
    def __enter__(self):return self
    def __exit__(self,*_):self.close()
