"""Sandbox-only, explicitly approved adaptation to a previously unknown C mapping.

No live system privileges, external actions, human approval identity service,
or modification to existing default policies. Numeric descriptors are still
ENGINEERED action identities. Validation is performed by a separate
simulation harness; the SHA receipt is NOT authentication.
"""
from __future__ import annotations

import json

from developmental_ai.affordance_memory import (
    FilteredNovel, RiskMemory, check as check_public, record_step,
)
from developmental_ai.contextual_affordance import ContextMemory
from developmental_ai.dual_sentinel import DualSentinel
from developmental_ai.outcome_skills import canonical, digest

SCHEMA = "developmental-ai.quarantined-c-review/v1"
ROUTE_SCHEMA = "developmental-ai.quarantined-c-route/v1"
_APPROVED_IN_THIS_PROCESS = object()


class CandidateRoute:
    """Public-observation controller. Only the offline stage constructs it.

    The two old diagnostic probes remain the only known-episode tests.
    If neither familiar history fits, use a separately learned and approved
    C memory (offline sandbox only). This cannot identify a truly new D.
    """

    def __init__(self, sources, candidate, *, _capability=None):
        if _capability is not _APPROVED_IN_THIS_PROCESS:
            raise ValueError("candidate requires an explicit staged approval")
        if not isinstance(sources, ContextMemory) or not isinstance(candidate, RiskMemory):
            raise TypeError("verified source histories and RiskMemory required")
        if not candidate.events:
            raise ValueError("candidate has no training")
        self.sources = sources
        self.candidate = candidate
        self.source_sha = sources.record()["sha256"]
        self.candidate_sha = candidate.record()["sha256"]
        self.sentinel = DualSentinel(sources)
        self._target = None
        self.events = []

    def choose(self, frame):
        check_public(frame)
        if self._target is not None:
            return self._target.choose(frame)
        return self.sentinel.choose(frame)

    def feedback(self, before, action, accepted, after):
        check_public(before)
        check_public(after)
        if self.choose(before) != action:
            raise ValueError("feedback action differs from chosen action")
        event = record_step(before, action, accepted, after)
        if self._target is None:
            self.sentinel.feedback(before, action, accepted, after)
            if self.sentinel.unknown and len(self.sentinel.events)==2:
                self._target=FilteredNovel(self.candidate)
                # The two diagnostic interventions happened in the REAL
                # simulated episode and must count toward its step budget.
                for previous in self.sentinel.events:
                    obs=record_step(previous["before"],previous["action"],
                                    previous["accepted"],previous["after"])
                    self._target.history.append({
                        "action":previous["action"],
                        "before":json.loads(canonical(previous["before"]["base"])),
                        "after":json.loads(canonical(previous["after"]["base"])),
                        "accepted":previous["accepted"],"effect":obs})
        else:
            self._target.feedback(before, action, accepted, after)
        self.events.append({"before":json.loads(canonical(before)),
                            "action":action,"accepted":accepted,
                            "after":json.loads(canonical(after))})
        return event

    def mode(self):
        if self._target is not None:
            return "quarantined-C-memory"
        if self.sentinel.selected is not None:
            return "known-memory"
        return "probing"

    def record(self):
        if not self.events:
            raise ValueError("empty candidate route")
        state={"schema":ROUTE_SCHEMA,"sources_sha256":self.source_sha,
               "candidate_sha256":self.candidate_sha,
               "events":self.events,"mode":self.mode()}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls, sources, candidate, saved, *, _capability=None):
        if _capability is not _APPROVED_IN_THIS_PROCESS:
            raise ValueError("candidate restore requires staged approval")
        if (type(saved) is not dict or set(saved)!={"state","sha256"}
            or type(saved["state"]) is not dict
            or saved["sha256"]!=digest(saved["state"])):
            raise ValueError("invalid candidate decision digest")
        state=saved["state"]
        if (set(state)!={"schema","sources_sha256","candidate_sha256","events","mode"}
            or state["schema"]!=ROUTE_SCHEMA or type(state["events"]) is not list
            or not 1<=len(state["events"])<=18):
            raise ValueError("invalid candidate event log")
        model=cls(sources,candidate,_capability=_capability)
        if (state["sources_sha256"]!=model.source_sha or
            state["candidate_sha256"]!=model.candidate_sha):
            raise ValueError("candidate replay belongs to different memories")
        for event in state["events"]:
            if type(event) is not dict or set(event)!={"before","action","accepted","after"}:
                raise ValueError("invalid public decision event")
            model.feedback(event["before"],event["action"],
                           event["accepted"],event["after"])
        if model.record()!=saved:
            raise ValueError("decision differs after policy reconstruction")
        return model


