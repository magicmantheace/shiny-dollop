# Test-media package WITH the recovery path — QEMU evidence, 2026-10-27

This record covers the recovery-inclusive rebuild of the owner
first-boot test-media package: the same package contract as
[the 9dbeda0 package](../test-media-2026-10-27/README.md), rebuilt
from the head that contains ADR 0010 gates A–C and the tier-4
recovery factor (ADR 0020), with the acceptance suite re-proven on
the new image. It supersedes that package, which predates the
recovery path and must not be written for a boot test any more.
**Nothing in this record is physical-hardware evidence; the TG01
has still never booted Synveil, and this remains a boot-test
package, not an install.**

## The package

- Directory: `out/test-media/` (same layout as before:
  `synveil-x86_64.img`, `synveil-release-v2.img`,
  `write-test-media.sh`, `OWNER_FIRST_BOOT_TEST.md`,
  `PACKAGE.json`, `SHA256SUMS`; `sha256sum -c SHA256SUMS` passes
  on all five entries).
- Build: `python3 tools/native_ab.py --build --browser
  --boot-target hardware --out out/package-recovery`, from
  **source commit `5fd76c0aca406b64ef8a37a35f1ba683172363ec`**
  (receipt: `build-receipt.json` in this record).
- **Image: SHA-256
  `83fc83a562d2224007b279e8aa63c22b8c2e6a9f5b08bd61db3b390649d2bebd`,
  4,169,138,176 bytes.** The image grew against the previous
  package: the ESP is now 1024 MiB (was 768) to hold the fallback,
  three generation UKIs, the recovery-status, maintenance and
  reset UKIs, and the control record. The rest of the layout is
  unchanged (SYSTEM_A/B 768 MiB, STATE 256 MiB at the same
  PARTUUID, DATA 384 MiB, RECOVERY 768 MiB empty by construction).
- Release media: `synveil-release-v2.img` SHA-256
  `ad126ad87ec638478255b5b106c7c604f4350259634cd1e1d352a756bd170682`
  (382,730,240 bytes); the receipt also carries the v3 and
  bad-signature media identities.
