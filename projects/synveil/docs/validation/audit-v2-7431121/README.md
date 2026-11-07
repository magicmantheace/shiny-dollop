# Durable audit v2 — native QEMU acceptance (slice 3)

Dated 2026-11-06. QEMU evidence only; no physical hardware is
claimed (physical validation remains parked under ADR 0023).

- Image source revision: `743112180f5b37a35da8d6fe7db699231c87b01d`
  (the revision the guest binaries stamp in their audit records;
  includes slice 1 `6e2fbdd`, slice 2 `38d8691`, the writer
  lock-wait fix `1d8a29a`, and the boundary-anchor checker fix
  `e4ec83f`).
- Joined image SHA-256:
  `97fb9c368e551963240740ee9ebc8d7063b9fb2cdac6d2a46a046f272bd24af3`
- Acceptance driver: `tests/smoke-native-audit-v2.py`, marker
  `SYNVEIL_AUDIT_V2_NATIVE_PASS` (one boot-pair attempt).
- Joined acceptance on the same image:
  `SYNVEIL_NATIVE_JOINED_QEMU_ENROLL_LOGIN_WESTON_PASS`
  (`joined-guest-validation.json`, `joined-boot1.log`,
  `joined-boot2.log`).

## What was proven

A private copy of the joined image had its state partition
seeded host-side (debugfs on the extracted ext4) with a
three-record **v1 journal** in the exact line form the pre-v2
writer emitted (a disclosed fixture — its `fields` say so —
generated for this gate, not by a guest). The joined harness's
graphical enrollment and two-boot login flow then ran against
that image. After the boots, the journal was extracted (the
ext4 journal replayed on the scratch copy with `e2fsck` first:
the boots end in a power cut, and raw reads otherwise see an
un-checkpointed tree) and verified:

- The 3 seeded v1 records are preserved **verbatim** as the
  journal's first records.
- The guest core appended **10 chained v2 records** across the
  two boots; the first v2 record's `prev_digest` equals
  SHA-512 of the last seeded v1 line — the v1→v2 boundary
  holds natively exactly as designed.
- The **packaged** `veil-audit` from the image's own rootfs
  accepts the journal (`check.json`): 13 records, 10 chained,
  chain anchor = the boundary digest, tail = the final v2
  record digest.
- The packaged `veil-audit export` produced a receipt pinning
  that anchor, the head digest, and the head position
  (10 chained of 13 records) (`receipt.json`).
- The receipt verifies the exported snapshot on the host with
  both the host-built and the packaged `veil-audit`
  (`verify --receipt`; `verify-host.txt`), and a truncated
  snapshot is **refused** against the same receipt.
- Both boot logs contain **zero** `persistent write failed`
  lines (see the lock-wait fix below).

Honest scope note: the export and the verification ran with
the packaged tooling **on the host, against the guest-written
journal** — not executed inside the guest. The in-guest links
of the chain (native v2 writing + the boundary) are what this
gate adds over the host-level slices.

## What this gate found and fixed

1. **Writer dropped records under lock contention**
   (`1d8a29a`). Slice 1 took the journal lock non-blocking, so
   when the supervisor and its supervised core appended
   concurrently at guest startup — each critical section
   carrying file + directory fsyncs on emulated storage — a
   contended append dropped its record (`persistent write
   failed: Resource temporarily unavailable` in the first
   native boot log). The writer now retries `WouldBlock` for a
   bounded 10 s (the lock precedes any write, so waiting cannot
   duplicate a record); inspection and retention keep the
   fail-fast lock. Host regression test holds the lock ~1.5 s
   and requires the append to land and verify. Native
   confirmation: zero failed writes in all four boot logs of
   this record.
2. **Checker reported `anchor: null` for boundary journals**
   (`e4ec83f`). The anchor was only set when a v2 record
   arrived with no prior link, so any journal whose chained
   segment follows v1 records — the normal upgrade shape —
   reported no anchor even though the boundary verified.
   Export receipts inherit the checker's anchor, so such a
   journal's receipt pinned `null`, which verified as
   `null == null` and anchored nothing. The checker now
   reports the first chained record's `prev_digest` as the
   anchor in all cases; regression tests pin the boundary
   anchor at inspection and export level, including refusal
   of a genesis-anchor forgery.

