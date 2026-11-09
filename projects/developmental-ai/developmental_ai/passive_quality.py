"""Audit representativeness of already-recorded numeric public evidence.

The audit has no simulator reference, source authentication service, or
action authority. It compares counts in coarse public feature regions to
an independently observed *opportunity menu* (no interventions).
Coverage ≠ correctness, independent provenance, causal support, safety,
or an upper bound on future harm. Deliberately fabricated evidence can
pass this audit and exact SHA-256 replay.
"""
from __future__ import annotations

import json

from developmental_ai.observable_affordances import check,canonical,digest
from developmental_ai.passive_outcome_learning import PassiveOutcomeArchive

SCHEMA="developmental-ai.passive-quality-audit/v1"
BINS=("x_dominant","y_dominant","near_equal")
MIN_COUNT=12
MIN_SHARE=0.15


def feature_bin(features):
    if (type(features) is not list or len(features)!=2 or
        any(type(x) is not int or not 0<=x<=8 for x in features)):
        raise ValueError("invalid numeric public affordances")
    x,y=features
    return ("x_dominant" if x>=y+2 else
            "y_dominant" if y>=x+2 else "near_equal")


class PassiveEvidenceQuality:
    """Public-only observations and action opportunities, NEVER outcomes of probes."""
    def __init__(self,archive,opportunities):
        if (not isinstance(archive,PassiveOutcomeArchive)
            or not archive.events or type(opportunities) not in (tuple,list)
            or not opportunities):
            raise ValueError("training archive and independent public opportunities required")
        self.archive_sha=archive.record()["sha256"]
        self.episode_ids={r["before"]["episode"] for r in archive.events}
        self.reference=[]
        for frame in opportunities:
            check(frame)
            if (frame["tick"]!=0 or frame["done"] or
                frame["episode"] in self.episode_ids or
                frame["episode"] in {x["episode"] for x in self.reference}):
                raise ValueError("reference opportunities must be disjoint unused episodes")
            self.reference.append(json.loads(canonical(frame)))
        self.counts={key:0 for key in BINS}
        self.population={key:0 for key in BINS}
        for row in archive.events:
            self.counts[feature_bin(row["outcome"]["features"])]+=1
        for frame in self.reference:
            for item in frame["actions"]:
                self.population[feature_bin(item["features"])]+=1

    def report(self):
        total=sum(self.counts.values())
        reference_total=sum(self.population.values())
        covered={}
        for name in BINS:
            expected=self.population[name]/reference_total
            observed=self.counts[name]/total
            covered[name]={
                "recorded":self.counts[name],
                "recorded_fraction":round(observed,6),
                "public_menu_fraction":round(expected,6),
                "bin_supported":(
                    self.population[name]==0 or
                    (self.counts[name]>=MIN_COUNT and observed>=MIN_SHARE))
            }
        eligible=all(c["bin_supported"] for c in covered.values())
        # There is no trusted attestation: a valid digest ≠ honest witness.
        return {"schema":SCHEMA,"coverage_passed":eligible,
                "origin_authenticated":False,
                "recorded_episodes":total,
                "opportunity_episodes":len(self.reference),
                "bins":covered,
                "archive_sha256":self.archive_sha,
                "reference_sha256":digest(self.reference),
                "learner_training_actions":0}

    def receipt(self):
        state=self.report()
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}
