"""Optional numeric observation/outcome learning across generated sandbox tasks.

No hidden action name is included in a feature or an agent decision. The
simulator's engineered two-number physical measurements encode a simple shared
feature-to-outcome rule; this is NOT causal discovery or real-world safety.
"""
from __future__ import annotations

import hashlib
import json
import random

SCHEMA = "developmental-ai.observable-affordance/v1"
MODEL_SCHEMA = "developmental-ai.numeric-outcome-memory/v1"
DOMAINS = ("collect", "route", "route-reversed")
MAX_SAMPLES = 1000


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",", ":"),allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def feature_check(feature):
    if (type(feature) is not list or len(feature)!=2 or
        any(type(v) is not int or not 0<=v<=8 for v in feature)):
        raise ValueError("invalid observed numeric features")
    return feature


def check(frame):
    if (type(frame) is not dict or set(frame)!={"schema","episode","tick",
        "budget","sensors","goal","actions","done"} or frame["schema"]!=SCHEMA
        or type(frame["episode"]) is not str or len(frame["episode"])!=64
        or any(c not in "0123456789abcdef" for c in frame["episode"])
        or type(frame["tick"]) is not int or type(frame["budget"]) is not int
        or not 0<=frame["tick"]<=frame["budget"]<=8
        or type(frame["goal"]) is not int or not 1<=frame["goal"]<=4
        or type(frame["done"]) is not bool
        or type(frame["sensors"]) is not list or len(frame["sensors"])!=2
        or any(type(v) is not int or v<0 or v>4 for v in frame["sensors"])
        or type(frame["actions"]) is not list or len(frame["actions"])>12
        or (frame["done"] and frame["actions"])):
        raise ValueError("invalid observable sandbox frame")
    seen=set()
    for row in frame["actions"]:
        if (type(row) is not dict or set(row)!={"id","features"} or
            type(row["id"]) is not str or len(row["id"])!=20 or
            not row["id"].startswith("a_") or
            any(c not in "0123456789abcdef" for c in row["id"][2:]) or
            row["id"] in seen):
            raise ValueError("invalid opaque action handle")
        seen.add(row["id"])
        feature_check(row["features"])
    return frame


class ObservableWorld:
    """Independent per-episode identifiers; observable physical measurements.

    Simulator sees the engineered rule. Learner never receives domain or rule.
    Actions of the three outcome kinds are sampled without replacement from
    the same 9x9 numeric lattice, ensuring a feasible but nontrivial task.
    """
    def __init__(self,seed,split,index,domain):
        if (type(seed) is not int or split not in ("train","test") or
            type(index) is not int or not 0<=index<100000 or domain not in DOMAINS):
            raise ValueError("invalid synthetic episode")
        self.episode=digest([SCHEMA,seed,split,index,domain])
        rng=random.Random(int(self.episode[:16],16))
        self.goal=3 if domain=="collect" else 4
        self.budget=6 if domain=="collect" else 7
        self.tick=0
        self.progress=0
        self.damage=0
        self.done=False
        self._domain=domain
        lattice=[(a,b) for a in range(9) for b in range(9)]
        progress=[pair for pair in lattice if pair[1]>=pair[0]+2]
        hazard=[pair for pair in lattice if pair[0]>=pair[1]+2]
        neutral=[pair for pair in lattice if abs(pair[0]-pair[1])<2]
        is_reversed=domain=="route-reversed"
        if is_reversed:progress,hazard=hazard,progress
        count=5 if domain=="collect" else 6
        chosen=(rng.sample(progress,count)+rng.sample(hazard,3 if domain=="collect" else 4)
                +rng.sample(neutral,2))
        rng.shuffle(chosen)
        names=[f"a_{rng.getrandbits(72):018x}" for _ in chosen]
        if len(set(names))!=len(names):
            raise RuntimeError("opaque handle collision")
        self._features=dict(zip(names,chosen))
        self._used=set()

    def frame(self):
        rows=[{"id":handle,"features":list(feature)} for handle,feature in self._features.items()
              if handle not in self._used] if not self.done else []
        return check({"schema":SCHEMA,"episode":self.episode,"tick":self.tick,
                      "budget":self.budget,"goal":self.goal,
                      "sensors":[self.progress,self.damage],"actions":rows,"done":self.done})

    def step(self,action,tick):
        if (self.done or type(tick) is not int or tick!=self.tick
            or type(action) is not str or action not in self._features
            or action in self._used):
            raise ValueError("invalid or stale simulated action")
        x,y=self._features[action]
        if self._domain=="route-reversed":x,y=y,x
        if y>=x+2:self.progress+=1
        elif x>=y+2:self.damage+=1
        self._used.add(action)
        self.tick+=1
        self.done=(self.damage>0 or self.progress>=self.goal or
                   self.tick>=self.budget or len(self._used)==len(self._features))
        return self.frame()

    def success(self):
        return self.progress>=self.goal and self.damage==0


