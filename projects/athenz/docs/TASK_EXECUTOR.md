# Isolated task executor (slice A3)

`athenz-task-executor` executes **one** planner queue item (slice A1)
under **one** standing task grant (slice A2) through a bounded
edit/test feedback loop. It is the third slice of the owner-directed
persistent coding autonomy track (ROADMAP.md, slices A1–A6).

```sh
athenz-task-executor run --grant <grant-id> --plan plan.json \
    --item roadmap-1 --editor-script editor.json --confirm
athenz-task-executor show-record <execution-id>
athenz-task-executor list-records --grant <grant-id>
```

Execution is an explicit owner action: `run` refuses without
`--confirm`. The plan must have been generated for the same repository
the grant authorizes; a plan for any other repository is refused.

## The loop

```
plan -> edit -> syntax -> targeted tests -> full regression
     -> diagnose -> retry (bounded)
```

1. **Plan.** The repository HEAD is fingerprinted (`base_sha`), and
   starting the task is authorized with `new_task=True`, consuming the
   grant's task budget atomically with the check. A denial here means
   no worktree and no edits (`outcome: denied`).
2. **Worktree.** A disposable Git worktree is created on a scratch
   branch `athenz-task/<grant-id>-<item-id>-<execution-suffix>` at the
   fingerprinted base, under the private profile's `task-worktrees/`
   directory. The owner's original working tree is never written.