- **Publisher key:** still the flagged development key
  `synveil-dev-2026-01` (`development: true`). A fresh keypair was
  generated under this build's own `out/package-recovery/trust/`
  (public key `1bf9009d…`, differing from the previous package's),
  so this package's generations and release media are
  self-consistent with the key they embed, as before.
- **Browser decision honored:** Chromium
  `156.0.8078.47-1~deb13u1`, stock configuration — the receipt's
  `test_ca`/`test_host`/`start_url` are all null (production
  build): no test CA, no hosts null-routing, no managed policy,
  no blocking launcher flags anywhere in the image. Sandbox
  enforcement and TLS verification untouched.

## On the packaged image itself

### Joined-image acceptance — both variants PASS (legs a + c)

`tests/smoke-native-joined-hardware.py` against
`out/package-recovery/build-receipt.json` and the packaged image,
3072 MB guests (verdicts: `guest-validation-vga.json`,
`guest-validation-usb.json`):

- marker `SYNVEIL_NATIVE_JOINED_HARDWARE_QEMU_ENROLL_LOGIN_WESTON_PASS`
  on both variants; every recorded field true on both, including
  `enrollment_graphical`, `mismatched_confirmation_rejected`,
  `wrong_password_denied_after_cold_reboot`,
  `weston_desktop_after_login`,
  `session_end_relocks_login`,
  `hard_power_cut_returns_to_login_and_credential_survives`, and
  **`broken_state_fails_closed_to_locked_login: true` on both
  variants** — the broken-state leg (destroyed STATE → locked
  login, password denied, no desktop) ran as boot 3 of each
  sequence, not skipped.
- `chromium_launched_and_persisted_on_data: true` on both
  (browser log and profile on DATA, Downloads dir present).
- `pointer_move_resize_keyboard` remains false by harness design
  (positive control), unchanged from previous records.
- `physical_hardware_tested: false`.

### Recovery maintenance entry — exercised on this image (leg d)

The packaged ESP carries `EFI/synveil/maintenance.efi` and
`EFI/synveil/reset.efi`. Both were extracted **from the packaged
image's own ESP** and digest-checked against the build receipt
(`maint-entry-result.json`): maintenance
`e95e53a26a15043c52f5908c02747c948bb3684eaec2cf3ee89fe8872199aad2`,
reset `bf2cffb5256ba92bc33dd05f016f95238fcd0d301be78b8fca7b9d8009d55b72`
— both match.

The extracted maintenance UKI was then installed as the ESP
fallback (`EFI/BOOT/BOOTX64.EFI`) on a COPY of the packaged disk —
the exact mechanism of the gate B2 record — and booted under OVMF.
The hardware-profile UKI carries `console=tty0` only
(`build/scripts/kernel.sh`), so the session was observed by QMP
screendump of the firmware framebuffer (`maint-entry-prompt.png`,
read firsthand). The framebuffer shows, in order:

```
Kernel command line: console=tty0 rdinit=/init panic=-1 loglevel=6 synveil.recovery=maint
[synveil-init] starting bootstrap userspace
SYNVEIL_HOME_READY
SYNVEIL_STATE_READY
SYNVEIL_RECOVERY_MAINT_V1
SYNVEIL_RECOVERY_MAINT_DENIED reason=no-credential
SYNVEIL_SERIAL_RECOVERY_LOCKED
```

That is the packaged image's own recovery path reaching
veil-recovery, finding the fresh (unenrolled) STATE, and denying
with `reason=no-credential` — the designed behavior with no
credential enrolled — with the serial console locked. A password
typed after the denial (`maint-entry-after-attempt.png`) landed
as inert console echo: no shell, no new markers, no session.

**Boundary, stated precisely:** the *authenticated* maintenance
session (enrolled credential, denial matrix, A/B restore,
exit-to-login) and the tier-4 reset flow were **not** re-run on
the packaged image. Their acceptance drivers speak the serial
marker protocol, and the hardware profile deliberately carries
no serial console, so they cannot drive this image. Those flows
stand on the QEMU-profile A/B acceptance of the same source
(fixture 31/31 and A/B 13/13 at evidence commit `06e5a7b`; see
[the tier-4 record](../recovery-factor-2026-10-27/README.md) and
[the gates record](../recovery-gates-2026-10-27/README.md)),
whose kernels differ from the packaged ones only in console
target and browser-test wiring.

## Browser/downloads acceptance — re-proven at this head (leg b)

By construction this leg cannot run against the packaged image:
the package is the production build (no test CA), and the
acceptance needs the loopback TLS fixture. It therefore ran, as
in the previous records, against the dedicated QEMU-target proof
disk built from the same source with the fixture CA
(`0467bb67422874519815d9d85d222ddbd7930a404a27f348e8ed436a58194b45`;
receipts `browser-build-receipt.json`, `browser-receipt.json`):

- marker `SYNVEIL_BROWSER_QEMU_PROOF_PASSED`; the receipt's
  re-derived gate reports `validated: true`, `failures: []`,
  `demonstrated: true`, on source `5fd76c0…`.
- B0–B7 all recorded: verified HTTPS browsing; downloads
  digest-verified in-guest and by host readback (payload SHA-256
  `3b7f6569e01e04e5e970cd34dbfe9ac0fb3b107631b4aa51aae1d97430cc4f1d`);
  collision uniquification with no silent overwrite (`.crdownload`
  residue 0); insufficient-storage outcome (oversized download
  size 0); the bad-CA endpoint: **zero GETs reached the
  wrong-CA server (17 GETs on the verified port, 2 refused
  handshakes on the bad port)**; downloads persist across cold
  reboot (B5), update to v2/slot B (B6), and rollback to
  v1/slot A (B7).
- The packaged image's own Chromium launch + DATA persistence is
  covered by the joined acceptance above; what this leg adds is
  the fixture-TLS and download semantics, on the proof disk only.

## Guarded writer (leg e)

`tests/write-test-media.py` at this head: **15/15 OK** (the
refusal suite: unsafe flags, non-USB and internal disks, mounted /
swap / backing-traced refusals failing closed, exact model+serial
confirmation, checksum and identity refusal, post-write
read-back). The shipped `write-test-media.sh` is byte-identical
to the previous package's (SHA-256
`4c58d228eca9e00c57e7311dd5d62b26c3ee073421484003afe58415cea1ac7c`);
the digest pin is supplied by the caller via `--expected-sha256`.