def outcome(before,action,after):
    check(before);check(after)
    handles={row["id"]:row["features"] for row in before["actions"]}
    if (type(action) is not str or action not in handles or
        before["episode"]!=after["episode"] or
        after["tick"]!=before["tick"]+1 or
        after["budget"]!=before["budget"] or after["goal"]!=before["goal"] or
        (not after["done"] and set(r["id"] for r in after["actions"])!=set(handles)-{action})):
        raise ValueError("invalid public sensor transition")
    delta=[v-u for u,v in zip(before["sensors"],after["sensors"])]
    if (any(v not in (0,1) for v in delta) or sum(delta)>1 or
        (not after["done"] and not after["actions"])):
        raise ValueError("invalid public outcome change")
    return {"features":list(handles[action]),"progress":bool(delta[0]),
            "damage":bool(delta[1])}


class NumericOutcomeMemory:
    """Exact replayable public measurements, no action-name identities."""
    def __init__(self):
        self.examples=[]

    def add(self,event):
        if (type(event) is not dict or set(event)!={"features","progress","damage"}
            or type(event["progress"]) is not bool or type(event["damage"]) is not bool
            or (event["progress"] and event["damage"]) or
            len(self.examples)>=MAX_SAMPLES):
            raise ValueError("invalid or oversized observed training evidence")
        feature_check(event["features"])
        self.examples.append(json.loads(canonical(event)))

    def estimate(self,features):
        feature_check(features)
        if not self.examples:
            return {"progress":0.0,"damage":0.0,"evidence":0}
        neighbors=sorted(enumerate(self.examples),key=lambda item:(
            (features[0]-item[1]["features"][0])**2+
            (features[1]-item[1]["features"][1])**2,item[0]))[:5]
        # Five nearest examples with deterministic squared-distance tie break.
        return {"progress":sum(int(r["progress"]) for _,r in neighbors)/len(neighbors),
                "damage":sum(int(r["damage"]) for _,r in neighbors)/len(neighbors),
                "evidence":len(neighbors)}

    def choose(self,frame):
        check(frame)
        if frame["done"]:
            return None
        ranked=[]
        for row in frame["actions"]:
            prediction=self.estimate(row["features"])
            # Explicit, hand-authored loss asymmetry: avoid injury first.
            score=prediction["progress"]*3-prediction["damage"]*10
            ranked.append((-score,row["id"]))
        return min(ranked)[1] if ranked else None

    def record(self):
        if not self.examples:
            raise ValueError("untrained public outcome model")
        state={"schema":MODEL_SCHEMA,"events":self.examples}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls,record):
        if (type(record) is not dict or set(record)!={"state","sha256"} or
            type(record["state"]) is not dict or
            record["sha256"]!=digest(record["state"])):
            raise ValueError("invalid evidence checkpoint integrity")
        state=record["state"]
        if (set(state)!={"schema","events"} or state["schema"]!=MODEL_SCHEMA or
            type(state["events"]) is not list or not 1<=len(state["events"])<=MAX_SAMPLES):
            raise ValueError("invalid public memory schema")
        memory=cls()
        for row in state["events"]:memory.add(row)
        if memory.record()!=record:
            raise ValueError("cannot replay numeric observation memory")
        return memory


