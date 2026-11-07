# Tier-4 reset transaction fix — crash-consistent factor revocation (2026-10-28)

**Verdict: the tier-4 reset transaction is crash-consistent at the evidence
commit below.** The defect that allowed a used recovery factor to survive a
reset is fixed by a durable reset journal (ADR 0021); a journaled factor can
never verify again, an interrupted reset is completed at the next recovery
entry, and `run_reset` reports success only when the credential replacement
AND the revocation are both durable. Fixture guest verdict **35/35**, A/B
guest verdict **13/13**, host workspace tests **182/182**. All evidence is
QEMU (serial console profile); `physical_hardware_tested: false`
everywhere.

## The defect (credited)

Found by the standalone repository's review of `ef72f3f`
(`magicmantheace/Synveil`,
`docs/validation/muse-sync-recovery-2026-10-28/MUSE_HANDOFF.md` at commit
`3abdbbb`, with their fault test `tests/muse-reset-revocation-fault.py`),
and confirmed firsthand in this branch before the fix: in
`veil-recovery.rs`, `run_reset()` replaced the root credential FIRST and
revoked the used factor SECOND. If revocation failed, it audited
`factor-revoke-failed`, emitted `SYNVEIL_RECOVERY_RESET_OK_REVOKE_FAILED`,
and returned **success** — password changed, used factor still active. A
power cut between the two writes left the same state. ADR 0020 decision D7
(a used factor auto-revokes; reset is single-use) was therefore not
actually guaranteed; the §11 guest tests in
`docs/validation/recovery-factor-2026-10-27/` exercised only the normal
path, where the revocation write happened to land.

## The fix (ADR 0021)

- A durable **reset journal** (`synveil.reset-journal/v1`,
  `/var/lib/synveil/auth/reset-journal.json`) naming the consumed factor
  generation is written and fsynced **before** the credential replacement.
- A factor whose generation is journaled can never verify again:
  `load_active_record` returns None while any journal exists (pending or
  corrupt). Enforcement does not depend on the revocation write.
- **Settling** runs at the top of `veil-recovery` (maintenance AND reset
  modes) and `veil-recovery-enroll`, before any factor operation: it makes
  the revocation durable (tombstone at journal generation + 1, or
  recognition that it already landed / the record is absent), clears the
  journal, and audits `reset-journal-completed`. A corrupt journal or a
  record/journal disagreement fails closed: never cleared, factor use
  denied, maintenance `status` reports `state=reset-incomplete`, rotation
  refuses with `reason=reset-incomplete`.
- Outcomes: replacement failure after the journal → journal cleared,
  factor still valid (Aborted). Revocation failure after the replacement →
  one completion attempt via settling; still failing → **Incomplete**:
  failure exit code, marker `SYNVEIL_RECOVERY_RESET_INCOMPLETE`,
  `RESET_OK_REVOKE_FAILED` deleted. Success is emitted only after the
  journal clears. New factor commits refuse while a journal exists.

### Interruption semantics (specified, and tested)

| Point of interruption | Result |
|---|---|
| Before the journal write | No state change; factor valid. |
| After journal, before replacement | Factor CONSUMED; old password still in effect; next entry settles (guest case t8c). |
| After replacement, before revocation | Factor dead on next entry; new password in effect (guest case t8b). |
| Revocation write itself fails in a live reset | Incomplete outcome (failure exit, `SYNVEIL_RECOVERY_RESET_INCOMPLETE`); factor dead via the journal; next entry settles. |

## Tests

Host (this pass, exact counts):

- `cargo fmt --all -- --check`: clean.
- `cargo test --workspace`: **182 passed, 0 failed** (175 baseline at
  `ef72f3f` + 7 new). The recovery module carries the fault and
  interruption tests: revocation failure after replacement is Incomplete,
  never success, and the journal keeps the factor dead; an interrupted
  reset completes at the next settling; a landed revocation with a lost
  journal cleanup settles by recognition; a journal/record generation
  disagreement fails closed; the journal-before-mutation order is asserted
  by the abort case (replacement failure leaves the factor fully valid).
- Python host contracts: `tests/recovery-factor.py` 17 OK (15 + 2 new
  journal contracts: the journal resets every scenario disk and t8b/t8c are
  registered), `tests/recovery-maint.py` 5 OK,
  `tests/recovery-status.py` 4 OK, `tests/native-recovery.py` 31 OK,
  `tests/smoke-gates.py` 30 OK.

Guest (QEMU, this pass, at evidence commit `5e9e240`):

