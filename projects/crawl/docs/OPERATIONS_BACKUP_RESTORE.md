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
   `<state>/state/runtime.json` and the checkpoint envelope digest in
   `<state>/checkpoints/latest.json`.

That is the complete backup: canonical state is fully contained in `<state>/`.

## Restore procedure

1. Stop any running runtime against the target state directory.
2. Replace `<state>/` with the backup copy.
3. Start the runtime with `--resume`. It validates the checkpoint digest chain
   and the ledger cursor before resuming; a corrupt checkpoint falls back to the
   previous retained checkpoint, and a corrupt `latest.json` pointer is recovered.
4. Confirm `checkpoint_recoveries >= 1` and `canonical_recovery_failures == 0`
   in `runtime.json`, and that event IDs in `underreach.sqlite3` remain unique.

## Schema migration strategy

Canonical Crawl state is persisted as versioned JSON envelopes (pydantic
`model_dump(mode="json")`) plus a small, stable relational shell (`CrawlRow`,
`CrawlEventRow`: id/status/floor/tick columns only). Migration policy:

1. **Envelope version is authoritative.** Every persisted JSON blob carries its
   protocol/schema version. Readers validate on load and reject unknown major
   versions rather than guessing.
2. **Additive changes are free.** New optional fields default on read; old
   writers never break new readers and vice versa for additive fields.
3. **Breaking changes ship a migrator.** A breaking schema change must add a
   `migrate_<from>_to_<to>()` function, covered by a test that round-trips a
   real persisted checkpoint through the migrator and asserts fingerprint
   equality of the canonical content. The migrator runs once at load/resume;
   the original blob is retained until the migrated checkpoint is verified.
4. **The relational shell does not drift.** `crawl_events` / `crawl` tables
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