# Optional continual-learning extension. The original NumericOutcomeMemory and
# its behavior stay unchanged, including all existing transfer regressions.
REGIME_SCHEMA = "developmental-ai.regime-retrieval/v1"
REGIME_CHUNK = 64
REGIME_TAIL = 12
REGIME_SMOOTHING = 0.05


class RegimeRetrievalMemory:
    """Retrieve earlier *experienced* action-outcome rules without regime labels.

    Records contain only a sequential stream of public numeric outcomes; neither
    environment names, phase boundaries, nor true simulator dynamics are supplied.
    Complete disjoint 64-event chunks are candidate memories. The most recent
    12 events *outside every candidate chunk* rank candidates by predictive
    likelihood. This is not a drift detector, causal discovery or an authenticity
    guarantee; fixed block and feedback budgets are hand-engineered priors.
    """

    def __init__(self):
        self.events = []
        self._cache = None

    def observe(self, event):
        if len(self.events) >= MAX_SAMPLES:
            raise ValueError("continual memory exceeds bounded sample budget")
        # Reuse the established public-outcome schema, including bool checks.
        probe = NumericOutcomeMemory()
        probe.add(event)
        self.events.append(probe.examples[0])
        self._cache = None

    @staticmethod
    def _category(event):
        return 0 if event["progress"] else 1 if event["damage"] else 2

    @staticmethod
    def _likelihood(memory, event):
        import math
        estimate = memory.estimate(event["features"])
        neutral = max(0.0, 1.0 - estimate["progress"] - estimate["damage"])
        scores = (estimate["progress"] + REGIME_SMOOTHING,
                  estimate["damage"] + REGIME_SMOOTHING,
                  neutral + REGIME_SMOOTHING)
        return math.log(scores[RegimeRetrievalMemory._category(event)]
                        / sum(scores))

    def selection(self):
        """Return an evidence-ranked block index; no feedback is consumed."""
        if len(self.events) < REGIME_CHUNK + REGIME_TAIL:
            raise ValueError("insufficient independent retrieval evidence")
        if self._cache is not None:
            return dict(self._cache[0])
        tail = self.events[-REGIME_TAIL:]
        n = (len(self.events) - REGIME_TAIL) // REGIME_CHUNK
        scores = []
        for index in range(n):
            memory = NumericOutcomeMemory()
            for event in self.events[index * REGIME_CHUNK:(index + 1) * REGIME_CHUNK]:
                memory.add(event)
            scores.append((sum(self._likelihood(memory, e) for e in tail), index, memory))
        # Exact ties favor earliest learned chunk; inspection of the scoring
        # tail never leaks into the model being scored.
        best = min(scores, key=lambda x: (-x[0], x[1]))
        ranking = sorted((s, i) for s, i, _ in scores)
        second = max((s for s, i in ranking if i != best[1]), default=best[0])
        decision = {"chunk_index": best[1], "chunks_evaluated": n,
                    "log_margin": round(best[0] - second, 6),
                    "evidence_events": REGIME_TAIL}
        self._cache = (decision, best[2])
        return dict(decision)

    def choose(self, frame):
        check(frame)
        if frame["done"]:
            return None
        self.selection()
        return self._cache[1].choose(frame)

    def record(self):
        if not self.events:
            raise ValueError("no experienced outcomes to checkpoint")
        state = {"schema": REGIME_SCHEMA, "events": self.events}
        return {"state": json.loads(canonical(state)), "sha256": digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record) != {"state", "sha256"}
                or type(record["state"]) is not dict
                or type(record["sha256"]) is not str
                or digest(record["state"]) != record["sha256"]):
            raise ValueError("invalid continual checkpoint integrity")
        state = record["state"]
        if (set(state) != {"schema", "events"}
                or state["schema"] != REGIME_SCHEMA
                or type(state["events"]) is not list
                or not 1 <= len(state["events"]) <= MAX_SAMPLES):
            raise ValueError("invalid continual checkpoint structure")
        memory = cls()
        for event in state["events"]:
            memory.observe(event)
        if memory.record() != record:
            raise ValueError("unreplayable continual evidence")
        return memory