- Fixture driver (`tests/smoke-recovery-factor.py`): **35/35 PASS**
  (`fixture-verdict.json`). All 31 cases of the tier-4 record re-pass with
  the journal flow — including §11 test 8 (used-factor reuse denied) and
  test 9 — plus 4 new cases:
  - `t8b-interrupted-reset-completed`: a journal + landed credential
    replacement planted on disk settles at the next reset entry
    (`reason=factor-revoked` before any prompt; journal file gone on the
    disk afterwards — verified by direct disk read in this pass, with the
    audit entry `event=reset-journal-completed factor_generation=1` and
    the record left as the generation-2 tombstone).
  - `t8b-new-password-in-effect`: maintenance authenticates with the NEW
    password and reports the factor revoked.
  - `t8c-journal-only-completed`: a journal alone settles identically.
  - `t8c-old-password-still-in-effect`: maintenance authenticates with
    the OLD password.
- A/B driver (`tests/smoke-recovery-factor-ab.py`) on a proof disk rebuilt
  at the evidence commit: **13/13 PASS** (`ab-verdict.json`) — §11 test 11
  DATA-partition integrity across a denied reset, a successful reset
  (whose serial shows the full new flow ending in
  `SYNVEIL_RECOVERY_RESET_OK`, `ab-reset-ok-serial.log`), and a rotation;
  the guest record ends at generation 3 (enroll → reset-revoke → rotate),
  which also proves enrollment/rotation still commit factors correctly
  around the journal.
- Preserved setup attempts (not test failures): the first fixture attempts
  as the non-root harness user failed on stale root-owned outputs, kernel
  seed permissions, a stale shared-kernel cache, and `merge_config.sh`
  creating its temp file inside the root-owned project directory; the
  driver has no root refusal, and the successful run executed as root,
  matching how the tier-4 evidence was produced. Separately, the first
  native-bundle rebuild for this pass failed its rootfs identity check
  because `build/work/rootfs` predated HEAD; it was deleted, rebuilt from
  source at the evidence commit, and reinstalled with a verified content
  hash.

## Identities

- Implementation: `aca9fdb7a98ba49bd14fa39b0d8233c158284e86`
  (fix: `recovery.rs`, `veil-recovery.rs`, `veil-recovery-enroll.rs`),
  `5e9e240141717ef5ab253baff0851a8fb2f49ac0` (guest cases +
  host contracts).
- Evidence commit: `5e9e240141717ef5ab253baff0851a8fb2f49ac0`.
- Native bundle at that commit: `veil-recovery` SHA-256
  `107c84aa38ffea6fff4ba24bff0b66321811874c783d73c8d1cf42eb116a312c`.
- Fixture reset image SHA-256
  `9fb968a30bde5a4b781a1246d141d581766e7b7e9414eb50b60260da3161e785`.
- A/B proof disk SHA-256
  `327445dd8263166533f0dca72532b9e9d494249c628717117c595910322017b2`;
  reset UKI SHA-256
  `8f1875456cc63a96b0751ee974c63d5ce4655a910c427479158c62917005f620`;
  DATA partition SHA-256
  `c2ca2615af4bd5ce185cbc2c7ba99b65bfccb1a78a62697affcc7cf4854c5a9b`
  (identical before/after), DATA probe SHA-256
  `eb3e42f2f96df3ebe322208fe79e4ddcfd0f818caf3460fc1e2a94684486b61d`.

## Boundaries, stated plainly

- **Source-only fix.** The shipped test-media package
  (`docs/validation/test-media-recovery-2026-10-27/`, built from `5fd76c0`,
  branch tip `ef72f3f`) still contains the defective reset code. The fix
  reaches installed systems only through a future A/B update or a package
  rebuild; first install remains blocked on TG01 physical validation, the
  A/B installation milestone, and owner authorization in any case.
  **Addendum (2026-10-28): the package rebuild has landed.** The current
  test-media package is built from `db32105` (image SHA-256
  `27603d90bc09d685819ca3a369745cb21751c094e712ae3cfdb69f8665da5696`) and
  ships this fix — the packaged binary verified to carry the ADR 0021
  transaction before packaging, ESP entries digest-verified from the
  packaged image, acceptances re-proven at that head
  (`docs/validation/test-media-resetfix-2026-10-28/`). The fix is
  therefore no longer source-only for test media; it reaches *installed*
  systems only through a future A/B update, and the first-install
  blockers above are unchanged.
- The development publisher key caveat is unchanged.
- The tier-4 record's stated boundary is unchanged: a post-reset login was
  proven at session level; a graphical desktop login with a reset
  credential was not exercised.
- QEMU evidence only; no physical hardware was tested.
