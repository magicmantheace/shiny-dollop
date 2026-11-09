"""A bounded learned one-slot memory gate, trained from delayed outcome feedback.

This is a contextual-bandit toy, *not* learned general memory or an RNN. The
simulator hides which source matters; only a context bit, signal channels and
symbols are visible. A learned gate must decide which observed signal to keep.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sqlite3
from pathlib import Path

SCHEMA = "selective-memory-v1"
MODES = ("learned", "first", "last", "random", "oracle")
BANDS = {"short": (2, 6), "long": (10, 20)}
CHANNELS = ("A", "B", "N")
PERMUTATION = (2, 0, 3, 1)  # Unknown to all learned policies.


def canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


def episode_seed(seed: int, split: str, index: int, band: str) -> int:
    if type(seed) is not int or split not in ("train", "test") or type(index) is not int or index < 0 or band not in BANDS:
        raise ValueError("invalid episode namespace")
    return int.from_bytes(hashlib.sha256(
        f"developmental-ai/{SCHEMA}/{seed}/{split}/{index}/{band}".encode()
    ).digest()[:8], "big")


class SignalTrial:
    """One hidden-target event, one competing event, and random distractors."""

    def __init__(self, seed: int, band: str = "short"):
        if type(seed) is not int or band not in BANDS:
            raise ValueError("invalid trial")
        rng = random.Random(seed)
        self.context = rng.randrange(2)
        correct_channel = "A" if self.context == 0 else "B"
        self.correct_symbol = rng.randrange(4)
        self.correct_action = PERMUTATION[self.correct_symbol]
        count = rng.randint(*BANDS[band])
        signals = [("A", self.correct_symbol if correct_channel == "A" else rng.randrange(4)),
                   ("B", self.correct_symbol if correct_channel == "B" else rng.randrange(4))]
        signals += [("N", rng.randrange(4)) for _ in range(count)]
        rng.shuffle(signals)
        self.signals = tuple(signals)

    def observations(self):
        return [{"kind": "context", "value": self.context}] + [
            {"kind": "signal", "channel": ch, "symbol": sym}
            for ch, sym in self.signals
        ] + [{"kind": "decision"}]


class SelectiveBrain:
    """SQLite checkpoint with two learned tables: source value and response Q."""

    def __init__(self, db: Path, seed: int, mode: str = "learned"):
        if type(seed) is not int or mode not in MODES:
            raise ValueError("invalid seed or mode")
        db.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db)
        try:
            with self.conn:
                self.conn.execute("CREATE TABLE IF NOT EXISTS select_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                self.conn.execute("CREATE TABLE IF NOT EXISTS select_gate (context INTEGER NOT NULL, channel TEXT NOT NULL, value REAL NOT NULL, PRIMARY KEY(context, channel))")
                self.conn.execute("CREATE TABLE IF NOT EXISTS select_q (context INTEGER NOT NULL, channel TEXT NOT NULL, symbol INTEGER NOT NULL, action INTEGER NOT NULL, value REAL NOT NULL, PRIMARY KEY(context,channel,symbol,action))")
            meta = dict(self.conn.execute("SELECT key,value FROM select_meta"))
            if meta and (meta.get("schema") != SCHEMA or meta.get("seed") != str(seed) or meta.get("mode") != mode):
                raise ValueError("incompatible checkpoint")
            self.seed, self.mode = seed, mode
            self.trained = int(meta.get("trained", "0"))
            if self.trained < 0:
                raise ValueError("invalid training count")
            self.gate = {(c, ch): float(v) for c, ch, v in self.conn.execute("SELECT context,channel,value FROM select_gate")}
            self.q = {(c, ch, sym, a): float(v) for c, ch, sym, a, v in self.conn.execute("SELECT context,channel,symbol,action,value FROM select_q")}
            if any(c not in (0, 1) or ch not in CHANNELS or not math.isfinite(v)
                   for (c, ch), v in self.gate.items()):
                raise ValueError("invalid stored gate")
            if any(c not in (0, 1) or ch not in CHANNELS or sym not in range(4)
                   or a not in range(4) or not math.isfinite(v)
                   for (c, ch, sym, a), v in self.q.items()):
                raise ValueError("invalid stored action table")
        except Exception:
            self.conn.close()
            raise

    def _choose_signal(self, context: int, held: tuple[str, int] | None,
                       candidate: tuple[str, int], rng: random.Random, epsilon: float) -> tuple[str, int]:
        if held is None:
            return candidate
        if self.mode == "first":
            return held
        if self.mode == "last":
            return candidate
        if self.mode == "random":
            return candidate if rng.randrange(2) else held
        if self.mode == "oracle":
            required = "A" if context == 0 else "B"
            return candidate if candidate[0] == required else held
        # Explicit gate decision, with online exploration. No fixed cue/phase rule.
        if rng.random() < epsilon:
            return candidate if rng.randrange(2) else held
        old_v = self.gate.get((context, held[0]), 0.0)
        new_v = self.gate.get((context, candidate[0]), 0.0)
        return candidate if new_v > old_v else held

    def _choose_action(self, context: int, held: tuple[str, int], rng: random.Random, epsilon: float) -> int:
        if self.mode == "oracle":
            return PERMUTATION[held[1]]
        if rng.random() < epsilon:
            return rng.randrange(4)
        vals = [self.q.get((context, held[0], held[1], a), 0.0) for a in range(4)]
        best = max(vals)
        return rng.choice([a for a, val in enumerate(vals) if val == best])

    def trial(self, split: str, index: int, band: str = "short", learn: bool = False,
              epsilon: float = 0.0, trace: bool = False) -> dict:
        if not 0 <= epsilon <= 1 or type(index) is not int or index < 0:
            raise ValueError("invalid trial options")
        if learn and (split != "train" or band != "short" or index != self.trained):
            raise ValueError("training must use next train/short index")
        sample = episode_seed(self.seed, split, index, band)
        trial = SignalTrial(sample, band)
        rng = random.Random(episode_seed(self.seed + 1, split, index, band))
        held = None
        steps = []
        for obs in trial.observations():
            if obs["kind"] == "context":
                if trace:
                    steps.append({"observation": obs, "memory": None, "operation": "context"})
            elif obs["kind"] == "signal":
                candidate = (obs["channel"], obs["symbol"])
                old = held
                held = self._choose_signal(trial.context, held, candidate, rng, epsilon)
                if trace:
                    steps.append({"observation": obs, "memory": list(held),
                                  "operation": "write" if held is candidate else "keep"})
            else:
                assert held is not None
                action = self._choose_action(trial.context, held, rng, epsilon)
                if trace:
                    steps.append({"observation": obs, "memory": list(held), "operation": "choose", "action": action})
        correct = action == trial.correct_action
        if learn:
            reward = 1.0 if correct else 0.0
            gate_key = (trial.context, held[0])
            old = self.gate.get(gate_key, 0.25)
            self.gate[gate_key] = old + 0.07 * (reward - old)
            key = (trial.context, held[0], held[1], action)
            old_q = self.q.get(key, 0.0)
            self.q[key] = old_q + 0.2 * ((1.0 if correct else -1.0) - old_q)
            self.trained += 1
        return {"correct": bool(correct), "chosen_channel": held[0], "steps": len(trial.signals),
                "events": steps if trace else []}

    def train(self, episodes: int) -> None:
        if type(episodes) is not int or episodes < 1:
            raise ValueError("positive integer episodes required")
        for _ in range(episodes):
            i = self.trained
            epsilon = max(0.08, 0.7 * (0.9994 ** i))
            self.trial("train", i, learn=True, epsilon=epsilon)
        self.persist()

    def evaluate(self, episodes: int = 400, band: str = "long", split: str = "test") -> dict:
        if type(episodes) is not int or episodes < 1 or split not in ("train", "test") or band not in BANDS:
            raise ValueError("invalid evaluation")
        total = 0
        correct_selection = 0
        for i in range(episodes):
            out = self.trial(split, i, band)
            total += out["correct"]
            arena = SignalTrial(episode_seed(self.seed, split, i, band), band)
            correct_selection += (out["chosen_channel"] == ("A" if arena.context == 0 else "B"))
        return {"schema": SCHEMA, "seed": self.seed, "mode": self.mode,
                "trained": self.trained, "band": band, "split": split, "episodes": episodes,
                "accuracy": round(total / episodes, 4),
                "target_retention": round(correct_selection / episodes, 4)}

    def persist(self):
        with self.conn:
            self.conn.execute("DELETE FROM select_gate")
            self.conn.execute("DELETE FROM select_q")
            self.conn.executemany("INSERT INTO select_gate VALUES(?,?,?)",
                                  ((c, ch, v) for (c, ch), v in self.gate.items()))
            self.conn.executemany("INSERT INTO select_q VALUES(?,?,?,?,?)",
                                  ((c, ch, s, a, v) for (c, ch, s, a), v in self.q.items()))
            self.conn.executemany("INSERT INTO select_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                                  (("schema", SCHEMA), ("seed", str(self.seed)), ("mode", self.mode), ("trained", str(self.trained))))

    def trace(self, index: int = 0, band: str = "long", split: str = "test") -> dict:
        out = self.trial(split, index, band, trace=True)
        body = {"schema": "developmental-ai.selection-trace/v1", "seed": self.seed,
                "split": split, "index": index, "band": band, "mode": self.mode,
                "source": "simulation", "scope": "simulation-only", "outcome": out}
        return {**body, "sha256": hashlib.sha256(canonical(body).encode()).hexdigest()}

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def verify_trace(data: dict) -> dict:
    """Validate environmental observations and transitions (not learned policy provenance)."""
    try:
        if type(data) is not dict or data.get("schema") != "developmental-ai.selection-trace/v1" or data.get("source") != "simulation" or data.get("scope") != "simulation-only" or data.get("mode") not in MODES:
            raise ValueError("invalid trace identity")
        body = {k: v for k, v in data.items() if k != "sha256"}
        digest = hashlib.sha256(canonical(body).encode()).hexdigest()
        if digest != data.get("sha256"):
            raise ValueError("checksum mismatch")
        trial = SignalTrial(episode_seed(data["seed"], data["split"], data["index"], data["band"]), data["band"])
        events = data["outcome"]["events"]
        if len(events) != len(trial.observations()):
            raise ValueError("wrong event count")
        held = None
        for event, obs in zip(events, trial.observations()):
            if event["observation"] != obs:
                raise ValueError("observation mismatch")
            operation = event["operation"]
            if obs["kind"] == "context":
                if operation != "context" or event["memory"] is not None:
                    raise ValueError("context mismatch")
            elif obs["kind"] == "signal":
                candidate = [obs["channel"], obs["symbol"]]
                if operation == "write":
                    held = candidate
                elif operation != "keep" or held is None:
                    raise ValueError("illegal memory operation")
                if event["memory"] != held:
                    raise ValueError("memory mismatch")
            else:
                if operation != "choose" or event["memory"] != held or held is None or type(event["action"]) is not int or event["action"] not in range(4):
                    raise ValueError("invalid decision")
        decision = events[-1]["action"]
        result = data["outcome"]
        if (result["correct"] != (decision == trial.correct_action)
                or result["chosen_channel"] != held[0] or result["steps"] != len(trial.signals)):
            raise ValueError("outcome mismatch")
        return {"verified": True, "sha256": digest, "steps": len(events)}
    except (KeyError, TypeError, IndexError, OverflowError) as exc:
        raise ValueError("malformed trace") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("train", "evaluate", "trace", "verify"))
    parser.add_argument("--db", type=Path, default=Path("selection.db"))
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--mode", choices=MODES, default="learned")
    parser.add_argument("--episodes", type=int, default=5000)
    parser.add_argument("--band", choices=tuple(BANDS), default="long")
    parser.add_argument("--split", choices=("train", "test"), default="test")
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--trace-file", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "verify":
            if not args.trace_file:
                parser.error("--trace-file required")
            print(json.dumps(verify_trace(json.loads(args.trace_file.read_text(encoding="utf-8"))), indent=2))
            return
        with SelectiveBrain(args.db, args.seed, args.mode) as brain:
            if args.command == "train":
                brain.train(args.episodes)
                print(json.dumps({"trained": brain.trained, "mode": brain.mode}, indent=2))
            elif args.command == "evaluate":
                print(json.dumps(brain.evaluate(args.episodes, args.band, args.split), indent=2))
            else:
                print(json.dumps(brain.trace(args.index, args.band, args.split), indent=2))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
