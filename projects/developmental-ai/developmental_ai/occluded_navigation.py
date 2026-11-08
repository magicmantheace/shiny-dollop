"""Occluded-target navigation: a one-time beacon and explicit dead-reckoning memory.

This simulation does not expose a persistent direction-to-target sensor.
The agent learns a policy, but retaining a cue and integrating *successful*
movement feedback are ENGINEERED memory operations, not learned recurrent state.
No privileged actions, network requests, personal data, or filesystem tools.
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

from .transfer import ACTIONS, DELTAS, Layout

SCHEMA = "occluded-navigation-v1"
MODES = ("memory", "reactive")
POLICIES = ("learned", "greedy", "oracle", "random")
TRACE_SCHEMA = "developmental-ai.occluded-trace/v1"
State = tuple[int, int, int]


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def episode_seed(seed: int, split: str, index: int, purpose: str = "layout") -> int:
    if type(seed) is not int or split not in ("train", "test") or type(index) is not int or index < 0 or purpose not in ("layout", "actions"):
        raise ValueError("invalid episode seed parameters")
    raw = f"developmental-ai/{SCHEMA}/{seed}/{split}/{index}/{purpose}".encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def _clip(value: int) -> int:
    return min(3, max(-3, value))


class OccludedWorld:
    """A goal clue appears on the first observation only; thereafter local walls."""

    def __init__(self, layout: Layout):
        if layout.start == layout.goal:
            raise ValueError("degenerate layout")
        self.layout = layout
        self.position = layout.start
        self.steps = 0
        self.finished = False
        self.limit = 2 * layout.size * layout.size

    def observe(self) -> dict:
        mask = 0
        for i, (dx, dy) in enumerate(DELTAS):
            p = (self.position[0] + dx, self.position[1] + dy)
            if not (0 <= p[0] < self.layout.size and 0 <= p[1] < self.layout.size) or p in self.layout.walls:
                mask |= 1 << i
        clue = [self.layout.goal[0] - self.position[0], self.layout.goal[1] - self.position[1]] if self.steps == 0 else None
        return {"beacon": clue, "blocked": mask}

    def step(self, action: int) -> tuple[float, bool, str]:
        if self.finished:
            raise RuntimeError("completed episode")
        if type(action) is not int or action not in range(len(ACTIONS)):
            raise ValueError("invalid action")
        mask = self.observe()["blocked"]
        self.steps += 1
        reward = -0.04
        if action == 4:
            if self.position == self.layout.goal:
                self.finished = True
                reward += 8.0
                event = "collected"
            else:
                reward -= 0.5
                event = "empty_interact"
        elif mask & (1 << action):
            reward -= 0.6
            event = "blocked"
        else:
            dx, dy = DELTAS[action]
            self.position = (self.position[0] + dx, self.position[1] + dy)
            event = "move"
        if self.steps >= self.limit and not self.finished:
            reward -= 2.0
            self.finished = True
            event = "timeout"
        return reward, self.finished, event


class DeadReckoning:
    """Explicit working memory; the learned policy does not create this structure."""

    def __init__(self, mode: str):
        if mode not in MODES:
            raise ValueError("invalid memory mode")
        self.mode = mode
        self.remaining: tuple[int, int] | None = None

    def observe(self, sensed: dict) -> State:
        cue = sensed["beacon"]
        if cue is not None:
            if self.remaining is not None:
                raise ValueError("beacon observed twice")
            self.remaining = (cue[0], cue[1])
        dx, dy = self.remaining if self.remaining is not None else (0, 0)
        return _clip(dx), _clip(dy), sensed["blocked"]

    def advance(self, action: int, event: str) -> None:
        if self.mode == "reactive":
            self.remaining = None  # loses the instruction after the first action
        elif event == "move" and self.remaining is not None:
            x, y = DELTAS[action]
            self.remaining = (self.remaining[0] - x, self.remaining[1] - y)


def greedy_action(state: State, rng: random.Random) -> int:
    dx, dy, mask = state
    if dx == 0 and dy == 0:
        return 4
    dirs = list(range(4))
    rng.shuffle(dirs)
    dirs.sort(key=lambda a: (dy if a == 1 else -dy if a == 0 else dx if a == 3 else -dx), reverse=True)
    for a in dirs:
        if not mask & (1 << a):
            return a
    return 4


def oracle_action(world: OccludedWorld) -> int:
    """Full-map BFS reference: NOT an equally informed controller."""
    from collections import deque
    if world.position == world.layout.goal:
        return 4
    queue = deque([(world.position, None)])
    seen = {world.position}
    while queue:
        pos, first = queue.popleft()
        if pos == world.layout.goal:
            return first
        for a, (dx, dy) in enumerate(DELTAS):
            nxt = (pos[0] + dx, pos[1] + dy)
            if (0 <= nxt[0] < world.layout.size and 0 <= nxt[1] < world.layout.size
                    and nxt not in world.layout.walls and nxt not in seen):
                seen.add(nxt)
                queue.append((nxt, a if first is None else first))
    raise RuntimeError("unreachable generated layout")


class OccludedBrain:
    """Separate versioned SQLite policy for a memory or reactive ablation."""

    def __init__(self, db: Path, seed: int = 17, mode: str = "memory"):
        if type(seed) is not int or mode not in MODES:
            raise ValueError("invalid seed/mode")
        db.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db)
        try:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS occluded_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS occluded_q (state TEXT NOT NULL, action INTEGER NOT NULL,
                    value REAL NOT NULL, PRIMARY KEY(state,action));
                CREATE TABLE IF NOT EXISTS occluded_visits (state TEXT PRIMARY KEY, count INTEGER NOT NULL);
            """)
            meta = dict(self.conn.execute("SELECT key,value FROM occluded_meta"))
            if meta and (meta.get("schema") != SCHEMA or meta.get("seed") != str(seed) or meta.get("mode") != mode):
                raise ValueError("incompatible checkpoint")
            self.seed, self.mode = seed, mode
            self.trained = int(meta.get("trained", "0"))
            if self.trained < 0:
                raise ValueError("invalid training counter")
            self.q = {(tuple(json.loads(s)), a): float(v) for s, a, v in self.conn.execute("SELECT state,action,value FROM occluded_q")}
            self.visits = {tuple(json.loads(s)): n for s, n in self.conn.execute("SELECT state,count FROM occluded_visits")}
            for (state, action), value in self.q.items():
                if len(state) != 3 or type(action) is not int or action not in range(5) or not math.isfinite(value):
                    raise ValueError("corrupt learned policy")
            if any(len(s) != 3 or type(n) is not int or n < 0 for s, n in self.visits.items()):
                raise ValueError("corrupt visit counts")
        except Exception:
            self.conn.close()
            raise

    def choose(self, state: State, rng: random.Random, epsilon: float = 0) -> int:
        if rng.random() < epsilon:
            return rng.randrange(5)
        values = [self.q.get((state, a), 0.0) for a in range(5)]
        best = max(values)
        return rng.choice([a for a, v in enumerate(values) if v == best])

    def run(self, split: str, index: int, policy: str = "learned", learn: bool = False,
            epsilon: float = 0.0, trace: bool = False) -> dict:
        if policy not in POLICIES or type(index) is not int or index < 0 or split not in ("train", "test") or not 0 <= epsilon <= 1:
            raise ValueError("invalid run options")
        if learn and (policy != "learned" or split != "train" or index != self.trained):
            raise ValueError("training only allowed on next train episode")
        world = OccludedWorld(Layout.generate(episode_seed(self.seed, split, index)))
        memory = DeadReckoning(self.mode)
        rng = random.Random(episode_seed(self.seed, split, index, "actions"))
        events = []
        total = 0.0
        last = ""
        while not world.finished:
            observation = world.observe()
            state = memory.observe(observation)
            if policy == "learned":
                action = self.choose(state, rng, epsilon)
            elif policy == "greedy":
                action = greedy_action(state, rng)
            elif policy == "oracle":
                action = oracle_action(world)
            else:
                action = rng.randrange(5)
            reward, done, event = world.step(action)
            memory.advance(action, event)
            next_state = memory.observe(world.observe())
            total += reward
            last = event
            if trace:
                events.append({"observation": observation, "memory_before": list(state),
                               "action": action, "event": event, "reward": reward, "done": done,
                               "observation_after": world.observe(), "memory_after": list(next_state)})
            if learn:
                self.visits[next_state] = self.visits.get(next_state, 0) + 1
                novelty = 0.06 / math.sqrt(self.visits[next_state]) if next_state != state else 0
                target = reward + novelty + (0 if done else 0.95 * max(self.q.get((next_state, a), 0.0) for a in range(5)))
                old = self.q.get((state, action), 0.0)
                self.q[(state, action)] = old + 0.23 * (target - old)
            if done:
                break
        if learn:
            self.trained += 1
        return {"success": last == "collected", "steps": world.steps,
                "reward": round(total, 8), "terminal": last, "events": events if trace else []}

    def train(self, episodes: int) -> None:
        if type(episodes) is not int or episodes < 1:
            raise ValueError("positive episodes required")
        for _ in range(episodes):
            epsilon = max(0.06, 0.65 * 0.9995 ** self.trained)
            self.run("train", self.trained, learn=True, epsilon=epsilon)
        self.persist()

    def persist(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM occluded_q")
            self.conn.execute("DELETE FROM occluded_visits")
            self.conn.executemany("INSERT INTO occluded_q VALUES (?,?,?)", ((canonical(s), a, v) for (s, a), v in self.q.items()))
            self.conn.executemany("INSERT INTO occluded_visits VALUES (?,?)", ((canonical(s), n) for s, n in self.visits.items()))
            self.conn.executemany("INSERT INTO occluded_meta(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                                  (("schema", SCHEMA), ("seed", str(self.seed)), ("mode", self.mode), ("trained", str(self.trained))))

    def evaluate(self, episodes: int = 200, policy: str = "learned", split: str = "test") -> dict:
        if type(episodes) is not int or episodes < 1 or split not in ("train", "test") or policy not in POLICIES:
            raise ValueError("invalid evaluation")
        values = [self.run(split, i, policy=policy) for i in range(episodes)]
        return {"schema": SCHEMA, "seed": self.seed, "mode": self.mode, "policy": policy,
                "trained": self.trained, "episodes": episodes, "split": split,
                "success_rate": round(sum(x["success"] for x in values) / episodes, 4),
                "mean_steps": round(sum(x["steps"] for x in values) / episodes, 3)}

    def trace(self, index: int = 0, split: str = "test", policy: str = "learned") -> dict:
        outcome = self.run(split, index, policy=policy, trace=True)
        body = {"schema": TRACE_SCHEMA, "seed": self.seed, "mode": self.mode,
                "index": index, "split": split, "policy": policy,
                "source": "simulation", "scope": "simulation-only", "outcome": outcome}
        return {**body, "sha256": hashlib.sha256(canonical(body).encode()).hexdigest()}

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def verify_trace(trace: dict) -> dict:
    """Independently replay transitions, observations and dead-reckoning operations.

    Does NOT prove the actions came from any particular learned checkpoint.
    """
    try:
        if type(trace) is not dict or trace.get("schema") != TRACE_SCHEMA or trace.get("source") != "simulation" or trace.get("scope") != "simulation-only" or trace.get("mode") not in MODES or trace.get("policy") not in POLICIES:
            raise ValueError("invalid trace header")
        body = {k: v for k, v in trace.items() if k != "sha256"}
        if hashlib.sha256(canonical(body).encode()).hexdigest() != trace.get("sha256"):
            raise ValueError("checksum mismatch")
        world = OccludedWorld(Layout.generate(episode_seed(trace["seed"], trace["split"], trace["index"])))
        memory = DeadReckoning(trace["mode"])
        total = 0.0
        for step in trace["outcome"]["events"]:
            if world.finished or world.observe() != step["observation"]:
                raise ValueError("invalid observation or excess steps")
            state = memory.observe(world.observe())
            if list(state) != step["memory_before"]:
                raise ValueError("invalid stored memory")
            action = step["action"]
            reward, done, event = world.step(action)
            memory.advance(action, event)
            after = world.observe()
            next_state = memory.observe(after)
            if (event != step["event"] or done != step["done"] or reward != step["reward"]
                    or after != step["observation_after"] or list(next_state) != step["memory_after"]):
                raise ValueError("invalid transition")
            total += reward
        outcome = trace["outcome"]
        if (not world.finished or len(outcome["events"]) != world.steps or
                outcome["success"] != (event == "collected") or outcome["steps"] != world.steps or
                outcome["terminal"] != event or abs(outcome["reward"] - total) > 1e-6):
            raise ValueError("invalid outcome")
        return {"verified": True, "steps": world.steps, "sha256": trace["sha256"]}
    except (TypeError, KeyError, IndexError, OverflowError, AttributeError, UnboundLocalError) as exc:
        raise ValueError("invalid trace structure") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("train", "evaluate", "trace", "verify"))
    parser.add_argument("--db", type=Path, default=Path("occluded.db"))
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--mode", choices=MODES, default="memory")
    parser.add_argument("--episodes", type=int, default=200)
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--split", choices=("train", "test"), default="test")
    parser.add_argument("--policy", choices=POLICIES, default="learned")
    parser.add_argument("--trace-file", type=Path)
    args = parser.parse_args()
    if args.command == "verify":
        if args.trace_file is None:
            parser.error("--trace-file is required")
        print(canonical(verify_trace(json.loads(args.trace_file.read_text(encoding="utf-8")))))
    else:
        with OccludedBrain(args.db, args.seed, args.mode) as brain:
            if args.command == "train":
                brain.train(args.episodes)
                print(canonical({"trained": brain.trained, "mode": brain.mode}))
            elif args.command == "evaluate":
                print(canonical(brain.evaluate(args.episodes, policy=args.policy, split=args.split)))
            else:
                print(canonical(brain.trace(args.index, args.split, args.policy)))


if __name__ == "__main__":
    main()