# Second optional continual policy: sooner re-use of past experience, or
# learning a fresh recent hypothesis without being told which rule changed.
FAST_REGIME_SCHEMA = "developmental-ai.fast-regime-retrieval/v1"
FAST_REGIME_TAIL = 4
FAST_REGIME_RECENT = 8


class FastRegimeMemory(RegimeRetrievalMemory):
    """Predictive retrieval with an out-of-sample, short-term candidate.

    The recent candidate is fitted on the eight observations *preceding* the
    four-scoring-event tail, never on the tail itself. Thus a formerly unseen
    rule can begin to form its own hypothesis rather than requiring a 64-event
    full archival block; old stable hypotheses are still accessible. The
    candidate set and 4/8 event windows are engineered, not self-discovered.
    """

    def selection(self):
        if len(self.events) < REGIME_CHUNK + FAST_REGIME_TAIL:
            raise ValueError("insufficient independent fast retrieval evidence")
        if self._cache is not None:
            return dict(self._cache[0])
        tail = self.events[-FAST_REGIME_TAIL:]
        candidate_count = (len(self.events) - FAST_REGIME_TAIL) // REGIME_CHUNK
        candidates = []
        for index in range(candidate_count):
            m = NumericOutcomeMemory()
            for event in self.events[index*REGIME_CHUNK:(index+1)*REGIME_CHUNK]:
                m.add(event)
            candidates.append((f"archive_{index}", index, m))
        if len(self.events) >= FAST_REGIME_RECENT + FAST_REGIME_TAIL:
            recent = NumericOutcomeMemory()
            for event in self.events[-(FAST_REGIME_TAIL+FAST_REGIME_RECENT):-FAST_REGIME_TAIL]:
                recent.add(event)
            candidates.append(("recent_8", candidate_count, recent))
        ranked = []
        for name, index, model in candidates:
            likelihood = sum(self._likelihood(model, e) for e in tail)
            ranked.append((-likelihood, index, name, model))
        # The first complete archive wins exact score ties over short-term.
        best = min(ranked, key=lambda x: (x[0], x[1]))
        runner_up = min((r for r in ranked if r is not best),
                        key=lambda x: (x[0], x[1]), default=None)
        decision = {"source": best[2], "candidates": len(ranked),
                    "log_margin": round(runner_up[0] - best[0], 6)
                    if runner_up is not None else 0.0,
                    "scoring_events": FAST_REGIME_TAIL,
                    "overlap_with_selected_training": 0}
        self._cache = (decision, best[3])
        return dict(decision)

    def record(self):
        if not self.events:
            raise ValueError("no experienced outcomes to checkpoint")
        state = {"schema": FAST_REGIME_SCHEMA, "events": self.events}
        return {"state": json.loads(canonical(state)), "sha256": digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record) != {"state", "sha256"}
                or type(record["state"]) is not dict
                or type(record["sha256"]) is not str
                or digest(record["state"]) != record["sha256"]):
            raise ValueError("invalid fast-retrieval checkpoint digest")
        state = record["state"]
        if (set(state) != {"schema", "events"}
                or state["schema"] != FAST_REGIME_SCHEMA
                or type(state["events"]) is not list
                or not 1 <= len(state["events"]) <= MAX_SAMPLES):
            raise ValueError("invalid fast-retrieval checkpoint structure")
        obj = cls()
        for event in state["events"]:
            obj.observe(event)
        if obj.record() != record:
            raise ValueError("fast-retrieval evidence failed replay")
        return obj


# Selection-only internal evidence consistency. Never silently overwrite
# old numeric memory, change benchmark physics, or promote this controller.
CONSISTENT_SCHEMA = "developmental-ai.consistent-regime-retrieval/v1"
CONSISTENCY_CUTOFF = -1.5
RECENT_NEAR_TIE = 0.75


