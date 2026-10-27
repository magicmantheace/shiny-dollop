"""Joint inference of *position and saved-world-model identity* from sensors.

Experimental, known 9/11-cell ring. The agent receives a one-time start/goal
beacon and ordinary commanded actions/odometry/landmark readings; the simulator's
hidden position, regime identity, outcomes and reward are never input to inference.
A bank of previously learned, immutable model hypotheses is required. No new
model is fitted, approved or installed, and no external actions are permitted.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path

from developmental_ai.adaptive_dynamics import ACTIONS, DynamicsModel, canonical, distance, index_of, reading_index
from developmental_ai.online_dynamics import score, validate_history

SCHEMA = "mixture-navigation/v1"
MAX_STEPS = 500


def digest(obj):
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def _models(models):
    if type(models) is not dict or not 1 <= len(models) <= 8:
        raise ValueError("expected 1-8 named dynamics models")
    fingerprints = {}
    for name, model in sorted(models.items()):
        if (type(name) is not str or not 1 <= len(name) <= 40 or
                any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in name) or
                not isinstance(model, DynamicsModel)):
            raise ValueError("invalid model bank entry")
        model.validate()
        fingerprints[name] = digest(model.counts)
    return fingerprints


def probe_priors(models, histories, *, effective_steps=16, floor=.05):
    """Heuristic model prior from separate, unlabelled observation-only probes.

    Caps effective evidence so a long or correlated probe cannot collapse the
    bank to certainty. This is NOT a calibrated confidence probability and
    should not be used as a real-world authorization signal.
    """
    _models(models)
    if type(histories) not in (tuple, list) or not 1 <= len(histories) <= 100:
        raise ValueError("expected 1-100 probe histories")
    if (type(effective_steps) is not int or not 1 <= effective_steps <= 40 or
            type(floor) not in (int, float) or not math.isfinite(floor) or not 0 <= floor <= .5):
        raise ValueError("invalid probe prior configuration")
    for h in histories:
        validate_history(h)
    if len({h["n"] for h in histories}) > 2:
        raise ValueError("invalid topology")
    scores = {k: score(models[k], histories) * effective_steps for k in sorted(models)}
    maximum = max(scores.values())
    evidence = {k: math.exp(v-maximum) for k, v in scores.items()}
    total = sum(evidence.values())
    weights = {k: floor/len(evidence) + (1-floor)*v/total for k,v in evidence.items()}
    return weights


class MixtureNavigator:
    """Normalized P(world model, true position | ordinary sensor history)."""

    def __init__(self, initial, goal, n, models, *, priors=None):
        if type(n) is not int or n not in (9, 11) or type(initial) is not int or type(goal) is not int or not (0 <= initial < n and 0 <= goal < n):
            raise ValueError("invalid initial beacon or topology")
        self.fingerprints = _models(models)
        self.models = {key: models[key] for key in sorted(models)}
        self.n, self.initial, self.goal = n, initial, goal
        self.steps = 0
        self.log_evidence = 0.0
        if priors is None:
            priors = {k:1.0/len(models) for k in models}
        if (type(priors) is not dict or set(priors) != set(models) or
                any(type(p) not in (float,int) or not math.isfinite(p) or p < 0 or p > 1 for p in priors.values()) or
                not math.isclose(sum(priors.values()),1.0,abs_tol=1e-8)):
            raise ValueError("invalid model priors")
        self.joint = {key: [float(priors[key]) if p == initial else 0.0 for p in range(n)] for key in sorted(models)}

    @property
    def probs(self):
        return [sum(row[pos] for row in self.joint.values()) for pos in range(self.n)]

    @property
    def weights(self):
        return {name: sum(row) for name, row in self.joint.items()}

    def select(self, *, threshold=.9):
        """Diagnostic model choice, with abstention; not a permission grant."""
        if type(threshold) not in (int, float) or not math.isfinite(threshold) or not .5 <= threshold <= 1:
            raise ValueError("invalid confidence threshold")
        weights = self.weights
        winner = max(sorted(weights), key=lambda k: weights[k])
        return winner if weights[winner] >= threshold else None

    def advance(self, action, observation):
        if type(action) is not int or action not in (0, 1, 2) or self.steps >= MAX_STEPS:
            raise ValueError("invalid or exhausted episode action")
        if type(observation) is not dict or set(observation) != {"beacon", "odometry", "landmark"} or observation["beacon"] is not None:
            raise ValueError("only ordinary post-initial sensor readings allowed")
        sensed_odo = index_of(observation["odometry"])
        sensed_mark = reading_index(observation["landmark"])
        updated = {key: [0.0] * self.n for key in self.models}
        for name, model in self.models.items():
            for old, mass in enumerate(self.joint[name]):
                if mass == 0.0:
                    continue
                if action == 2:
                    moves = ((0, 1.0),)
                else:
                    command = ACTIONS[action]
                    moves = zip((command, 0, -command), model.motion_probs(command))
                for step, chance in moves:
                    pos = (old + step) % self.n
                    updated[name][pos] += (mass * chance * model.odo_probs(step)[sensed_odo]
                                           * model.landmark_probs(self.n, pos)[sensed_mark])
        evidence = sum(sum(row) for row in updated.values())
        if evidence <= 0 or not math.isfinite(evidence):
            raise ValueError("invalid predictive probability")
        self.joint = {key: [v / evidence for v in row] for key, row in updated.items()}
        self.steps += 1
        self.log_evidence += math.log(evidence)
        return math.log(evidence)

    def heuristic(self):
        if self.probs[self.goal] >= .45:
            return 2
        losses = []
        for action in (0, 1):
            command = ACTIONS[action]
            loss = sum(mass * chance * distance((pos + delta) % self.n, self.goal, self.n)
                       for name, row in self.joint.items()
                       for pos, mass in enumerate(row)
                       for delta, chance in zip((command, 0, -command), self.models[name].motion_probs(command)))
            losses.append(loss)
        return 0 if losses[0] < losses[1] else 1

    def snapshot(self):
        body = {"schema": SCHEMA, "n": self.n, "initial": self.initial, "goal": self.goal,
                "steps": self.steps, "log_evidence": self.log_evidence,
                "models": self.fingerprints, "joint": self.joint}
        return {"body": body, "digest": digest(body)}

    @classmethod
    def restore(cls, record, models):
        if type(record) is not dict or set(record) != {"body", "digest"} or type(record["body"]) is not dict or type(record["digest"]) is not str or digest(record["body"]) != record["digest"]:
            raise ValueError("invalid or altered snapshot")
        b = record["body"]
        if set(b) != {"schema", "n", "initial", "goal", "steps", "log_evidence", "models", "joint"} or b["schema"] != SCHEMA:
            raise ValueError("incompatible state schema")
        if type(b.get("joint")) is not dict or set(b["joint"]) != set(models):
            raise ValueError("invalid posterior bank")
        # Restore actual joint probabilities below; the constructor validates
        # basic syntax and binding, while the snapshot is independently checked.
        nav = cls(b["initial"], b["goal"], b["n"], models)
        if (b["models"] != nav.fingerprints or type(b["steps"]) is not int or not 0 <= b["steps"] <= MAX_STEPS or
                type(b["log_evidence"]) not in (int, float) or not math.isfinite(b["log_evidence"]) or b["log_evidence"] > 1e-8):
            raise ValueError("incompatible snapshot or model bank")
        joint = b["joint"]
        if type(joint) is not dict or set(joint) != set(nav.models):
            raise ValueError("invalid joint posterior")
        for row in joint.values():
            if (type(row) is not list or len(row) != nav.n or
                    any(type(p) not in (int, float) or not math.isfinite(p) or p < 0 or p > 1 for p in row)):
                raise ValueError("invalid posterior values")
        if not math.isclose(sum(sum(row) for row in joint.values()), 1.0, abs_tol=1e-8):
            raise ValueError("unnormalized posterior")
        if b["steps"] == 0:
            if any(any(abs(p) > 1e-9 for i,p in enumerate(joint[k]) if i != nav.initial) for k in joint) or b["log_evidence"] != 0:
                raise ValueError("inconsistent initial checkpoint")
        nav.joint = {k: list(joint[k]) for k in nav.models}
        nav.steps, nav.log_evidence = b["steps"], float(b["log_evidence"])
        return nav


class MixtureCheckpoint:
    """One local SQLite checkpoint. SHA detects accidental edits, not forgery."""

    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS mixture_state (id INTEGER PRIMARY KEY CHECK(id=1), record TEXT NOT NULL)")

    def save(self, navigator):
        if not isinstance(navigator, MixtureNavigator):
            raise ValueError("expected mixture navigator")
        saved = canonical(navigator.snapshot())
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO mixture_state(id,record) VALUES(1,?)", (saved,))

    def load(self, models):
        row = self.db.execute("SELECT record FROM mixture_state WHERE id=1").fetchone()
        if row is None:
            return None
        return MixtureNavigator.restore(json.loads(row[0]), models)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
