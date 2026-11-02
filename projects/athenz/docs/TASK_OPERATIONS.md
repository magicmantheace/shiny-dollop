# Durable, inspectable operations (slice A4)

`athenz-task-operations` runs an ordered list of planner queue items
(slice A1) under one standing task grant (slice A2), executing each
item with the slice A3 executor, and persists the whole run in the
private profile database so it survives shutdowns and model changes.
It is the fourth slice of the owner-directed persistent coding
autonomy track (ROADMAP.md, slices A1–A6).

```sh
athenz-task-operations start --grant <grant-id> --plan plan.json \
    --editor-script-for roadmap-1=editor1.json \
    --editor-script-for roadmap-2=editor2.json --confirm
athenz-task-operations resume <operation-id> \
    --editor-script-for roadmap-2=editor2.json --confirm
athenz-task-operations resume <operation-id> --retry-suspect \
    --editor-script editor.json --confirm
athenz-task-operations pause <operation-id>
athenz-task-operations abort <operation-id>
athenz-task-operations list [--grant <grant-id>]
athenz-task-operations show <operation-id>
```

Starting and resuming are explicit owner actions: both refuse
without `--confirm`. Editors are owner-written editor scripts,
exactly as in slice A3 — one script for every item
(`--editor-script`) or one per item (`--editor-script-for`).

## The operation record

An operation (`athenz.task-operation/v1`) is created from a planner
output and a grant, and freezes all of the following before anything
runs:

- the **queue**: the selected items, in order, with their full
  planner snapshots, plus a fingerprint (SHA-256) of the exact
  planner output they came from;
- the **permission fingerprint**: a hash of the grant's scope fields
  (objective, provenance, repository/worktree, task classes, file
  globs, tools, network policy, budgets, expiry). Volatile usage
  counters and the grant's lifecycle state are *not* part of it —
  spending budget or pausing a grant is not a scope change;
- the **code fingerprint**: a hash of the repository path, base
  commit, branch and queue fingerprint;
- **model and editor fingerprints**: opaque strings recorded at
  start. The CLI derives the editor fingerprint from the editor
  scripts' contents unless `--editor-fingerprint` overrides it;
  the model fingerprint defaults to `scripted/no-model`, because
  A4 ships no model editor;
- a **base revision per item** (repository HEAD and branch at
  creation, plus the A3 scratch branch once the item has run);
- per-item stage state, linked A3 execution ids, output summaries
  (outcome, attempts, edited files, stage results, branch/worktree),
  failure signatures, and an append-only event log;
- accrued wall-clock seconds and the drive segments they came from.

## State machines

Operation: `active` → `paused` (owner pause, or a refused resume),
`completed` (every item succeeded), `aborted` (owner abort, or a
resume refused by a missing/revoked/expired grant or a changed
permission fingerprint), `stalled` (see below).

Item: `pending` → `running` → one of `succeeded`, `failed`,
`blocked`, `denied` (the A3 outcome, recorded verbatim), with two
operation-level states in addition: `suspect` (below) and `skipped`
(pending items of an aborted operation).

The driver runs items **in order and stops at the first
non-success outcome**. Later items stay `pending` — the driver
never skips ahead past a failure, a block or a denial.

## Checkpoint discipline

