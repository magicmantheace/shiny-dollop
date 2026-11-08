"""Two independently keyed synthetic attestations of passive public events.

Sandbox-only demonstration. HMAC authenticates possession of the fixture
secret provided by the verifier, NOT event truth, human consent, independence
of organizations or guaranteed safety. Two compromised keys can sign the
same fabricated outcome. No method chooses or performs learner actions.
"""
from __future__ import annotations

import hmac
import hashlib
import json

from developmental_ai.observable_affordances import canonical, digest
from developmental_ai.passive_outcome_learning import PassiveOutcomeArchive

SCHEMA="developmental-ai.paired-witness/v1"
ROLES=("primary","witness")
RECORDS=240


def keyring_check(keys):
    if (type(keys) is not dict or set(keys)!=set(ROLES)
        or any(type(keys[k]) is not bytes or len(keys[k])<32 for k in ROLES)
        or keys["primary"]==keys["witness"]):
        raise ValueError("distinct pretrusted fixture keys required")
    return keys


def _payload(role,event):
    return {"schema":SCHEMA,"role":role,"public_event":event}


def sign_observation(event,role,key):
    """Fixture-origin envelope; providing a key is NOT proof of honesty."""
    if role not in ROLES or type(key) is not bytes or len(key)<32:
        raise ValueError("invalid signer role or key")
    if (type(event) is not dict or
        set(event)!={"before","action","after","outcome"}):
        raise ValueError("invalid public event to sign")
    frozen=json.loads(canonical(event))
    value=hmac.new(key,canonical(_payload(role,frozen)).encode(),
                   hashlib.sha256).hexdigest()
    return {"role":role,"event":frozen,"mac":value}


def sign_archive(archive,role,key):
    if not isinstance(archive,PassiveOutcomeArchive):
        raise TypeError("public observation archive required")
    return [sign_observation(event,role,key) for event in archive.events]


class PairedWitnessGate:
    """Quarantine *all* evidence when any signed pair fails validation."""
    def __init__(self,trusted_keys):
        self._keys=dict(keyring_check(trusted_keys))

    def _valid_mac(self,envelope,role):
        if (type(envelope) is not dict or
            set(envelope)!={"role","event","mac"} or
            envelope["role"]!=role or type(envelope["mac"]) is not str or
            len(envelope["mac"])!=64 or
            any(x not in "0123456789abcdef" for x in envelope["mac"])):
            return False
        expected=hmac.new(
            self._keys[role],
            canonical(_payload(role,envelope["event"])).encode(),
            hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected,envelope["mac"])

    def assess(self,primary,witness):
        def reject(reason,matched=0):
            return {"approved":False,"reason":reason,
                    "fixture_signatures_verified":False,
                    "physical_truth_verified":False,
                    "paired_events":matched,
                    "learner_training_actions":0,
                    "archive":None}
        if type(primary) is not list or len(primary)!=RECORDS:
            return reject("missing_primary_or_count")
        if type(witness) is not list or len(witness)!=RECORDS:
            return reject("missing_witness_or_count")
        archive=PassiveOutcomeArchive()
        for i,(left,right) in enumerate(zip(primary,witness)):
            if not self._valid_mac(left,"primary"):
                return reject("invalid_primary_mac",i)
            if not self._valid_mac(right,"witness"):
                return reject("invalid_witness_mac",i)
            if left["event"]!=right["event"]:
                return reject("witness_disagreement",i)
            try:
                event=left["event"]
                observed=archive.observe(event["before"],event["action"],
                                         event["after"])
                if observed!=event["outcome"]:
                    return reject("invalid_public_transition",i)
            except (ValueError,TypeError,KeyError,IndexError):
                return reject("invalid_public_transition",i)
        return {"approved":True,"reason":"paired_fixture_attestations_match",
                "fixture_signatures_verified":True,
                "physical_truth_verified":False,
                "paired_events":RECORDS,
                "learner_training_actions":0,
                "archive":archive}

    def receipt(self,decision):
        """Integrity-only report; secret keys are never serialized."""
        if type(decision) is not dict or set(decision)!={
            "approved","reason","fixture_signatures_verified",
            "physical_truth_verified","paired_events",
            "learner_training_actions","archive"}:
            raise ValueError("invalid witness decision")
        public={k:v for k,v in decision.items() if k!="archive"}
        public["archive_sha256"]=(
            decision["archive"].record()["sha256"] if decision["archive"] else None)
        return {"state":public,"sha256":digest(public)}
