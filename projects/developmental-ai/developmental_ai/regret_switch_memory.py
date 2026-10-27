"""Prequential regret-based hard choice of remembered source and recency models.

A measured alternative to soft-probability mixing. For each of eight public
outcomes, prediction probabilities are obtained from relation models fitted
ONLY on earlier events. Contradictions and source recovery are author-defined
criteria, not learned latent rules, evidence authentication, or safety.
"""
from __future__ import annotations

import json
import math

from developmental_ai.prequential_ensemble_memory import (
    PrequentialEnsembleMemory, SOURCE, WARMUP, VALIDATION, WINDOWS
)
from developmental_ai.observable_affordances import MAX_SAMPLES, canonical, digest

SCHEMA="developmental-ai.regret-switch-memory/v1"
FAST_TAIL=4
SURPRISE_P=0.125
FAST_ERRORS=2
SOURCE_SUPPORT_P=0.55
SOURCE_RATIO=2.0
SOURCE_SUPPORT_MIN=2
SOURCE_REGRET_MARGIN=1.0
LONG_REGRET_MARGIN=1.0
LONG_SURPRISE_MIN=12


class RegretSwitchMemory(PrequentialEnsembleMemory):
    """Choose a single action model using public out-of-sample regret."""

    def selection(self):
        if self._cache is not None:
            return self._cache
        if len(self.events)<WARMUP:
            raise ValueError("insufficient public source outcomes")
        archive=self._model(self.events[:SOURCE])
        recent8=self._model(self.events[-WINDOWS[0]:])
        recent32=self._model(self.events[-WINDOWS[1]:])
        logscore=[0.0,0.0,0.0]
        newest=[]
        for i in range(len(self.events)-VALIDATION,len(self.events)):
            event=self.events[i]
            fitted=[archive,
                    self._model(self.events[i-WINDOWS[0]:i]),
                    self._model(self.events[i-WINDOWS[1]:i])]
            ps=[self._observed_likelihood(m,event) for m in fitted]
            if any(not math.isfinite(p) or p<=0 for p in ps):
                raise ValueError("bad prequential probabilities")
            for index,p in enumerate(ps):
                logscore[index]+=math.log(p)
            newest.append(ps)
        tail=newest[-FAST_TAIL:]
        conflicts=sum(int(p[0]<SURPRISE_P) for p in tail)
        return_support=sum(int(p[0]>=SOURCE_SUPPORT_P and
                               p[0]>=SOURCE_RATIO*p[1]) for p in tail)
        long_conflicts=sum(int(self._observed_likelihood(archive,e)<SURPRISE_P)
                           for e in self.events[-WINDOWS[1]:])
        if conflicts>=FAST_ERRORS:
            use_source=False
            reason="archive_contradicted"
        elif return_support>=SOURCE_SUPPORT_MIN:
            use_source=True
            reason="source_predictive_support"
        elif logscore[0]-logscore[1]>SOURCE_REGRET_MARGIN:
            use_source=True
            reason="source_lower_prequential_regret"
        else:
            use_source=False
            reason="recent_lower_prequential_regret"
        if use_source:
            name="source192"
            chosen=archive
        elif (logscore[2]-logscore[1]>=LONG_REGRET_MARGIN and
              long_conflicts>=LONG_SURPRISE_MIN):
            name="recent32"
            chosen=recent32
        else:
            name="recent8"
            chosen=recent8
        decision={
            "source":name,
            "reason":reason,
            "prequential_scores":[round(v,6) for v in logscore],
            "prequential_scoring_events":VALIDATION,
            "predictor_training_overlap":0,
            "source_conflicts_latest4":conflicts,
            "source_support_latest4":return_support,
            "source_conflicts_latest32":long_conflicts,
            "recorded_events":len(self.events),
            "source_retained":True,
        }
        self._cache=(decision,chosen)
        return self._cache

    def choose(self,frame):
        # Inherit exact strict public frame validation and avoid any
        # simulation-privileged world information.
        from developmental_ai.observable_affordances import VariableOutcomeMemory
        VariableOutcomeMemory().choose(frame)
        if frame["done"]:
            return None
        _,model=self.selection()
        return model.choose(frame)

    def record(self):
        if not self.events:
            raise ValueError("untrained regret selector")
        state={"schema":SCHEMA,"events":self.events}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls,record):
        if (type(record) is not dict or set(record)!={"state","sha256"}
                or type(record["state"]) is not dict
                or type(record["sha256"]) is not str
                or digest(record["state"])!=record["sha256"]):
            raise ValueError("invalid regret checkpoint hash")
        state=record["state"]
        if (set(state)!={"schema","events"} or state["schema"]!=SCHEMA
                or type(state["events"]) is not list or
                not 1<=len(state["events"])<=MAX_SAMPLES):
            raise ValueError("invalid regret checkpoint structure")
        m=cls()
        for e in state["events"]:
            m.observe(e)
        if m.record()!=record:
            raise ValueError("regret checkpoint replay mismatch")
        return m
