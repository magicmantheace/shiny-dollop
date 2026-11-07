# Durable audit record format v2 — design proposal (NOT accepted)

Status: **proposal**, written 2026-11-06 when development resumed
under ADR 0023's working queue ("completion of the Phase 2 durable
audit record format" is the queue head). Nothing in this document is
implemented yet. When the owner accepts a direction, the decision is
recorded as an ADR and this note is folded into `docs/AUDIT.md`.

## What is actually still open

The Phase 2 roadmap item "Add durable audit record format" is the
last unchecked box in Phase 2. The v1 system (`docs/AUDIT.md`) is
already substantial: versioned JSONL records, hardened append path,
one-slot rollover, offline structural inspection, snapshot
export/verify against a retained digest, explicit archive release
with receipts, and extensive host + guest gates. The recorded gaps
that keep the item open are:

1. **Tamper evidence** — no integrity chain: a well-formed edit,
   deletion, or reordering of records inside a journal is not
   detectable by `veil-audit check` (it says so itself).
2. **Independent integrity anchoring** — nothing binds a journal's
   current head to a value held separately, so tail truncation is
   undetectable even with digests of exported snapshots.
3. **Automatic retention** — rollover has one archive slot and then
   refuses; there is no policy beyond the owner's manual release.
4. **Disk-full policy on the installed system** — ENOSPC behaviour
   is gate-tested on synthetic filesystems, but no policy decides
   what a real installed system does when the state partition fills.
5. **Power-loss / interrupted-rotation durability** — process-kill
   and emulator-stop evidence exists; a cut between rename, directory
   sync, and next-file creation, and real device-cache loss, remain
   unproven (and partly unprovable in QEMU).

Items 4 and 5 are policy/evidence problems, not format problems.
This proposal covers items 1 and 2 (the format change). Items 3–5
are listed so the roadmap item is not declared complete on the
format work alone.

## Frozen-zone analysis (ADR 0023)

The audit record format and the `veil-audit` tooling are **not** in
ADR 0023's enumerated frozen zone: they are not kernel/boot
configuration, not the bootstrap `/init` or state-partition
identity/mount behaviour, not slot selection or boot-attempt
accounting, not trial-boot/health/owner-confirm/rollback logic, and
not the update transaction or signature verification. The writer is
`veil-core` (a userspace service) plus offline tools; state lives on
the data/state partition in the audit subsystem's own format.

Adjacencies that must NOT be touched by this work:

- The **A/B updater's own control records** (veil-ab state on the
  state partition) are the updater's, not core audit's. Untouched.
- The **graphical update controls' behaviour contract**, including
  the audit wording the S2 reskin preserved byte-for-byte, is the
  update GUI's own session surface. Untouched.
- The **supervision/session infrastructure** (how services start)
  is unchanged; the supervisor's lifecycle *events* keep their
  names and fields — only the record envelope gains chain fields.

One ADR 0023 consequence does bind this work: the chained writer
changes the shipped image's payload, so under Decision 3 the format
is not accepted until the joined QEMU acceptance (boot to the
authenticated desktop) **and** the complete update round trip have
been re-run green against the image carrying it, with the evidence
recorded. PR #17 remains unmerged regardless.

## Proposed v2 record

Schema identifier `synveil.audit/v2`. All v1 envelope fields are
unchanged. Two fields are added:

- `prev_digest` — BLAKE2b-512 (lowercase hex) of the previous
  record's canonical bytes in the same journal file, or the string
  `"genesis"` for the first record of a file whose predecessor is
  not an archived sibling (fresh journal).
- `record_digest` — BLAKE2b-512 of the record's canonical
  serialization with `record_digest` itself omitted (all other
  fields, including `prev_digest`, in their emitted byte form).

Canonical serialization is the emitted JSON line without its
trailing newline — the writer already guarantees one record per
line with escaped control characters, so the bytes on disk ARE the
canonical form; no re-serialization is needed to verify.

Chain continuity rules:

- **Within a file:** record *n*'s `prev_digest` is the digest of
  record *n−1*'s line bytes.
