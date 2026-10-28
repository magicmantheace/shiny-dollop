# ADR 0010 tier 4 (recovery factor) — QEMU evidence record (2026-10-27)

**Result: ADR 0010 tier 4 is IMPLEMENTED and DEMONSTRATED in QEMU**
at commit `06e5a7b` — all thirteen acceptance tests of the recovery
factor specification's section 11 have guest evidence below, with
one stated boundary on test 2. **Physical hardware: NOT tested.**
Per ADR 0010 gate E, physical installation remains blocked: the
remaining blockers are physical validation on the target machine
and the A/B installation milestone — tier 4 is no longer one of
them. The shipped test-media package (built from `9dbeda0`) predates
this work and does not contain the recovery path.

Approval trail: the owner approved Option A with the recommended
defaults on 2026-10-27, recorded in
[ADR 0020](../../adr/0020-recovery-factor-design-approval.md)
(commit `0fce0df`, before any implementation). Specification:
[RECOVERY_FACTOR_SPEC.md](../../RECOVERY_FACTOR_SPEC.md).

## Identities

- Branch: `synveil/first-boot-desktop-muse`. **PR #17 is not
  merged.** No firmware variables were written at any point.
- Implementation commits: `f58627c` (credential helpers),
  `51fa976` (recovery record/anchor library), `25878d6` (reset flow
  + rotation in `veil-recovery`), `f8b17a6` (`veil-recovery-enroll`
  + build wiring), `9103a6b` (reset UKI wiring + host contract
  tests), `c45a799` (rotation print offer), `cfc88bb` (guest
  drivers). Evidence runs at `06e5a7b` (fixture substrate) — the
  only change from `cfc88bb` is a guest-driver expectation fix.
- Fixture verdict: `fixture-verdict.json` — 31 of 31 driver cases
  pass, `source_commit` `06e5a7bcc4b8698a4e0b22f5b59ac306854078b9`.
- A/B proof disk: built at `06e5a7b` by `tools/native_ab.py
  --build --rebuild-joined`; receipt SHA-256 of the disk
  `0a995cca6718bb7b67793c268acd23c6dc80afcc93ac45f2ffcd5f5119bb5965`;
  reset UKI SHA-256
  `1308ad70eafd000e6794a36424d60e9f03b72bf5425f7151e18f273e7148d0d1`
  (ESP entry `EFI/synveil/reset.efi`). A/B verdict:
  `ab-verdict.json` — 13 of 13 cases pass.
- Serial transcripts in this record have the one-time factor
  displays replaced by `[REDACTED-FACTOR]`; the factors were
  synthetic, generated inside the guest, held in driver memory
  only, and never written to any verdict. Raw transcripts remain in
  the working tree under `out/recovery-factor-smoke/` and
  `out/recovery-factor-ab/`. No real owner factor has ever been
  generated.

## Design as implemented (decisions D1–D10, ADR 0020)

Printed 256-bit key (grouped Crockford Base32 + non-secret check
group), Argon2id verifier record `synveil.recovery-record/v1` at
`/var/lib/synveil/auth/recovery.json` (root-owned 0700 directory,
0600 single-link record, atomic replacement), installation binding
via the domain-separated verifier input `synveil-recovery-v1` ‖
installation id ‖ account ‖ key. Enrollment is a separate explicit
step (`veil-recovery-enroll`, interactive terminals only, single
display, check + middle group confirmation, decline commits
nothing); the reset flow lives in `veil-recovery` under
`synveil.recovery=reset`; rotation is the maintenance session's
`rotate` command under normal authentication; a factor used in a
successful reset is automatically revoked.

**D8 anchor mechanism, as chosen and its limits:** the anchor is a
small strict JSON record (`synveil.installation-anchor/v1`) holding
only the installation id, stored at
`/var/lib/synveil/installation-anchor.json` — beside
`ab-control.json`, in the STATE partition root, outside the
credential directory — under the same file discipline as credential
records (regular file, 0600, single link, exact-size bound, strict
field allowlist, written once with create-new semantics; today the
STATE partition root is the only installation-control area that
exists). It provides **no cryptographic integrity of its own**: it
defeats transplantation of records and presentation of a bare
copied credential directory, because the record and the anchor must
agree and the verifier input is bound to the anchored id; it does
not defeat an attacker who can rewrite both stores with
self-consistent values. That limit is the specification section 8
limit, stated in ADR 0020; the exact storage/integrity mechanism
remains subject to ADR 0010's separate review, and nothing in this
record claims tier 4 "validated" beyond the guest evidence below.

