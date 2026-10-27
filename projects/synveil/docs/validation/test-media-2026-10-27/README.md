# Test-media record — 2026-10-27 (full-stack owner package)

The owner test-media package was rebuilt from the current head
and the four points of the 2026-10-25 independent review were
re-proven **on this image** (nothing is inherited from earlier
images). This is the package's second rebuild of the day: the
first (source `9be2404`, image `283b1974…`) was superseded
before delivery by the owner's final decision on browser
connections (below), and nothing from it ships.

**Browser configuration of this image:** stock. By the
owner's explicit decision of 2026-10-27 ("I don't want you
blocking connections at all"), the shipped Chromium carries
**no connection blocking in any layer** — no `/etc/hosts`
null-routing, no managed policy, no blocking launcher flags
or seeded preferences. What remains is the integration that
is not connection control: Wayland/Ozone launch, the kernel
sandbox, TLS verification, the persistent profile, and a
profile seed pinning only the download directory. The
earlier same-day states (the three-layer privacy regime, the
IPv6 gate correction, then the accounts.google.com
exception) are recorded in `docs/BROWSER.md` and the addenda
to the browser-privacy record; that record describes a
superseded image.

1. **Writer safety** — `tests/write-test-media.py`: 15/15
   fixture refusal tests pass at the final head. The writer
   traces every mounted filesystem and swap device through
   sysfs backing-device relationships (device-mapper/LVM/LUKS,
   md, loop) to the whole disks behind them, fails closed when
   a chain cannot be determined, pins the image digest,
   requires an exact device-name confirmation, and verifies a
   full read-back digest. Fixtures only; no device was
   written.
2. **Graphics path** — the `vga` variant below: the complete
   image passed the full framebuffer acceptance with the
   display on QEMU **standard VGA** (no virtio GPU attached).
   Driver basis, stated exactly: the hardware kernel carries
   `CONFIG_DRM_SIMPLEDRM=y` and `CONFIG_DRM_BOCHS` is **not
   set** (verified from the gen-v1 build manifests), so with
   no other DRM driver able to bind the VGA adapter, the
   session ran through **simpledrm on the EFI framebuffer** —
   the same path the TG01's RTX 3060 will use. Physical RTX
   3060 behaviour remains explicitly unverified
   (`physical_hardware_tested: false` in both records).
3. **USB storage boot** — the `usb` variant below: the
   complete image booted from emulated USB storage
   (`qemu-xhci` + `usb-storage`) through the full sequence:
   graphical enrollment, mismatched confirmation rejected,
   cold reboot, wrong password denied, login, desktop **with
   the browser**, session-end relock, hard power cut returning
   to the same login screen with the credential intact, and a
   destroyed-STATE boot failing closed to the locked login —
   state on the image-provided STATE partition throughout.
   The browser's presence is not implied: the harness read
   the DATA partition back from the booted disk copies and
   found the sessions' browser logs with
   `SYNVEIL_BROWSER_STARTED` markers (2 in the VGA run, 3 in
   the USB run), the Chromium profile, and the Downloads
   directory (`chromium_launched_and_persisted_on_data: true`
   in both records).
4. **Claims discipline** — the package documents
   (`OWNER_FIRST_BOOT_TEST.md` in the package,
   `docs/PHYSICAL_BOOT.md`, package `PACKAGE.json`) contain
   no absolute "Windows cannot be affected" language; they
   enumerate the specific protections: the guest's writes
   confined to its own STATE/DATA partitions and (when
   staging) its inactive system slot, all located by fixed
   GPT identity; no formatter, partitioner or EFI-variable
   tool in the image; the boot/update design writes **no
   firmware variables** (ESP fallback + kexec chain-load);
   the one-time boot menu leaves the permanent boot order,
   the Windows ESP and Windows Boot Manager untouched; the
   media write is the only destructive step — guarded on
   Linux (digest pin, whole-removable-USB-only,
   backing-traced refusal failing closed, exact-name
   confirmation, read-back verify) and procedural-only on
   Windows, named there as the weaker path.

## Identities

- Build source commit:
  `9dbeda0d2be75c3f6e3267c949ec6db3656193e3`
  (`tools/native_ab.py --build --browser --boot-target
  hardware`). This source is the unblocking change itself:
  hosts null-routing, managed policy, blocking flags/seed,
  the receipt's privacy fields, and the gate's egress
  conditions all removed; `tests/smoke-gates.py` carries the
  positive fixture `test_vendor_egress_not_gated` (the IPv6
  extraction work remains, as receipt information only).
- Disk image `synveil-x86_64.img`: SHA-256
  `4be22adaaddb4c5e5abab87d8d636abc18cd4f4e67265b0a1fac188db1925553`,
  3,900,702,720 bytes. Layout (ADR 0011): ESP 768 MB,
  SYSTEM_A 768 MB (v1 installed), SYSTEM_B 768 MB (empty
  until an update stages), STATE 256 MB, DATA 384 MB,
  RECOVERY 768 MB.
- Release media `synveil-release-v2.img` (in the package):
  SHA-256
  `172888a85d490506ef8a4947ffbbfbe8ab1232d5af66de227b319234f57f6f3d`.
- Browser: Chromium `156.0.8078.47-1~deb13u1`,
  stock-configured, and **no proof material** — the build
  receipt records `test_ca: None`, `test_host: None`,
  `start_url: None`, and its browser record carries no
  privacy/null-routing fields at all (the fields no longer
  exist).
- Publisher: development key `synveil-dev-2026-01`
  (`development: true` in the build receipt).

## What the guest records do and do not claim

- The A/B desktop proof is a **peel**, not the joined image's
  drag/
...[truncated 2981 chars]