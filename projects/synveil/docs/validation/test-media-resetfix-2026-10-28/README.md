# Test-media package WITH the ADR 0021 reset fix — QEMU evidence, 2026-10-28

This record covers the rebuild of the owner first-boot test-media
package from the head that contains the crash-consistent tier-4
reset transaction (ADR 0021). The previous package (source
`5fd76c0`, image `83fc83a5…`;
[its record](../test-media-recovery-2026-10-27/README.md)) shipped
the reset code in which a failed revocation — or a power cut
between credential replacement and revocation — left the used
recovery factor active while reporting success. That package is
superseded by this one and must not be written for a boot test
any more. **Nothing in this record is physical-hardware evidence;
the TG01 has still never booted Synveil, and this remains a
boot-test package, not an install.**

## The package

- Directory: `out/test-media/` (same layout as before:
  `synveil-x86_64.img`, `synveil-release-v2.img`,
  `write-test-media.sh`, `OWNER_FIRST_BOOT_TEST.md`,
  `PACKAGE.json`, `SHA256SUMS`; `sha256sum -c SHA256SUMS` passes
  on all five entries).
- Build: `python3 tools/native_ab.py --build --browser
  --boot-target hardware --rebuild-joined --out
  out/package-resetfix`, from **source commit
  `db32105b05d24ecaf6d08cf11e796f2892a1b67a`** (receipt:
  `build-receipt.json` in this record).
- **Image: SHA-256
  `27603d90bc09d685819ca3a369745cb21751c094e712ae3cfdb69f8665da5696`,
  4,169,138,176 bytes.** Layout unchanged from the previous
  package (ESP 1024 MiB; SYSTEM_A/B 768 MiB; STATE 256 MiB at the
  same PARTUUID `7c9e2d41-8b3a-4f5e-a6d1-2e8c4b7f9053`; DATA
  384 MiB; RECOVERY 768 MiB).
- Release media: `synveil-release-v2.img` SHA-256
  `d58961fb43d9fa6bf04fb94db169beb4e2e6967b43204fcf578a8bd5d31593c7`
  (382,730,240 bytes); the receipt also carries the v3
  (`39a25f1d…`) and bad-signature (`856780e3…`) media identities.
- **Publisher key:** still the flagged development key
  `synveil-dev-2026-01` (`development: true`). A fresh keypair was
  generated under this build's own `out/package-resetfix/trust/`
  (public key
  `f1901ab891f4446af39004407ab9eee9732315c02608d38788597083a511f88d`,
  differing from the previous package's), so this package's
  generations and release media are self-consistent with the key
  they embed, as before.
- **Browser decision honored:** Chromium
  `156.0.8078.47-1~deb13u1`, stock configuration — the receipt's
  `test_ca`/`test_host`/`start_url` are all null (production
  build): no test CA, no hosts null-routing, no managed policy,
  no blocking launcher flags anywhere in the image. Sandbox
  enforcement and TLS verification untouched.

### The fix is in the binaries that were packaged

`tools/native_ab.py`'s joined-baseline reuse checks only that
`usr/sbin/veil-ab` exists; it does not detect source changes, so
`--rebuild-joined` was mandatory for this rebuild and was used.
The rebuilt baseline's `usr/sbin/veil-recovery` was inspected
directly before packaging: it carries the ADR 0021 vocabulary —
`SYNVEIL_RECOVERY_RESET_INCOMPLETE`, the journal markers
(`stage=journal`, `journal-unresolved`, `anchor-mismatch`) — and
the defective success marker `SYNVEIL_RECOVERY_RESET_OK_REVOKE_FAILED`
is **absent** (it no longer exists in the source). The packaged
generations were built from that baseline.

## On the packaged image itself

### Joined-image acceptance — both variants PASS (legs a + c)

`tests/smoke-native-joined-hardware.py` against
`out/package-resetfix/build-receipt.json` and the packaged image,
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
  login, password denied, no desktop) ran as a boot of each
  sequence, not skipped.
- `chromium_launched_and_persisted_on_data: true` on both
  (browser log and profile on DATA, Downloads dir present).
- The only false fields on either variant are the by-design
  ones: `pointer_move_resize_keyboard` (positive control),
  `separate_state_disk_used` (STATE is on the image's own
  partition), and `physical_hardware_tested: false`.

### Recovery maintenance entry — exercised on this image (leg d)

The packaged ESP carries `EFI/synveil/maintenance.efi` and
`EFI/synveil/reset.efi`. Both were extracted **from the packaged
image's own ESP** and digest-checked against the build receipt
(`maint-entry-result.json`): maintenance
`6e32499aff38691f7a8921d35a2a0b8ae438dc86e40e35abfafa678457e91ca3`,
reset `9b19927aa9b0832e64e623230a70df906fd17dab9f2fdfc348a957cc19c45375`
— both match.

The extracted maintenance UKI was then installed as the ESP
fallback (`EFI/BOOT/BOOTX64.EFI`) on a COPY of the packaged disk —
the exact mechanism of the gate B2 record — and booted under
OVMF. The hardware-profile UKI carries `console=tty0` only, so
the session was observed by QMP screendump of the firmware
framebuffer (`maint-entry-prompt.png`, read firsthand). The
framebuffer shows, in order:

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
exit-to-login) and the tier-4 reset flow — **including every
ADR 0021 transaction leg** (journal write before mutation,
settling of an interrupted reset, honest failure on revocation
failure) — were **not** exercised on the packaged image. Their
acceptance drivers speak the serial marker protocol, and the
hardware profile deliberately carries no serial console, so they
cannot drive this image. Those flows stand on the QEMU-profile
guest evidence at `5e9e240` (fixture **35/35**, including the
interruption cases t8b/t8c added for ADR 0021, and A/B **13/13**;
see [the reset-transaction record](../recovery-reset-transaction-2026-10-28/README.md)),
whose kernels differ from the packaged ones only in console
target and browser-test wiring. What this pass adds on the
packaged image itself is: the fixed binary is verifiably the one
packaged (above), the ESP entries carrying it digest-match the
receipt, and the maintenance entry boots to its locked denial
state.

## Browser/downloads acceptance — re-proven at this head (leg b)

By construction this leg cannot run against the packaged image:
the package is the production build (no test CA), and the
acceptance needs the loopback TLS fixture. It therefore ran, as
in the previous records, against the dedicated QEMU-target proof
disk built from the same source with a fresh fixture CA
(`0bcbf279e7877a8fcd7c2aa31346f2a25a71a78a2545ce48a8bd85e1249fed1a`,
CA SHA-256
`195b4fd4508e1d88fc89efa28852c119de1832c33145a0b35c4e06afdedb46fd`;
receipts `browser-build-receipt.json`, `browser-receipt.json`):

- marker `SYNVEIL_BROWSER_QEMU_PROOF_PASSED`; the receipt's
  re-derived gate reports `validated: true`, `failures: []`,
  `demonstrated: true`, on source `db32105…`.
- B0–B7 all recorded: verified HTTPS browsing; downloads
  digest-verified in-guest and by host readback (payload SHA-256
  `3b7f6569e01e04e5e970cd34dbfe9ac0fb3b107631b4aa51aae1d97430cc4f1d`,
  matching at
...[truncated 6643 chars]