- **Across rollover:** the new active file's first record carries
  `prev_digest` = digest of the archived file's last record, and a
  `fields` marker naming the archive it continues. The existing
  rollover already syncs the archive before creating the new file,
  so the digest is computed from durable bytes.
- **Across process restarts:** the writer already opens the journal
  under the stable lock, refuses incomplete tails, and reads the
  final byte before appending. It additionally reads the final
  record to continue the chain. An incomplete tail already refuses
  appends, so there is no "continue from a partial record" case.
- **First record ever (no journal exists):** `prev_digest` is
  `"genesis"`.

## Checker and anchoring

- `veil-audit check` becomes chain-aware for v2 journals: it
  verifies every link and digest and reports the first break's
  record index and kind (edit / reorder / delete-middle /
  digest-mismatch). Its report gains `chain: {verified: bool,
  records: n, head_digest: …}` and keeps `authenticated: false` —
  a chain proves internal consistency and makes later edits
  evident; it does not prove origin, and it does not detect
  deletion of whole tail records on its own.
- **Anchoring** reuses the existing export machinery: the export
  receipt already carries a BLAKE2b-512 of the snapshot. For a v2
  journal the receipt additionally records `head_digest` (the last
  record's `record_digest`). An owner who retains receipts can
  detect tail truncation by comparing a later journal's chain
  against the anchored head. No new tool, no new trust claim:
  `verify` still detects changed bytes relative to a retained
  digest, now including "the journal used to continue past this
  head and no longer does."

## Compatibility

- v1 journals remain readable forever: `check`, `export`, `verify`,
  `release-archive`, and `inspect-release` accept v1 exactly as
  today (their strict schemas are per-version).
- The writer emits v2 only for a **new** active file (fresh journal
  or the file created by rollover). An existing v1 active journal
  keeps appending v1 until it rotates, so a live system migrates at
  its rotation boundary with no rewrite of history. Mixed layouts
  (v1 archive + v2 active) are valid and the checker reports each
  file's version.
- Record size bounds are unchanged (64 KiB/record, 4 MiB/file);
  the two digest fields add ~200 bytes per record.

## What this does not solve (stated plainly)

- A root attacker can rewrite the whole file with a self-consistent
  chain. Tamper *evidence* here is against later modification of
  records relative to an anchored head or an exported snapshot —
  the same trust level the existing export/verify already states.
- Tail truncation is detectable only against a previously anchored
  head. Without an anchor, a shortened chain is internally valid.
- Nothing here addresses automatic retention (gap 3), installed
  disk-full policy (gap 4), or power-loss durability (gap 5).

## Implementation slices (proposed order)

1. **Host slice:** writer chaining in `audit.rs` (v2 emit for new
   files), chain verification in `audit_check.rs`, unit + fault-
   injection + process-cut tests extended to chained journals.
   Gate: full Rust suite green (baseline 182 + audit tests).
2. **Tooling slice:** export/verify receipts carry `head_digest`
   for v2; release/inspect paths accept v2 journals. Gate: host
   suite green.
3. **Acceptance slice:** rebuild the native image with the chained
   writer; re-run the native audit gates, the joined acceptance,
   and the full update round trip per ADR 0023 Decision 3; record
   exact-revision evidence under `docs/validation/`. Only then is
   the format called accepted, and the ROADMAP note is updated to
   name what remains (gaps 3–5) instead of silently closing the
   item.

## Open questions for the owner

- Is BLAKE2b-512 (already the project's pinned digest, via the
  Argon2 dependency) acceptable for the chain, or should the chain
  use a different primitive?
- Should the writer switch an existing v1 active journal to v2 at
  first open after upgrade (chain anchored to the v1 tail by
  digesting its last line), or is rotation-boundary migration
  (proposed above) acceptable?

---

## Implementation amendment (2026-11-06) — slice 1 landed at host level

Written after implementing slice 1 against the actual code; it
corrects four things the proposal above got wrong or left open:

- **Digest: SHA-512, not BLAKE2b-512.** There is no `digest.rs`
  and no BLAKE2b in the tree; `veil-core` ships an in-tree
  SHA-512 (`src/veil-core/src/sha512.rs`), which the chain uses.
- **Writer: the veil-core journal path, not `audit_json.rs`.**
  The durable journal is written by `audit::emit` →
  `append_record` in `src/veil-core/src/audit.rs` (the
  `audit_json.rs` writer serves the A/B agents' separate
  journals, which still write v1 — chaining them is future
  work, not slice 1). The chained append shares the existing
  locked append flow via a prepare step that reads the journal
  tail inside the directory lock.
- **Link definition (resolves the chain-continuity question):**
  a v2 record's `record_digest` = SHA-512(prev_digest bytes ‖
  canonical record bytes without `record_digest`); a **v1
  record's link hash is defined as SHA-512 of its raw line
  bytes**, so pre-chain journals link into the chain at the
  upgrade boundary with no migration event, and the first
  record after a rollover chains from the `.1` archive's tail.
  New records use schema `synveil.audit/v2` (the v1 envelope
  plus the two digest fields); the checker accepts exactly the
  v1 or v2 shape and verifies links within the file, reporting
  the first chained record's `prev_digest` as the chain
  `anchor`. Anchoring that value in export receipts (the
  proposal's slice 2) is **not** implemented yet.
- **Status:** slice 1 (writer chaining + checker verification
  + tests) is implemented and the full `veil-core` suite
  passes (158 library tests + integration targets). Slice 2
  (export/verify/release anchoring) and slice 3 (native QEMU
  acceptance — the ADR 0023 Decision 3 re-validation) remain
  open, so per that decision the format is **not yet accepted**:
  it must not be described as accepted until an image carrying
  it passes the joined acceptance and a full update round trip.

One environment note from the test work: the rollover-chain
test intermittently saw flock `WouldBlock` under parallel test
load because the crash-worker tests fork child processes while
other tests hold the journal's directory lock (the child
inherits the locked description until exec; strace-verified —
the lock file was touched by no other thread). The writer takes
the lock before any write, so the contention is a clean,
retryable failure; the test retries on `WouldBlock` for that
reason. Production append rates make the window vanishingly
small, and `emit` already degrades truthfully on write failure.

