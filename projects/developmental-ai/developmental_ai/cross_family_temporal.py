"""Read-only temporal-model adapter for delayed-choice cue proposals.

The model is fitted ONLY to navigation-family public sensor streams. Candidate
cue labels and the artificial observation-to-forecast symbol vocabulary are
engineering priors. This is NOT unsupervised discovery of a universal temporal
ontology, and it grants no action authority.
"""
from __future__ import annotations
import json
from developmental_ai.environment_api import canonical,digest
from developmental_ai.variable_correspondence import VariableCorrespondence, _candidates

SCHEMA = "developmental-ai.cross-family-temporal/v1"


def validate_cues(observed,candidates):
    _candidates(observed,candidates)
    labels = []
    for name, proposal, _ in candidates:
        if type(proposal) is not list or len(proposal) != 2 or type(proposal[0]) is not int or not 0 <= proposal[0] <= 3 or proposal[1] != 0 or type(proposal[1]) is not int:
            raise ValueError("unrecognized or privileged delayed-choice proposal")
        labels.append(proposal[0])
    if set(labels) != set(range(4)) or len(labels) != 5:
        raise ValueError("missing cue class")


class CrossFamilyTemporal:
    """Snapshot-bound adapter, no learning or mutation on target episodes."""
    def __init__(self, model):
        if not isinstance(model,VariableCorrespondence):
            raise ValueError("must use fitted navigation temporal model")
        self.model = VariableCorrespondence.restore(model.record())
        self.source_digest = self.model.record()["sha256"]

    def evaluate(self,observed,candidates):
        validate_cues(observed,candidates)
        report = self.model.details(observed,candidates)
        selected = next(row for row in candidates if row[0] == report["selected"])
        return {"cue":selected[1][0],"source":report["selected"],
                "expected_common_events":report["reports"][report["selected"]]["expected_matches"]}

    def record(self):
        state={"schema":SCHEMA,"model":self.model.record(),"source_digest":self.source_digest}
        return {"state":json.loads(canonical(state)),"sha256":digest(state)}

    @classmethod
    def restore(cls,record):
        if (type(record) is not dict or set(record)!={"state","sha256"} or type(record["state"]) is not dict or
                type(record["sha256"]) is not str or digest(record["state"])!=record["sha256"]):
            raise ValueError("invalid cross-family checkpoint")
        s=record["state"]
        if set(s)!={"schema","model","source_digest"} or s["schema"]!=SCHEMA:
            raise ValueError("incompatible cross-family schema")
        model=VariableCorrespondence.restore(s["model"])
        instance=cls(model)
        if instance.record()!=record:
            raise ValueError("cross-family model was replaced")
        return instance