## Per-test verdicts (specification section 11)

1. **Wrong factor denied, counted, throttled — PASS.**
   `throttle-3.log`: after five recorded failures across two boots
   the reset entry refuses with `reason=throttled` before offering
   any prompt. A transcription error (bad check group) is rejected
   as `SYNVEIL_RECOVERY_RESET_TRANSCRIPTION` without consuming an
   attempt — the subsequent first wrong guess is `attempt=1`.
2. **Correct factor resets; only the new password opens a session
   after cold reboot — PASS at the credential-authority level.**
   `reset-ok.log` (verify → explicit confirm → password replaced →
   `RESET_OK`), `reset-ok-maint.log` (cold-reboot authentication
   with the new password through the maintenance path's shared
   ADR 0009 verifier), old password denied three times
   (`t2-old-password-denied`). **Boundary:** a graphical desktop
   session login with the reset credential on the joined image was
   NOT exercised; the claim is the reset + the shared-verifier
   authentication, not a desktop login.
3. **Cross-installation denial both directions — PASS.**
   Factors: `cross-factor-1.log` (installation 2's factor denied
   twice on installation 1; installation 1's own factor then
   verifies, proving binding rather than breakage) and the mirrored
   case in the fixture verdict (`t3-cross-factor-b`). Records:
   `cross-record-1.log` — a transplanted record is refused
   pre-input with `reason=anchor-mismatch`, both directions
   (`t3-cross-record-a/b`).
4. **Copied STATE credential directory alone insufficient — PASS.**
   `copied-state.log`: with the anchor deleted, the genuine factor
   is never even prompted for; refusal is `reason=no-anchor`, and
   host checks confirm nothing was initialized or repaired (record
   and credential hashes unchanged).
5. **Corrupt record variants denied without crash/hang/fallback —
   PASS, five variants.** Tag bit-flip (record still parses, the
   genuine factor fails verification three times and the console
   locks); inflated Argon2 cost, truncated PHC, wrong permissions
   (0644), and a symlink in place of the record each refuse
   pre-input with `reason=corrupt-record` (fixture cases
   `t5-*`; `corrupt-symlink.log` is the representative transcript).
6. **Corrupt/missing/foreign anchor denied, no store initialized —
   PASS.** Garbage anchor → `reason=anchor-invalid`; the other
   installation's anchor → `reason=anchor-mismatch`; record and
   credential hashes identical before and after each attempt
   (fixture cases `t6-*`; removal is test 4).
7. **Rotation — PASS.** `rotation.log` (rotation under normal
   authentication, generation 2 active across a cold reboot),
   `rotation-reset.log` (old factor denied `attempt=1`, new factor
   verifies and resets). An aborted rotation confirms nothing and
   leaves the old factor in force (`t7-rotation-abort-keeps-old`:
   the old factor still verifies afterwards).
8. **Used factor revoked (D7) — PASS.** `reset-ok-reused.log`:
   after the successful reset the same factor is refused pre-input
   with `reason=factor-revoked`; the maintenance status reports the
   factor `state=revoked` (the tombstone carries the next record
   revision number, as rotations do).
9. **Audit entries, no secret material — PASS.**
   `reset-ok-audit.log` contains `factor-enrollment-confirmed`,
   `factor-verification-verified`, `reset-confirmed`,
   `password-replaced`, `factor-revoked`, `reset-completed`, and
   `reset-denied` entries; the drivers assert the factor and both
   passwords are absent from the log. The A/B run's log
   (`ab-recovery-maintenance.log`) likewise records enrollment,
   reset, and `factor-rotation-completed` with no secrets.
10. **No serial bypass at any stage — PASS.** Every case ends in
    `SYNVEIL_SERIAL_RECOVERY_LOCKED` followed by the split-marker
    probe (no shell, no `uid=0`, no bypass marker) — the fixture
    driver's per-case results include the probe outcome, and the
    reset-armed stages are covered by the reset cases themselves.
    There is no path from serial input, kernel arguments, or a
    developer override to a reset: the reset entry exists only in
    images whose build-time kernel flag set it, and even there it
    demands the bound factor before any input.
