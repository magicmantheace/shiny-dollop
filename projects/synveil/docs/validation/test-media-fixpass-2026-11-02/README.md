# Test-media package WITH the ADR 0022 fixes — QEMU evidence, 2026-11-02

The owner-filmed desktop-session killer (Weston subsurface-order
assert), the GTK image-format failure in Chromium, and the
weston-session logging gap are fixed by ADR 0022. This package is
the rebuild that carries them. It supersedes the `db32105`
package (image `27603d90…`), which must not be written any more.

## The package

- Source commit: `a2362132b722b6fdb15cb77d5829ae75ac9334ff`
  (the three fix commits: `66256e0` session logging, `b1ec4b2`
  pixbuf/mime generation, `a236213` Weston patch).
- Image: `synveil-x86_64.img`, 4,169,138,176 bytes, SHA-256
  `f45a79c3bdf0690b3670ef0971f0457e5511d4a1e659724b05d45c8bea767f38`
  (independently re-hashed after the build; matches
  `build-receipt.json` in this directory).
- Update media: `synveil-release-v2.img`, 383,778,816 bytes,
  SHA-256
  `a40a0d26a80c754415c6dc7e9c50b7c525f9d3be2c3c0aa2a53b376b2f3e2e55`.
- Publisher key unchanged: `synveil-dev-2026-01` (development).
- Disk layout unchanged (ESP 1024 MB, slots 768 MB, STATE
  `7c9e2d41-8b3a-4f5e-a6d1-2e8c4b7f9053`, DATA).

### The fixes are in what was packaged

- Weston: the stage receipt records patch
  `weston-15.0.1-subsurface-order-assert.patch` (SHA-256
  `bb4bf87e…`) and patched `libweston/surface-state.c` SHA-256
  `99e3b8a5…`, identical to a pristine-extraction dry run. The
  packaged gen-v1 `libweston-15.so` hashes to `8207fe15…`,
  different from the superseded package's `6243a579…`.
- Pixbuf/mime: the packaged gen-v1 rootfs contains
  `usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders.cache`
  and `usr/share/mime/mime.cache`; the stage's
  `pixbuf_mime_gate` passed in the real stage build
  (loaders.cache SHA-256 `e0cf3e93…`, 11 module loaders, 12
  mime-database files). Before packaging, a chroot of the
  packaged rootfs files decoded PNG (OK) and GIF (OK, module
  loader via the generated cache) and registered all 13
  formats.
- Session logging: the packaged gen-v1
  `usr/libexec/synveil/weston-session` is byte-identical to the
  fixed source (`fail()` routing on every fatal branch).

## On the packaged image itself

### Joined-image acceptance — virtio variant PASS

`tests/smoke-native-joined-hardware.py --ab-receipt
out/package-fixpass/build-receipt.json --memory 4096M` on this
VM (QEMU 8.2.2, OVMF 2024.02, TCG) ended with
`SYNVEIL_NATIVE_JOINED_HARDWARE_QEMU_ENROLL_LOGIN_WESTON_PASS`.
The committed `guest-validation.json` (image SHA-256
`f45a79c3…`, source `a236213`) records: graphical enrollment
with mismatched confirmation rejected; Weston desktop after
login with all windows closed by their own primitives and the
terminal exited — **the session survived the full desktop
proof**, the behavior the assert used to kill; session-end
relock; cold-reboot wrong-password denial; hard power cut
returning to login with the credential intact; destroyed-STATE
boot failing closed to a locked login; serial containing no
guest console or shell. Chromium evidence on the same run:
browser log on the DATA partition with 2 `BROWSER_STARTED`
markers, profile and Downloads directory present.

Two environment facts from this pass, recorded because they
contradict earlier notes:

- This VM's QEMU/OVMF stack was previously recorded as unable
  to boot the packaged image at all (guest resets ~20 s into
  early kernel init). The new image booted on it repeatedly
  (two manual probes reached FIRST USER SETUP; the acceptance
  then passed end to end). What changed on the host: QEMU/OVMF
  were reinstalled from the offline package cache during this
  pass, and the successful runs give the guest 4096 MB.
- At the harness's default 768 MB the same image fails in the
  EFI stub with `Failed to decompress kernel` /
  `efi_stub_entry() failed` / `Out of Resources` (serial log,
  first acceptance attempt this pass) — an OOM in kernel
  decompression, not a guest defect. Guest memory below the
  UKI's decompression needs is not a supported configuration
  for this acceptance.

### Not re-proven on this package

- The emulated-USB and VGA/simpledrm variants of the joined
  acceptance (run for earlier packages) were not re-run; only
  the virtio variant above.
- The separate browser/downloads QEMU proof (verified HTTPS,
  bad-CA refusal, download digests across reboot/update/
  rollback) was not re-run at this head; the Chromium payload
  is the same pinned closure, and this pass's changes to it
  are the added generated data files proven in the chroot
  checks above.
- The recovery maintenance/reset ESP entries were not
  re-exercised on this image; their code is unchanged by
  ADR 0022 and their evidence stands at the reset-fix record.
- **Physical hardware (TG01) remains untested**, and the
  owner-PC VM re-verification of the filmed failures (session
  survival over minutes of use, the GTK save dialog) is still
  outstanding — see ADR 0022.

## Local checks at this head

- `cargo test` (full workspace): 182 passed, 0 failed.
- `tests/ab-update.py`: 18 tests OK.
- `tests/offline-checks.py`: 8 tests OK.
- `build/scripts/doctor.sh`: PASS.
- Distro stage build with the new pixbuf/mime gate: PASS
  (marker `SYNVEIL_DISTRO_CHROMIUM_STAGED_NOT_BOOTED`).
- Native Weston build with the patch gate: PASS; `--plan`
  source verification PASS.
