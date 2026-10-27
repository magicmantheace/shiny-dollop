"""Auditable, bounded multi-objective transfer experiment (Python stdlib only).

Three tasks share the same *local* observation and action vocabulary:
``reach`` navigates to a location; ``collect`` navigates and interacts there;
``courier`` interacts at pickup then returns to its origin to deliver. An
explicit direction-to-current-target cue switches at pickup. This is a useful
but narrow task-transfer test, NOT evidence of autonomous planning or a mind.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sqlite3
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from .transfer import ACTIONS, DELTAS, Layout, State

SCHEMA = "curriculum-v1"
TASKS = ("reach", "collect", "courier")
POLICIES = ("learned", "random", "greedy", "oracle")


def task_seed(master_seed: int, split: str, task: str, index: int) -> int:
    if split not in ("train", "test") or task not in TASKS or index < 0:
        raise ValueError("invalid split, task, or episode index")
    payload = f"developmental-ai/{SCHEMA}/{master_seed}/{split}/{task}/{index}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class TaskArena:
    """Simulation-only environment; never executes external actions."""

    def __init__(self, layout: Layout, task: str):
        if task not in TASKS or layout.start == layout.goal:
            raise ValueError("unknown task or degenerate layout")
        self.layout = layout
        self.task = task
        self.position = layout.start
        self.carrying = False
        self.finished = False
        self.steps = 0
        self.limit = (4 if task == "courier" else 2) * layout.size ** 2

    @property
    def target(self) -> tuple[int, int]:
        return self.layout.start if self.task == "courier" and self.carrying else self.layout.goal

    def _blocked(self, action: int) -> bool:
        dx, dy = DELTAS[action]
        x, y = self.position[0] + dx, self.position[1] + dy
        return not (0 <= x < self.layout.size and 0 <= y < self.layout.size) or (x, y) in self.layout.walls

    def observe(self) -> State:
        """Same three local features for all tasks; no task label or global map."""
        dx = self.target[0] - self.position[0]
        dy = self.target[1] - self.position[1]
        mask = sum(1 << i for i in range(4) if self._blocked(i))
        return (max(-3, min(3, dx)), max(-3, min(3, dy)), mask)

    def step(self, action: int) -> tuple[State, float, bool, str]:
        if self.finished:
            raise RuntimeError("episode already finished")
        if type(action) is not int or not 0 <= action < len(ACTIONS):
            raise ValueError("invalid simulated action")
        self.steps += 1
        reward = -0.04
        event = "move"
        if action == 4:
            if self.position == self.target and self.task != "reach":
                if self.task == "courier" and not self.carrying:
                    self.carrying = True
                    reward += 2
                    event = "pickup"
                else:
                    reward += 8
                    self.finished = True
                    event = "delivered" if self.task == "courier" else "collected"
            else:
                reward -= 0.5
                event = "empty_interact"
        elif self._blocked(action):
            reward -= 0.6
            event = "blocked"
        else:
            dx, dy = DELTAS[action]
            self.position = (self.position[0] + dx, self.position[1] + dy)
            if self.task == "reach" and self.position == self.layout.goal:
                self.finished = True
                reward += 8
                event = "reached"
        if self.steps >= self.limit and not self.finished:
            self.finished = True
            reward -= 2
            event = "timeout"
        return self.observe(), reward, self.finished, event


def _oracle_action(arena: TaskArena) -> int:
    """Full-layout upper bound, not a same-observation policy."""
    if arena.position == arena.target:
        return 4
    queue = deque([(arena.position, None)])
    seen = {arena.position}
    while queue:
        pos, first = queue.popleft()
        if pos == arena.target:
            return first if first is not None else 4
        for a, (dx, dy) in enumerate(DELTAS):
            x, y = pos[0] + dx, pos[1] + dy
            nxt = (x, y)
            if (0 <= x < arena.layout.size and 0 <= y < arena.layout.size
                    and nxt not in arena.layout.walls and nxt not in seen):
                seen.add(nxt)
                queue.append((nxt, a if first is None else first))
    raise RuntimeError("generator promised a reachable goal")


def _greedy_action(state: State, rng: random.Random) -> int:
    """Hand-written same-observation, obstacle-aware baseline (may loop)."""
    dx, dy, blocked = state
    if dx == 0 and dy == 0:
        return 4
    directions = list(range(4))
    rng.shuffle(directions)
    preference = {
        0: (-dy), 1: dy, 2: (-dx), 3: dx,
    }
    # Highest reduction of clipped Manhattan target displacement; tie seeded.
    directions.sort(key=lambda a: preference[a], reverse=True)
    for a in directions:
        if not (blocked & (1 << a)):
            return a
    return 4


def choose_action(arena: TaskArena, policy: str, rng: random.Random,
                  brain: "CurriculumBrain | None" = None, epsilon: float = 0.0) -> int:
    if policy == "random":
        return rng.randrange(len(ACTIONS))
    if policy == "greedy":
        return _greedy_action(arena.observe(), rng)
    if policy == "oracle":
        return _oracle_action(arena)
    if policy == "learned" and brain is not None:
        return brain.choose(arena.observe(), rng, epsilon)
    raise ValueError("unknown policy or missing brain")


def play(arena: TaskArena, policy: str, rng: random.Random,
         brain: "CurriculumBrain | None" = None, learning: bool = False,
         epsilon: float = 0.0, record: bool = False) -> tuple[dict, list[dict]]:
    if learning and (brain is None or policy != "learned"):
        raise ValueError("training requires the learned policy")
    total = 0.0
    blocked = 0
    events: list[dict] = []
    last = ""
    while not arena.finished:
        old = arena.observe()
        action = choose_action(arena, policy, rng, brain, epsilon)
        state, reward, done, event = arena.step(action)
        total += reward
        blocked += event == "blocked"
        last = event
        if record:
            events.append({"before": list(old), "action": action, "after": list(state),
                           "reward": reward, "event": event, "done": done})
        if learning:
            assert brain is not None
            brain.visits[state] += 1
            bonus = 0.06 / math.sqrt(brain.visits[state]) if state != old else 0
            target = reward + bonus
            if not done:
                target += 0.95 * max(brain.q.get((state, a), 0.0) for a in range(len(ACTIONS)))
            original = brain.q.get((old, action), 0.0)
            brain.q[(old, action)] = original + 0.23 * (target - original)
    success = last in ("reached", "collected", "delivered")
    return ({"success": success, "steps": arena.steps, "external_reward": total,
             "blocked": blocked, "terminal_event": last}, events)


class CurriculumBrain:
    """One shared Q-policy across task types; versioned, seed-bound checkpoints."""

    def __init__(self, database: Path, seed: int = 17):
        database.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(database)
        try:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS curriculum_meta (
                    name TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS curriculum_q (
                    state TEXT NOT NULL, action INTEGER NOT NULL, value REAL NOT NULL,
                    PRIMARY KEY(state, action));
                CREATE TABLE IF NOT EXISTS curriculum_visits (
                    state TEXT PRIMARY KEY, count INTEGER NOT NULL);
            """)
            meta = dict(self.conn.execute("SELECT name,value FROM curriculum_meta"))
            if meta and (meta.get("schema") != SCHEMA or meta.get("seed") != str(seed)):
                raise ValueError("checkpoint schema or training seed mismatch")
            self.seed = seed
            self.trained = int(meta.get("trained", "0"))
            self.training_tasks = tuple(json.loads(meta["training_tasks"])) if "training_tasks" in meta else ()
            self.q = {(tuple(json.loads(state)), action): value for state, action, value
                      in self.conn.execute("SELECT state,action,value FROM curriculum_q")}
            self.visits = defaultdict(int, {tuple(json.loads(state)): count for state, count
                                            in self.conn.execute("SELECT state,count FROM curriculum_visits")})
        except Exception:
            self.conn.close()
            raise

    def choose(self, state: State, rng: random.Random, epsilon: float = 0.0) -> int:
        if rng.random() < epsilon:
            return rng.randrange(len(ACTIONS))
        values = [self.q.get((state, a), 0.0) for a in range(len(ACTIONS))]
        maximum = max(values)
        return rng.choice([a for a, value in enumerate(values) if value == maximum])

    def persist(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM curriculum_q")
            self.conn.executemany("INSERT INTO curriculum_q VALUES (?,?,?)",
                                  ((_canonical(state), a, v) for (state, a), v in self.q.items()))
            self.conn.execute("DELETE FROM curriculum_visits")
            self.conn.executemany("INSERT INTO curriculum_visits VALUES (?,?)",
                                  ((_canonical(state), n) for state, n in self.visits.items()))
            self.conn.executemany("INSERT INTO curriculum_meta VALUES (?,?) "
                                  "ON CONFLICT(name) DO UPDATE SET value=excluded.value",
                                  (("schema", SCHEMA), ("seed", str(self.seed)),
                                   ("trained", str(self.trained)),
                                   ("training_tasks", _canonical(self.training_tasks))))

    def train(self, episodes: int, tasks: tuple[str, ...] = ("collect",)) -> None:
        if episodes < 1 or not tasks or len(set(tasks)) != len(tasks) or any(t not in TASKS for t in tasks):
            raise ValueError("positive episodes and unique known training tasks required")
        if self.training_tasks and self.training_tasks != tuple(tasks):
            raise ValueError("cannot resume with a different task curriculum")
        self.training_tasks = tuple(tasks)
        for _ in range(episodes):
            index = self.trained
            task = tasks[index % len(tasks)]
            arena = TaskArena(Layout.generate(task_seed(self.seed, "train", task, index)), task)
            rng = random.Random(task_seed(self.seed + 1, "train", task, index))
            epsilon = max(0.055, 0.6 * 0.9995 ** index)
            play(arena, "learned", rng, brain=self, learning=True, epsilon=epsilon)
            self.trained += 1
        self.persist()  # durable boundary; interrupted batches before here are not saved

    def evaluate(self, task: str, episodes: int = 100, split: str = "test",
                 policy: str = "learned") -> dict:
        if task not in TASKS or split not in ("train", "test") or policy not in POLICIES or episodes < 1:
            raise ValueError("invalid evaluation parameters")
        outcomes = []
        for i in range(episodes):
            arena = TaskArena(Layout.generate(task_seed(self.seed, split, task, i)), task)
            rng = random.Random(task_seed(self.seed + 2, split, task, i))
            result, _ = play(arena, policy, rng, self if policy == "learned" else None)
            outcomes.append(result)
        return {"schema": SCHEMA, "task": task, "split": split, "policy": policy,
                "seed": self.seed, "episodes": episodes, "trained_episodes": self.trained,
                "success_rate": round(sum(o["success"] for o in outcomes) / episodes, 4),
                "mean_steps": round(sum(o["steps"] for o in outcomes) / episodes, 2),
                "mean_blocked": round(sum(o["blocked"] for o in outcomes) / episodes, 2)}

    def trace(self, task: str, index: int = 0, split: str = "test", policy: str = "learned") -> dict:
        seed = task_seed(self.seed, split, task, index)
        arena = TaskArena(Layout.generate(seed), task)
        rng = random.Random(task_seed(self.seed + 2, split, task, index))
        result, events = play(arena, policy, rng, self if policy == "learned" else None, record=True)
        payload = {"schema": "developmental-ai.trace/v1", "source": "simulation",
                   "scope": "simulation-only", "seed": self.seed, "split": split,
                   "task": task, "episode_index": index, "layout_seed": seed,
                   "policy": policy, "outcome": result, "events": events}
        return {**payload, "sha256": hashlib.sha256(_canonical(payload).encode()).hexdigest()}

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "CurriculumBrain":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def verify_trace(trace: dict) -> dict:
    """Replay supplied action sequence from a reproducible simulated layout.

    This verifies internal consistency, not externally attested authorship;
    anyone can generate a self-consistent trace and recompute its checksum.
    """
    if not isinstance(trace, dict):
        raise ValueError("trace must be a JSON object")
    try:
        payload = {k: v for k, v in trace.items() if k != "sha256"}
        if (trace.get("schema") != "developmental-ai.trace/v1" or
                trace.get("source") != "simulation" or trace.get("scope") != "simulation-only" or
                trace.get("policy") not in POLICIES):
            raise ValueError("unrecognized trace schema or policy")
        digest = hashlib.sha256(_canonical(payload).encode()).hexdigest()
        if digest != trace.get("sha256"):
            raise ValueError("trace checksum mismatch")
        seed = task_seed(trace["seed"], trace["split"], trace["task"], trace["episode_index"])
        if seed != trace["layout_seed"]:
            raise ValueError("layout seed mismatch")
        arena = TaskArena(Layout.generate(seed), trace["task"])
        total = 0.0
        blocked = 0
        last = ""
        if not isinstance(trace["events"], list) or len(trace["events"]) > arena.limit:
            raise ValueError("invalid event count")
        for expected in trace["events"]:
            if arena.finished or list(arena.observe()) != expected["before"]:
                raise ValueError("replay observation mismatch")
            next_state, reward, done, event = arena.step(expected["action"])
            if (list(next_state) != expected["after"] or reward != expected["reward"] or
                    done != expected["done"] or event != expected["event"]):
                raise ValueError("replay event mismatch")
            total += reward
            blocked += event == "blocked"
            last = event
        outcome = {"success": last in ("reached", "collected", "delivered"),
                   "steps": arena.steps, "external_reward": total, "blocked": blocked,
                   "terminal_event": last}
        if not arena.finished or trace["outcome"] != outcome:
            raise ValueError("incomplete trace or outcome mismatch")
        return {"verified": True, "steps": arena.steps, "task": trace["task"],
                "checksum": digest}
    except (KeyError, TypeError, OverflowError, IndexError) as exc:
        raise ValueError("malformed trace") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("train", "evaluate", "trace", "verify"))
    parser.add_argument("--db", type=Path, default=Path("curriculum_brain.db"))
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--episodes", type=int, default=1000)
    parser.add_argument("--task", choices=TASKS, default="collect")
    parser.add_argument("--tasks", nargs="+", choices=TASKS, default=["collect"])
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--split", choices=("train", "test"), default="test")
    parser.add_argument("--policy", choices=POLICIES, default="learned")
    parser.add_argument("--trace-file", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "verify":
            if args.trace_file is None:
                parser.error("verify requires --trace-file")
            print(json.dumps(verify_trace(json.loads(args.trace_file.read_text(encoding="utf-8"))), indent=2))
            return
        with CurriculumBrain(args.db, args.seed) as brain:
            if args.command == "train":
                brain.train(args.episodes, tuple(args.tasks))
                print(json.dumps({"trained_episodes": brain.trained, "training_tasks": brain.training_tasks}))
            elif args.command == "evaluate":
                print(json.dumps(brain.evaluate(args.task, args.episodes, args.split, args.policy), indent=2))
            else:
                print(json.dumps(brain.trace(args.task, args.index, args.split, args.policy), indent=2))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
