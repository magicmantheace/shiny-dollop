"""A toy delayed-cue association with explicit, inspectable working-memory ablations.

The initial signal disappears before a decision; distractor signals occur in between.
An engineered memory gate retains the initial signal, while tabular Q-learning learns
which of four buttons it predicts. This tests memory *use*, not learned attention,
recurrent representations, language, agency, or a biological nervous system.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = "delayed-choice-v1"
MODES = ("retain", "reactive", "overwrite")
BANDS = {"short": (2, 6), "long": (10, 20)}
ACTIONS = 4
# An association to discover from feedback, not an action exposed in observations.
HIDDEN_ASSOCIATION = (2, 0, 3, 1)


def _json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False)


def episode_seed(seed: int, split: str, index: int, band: str) -> int:
    if type(seed) is not int or split not in ("train", "test") or type(index) is not int or index < 0 or band not in BANDS:
        raise ValueError("invalid episode namespace")
    data = f"developmental-ai/{SCHEMA}/{seed}/{split}/{band}/{index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(data).digest()[:8], "big")


class DelayArena:
    """A deterministic simulated trial; actions cannot operate outside this arena."""

    def __init__(self, seed: int, band: str = "short"):
        if band not in BANDS:
            raise ValueError("invalid delay band")
        rng = random.Random(seed)
        self.cue = rng.randrange(ACTIONS)
        self.correct_action = HIDDEN_ASSOCIATION[self.cue]
        self.delay = rng.randint(*BANDS[band])
        self.noise = [rng.randrange(ACTIONS) for _ in range(self.delay)]
        self.cursor = 0
        self.done = False
        self.reward_total = 0.0
        self.correct = False

    def observe(self) -> dict:
        if self.cursor == 0:
            return {"phase": "cue", "token": self.cue}
        if self.cursor <= self.delay:
            return {"phase": "distractor", "token": self.noise[self.cursor - 1]}
        if not self.done:
            return {"phase": "decision", "token": None}
        return {"phase": "finished", "token": None}

    def step(self, action: int) -> tuple[dict, float, bool, str]:
        if self.done:
            raise RuntimeError("cannot advance finished trial")
        if type(action) is not int:
            raise ValueError("action must be an integer")
        if self.cursor <= self.delay:
            if action != ACTIONS:
                raise ValueError("only continue permitted before decision")
            self.cursor += 1
            event, reward = "advanced", -0.01
        else:
            if not 0 <= action < ACTIONS:
                raise ValueError("invalid choice")
            self.correct = action == self.correct_action
            self.done = True
            self.cursor += 1
            event, reward = ("correct", 1.0) if self.correct else ("incorrect", -1.0)
        self.reward_total += reward
        return self.observe(), reward, self.done, event


class WorkingMemory:
    """An explicit baseline memory gate, *not* a learned or general memory model."""

    def __init__(self, mode: str):
        if mode not in MODES:
            raise ValueError("invalid memory mode")
        self.mode = mode
        self.token: int | None = None

    def observe(self, observation: dict) -> None:
        if self.mode == "reactive":
            self.token = observation["token"]
        elif self.mode == "overwrite":
            if observation["token"] is not None:
                self.token = observation["token"]
        elif observation["phase"] == "cue":
            self.token = observation["token"]

    def recall(self) -> int | None:
        return self.token


def run_trial(arena: DelayArena, mode: str, rng: random.Random,
              brain: "DelayBrain | None" = None, learn: bool = False,
              epsilon: float = 0.0, trace: bool = False) -> tuple[dict, list[dict]]:
    if learn and brain is None:
        raise ValueError("training needs a brain")
    memory = WorkingMemory(mode)
    events: list[dict] = []
    choice_memory: int | None = None
    while not arena.done:
        before = arena.observe()
        memory.observe(before)
        if before["phase"] == "decision":
            choice_memory = memory.recall()
            action = brain.choose(choice_memory, rng, epsilon) if brain is not None else rng.randrange(ACTIONS)
        else:
            action = ACTIONS  # Waiting/advancing is automatic; only final choice is learned.
        after, reward, done, event = arena.step(action)
        if trace:
            events.append({"before": before, "action": action, "after": after,
                           "reward": reward, "done": done, "event": event})
    if learn:
        assert brain is not None
        brain.update(choice_memory, action, 1.0 if arena.correct else -1.0)
    return ({"correct": arena.correct, "steps": arena.cursor,
             "reward": round(arena.reward_total, 8), "mode": mode}, events)


class DelayBrain:
    """Seed/mode/version-bound durable tabular association learner."""

    def __init__(self, database: Path, seed: int, mode: str = "retain"):
        if type(seed) is not int or mode not in MODES:
            raise ValueError("invalid seed/memory mode")
        database.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(database)
        try:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS delay_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS delay_q (
                    remembered INTEGER NOT NULL, action INTEGER NOT NULL, value REAL NOT NULL,
                    PRIMARY KEY (remembered, action));
            """)
            meta = dict(self.conn.execute("SELECT key,value FROM delay_meta"))
            if meta and (meta.get("schema") != SCHEMA or meta.get("seed") != str(seed)
                         or meta.get("mode") != mode):
                raise ValueError("incompatible checkpoint; refuse to resume")
            self.seed, self.mode = seed, mode
            self.trained = int(meta.get("trained", 0))
            self.q = {(None if k == -1 else k, a): value for k, a, value
                      in self.conn.execute("SELECT remembered,action,value FROM delay_q")}
            if any(a not in range(ACTIONS) or (k is not None and k not in range(ACTIONS)) or
                   not math.isfinite(v) for (k, a), v in self.q.items()):
                raise ValueError("invalid stored policy")
        except Exception:
            self.conn.close()
            raise

    def choose(self, remembered: int | None, rng: random.Random, epsilon: float = 0) -> int:
        if not 0 <= epsilon <= 1:
            raise ValueError("invalid exploration probability")
        if rng.random() < epsilon:
            return rng.randrange(ACTIONS)
        values = [self.q.get((remembered, a), 0.0) for a in range(ACTIONS)]
        top = max(values)
        return rng.choice([a for a, v in enumerate(values) if v == top])

    def update(self, remembered: int | None, action: int, reward: float) -> None:
        old = self.q.get((remembered, action), 0.0)
        self.q[(remembered, action)] = old + 0.16 * (reward - old)

    def persist(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM delay_q")
            self.conn.executemany("INSERT INTO delay_q VALUES(?,?,?)",
                                  ((-1 if k is None else k, a, v) for (k, a), v in self.q.items()))
            self.conn.executemany("INSERT INTO delay_meta(key,value) VALUES(?,?) "
                                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                                  (("schema", SCHEMA), ("seed", str(self.seed)),
                                   ("mode", self.mode), ("trained", str(self.trained))))

    def train(self, episodes: int) -> None:
        if type(episodes) is not int or episodes < 1:
            raise ValueError("training episodes must be positive")
        for _ in range(episodes):
            i = self.trained
            arena = DelayArena(episode_seed(self.seed, "train", i, "short"))
            rng = random.Random(episode_seed(self.seed + 1, "train", i, "short"))
            epsilon = max(0.035, 0.5 * 0.997 ** i)
            run_trial(arena, self.mode, rng, self, learn=True, epsilon=epsilon)
            self.trained += 1
        self.persist()

    def evaluate(self, episodes: int = 400, band: str = "long", split: str = "test") -> dict:
        if type(episodes) is not int or episodes < 1 or band not in BANDS or split not in ("train", "test"):
            raise ValueError("invalid evaluation request")
        correct = 0
        for i in range(episodes):
            arena = DelayArena(episode_seed(self.seed, split, i, band), band)
            rng = random.Random(episode_seed(self.seed + 2, split, i, band))
            outcome, _ = run_trial(arena, self.mode, rng, self)
            correct += outcome["correct"]
        return {"schema": SCHEMA, "seed": self.seed, "memory_mode": self.mode,
                "trained_episodes": self.trained, "split": split, "delay_band": band,
                "episodes": episodes, "success_rate": round(correct / episodes, 4)}

    def trace(self, index: int, band: str = "long", split: str = "test") -> dict:
        seed = episode_seed(self.seed, split, index, band)
        rng = random.Random(episode_seed(self.seed + 2, split, index, band))
        outcome, events = run_trial(DelayArena(seed, band), self.mode, rng, self, trace=True)
        body = {"schema": "developmental-ai.delay-trace/v1", "source": "simulation",
                "scope": "simulation-only", "seed": self.seed, "split": split,
                "index": index, "band": band, "mode": self.mode,
                "outcome": outcome, "events": events}
        return {**body, "sha256": hashlib.sha256(_json(body).encode()).hexdigest()}

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "DelayBrain":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def verify_trace(trace: dict) -> dict:
    """Recompute deterministic transitions, not trust a user-supplied checksum."""
    try:
        if (type(trace) is not dict or trace.get("schema") != "developmental-ai.delay-trace/v1"
                or trace.get("source") != "simulation" or trace.get("scope") != "simulation-only"
                or trace.get("mode") not in MODES):
            raise ValueError("invalid trace identity")
        payload = {k: v for k, v in trace.items() if k != "sha256"}
        digest = hashlib.sha256(_json(payload).encode()).hexdigest()
        if digest != trace.get("sha256"):
            raise ValueError("checksum mismatch")
        arena = DelayArena(episode_seed(trace["seed"], trace["split"], trace["index"], trace["band"]), trace["band"])
        memory = WorkingMemory(trace["mode"])
        if not isinstance(trace["events"], list) or len(trace["events"]) != arena.delay + 2:
            raise ValueError("event count mismatch")
        for event in trace["events"]:
            before = arena.observe()
            if event["before"] != before:
                raise ValueError("observation mismatch")
            memory.observe(before)
            if before["phase"] == "decision":
                if not 0 <= event["action"] < ACTIONS:
                    raise ValueError("invalid final choice")
            else:
                if event["action"] != ACTIONS:
                    raise ValueError("invalid advance action")
            after, reward, done, label = arena.step(event["action"])
            if (event["after"] != after or event["reward"] != reward or
                    event["done"] != done or event["event"] != label):
                raise ValueError("transition mismatch")
        outcome = {"correct": arena.correct, "steps": arena.cursor,
                   "reward": round(arena.reward_total, 8), "mode": trace["mode"]}
        if not arena.done or trace["outcome"] != outcome:
            raise ValueError("outcome mismatch")
        return {"verified": True, "steps": arena.cursor, "sha256": digest}
    except (KeyError, TypeError, IndexError, OverflowError) as exc:
        raise ValueError("malformed trace") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("train", "evaluate", "trace", "verify"))
    parser.add_argument("--db", type=Path, default=Path("delayed_brain.db"))
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--episodes", type=int, default=800)
    parser.add_argument("--mode", choices=MODES, default="retain")
    parser.add_argument("--band", choices=tuple(BANDS), default="long")
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--split", choices=("train", "test"), default="test")
    parser.add_argument("--trace-file", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "verify":
            if args.trace_file is None:
                parser.error("verify requires --trace-file")
            print(json.dumps(verify_trace(json.loads(args.trace_file.read_text(encoding="utf-8"))), indent=2))
            return
        with DelayBrain(args.db, args.seed, args.mode) as brain:
            if args.command == "train":
                brain.train(args.episodes)
                print(json.dumps({"trained_episodes": brain.trained, "mode": brain.mode}))
            elif args.command == "evaluate":
                print(json.dumps(brain.evaluate(args.episodes, args.band, args.split), indent=2))
            else:
                print(json.dumps(brain.trace(args.index, args.band, args.split), indent=2))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
