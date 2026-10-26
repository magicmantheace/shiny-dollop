# A/B bootable update/rollback — QEMU proof record (2026-10-26)

**Result: bootable update/rollback DEMONSTRATED in QEMU.** All nine
scenario records pass on one disk, in sequence, ending with
`SYNVEIL_AB_QEMU_PROOF_PASS` from `tests/smoke-native-ab.py`.
This is QEMU evidence only. **Physical hardware: NOT validated**
(the proof disk is a separate artifact from the shipped test
image; the shipped image, SHA-256
`6b10b482239ca3e771bd20d85a5f4e0dc414a00fc34334408eb134b150bacfc3`,
is untouched by this work).

## Identities

- Proof artifacts (disk + generations) built from source commit
  `99cca31ba53d1590e06bb5c5b2fba956848aec55`
  (`build-receipt.json` in this directory is the builder's own
  receipt). Later commits up to `a784616` changed only the proof
  driver (`tests/smoke-native-ab.py`) and its interaction model —
  no guest code, so the built artifacts stand as built at
  `99cca31`.
- Proof disk: 1,115,684,864 bytes, SHA-256
  `67fd79bfcf2d41f9089455e796d8a450581e3efec8197f6859b7c1129b6eb9d3`.
- Generations (UKI = kernel EFI-stub bzImage with embedded
  initramfs; identity stamped at build time in
  `/etc/synveil/generation.json` and the slot's `gen.json`):
  - v1 `synveil-gen-v1`: 61,146,112 bytes, SHA-256
    `bb2024de1afdf7e750d0d45ac75af8f95522065bba60b3a39c137147b80bd600`
    (Weston background `0xFF101820`)
  - v2 `synveil-gen-v2`: 61,146,112 bytes, SHA-256
    `b030f1a5b2a89efc924b13ca6c6fb16b617b5ed097433405fe012c6990eed0c4`
    (background `0xFF0B3D2E` — the observable change)
  - v3 `synveil-gen-v3`: 60,478,464 bytes, SHA-256
    `bae005989b564509cc3dbd133f393232abd9f9799243741b78f931eb973397a5`
    (background `0xFF3D0B0B`; `veil-seat` replaced by an exit-1
    stub so the *real* health path fails it — no check weakened)
- Publisher trust: key id `synveil-dev-2026-01`, **development
  only**. The private key exists only in the git-ignored
  `out/ab-proof/trust/` directory and is not in Git, any image,
  or this record. Guest verification is in-tree Ed25519
  (veil-core `ed25519.rs`, verify-only; the offline cargo
  registry contains no signature crates to pin, so the
  implementation is in-tree with FIPS 180-4 + RFC 8032 /
  OpenSSL-generated known-answer tests).

## Design as proven (differs from the original Pass A sketch)

- **Boot selection writes NO firmware variables.** The firmware
  loads the ESP fallback (a permanent copy of generation A);
  whichever generation runs, its early-init A/B hook reads the
  control record on STATE and converges to the desired slot
  (pending trial first, else confirmed) by chain-loading that
  slot's UKI with `kexec_file_load` (cmdline NUL-terminated,
  slot bytes re-hashed against the record before transfer).
  BootOrder / Boot#### / BootNext are never read or written;
  normal Windows startup is untouched by construction.
  (`tools/ab_update.py`'s efivarfs BootNext design from the
  first Pass B iteration was deleted, commit `892469b`.)
- **Attempt accounting before services:** the hook decrements
  the persisted trial attempt record before any service starts;
  an exhausted trial is expired by the hook itself and the
  confirmed generation boots in the same power cycle. A trial
  that boots directly (not via chain) decrements itself. A
  `chain_in_flight` flag prevents double accounting across the
  hand-over.
- **Fail closed:** if chain-load of the desired slot fails on a
  non-confirmed generation, or the running generation's own slot
  digest does not match the record, the hook runs the
  recovery-status diagnostics and holds — the wrong system
  never runs.
- **Bidirectional migration safety:** a candidate is staged
  only if it can read the current STATE format **and** the
  confirmed generation can read the candidate's format
  (readable range `[min_reader_state_format, state_format]`);
  owner rollback applies the same check to the retained
  generation, and refuses to discard a booted trial whose
  writes the confirmed generation cannot read. Host core:
  `tools/ab_update.py` (`tests/ab-update.py` 18/18); the guest
  agent mirrors the same rules.
- **In-guest agent** `veil-ab` (in veil-core): verifies release
  signatures against the build-time pinned publisher
  (`/etc/synveil/publisher.json`), writes only the inactive
  slot, re-hashes on read-back, and persists the trial record
  before any transfer. Health checks on a trial boot: STATE
  read/write, credential PHC parses (Argon2id), veil-core
  status socket answers, Wayland session live
  (`/run/user/1000/synveil-0` + weston + veil-seat), slot
  digest equals the trial record, running stamp identity.
  Health deadline 300 s; on failure the agent reboots and the
  attempt accounting handles the rest. Action socket
  `/run/synveil-ab/agent.sock`, schema `synveil.ab-agent/v1`
  (status / stage / rollback / reboot), driven in the proof by
  five fixed QMP-typed commands — never arbitrary text.

