"""Experimental relation-transfer model trained on public numeric outcomes.

No family identifiers, band/rule centers, stable handles or target labels are
accepted. Range = max-minus-min is an intentionally hand-authored inductive
bias: training only estimates P(outcome | range). A good zero-shot score on
families deliberately sharing this rule is NOT general physics inference.
"""
from __future__ import annotations

import json

from developmental_ai.observable_affordances import (
    MAX_SAMPLES, VARIABLE_MODEL_SCHEMA, VariableOutcomeMemory,
    canonical, digest, variable_feature_check,
)

SCHEMA = "developmental-ai.relational-outcome-memory/v1"
ALPHA = 0.25


def span(features):
    variable_feature_check(features)
    vals = tuple(features.values())
    return max(vals) - min(vals)


class RelationOutcomeMemory:
    """Learn value-range outcome distributions across unseen feature-key sets.

    All observed examples are retained and checkpointed, without per-family
    names. Buckets share only a *designer-specified* range statistic.
    """
    def __init__(self):
        self.events = []
        self.counts = [[0, 0, 0] for _ in range(10)]

    def observe(self, event):
        if (type(event) is not dict or set(event) != {"features", "progress", "damage"}
                or type(event["progress"]) is not bool
                or type(event["damage"]) is not bool
                or (event["progress"] and event["damage"])
                or len(self.events) >= MAX_SAMPLES):
            raise ValueError("invalid relational outcome evidence")
        bucket = span(event["features"])
        copy = json.loads(canonical(event))
        self.events.append(copy)
        category = 0 if copy["progress"] else 1 if copy["damage"] else 2
        self.counts[bucket][category] += 1

    def estimate(self, features):
        bucket = span(features)
        counts = self.counts[bucket]
        total = sum(counts)
        return {
            "progress": (counts[0] + ALPHA) / (total + 3 * ALPHA),
            "damage": (counts[1] + ALPHA) / (total + 3 * ALPHA),
            "evidence": total,
            "span": bucket,
        }

    def choose(self, frame):
        # Strictly reuse the existing variable-schema *frame* validation and
        # refuse unknown or malformed action handles; its prediction is not used.
        VariableOutcomeMemory().choose(frame)
        if frame["done"]:
            return None
        ranked = []
        for action in frame["actions"]:
            probabilities = self.estimate(action["features"])
            score = 3 * probabilities["progress"] - 10 * probabilities["damage"]
            ranked.append((-score, action["id"]))
        return min(ranked)[1] if ranked else None

    def record(self):
        if not self.events:
            raise ValueError("empty relation model")
        state = {"schema": SCHEMA, "events": self.events,
                 "outcome_counts": self.counts}
        return {"state": json.loads(canonical(state)), "sha256": digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record) != {"state", "sha256"}
                or type(record["state"]) is not dict
                or type(record["sha256"]) is not str
                or record["sha256"] != digest(record["state"])):
            raise ValueError("invalid relation memory checksum")
        state = record["state"]
        if (set(state) != {"schema", "events", "outcome_counts"}
                or state["schema"] != SCHEMA
                or type(state["events"]) is not list
                or not 1 <= len(state["events"]) <= MAX_SAMPLES):
            raise ValueError("invalid relation memory checkpoint")
        result = cls()
        for example in state["events"]:
            result.observe(example)
        if result.record() != record:
            raise ValueError("relation memory checksum does not replay learned counts")
        return result
