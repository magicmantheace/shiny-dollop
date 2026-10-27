"""Experimental within-episode model switching from ordinary ring sensors.

Retains a posterior over known 9/11-ring positions AND two immutable, previously
fitted structured world-model hypotheses. A bounded switching hazard lets
old-model evidence decay instead of forcing one regime throughout an episode.
This does NOT discover novel models, infer free-form geometry, choose goals,
or authorize physical, file, network, or OS actions.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path

from developmental_ai.adaptive_dynamics import ACTIONS, canonical, distance, index_of, reading_index
from developmental_ai.structured_landmarks import StructuredModel

SCHEMA = "switching-belief/v1"
MAX_STEPS = 500


def _digest(obj):
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def _bank(models):
    if type(models) is not dict or not 1 <= len(models) <= 2:
        raise ValueError("expected one or two named, learned structured models")
    fingerprints = {}
    for name, model in sorted(models.items()):
        if (type(name) is not str or not 1 <= len(name) <= 40 or
                any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in name) or
                not isinstance(model, StructuredModel)):
            raise ValueError("invalid structured model entry")
        model.validate()
        fingerprints[name] = _digest(model.state())
    return fingerprints


class SwitchingBelief:
    """P(position, model | observations) with optional model-transition hazard.

    With hazard=0, the filter is exactly a static across-episode mixture.
    With two models, hazard h transitions between them before each sensor
    update. This is a *hand-chosen transition prior*, not learned adaptation.
    """

    def __init__(self, initial, goal, n, models, *, hazard=0.0, priors=None):
        if (type(n) is not int or n not in (9, 11) or type(initial) is not int or
                type(goal) is not int or not (0 <= initial < n and 0 <= goal < n)):
            raise ValueError("invalid one-time beacon")
        if type(hazard) not in (int, float) or not math.isfinite(hazard) or not 0 <= hazard <= .3:
            raise ValueError("invalid switching hazard")
        self.fingerprints = _bank(models)
        self.models = {name: models[name] for name in sorted(models)}
        if priors is None:
            priors = {name: 1 / len(models) for name in models}
        if (type(priors) is not dict or set(priors) != set(models) or
                any(type(p) not in (int, float) or not math.isfinite(p) or p < 0 or p > 1
                    for p in priors.values()) or
                not math.isclose(sum(priors.values()), 1, abs_tol=1e-10)):
            raise ValueError("invalid model priors")
        self.initial, self.goal, self.n, self.hazard = initial, goal, n, float(hazard)
        self.joint = {name: [float(priors[name]) if i == initial else 0. for i in range(n)]
                      for name in self.models}
        self.steps = 0
        self.log_evidence = 0.0

    @property
    def probs(self):
        return [sum(row[i] for row in self.joint.values()) for i in range(self.n)]

    @property
    def weights(self):
        return {name: sum(row) for name, row in self.joint.items()}

    def selected(self, threshold=.8):
        if type(threshold) not in (int, float) or not math.isfinite(threshold) or not .5 <= threshold <= 1:
            raise ValueError("invalid diagnostic threshold")
        weights = self.weights
        name = max(weights, key=lambda k: (weights[k], k))
        return name if weights[name] >= threshold else None

    def advance(self, action, observation):
        if type(action) is not int or action not in (0, 1, 2) or self.steps >= MAX_STEPS:
            raise ValueError("invalid or exhausted action")
        if (type(observation) is not dict or set(observation) != {"beacon", "odometry", "landmark"}
                or observation["beacon"] is not None):
            raise ValueError("post-initial ordinary sensors required")
        odometry = index_of(observation["odometry"])
        marker = reading_index(observation["landmark"])
        keys = list(self.models)
        old = self.joint
        if len(keys) == 2 and self.hazard > 0:
            a, b = keys
            prior = {a: [(1-self.hazard)*x + self.hazard*y for x,y in zip(old[a],old[b])],
                     b: [(1-self.hazard)*y + self.hazard*x for x,y in zip(old[a],old[b])]}
        else:
            prior = old
        posterior = {name: [0.0] * self.n for name in keys}
        for name, model in self.models.items():
            for pos, mass in enumerate(prior[name]):
                if mass <= 0:
                    continue
                moves = ((0,1.0),) if action == 2 else zip(
                    (ACTIONS[action],0,-ACTIONS[action]), model.motion_probs(ACTIONS[action]))
                for displacement, chance in moves:
                    arrival = (pos + displacement) % self.n
                    posterior[name][arrival] += (mass * chance *
                        model.odo_probs(displacement)[odometry] *
                        model.landmark_probs(self.n, arrival)[marker])
        evidence = sum(sum(row) for row in posterior.values())
        if not math.isfinite(evidence) or evidence <= 0 or evidence > 1+1e-8:
            raise ValueError("invalid predictive sensor likelihood")
        self.joint = {name: [p/evidence for p in row] for name,row in posterior.items()}
        self.steps += 1
        self.log_evidence += math.log(evidence)
        return math.log(evidence)

    def heuristic(self):
        """Legacy expected distance, without mixing weights into permissions."""
        if self.probs[self.goal] >= .45:
            return 2
        losses = []
        for action in (0, 1):
            cmd = ACTIONS[action]
            losses.append(sum(weight * motion_p * distance((pos + delta) % self.n, self.goal, self.n)
                for name, row in self.joint.items() for pos, weight in enumerate(row)
                for delta, motion_p in zip((cmd, 0, -cmd), self.models[name].motion_probs(cmd))))
        return 0 if losses[0] < losses[1] else 1

    def snapshot(self):
        state = {"schema": SCHEMA, "initial": self.initial, "goal": self.goal,
                 "n": self.n, "hazard": self.hazard, "models": self.fingerprints,
                 "joint": self.joint, "steps": self.steps, "log_evidence": self.log_evidence}
        return {"state": state, "sha256": _digest(state)}

    @classmethod
    def restore(cls, record, models, *, expected_hazard=None):
        if (type(record) is not dict or set(record) != {"state", "sha256"} or
                type(record["state"]) is not dict or type(record["sha256"]) is not str or
                _digest(record["state"]) != record["sha256"]):
            raise ValueError("altered or invalid switching checkpoint")
        s = record["state"]
        if (set(s) != {"schema", "initial", "goal", "n", "hazard", "models",
                       "joint", "steps", "log_evidence"} or s["schema"] != SCHEMA):
            raise ValueError("incompatible switching state")
        try:
            if expected_hazard is not None and s["hazard"] != expected_hazard:
                raise ValueError("hazard configuration mismatch")
            nav = cls(s["initial"],s["goal"],s["n"],models,hazard=s["hazard"])
        except (KeyError,TypeError,IndexError) as exc:
            raise ValueError("invalid switching configuration") from exc
        if s["models"] != nav.fingerprints:
            raise ValueError("immutable model bank mismatch")
        if (type(s["steps"]) is not int or not 0 <= s["steps"] <= MAX_STEPS or
                type(s["log_evidence"]) not in (int,float) or not math.isfinite(s["log_evidence"]) or
                s["log_evidence"] > 1e-8):
            raise ValueError("invalid checkpoint counters")
        joint = s["joint"]
        if type(joint) is not dict or set(joint) != set(nav.models):
            raise ValueError("invalid saved model posterior")
        for row in joint.values():
            if (type(row) is not list or len(row) != nav.n or
                    any(type(p) not in (int,float) or not math.isfinite(p) or p < 0 or p > 1 for p in row)):
                raise ValueError("invalid joint probabilities")
        if not math.isclose(sum(sum(row) for row in joint.values()),1,abs_tol=1e-9):
            raise ValueError("posterior not normalized")
        if s["steps"] == 0 and (s["log_evidence"] != 0 or any(
                any(abs(p)>1e-10 for i,p in enumerate(row) if i != nav.initial)
                for row in joint.values())):
            raise ValueError("invalid initial position")
        nav.joint = {name:list(joint[name]) for name in nav.models}
        nav.steps,nav.log_evidence = s["steps"],float(s["log_evidence"])
        return nav


class SwitchingCheckpoint:
    """Local, digest-checked SQLite checkpoint; NOT authenticated authorization."""
    def __init__(self, path):
        p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(p)
        self.db.execute("CREATE TABLE IF NOT EXISTS switching_state (id INTEGER PRIMARY KEY CHECK(id=1), record TEXT NOT NULL)")

    def save(self, nav):
        if not isinstance(nav,SwitchingBelief):raise ValueError("invalid switching navigator")
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO switching_state(id,record) VALUES(1,?)",
                            (canonical(nav.snapshot()),))

    def load(self, models, *, expected_hazard=None):
        row=self.db.execute("SELECT record FROM switching_state WHERE id=1").fetchone()
        if row is None:return None
        try:return SwitchingBelief.restore(json.loads(row[0]),models,expected_hazard=expected_hazard)
        except (TypeError,KeyError,json.JSONDecodeError) as exc:
            raise ValueError("invalid switching checkpoint") from exc

    def close(self):self.db.close()
    def __enter__(self):return self
    def __exit__(self,*_):self.close()


def _calibration_stream(record):
    """Validate a strictly ordinary-observation stream, with no truth fields."""
    if (type(record) is not dict or set(record) != {"initial", "goal", "n", "observations"} or
            type(record["observations"]) is not list or
            not 1 <= len(record["observations"]) <= MAX_STEPS):
        raise ValueError("invalid or privileged calibration stream")
    # A dummy single-model filter verifies the one-time beacon and every
    # action/sensor tuple without accessing simulator hidden state.
    for event in record["observations"]:
        if (type(event) is not list or len(event) != 2 or
                type(event[0]) is not int or event[0] not in (0,1,2) or
                type(event[1]) is not dict or set(event[1]) != {"beacon", "odometry", "landmark"} or
                event[1]["beacon"] is not None):
            raise ValueError("invalid calibration sensor event")
        index_of(event[1]["odometry"])
        reading_index(event[1]["landmark"])
    if (type(record["n"]) is not int or record["n"] not in (9,11) or
            type(record["initial"]) is not int or not 0 <= record["initial"] < record["n"] or
            type(record["goal"]) is not int or not 0 <= record["goal"] < record["n"]):
        raise ValueError("invalid calibration beacon")


def calibrate_hazard(models, streams, *, candidates=(0.,.01,.04,.10,.20)):
    """Pick a transition prior by observation likelihood; never uses truth.

    Callers must collect these on a separate train namespace, and must not use
    evaluation streams to retune candidates. Receipt is a checksum, not consent.
    """
    fingerprints = _bank(models)
    if type(streams) not in (list,tuple) or not 2 <= len(streams) <= 200:
        raise ValueError("insufficient independent calibration streams")
    if (type(candidates) not in (tuple,list) or not candidates or len(set(candidates)) != len(candidates) or
            0. not in candidates or any(type(h) not in (float,int) or not math.isfinite(h) or not 0 <= h <= .3 for h in candidates)):
        raise ValueError("invalid hazard candidates")
    digests=[]
    for record in streams:
        _calibration_stream(record)
        digests.append(_digest(record))
    if len(set(digests)) != len(digests):
        raise ValueError("repeated calibration evidence")
    scores={}
    steps=sum(len(r["observations"]) for r in streams)
    for hazard in candidates:
        evidence=0.
        for r in streams:
            nav=SwitchingBelief(r["initial"],r["goal"],r["n"],models,hazard=hazard)
            for action,observation in r["observations"]:
                evidence+=nav.advance(action,observation)
        scores[str(hazard)]=round(-evidence/steps,9)
    winner=min(candidates,key=lambda h:(scores[str(h)],h))
    state={"schema":"switching-calibration/v1","models":fingerprints,"hazard":winner,
           "calibration_digest":_digest(sorted(digests)),"episodes":len(streams),
           "total_steps":steps,"scores":scores}
    return {"state":state,"sha256":_digest(state)}


def verified_hazard(receipt,models):
    """Fail closed on bank mismatch or malformed receipt; not authorization."""
    if (type(receipt) is not dict or set(receipt) != {"state","sha256"} or
            type(receipt["state"]) is not dict or
            type(receipt["sha256"]) is not str or _digest(receipt["state"]) != receipt["sha256"]):
        raise ValueError("invalid calibration receipt")
    state=receipt["state"]
    if (set(state) != {"schema","models","hazard","calibration_digest","episodes","total_steps","scores"} or
            state["schema"] != "switching-calibration/v1" or state["models"] != _bank(models) or
            type(state["calibration_digest"]) is not str or len(state["calibration_digest"]) != 64 or
            any(c not in "0123456789abcdef" for c in state["calibration_digest"]) or
            type(state["episodes"]) is not int or not 2 <= state["episodes"] <= 200 or
            type(state["total_steps"]) is not int or state["total_steps"] < state["episodes"] or
            type(state["scores"]) is not dict or not state["scores"] or
            any(type(v) not in (int,float) or not math.isfinite(v) or v < 0 for v in state["scores"].values()) or
            type(state["hazard"]) not in (int,float) or not 0 <= state["hazard"] <= .3 or
            str(state["hazard"]) not in state["scores"] or
            any(type(k) is not str for k in state["scores"])):
        raise ValueError("invalid model-bound calibration")
    try:
        hazards=[float(key) for key in state["scores"]]
        if (any(not math.isfinite(h) or h < 0 or h > .3 or str(h) not in state["scores"] for h in hazards) or
                state["hazard"] != min(hazards,key=lambda h:(state["scores"][str(h)],h)) or
                str(state["hazard"]) not in state["scores"]):
            raise ValueError("invalid calibration winner")
    except (TypeError,OverflowError,ValueError) as exc:
        raise ValueError("invalid model-bound calibration") from exc
    return state["hazard"]