## Environment notes (not product behaviour)

- The graphical harness types through an emulated USB
  keyboard; under TCG its stock 75 ms key hold intermittently
  loses presses (correct confirmations read as mismatches).
  The audit smoke lengthens the hold to 200 ms for its own
  runs and retries the boot pair on a fresh seeded copy if a
  boot desyncs; attempts are recorded in `result.json`. The
  audit assertions themselves never retry.
- A correct login is also intermittently refused on this
  host: the greeter allows the seat broker 4 s to answer, and
  the Argon2id verify (64 MiB, t=3) under TCG straddles that
  window. Authentication mechanics are frozen (ADR 0023) and
  were not touched; the same image passed the shipped joined
  smoke end-to-end in this session.

## Files

- `result.json` — the audit smoke's structured verdict.
- `journal.jsonl` — the extracted guest journal (3 v1 seed
  records + 10 guest v2 records).
- `check.json` — packaged `veil-audit check` output.
- `receipt.json` — packaged `veil-audit export` receipt.
- `verify-host.txt` — host `veil-audit verify --receipt`
  transcript.
- `joined-guest-validation.json` — the shipped joined
  acceptance verdict on the same image.
- `ab-smoke-receipt.json` — the update round trip receipt on
  generations built from this revision (see below).

The serial logs of every boot (audit pair, joined pair, and
the nine A/B scenario logs) are retained in the run output
(`out/audit-v2-proof/`, `out/native-joined/`,
`out/ab-proof/smoke-evidence/`) but are not committed: the
repository's `.gitignore` excludes `*.log`, and prior
evidence folders keep the same README + JSON convention.

## A/B update round trip

**Passed: `SYNVEIL_AB_QEMU_PROOF_PASS`** — all nine scenarios
green in one continuous run of `tests/smoke-native-ab.py`
(S0 provision/enroll, S1 stage v2, S2 trial v2 confirmed,
S3 owner rollback to v1, S4 failing candidate falls back,
S5 invalid signature refused, S6 power cut mid-stage,
S6b stage after the interrupt, S7 corrupt slots fail
closed); `ab-smoke-receipt.json` records
`bootable_update_rollback_demonstrated: true`, no gate
violations, `physical_hardware_tested: false`.

Provenance: both A/B generations were built from the same
revision as the joined image above (guest binaries stamp
`7431121`); the receipt's `source_commit` (`0b7b245`) is the
checkout HEAD at run time — the commits between `7431121`
and it are tests-only harness changes (key-hold pacing,
typing budgets, scanout patience, failure-frame logging in
the two QEMU smokes) plus the audit smoke's committed final
form (`6c01414`). No guest code changed after the image
build.

Getting the round trip green was itself diagnostic. Three
harness defects — none in guest code — hid the result across
several runs, and each is fixed in-tree with its cause
recorded in the commit message: the update GUI's open
animation raced terminal focus and ate typed commands; the
greeter's first presented frame can lag its serial
`LOGIN_READY` marker past the login helper's scanout budget;
and, decisively for S6b, the QMP socket path
(`$TMPDIR/synveil-ab-*/s6b-recover-stage/…`) exceeded the
108-byte AF_UNIX limit in this environment, so every QMP
operation for that one scenario failed silently — the runs
here use a short TMPDIR path. A separate in-guest finding
from this pass — audit lock contention dropping records at
boot, and the checker reporting a null anchor for
v1-boundary journals — is fixed in `1d8a29a` and `e4ec83f`
and covered by regression tests.

With slice 3 landed, the v2 audit format is **accepted**
(docs/DURABLE_AUDIT_V2_DESIGN.md, docs/AUDIT.md). Remaining
Phase 2 audit gaps are named in ROADMAP.md: automatic
retention beyond the single archive slot, an installed
disk-full policy, and power-loss durability validation.
