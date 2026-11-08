"""Optional multi-switch contrastive outcome memory on an unchanged schema.

All inferred 'change points' are derived solely from chronological, observed
features/progress/damage records. A negative-surprise entry gate is balanced
by explicit archive *advantage* over an independent recent comparison sample
before reentry; neutral outcomes agreeing under both models cannot, alone,
force a return to obsolete knowledge. Handcrafted thresholds and sensor-range
features are research priors, not domain-general safety.
"""
from __future__ import annotations

import json

from developmental_ai.fast_shock_memory import (
    FastShockMemory, ANCHOR, SURPRISE_PROBABILITY,
)
from developmental_ai.observable_affordances import MAX_SAMPLES, canonical, digest

SCHEMA = "developmental-ai.multi-switch-contrast/v1"
WARMUP = 240
ENTRY_TAIL = 4
ENTRY_ERRORS = 2
ARCHIVE_SUPPORT_PROB = 0.55
ARCHIVE_ADVANTAGE_RATIO = 4.0
RETURN_SUPPORT_EVENTS = 2
MIN_RECENT_FOR_RETURN = 8
LONG_AFTER_RECENT = 24
SHORT_HORIZON = 8
LONG_HORIZON = 32


class MultiSwitchContrastMemory(FastShockMemory):
    """A stable archive, fast recent evidence and evidence-based return."""

    def __init__(self):
        super().__init__()
        self._cached_selection = None

    def observe(self, event):
        super().observe(event)
        self._cached_selection = None

    def selection(self):
        if self._cached_selection is not None:
            return self._cached_selection
        if len(self.events) < WARMUP:
            raise ValueError("fewer than 240 public source observations")
        anchor = self._model(self.events[:ANCHOR])
        state = "archive"
        recent_since = None
        transitions = []
        entry_count = 0
        archive_support = 0
        # Deterministic state reconstruction from PUBLIC historical evidence.
        for i in range(WARMUP + 1, len(self.events) + 1):
            trailing = self.events[max(0, i - ENTRY_TAIL):i]
            if state == "archive":
                entry_count = sum(
                    self._probability(anchor, event) < SURPRISE_PROBABILITY
                    for event in trailing
                )
                if entry_count >= ENTRY_ERRORS:
                    state = "recent"
                    recent_since = i
                    transitions.append({"index": i, "source": "recent"})
            else:
                archive_support = 0
                if i - recent_since >= MIN_RECENT_FOR_RETURN:
                    # Always exclude the four scored observations from the
                    # competing recent fit; never use simulator phase names.
                    prior = self.events[max(WARMUP, i - LONG_HORIZON
                                            - ENTRY_TAIL): i - ENTRY_TAIL]
                    if len(prior) >= MIN_RECENT_FOR_RETURN:
                        alternate = self._model(prior)
                        archive_support = sum(
                            self._probability(anchor, event) >= ARCHIVE_SUPPORT_PROB
                            and self._probability(anchor, event) >=
                            ARCHIVE_ADVANTAGE_RATIO *
                            self._probability(alternate, event)
                            for event in trailing
                        )
                        if archive_support >= RETURN_SUPPORT_EVENTS:
                            state = "archive"
                            recent_since = None
                            transitions.append({"index": i, "source": "archive"})
        if state == "archive":
            source = "archive"
            used = ANCHOR
            model = anchor
        else:
            since = len(self.events) - recent_since
            used = (LONG_HORIZON if since >= LONG_AFTER_RECENT
                    else SHORT_HORIZON)
            source = "recent32" if used == LONG_HORIZON else "recent8"
            model = self._model(self.events[-used:])
        decision = {
            "source": source,
            "trained_events": len(self.events),
            "selected_horizon": used,
            "inferred_transitions": transitions,
            "entry_unexpected_last_evaluation": entry_count,
            "last_archive_support": archive_support,
            "recent_model_overlap_with_gate": used if state == "recent" else 0,
        }
        self._cached_selection = (decision, model)
        return self._cached_selection

    def record(self):
        if not self.events:
            raise ValueError("no public outcomes to save")
        state = {"schema": SCHEMA, "events": self.events}
        return {"state": json.loads(canonical(state)), "sha256": digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or
                set(record) != {"state", "sha256"} or
                type(record["state"]) is not dict or
                type(record["sha256"]) is not str or
                digest(record["state"]) != record["sha256"]):
            raise ValueError("invalid contrast model checksum")
        state = record["state"]
        if (set(state) != {"schema", "events"} or state["schema"] != SCHEMA
                or type(state["events"]) is not list
                or not 1 <= len(state["events"]) <= MAX_SAMPLES):
            raise ValueError("invalid contrast model checkpoint structure")
        model = cls()
        for event in state["events"]:
            model.observe(event)
        if model.record() != record:
            raise ValueError("cannot exactly replay contrastive evidence")
        return model
