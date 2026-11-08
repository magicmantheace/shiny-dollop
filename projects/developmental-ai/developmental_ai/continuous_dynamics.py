"""Restart-safe, simulation-only observation-driven model switching.

A bounded sequence of ordinary action/odometry/landmark histories is scored
against *previously trained immutable* dynamics models. Regime names, true
positions and simulator physics are never observed by this monitor. A recent
likelihood margin and repeated confirmations govern switching; large misses
raise a review-only anomaly. No new model is learned or installed automatically.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from pathlib import Path

from developmental_ai.adaptive_dynamics import canonical
from developmental_ai.online_dynamics import ModelBank, SCHEMA as MODEL_SCHEMA, score, trajectory, validate_history

SCHEMA = "continuous-dynamics/v1"
MAX_WINDOW = 16
MAX_HISTORY = 500
MAX_ROWS = 64


def _hash(data):
    return hashlib.sha256(canonical(data).encode("utf-8")).hexdigest()


def catalogue(bank):
    """Validated immutable list and fingerprint of models in a bank."""
    rows = bank.conn.execute("SELECT name, digest FROM online_models ORDER BY name").fetchall()
    if not rows or len(rows) > 16:
        raise ValueError("model bank size must be 1..16")
    models = {}
    for name, _ in rows:
        models[name] = bank.get(name)  # enforces seed, schema, integrity
    bindings = [(name, _hash(model.counts)) for name, model in models.items()]
    return models, _hash({"model_schema": MODEL_SCHEMA, "seed": bank.seed, "models": bindings})


class StreamMonitor:
    """One SQLite transaction per observed (partial-world) episode.

    The monitor never reads simulator regime labels. The caller generates
    ordinary observation histories and supplies them one at a time.
    """
    def __init__(self, db, bank: ModelBank, *, window=4, confirmations=2,
                 margin=.12, floor=-4.0):
        if type(window) is not int or not 2 <= window <= MAX_WINDOW:
            raise ValueError("invalid window")
        if type(confirmations) is not int or not 1 <= confirmations <= 8:
            raise ValueError("invalid confirmations")
        if type(margin) not in (int, float) or not math.isfinite(margin) or margin < 0:
            raise ValueError("invalid margin")
        if type(floor) not in (int, float) or not math.isfinite(floor) or floor > 0:
            raise ValueError("invalid anomaly floor")
        self.models, self.fingerprint = catalogue(bank)
        self.seed = bank.seed
        self.config = {"window": window, "confirmations": confirmations,
                       "margin": float(margin), "floor": float(floor)}
        path = Path(db)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        try:
            self.conn.execute("CREATE TABLE IF NOT EXISTS continuous_state "
                              "(id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL, digest TEXT NOT NULL)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS continuous_events "
                              "(seq INTEGER PRIMARY KEY, body TEXT NOT NULL, digest TEXT NOT NULL)")
            row = self.conn.execute("SELECT body, digest FROM continuous_state WHERE id=1").fetchone()
            if row is None:
                self.state = self._fresh()
            else:
                body, digest = row
                if _hash(json.loads(body)) != digest:
                    raise ValueError("tampered monitor checkpoint")
                self.state = json.loads(body)
                self._check_state()
        except Exception:
            self.conn.close()
            raise

    def _fresh(self):
        return {"schema": SCHEMA, "seed": self.seed, "catalogue": self.fingerprint,
                "config": self.config, "seq": 0, "active": None,
                "pending": None, "streak": 0, "window": [], "last_status": "warming", "last_event_digest": None}

    def _check_state(self):
        state = self.state
        if (type(state) is not dict or set(state) != set(self._fresh()) or
            state["schema"] != SCHEMA or state["seed"] != self.seed or
            state["catalogue"] != self.fingerprint or state["config"] != self.config):
            raise ValueError("incompatible model bank or monitor configuration")
        if (type(state["seq"]) is not int or not 0 <= state["seq"] <= MAX_HISTORY or
            type(state["streak"]) is not int or not 0 <= state["streak"] <= self.config["confirmations"] or
            state["active"] not in (None, *self.models) or
            state["pending"] not in (None, *self.models, "unknown") or
            state["last_status"] not in ("warming", "stable", "switch", "unknown", "uncertain") or
            (state["seq"] == 0 and state["last_event_digest"] is not None) or
            (state["seq"] > 0 and (type(state["last_event_digest"]) is not str or len(state["last_event_digest"]) != 64))):
            raise ValueError("malformed monitor checkpoint")
        win = state["window"]
        if type(win) is not list or len(win) > self.config["window"]:
            raise ValueError("invalid monitor window")
        for history in win:
            validate_history(history)
        if state["seq"]:
            row = self.conn.execute("SELECT body, digest FROM continuous_events WHERE seq=?", (state["seq"],)).fetchone()
            if row is None or row[1] != state["last_event_digest"] or _hash(json.loads(row[0])) != row[1]:
                raise ValueError("missing or invalid monitor tail event")

    def observe(self, history):
        validate_history(history)
        if self.state["seq"] >= MAX_HISTORY:
            raise ValueError("monitor history limit reached; archive and start a new session")
        next_state = json.loads(canonical(self.state))
        next_state["seq"] += 1
        recent = (next_state["window"] + [history])[-self.config["window"]:]
        next_state["window"] = recent
        totals = {name: score(model, recent) for name, model in self.models.items()}
        ordered = sorted(totals, key=lambda name: (-totals[name], name))
        winner = ordered[0]
        runner = totals[ordered[1]] if len(ordered) > 1 else float("-inf")
        separated = totals[winner] - runner >= self.config["margin"]
        sufficient = len(recent) >= self.config["window"]
        proposed = "unknown" if totals[winner] < self.config["floor"] else (winner if separated else None)
        status = "warming" if not sufficient else "uncertain"
        if sufficient and proposed is not None:
            if proposed == next_state["pending"]:
                next_state["streak"] = min(self.config["confirmations"], next_state["streak"] + 1)
            else:
                next_state["pending"], next_state["streak"] = proposed, 1
            if next_state["streak"] >= self.config["confirmations"]:
                if proposed == "unknown":
                    status = "unknown"
                elif proposed != next_state["active"]:
                    next_state["active"] = proposed
                    status = "switch"
                else:
                    status = "stable"
        else:
            next_state["pending"], next_state["streak"] = None, 0
        next_state["last_status"] = status
        event = {"schema": SCHEMA, "seq": next_state["seq"], "selected": next_state["active"],
                 "status": status, "candidate": proposed if sufficient else None,
                 "previous_event_digest": self.state["last_event_digest"],
                 "scores": {k: round(v, 6) for k, v in sorted(totals.items())},
                 "window_size": len(recent), "scope": "simulation-only"}
        next_state["last_event_digest"] = _hash(event)
        # The state and event commit atomically: a crash cannot advance only one.
        with self.conn:
            self.conn.execute("INSERT INTO continuous_events VALUES(?,?,?)",
                              (event["seq"], canonical(event), _hash(event)))
            self.conn.execute("INSERT OR REPLACE INTO continuous_state VALUES(1,?,?)",
                              (canonical(next_state), _hash(next_state)))
        self.state = next_state
        return event

    def events(self):
        rows = self.conn.execute("SELECT seq, body, digest FROM continuous_events ORDER BY seq").fetchall()
        previous = None
        for index, (seq, body, digest) in enumerate(rows, start=1):
            record = json.loads(body)
            if (seq != index or _hash(record) != digest or
                record.get("previous_event_digest") != previous or record.get("seq") != seq):
                raise ValueError("corrupt monitor event ledger")
            previous = digest
        if len(rows) != self.state["seq"] or previous != self.state["last_event_digest"]:
            raise ValueError("event/state mismatch")
        if rows and json.loads(rows[-1][1])["selected"] != self.state["active"]:
            raise ValueError("event/state mismatch")
        return [json.loads(row[1]) for row in rows]

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--models-db", type=Path, required=True)
    p.add_argument("--monitor-db", type=Path, required=True)
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--episodes", type=int, default=20)
    p.add_argument("--start-index", type=int, default=6000)
    p.add_argument("--noise", choices=("standard", "high"), default="standard")
    p.add_argument("--layout", choices=("fixed", "shifted"), default="fixed")
    args = p.parse_args()
    if args.episodes < 1 or args.episodes > MAX_HISTORY or args.start_index < 0:
        p.error("invalid episodes or start-index")
    with ModelBank(args.models_db, args.seed) as bank, StreamMonitor(args.monitor_db, bank) as monitor:
        for i in range(args.start_index, args.start_index + args.episodes):
            event = monitor.observe(trajectory(args.seed, "test", i, args.noise, args.layout))
            print(canonical(event))


if __name__ == "__main__":
    main()
