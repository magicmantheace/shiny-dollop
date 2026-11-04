"""SQLite-backed background job queue + worker runner (F5.1).

The library database (migration 3) carries a `jobs` table: durable work
items with a kind, a JSON payload, a lifecycle state
(``queued`` -> ``running`` -> ``done`` | ``failed``), the claiming
worker's id, an attempt count, and — once finished — a JSON result or an
error string. The queue is generic: handlers are registered by kind in
`HANDLERS`, and F5.2/F5.3 add report/generation kinds without touching
the queue mechanics.

Claim semantics: `claim` takes the oldest queued job (lowest job_id —
FIFO) inside a ``BEGIN IMMEDIATE`` transaction, so two workers, even in
separate processes, can never take the same job. `attempts` counts
claims: a job may be claimed at most `MAX_ATTEMPTS` times in its life.

Stale policy: a worker that dies mid-job leaves it ``running`` forever
unless someone requeues it. `requeue_stale` returns every running job
whose claim is older than the given age to ``queued`` (worker and claim
time cleared, attempts kept) — unless the job has already been claimed
`MAX_ATTEMPTS` times, in which case it is marked ``failed`` with a
named error instead of being handed out again.

Handlers: a handler is ``callable(lib, payload) -> result`` where the
result must be JSON-serializable. A handler that returns normally
completes its job with that result — including a *negative* result such
as the validation preview's ``{"valid": false, ...}`` (a successful
preview of a bad scene). A handler that raises fails its job with the
exception recorded as the error text.
"""
from __future__ import annotations

import json
from pathlib import Path

from .ipc import write_ipc
from .library import Library
from .schema import ValidationError, validate_scene
from .timing import compute_schedule, resolve_timing

# A job may be claimed at most this many times across its whole life;
# a stale claim on a job that has used them all fails the job instead
# of requeueing it (see requeue_stale).
MAX_ATTEMPTS = 3

STATES = ("queued", "running", "done", "failed")


class JobError(ValueError):
    """A queue operation was refused, with a named reason."""


def _dump_json(value: object, what: str) -> str:
    try:
        return json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise JobError(f"{what} is not JSON-serializable: {exc}") from exc


def _row_to_job(row) -> dict:
    job = dict(row)
    job["payload"] = json.loads(job.pop("payload_json"))
    result_json = job.pop("result_json")
    job["result"] = json.loads(result_json) if result_json is not None else None
    return job


