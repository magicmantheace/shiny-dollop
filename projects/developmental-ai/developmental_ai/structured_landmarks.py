"""Small structured landmark map inferred from *unlabelled* ring trajectories.

Assumptions, NOT learned discoveries: two distinguishable landmarks lie n//2
positions apart on a known 9/11 ring; background and landmark sensors have
three shared categorical emission types. Their *offset* and observation noise,
plus motion and odometry, are fitted without hidden positions after the beacon.
No simulator reward, regime labels, external tools or permission changes.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path

from developmental_ai.adaptive_dynamics import DynamicsModel, blank_counts, canonical, index_of
from developmental_ai.online_dynamics import forward_backward, validate_history

SCHEMA="structured-landmarks/v1"
INIT_ROLES=((30., .1, .1), (2., 25., .1), (2., .1, 25.))
MAX_HISTORIES=2400


def checksum(data):
    return hashlib.sha256(canonical(data).encode()).hexdigest()


def _offsets_valid(offsets):
    return (type(offsets) is dict and set(offsets)=={"9", "11"} and
            all(type(offsets[str(n)]) is int and 0<=offsets[str(n)]<n for n in (9,11)))


class StructuredModel:
    """Three position-independent emission roles tied to a learned ring offset."""
    def __init__(self, offsets=None, motion=None, odo=None, roles=None):
        self.offsets={"9":0,"11":0} if offsets is None else offsets
        self.motion=[[7.,2.,1.],[7.,2.,1.]] if motion is None else motion
        self.odo=[[7.,1.,1.],[1.,7.,1.],[1.,1.,7.]] if odo is None else odo
        self.roles=[list(r) for r in INIT_ROLES] if roles is None else roles
        self.validate()

    def validate(self):
        if not _offsets_valid(self.offsets):raise ValueError("invalid map offsets")
        for matrix,rows in ((self.motion,2),(self.odo,3),(self.roles,3)):
            if (type(matrix) is not list or len(matrix)!=rows or
                any(type(row) is not list or len(row)!=3 or
                    any(type(v) not in (int,float) or not math.isfinite(v) or v<0 or v>1e8 for v in row)
                    for row in matrix)):
                raise ValueError("invalid model probabilities")

    def motion_probs(self,cmd):
        if type(cmd) is not int or cmd not in (-1,1):raise ValueError("invalid command")
        return DynamicsModel.probs(self.motion[0 if cmd==-1 else 1])

    def odo_probs(self,delta):
        return DynamicsModel.probs(self.odo[index_of(delta)])

    def role(self,n,pos):
        if type(n) is not int or n not in (9,11) or type(pos) is not int or not 0<=pos<n:
            raise ValueError("invalid position")
        origin=self.offsets[str(n)]
        if pos==origin:return 1
        if pos==(origin+n//2)%n:return 2
        return 0

    def landmark_probs(self,n,pos):
        return DynamicsModel.probs(self.roles[self.role(n,pos)])

    def state(self):
        return {"schema":SCHEMA,"offsets":self.offsets,"motion":self.motion,"odo":self.odo,"roles":self.roles}

    def record(self,seed):
        if type(seed) is not int:raise ValueError("invalid seed")
        state={**self.state(),"seed":seed}
        return {"state":state,"digest":checksum(state)}

    @classmethod
    def from_record(cls,record,seed):
        if (type(record) is not dict or set(record)!={"state","digest"} or
                type(record["state"]) is not dict or set(record["state"])!={"schema","seed","offsets","motion","odo","roles"} or
                record["state"]["schema"]!=SCHEMA or type(record["state"]["seed"]) is not int or
                record["state"]["seed"]!=seed or
                type(record["digest"]) is not str or checksum(record["state"])!=record["digest"]):
            raise ValueError("invalid or incompatible learned model")
        s=record["state"]
        return cls(s["offsets"],s["motion"],s["odo"],s["roles"])


def select_offsets(histories,model):
    """Choose landmark locations using only marginal sensor history likelihood."""
    by_n={n:[] for n in (9,11)}
    for h in histories:
        n,_,_=validate_history(h)
        by_n[n].append(h)
    if any(not group for group in by_n.values()):
        raise ValueError("need samples of both known ring sizes")
    offsets={}
    for n,group in by_n.items():
        candidates=[]
        for offset in range(n):
            model.offsets[str(n)]=offset
            likelihood=sum(forward_backward(model,h) for h in group)
            candidates.append(likelihood)
        offsets[str(n)]=max(range(n),key=lambda o:(candidates[o],-o))
        model.offsets[str(n)]=offsets[str(n)]
    return offsets


def fit_structured(histories,*,iterations=6,select_map=True):
    """Latent forward/backward EM; offsets selected from *training* histories.

    Baseline samples and optimizer passes must be matched in evaluations.
    Known two-site geometry is an inductive bias, not learned representation.
    """
    if type(histories) not in (list,tuple) or not 2<=len(histories)<=MAX_HISTORIES:
        raise ValueError("invalid fit histories")
    if type(iterations) is not int or not 1<=iterations<=30 or type(select_map) is not bool:
        raise ValueError("invalid fit parameters")
    for h in histories:validate_history(h)
    model=StructuredModel()
    curves=[]
    if select_map:select_offsets(histories,model)
    for _ in range(iterations):
        expected=blank_counts()
        likelihood=sum(forward_backward(model,h,expected) for h in histories)
        role_counts=[[0.]*3 for _ in range(3)]
        for n in (9,11):
            for pos,counts in enumerate(expected["landmark"][str(n)]):
                r=model.role(n,pos)
                for i,v in enumerate(counts):role_counts[r][i]+=v
        # Dirichlet regularization: preserve sparse-map identity when coverage
        # is poor. These fixed priors are part of the declared inductive bias.
        model=StructuredModel(dict(model.offsets),
                              [[x+.05 for x in row] for row in expected["motion"]],
                              [[x+.05 for x in row] for row in expected["odo"]],
                              [[role_counts[r][i]+.05*INIT_ROLES[r][i] for i in range(3)] for r in range(3)])
        curves.append(round(likelihood,6))
    return model,curves


class ModelStorage:
    """One local, seed-bound, versioned, checked checkpoint; never approves rollout."""
    def __init__(self,path):
        p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(p)
        self.db.execute("CREATE TABLE IF NOT EXISTS structured_state (id INTEGER PRIMARY KEY CHECK(id=1), record TEXT NOT NULL)")

    def save(self,model,seed):
        if not isinstance(model,StructuredModel):raise ValueError("invalid model")
        model.validate()
        payload=canonical(model.record(seed))
        with self.db:
            self.db.execute("INSERT INTO structured_state(id,record) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET record=excluded.record",(payload,))

    def load(self,seed):
        row=self.db.execute("SELECT record FROM structured_state WHERE id=1").fetchone()
        if not row:return None
        try:return StructuredModel.from_record(json.loads(row[0]),seed)
        except (TypeError,KeyError,json.JSONDecodeError) as e:raise ValueError("invalid model checkpoint") from e

    def close(self):self.db.close()
    def __enter__(self):return self
    def __exit__(self,*_):self.close()
