"""Reward-only token-pair alignment across disjoint symbolic alphabets.

The learner sees public observations, candidate symbolic forecasts and offsets;
no simulator truth, source label, permutation, oracle cue, or paired reference.
It fits a reward-conditioned pair-frequency score, not a neural representation.
The slot alignment and four-token alphabets are ENGINEERED priors. Simulation only.
"""
from __future__ import annotations

import hashlib
import json
import math
import random

from developmental_ai.environment_api import canonical, digest

SCHEMA = "developmental-ai.raw-token-alignment/v1"
START = 88500
LIMIT = 360
SOURCES = tuple(f"src_{i}" for i in range(5))
OBS = tuple(f"sensor-{i}" for i in range(4))
FORECAST = tuple(f"forecast-{i}" for i in range(4))
LENGTH = 8


def validate(observed, candidates):
    if (type(observed) is not list or len(observed) != LENGTH or
            any(type(v) is not str or v not in OBS for v in observed) or
            type(candidates) is not list or len(candidates) != 5):
        raise ValueError("invalid public observation stream")
    labels = set()
    for row in candidates:
        if (type(row) is not list or len(row) != 3 or
                type(row[0]) is not str or row[0] not in SOURCES or row[0] in labels or
                type(row[1]) is not list or len(row[1]) != 2 or
                any(type(v) is not int or not -8 <= v <= 8 for v in row[1]) or
                type(row[2]) is not list or len(row[2]) != LENGTH or
                any(type(v) is not str or v not in FORECAST for v in row[2])):
            raise ValueError("invalid, duplicate or privileged cue")
        labels.add(row[0])
    if labels != set(SOURCES):
        raise ValueError("missing candidate sources")
    return {row[0]: list(row[2]) for row in candidates}


def pairs(observed, forecast):
    return [(OBS.index(a) * 4 + FORECAST.index(b)) for a, b in zip(observed, forecast)]


class RewardTokenAligner:
    """Bandit fit via balanced random exploration, pooled positive/negative pairs.

    A terminal navigation success is the ONLY fit label. Evaluation is read-only.
    Chosen-source records are verified by deterministic replay on restore.
    """
    def __init__(self, seed):
        if type(seed) is not int:
            raise ValueError("invalid model seed")
        self.seed = seed
        self.successes = [0] * 16
        self.failures = [0] * 16
        self.events = []
        self.pending = None

    def _random_name(self, index):
        b = hashlib.sha256(f"{SCHEMA}/{self.seed}/{index}/explore".encode()).digest()
        return SOURCES[int.from_bytes(b[:8], "big") % 5]

    def propose(self, observed, candidates, *, split, index):
        forecasts = validate(observed, candidates)
        if (self.pending is not None or split != "train" or type(index) is not int or
                index != START + len(self.events) or len(self.events) >= LIMIT):
            raise ValueError("unrequested or out-of-order training proposal")
        selected = self._random_name(index)
        self.pending = (index, list(observed), forecasts[selected], selected)
        return list(next(c[1] for c in candidates if c[0] == selected))

    def feedback(self, success, *, split, index):
        if (type(success) is not bool or self.pending is None or split != "train" or
                type(index) is not int or index != self.pending[0]):
            raise ValueError("invalid reward or missing pending decision")
        _, obs, forecast, name = self.pending
        table = self.successes if success else self.failures
        for key in pairs(obs, forecast):
            table[key] += 1
        self.events.append({"index": index, "observed": obs, "forecast": forecast,
                            "chosen": name, "success": success})
        self.pending = None

    def score(self, observed, forecast):
        if not self.events or self.pending is not None:
            raise ValueError("model must be fitted and settled")
        pos = sum(self.successes)
        neg = sum(self.failures)
        # A finite Laplace-smoothed log likelihood ratio over raw token pairs.
        # No engineered equality count or known permutation is supplied.
        return sum(math.log((self.successes[key]+1)/(pos+16)) -
                   math.log((self.failures[key]+1)/(neg+16)) for key in pairs(observed, forecast))

    def source(self, observed, candidates):
        forecasts = validate(observed, candidates)
        rankings = [(self.score(observed, seq), name) for name, seq in forecasts.items()]
        best = max(q for q, _ in rankings)
        return min(name for q, name in rankings if q == best)

    def predict(self, observed, candidates):
        chosen = self.source(observed, candidates)
        return list(next(c[1] for c in candidates if c[0] == chosen))

    def record(self):
        if not self.events or self.pending is not None:
            raise ValueError("incomplete model")
        state = {"schema": SCHEMA, "seed": self.seed, "events": self.events,
                 "successes": self.successes, "failures": self.failures}
        return {"state": json.loads(canonical(state)), "digest": digest(state)}

    @classmethod
    def restore(cls, saved):
        if (type(saved) is not dict or set(saved) != {"state", "digest"} or
                type(saved["state"]) is not dict or saved["digest"] != digest(saved["state"])):
            raise ValueError("invalid checkpoint integrity")
        s = saved["state"]
        if (set(s) != {"schema", "seed", "events", "successes", "failures"} or
                s["schema"] != SCHEMA or type(s["events"]) is not list or
                not 1 <= len(s["events"]) <= LIMIT):
            raise ValueError("incompatible checkpoint")
        rebuilt = cls(s["seed"])
        for i, event in enumerate(s["events"]):
            if (type(event) is not dict or set(event) != {"index", "observed", "forecast", "chosen", "success"} or
                    event["index"] != START+i or type(event["success"]) is not bool or
                    type(event["chosen"]) is not str or event["chosen"] not in SOURCES or
                    type(event["forecast"]) is not list or len(event["forecast"]) != LENGTH or
                    any(type(x) is not str or x not in FORECAST for x in event["forecast"]) or
                    type(event["observed"]) is not list or len(event["observed"]) != LENGTH or
                    any(type(x) is not str or x not in OBS for x in event["observed"])):
                raise ValueError("invalid learned event")
            # Rebuild source decisions and reward statistics without simulator truth.
            dummy = [[name,[0,0],list(event["forecast"] if name == event["chosen"] else [FORECAST[0]]*LENGTH)]
                     for name in SOURCES]
            rebuilt.propose(event["observed"], dummy, split="train", index=START+i)
            if rebuilt.pending[3] != event["chosen"]:
                raise ValueError("saved choice conflicts with policy")
            rebuilt.feedback(event["success"], split="train", index=START+i)
        if rebuilt.record() != saved:
            raise ValueError("checkpoint statistics do not replay")
        return rebuilt