Per-item state is written durably (a revision-checked
compare-and-swap update of the operation record, following the
scheduler's checkpoint pattern) at three points:

1. **before** the item executes — the item is `running` on disk
   before the A3 executor is invoked;
2. **after** the item executes — its outcome and its A3 execution
   id are linked into the record;
3. at every stop, refusal, pause, abort and completion.

A crash therefore leaves the worst case fully described: items
before the crash point are final, the item in flight is `running`,
and nothing is ever silently marked succeeded.

## Resume protocol

`resume_operation` verifies, in order, before executing anything:

1. **Suspect items.** A leftover `running` item means the previous
   process died mid-item. It is converted to `suspect`; any A3
   execution record the dead process created for it is linked as an
   orphan (its partial work stays inspectable and is never counted
   a success). The resume then stops with
   `suspect_item_requires_owner_decision` unless the owner passes
   `--retry-suspect`, which records the retry decision on the item
   and requeues it.
2. **Fingerprint drift.** If the caller supplies a model or editor
   fingerprint that differs from the recorded one, the resume is
   refused (`model_fingerprint_changed` /
   `editor_fingerprint_changed`) and the operation pauses. The new
   fingerprint is never silently adopted; there is no override flag.
3. **The grant.** It must still exist (`grant_not_found`), be
   neither revoked (`grant_revoked`) nor expired (`grant_expired`)
   — those abort the operation — and not be paused (`grant_paused`,
   the operation pauses and can be resumed once the grant is). Its
   permission fingerprint must match the recorded one exactly; any
   scope change aborts the resume with
   `permission_fingerprint_changed`. Scope changes require a new
   grant (slice A2) and therefore a new operation.
4. **Base revisions.** Immediately before each remaining item runs,
   the repository HEAD is compared with the item's recorded base
   revision. A mismatch blocks the item with
   `base_revision_changed` and stops the drive — there is **no
   automatic re-base**. The owner inspects, and either accepts the
   new base by starting a fresh operation or restores the old one.

Completed items are **never re-executed**: resume skips them by
state, and their A3 execution records stay linked as the evidence
of what ran. A failed, blocked or denied item may be retried by a
resume (each retry is a new A3 execution under the same grant
budgets); a `skipped` item belongs to an aborted operation and is
final.

## Loop and stall detection

Every non-success execution contributes a **failure signature**: a
hash of the A3 outcome, the failing stage, and the output tail,
normalized so that per-run worktree paths (which embed a fresh
execution id) and unittest durations do not disguise an identical
failure as a new one. Consecutive identical signatures for the
same item are counted **across resumes**. At the operation's stall
threshold (default 2, set at creation), the operation is marked
`stalled` with the item and signature recorded, and driving stops.
A different failure resets the count; a success clears it.

## Budgets across restarts

- The grant's budgets (tasks, test runs, retries, wall-clock) are
  consumed atomically by slice A3's authorization checks, so they
  accumulate across process lifetimes by construction; a resume
  also refuses up front when the grant's wall-clock budget is
  already exhausted.
- The operation's own `accrued_wall_clock_seconds` is persisted at
  every checkpoint: each drive segment credits its elapsed time at
  its durable boundaries, and grant-accounted seconds are folded in
  without double counting. A segment belonging to a dead process is
  credited only from the grant's accounting — its end is unknown,
  and downtime is never credited as work.

## Inspection

`show` (and `inspect_operation`) returns the full operation record
plus a structured summary:

- **attempted** — items that have run (or are in flight), with
  their execution ids;
- **changed** — per execution, the files edited and their unified
  diffs, and the scratch branch holding them;
- **tested** — per execution, every verification stage with exit
  code, skip and timeout flags, and the outcome;
- **blocked** — items in `blocked`, `denied` or `suspect` state,
  with the reason;
- **unfinished** — every item not `succeeded` or `skipped`, with
  its state and reason.

`list` returns operation records, optionally filtered by grant.

## Isolation and limits

- Operation records are private profile data, in the same profile
  database as grants and execution records — never in a repository.
- Items execute in slice A3's disposable worktrees, one per
  execution, each based on the item's recorded base revision. An
  operation is a queue of **independent** candidate executions:
  because A3 never commits, one item's uncommitted edits are not
  visible to the next item's worktree. Composing or landing the
  results is promotion — slice A5.
- **Single-driver assumption (explicit):** records are updated
  with a revision check that fails closed on a conflicting writer,
  but there is no cross-process locking and no background daemon.
  The owner drives one operation at a time; a second driver is
  detected at its next checkpoint, not prevented in advance.

## Non-goals

- **No promotion.** Nothing here commits, merges, pushes or
  disposes of scratch branches; that boundary is slice A5.
- **No model editor.** The editor interface is slice A3's; a
  model-backed editor plugs in there and inherits this module's
  fingerprint checks, gaining no wider powers.
- **No re-basing, no scope adoption, no grant mutation.** An
  operation never edits its grant, its queue or its fingerprints
  after creation.
