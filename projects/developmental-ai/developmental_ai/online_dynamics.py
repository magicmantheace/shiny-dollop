"""Latent-state dynamics learned from ordinary action/sensor histories.

The learner never receives actual transitions, positions after reset, simulator
regime names, rewards, or other privileged calibration labels. Initial position
is disclosed by the environment's ordinary first-step beacon. A categorical
forward/backward expectation-maximization procedure estimates motion, odometry,
and landmark likelihoods from sequences of (action, odometry, landmark).

This is still a tightly engineered probabilistic model of a known ring, not
unconstrained autonomous discovery of physics, identity or general intelligence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sqlite3
from pathlib import Path

from developmental_ai.adaptive_dynamics import (
    ACTIONS, CalibrationWorld, DynamicsModel, blank_counts, canonical, index_of, reading_index, seed_for,
)

SCHEMA = "online-dynamics/v1"
DEFAULT_STEPS = 12
MAX_STEPS = 40
MAX_EPISODES = 12000


def trajectory(seed: int, split: str, index: int, noise="standard", layout="fixed", steps=DEFAULT_STEPS):
    """Generate only ordinary sensors; the physics configuration stays private."""
    if type(steps) is not int or not 1 <= steps <= MAX_STEPS:
        raise ValueError("invalid trajectory length")
    world = CalibrationWorld(seed, split, index, noise, layout)
    start = world.initial_observation()["beacon"][0]
    rng = random.Random(seed_for(seed, split, index, "policy"))
    observations = []
    for _ in range(steps):
        action = rng.randrange(2)  # movement only; avoid terminal collection action
        seen, _, _, _ = world.step(action)
        observations.append((ACTIONS[action], seen["odometry"], seen["landmark"]))
    return {"n": world.n, "initial": start, "observations": observations}


def validate_history(history):
    if type(history) is not dict or set(history) != {"n", "initial", "observations"}:
        raise ValueError("invalid observation record")
    n, initial, obs = history["n"], history["initial"], history["observations"]
    if type(n) is not int or n not in (9,11) or type(initial) is not int or not 0 <= initial < n:
        raise ValueError("invalid initial beacon")
    if type(obs) not in (list,tuple) or not 1 <= len(obs) <= MAX_STEPS:
        raise ValueError("invalid observation sequence length")
    for step in obs:
        if type(step) not in (list,tuple) or len(step) != 3:
            raise ValueError("invalid observed action")
        command, odo, landmark = step
        if type(command) is not int or command not in (-1,1):
            raise ValueError("invalid action")
        index_of(odo)
        reading_index(landmark)
    return n, initial, obs


def initial_model():
    """Generic symmetric initial assumptions, without ground-truth labels."""
    counts = blank_counts()
    counts["motion"] = [[7.,2.,1.], [7.,2.,1.]]
    counts["odo"] = [[1.,1.,7.], [1.,7.,1.], [7.,1.,1.]]
    for rows in counts["landmark"].values():
        for row in rows:
            row[:] = [12., .15, .15]
    return DynamicsModel(counts)


def _weights(model, n, old, command, odo, mark):
    m = model.motion_probs(command)
    for cls, delta in enumerate((command,0,-command)):
        dest=(old+delta)%n
        yield cls,delta,dest,(m[cls]*model.odo_probs(delta)[index_of(odo)]
                              *model.landmark_probs(n,dest)[reading_index(mark)])


def forward_backward(model: DynamicsModel, history, counts=None):
    """Return marginal observation log likelihood and optionally EM soft counts."""
    n, initial, observations=validate_history(history)
    alpha=[[float(p==initial) for p in range(n)]]
    scalings=[]
    for command,odo,landmark in observations:
        nxt=[0.] * n
        for old,prior in enumerate(alpha[-1]):
            if prior:
                for _,_,dest,weight in _weights(model,n,old,command,odo,landmark):
                    nxt[dest]+=prior*weight
        norm=sum(nxt)
        if norm <= 0 or not math.isfinite(norm):
            raise ValueError("invalid likelihood")
        alpha.append([v/norm for v in nxt])
        scalings.append(norm)
    ll=sum(math.log(x) for x in scalings)
    if counts is None:
        return ll
    beta=[1.] * n
    for t in range(len(observations)-1,-1,-1):
        command,odo,landmark=observations[t]
        earlier=[0.] * n
        divisor=scalings[t]
        for old in range(n):
            for cls,delta,dest,weight in _weights(model,n,old,command,odo,landmark):
                posterior=alpha[t][old]*weight*beta[dest]/divisor
                counts["motion"][0 if command==-1 else 1][cls]+=posterior
                counts["odo"][index_of(delta)][index_of(odo)]+=posterior
                counts["landmark"][str(n)][dest][reading_index(landmark)]+=posterior
                earlier[old]+=weight*beta[dest]/divisor
        beta=earlier
    return ll


def fit(histories, *, iterations=12, start=None):
    if type(histories) not in (list,tuple) or not 1 <= len(histories) <= MAX_EPISODES:
        raise ValueError("invalid training histories")
    if type(iterations) is not int or not 1 <= iterations <= 50:
        raise ValueError("invalid optimizer iterations")
    for h in histories:
        validate_history(h)
    model=initial_model() if start is None else DynamicsModel(json.loads(canonical(start.counts)))
    log_likelihood=[]
    for _ in range(iterations):
        expected=blank_counts()
        before=sum(forward_backward(model,h,expected) for h in histories)
        model=DynamicsModel(expected)
        log_likelihood.append(round(before,5))
    return model,log_likelihood


def score(model, histories):
    if not histories:
        raise ValueError("no histories")
    return sum(forward_backward(model,h) for h in histories)/sum(len(h["observations"]) for h in histories)


class ModelBank:
    """Immutable model bank; choose model via unsupervised observation likelihood."""
    def __init__(self, db, seed=17):
        if type(seed) is not int:
            raise ValueError("invalid seed")
        path=Path(db)
        path.parent.mkdir(parents=True,exist_ok=True)
        self.conn=sqlite3.connect(path)
        try:
            self.conn.execute("CREATE TABLE IF NOT EXISTS online_models (name TEXT PRIMARY KEY, schema TEXT NOT NULL, seed INTEGER NOT NULL, histories INTEGER NOT NULL, counts TEXT NOT NULL, digest TEXT NOT NULL)")
            self.seed=seed
        except Exception:
            self.conn.close()
            raise

    @staticmethod
    def _check_name(name):
        if type(name) is not str or not 1 <= len(name) <= 40 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in name):
            raise ValueError("invalid model name")

    def save(self,name,model,histories):
        self._check_name(name)
        model.validate()
        if type(histories) is not int or histories < 1:
            raise ValueError("invalid history count")
        contents=canonical(model.counts)
        digest=hashlib.sha256(contents.encode()).hexdigest()
        with self.conn:
            self.conn.execute("INSERT INTO online_models VALUES(?,?,?,?,?,?)",(name,SCHEMA,self.seed,histories,contents,digest))
        return digest

    def get(self,name):
        self._check_name(name)
        row=self.conn.execute("SELECT schema,seed,histories,counts,digest FROM online_models WHERE name=?",(name,)).fetchone()
        if row is None:
            raise ValueError("unknown model")
        schema,seed,histories,contents,digest=row
        if schema!=SCHEMA or seed!=self.seed or type(histories) is not int or histories<1 or hashlib.sha256(contents.encode()).hexdigest()!=digest:
            raise ValueError("invalid or incompatible model")
        return DynamicsModel(json.loads(contents))

    def select(self,histories):
        if type(histories) not in (list,tuple) or not histories:
            raise ValueError("invalid selection evidence")
        for h in histories:
            validate_history(h)
        names=[r[0] for r in self.conn.execute("SELECT name FROM online_models ORDER BY name")]
        if not names:
            raise ValueError("no models available")
        scores={name:score(self.get(name),histories) for name in names}
        selected=max(sorted(scores),key=lambda name:scores[name])
        return {"selected":selected,"mean_log_likelihoods":{k:round(v,6) for k,v in sorted(scores.items())}}

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self,*_):
        self.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("command",choices=("train","select"))
    p.add_argument("--db",type=Path,default=Path("online-models.db"))
    p.add_argument("--seed",type=int,default=17)
    p.add_argument("--name",default="standard")
    p.add_argument("--noise",choices=("standard","high"),default="standard")
    p.add_argument("--layout",choices=("fixed","shifted"),default="fixed")
    p.add_argument("--episodes",type=int,default=500)
    p.add_argument("--steps",type=int,default=12)
    p.add_argument("--iterations",type=int,default=12)
    args=p.parse_args()
    if not 1<=args.episodes<=MAX_EPISODES:
        p.error("episode count out of range")
    histories=[trajectory(args.seed,"train" if args.command=="train" else "test",i,args.noise,args.layout,args.steps) for i in range(args.episodes)]
    with ModelBank(args.db,args.seed) as bank:
        if args.command=="train":
            model,curve=fit(histories,iterations=args.iterations)
            print(canonical({"schema":SCHEMA,"name":args.name,"digest":bank.save(args.name,model,len(histories)),"log_likelihood_curve":curve,"scope":"simulation-only"}))
        else:
            print(canonical({"schema":SCHEMA,"episodes":args.episodes,"selection":bank.select(histories)}))


if __name__=="__main__":
    main()
