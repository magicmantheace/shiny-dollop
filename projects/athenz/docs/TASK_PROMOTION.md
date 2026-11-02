# Promotion and self-development boundary (slice A5)

`athenz-task-promote` is the bridge between a finished slice A3/A4
candidate and anything more durable — and the bridge is deliberately
narrow. It is the fifth slice of the owner-directed persistent coding
autonomy track (ROADMAP.md, slices A1–A6).

```sh
athenz-task-promote prepare --execution <execution-id>
athenz-task-promote prepare --operation <operation-id> --item <item-id>
athenz-task-promote show <proposal-id>
athenz-task-promote list [--execution <execution-id>]
athenz-task-promote commit <proposal-id> --confirm
athenz-task-promote discard <proposal-id> --confirm
athenz-task-promote discard --execution <execution-id> --confirm
```

A candidate is what slices A3/A4 leave behind: edits sitting
**uncommitted** on an isolated scratch branch
(`athenz-task/<grant>-<item>-<exec>`) in a disposable worktree under
the private profile's `task-worktrees/` directory. Slices A3/A4 never
commit, merge, push or delete anything; what may happen to a
candidate is decided here, by the owner, one proposal at a time.

## The proposal

`prepare` builds a durable proposal record
(`athenz.task-promotion/v1`) in the private profile database — never
in a repository. It refuses unless the target is a **succeeded**
execution: a failed, blocked or denied A3 record, or an A4 operation
item in any other state, has no proposal path. A proposal contains:

- **The full diff** of the scratch worktree against the execution's
  recorded base revision: per-file status and line counts, a stat
  summary, the complete patch text, and a SHA-256 hash of that patch.
  Tracked changes come from `git diff <base>`; files the editor
  created (untracked) are appended as new-file patches. Python
  bytecode caches (`__pycache__`, `*.pyc`) are excluded — they are
  artifacts of running the tests, including A3's own verification
  runs, not candidate edits.
- **The linked evidence**: the A3 execution's attempts verbatim
  (every edit's diff, every stage run with its argv, exit code,
  timeout flag and output tails), its outcome and budget usage, and —
  for an operation item — the A4 output summaries and the
  operation's permission and code fingerprints.
- **A fresh regression check** (see below).
- **The grant state at proposal time**: a snapshot of the grant's
  lifecycle state, scope and budget usage, or `null` if the grant no
  longer exists.
- **A rollback section**: the base revision and the exact discard
  procedure, manual equivalent included.
- **The remaining owner steps**, spelled out in the proposal itself:
  review; optionally checkpoint-commit or discard through this CLI;
  and the landing actions this module cannot perform (below).

One live proposal per execution: preparing a second proposal while
one is `prepared` or `committed` is refused — discard the old one
first. Preparing also refuses when the worktree is gone, is on a
different branch than recorded, or its scratch branch has advanced
past the recorded base (something outside A3/A5 committed there;
this module only proposes uncommitted candidates).

## The regression-at-proposal rule