def _require_job(lib: Library, job_id: int) -> dict:
    row = lib.db.execute(
        "SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    if row is None:
        raise JobError(f"unknown job {job_id}")
    return _row_to_job(row)


def enqueue(lib: Library, kind: str, payload: object) -> int:
    """Append a queued job; returns its job_id.

    The payload must be JSON-serializable (it is stored verbatim as
    JSON); the kind is any non-empty string — whether a handler exists
    for it is decided when a worker runs it.
    """
    if not isinstance(kind, str) or not kind or len(kind) > 64:
        raise JobError(f"job kind must be a string of 1..64 chars, got {kind!r}")
    payload_json = _dump_json(payload, "job payload")
    cur = lib.db.execute(
        "INSERT INTO jobs(kind, payload_json) VALUES(?,?)", (kind, payload_json))
    lib.db.commit()
    return int(cur.lastrowid)


def claim(lib: Library, worker_id: str) -> dict | None:
    """Atomically claim the oldest queued job for `worker_id`.

    Returns the claimed job (state ``running``, attempts incremented)
    or None when the queue is empty. The select + update run inside a
    BEGIN IMMEDIATE transaction (or the caller's already-open
    transaction), so a second worker can never claim the same job.
    """
    if not isinstance(worker_id, str) or not worker_id:
        raise JobError(f"worker_id must be a non-empty string, got {worker_id!r}")
    db = lib.db
    own_txn = not db.in_transaction
    if own_txn:
        db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute(
            "SELECT job_id FROM jobs WHERE state='queued' "
            "ORDER BY job_id LIMIT 1").fetchone()
        if row is None:
            if own_txn:
                db.execute("COMMIT")
            return None
        job_id = row["job_id"]
        db.execute(
            "UPDATE jobs SET state='running', worker_id=?, "
            "claimed_at=CURRENT_TIMESTAMP, attempts=attempts+1 "
            "WHERE job_id=? AND state='queued'",
            (worker_id, job_id))
        if own_txn:
            db.execute("COMMIT")
    except Exception:
        if own_txn and db.in_transaction:
            db.execute("ROLLBACK")
        raise
    return get_job(lib, job_id)


def complete(lib: Library, job_id: int, result: object) -> dict:
    """Mark a running job done, storing its JSON-serializable result."""
    job = _require_job(lib, job_id)
    if job["state"] != "running":
        raise JobError(
            f"job {job_id} is {job['state']}, not running; cannot complete it")
    result_json = _dump_json(result, "job result")
    lib.db.execute(
        "UPDATE jobs SET state='done', result_json=?, error=NULL, "
        "finished_at=CURRENT_TIMESTAMP WHERE job_id=?",
        (result_json, job_id))
    lib.db.commit()
    return get_job(lib, job_id)


def fail(lib: Library, job_id: int, error: object) -> dict:
    """Mark a running job failed, recording the error text."""
    job = _require_job(lib, job_id)
    if job["state"] != "running":
        raise JobError(
            f"job {job_id} is {job['state']}, not running; cannot fail it")
    lib.db.execute(
        "UPDATE jobs SET state='failed', error=?, finished_at=CURRENT_TIMESTAMP "
        "WHERE job_id=?",
        (str(error), job_id))
    lib.db.commit()
    return get_job(lib, job_id)


def requeue_stale(lib: Library, older_than_s: float) -> dict:
    """Return stale running jobs to the queue (see module docstring).

    A running job is stale when its claim is older than `older_than_s`
    seconds. Jobs with attempts remaining go back to ``queued``; a job
    that has already been claimed `MAX_ATTEMPTS` times goes to
    ``failed`` with a named error. Returns {"requeued": n, "failed": n}.
    """
    if (isinstance(older_than_s, bool)
            or not isinstance(older_than_s, (int, float)) or older_than_s < 0):
        raise JobError(
            f"older_than_s must be a non-negative number, got {older_than_s!r}")
    modifier = f"-{float(older_than_s)} seconds"
    rows = lib.db.execute(
        "SELECT job_id, attempts, worker_id, claimed_at FROM jobs "
        "WHERE state='running' AND claimed_at IS NOT NULL "
        "AND claimed_at <= datetime('now', ?)", (modifier,)).fetchall()
    requeued = failed = 0
    for row in rows:
        if row["attempts"] >= MAX_ATTEMPTS:
            lib.db.execute(
                "UPDATE jobs SET state='failed', error=?, "
                "finished_at=CURRENT_TIMESTAMP WHERE job_id=?",
                (f"job exceeded max attempts ({MAX_ATTEMPTS}): claimed "
                 f"{row['attempts']} times without finishing; last claim by "
                 f"{row['worker_id']} at {row['claimed_at']} went stale",
                 row["job_id"]))
            failed += 1
        else:
            lib.db.execute(
                "UPDATE jobs SET state='queued', worker_id=NULL, "
                "claimed_at=NULL WHERE job_id=?", (row["job_id"],))
            requeued += 1
    lib.db.commit()
    return {"requeued": requeued, "failed": failed}


def get_job(lib: Library, job_id: int) -> dict | None:
    """One job by id (payload/result parsed), or None."""
    row = lib.db.execute(
        "SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    return _row_to_job(row) if row is not None else None


def list_jobs(lib: Library, state: str | None = None) -> list[dict]:
    """All jobs in job_id order, optionally filtered to one state."""
    if state is not None and state not in STATES:
        raise JobError(f"unknown job state {state!r} (expected one of {STATES})")
    if state is None:
        rows = lib.db.execute("SELECT * FROM jobs ORDER BY job_id").fetchall()
    else:
        rows = lib.db.execute(
            "SELECT * FROM jobs WHERE state=? ORDER BY job_id",
            (state,)).fetchall()
    return [_row_to_job(row) for row in rows]


# ---------------------------------------------------------------------------
# Built-in handlers

def _require_payload(payload: object, kind: str) -> dict:
    if not isinstance(payload, dict):
        raise JobError(f"{kind} payload must be a JSON object")
    scene = payload.get("scene")
    if not isinstance(scene, dict):
        raise JobError(f"{kind} payload requires a 'scene' object")
    return payload


def _handle_validate_scene(lib: Library, payload: object) -> dict:
    """Validation preview record for a scene document.

    An invalid scene is a completed preview, not a job failure:
    {"valid": false, "error": <reason>}. For a valid scene the record
    carries the scene id, the event count, the makespan and the
    per-actor occupancy windows from `compute_schedule`. Makespan is
    the schedule's scene end: per event, the latest of its dispatch
    time, its occupancy-window end (speak/interact) and, for a move,
    its arrival (dispatch + duration_ms).
    """
    payload = _require_payload(payload, "validate_scene")
    scene = payload["scene"]
    try:
        validate_scene(scene)
    except ValidationError as exc:
        return {"valid": False, "error": str(exc)}
    timing = resolve_timing(scene.get("timing"))
    records = compute_schedule(scene["events"], timing)
    makespan = 0
    actor_windows: dict[str, list[dict]] = {}
    for record in records:
        end = record["effective_ms"]
        if record["window_end_ms"] is not None:
            end = max(end, record["window_end_ms"])
        if record["op"] == "move":
            event = scene["events"][record["index"]]
            end = max(end, record["effective_ms"] + int(event.get("duration_ms", 0)))
        makespan = max(makespan, end)
        if record["window_start_ms"] is not None and record["actor_id"] is not None:
            actor_windows.setdefault(record["actor_id"], []).append(
                {"start_ms": record["window_start_ms"],
                 "end_ms": record["window_end_ms"]})
    for windows in actor_windows.values():
        windows.sort(key=lambda w: w["start_ms"])
    return {
        "valid": True,
        "scene_id": scene["scene_id"],
        "event_count": len(scene["events"]),
        "makespan_ms": makespan,
        "actor_windows": actor_windows,
    }


def _handle_export_scene(lib: Library, payload: object) -> dict:
    """Validate a scene and write it as an IPC envelope to payload['out']."""
    payload = _require_payload(payload, "export_scene")
    out = payload.get("out")
    if not isinstance(out, str) or not out:
        raise JobError("export_scene payload requires an 'out' path string")
    scene = payload["scene"]
    envelope = write_ipc(Path(out), scene)
    return {"written": out, "ipc_version": envelope["ipc_version"],
            "scene_id": scene["scene_id"]}


HANDLERS = {
    "validate_scene": _handle_validate_scene,
    "export_scene": _handle_export_scene,
}


def run_worker(lib: Library, worker_id: str, *,
               stale_after_s: float | None = None) -> list[dict]:
    """Run queued jobs until the queue is empty; returns run summaries.

    When `stale_after_s` is given, stale running jobs are requeued (or
    failed at max attempts) before claiming starts, so a crashed
    predecessor's work is picked up in the same pass. Each summary is
    {"job_id", "kind", "state"} for one job this worker ran, in run
    order. This is a drain-and-exit runner: it never blocks waiting for
    new work (no daemon mode in this slice).
    """
    if stale_after_s is not None:
        requeue_stale(lib, stale_after_s)
    summaries = []
    while True:
        job = claim(lib, worker_id)
        if job is None:
            return summaries
        handler = HANDLERS.get(job["kind"])
        if handler is None:
            fail(lib, job["job_id"],
                 f"no handler registered for job kind {job['kind']!r}")
            summaries.append({"job_id": job["job_id"], "kind": job["kind"],
                              "state": "failed"})
            continue
        try:
            result = handler(lib, job["payload"])
        except Exception as exc:  # a handler exception is a job failure
            fail(lib, job["job_id"], f"{type(exc).__name__}: {exc}")
            summaries.append({"job_id": job["job_id"], "kind": job["kind"],
                              "state": "failed"})
        else:
            complete(lib, job["job_id"], result)
            summaries.append({"job_id": job["job_id"], "kind": job["kind"],
                              "state": "done"})
