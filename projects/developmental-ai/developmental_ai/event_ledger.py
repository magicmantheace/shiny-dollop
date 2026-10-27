"""Strict, simulation-only event export for future AthenZ/Synveil adapters.

No execution, networking, user identity ingestion, or authorization is provided.
Hash chains detect accidental changes, not malicious re-signing or provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

LEDGER_SCHEMA = "developmental-ai.sim-ledger/v1"
EVENT_SCHEMA = "developmental-ai.event/v1"
MAX_EVENTS = 1024
MAX_BYTES = 2_000_000
OPAQUE_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
EVENT_KEYS = frozenset(("schema", "event_id", "trace_id", "sequence", "source_kind",
                        "subject_kind", "subject_id", "scope", "kind", "payload",
                        "previous_sha256", "sha256"))
LEDGER_KEYS = frozenset(("schema", "source_kind", "scope", "trace_sha256", "subject_id", "events"))
KINDS = frozenset(("observation", "action_proposed", "outcome", "episode_complete"))


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(data: Any) -> str:
    return hashlib.sha256(_canonical(data).encode("utf-8")).hexdigest()


def _validate_trace(trace: dict) -> None:
    if type(trace) is not dict:
        raise ValueError("trace must be a dictionary")
    if trace.get("schema") == "developmental-ai.delay-trace/v1":
        from .delayed_choice import verify_trace
    elif trace.get("schema") == "developmental-ai.trace/v1":
        from .curriculum import verify_trace
    elif trace.get("schema") == "developmental-ai.occluded-trace/v1":
        from .occluded_navigation import verify_trace
    elif trace.get("schema") == "developmental-ai.uncertain-trace/v1":
        from .uncertain_navigation import verify_trace
    else:
        raise ValueError("unsupported trace version")
    verify_trace(trace)


def export_trace(trace: dict, subject_id: str = "local-agent") -> dict:
    """Make a hash-linked, bounded event log from a verified simulation trace."""
    if type(subject_id) is not str or not OPAQUE_ID.fullmatch(subject_id):
        raise ValueError("subject ID must be a short opaque lower-case identifier")
    _validate_trace(trace)
    trace_id = trace["sha256"]
    spatial = trace["schema"] == "developmental-ai.occluded-trace/v1"
    uncertain = trace["schema"] == "developmental-ai.uncertain-trace/v1"
    steps = trace["outcome"]["events"] if (spatial or uncertain) else trace["events"]
    if len(steps) * 3 + 1 > MAX_EVENTS:
        raise ValueError("trace exceeds maximum event count")
    events: list[dict] = []
    previous = "0" * 64

    def append(kind: str, payload: dict) -> None:
        nonlocal previous
        seq = len(events)
        body = {"schema": EVENT_SCHEMA, "event_id": f"{trace_id[:16]}-{seq:04d}",
                "trace_id": trace_id, "sequence": seq, "source_kind": "simulation",
                "subject_kind": "agent", "subject_id": subject_id,
                "scope": "simulation-only", "kind": kind, "payload": payload,
                "previous_sha256": previous}
        if len(_canonical(payload).encode()) > 8_192:
            raise ValueError("event payload is too large")
        previous = _digest(body)
        events.append({**body, "sha256": previous})

    for step in steps:
        if uncertain:
            append("observation", {"state": step["observation"], "memory": step["state"]})
            append("action_proposed", {"action": step["action"]})
            append("outcome", {"memory": step["next_state"], "reward": step["reward"],
                               "event": step["event"], "done": step["done"]})
        elif spatial:
            append("observation", {"state": step["observation"], "memory": step["memory_before"]})
            append("action_proposed", {"action": step["action"]})
            append("outcome", {"state": step["observation_after"], "memory": step["memory_after"],
                               "reward": step["reward"], "event": step["event"], "done": step["done"]})
        else:
            append("observation", {"state": step["before"]})
            append("action_proposed", {"action": step["action"]})
            append("outcome", {"state": step["after"], "reward": step["reward"],
                               "event": step["event"], "done": step["done"]})
    final = {k: v for k, v in trace["outcome"].items() if k != "events"} if (spatial or uncertain) else trace["outcome"]
    append("episode_complete", {"outcome": final})
    ledger = {"schema": LEDGER_SCHEMA, "source_kind": "simulation",
              "scope": "simulation-only", "subject_id": subject_id,
              "trace_sha256": trace_id, "events": events}
    if len(_canonical(ledger).encode()) > MAX_BYTES:
        raise ValueError("event ledger exceeds size bound")
    return ledger


def verify_ledger(ledger: dict, trace: dict | None = None) -> dict:
    """Validate schema/chain. Optionally bind every event to a verified trace."""
    try:
        if type(ledger) is not dict or set(ledger) != LEDGER_KEYS:
            raise ValueError("invalid ledger envelope")
        if (ledger["schema"] != LEDGER_SCHEMA or ledger["source_kind"] != "simulation"
                or ledger["scope"] != "simulation-only"
                or type(ledger["subject_id"]) is not str
                or not OPAQUE_ID.fullmatch(ledger["subject_id"])):
            raise ValueError("untrusted ledger source or identity")
        if (type(ledger["trace_sha256"]) is not str or
                not re.fullmatch(r"[a-f0-9]{64}", ledger["trace_sha256"])):
            raise ValueError("invalid trace digest")
        entries = ledger["events"]
        if type(entries) is not list or not 1 <= len(entries) <= MAX_EVENTS:
            raise ValueError("invalid event count")
        if len(_canonical(ledger).encode()) > MAX_BYTES:
            raise ValueError("oversized event ledger")
        previous = "0" * 64
        for seq, event in enumerate(entries):
            if type(event) is not dict or set(event) != EVENT_KEYS:
                raise ValueError("unrecognized event fields")
            if (event["schema"] != EVENT_SCHEMA or event["event_id"] != f"{ledger['trace_sha256'][:16]}-{seq:04d}"
                    or event["trace_id"] != ledger["trace_sha256"] or type(event["sequence"]) is not int
                    or event["sequence"] != seq or event["source_kind"] != "simulation"
                    or event["subject_kind"] != "agent" or event["subject_id"] != ledger["subject_id"]
                    or event["scope"] != "simulation-only" or event["kind"] not in KINDS
                    or type(event["payload"]) is not dict or event["previous_sha256"] != previous):
                raise ValueError("invalid event identity, sequence, or source")
            if len(_canonical(event["payload"]).encode()) > 8_192:
                raise ValueError("oversized event payload")
            body = {k: v for k, v in event.items() if k != "sha256"}
            computed = _digest(body)
            if computed != event["sha256"]:
                raise ValueError("event chain mismatch")
            previous = computed
        if (len(entries) - 1) % 3 != 0 or entries[-1]["kind"] != "episode_complete":
            raise ValueError("incomplete episode record")
        for i in range(0, len(entries) - 1, 3):
            if tuple(e["kind"] for e in entries[i:i+3]) != ("observation", "action_proposed", "outcome"):
                raise ValueError("unexpected event sequence")
        if trace is not None:
            if export_trace(trace, ledger["subject_id"]) != ledger:
                raise ValueError("ledger differs from independently replayed trace")
        return {"verified": True, "events": len(entries), "tail_sha256": previous,
                "trace_bound": trace is not None}
    except (KeyError, TypeError, OverflowError, UnicodeError) as exc:
        raise ValueError("malformed event ledger") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("export", "verify"))
    parser.add_argument("--trace-file", type=Path)
    parser.add_argument("--ledger-file", type=Path)
    parser.add_argument("--subject-id", default="local-agent")
    args = parser.parse_args()
    try:
        if args.command == "export":
            if args.trace_file is None:
                parser.error("export requires --trace-file")
            trace = json.loads(args.trace_file.read_text(encoding="utf-8"))
            print(json.dumps(export_trace(trace, args.subject_id), indent=2))
        else:
            if args.ledger_file is None:
                parser.error("verify requires --ledger-file")
            ledger = json.loads(args.ledger_file.read_text(encoding="utf-8"))
            trace = json.loads(args.trace_file.read_text(encoding="utf-8")) if args.trace_file else None
            print(json.dumps(verify_ledger(ledger, trace), indent=2))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
