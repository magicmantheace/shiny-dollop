# Physical UEFI boot bring-up

**Status (2026-10-25): Ready for the owner's first boot test — not an install, not yet physically validated.**

**Networking/browser scope note (2026-10-26):** the A/B proof disk
(not this test-media image) gained guest networking and a graphical
browser, demonstrated **in QEMU only** — QEMU user networking
(slirp) with a `virtio-net-pci` device; see
[BROWSER.md](BROWSER.md) and the
[browser proof record](validation/browser-qemu-proof-2026-10-26/README.md).
The owner test-media image described below still contains **no
networking**, and the TG01's network hardware, drivers, and
firmware remain **unverified**. Nothing in the QEMU browser proof
changes this document's physical-boot status.

**Review resolution (2026-10-25):** an independent review found the
earlier "owner test-ready" conclusion premature and held the status
at "Not ready" until four points closed with evidence. They have now
closed — (1) the test-media writer traces backing-device
relationships (device-mapper/LVM/LUKS, md, loop) for every mount and
swap source, fails closed on uncertainty, and carries 15 fixture
refusal tests; (2) the driver used by the original acceptance was
identified as virtio_gpu (diagnostic-twin serial evidence), and the
full acceptance was re-run with the display on simpledrm (standard
VGA, no virtio GPU); (3) the complete joined hardware image was
booted from emulated USB storage through the full acceptance
sequence; (4) recovery and Windows-safety wording now states only
the specific protections implemented and tested, and keeps explicit
that rewriting disposable test media is not independent
installed-system recovery. Full record:
[review-resolution record](validation/review-resolution-2026-10-25/README.md).
Physical RTX 3060 compatibility remains explicitly unverified.

Target: HP Pavilion TG01, Intel i5-10400F, RTX 3060 12 GB, 32 GB RAM,
USB HID keyboard/mouse, UEFI firmware and Windows 11 on the internal disk.

A single **joined image** now exists that boots (in QEMU) through
graphical enrollment and login into a multiwindow Weston desktop,
with state on a GPT state partition the image itself provides, and
the hardware-profile build of that same image has now been
boot-validated end to end in QEMU/OVMF — enrollment, login, Weston
desktop, cold-reboot persistence, plus hard-power-cut and
broken-state failure boots
([validation record](validation/joined-hardware-124abbc/README.md)).
The owner test-media package (`out/test-media/`: image, SHA256SUMS,
guarded writer, [owner guide](OWNER_FIRST_BOOT_TEST.md)) is assembled
and checksum-verified. The EFI binaries remain **unsigned** (Secure
Boot handling, including the BitLocker caution, is in the owner
guide), and HP firmware behavior is unverified until the owner's
test. This is a disposable-media boot test; a safe standalone owner
install additionally requires the ADR 0010 recovery program and the
A/B milestone below.

## Exact separation of targets

- `SYNVEIL_BOOT_TARGET=qemu` (default): use QEMU virtio graphics, serial
  diagnostics and existing automated tests.
- `SYNVEIL_BOOT_TARGET=hardware` (opt in): request UEFI GOP/simpleDRM
  framebuffer with text console on `tty0`; compile USB HID, mass storage,
  UAS, AHCI and NVMe support into the kernel. This is a kernel **build**
  target only. It does not enable NVIDIA acceleration, create an installer,
  verify Secure Boot, or alter an installed disk.
- Kernel build writes `out/manifests/kernel-boot-target.txt`; subsequent
  `bash build.sh manifest` records `boot_target` from that file, not from
  the caller's current shell environment. Ordinary QEMU bundles must reject
  a hardware-labelled build.

## Safe, file-only developer build

In an isolated Linux development checkout with the pinned toolchain built:

```sh
# This section builds artifacts under out/. It does NOT write a USB.
# For this kernel/EFI validation only, omit native core and owner credentials.
SYNVEIL_GRAPHICS_ROOTFS=1 SYNVEIL_DESKTOP_AUTOSTART=1 \
SYNVEIL_NETWORK_ROOTFS=1 bash build.sh rootfs

SYNVEIL_BOOT_TARGET=hardware bash build.sh kernel
bash build.sh image
bash build.sh manifest
bash tests/inspect-image.sh out/synveil-x86_64.img
grep -E 'CONFIG_(DRM_SIMPLEDRM|SYSFB_SIMPLEFB|USB_STORAGE|BLK_DEV_NVME|SATA_AHCI)=y' \
    out/manifests/kernel.config
cat out/manifests/kernel-boot-target.txt
```

