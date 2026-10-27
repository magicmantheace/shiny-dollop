# Test-media record — 2026-10-27 (full-stack owner package)

The owner test-media package was rebuilt from the current head and
the four points of the 2026-10-25 independent review were re-proven
**on this image** (nothing is inherited from earlier images):

1. **Writer safety** — `tests/write-test-media.py`: 15/15 fixture
   refusal tests pass at the final head. The writer traces every
   mounted filesystem and swap device through sysfs
   backing-device relationships (device-mapper/LVM/LUKS, md, loop)
   to the whole disks behind them, fails closed when a chain
   cannot be determined, pins the image digest, requires an exact
   device-name confirmation, and verifies a full read-back digest.
   Fixtures only; no device was written.
2. **Graphics path** — the `vga` variant below: the complete image
   passed the full framebuffer acceptance with the display on
   QEMU **standard VGA** (no virtio GPU attached). Driver basis,
   stated exactly: the hardware kernel carries
   `CONFIG_DRM_SIMPLEDRM=y` and `CONFIG_DRM_BOCHS` is **not set**
   (verified from the gen-v1 build manifests), so
   with no other DRM driver able to bind the VGA adapter, the
   session ran through **simpledrm on the EFI framebuffer** — the
   same path the TG01's RTX 3060 will use. Physical RTX 3060
   behaviour remains explicitly unverified
   (`physical_hardware_tested: false` in both records).
3. **USB storage boot** — the `usb` variant below: the complete
   image booted from emulated USB storage (`qemu-xhci` +
   `usb-storage`) through the full sequence: graphical
   enrollment, mismatched confirmation rejected, cold reboot,
   wrong password denied, login, desktop **with the browser**,
   session-end relock, hard power cut returning to the same login
   screen with the credential intact, state on the
   image-provided STATE partition throughout. The browser's
   presence is not implied: the harness read the DATA partition
   back from the booted disk copy and found the session's
   browser log with **2 `SYNVEIL_BROWSER_STARTED` markers** (one
   per boot), the Chromium profile, and the Downloads directory
   (`chromium_launched_and_persisted_on_data: true`).
4. **Claims discipline** — the package documents
   (`docs/OWNER_FIRST_BOOT_TEST.md`, `docs/PHYSICAL_BOOT.md`,
   package `PACKAGE.json`) contain no absolute "Windows cannot be
   affected" language; they enumerate the specific protections:
   the guest's writes confined to its own STATE/DATA partitions
   and (when staging) its inactive system slot, all located by
   fixed GPT identity; no formatter, partitioner or EFI-variable
   tool in the image; the boot/update design writes **no firmware
   variables** (ESP fallback + kexec chain-load); the one-time
   boot menu leaves the permanent boot order, the Windows ESP and
   Windows Boot Manager untouched; the media write is the only
   destructive step — guarded on Linux (digest pin,
   whole-removable-USB-only, backing-traced refusal failing
   closed, exact-name confirmation, read-back verify) and
   procedural-only on Windows, named there as the weaker path.

## Identities

- Build source commit: `9be2404b27cc9980362ff5d2cedcaecec5de0b72`
  (`tools/native_ab.py --build --browser --boot-target hardware`).
  The source includes this pass's harness work (peel desktop
  proof, journal-aware readback, image-lock wait — `7473b2e`,
  `b9fd698`, `75c6f83`, `176e955`) and the change set of
  `9be2404` itself (accounts.google.com unblock + IPv6 gate
  fix, below). An earlier package built from `768150a` in this
  same pass was superseded before delivery when the owner's
  unblock decision arrived; nothing from it ships.
- Disk image `synveil-x86_64.img`: SHA-256
  `283b1974be9e292d6e28f5ec9848bf5427ffc9e8f5c690a16e502378df3e6c83`,
  3,900,702,720 bytes. Layout (ADR 0011): ESP 768 MB, SYSTEM_A
  768 MB (v1 installed), SYSTEM_B 768 MB (empty until an update
  stages), STATE 256 MB, DATA 384 MB, RECOVERY 768 MB.
- Release media `synveil-release-v2.img` (in the package):
  SHA-256
  `7dcdc68e2f7b2b9724af34f5969151cf9942f0a76d7e10bb31c470be9bcdc755`.
