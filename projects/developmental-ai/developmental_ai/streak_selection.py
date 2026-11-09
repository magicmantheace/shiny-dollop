"""Experimental consecutive-evidence selector for bounded simulation events.

This is an *optional* research alternative to the conservative decision gate.
Its empirical calibration error is not a confidence bound. The default
StepDetector and decision_abstention rules are unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math

from developmental_ai.adaptive_dynamics import canonical
from developmental_ai.decision_abstention import signal
from developmental_ai.step_dynamics import catalogue

SCHEMA = "streak-selection/v1"


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _initial():
    return {"episode": 0, "step": 0, "seq": 0, "lead": None, "streak": 0}


def _advance(state, event, names):
    """Reject dropped, reordered or repeated step records before updating."""
    if type(event) is not dict or any(type(event.get(k)) is not int for k in ("episode", "step", "seq")):
        raise ValueError("missing or malformed detector sequence")
    episode, step, seq = event["episode"], event["step"], event["seq"]
    if episode < 1 or not 1 <= step <= 40 or seq <= state["seq"]:
        raise ValueError("repeated or invalid step")
    if step == 1:
        if episode != state["episode"] + 1:
            raise ValueError("episode skipped or reordered")
    elif episode != state["episode"] or step != state["step"] + 1:
        raise ValueError("missing step or episode boundary")
    s = signal(event, names)
    streak = state["streak"] + 1 if step != 1 and s["lead"] == state["lead"] else 1
    state.update({"episode": episode, "step": step, "seq": seq,
                  "lead": s["lead"], "streak": streak})
    return s


@dataclass(frozen=True)
class StreakProfile:
    schema: str
    seed: int
    bank_digest: str
    min_streak: int
    max_empirical_error: float
    threshold: float
    calibration_steps: int
    eligible_steps: int
    accepted_steps: int
    wrong_steps: int
    evidence_digest: str
    digest: str

    def as_dict(self):
        return {key: getattr(self, key) for key in self.__dataclass_fields__}


def train_profile(bank, labeled_events, *, min_streak=3, max_empirical_error=.02,
                  min_accepted=24):
    """Select a frozen threshold using *offline labeled calibration only*."""
    models, fingerprint = catalogue(bank)
    if (type(min_streak) is not int or not 2 <= min_streak <= 12 or
        type(max_empirical_error) not in (int, float) or not math.isfinite(max_empirical_error)
        or not 0 <= max_empirical_error < 1 or
        type(min_accepted) is not int or not 1 <= min_accepted <= 100000):
        raise ValueError("invalid training configuration")
    if type(labeled_events) not in (list, tuple) or not 100 <= len(labeled_events) <= 100000:
        raise ValueError("invalid calibration size")
    state = _initial()
    eligible = []
    for pair in labeled_events:
        if (type(pair) not in (tuple, list) or len(pair) != 2 or
            pair[1] not in models):
            raise ValueError("invalid calibration record")
        event, truth = pair
        s = _advance(state, event, models)
        if state["streak"] >= min_streak and s["status"] not in ("warming", "unknown"):
            eligible.append((s["gap"], s["lead"] != truth))
    eligible.sort(key=lambda v: v[0], reverse=True)
    best = None
    accepted = wrong = i = 0
    while i < len(eligible):
        gap = eligible[i][0]
        while i < len(eligible) and eligible[i][0] == gap:
            wrong += int(eligible[i][1])
            accepted += 1
            i += 1
        if accepted >= min_accepted and wrong / accepted <= max_empirical_error:
            if best is None or accepted > best[0]:
                best = (accepted, wrong, gap)
    if best is None:
        n, w, threshold = 0, 0, 1e6  # explicit no-decision fallback
    else:
        n, w, threshold = best
    fields = {"schema": SCHEMA, "seed": bank.seed, "bank_digest": fingerprint,
              "min_streak": min_streak, "max_empirical_error": float(max_empirical_error),
              "threshold": float(threshold), "calibration_steps": len(labeled_events),
              "eligible_steps": len(eligible), "accepted_steps": n, "wrong_steps": w,
              "evidence_digest": digest([{"event": e, "truth": t} for e, t in labeled_events])}
    return StreakProfile(**fields, digest=digest(fields))


def verify_profile(bank, profile):
    if type(profile) is not StreakProfile:
        raise ValueError("unsupported profile")
    fields = profile.as_dict()
    claimed = fields.pop("digest")
    _, fingerprint = catalogue(bank)
    if (fields["schema"] != SCHEMA or type(fields["seed"]) is not int or
        fields["seed"] != bank.seed or fields["bank_digest"] != fingerprint or
        digest(fields) != claimed or type(fields["min_streak"]) is not int or
        not 2 <= fields["min_streak"] <= 12 or
        type(fields["max_empirical_error"]) not in (int, float) or
        not 0 <= fields["max_empirical_error"] < 1 or
        type(fields["threshold"]) not in (int, float) or
        not math.isfinite(fields["threshold"]) or fields["threshold"] < 0 or
        any(type(fields[k]) is not int for k in
            ("calibration_steps", "eligible_steps", "accepted_steps", "wrong_steps")) or
        not 100 <= fields["calibration_steps"] <= 100000 or
        not 0 <= fields["wrong_steps"] <= fields["accepted_steps"] <= fields["eligible_steps"] <= fields["calibration_steps"] or
        (fields["accepted_steps"] > 0 and fields["wrong_steps"] / fields["accepted_steps"] > fields["max_empirical_error"]) or
        type(fields["evidence_digest"]) is not str or len(fields["evidence_digest"]) != 64):
        raise ValueError("invalid or stale streak calibration")
    return profile


def load_profile(blob):
    data = json.loads(blob)
    if type(data) is not dict or set(data) != set(StreakProfile.__dataclass_fields__):
        raise ValueError("invalid profile fields")
    return StreakProfile(**data)


class StreakSelector:
    """Pure bounded postprocessor. No sensor, model, or system permissions."""
    def __init__(self, bank, profile, checkpoint=None):
        self.profile = verify_profile(bank, profile)
        self.names = tuple(sorted(catalogue(bank)[0]))
        self.state = _initial()
        if checkpoint is not None:
            self.restore(checkpoint)

    def observe(self, event):
        next_state = dict(self.state)
        s = _advance(next_state, event, self.names)
        self.state = next_state
        if (s["status"] in ("warming", "unknown") or
            next_state["streak"] < self.profile.min_streak or
            s["gap"] < self.profile.threshold):
            return None
        return s["lead"]

    def checkpoint(self):
        body = {"schema": SCHEMA, "profile_digest": self.profile.digest,
                "state": dict(self.state)}
        return {**body, "digest": digest(body)}

    def restore(self, checkpoint):
        if type(checkpoint) is not dict or set(checkpoint) != {"schema", "profile_digest", "state", "digest"}:
            raise ValueError("invalid checkpoint")
        body = {k: v for k, v in checkpoint.items() if k != "digest"}
        s = checkpoint["state"]
        if (checkpoint["schema"] != SCHEMA or checkpoint["profile_digest"] != self.profile.digest or
            checkpoint["digest"] != digest(body) or type(s) is not dict or
            set(s) != set(_initial()) or
            any(type(s[k]) is not int for k in ("episode", "step", "seq", "streak")) or
            s["episode"] < 0 or not 0 <= s["step"] <= 40 or s["seq"] < 0 or
            not 0 <= s["streak"] <= s["step"] or
            s["lead"] not in (None, *self.names) or
            (s["episode"] == 0) != (s["seq"] == 0)):
            raise ValueError("invalid checkpoint contents")
        self.state = dict(s)