Execution-time test results are evidence about the past. A proposal
therefore re-runs the **full test suite** (`unittest discover -s
tests`) in the scratch worktree at proposal time, through slice A3's
constrained runner exactly: the fixed argv template, the scrubbed
environment, the timeout — and a fresh grant authorization first
(tool `run_tests`, consuming one test-run budget atomically with the
check, exactly as A3's own stage runs do). The actual result — argv,
exit code, timeout flag, duration, output tails — is recorded in the
proposal.

A proposal is **promotable** only when that fresh regression actually
ran and was green, and the candidate diff is non-empty. A red
regression, an unrunnable one (no `tests/` directory, runner
unavailable, or the grant no longer authorizing test runs — paused,
revoked or expired grants included) marks the proposal
**not promotable**, with the specific reason recorded. The proposal
still exists and can be inspected and discarded; it cannot be
checkpoint-committed. `prepare` documents its cost plainly: it is
read-only against the candidate *except* for this regression run,
which executes the worktree's own test suite.

## The checkpoint commit (the module's only write)

`commit` — explicit owner action, `--confirm` required — creates
**one local commit** on the proposal's isolated scratch branch,
containing exactly the proposal's diff, with a message referencing
the proposal, execution (and operation, when applicable), grant and
base revision. Before committing it verifies, in order:

1. the proposal is `prepared` and promotable;
2. the worktree is inside the managed `task-worktrees/` location and
   is on the recorded scratch branch, whose HEAD is still the
   recorded base revision;
3. **the diff-match rule**: the worktree's current diff, recomputed
   at commit time, hashes identically to the proposal's recorded
   diff and names the same files. If the candidate changed since the
   proposal — an edit, a new file, anything — the commit is refused,
   the refusal is recorded in the proposal's event log, and the owner
   re-prepares. There is no "commit whatever is there now" mode.

After committing, the commit's parent (must be the recorded base)
and its file list (must equal the proposal's) are verified and
recorded in the proposal. Nothing else is written anywhere: the
repository's own branch, its working tree and every other branch are
untouched — the tests assert this by hash comparison.

## Discard

`discard` — explicit owner action, `--confirm` required — is the
disposal path slices A3/A4 deferred here. It works on a proposal or
directly on an execution id (any outcome: failed and blocked
candidates are kept worktrees too, and they need a disposal path).
Before removing anything it computes the candidate's final diff,
then removes the scratch worktree (`git worktree remove --force`)
and deletes the scratch branch (`git branch -D` — deliberately the
forceful form: a scratch branch is unmerged by construction, and a
checkpoint commit on it is discarded with it, its SHA recorded).
The disposal is recorded in the promotion store: what was discarded
(branch, worktree, base revision), its final diff hash and stat,
any checkpoint commit SHA, when, and that it was an owner action.

Refusals: without `--confirm`; for an already-discarded proposal;
for **any branch that is not an `athenz-task/` scratch branch**; and
for **any worktree outside the managed `task-worktrees/` location**.
Those two scope checks run before any Git operation, so a tampered
or foreign record cannot turn discard into a general deletion tool.

## What remains owner-only, and why

This module exposes **no** push, merge, tag, release, package
installation, deployment or self-update operation — the test suite
asserts this over the module's public API surface and the CLI's
subcommand set. That is the self-development boundary stated in the
roadmap: this machinery can *prepare* candidates and, under explicit
owner confirmation, locally commit or discard them on isolated
branches. It cannot land them anywhere, and it cannot modify the
running AthenZ — an update must not replace the currently functioning
Twin on its own.

Landing a checkpointed candidate — merging it into a protected
branch, pushing it to a remote, tagging or releasing it, installing
it, deploying it — remains a separately reviewed owner decision,
taken through the owner's own route with its own regression and
rollback checks (the same reason slice A2 lists push/merge/release/
install/deploy and private-data access as never grantable). A grant
cannot widen this boundary either: nothing in slice A2's scope fields
is consulted here except the regression run's `run_tests`
authorization, and no grant state makes a proposal promotable that
its fresh regression did not earn.

## Limits

- **Single driver, like A4.** Proposal records are plain durable
  rows; there is no cross-process locking. The owner drives one
  promotion action at a time.
- **The regression is the repository's own test suite**, run with
  the owner's privileges minus A3's scrubbed environment — the same
  honest limit A3 documents for its runner. It is evidence, not a
  sandbox verdict. (An earlier version of this note flagged that the
  regression inherited Python's bytecode-cache semantics for files
  rewritten inside one mtime tick — a same-size rewrite could be
  judged against stale bytecode. That is **fixed**: the shared A3
  runner now purges worktree caches around every run, redirects
  cache reads to a fresh empty per-run `PYTHONPYCACHEPREFIX`, and
  disables cache writes, so the regression judges the candidate
  bytes on disk. See "Bytecode freshness" in
  `docs/TASK_EXECUTOR.md`.)
- **No composition.** Each proposal is one execution's candidate.
  Combining several items' candidates into one landing is owner
  work at landing time, not something this module stages.
