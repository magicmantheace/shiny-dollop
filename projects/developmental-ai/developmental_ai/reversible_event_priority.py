"""Experimental reward-driven event selection across unannounced goal reversals.

An explicitly bounded one-event-at-a-time contextual bandit. A bank retains
per-context reward hypotheses and may start/revisit one after surprising
outcomes. The segmenter and four latent event labels are engineering priors.
Only a public context, raw tokens, a proposed span and a terminal boolean enter
training. Neither private goal, true event boundary nor phase enters this API.
Checkpoints replay actions and feedback; SHA-256 is NOT authentication.
"""
from __future__ import annotations

import hashlib
import json
import math

from developmental_ai.environment_api import canonical, digest
from developmental_ai.event_segmentation import EventSegmentationModel, check_stream

SCHEMA = "developmental-ai.reversible-event-priority/v1"
MODES = ("bank", "cumulative", "window", "frozen")
MAX_EVENTS = 450
WINDOW = 32
MAX_BANK = 3


def _counts(events, context):
    counts = [[0, 0] for _ in range(4)]
    for e in events:
        if e["context"] == context:
            wins, total = counts[e["chosen"]["label"]]
            counts[e["chosen"]["label"]] = [wins + int(e["success"]), total + 1]
    return counts


def _prob(counts, label):
    w, n = counts[label]
    return (w + 1) / (n + 2)


def _stable_random(seed, index, count):
    h = hashlib.sha256(f"{SCHEMA}/{seed}/{index}".encode()).digest()
    return int.from_bytes(h[:8], "big") % count


