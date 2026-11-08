"""Small, deliberately inspectable benchmark for out-of-layout transfer.

The learner observes only target displacement (clipped to three cells) and the
four blocked neighboring directions. It never receives a layout identifier,
absolute coordinates, a shortest path, or a lookup of known test maps.

This is still tabular Q-learning, not a world model or a digital mind.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sqlite3
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

ACTIONS = ("north", "south", "west", "east", "eat")
DELTAS = ((0, -1), (0, 1), (-1, 0), (1, 0))
State = tuple[int, int, int]


def episode_seed(master_seed: int, split: str, index: int) -> int:
    """Namespaced, stable procedural layout seed; independent of Python hash()."""
    if split not in ("train", "test"):
        raise ValueError("split must be 'train' or 'test'")
    if index < 0:
        raise ValueError("episode index cannot be negative")
    payload = f"developmental-ai/transfer-v1/{master_seed}/{split}/{index}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _reachable(start: tuple[int, int], goal: tuple[int, int],
               walls: frozenset[tuple[int, int]], size: int) -> bool:
    queue = deque([start])
    visited = {start}
    while queue:
        point = queue.popleft()
        if point == goal:
            return True
        for dx, dy in DELTAS:
            nxt = (point[0] + dx, point[1] + dy)
            if (0 <= nxt[0] < size and 0 <= nxt[1] < size and
                    nxt not in walls and nxt not in visited):
                visited.add(nxt)
                queue.append(nxt)
    return False


@dataclass(frozen=True)
class Layout:
    size: int
    start: tuple[int, int]
    goal: tuple[int, int]
    walls: frozenset[tuple[int, int]]

    @classmethod
    def generate(cls, seed: int) -> "Layout":
        rng = random.Random(seed)
        for _ in range(500):
            size = rng.randint(5, 8)
            start = (rng.randrange(size), rng.randrange(size))
            goal = (rng.randrange(size), rng.randrange(size))
            if abs(start[0] - goal[0]) + abs(start[1] - goal[1]) < 3:
                continue
            density = rng.uniform(0.10, 0.24)
            walls = frozenset(
                (x, y) for x in range(size) for y in range(size)
                if (x, y) not in (start, goal) and rng.random() < density
            )
            if _reachable(start, goal, walls, size):
                return cls(size, start, goal, walls)
        raise RuntimeError("could not produce a reachable randomized layout")


class TransferArena:
    def __init__(self, layout: Layout):
        self.layout = layout
        self.position = layout.start
        self.steps = 0
        self.finished = False
        self.limit = 2 * layout.size * layout.size

    def _blocked(self, action: int) -> bool:
        dx, dy = DELTAS[action]
        x, y = self.position[0] + dx, self.position[1] + dy
        return (not (0 <= x < self.layout.size and 0 <= y < self.layout.size)
                or (x, y) in self.layout.walls)

    def observe(self) -> State:
        dx = self.layout.goal[0] - self.position[0]
        dy = self.layout.goal[1] - self.position[1]
        mask = sum(1 << i for i in range(4) if self._blocked(i))
        return (max(-3, min(3, dx)), max(-3, min(3, dy)), mask)

    def step(self, action: int) -> tuple[State, float, bool, str]:
        if self.finished:
            raise RuntimeError("cannot act after episode ends")
        if action not in range(len(ACTIONS)):
            raise ValueError("unknown action")
        self.steps += 1
        reward = -0.04
        event = "move"
        if action == 4:
            if self.position == self.layout.goal:
                reward += 8
                self.finished = True
                event = "food"
            else:
                reward -= 0.5
                event = "empty_eat"
        elif self._blocked(action):
            reward -= 0.6
            event = "blocked"
        else:
            dx, dy = DELTAS[action]
            self.position = (self.position[0] + dx, self.position[1] + dy)
        if self.steps >= self.limit and not self.finished:
            self.finished = True
            reward -= 2
            event = "timeout"
        return self.observe(), reward, self.finished, event


@dataclass(frozen=True)
class Outcome:
    success: bool
    steps: int
    reward: float
    blocked: int


class TransferBrain:
    """Persistent state-action values, with no knowledge of individual layouts."""

    def __init__(self, database: Path, seed: int = 17):
        database.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(database)
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS transfer_metadata (
                name TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS transfer_skills (
                state TEXT NOT NULL, action INTEGER NOT NULL, value REAL NOT NULL,
                PRIMARY KEY(state,action)
            );
            CREATE TABLE IF NOT EXISTS transfer_visits (
                state TEXT PRIMARY KEY, count INTEGER NOT NULL
            );
        """)
        # Seed is part of the stored training distribution; mixing seeds would
        # make a claimed disjoint held-out split difficult to audit.
        stored = self.conn.execute(
            "SELECT value FROM transfer_metadata WHERE name='seed'").fetchone()
        if stored is not None and int(stored[0]) != seed:
            self.conn.close()
            raise ValueError("existing brain was trained with a different seed")
        self.seed = seed
        self.trained = int(self._metadata("trained", "0"))
        self.q: dict[tuple[State, int], float] = {
            (tuple(json.loads(state)), action): value
            for state, action, value in self.conn.execute(
                "SELECT state,action,value FROM transfer_skills")
        }
        self.visits = defaultdict(int, {
            tuple(json.loads(state)): count
            for state, count in self.conn.execute(
                "SELECT state,count FROM transfer_visits")
        })
        self.rng = random.Random(episode_seed(seed, "train", self.trained))

    def _metadata(self, key: str, default: str) -> str:
        row = self.conn.execute(
            "SELECT value FROM transfer_metadata WHERE name=?", (key,)).fetchone()
        return row[0] if row else default

    def persist(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM transfer_skills")
            self.conn.executemany(
                "INSERT INTO transfer_skills VALUES (?,?,?)",
                ((json.dumps(state), action, value)
                 for (state, action), value in self.q.items()))
            self.conn.execute("DELETE FROM transfer_visits")
            self.conn.executemany(
                "INSERT INTO transfer_visits VALUES (?,?)",
                ((json.dumps(state), n) for state, n in self.visits.items()))
            self.conn.executemany(
                "INSERT INTO transfer_metadata VALUES (?,?) "
                "ON CONFLICT(name) DO UPDATE SET value=excluded.value",
                (("seed", str(self.seed)), ("trained", str(self.trained)),
                 ("schema", "transfer-v1")))

    def _choose(self, state: State, epsilon: float, rng: random.Random) -> int:
        if rng.random() < epsilon:
            return rng.randrange(len(ACTIONS))
        values = [self.q.get((state, a), 0.0) for a in range(len(ACTIONS))]
        best = max(values)
        return rng.choice([a for a, val in enumerate(values) if val == best])

    def _run(self, layout: Layout, learning: bool, rng: random.Random,
             epsilon: float = 0.0) -> Outcome:
        arena = TransferArena(layout)
        total = 0.0
        blocked = 0
        success = False
        while not arena.finished:
            old = arena.observe()
            action = self._choose(old, epsilon, rng)
            state, reward, done, event = arena.step(action)
            total += reward
            blocked += event == "blocked"
            success = event == "food"
            if learning:
                self.visits[state] += 1
                # A small novelty incentive; only reward actual exploration.
                bonus = 0.06 / math.sqrt(self.visits[state]) if state != old else 0
                target = reward + bonus
                if not done:
                    target += 0.95 * max(
                        self.q.get((state, a), 0) for a in range(len(ACTIONS)))
                self.q[(old, action)] = self.q.get((old, action), 0) + 0.23 * (
                    target - self.q.get((old, action), 0))
        return Outcome(success, arena.steps, total, blocked)

    def train(self, episodes: int) -> None:
        if episodes < 1:
            raise ValueError("training episode count must be positive")
        for _ in range(episodes):
            index = self.trained
            layout = Layout.generate(episode_seed(self.seed, "train", index))
            epsilon = max(0.055, 0.6 * (0.9995 ** index))
            # The seed of the action RNG is reproducible across restarts.
            rng = random.Random(episode_seed(self.seed + 1, "train", index))
            self._run(layout, learning=True, rng=rng, epsilon=epsilon)
            self.trained += 1
        self.persist()

    def evaluate(self, episodes: int, split: str = "test") -> dict:
        if episodes < 1:
            raise ValueError("evaluation episode count must be positive")
        if split not in ("train", "test"):
            raise ValueError("split must be train or test")
        outcomes = []
        for index in range(episodes):
            layout = Layout.generate(episode_seed(self.seed, split, index))
            rng = random.Random(episode_seed(self.seed + 2, split, index))
            outcomes.append(self._run(layout, learning=False, rng=rng))
        return {
            "schema": "transfer-v1",
            "split": split,
            "seed": self.seed,
            "episodes": episodes,
            "trained_episodes": self.trained,
            "success_rate": round(sum(o.success for o in outcomes) / episodes, 4),
            "mean_steps": round(sum(o.steps for o in outcomes) / episodes, 2),
            "mean_blocked": round(sum(o.blocked for o in outcomes) / episodes, 2),
            "mean_external_reward": round(sum(o.reward for o in outcomes) / episodes, 3),
        }

    def close(self) -> None:
        self.conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("train", "evaluate"))
    parser.add_argument("--db", type=Path, default=Path("transfer_brain.db"))
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--episodes", type=int, default=4000)
    parser.add_argument("--split", choices=("train", "test"), default="test")
    args = parser.parse_args()
    try:
        brain = TransferBrain(args.db, seed=args.seed)
        try:
            if args.command == "train":
                print("before:", json.dumps(brain.evaluate(200)))
                brain.train(args.episodes)
                print("after:", json.dumps(brain.evaluate(200)))
            else:
                print(json.dumps(brain.evaluate(args.episodes, args.split), indent=2))
        finally:
            brain.close()
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