## Scenarios (all on the one proof disk, in order)

Machine-readable detail: `smoke-receipt.json`. Raw serial logs:
one file per boot below (S1+S2 share a boot by design).

| Scenario | Result | What it proves |
|---|---|---|
| S0 provision/enroll | PASS | Fresh disk enrolls; account credential, and a known file on DATA (`/home/synveil/ab-known-file`) created as survival baseline |
| S1 stage v2 | PASS | Signed v2 release staged from release media into the inactive slot; trial record persisted |
| S2 trial v2 confirmed | PASS | Reboot chain-loads v2; observable change verified by framebuffer color proof; graphical login works; health checks pass; agent confirms v2; credential + known file unchanged |
| S3 owner rollback to v1 | PASS | Owner rollback arms a trial of retained v1; v1 boots, logs in, color-proves v1, health-confirms; credential + known file survive the rollback |
| S4 failing candidate | PASS | v3 (seat stubbed) staged from v1; three trial boots each end in `SYNVEIL_AB_HEALTH_FAILED check=session` and reboot; attempts 3→2→1→0 accounted across boots; the entry hook then prints `SYNVEIL_AB_TRIAL_EXHAUSTED` and boots confirmed v1 in the same cycle; login succeeds; trial record cleared; survival holds |
| S5 invalid signature | PASS | Corrupted-signature release refused in-guest (`release signature verification failed`); no trial created; confirmed slot untouched (v1, digest identical) |
| S6 interrupted staging | PASS | Power (QMP quit) cut the moment `SYNVEIL_AB_STAGE_COPYING` prints; no `SYNVEIL_AB_STAGED`; control record afterwards: no trial, confirmed untouched |
| S6b stage after interrupt | PASS | The system still boots its confirmed generation, a fresh stage of v2 succeeds, and an owner rollback decision discards the pending (never-booted) trial |
| S7 corrupt slots fail closed | PASS | On a branch copy of the disk, both slot images' `gen.efi` are zeroed while the ESP fallback copy is intact; the hook's digest check refuses (`SYNVEIL_AB_CHAIN_FAILED` on the entry generation, then the fail-closed path prints `SYNVEIL_AB_FAIL_CLOSED` + recovery diagnostics `SYNVEIL_RECOVERY_STATUS_V1`); `SYNVEIL_LOGIN_READY` never appears — no wrong system runs |

## Saved-setting leg — NOT demonstrated (honest limitation)

Adam's sequence asks that a saved setting survive update and
rollback. The proof records the desktop preference file's hash
from STATE at every scenario, but the QEMU boot target's profile
exposes **no user-facing settings surface** through which a
setting can be changed: the greeter's arrows are inert (proven
by pixel-identical captured frames) and the Weston session in
this milestone has no settings UI. S0 therefore gates on the
credential + known file only, and the setting-survival leg is
recorded as **not demonstrated**, not silently dropped. It
becomes demonstrable when a settings surface ships (Priority 2
era) and should be re-run then.

## Both-slots-dead recovery — what S7 does and does not claim

The chain design has no ESP recovery *entry point* in the old
design's sense; the ESP fallback is the generation-A entry
point, and recovery from a both-slots-corrupt disk on removable
media is **media rewrite** (the same story as the shipped test
image: rewriting the media is the recovery; it is not
installed-system recovery). S7 claims only the fail-closed
behavior above: corrupt slots are detected by digest and the
machine holds at recovery diagnostics instead of running a
wrong or partial system.

## Failures encountered on the way (root causes, all fixed)

Recorded here because the fixes are part of the deliverable
(all in `tests/smoke-native-ab.py` / guest code, commits noted
in git log `66c50b6..a784616`):

1. `kexec_file_load` EINVAL — the kernel requires the cmdline
   buffer to include its NUL terminator; the hook passed
   `/proc/cmdline` verbatim (`5f55ab3`).
2. Health session probe searched for a `wayland-*` socket; the
   session's display is named `synveil-0`, so no trial could
   ever confirm (`99cca31`).
3. Marker-prefix collisions in the driver: a bare
   `SYNVEIL_AB_CONFIRMED` wait matched `SYNVEIL_AB_CONFIRMED_BOOT`
   from the entry generation of the same boot (one S2 result was
   a false pass before this was caught and the wait made exact
   + anchored).
4. Cross-boot line-buffer hazard: post-reboot logins matched the
   previous boot's `LOGIN_READY`/`AUTH_ACTIVE` lines; login()
   now takes the caller's boot-cycle mark.
5. `Boot.seen()` is prefix-based; S5's mid-line substring check
   could never pass (the guest refusal itself was correct).

## Not in this pass

- HTTPS browsing + persistent downloads inside Synveil: **NO**
  (Priorities 3–4, not attempted here).
- Graphical update controls: **not built** (Priority 2). What
  exists for it: the agent's typed socket protocol
  (`synveil.ab-agent/v1`, actions status/stage/rollback/reboot)
  already runs as root behind a 0660 root:synveil socket; a
  desktop client needs no protocol change.
- Physical boot of the A/B disk: not attempted; QEMU TCG only.