class ConsistentRegimeMemory(FastRegimeMemory):
    """Retain old skills while rejecting internally contradictory blocks.

    Complete archival blocks are split in half. Each half predicts feedback
    from the other half, out of sample. Under-performing blocks are excluded
    from selection but NEVER deleted. A fresh, independently-scored recent
    candidate remains available for rules absent from the archive. This is
    engineered model validation, not a trustworthy evidence-source check.
    """

    @classmethod
    def _cross_half_score(cls, events):
        if len(events) != REGIME_CHUNK:
            raise ValueError("not a complete archived memory")
        a, b = NumericOutcomeMemory(), NumericOutcomeMemory()
        for row in events[:REGIME_CHUNK//2]:
            a.add(row)
        for row in events[REGIME_CHUNK//2:]:
            b.add(row)
        total = (sum(cls._likelihood(a, row) for row in events[REGIME_CHUNK//2:])
                 + sum(cls._likelihood(b, row) for row in events[:REGIME_CHUNK//2]))
        return total / REGIME_CHUNK

    def selection(self):
        if len(self.events) < REGIME_CHUNK + FAST_REGIME_TAIL:
            raise ValueError("insufficient independent consistency evidence")
        if self._cache is not None:
            return dict(self._cache[0])
        tail = self.events[-FAST_REGIME_TAIL:]
        block_count = (len(self.events) - FAST_REGIME_TAIL)//REGIME_CHUNK
        quarantine = []
        candidates = []
        for index in range(block_count):
            events = self.events[index*REGIME_CHUNK:(index+1)*REGIME_CHUNK]
            quality = self._cross_half_score(events)
            if quality < CONSISTENCY_CUTOFF:
                quarantine.append(index)
                continue
            memory = NumericOutcomeMemory()
            for event in events:
                memory.add(event)
            candidates.append((f"archive_{index}", index, memory))
        recent = NumericOutcomeMemory()
        for event in self.events[-(FAST_REGIME_RECENT+FAST_REGIME_TAIL):-FAST_REGIME_TAIL]:
            recent.add(event)
        candidates.append(("recent_8", block_count, recent))
        ranked = []
        for name, index, memory in candidates:
            cost = -sum(self._likelihood(memory, e) for e in tail)
            ranked.append((cost, index, name, memory))
        best = min(ranked, key=lambda x: (x[0], x[1]))
        recent_entry = next(r for r in ranked if r[2] == "recent_8")
        if best is not recent_entry and recent_entry[0] - best[0] <= RECENT_NEAR_TIE:
            best = recent_entry
        next_best = min((r for r in ranked if r is not best),
                        key=lambda x: (x[0], x[1]), default=None)
        decision = {
            "source": best[2], "candidates": len(ranked),
            "quarantined_archive_indices": quarantine,
            "log_margin": round(next_best[0] - best[0], 6)
                          if next_best is not None else 0.0,
            "scoring_events": FAST_REGIME_TAIL,
            "overlap_with_selected_training": 0,
        }
        self._cache = (decision, best[3])
        return dict(decision)

    def record(self):
        if not self.events:
            raise ValueError("no experienced outcomes to checkpoint")
        state = {"schema": CONSISTENT_SCHEMA, "events": self.events}
        return {"state": json.loads(canonical(state)), "sha256": digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record) != {"state", "sha256"}
                or type(record["state"]) is not dict
                or type(record["sha256"]) is not str
                or digest(record["state"]) != record["sha256"]):
            raise ValueError("invalid consistency checkpoint digest")
        state = record["state"]
        if (set(state) != {"schema", "events"}
                or state["schema"] != CONSISTENT_SCHEMA
                or type(state["events"]) is not list
                or not 1 <= len(state["events"]) <= MAX_SAMPLES):
            raise ValueError("invalid consistency checkpoint schema")
        obj = cls()
        for event in state["events"]:
            obj.observe(event)
        if obj.record() != record:
            raise ValueError("cannot replay consistency checkpoint")
        return obj


# A third, opt-in extension to the SAME public-outcome learning architecture.
# Unlike NumericOutcomeMemory, it accepts previously unknown feature vocabularies.
# Exact key-set partitioning is a deliberately engineered inductive bias.
VARIABLE_MODEL_SCHEMA = "developmental-ai.variable-outcome-memory/v1"
VARIABLE_MAX_KEYS = 5


def variable_feature_check(features):
    if (type(features) is not dict or not 2 <= len(features) <= VARIABLE_MAX_KEYS
            or any(type(k) is not str or not 1 <= len(k) <= 30
                   or any(c not in "abcdefghijklmnopqrstuvwxyz_" for c in k)
                   or type(v) is not int or not 0 <= v <= 9
                   for k, v in features.items())):
        raise ValueError("invalid variable numeric action observations")
    return features


class VariableOutcomeMemory:
    """Persistent outcome learning across *observed* feature schemas.

    No family labels, hidden physics, source names, stable action IDs or known
    target vocabulary are accepted by observe(). Each independently learned
    schema shares one append-only event history but predicts with its own
    5NN evidence, avoiding contamination when attribute vocabularies differ.

    The schema signature is manually defined as the set of observed keys.
    This does not semantically align new words with old words or demonstrate
    zero-shot transfer. Target-family feedback is still required.
    """

    def __init__(self):
        self.events = []
        self._groups = {}

    def observe(self, event):
        if (type(event) is not dict or set(event) != {"features", "progress", "damage"}
                or type(event["progress"]) is not bool or type(event["damage"]) is not bool
                or (event["progress"] and event["damage"])
                or len(self.events) >= MAX_SAMPLES):
            raise ValueError("invalid or oversized variable outcome event")
        variable_feature_check(event["features"])
        row = json.loads(canonical(event))
        self.events.append(row)
        signature = tuple(sorted(row["features"]))
        self._groups.setdefault(signature, []).append(row)

    def estimate(self, features):
        variable_feature_check(features)
        signature = tuple(sorted(features))
        seen = self._groups.get(signature, [])
        if not seen:
            return {"progress": 0.0, "damage": 0.0,
                    "evidence": 0, "schema_known": False}
        neighbors = sorted(enumerate(seen), key=lambda entry: (
            sum((features[key] - entry[1]["features"][key]) ** 2
                for key in signature), entry[0]))[:5]
        return {
            "progress": sum(int(row["progress"]) for _, row in neighbors) / len(neighbors),
            "damage": sum(int(row["damage"]) for _, row in neighbors) / len(neighbors),
            "evidence": len(neighbors), "schema_known": True,
        }

    def choose(self, frame):
        if (type(frame) is not dict or
                set(frame) != {"schema","episode","tick","budget","progress",
                               "damage","target","actions","done"} or
                frame["schema"] != "developmental-ai.variable-affordance-frame/v1" or
                type(frame["done"]) is not bool or
                type(frame["actions"]) is not list or len(frame["actions"]) > 16):
            raise ValueError("invalid variable-affordance public frame")
        if frame["done"]:
            return None
        options = []
        seen = set()
        for action in frame["actions"]:
            if (type(action) is not dict or set(action) != {"id", "features"}
                    or type(action["id"]) is not str or not action["id"].startswith("a_")
                    or len(action["id"]) != 20 or action["id"] in seen):
                raise ValueError("invalid anonymous action observation")
            seen.add(action["id"])
            prediction = self.estimate(action["features"])
            score = prediction["progress"] * 3 - prediction["damage"] * 10
            options.append((-score, action["id"]))
        return min(options)[1] if options else None

    def signatures(self):
        return {"|".join(sig): len(rows) for sig, rows in sorted(self._groups.items())}

    def record(self):
        if not self.events:
            raise ValueError("no observed events to preserve")
        state = {"schema": VARIABLE_MODEL_SCHEMA, "events": self.events}
        return {"state": json.loads(canonical(state)), "sha256": digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record) != {"state","sha256"}
                or type(record["state"]) is not dict or
                type(record["sha256"]) is not str
                or digest(record["state"]) != record["sha256"]):
            raise ValueError("invalid cross-schema memory digest")
        state = record["state"]
        if (set(state) != {"schema","events"} or
                state["schema"] != VARIABLE_MODEL_SCHEMA or
                type(state["events"]) is not list or
                not 1 <= len(state["events"]) <= MAX_SAMPLES):
            raise ValueError("invalid cross-schema memory structure")
        obj = cls()
        for row in state["events"]:
            obj.observe(row)
        if obj.record() != record:
            raise ValueError("cross-schema observation memory cannot replay")
        return obj