Keep the output under `out/` (a normal file). Do not run `dd`,
`mkfs`, `parted`, or an installer against any physical device for this
milestone. The existing `image.sh` creates its GPT partitions **inside a
regular image file**, without privileges or loop devices. Its success is not
a claim of boot success on the physical machine.

## Mandatory gates before owner-side USB boot

- [x] Source-built hardware kernel and FAT/EFI image verified in CI
      ([hardware build proof at 0cc3879](https://github.com/magicmantheace/Synveil/actions/runs/39505922998)).
      This is build-only evidence, not an actual hardware boot.
- [x] Experimental Debian/XFCE ISO built with BIOS and UEFI El Torito
      boot entries verified ([image build](https://github.com/magicmantheace/Synveil/actions/runs/39506908391),
      [fail-closed UEFI inspection](https://github.com/magicmantheace/Synveil/actions/runs/39522697228)).
      An entry in an ISO is not proof of a running desktop.
- [x] Experimental **Debian/XFCE** image booted in actual OVMF/QEMU UEFI
      and Xfwm4 moved/resized, maximized, minimized and restored its
      real Terminal and Thunar application windows. Both the serial session
      marker and framebuffer passed at exact SHA `c0242259f`
      ([completed CI evidence](https://github.com/magicmantheace/Synveil/actions/runs/39541711454),
      [validation record](validation/desktop-live-c024225/README.md)).
      The [subsequent 437020d guest run](validation/desktop-live-437020d/README.md)
      additionally passed **two fresh EFI cold boots**, a running panel and
      graphical Settings Manager. No state/data persisted between those boots.
      This is **not** a native Synveil compositor, protected owner login,
      installed-system boot, hardware GPU test, or production release.
- [x] Correct `tty0` screen diagnostics and UEFI firmware framebuffer
      tested in a disposable QEMU UEFI graphical session.
      Proven for the hardware-profile joined image (2026-10-25): in an
      OVMF graphical session the acceptance recorded distinct live
      text-console frames on the UEFI framebuffer before the greeter
      took over, and the auth UI + Weston desktop rendered through
      that framebuffer path at 1280×800 — see
      [validation record](validation/joined-hardware-124abbc/README.md).
      This is the emulated GOP framebuffer; the TG01's physical panel
      path is covered by the physical-validation gate below.
      **Extended (2026-10-25, review resolution):** the original
      acceptance's display driver was identified as virtio_gpu
      (diagnostic-twin evidence), and the full acceptance was re-run
      with the display on **simpledrm** (standard VGA — the firmware-
      framebuffer path the RTX 3060 will use) and again with the
      complete image booted from **emulated USB storage**; both pass
      ([record](validation/review-resolution-2026-10-25/README.md)).
- [ ] Real multiwindow desktop with graphical login and owner enrollment;
      keyboard, pointer, launcher, terminal, file manager and settings.
      **QEMU-proven subset (2026-10-25, joined image @ 124abbc):**
      graphical enrollment + login (wrong password denied after cold
      reboot), multiwindow Weston desktop, keyboard and pointer incl.
      window move/resize, weston-terminal, session-end relock, state
      persisted on the image-provided partition — see
      [validation record](validation/joined-124abbc/README.md).
      The same acceptance now also passes on the **hardware-profile
      image** (scanout-driven driver; power-cut and broken-state
      failure boots included) — see
      [validation record](validation/joined-hardware-124abbc/README.md).
      Still missing: launcher, file manager and settings applications;
      any physical-hardware boot.
- [x] Non-root session; no unauthenticated serial or local root-shell bypass.
      Proven for the joined image in QEMU (2026-10-25): the desktop
      session runs as UID 1000 behind the seat lease, the production
      profile carries no developer-serial-recovery marker, and the
      serial console stays locked through enroll/login/relock.
      Extended to the hardware-profile image the same day: its
      initramfs inventory shows the auth-desktop marker and no
      developer-serial-recovery marker, and across four QEMU runs
      (including the broken-state boot) the serial capture contained
      only firmware output — the guest has no serial console at all
      (console=tty0) and the tty0 console stays locked.
      Physical-hardware confirmation remains outstanding.
- [ ] Independent console/recovery path when the desktop/seat fails.
      **Partially proven (2026-10-25):** bounded supervisor restarts
      for seat and desktop, fail-closed relock on session end/seat
      loss, recovery from a hard power cut mid-session, and fail-
      closed degradation to a locked login when the state filesystem
      is destroyed — all exercised on the hardware-profile image in
      QEMU ([validation record](validation/joined-hardware-124abbc/README.md)).
      The read-only `recovery-status` diagnostic mode (ADR 0010 tier
      A) exists in the initramfs but is unreachable under this image's
      fixed kernel command line, and the interactive owner recovery
      of ADR 0010 tiers B–D is unimplemented and gated on an
      owner-approved design. For this disposable test media the
      documented recovery procedure is a media rewrite
      ([owner guide](OWNER_FIRST_BOOT_TEST.md)). The gate stays open
      for installed systems.
- [x] Signed or otherwise owner-verified release/image provenance, with
      clear test-media identification and checksums.
      Owner-verified route (2026-10-25): the image is **unsigned**;
      its SHA-256 is pinned in the committed
      [validation record](validation/joined-hardware-124abbc/README.md)
      and in the package's `PACKAGE.json`/`SHA256SUMS`
      (`out/test-media/`, `sha256sum --check` verified). Test-media
      identification is explicit in the package name, manifest warning
      and owner guide. Signing remains a release-milestone item.
- [x] Dedicated removable-media preparation method reviewed for correct
      device identity and destructive-operation confirmation.
      Provided (2026-10-25): `tools/write-test-media.sh` pins the
      expected digest from the validation record, accepts only whole
      removable/USB disks (never partitions, never internal disks),
      refuses mounted or system-hosting devices, displays model,
      serial and size, requires typing the exact device name, and
      verifies a full read-back digest after writing; its refusal
      paths were executed in this environment. The reviewed Windows
      path (digest check via certUtil, target identification in Disk
      Management, balenaEtcher with automatic validation or Rufus in
      DD mode) is in the [owner guide](OWNER_FIRST_BOOT_TEST.md).
      **Hardened (2026-10-25, review resolution):** the in-use check
      no longer compares device-name prefixes — it traces every
      mounted filesystem and swap device through sysfs
      backing-device relationships (device-mapper slaves for
      LUKS/LVM, md components, loop backing files) to the whole
      disks behind them and fails closed when a chain cannot be
      determined; 15 fixture tests cover the refusal cases,
      including LUKS/LVM volumes backed by the selected disk
      ([record](validation/review-resolution-2026-10-25/README.md)).
- [ ] Documented HP firmware compatibility, USB boot selection, network
      and RTX 3060 fallback limitations. Windows partitions must remain
      untouched, including firmware boot-order and ESP changes.
      **Documentation written (2026-10-25)** in the
      [owner guide](OWNER_FIRST_BOOT_TEST.md): one-time boot-menu
      selection (Esc/F9) so the permanent boot order, ESP and Windows
      partitions are untouched by construction; Secure Boot handling
      with the BitLocker-recovery caution; RTX 3060 expectations (no
      NVIDIA/nouveau driver in the kernel — firmware framebuffer via
      simpledrm, software rendering, firmware-chosen resolution, the
      10400F's inactive motherboard video outputs); no networking in
      this test image. Firmware *compatibility* itself can only be
      established by the physical test below.
- [ ] Physical validation recorded **separately** from QEMU.

UEFI Secure Boot may reject unsigned EFI-stub binaries. Changing Secure Boot
could trigger Windows device-encryption/BitLocker recovery. Do not make
firmware security changes without appropriate recovery planning and explicit
owner authorization.

## Updateable external SSD (later milestone)

Before installation: confirm an A/B immutable system design (ESP, slots A/B,
persistent home/state, independent recovery), partition identification via
stable verified UUIDs, and signed release/update metadata. Prove startup
attempt accounting, boot-health confirmation, interrupted write handling,
confirmed-slot fallback, user-data preservation, and manual rollback on
**disposable** virtual disks. Never install over or modify Windows media.

See [ADR 0013](adr/0013-first-boot-desktop-priority.md),
[ADR 0011](adr/0011-dual-slot-installation.md), and
[the first-install contract](FIRST_INSTALL.md).