## Host gates run in this pass

- `cargo fmt --all -- --check`: clean.
- `cargo test --workspace`: **175 passed, 0 failed** (run
  firsthand at `5fd76c0`).
- Python suites: `tests/write-test-media.py` 15 OK,
  `tests/smoke-gates.py` 30 OK, `tests/ab-update.py` 18 OK,
  `tests/recovery-maint.py` 5 OK, `tests/recovery-status.py`
  4 OK. (The recovery fixture/A/B suites were run in the gates
  and tier-4 passes at this same head; this pass re-ran the
  suites the packaging touches.)

## Failed attempts in this pass (preserved)

- **Package build, attempt 1** (with `--rebuild-joined`): killed
  mid-generation-build by an environment service restart after
  the joined baseline rebuild and generation v1 had completed;
  the process died without error output and no artifact from it
  was used. The environment restart also removed the non-root
  `svrunner` user; it was recreated (uid 1001) and the traversal
  permissions re-opened before the acceptance runs. Attempt 2
  (same command minus `--rebuild-joined`, reusing attempt 1's
  completed HEAD joined baseline) finished: receipt above.
- **Joined acceptance (VGA), attempts 1–3** never reached the
  guest, all harness-environment causes: attempt 1 ran as root
  (the harness requires a non-root runner); attempt 2's log
  redirect failed on a root-owned log file and its receipt read
  was refused by the build directory's permissions; attempt 3
  booted nothing because the QMP socket path under the deep
  TMPDIR exceeded the Unix-socket length limit
  (`QMP socket must be an absolute short path`). Attempt 4, with
  TMPDIR at `/home/hatch/stmp`, passed as recorded. Attempts for
  the USB variant and the browser acceptance then ran clean
  first time under the same setup.

## What this package does not prove

- No physical hardware evidence of any kind; the TG01 boot test
  is still the first physical run. QEMU's standard VGA GOP and
  emulated USB storage stand in for the TG01's firmware GOP on
  an RTX 3060 (no native driver) and a real USB drive.
- The authenticated maintenance session and tier-4 reset flow on
  the packaged (hardware-profile) image specifically — see the
  boundary under leg (d). On an installed system the owner
  reaches these entries from the boot menu; exercising them
  end-to-end on the hardware profile needs a framebuffer-driven
  acceptance that does not exist yet.
- Mid-download cancel/resume behavior (an insufficient-storage
  download outcome is proven; cancel/resume is not).
- That the TG01's own network hardware is driven by this kernel
  (networking is proven in QEMU only).
- Production signing: the publisher key is the flagged
  development key, regenerated per build directory.
- Install-readiness: this is a boot test of disposable media.
  Installation remains gated on physical validation, the A/B
  installation milestone, and the owner's authorization (see
  `docs/FIRST_INSTALL.md`).

## Documents updated with this package

- `docs/PHYSICAL_BOOT.md`: status now names this package
  (source `5fd76c0…`, image `83fc83a5…`).
- `docs/FIRST_INSTALL.md`: the tier-4 blocker paragraph updated
  — the shipped package no longer predates the recovery path.
- `docs/OWNER_FIRST_BOOT_TEST.md`: identities, the writer
  example digest, and the password-loss section updated for the
  recovery-inclusive image (the guide no longer claims the image
  has no recovery path). The `docs/` copy and the packaged copy
  are identical again; the `docs/` copy had drifted stale
  (it still described the superseded `283b1974…` package and
  the removed browser connection-blocking regime) and was
  re-synced from the packaged guide in this pass.
