"""Evidence-triggered horizon choice for identical-schema latent reversals.

Archived source skill remains intact. Short (8) versus longer (32) recent
context is selected by a *developer-defined* count of public predictive
surprises relative to the archive, not by hidden simulator change labels.
Trigger events overlap with recent model training: this is not an
independent validation method and is subject to selection overfitting.
"""
from __future__ import annotations

import json

from developmental_ai.fast_shock_memory import (
    FastShockMemory, ANCHOR, RECENT, SURPRISE_WINDOW,
    SURPRISE_PROBABILITY,
)
from developmental_ai.observable_affordances import (
    MAX_SAMPLES, canonical, digest,
)

SCHEMA = "developmental-ai.adaptive-memory-horizon/v1"
LONG_WINDOW = 32
LONG_SURPRISE_MIN = 15


class AdaptiveHorizonMemory(FastShockMemory):
    """Pick archived, last-eight, or last-thirty-two learned outcome data."""

    def selection(self):
        if len(self.events) < ANCHOR + RECENT:
            raise ValueError("insufficient public evidence for horizon selection")
        anchor = self._model(self.events[:ANCHOR])
        latest = self.events[-LONG_WINDOW:]
        surprising = [
            int(self._probability(anchor, row) < SURPRISE_PROBABILITY)
            for row in latest
        ]
        newest_four = sum(surprising[-SURPRISE_WINDOW:])
        newest_eight = sum(surprising[-RECENT:])
        newest_thirty_two = sum(surprising)
        switched = newest_four >= 2 or (
            newest_four == 1 and newest_eight >= 3
        )
        if not switched:
            source = "archive"
            fit = anchor
            length = ANCHOR
        else:
            length = (LONG_WINDOW if newest_thirty_two >= LONG_SURPRISE_MIN
                      else RECENT)
            source = "recent32" if length == LONG_WINDOW else "recent8"
            fit = self._model(self.events[-length:])
        summary = {
            "source": source,
            "latest_four_surprises": newest_four,
            "latest_eight_surprises": newest_eight,
            "latest_thirty_two_surprises": newest_thirty_two,
            "used_events": length,
            "selection_training_overlap": (0 if source == "archive"
                                           else length),
            "recorded_events": len(self.events),
        }
        return summary, fit

    def record(self):
        if not self.events:
            raise ValueError("untrained adaptive horizon")
        state = {"schema": SCHEMA, "events": self.events}
        return {"state": json.loads(canonical(state)), "sha256": digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or
                set(record) != {"state", "sha256"} or
                type(record["state"]) is not dict or
                type(record["sha256"]) is not str or
                digest(record["state"]) != record["sha256"]):
            raise ValueError("invalid adaptive horizon hash")
        state = record["state"]
        if (set(state) != {"schema", "events"} or
                state["schema"] != SCHEMA or
                type(state["events"]) is not list or
                not 1 <= len(state["events"]) <= MAX_SAMPLES):
            raise ValueError("invalid adaptive horizon checkpoint")
        model = cls()
        for row in state["events"]:
            model.observe(row)
        if model.record() != record:
            raise ValueError("adaptive horizon checkpoint replay mismatch")
        return model