- Browser: Chromium `156.0.8078.47-1~deb13u1` with the shipped
  privacy layers (managed policy, launcher flags/profile seed,
  `/etc/hosts` null-routing of 9 vendor hosts) and **no proof
  material** — the build receipt records `test_ca: None`,
  `test_host: None`, `start_url: None`, and its
  `nulled_phone_home_hosts` list is exactly the nine.
  **accounts.google.com is reachable by the owner's decision
  of 2026-10-27** (Google sign-in works); the privacy gate's
  IPv6 blindness found by the same day's independent review is
  fixed at this source (parser extracts IPv6 endpoints;
  regression fixtures in `tests/smoke-gates.py`), and the gate
  treats accounts.google.com as the disclosed exception. The
  privacy measurement itself stands at the
  [browser-privacy record](../browser-privacy-proof-2026-10-27/README.md)
  **as corrected there**: its egress values are the IPv4 set
  its parser then measured; this record repeats no absolute
  no-egress claim.
- Publisher: development key `synveil-dev-2026-01`
  (`development: true` in the build receipt).

## What the guest records do and do not claim

- The A/B desktop proof is a **peel**, not the joined image's
  drag/resize choreography: the five full-stack windows stack in
  varying order, so each window is closed by its own proven
  primitive (browser by focus click + Ctrl+Shift+W after its
  page settles, files and update GUI by their drawn close
  boxes, first window by raise + Escape), the terminal is
  focused and exited by the typed fixed `exit` command, and
  success is the login screen's return — the session's own end
  condition. `pointer_move_resize_keyboard` is recorded
  **false** for this image and
  `desktop_windows_closed_and_terminal_exited` true; no
  drag/resize is claimed for the A/B desktop.
- The broken-state boot is **skipped** (recorded in both JSONs):
  on the A/B layout a destroyed STATE partition takes the
  recovery-diagnostics path, not this harness's locked-login
  path. It is not part of this pass's sequence.
- The update/rollback mechanics themselves stand at the earlier
  records (`ab-qemu-proof-2026-10-26`,
  `ab-gui-qemu-proof-2026-10-26`,
  `browser-qemu-proof-2026-10-27`); this pass proves the
  packaged full-stack image boots and runs its whole desktop
  from both the framebuffer path and USB storage.

## Failures on the way (kept, with causes)

- First framebuffer attempt died copying the 3.9 GB image into a
  512 MB tmpfs (harness `TMPDIR` placement) — environment, not
  the image.
- At the harness's former default 1024 MB the hardware-kernel
  image **panics** in `do_populate_rootfs` (write error
  unpacking the ~560 MB browser rootfs): a real minimum-RAM
  fact for this stack, captured on the serial console. The
  acceptance runs at 3072 MB, as the browser acceptance does;
  the TG01's 32 GB is far above the failing size.
- The joined desktop proof failed on this healthy desktop
  (window occlusion by the files/GUI windows and the
  autostarted browser) — resolved by the peel proof above, not
  by weakening a gate: session end still requires both the
  first window and the terminal to exit.
- The first USB run's guest sequence passed but its readback
  reported no browser evidence (profile spuriously "present"):
  SIGTERM teardown leaves the DATA journal un-replayed and
  debugfs could not open the extracted copy at all. Journal
  replay on a copy recovered the complete evidence, and the
  readback now replays the journal and fails distinctly when a
  filesystem will not open.
- One USB re-run died at the power-cut-recovery boot with
  QEMU's "Failed to get write lock": qemu.sh backgrounds QEMU
  under bash, so the wrapper's exit did not prove the lock was
  released. Harness teardown now waits for the lock.
- The rebuild for the post-decision source took three
  attempts: the rootfs step refuses a dirty checkout (the
  pass's own uncommitted docs — stashed and restored); a
  compiler died on a full 512 MB `/tmp` tmpfs (this pass's own
  diagnostic extract — cleaned, build `TMPDIR` moved to the
  workspace mount); and one build was killed mid-assembly by
  an environment restart and rerun detached. None of these
  touched the image's content; the receipt above is from the
  completed run and its digest was recomputed independently.

## Files

- `guest-validation-vga.json` — framebuffer (standard VGA,
  simpledrm) variant, storage virtio-blk.
- `guest-validation-usb.json` — emulated USB storage variant,
  graphics virtio-vga.
- `build-receipt.json` — the image build receipt (source,
  digests, generations, publisher, browser payload).
