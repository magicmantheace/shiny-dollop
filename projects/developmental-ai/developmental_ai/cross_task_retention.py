"""Experimental reward-learned retention strategy transferred across task families.

The candidate strategies (keep initial vs overwrite with latest) and the
semantic cue/step mapping are engineered. Selection of the strategy and the
symbol/action association are learned from ordinary delayed-task observations
and terminal rewards, without hidden correct actions or simulator internals.
The chosen strategy can gate an existing learned spatial-memory updater on
occluded navigation. This is *not* general learned attention.
"""
from __future__ import annotations

import hashlib
import json
import math
import random

from developmental_ai.environment_api import EnvironmentSession, canonical, digest

SCHEMA = "developmental-ai.cross-task-retention/v1"
STRATEGIES = ("initial", "latest")
MAX_TRAIN = 4000


def _seed(seed, *parts):
    return int.from_bytes(hashlib.sha256((SCHEMA + "/" + "/".join(map(str, (seed, *parts)))).encode()).digest()[:8], "big")


def _validate_frame(frame, tick):
    if (type(frame) is not dict or frame.get("family") != "delayed" or
            frame.get("scope") != "simulation-only" or frame.get("source") != "simulation" or
            frame.get("tick") != tick or type(frame.get("observation")) is not dict or
            set(frame["observation"]) != {"phase", "token"}):
        raise ValueError("invalid delayed-task public frame")
    obs = frame["observation"]
    if (obs["phase"] not in ("cue", "distractor", "decision", "finished") or
            (obs["phase"] in ("cue", "distractor") and (type(obs["token"]) is not int or not 0 <= obs["token"] < 4)) or
            (obs["phase"] in ("decision", "finished") and obs["token"] is not None)):
        raise ValueError("invalid delayed-task public observation")
    return obs


def _trial(seed, index, strategy, q=None, *, split="train", variant="short", learn=False):
    """Task outcome is the only learning signal; no privileged answer supplied."""
    if strategy not in STRATEGIES or split not in ("train", "test") or variant not in ("short", "long"):
        raise ValueError("invalid trial configuration")
    session = EnvironmentSession("delayed", seed, split, index, variant=variant)
    rng = random.Random(_seed(seed, strategy, split, index, "policy"))
    memory = None
    cue_seen = False
    last = None
    while not session.done:
        frame = session.frame()
        obs = _validate_frame(frame, session.tick)
        if obs["phase"] == "cue":
            if cue_seen:
                raise ValueError("duplicate initial cue")
            cue_seen = True
            memory = obs["token"]
        elif obs["phase"] == "distractor" and strategy == "latest":
            memory = obs["token"]
        if obs["phase"] == "decision":
            if not cue_seen or memory is None:
                raise ValueError("missing memory evidence")
            if q is None:
                action = 0
            else:
                values = q[str(memory)]
                epsilon = .25 if learn else 0
                action = rng.randrange(4) if rng.random() < epsilon else rng.choice(
                    [a for a, v in enumerate(values) if v == max(values)])
        else:
            action = 4
        if action not in frame["available_actions"]:
            raise ValueError("strategy issued illegal action")
        result = session.step(action, expected_tick=frame["tick"])
        if obs["phase"] == "decision":
            last = result["event"]
            if learn:
                if type(result["reward"]) not in (float,int) or not math.isfinite(result["reward"]):
                    raise ValueError("invalid reward")
                old = q[str(memory)][action]
                q[str(memory)][action] = old + .3*(result["reward"]-old)
    return last == "correct"


class RetentionGate:
    """Read-only snapshot of a strategy picked on separate train-only trials."""
    def __init__(self, *, seed, trained, validated, strategy, q, scores):
        if (type(seed) is not int or type(trained) is not int or not 1 <= trained <= MAX_TRAIN or
                type(validated) is not int or not 1 <= validated <= 2000 or strategy not in STRATEGIES or
                type(q) is not dict or set(q) != set(STRATEGIES) or
                type(scores) is not dict or set(scores) != set(STRATEGIES)):
            raise ValueError("invalid retention gate configuration")
        for option in STRATEGIES:
            table = q[option]
            if (type(table) is not dict or set(table) != {"0", "1", "2", "3"} or
                    any(type(values) is not list or len(values)!=4 or any(type(v) not in (float,int) or not math.isfinite(v) or abs(v)>1.01 for v in values) for values in table.values()) or
                    type(scores[option]) is not int or not 0 <= scores[option] <= validated):
                raise ValueError("invalid learned gate values")
        if strategy != max(STRATEGIES, key=lambda s:(scores[s], -STRATEGIES.index(s))):
            raise ValueError("saved strategy contradicts training-only validation")
        self.seed, self.trained, self.validated, self.strategy = seed, trained, validated, strategy
        self.q = json.loads(canonical(q))
        self.scores = dict(scores)

    @property
    def retains_initial(self):
        return self.strategy == "initial"

    def record(self):
        state = {"schema":SCHEMA, "seed":self.seed, "trained":self.trained,
                 "validated":self.validated, "strategy":self.strategy,
                 "q":self.q, "scores":self.scores}
        return {"state":state, "digest":digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record) != {"state", "digest"} or
                type(record["state"]) is not dict or record["digest"] != digest(record["state"]) or
                set(record["state"]) != {"schema", "seed", "trained", "validated", "strategy", "q", "scores"} or
                record["state"]["schema"] != SCHEMA):
            raise ValueError("invalid or modified retention snapshot")
        return cls(**{k:v for k,v in record["state"].items() if k!="schema"})


def fit_gate(seed, *, episodes=400, validation=120):
    """No test data: 2 independently learned mappings; separate train validation.

    Each candidate sees the same fit episodes 0..N-1. Validation uses train
    indices 5000+ and cannot change either candidate's learned mapping.
    """
    if (type(seed) is not int or type(episodes) is not int or not 1 <= episodes <= MAX_TRAIN or
            type(validation) is not int or not 1 <= validation <= 2000):
        raise ValueError("invalid fitting budget")
    tables = {s:{str(symbol):[0.]*4 for symbol in range(4)} for s in STRATEGIES}
    for strategy in STRATEGIES:
        for index in range(episodes):
            _trial(seed,index,strategy,tables[strategy],learn=True)
    scores = {strategy:sum(_trial(seed,5000+i,strategy,tables[strategy]) for i in range(validation))
              for strategy in STRATEGIES}
    choice = max(STRATEGIES, key=lambda s:(scores[s], -STRATEGIES.index(s)))
    return RetentionGate(seed=seed,trained=episodes,validated=validation,strategy=choice,q=tables,scores=scores)


def delayed_success(gate, index, *, strategy=None, variant="long"):
    if not isinstance(gate,RetentionGate):
        raise ValueError("expected learned gate")
    option = gate.strategy if strategy is None else strategy
    return _trial(gate.seed,index,option,gate.q[option],split="test",variant=variant)
