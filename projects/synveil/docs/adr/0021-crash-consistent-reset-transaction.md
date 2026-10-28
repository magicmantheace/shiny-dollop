# ADR 0021: The password-reset transaction is crash-consistent (reset journal)

- Status: Accepted
- Date: 2026-10-28
- Supersedes: none
- Superseded by: none
- Related: [ADR 0010](0010-independent-owner-recovery.md) (tier 4),
  [ADR 0020](0020-recovery-factor-design-approval.md) (decision D7),
  [recovery factor specification](../RECOVERY_FACTOR_SPEC.md)
  section 9

## Context

ADR 0020 decision D7 states that a factor used for a successful
password reset is automatically revoked — the factor is single-use.
The first implementation (through commit `ef72f3f`) performed the
reset as two sequential durable writes in `veil-recovery`'s
`run_reset()`: replace the credential record, then revoke the
factor record. On a revocation error it emitted
`SYNVEIL_RECOVERY_RESET_OK_REVOKE_FAILED` and returned success
with the used factor still active, and a power cut between the two
writes left the same state. The reset was therefore not
single-use under exactly the failures D7 exists to cover.

The defect was found by the standalone repository's independent
review of `ef72f3f`, not by this repository's own tests: its
handoff (`magicmantheace/Synveil`,
`docs/validation/muse-sync-recovery-2026-10-28/MUSE_HANDOFF.md`,
commit `3abdbbb`) compiled the unchanged `run_reset` function
against storage doubles that force revocation to fail after a
successful replacement and reproduced
`password_changed=true, factor_active=true, success=true` in CI.
The owner approved the fix on 2026-10-28. This ADR records the
design; it changes no D1–D10 decision — it makes D7 true under
failure, which is what D7 already promised.

## Decision

The reset is a journaled transaction in `veil-core`'s recovery
library (`execute_reset_transaction`), with a durable journal
entry (`synveil.reset-journal/v1`,
`/var/lib/synveil/auth/reset-journal.json`) under the credential
store's own file discipline (root-owned 0700 directory, 0600
single-link file, strict parsing, atomic write with fsync):

1. **Journal before mutation.** After the owner's confirmation
   and the gating audit entry, and before the credential is
   replaced, the flow durably writes a journal entry naming the
   factor generation being consumed, its installation identifier,
   and the start time. The journal holds no secret material.
2. **The journal is the enforcement.** From the moment the
   journal is durable, the named factor is consumed:
   `load_active_record` refuses to hand out a record as
   verifiable while any journal exists, so single-use never
   depends on the revocation write having landed.
3. **Exact abort on a live replacement failure.** The credential
   replacement is atomic and reports its own failure; in that
   case (and only that case, where the caller knows nothing
   changed) the journal is cleared and the factor remains valid.
   If clearing the journal also fails, the outcome is Incomplete,
   not Aborted.
4. **Honest outcomes.** The reset reports success only when the
   credential replacement AND the factor revocation are both
   durable. A revocation failure triggers one completion attempt
   through the settling path; if that fails, the outcome is
   `SYNVEIL_RECOVERY_RESET_INCOMPLETE` with a failure exit code
   and the journal remains. The previous
   `RESET_OK_REVOKE_FAILED` success marker is removed.
5. **Settling at every entry.** Every entry into the recovery
   environment — `veil-recovery` in both maintenance and reset
   modes, and `veil-recovery-enroll` — settles a pending journal
   before any other factor operation: the revocation of the
   journal's generation is made durable and the journal cleared.
   Settling recognizes a revocation that already landed (tombstone
   at journal generation + 1) and a record that no longer exists.
   A journal that is corrupt, or that disagrees with the record,
   is never cleared and never ignored: settling fails, factor use
   is denied, maintenance reports the factor state as
   `reset-incomplete`, and rotation/enrollment refuse until the
   state is resolved under normal authentication.
6. **Interruption semantics.** A crash after the journal write
   consumes the factor in every case. If the credential
   replacement had not landed, the old password remains in
   effect; if it had, the new password is in effect. Settling at
   the next entry makes the revocation durable either way.

## Alternatives considered

- **Revoke before replacing.** Revoking first inverts the failure
  window instead of closing it: a crash after revocation but
  before replacement leaves the owner locked out with the
  password unchanged and the factor dead — and a live replacement
  failure after a durable revocation cannot be aborted exactly.
  The journal gives strictly better semantics in both directions.
- **Report the partial state more honestly only** (rename the
  marker, return failure, keep the sequence). This fixes the
  label, not the state: the used factor would still verify on the
  next boot. The handoff explicitly rejected this, correctly.
- **Two-phase record format** (fold the journal into the recovery
  record as a "consumed" flag written before replacement). This
  is the same journal with worse separation: it rewrites the
  verifier record before the Argon2 replacement is known to have
  succeeded, couples the throttling counter's file to the
  transaction, and complicates the strict record schema that
  specification section 11 test 5 pins. A separate small journal
  file reuses the existing atomic-write discipline unchanged.

## Consequences

- D7 single-use now holds under revocation write failure and
  under power loss at either write boundary, not only on the
  normal path.
- One new small file exists in the credential directory during a
  reset, and (after an interrupted reset) until the next
  recovery-environment entry settles it. Nothing outside the
  recovery flows reads it, and committing a new factor over an
  unsettled journal is refused in the library.
- Availability cost, stated plainly: an interruption in the short
  window between the journal write and the credential replacement
  consumes the factor while the old password remains in effect.
  An owner who has forgotten that password is in the
  specification section 7 unrecoverable case. This is the
  deliberate fail-closed direction: the alternative leaves a
  possibly-observed factor standing as a reset authority.
- The tier-4 acceptance record of 2026-10-27 stands for the
  normal path at its commit; the fault and interruption coverage
  is recorded separately (see Validation).

## Validation

Fault-injection and interruption coverage lives in the recovery
library's unit tests (the handoff scenario: replacement succeeds,
revocation storage fails — outcome Incomplete, factor unverifiable
while the journal stands, settling completes it) and in guest
cases t8b/t8c of `tests/smoke-recovery-factor.py` (a durable
journal planted in the exact guest shape, with and without the
credential replacement landed, completed at the next recovery
entry). Guest evidence at the fix commit is recorded in
`docs/validation/recovery-reset-transaction-2026-10-28/`. QEMU
evidence only; physical hardware remains untested, and ADR 0010
gate E is unaffected.