class StagedCReview:
    """Single-use, evidence-based sandbox permission; never auto-approves.

    The training/validation *harness* supplies observed paired evaluation
    metrics; it is not cryptographically trusted. Do not expose this gate
    as a real-world safety authority or as user-authenticated consent.
    """
    def __init__(self, sources, candidate, validation):
        if not isinstance(sources,ContextMemory) or not isinstance(candidate,RiskMemory):
            raise TypeError("two known memories and trained candidate required")
        if len(candidate.events)!=80:
            raise ValueError("expected exactly 80 quarantined simulation episodes")
        if type(validation) is not dict or set(validation)!={"A","B","C"}:
            raise ValueError("separate paired offline validation required")
        for value in validation.values():
            if (type(value) is not dict or set(value)!={"successes","episodes","spoilage","stalled"}
                or any(type(n) is not int or n<0 for n in value.values())
                or value["episodes"]!=24 or value["successes"]>24 or value["spoilage"]>24
                or value["stalled"]>24):
                raise ValueError("invalid rehearsal evidence")
        self._sources=sources
        self._candidate=candidate
        self._sources_sha=sources.record()["sha256"]
        self._candidate_sha=candidate.record()["sha256"]
        risks=sorted(candidate.avoid())
        source_risks=set().union(
            *(memory.avoid() for _,memory in sources._rows.values()))
        eligible=(len(risks)==1 and not set(risks)&source_risks and
                  all(v["successes"]==24 and v["spoilage"]==0 and v["stalled"]==0
                      for v in validation.values()))
        self._receipt={"schema":SCHEMA,"sources_sha256":self._sources_sha,
                       "candidate_sha256":self._candidate_sha,
                       "candidate_training_episodes":len(candidate.events),
                       "validation_split":"train",
                       "validation_indices":[1200,1223],
                       "validation":json.loads(canonical(validation)),
                       "learned_candidates":risks,
                       "eligible_for_explicit_approval":eligible,
                       "toy_simulator_only":True}
        self._receipt_sha=digest(self._receipt)
        self._closed=False

    def review(self):
        return {"receipt":json.loads(canonical(self._receipt)),
                "sha256":self._receipt_sha}

    def reject(self):
        if self._closed:
            raise ValueError("proposal resolved")
        self._closed=True

    def approve(self, *, approved:bool, receipt_sha256:str):
        if self._closed or approved is not True or receipt_sha256!=self._receipt_sha:
            raise ValueError("explicit approval with matching receipt required")
        if not self._receipt["eligible_for_explicit_approval"]:
            raise ValueError("offline candidate failed validation")
        if (self._sources.record()["sha256"]!=self._sources_sha or
            self._candidate.record()["sha256"]!=self._candidate_sha):
            raise ValueError("memory changed after staged validation")
        self._closed=True
        return CandidateRoute(self._sources,self._candidate,
                              _capability=_APPROVED_IN_THIS_PROCESS)

    def preview(self):
        """Non-authoritative sandbox rehearsal. This is NOT approval."""
        if self._closed:
            raise ValueError("review has been resolved")
        return CandidateRoute(self._sources,self._candidate,
                              _capability=_APPROVED_IN_THIS_PROCESS)

    def restore_route(self, approved_route, saved):
        if not isinstance(approved_route,CandidateRoute):
            raise TypeError("a staged sandbox route is required")
        if (approved_route.source_sha!=self._sources_sha or
            approved_route.candidate_sha!=self._candidate_sha):
            raise ValueError("stale or unrelated staged route")
        return CandidateRoute.restore(self._sources,self._candidate,saved,
                                      _capability=_APPROVED_IN_THIS_PROCESS)