class ReversibleEventPriority:
    """Reward-only priority learner with no runtime access to private goals.

    The active expert is selected separately per public context. Bank entries
    are never erased: on an outcome surprise the selector can restore a prior
    bank entry or open one fresh hypothesis (at most three). The comparator
    modes are cumulative, recent-window, and initial frozen evidence.
    """

    def __init__(self, model, *, seed, mode="bank"):
        if (not isinstance(model, EventSegmentationModel) or type(seed) is not int or
                mode not in MODES):
            raise ValueError("invalid model/seed/priority mode")
        self.model = EventSegmentationModel.restore(model.record())
        self.model_sha = self.model.record()["sha256"]
        self.seed, self.mode = seed, mode
        self.events = []
        self.pending = None
        self.banks = {0: [[[0,0] for _ in range(4)]], 1: [[[0,0] for _ in range(4)]]}
        self.active = {0:0, 1:0}
        self.recent = {0:[], 1:[]}
        self.switches = []

    def _check(self, context, tokens):
        if self.model.record()["sha256"] != self.model_sha:
            raise ValueError("event segmenter mutated")
        if type(context) is not int or context not in (0,1):
            raise ValueError("invalid public context")
        check_stream(tokens)
        return self.model.spans(tokens)

    def _mode_counts(self, context):
        if self.mode == "bank":
            return self.banks[context][self.active[context]]
        if self.mode == "window":
            return _counts(self.recent[context][-WINDOW:], context)
        if self.mode == "frozen":
            return _counts(self.events[:200], context)
        return _counts(self.events, context)

    def _choose(self, context, tokens, *, training, index):
        spans = self._check(context, tokens)
        counts = self._mode_counts(context)
        # Train-only exploration; deterministic from public indices.
        if training and _stable_random(self.seed, index+711, 7) == 0:
            pick = _stable_random(self.seed, index+913, len(spans))
        else:
            pick = max(range(len(spans)),key=lambda i:(
                _prob(counts, spans[i]["label"]), -spans[i]["start"]))
        item = spans[pick]
        return {"start":item["start"], "end":item["end"],
                "label":item["label"], "center":(item["start"]+item["end"]-1)//2}

    def propose(self, context, tokens, *, split, index):
        if (self.pending is not None or split != "train" or type(index) is not int or
                index < 0 or index >= 1_000_000 or len(self.events) >= MAX_EVENTS or
                (self.events and index <= self.events[-1]["index"])):
            raise ValueError("invalid training proposal ordering")
        decision = self._choose(context, tokens, training=True, index=index)
        self.pending={"context":context,"tokens":list(tokens),"index":index,"chosen":decision}
        return dict(decision)

    def feedback(self, success, *, split, index):
        if (self.pending is None or type(success) is not bool or split != "train" or
                type(index) is not int or index != self.pending["index"]):
            raise ValueError("unexpected or invalid reward")
        e = {**self.pending, "success":success}
        context, label = e["context"], e["chosen"]["label"]
        if self.mode == "bank":
            current=self.banks[context][self.active[context]][label]
            current[0]+=int(success);current[1]+=1
        self.events.append(e)
        self.recent[context].append(e)
        self.pending=None
        if self.mode == "bank":
            self._maybe_switch(context)

    def _maybe_switch(self, context):
        history=self.recent[context]
        if len(history)<8:return
        recent=history[-12:]
        n=len(recent)
        # Compare alternative remembered hypotheses on ACTUALLY chosen labels;
        # this is off-policy likelihood scoring, not observed counterfactual reward.
        def log_likelihood(bank):
            return sum(math.log(max(.08,min(.92,
                _prob(bank, e["chosen"]["label"]) if e["success"] else
                1-_prob(bank,e["chosen"]["label"])))) for e in recent)
        options=self.banks[context]
        active=self.active[context]
        scores=[log_likelihood(entry) for entry in options]
        best=max(range(len(options)),key=lambda j:(scores[j],-j))
        if best!=active and scores[best]-scores[active]>=2.0 and n>=8:
            self.active[context]=best
            self.switches.append([len(self.events),context,active,best,"recall"])
            return
        # A sustained run of surprising terminal failures is evidence against
        # the active hypothesis. Preserve it and try a bounded fresh expert.
        failures=sum(not e["success"] for e in recent[-8:])
        seen=sum(x[1] for x in options[active])
        if (len(options)<MAX_BANK and seen>=18 and failures>=7 and
                sum(_prob(options[active],e["chosen"]["label"]) for e in recent[-8:])/8 >=.42):
            options.append([[0,0] for _ in range(4)])
            self.active[context]=len(options)-1
            self.switches.append([len(self.events),context,active,self.active[context],"new"])
            self.recent[context]=[]  # compare fresh regime against fresh evidence

    def choose(self, context, tokens):
        if self.pending is not None or not self.events:
            raise ValueError("untrained or pending learning step")
        return self._choose(context,tokens,training=False,index=0)

    def record(self):
        if self.pending is not None or not self.events:
            raise ValueError("pending or untrained priority bank")
        if self.model.record()["sha256"] != self.model_sha:
            raise ValueError("underlying segmenter mutated")
        state={"schema":SCHEMA,"model_sha256":self.model_sha,"seed":self.seed,
               "mode":self.mode,"events":self.events,"banks":self.banks,
               "active":self.active,"switches":self.switches}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls, saved, model):
        if (type(saved) is not dict or set(saved)!={"state","sha256"} or
                type(saved["state"]) is not dict or type(saved["sha256"]) is not str or
                digest(saved["state"])!=saved["sha256"]):
            raise ValueError("invalid or modified checkpoint")
        s=saved["state"]
        if (set(s)!={"schema","model_sha256","seed","mode","events","banks","active","switches"} or
                s["schema"]!=SCHEMA or type(s["events"]) is not list or
                not 1<=len(s["events"])<=MAX_EVENTS):
            raise ValueError("incompatible checkpoint")
        x=cls(model,seed=s["seed"],mode=s["mode"])
        if x.model_sha!=s["model_sha256"]:raise ValueError("wrong segmenter")
        for e in s["events"]:
            if type(e) is not dict or set(e)!={"context","tokens","index","chosen","success"}:
                raise ValueError("malformed evidence event")
            choice=x.propose(e["context"],e["tokens"],split="train",index=e["index"])
            if choice!=e["chosen"]:raise ValueError("unreplayable training action")
            x.feedback(e["success"],split="train",index=e["index"])
        if x.record()!=saved:raise ValueError("checkpoint diverges from recorded evidence")
        return x