3. **Edit.** The editor proposes full-file replacements. *Every* edit
   is authorized (`tool=edit`, the file's scope) **before any edit of
   the attempt is applied**, so a denied edit aborts the attempt with
   nothing half-applied. Edit paths are additionally resolved strictly
   inside the worktree: no absolute paths, no `..`, no symlink
   components, no protected filenames (the supervised-coding denylist).
4. **Verify.** Stages run in order and stop at the first failure:
   `syntax` (`py_compile` of the Python files edited this attempt),
   `targeted` (unittest modules derived from the files edited so far:
   an edited test file targets itself; an edited source file targets
   `tests/test_<stem>.py` when it exists; plus any `--test-module`
   given), then `full` (`unittest discover -s tests`). A stage with
   nothing to run is recorded as skipped, with its reason. Success
   requires every non-skipped stage green **and** at least one test
   stage to have actually run — an attempt that verifies nothing is
   `blocked` (`no_runnable_verification`), never a success.
5. **Diagnose and retry.** A failed stage's exit code and output tail
   become the diagnostics handed to the editor for the next attempt.
   Between attempts, authorization is re-checked and one retry is
   consumed atomically (with accrued wall-clock seconds), so a grant
   paused or revoked mid-run stops the loop at that boundary.

Attempts are bounded by the grant's retry budget **and** a hard cap
of 5 attempts per task, whichever comes first. Each test-runner
invocation consumes one of the grant's test runs, atomically with its
authorization check.

## The editor interface

An editor is a callable:

```python
editor(item, worktree, diagnostics) -> [{"path": rel, "content": text}]
```

`diagnostics` is `None` on the first attempt, then a dict with the
failing `stage`, `exit_code`, `timed_out`, an `output` tail and the
`edited_files` so far. Raising `EditorBlocked` stops the run as
`blocked`; returning no edits does the same.

A3 ships the harness, **not** a model integration. The deterministic
editor provided is `ScriptedEditor`, driven in the CLI by an editor
script the owner writes and can review in advance:

```json
{"attempts": [[{"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}]]}
```

Each inner list is one attempt's edits. An optional top-level
`"blocked": "reason"` makes the editor report itself blocked. A
model-backed editor plugs into the same callable interface later; it
will get no wider powers than this interface and the grant allow.

## The constrained runner

- **Fixed argv templates only** — `syntax`, `targeted`, `full`
  (see `build_command`). There is no shell, no string command, and no
  way to name another program. Commands run only when the grant's
  `permitted_tools` includes `run_tests`.
- **Scrubbed environment.** A test command inherits only `PATH`,
  `PATHEXT`, `SYSTEMROOT`, `WINDIR`, `COMSPEC`, `TEMP`/`TMP`/`TMPDIR`,
  `LANG`, `LC_*` and `TZ`. `HOME` is redirected into the worktree;
  `PYTHONNOUSERSITE=1`, `PYTHONDONTWRITEBYTECODE=1` and a per-run
  `PYTHONPYCACHEPREFIX` (see bytecode freshness below) are set.
  Credentials, tokens, `ATHENZ_HOME` and `PYTHONPATH` never reach a
  test process.
- **Bytecode freshness.** A verdict is earned by the source bytes on
  disk, never by a `__pycache__` entry. Python's timestamp-based
  cache validation compares only the source's mtime (whole seconds)
  and size, so a same-size file rewritten within one mtime tick is
  served *stale* bytecode by a plain interpreter — meaning a
  verification run could pass or fail against code that is no longer
  on disk. The runner defends in independent layers: (1) bytecode
  caches under the worktree are purged before and after every
  invocation (only `__pycache__` directories and `*.pyc`/`*.pyo`
  files; symlinks are never followed out of the tree); (2) the
  scrubbed environment points `PYTHONPYCACHEPREFIX` at a fresh
  empty directory created per run and removed afterwards, so every
  cache lookup misses and imports compile from source; (3) `-B` in
  every argv template and `PYTHONDONTWRITEBYTECODE=1` stop runner
  processes writing caches at all. Note `-B` alone would not
  suffice — it governs writing, not reading — which is why the
  layers are combined. A side benefit: runs leave no `__pycache__`
  behind in the kept worktree. Slice A5's regression-at-proposal run
  shares this runner and gets the same guarantee.
- **Timeout.** Every invocation is bounded (`--command-timeout`,
  default 120 s); a timeout is recorded as a failed run with
  `timed_out: true`, not as an executor crash.
- **No network.** Test commands get no network access by construction
  in this slice: no template can open a connection, and the scrubbed
  environment carries no proxy or credential configuration. The
  grant's network policy governs future tool classes, not these
  templates.
- A worktree is an isolation boundary for *edits*, not an OS security
  sandbox: test code is the granted repository's own code, run with
  the owner's privileges minus the scrubbed environment. That is the
  same honest limit the supervised worker documents.

## Execution records

Every run writes a durable record (`athenz.task-execution/v1`) to a
`task_executions` table in the private profile database — never into
any repository. A record holds the grant id, the queue item, the
repository, the fingerprinted base commit and branch, the scratch
branch and worktree path, and **every attempt**: the edits applied
(each with its unified diff), every stage run with argv, exit code,
timeout flag, duration and stdout/stderr tails, plus the final
`outcome` and `stop_reason` and a snapshot of the grant's budget
usage. Failures are recorded with the same fidelity as successes;
`show-record` returns the record verbatim. Outcomes are:

| Outcome | Meaning |
| --- | --- |
| `succeeded` | All non-skipped stages green, at least one test stage ran. |
| `failed` | Attempts or budgets exhausted with tests still failing. |
| `blocked` | The editor stopped, the grant was paused/revoked mid-run, or nothing runnable could verify the work. |
| `denied` | An authorization check refused an operation (nothing denied was performed). |

## Isolation guarantees

- The executor refuses to operate on any path outside the granted
  repository's disposable worktree: edits resolve strictly inside it,
  and test commands run with the worktree as their working directory.
- It never writes to the owner's original working tree, and never
  commits: the scratch branch stays at the base commit with the edits
  uncommitted in the kept worktree.
- It has **no code path that reads the private Twin/identity stores**.
  Its only profile access is the grant store (for `authorize()`) and
  its own execution-record tables.
- It cannot reach other repositories: the grant names exactly one,
  and the plan must have been generated for that same repository.

## Non-goals

- **No promotion, merge, push or disposal.** The scratch branch and
  worktree are kept for owner review; what happens to them is slice
  A5's promotion boundary.
- **No durability or resume across process restarts.** A run is
  in-memory; its record is the durable artifact. Resumable operations
  are slice A4.
- **No model editor yet** (see the editor interface above), and no
  multi-item runs: one item, one grant, one run.
