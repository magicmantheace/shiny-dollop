"""Uncertain motion and intermittent landmark navigation in a 1-D ring.

The beacon containing initial position and hidden target is shown once. The
agent receives noisy odometry and occasional landmark observations thereafter.
A deliberately ENGINEERED Bayesian state estimator supports an independently
trained tabular control policy. No private data or external actuators.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sqlite3
from pathlib import Path

SCHEMA = "uncertain-ring/v1"
TRACE_SCHEMA = "developmental-ai.uncertain-trace/v1"
MODES = ("belief", "dead", "reactive")
POLICIES = ("learned", "heuristic", "random", "oracle")
ACTIONS = (-1, 1, 0)  # left, right, collect


def canonical(obj):
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, allow_nan=False)


def seed_for(seed, split, index, purpose):
    if type(seed) is not int or split not in ("train", "test") or type(index) is not int or index < 0 or purpose not in ("world", "policy"):
        raise ValueError("invalid deterministic seed")
    b = f"{SCHEMA}/{seed}/{split}/{index}/{purpose}".encode()
    return int.from_bytes(hashlib.sha256(b).digest()[:8], "big")


def distance(a, b, n):
    return min((b-a) % n, (a-b) % n)


def signed_distance(a, b, n):
    right = (b-a) % n
    left = (a-b) % n
    return right if right <= left else -left


class RingWorld:
    """Locally deterministic stochastic physics; neither policy sees position."""
    def __init__(self, seed, split, index, noise="standard", landmarks=True):
        if noise not in ("standard", "high") or type(landmarks) is not bool:
            raise ValueError("invalid environment configuration")
        self.rng = random.Random(seed_for(seed, split, index, "world"))
        self.n = self.rng.choice((9, 11))
        self.pos = self.rng.randrange(self.n)
        self.goal = (self.pos + self.rng.randrange(1, self.n)) % self.n
        self.initial = self.pos
        self.noise = noise
        self.landmarks = landmarks
        self.steps = 0
        self.limit = self.n * 5
        self.done = False

    @property
    def p_correct(self):
        return .70 if self.noise == "standard" else .48

    @property
    def odo_correct(self):
        return .72 if self.noise == "standard" else .48

    def initial_observation(self):
        return {"beacon": [self.initial, self.goal], "odometry": None, "landmark": None}

    def _landmark(self):
        if not self.landmarks:
            return None
        mark = 0 if self.pos == 0 else 1 if self.pos == self.n//2 else None
        draw = self.rng.random()
        if mark is None:
            return 0 if draw < .01 else 1 if draw < .02 else None
        return mark if draw < .85 else 1-mark if draw < .86 else None

    def step(self, action):
        if self.done:
            raise RuntimeError("episode ended")
        if type(action) is not int or action not in range(3):
            raise ValueError("invalid action")
        previous = self.pos
        self.steps += 1
        event = "move"
        if action == 2:
            delta = 0
            event = "success" if self.pos == self.goal else "miss"
        else:
            intended = ACTIONS[action]
            p = self.rng.random()
            delta = intended if p < self.p_correct else 0 if p < self.p_correct + .20 else -intended
            self.pos = (self.pos + delta) % self.n
            event = "move" if delta == intended else "slip" if delta == 0 else "reverse"
        self.done = (event == "success") or self.steps >= self.limit
        if self.steps == self.limit and event != "success":
            event = "timeout"
        reward = 5.0 if self.pos == self.goal and action == 2 else (-.50 if action == 2 else -.035)
        # Training reward includes environment-provided (not sensed) distance progress.
        if action != 2:
            reward += .12 * (distance(previous, self.goal, self.n) - distance(self.pos, self.goal, self.n))
        if event == "timeout":
            reward -= 1.0
        p = self.rng.random()
        possibilities = (-1, 0, 1)
        other = [x for x in possibilities if x != delta]
        odo = delta if p < self.odo_correct else other[0] if p < (1+self.odo_correct)/2 else other[1]
        return {"beacon": None, "odometry": odo, "landmark": self._landmark()}, reward, self.done, event


def landmark_prob(position, seen, n, enabled):
    if not enabled:
        return 1.0 if seen is None else 0.0
    mark = 0 if position == 0 else 1 if position == n//2 else None
    if mark is None:
        return .98 if seen is None else .01
    return .85 if seen == mark else .01 if seen == 1-mark else .14


class Navigator:
    """Built-in Bayesian motion/landmark filter vs raw odometry ablations."""
    def __init__(self, initial, goal, n, mode, noise, landmarks):
        if mode not in MODES:
            raise ValueError("invalid estimator")
        self.mode, self.noise, self.landmarks = mode, noise, landmarks
        self.n, self.goal = n, goal
        self.probs = [float(i == initial) for i in range(n)]
        self.dead = initial
        self.known = mode != "reactive"

    def advance(self, action, sensed):
        if action not in range(3):
            raise ValueError("invalid action")
        if self.mode == "reactive":
            self.known = False
            return
        odo = sensed["odometry"]
        if self.mode == "dead":
            self.dead = (self.dead + odo) % self.n
            self.probs = [float(i == self.dead) for i in range(self.n)]
            return
        if action == 2:
            candidates = self.probs[:]
        else:
            intended = ACTIONS[action]
            motion_correct = .70 if self.noise == "standard" else .48
            outcomes = ((intended, motion_correct), (0, .20), (-intended, 1-motion_correct-.20))
            candidates = [0.0] * self.n
            odo_correct = .72 if self.noise == "standard" else .48
            for old, prior in enumerate(self.probs):
                for delta, p in outcomes:
                    likelihood = odo_correct if odo == delta else (1-odo_correct)/2
                    candidates[(old+delta) % self.n] += prior*p*likelihood
        candidates = [p*landmark_prob(i, sensed["landmark"], self.n, self.landmarks)
                      for i, p in enumerate(candidates)]
        total = sum(candidates)
        if total <= 0:
            raise RuntimeError("impossible observation")
        self.probs = [p/total for p in candidates]

    def features(self):
        if not self.known:
            return (9, 0, 0)
        position = max(range(self.n), key=lambda k:self.probs[k])
        direction = signed_distance(position, self.goal, self.n)
        pgoal = self.probs[self.goal]
        confidence = 2 if pgoal >= .70 else 1 if pgoal >= .30 else 0
        return (max(-3,min(3,direction)), confidence, int(max(self.probs)*10)//3)

    def heuristic(self):
        if not self.known:
            return 0
        if self.probs[self.goal] >= .45:
            return 2
        losses = []
        for action in (0, 1):
            movement = ACTIONS[action]
            losses.append(sum(p*distance((k+movement)%self.n, self.goal, self.n) for k,p in enumerate(self.probs)))
        return 0 if losses[0] < losses[1] else 1


class RingBrain:
    def __init__(self, db, seed=17, mode="belief"):
        if type(seed) is not int or mode not in MODES:
            raise ValueError("invalid brain configuration")
        db = Path(db)
        db.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db)
        try:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS ring_meta (key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS ring_q (state TEXT NOT NULL,action INTEGER NOT NULL,value REAL NOT NULL,PRIMARY KEY(state,action));
            """)
            meta = dict(self.conn.execute("SELECT key,value FROM ring_meta"))
            if meta and (meta.get("schema") != SCHEMA or meta.get("seed") != str(seed) or meta.get("mode") != mode):
                raise ValueError("incompatible checkpoint")
            self.seed, self.mode = seed, mode
            self.trained = int(meta.get("trained", "0"))
            if self.trained < 0:
                raise ValueError("invalid training counter")
            self.q = {(tuple(json.loads(state)), action):value for state, action, value in self.conn.execute("SELECT state,action,value FROM ring_q")}
            if any(len(s)!=3 or a not in range(3) or not math.isfinite(v) for (s,a),v in self.q.items()):
                raise ValueError("invalid stored policy")
        except Exception:
            self.conn.close()
            raise

    def choose(self, state, rng, epsilon):
        if rng.random() < epsilon:
            return rng.randrange(3)
        vs = [self.q.get((state,a),0) for a in range(3)]
        best = max(vs)
        return rng.choice([a for a,v in enumerate(vs) if v == best])

    def run(self, split, index, policy="learned", noise="standard", landmarks=True, learn=False, trace=False):
        if policy not in POLICIES or split not in ("train", "test") or type(index) is not int or index < 0 or type(landmarks) is not bool:
            raise ValueError("invalid episode")
        if learn and (policy!="learned" or split!="train" or index!=self.trained or noise!="standard" or not landmarks):
            raise ValueError("training mismatch")
        world = RingWorld(self.seed,split,index,noise,landmarks)
        navigator = Navigator(world.initial,world.goal,world.n,self.mode,noise,landmarks)
        rng = random.Random(seed_for(self.seed,split,index,"policy"))
        events = []
        total_reward = 0.
        last = ""
        while not world.done:
            state = navigator.features()
            action = (self.choose(state,rng,max(.06,.60*.9994**index) if learn else 0)
                      if policy=="learned" else navigator.heuristic() if policy=="heuristic"
                      else rng.randrange(3) if policy=="random" else 2 if world.pos==world.goal
                      else 0 if signed_distance(world.pos,world.goal,world.n)<0 else 1)
            observation, reward, done, event = world.step(action)
            navigator.advance(action,observation)
            next_state = navigator.features()
            total_reward += reward
            last = event
            if trace:
                events.append({"state":list(state),"action":action,"observation":observation,
                               "next_state":list(next_state),"reward":round(reward,8),"event":event,"done":done})
            if learn:
                target = reward + (0 if done else .95*max(self.q.get((next_state,a),0.) for a in range(3)))
                old = self.q.get((state,action),0.)
                self.q[state,action] = old + .2*(target-old)
        if learn:
            self.trained += 1
        return {"success":last=="success", "steps":world.steps,"reward":round(total_reward,8),"terminal":last,"events":events if trace else []}

    def train(self, episodes):
        if type(episodes) is not int or episodes < 1:
            raise ValueError("positive training episodes required")
        for _ in range(episodes):
            self.run("train",self.trained,learn=True)
        self.persist()

    def persist(self):
        with self.conn:
            self.conn.execute("DELETE FROM ring_q")
            self.conn.executemany("INSERT INTO ring_q VALUES (?,?,?)", ((canonical(s),a,v) for (s,a),v in self.q.items()))
            self.conn.executemany("INSERT INTO ring_meta(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                                  (("schema",SCHEMA),("seed",str(self.seed)),("mode",self.mode),("trained",str(self.trained))))

    def evaluate(self, episodes=200, policy="learned", noise="standard", landmarks=True):
        if type(episodes) is not int or episodes<1:
            raise ValueError("positive evaluation episodes required")
        runs=[self.run("test",i,policy,noise,landmarks) for i in range(episodes)]
        return {"schema":SCHEMA,"seed":self.seed,"mode":self.mode,"policy":policy,"trained":self.trained,
                "noise":noise,"landmarks":landmarks,"episodes":episodes,
                "success_rate":round(sum(x["success"] for x in runs)/episodes,4),
                "mean_steps":round(sum(x["steps"] for x in runs)/episodes,3)}

    def trace(self,index=0,policy="learned",noise="standard",landmarks=True):
        outcome=self.run("test",index,policy,noise,landmarks,trace=True)
        body={"schema":TRACE_SCHEMA,"seed":self.seed,"mode":self.mode,"index":index,
              "policy":policy,"noise":noise,"landmarks":landmarks,"source":"simulation",
              "scope":"simulation-only","outcome":outcome}
        return {**body,"sha256":hashlib.sha256(canonical(body).encode()).hexdigest()}

    def close(self):
        self.conn.close()

    def __enter__(self):return self
    def __exit__(self,*_):self.close()


def verify_trace(trace):
    if type(trace) is not dict or trace.get("schema")!=TRACE_SCHEMA or trace.get("source")!="simulation" or trace.get("scope")!="simulation-only":
        raise ValueError("invalid trace")
    body={k:v for k,v in trace.items() if k!="sha256"}
    if hashlib.sha256(canonical(body).encode()).hexdigest()!=trace.get("sha256"):
        raise ValueError("incorrect trace digest")
    try:
        world=RingWorld(trace["seed"],"test",trace["index"],trace["noise"],trace["landmarks"])
        nav=Navigator(world.initial,world.goal,world.n,trace["mode"],trace["noise"],trace["landmarks"])
        total=0.
        last=""
        for step in trace["outcome"]["events"]:
            if world.done or list(nav.features())!=step["state"]:
                raise ValueError("invalid prior state")
            obs,reward,done,event=world.step(step["action"])
            nav.advance(step["action"],obs)
            if (obs!=step["observation"] or list(nav.features())!=step["next_state"] or
                round(reward,8)!=step["reward"] or done!=step["done"] or event!=step["event"]):
                raise ValueError("invalid replayed transition")
            last=event
            total+=reward
        outcome=trace["outcome"]
        if (not world.done or outcome["steps"]!=world.steps or len(outcome["events"])!=world.steps or
            outcome["success"]!=(last=="success") or outcome["terminal"]!=last or
            abs(outcome["reward"]-total)>1e-6):
            raise ValueError("invalid reported outcome")
        return {"verified":True,"steps":world.steps,"sha256":trace["sha256"]}
    except (KeyError,IndexError,TypeError,AttributeError,OverflowError) as exc:
        raise ValueError("invalid trace structure") from exc


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=("train","evaluate","trace","verify"))
    parser.add_argument("--db",type=Path,default=Path("uncertain_ring.db"))
    parser.add_argument("--seed",type=int,default=17)
    parser.add_argument("--mode",choices=MODES,default="belief")
    parser.add_argument("--policy",choices=POLICIES,default="learned")
    parser.add_argument("--episodes",type=int,default=200)
    parser.add_argument("--index",type=int,default=0)
    parser.add_argument("--noise",choices=("standard","high"),default="standard")
    parser.add_argument("--no-landmarks",action="store_true")
    parser.add_argument("--trace-file",type=Path)
    args=parser.parse_args()
    if args.command=="verify":
        if args.trace_file is None:parser.error("--trace-file required")
        print(canonical(verify_trace(json.loads(args.trace_file.read_text(encoding="utf-8")))))
    else:
        with RingBrain(args.db,args.seed,args.mode) as brain:
            if args.command=="train":
                brain.train(args.episodes)
                print(canonical({"trained":brain.trained,"mode":brain.mode}))
            elif args.command=="evaluate":
                print(canonical(brain.evaluate(args.episodes,args.policy,args.noise,not args.no_landmarks)))
            else:
                print(canonical(brain.trace(args.index,args.policy,args.noise,not args.no_landmarks)))


if __name__=="__main__":main()
