"""Bounded simulation-only controller joining discovered models to navigation.

A frozen MixedProposal supplies observation-learned models; a separately
calibrated, bank-bound receipt supplies the per-step switching hazard. The
controller only consumes a start beacon, its own actions, ordinary odometry,
and landmark readings. It never observes the actual position, regime, reward,
model training labels, or simulator state and cannot execute external actions.

This is experimental *model reuse*, not online model discovery or deployment.
"""
from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path

from developmental_ai.adaptive_dynamics import canonical
from developmental_ai.mixed_experience import MixedProposal
from developmental_ai.switching_belief import (
    SwitchingBelief, _bank, _digest, verified_hazard,
)

SCHEMA = "closed-loop-adaptation/v1"
MAX_LOG = 55  # ring-world episodes are at most 11*5 steps


def models_from_proposal(proposal):
    if not isinstance(proposal, MixedProposal):
        raise ValueError("expected observation-learned, frozen proposal")
    return {"h%d" % i: copy.deepcopy(model) for i, model in enumerate(proposal.models)}


class NavigationSession:
    """An inspectable action *suggestion* loop with no simulator privileges.

    select_action() returns only a bounded ring action and locks it pending a
    matching advance(). No goal/permission/memory promotion is inferred from
    a high model posterior. A simulated outcome may end a session; outcomes are
    not used to update the fitted models or change the switching prior.
    """

    def __init__(self, proposal, initial, goal, n, receipt=None, *, mode="switching"):
        if mode not in ("switching", "static"):
            raise ValueError("invalid control mode")
        models = models_from_proposal(proposal)
        if mode == "switching":
            if receipt is None:
                raise ValueError("switching requires an independently calibrated receipt")
            hazard = verified_hazard(receipt, models)
        else:
            hazard = 0.0
        self.proposal_digest = _digest(proposal.record())
        self.receipt_digest = _digest(receipt) if mode == "switching" else None
        self.mode = mode
        self.nav = SwitchingBelief(initial, goal, n, models, hazard=hazard)
        self.pending = None
        self.finished = False
        self.log = []

    def select_action(self):
        if self.finished or len(self.log) >= MAX_LOG:
            raise ValueError("session finished or budget exhausted")
        if _bank(self.nav.models) != self.nav.fingerprints:
            raise ValueError("learned model mutated during session")
        if self.pending is None:
            self.pending = self.nav.heuristic()
        return self.pending

    def advance(self, action, observation, *, done=False):
        if (self.finished or self.pending is None or type(action) is not int or
                action != self.pending or type(done) is not bool or len(self.log) >= MAX_LOG):
            raise ValueError("unrequested, mismatched or exhausted action")
        if _bank(self.nav.models) != self.nav.fingerprints:
            raise ValueError("learned model mutated during session")
        # Pass the strictly ordinary sensor record to the existing validator.
        log_likelihood = self.nav.advance(action, observation)
        self.log.append({"action": action, "observation": dict(observation), "done": done})
        self.pending = None
        self.finished = done or len(self.log) == MAX_LOG
        return {"log_likelihood": log_likelihood, "position_belief": list(self.nav.probs),
                "model_weights": dict(self.nav.weights), "model_selected": self.nav.selected(),
                "finished": self.finished}

    def snapshot(self):
        state = {"schema": SCHEMA, "mode": self.mode, "proposal_digest": self.proposal_digest,
                 "receipt_digest": self.receipt_digest, "navigator": self.nav.snapshot(),
                 "log": self.log, "pending": self.pending, "finished": self.finished}
        return {"state": state, "sha256": _digest(state)}

    @classmethod
    def restore(cls, record, proposal, receipt=None):
        if (type(record) is not dict or set(record) != {"state", "sha256"} or
                type(record["state"]) is not dict or type(record["sha256"]) is not str or
                _digest(record["state"]) != record["sha256"]):
            raise ValueError("invalid or altered session snapshot")
        state = record["state"]
        if set(state) != {"schema", "mode", "proposal_digest", "receipt_digest", "navigator", "log", "pending", "finished"} or state["schema"] != SCHEMA:
            raise ValueError("invalid session schema")
        b = state["navigator"]
        if type(b) is not dict or type(b.get("state")) is not dict:
            raise ValueError("invalid nested navigator")
        ns = b["state"]
        try:
            rebuilt = cls(proposal, ns["initial"], ns["goal"], ns["n"], receipt, mode=state["mode"])
        except (TypeError, KeyError) as exc:
            raise ValueError("invalid checkpoint configuration") from exc
        if (rebuilt.proposal_digest != state["proposal_digest"] or
                rebuilt.receipt_digest != state["receipt_digest"] or
                type(state["log"]) is not list or len(state["log"]) > MAX_LOG or
                type(state["finished"]) is not bool or
                (state["pending"] is not None and (type(state["pending"]) is not int or state["pending"] not in (0, 1, 2)))):
            raise ValueError("checkpoint source or control state mismatch")
        # Replay the entire bounded *ordinary-sensor* history; do not trust a
        # recomputed checksum, a forged final posterior or a forged pending act.
        for event in state["log"]:
            if (type(event) is not dict or set(event) != {"action", "observation", "done"} or
                    rebuilt.finished or event["action"] != rebuilt.select_action()):
                raise ValueError("inconsistent saved action history")
            rebuilt.advance(event["action"], event["observation"], done=event["done"])
        if state["pending"] is not None:
            if rebuilt.select_action() != state["pending"]:
                raise ValueError("invalid pending action")
        if (rebuilt.finished != state["finished"] or
                canonical(rebuilt.nav.snapshot()) != canonical(state["navigator"])):
            raise ValueError("saved posterior does not match replayed observations")
        return rebuilt


class NavigationCheckpoint:
    """One local, versioned SQLite session; checksum is not authentication."""

    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS adaptation_state (id INTEGER PRIMARY KEY CHECK(id=1), record TEXT NOT NULL)")

    def save(self, session):
        if not isinstance(session, NavigationSession):
            raise ValueError("invalid navigation session")
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO adaptation_state VALUES (1,?)", (canonical(session.snapshot()),))

    def load(self, proposal, receipt=None):
        row = self.db.execute("SELECT record FROM adaptation_state WHERE id=1").fetchone()
        if row is None:
            return None
        try:
            return NavigationSession.restore(json.loads(row[0]), proposal, receipt)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid session record") from exc

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