## Implementation amendment (2026-11-06) — slice 2 landed at host level

The tooling slice is implemented in `audit_export.rs` and the
`veil-audit` CLI:

- **Export receipts anchor the chain.** For a chained (v2)
  journal, the `synveil.audit-export/v1` receipt gains a `chain`
  object: `anchor` (the first chained record's `prev_digest`,
  as reported by the checker), `head_digest` (the last record's
  record digest — the checker's chain `tail`), `chained_records`,
  and `records` (the head's position: the chained count within
  the export's total record count). v1 receipts are unchanged.
  This is the proposal's anchoring design with the slice-1
  digest amendment applied: the anchor values are SHA-512 chain
  digests; the snapshot's own checksum stays BLAKE2b-512.
- **Receipt verification.** `veil-audit verify --path SNAPSHOT
  --receipt RECEIPT-FILE` verifies a snapshot against its
  retained receipt (the legacy `--digest` form is unchanged and
  the two are mutually exclusive). The receipt file is bounded
  (8 KiB) and decoded with the strict audit JSON decoder. The
  receipt must name the exact byte count, record count and
  snapshot digest, and — for a v2 export — the exact anchor,
  head digest and head position. A mutated record, a receipt
  naming the wrong anchor or head, and a truncated export all
  fail verification; truncation is caught by the retained head
  even though the truncated bytes still form an internally
  valid shorter chain. The trust statement is unchanged:
  verification detects changed bytes relative to a separately
  retained receipt; it does not authenticate origin, and a root
  attacker who can rewrite both snapshot and receipt is out of
  scope, exactly as for digest verification.
- **Release/inspect accept v2.** The retention release and
  inspection paths run on the chain-aware inspector from
  slice 1, so chained archives release and inspect like v1;
  a regression test now covers release + inspection of a
  chained journal.
- **Status:** host gate green — the full `veil-core` suite
  passes (162 library tests + integration targets, including
  new receipt generation/verification unit tests, tamper cases,
  and a CLI test that exports a genuine chained journal written
  by the real core and verifies it against its receipt). Slice 3
  (native QEMU acceptance per ADR 0023 Decision 3) remains
  open, so the format is still **not accepted** and must not be
  described as accepted until that pass lands.