11. **DATA partition identical across flows — PASS (A/B
    substrate).** `ab-verdict.json`: raw DATA partition SHA-256
    `77c3999816e9ebc1d3ff9845dcfc787dd736eedf4f088cb52a5efadb251d2c4a`
    identical after a denied attempt (`ab-reset-denied.log`), a
    successful reset (`ab-reset-ok.log`), and a rotation
    (`ab-rotate.log`); the owner probe file's content SHA-256
    `eb3e42f2f96df3ebe322208fe79e4ddcfd0f818caf3460fc1e2a94684486b61d`
    likewise. The partition superblock mount count stayed 0 — the
    recovery flows never mount DATA. (First-run note: hashing the
    extraction after `e2fsck` replay made the copies differ by
    e2fsck's own superblock timestamps; the measurement was fixed
    to hash the raw extraction, and the re-run is the evidence
    above. The first run's verdict is preserved in the working
    tree's `out/` history, not in this record.)
12. **No interface re-displays the factor — PASS.** The fixture
    driver accounts for every captured factor across every boot
    transcript of the run: each appears exactly once, inside its
    single display window; passwords likewise never appear
    (`t12-factor-hygiene`, `t12-password-hygiene`).
    `enroll-install1.log` shows the post-commit inspection: the
    recovery record and audit log contents contain no factor.
13. **Networking absent — PASS.** All fixture and A/B boots ran
    with QEMU networking disabled (`-net none` in
    `build/scripts/qemu.sh` unless its explicit opt-in is set; the
    A/B boot class passes `-net none` directly), and no recovery
    component contains a network path (host contract test
    `tests/recovery-factor.py`).

Section 6 custody details are covered by `decline.log`
(decline commits nothing; an unconfirmed factor is discarded and
never committed; the disk afterwards contains only
`credential.phc`), the print offer (no local printer device exists
in the fixture guests, so `SYNVEIL_RECOVERY_FACTOR_PRINT_UNAVAILABLE`
is what the evidence shows; the direct-device write path is
implemented per D3 and host-contract covered), and the enrollment
case in `enroll-install1.log`.

## Attempts and failures preserved

- Fixture driver run 1 at `cfc88bb`: 28 of 31 cases passed. The
  three failures were driver-expectation bugs, each verified
  against the run's own artifacts (debugfs reports missing files
  with exit 0 and empty output, defeating the absence checks; the
  revocation tombstone carries the next revision number, defeating
  a generation pin). Fixed in `06e5a7b`; the 31-of-31 verdict above
  is run 2 at that commit.
- A/B driver run 1: 9 of 13 cases passed. Failures: the same
  revision-number pin (rotation on that disk commits generation 3:
  enrollment 1, revocation 2, rotation 3) and the e2fsck-timestamp
  measurement artifact described under test 11. Fixed in `615b2a6`
  (driver only; the proof disk and guest code are unchanged from
  `06e5a7b`); the 13-of-13 verdict above is run 2.
- Environment note: during this pass the VM lost its packaged
  QEMU/build tools twice (service restarts); they were restored
  from the workspace `.deb-cache`. One early fixture build also ran
  with the wrong PATH (the kernel's Rust config flips when the
  pinned toolchain is absent), producing a throwaway fixture that
  was discarded before any boot; all evidence above was produced
  with the verified toolchain environment, and fixture identities
  are stamped per commit in each fixture's `fixture.json`.

## Host suites at the evidence commit

- `cargo fmt --all -- --check`: clean.
- `cargo test --workspace`: **175 passed, 0 failed** (baseline at
  `f48ee07` was 166; the nine new tests are the credential-helper
  and recovery-library unit tests).
- Python host suites, all OK: `tests/recovery-factor.py` (15),
  `tests/recovery-maint.py` (5), `tests/recovery-status.py` (4),
  `tests/native-guest-fixture.py` (8), `tests/ab-update.py` (18),
  `tests/native-build.py` (16), `tests/native-rootfs.py` (10).

## Boundaries

- QEMU evidence only; physical hardware not tested. Physical
  installation remains blocked per ADR 0010 gate E on physical
  validation and the A/B installation milestone.
- Test 2's graphical desktop session login after a reset was not
  exercised (see test 2).
- Gate A (tier 1) remains demonstrated on its dedicated fixture
  only; nothing in this pass changes that status.
- The recovery path in this record is not in the shipped test-media
  package (`9dbeda0`); a package rebuild from a recovery-inclusive
  head is a separate step, as is any install.
