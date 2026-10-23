# Crawl / The Underreach — Backup, Restore & Schema Migration

Complements `UNDERREACH_ALPHA_OPERATOR_GUIDE.md`. Local-first; no cloud services required.

## State layout

A running runtime owns one state directory (passed as `--state-directory`):

```
<state>/
  runtime.lock            # process lock (stale-lock recovery built in)
  state/
    runtime.json          # last written status snapshot
    underreach.sqlite3    # canonical Crawl rows + canonical event rows
  checkpoints/            # underreach.alpha-checkpoint.v1 envelopes
    latest.json           # pointer to newest verified checkpoint (corrupt-pointer fallback built in)
    <checkpoint-id>/...
  logs/
```

Checkpoints are atomic (tmp + fsync + validate + rename) with a digest chain
(envelope, fingerprint, ledger cursor with ID + content digests); retention is 12.

## Backup procedure

Stop the runtime first (create `<state>/stop.request`, or clean shutdown):

1. Verify the runtime stopped: `runtime.lock` released and `runtime.json`
   `overall_status` is `stopped`.
2. Copy the whole `<state>/` directory to the backup location:
   `robocopy <state> <backup> /MIR` (Windows) or `rsync -a <state>/ <backup>/` (Linux).
3. Record the fingerprint: the `final_fingerprint` / `final_ledger_digest` fields in
   `<generated>/underreach_alpha_runtime_report.json` (the report is written to
   the separately configured `--generated-directory`, not under `<state>/`; the
   `<state>/state/runtime.json` status snapshot does not carry these fields)
   and the checkpoint envelope digest in
   `<state>/checkpoints/latest.json`.

That is the complete backup: canonical state is fully contained in `<state>/`.

## Restore procedure

1. Stop any running runtime against the target state directory.
2. Replace `<state>/` with the backup copy.
3. Start the runtime with `--resume`. It validates the checkpoint digest chain
   and the ledger cursor before resuming; a corrupt checkpoint falls back to the
   previous retained checkpoint, and a corrupt `latest.json` pointer is recovered.
4. Confirm `checkpoint_recoveries >= 1` and `canonical_recovery_failures == 0`
   in the latest `underreach_alpha_runtime_report.json` in the generated
   directory — these counters are report-only. `runtime.json` instead carries
   `restart_count` / `recovery_count` (and `overall_status`), and the
   `<state>/checkpoints/latest.json` pointer proves which checkpoint the resume
   validated. Also confirm that event IDs in `underreach.sqlite3` remain unique.

## Schema migration strategy

Canonical Crawl state is persisted as versioned JSON envelopes
(`{"protocol", "schema_version", "state"|"event"}` around the pydantic
`model_dump(mode="json")` payload) plus a small, stable relational shell
(`CrawlRow`, `CrawlEventRow`: id/status/floor/tick columns only). Checkpoints
are versioned separately (`underreach.alpha-checkpoint.v1` protocol plus a
digest over the envelope body). Migration policy:

1. **Envelope version is authoritative.** Every persisted canonical JSON blob
   carries its protocol (`underreach.crawl-state.v1` /
   `underreach.crawl-event.v1`) and an integer `schema_version` (currently 1).
   Readers validate on load (`_decode_state` / `_decode_event` in
   `crawl_persistence.py`) and raise `PersistenceVersionError` on an unknown
   protocol or schema version rather than guessing. Blobs written before
   envelopes existed carry no `protocol` field and are treated as schema v1.
2. **Additive changes are free.** New optional fields default on read; old
   writers never break new readers and vice versa for additive fields.
3. **Breaking changes are detected, not silently loaded.** A breaking schema
   change must bump the envelope's `schema_version`; old readers refuse the
   new blobs with a clear error. The migration workflow for that case is to
   stop the runtime and restore from a pre-change checkpoint backup, or to
   write a one-off `migrate_<from>_to_<to>()` script whose round-trip through
   a real persisted checkpoint asserts fingerprint equality of the canonical
   content. No automated migrator exists yet — an unknown version is a hard
   failure, never a guess.
4. **The relational shell does not drift.** `crawl_events` / `crawls` tables
   carry only scalar index columns; canonical truth lives in the JSON payloads,
   so column migrations are not expected. If a column is ever added, it is
   nullable with a documented default and `initialize()` creates it idempotently.
5. **No destructive migrations.** `reset_all()` (full wipe) is a test/dev-only
   operation and is never invoked by the runtime's normal start/resume path.

## Admin intervention

Not implemented as of 2026-10-23: there is no admin console for Crawl, and
operator actions (stop/resume/restore) are filesystem-level, never injected as
canonical events. If admin intervention as an authoritative event is ever
required, it must be recorded through the canonical event ledger with explicit
`admin` provenance — never by editing the database directly.
