# Owner first-boot test — HP Pavilion TG01 + external USB drive

This is a **boot test of a prebuilt test-media image** on a dedicated
external USB drive. It is not an install: nothing is installed
anywhere, the drive's previous contents are erased by the media
write, and the Windows disk, its ESP and the firmware boot order are
not modified by the test. The image is the current full Synveil
stack — A/B updater with graphical update controls, the Chromium
browser with its privacy configuration, and persistent Downloads —
boot-validated end to end in QEMU on this exact image (graphical
enrollment, cold reboot, wrong password denied, login, desktop with
the browser, relock, state persisted; once on the firmware-
framebuffer display path and once booted from emulated USB storage).
It has never been booted on physical hardware — that is what this
test establishes, one way or the other.

Image identity (verify before writing, and again if anything looks
off): `synveil-test-media` package, image `synveil-x86_64.img`,
SHA-256
`283b1974be9e292d6e28f5ec9848bf5427ffc9e8f5c690a16e502378df3e6c83`,
3,900,702,720 bytes (≈3.63 GiB — use an 8 GB or larger stick/drive),
source commit `9be2404b27cc9980362ff5d2cedcaecec5de0b72`.
The package also carries `synveil-release-v2.img` (SHA-256
`7dcdc68e2f7b2b9724af34f5969151cf9942f0a76d7e10bb31c470be9bcdc755`),
the signed v2 update used by the update test below. Validation
evidence: [test-media record](validation/test-media-2026-10-27/README.md).

**Publisher key:** updates are verified against the Synveil
**development** publisher key `synveil-dev-2026-01`. It is a flagged
development key, not a production release key; treat the update
test as a mechanics test, not as evidence about a future production
signing setup.

## Before you start

1. **BitLocker recovery key — do this first.** The test image is
   unsigned, so the firmware will refuse it while Secure Boot is on;
   disabling Secure Boot can make Windows demand its BitLocker /
   device-encryption recovery key at the next Windows boot. Before
   touching any firmware setting:
   - In Windows, check `manage-bde -status C:` (or Settings → Privacy
     & security → Device encryption) to learn whether encryption is on.
   - Get the 48-digit recovery key (Microsoft account → Devices →
     recovery keys, or `manage-bde -protectors -getkey C:`) and keep it
     somewhere you can read while the PC is at a recovery screen —
     phone or paper, not only on this PC.
   - If encryption is on and you cannot obtain the key, **stop**: do
     not change Secure Boot settings. Report that instead; it is a
     valid test outcome.
2. **The external drive will be completely erased** by the media
   write. Use a dedicated drive with nothing on it you need. The
   update test uses a second USB stick (any small size) for the
   release image.
3. **Plug the monitor into the RTX 3060.** The i5-10400F has no
   integrated GPU, so the motherboard's video outputs are inactive;
   only the graphics card's outputs carry a picture. Use a wired USB
   keyboard and mouse.

## Write the test media

Windows (on the TG01 itself is fine):

1. Copy the package folder to the PC and verify the image:
   `certUtil -hashfile synveil-x86_64.img SHA256` must print exactly
   the SHA-256 above. If it differs, stop — the copy is corrupt.
2. Note the drive's disk number, model and capacity in Disk
   Management (`diskmgmt.msc`). Unplug any other USB storage so
   there is exactly one candidate target.
3. Write with balenaEtcher (select the image, select **that** drive,
   Flash; Etcher's automatic validation should pass) or Rufus
   (choose the image and, when asked, **DD mode**, not ISO mode).
   Double-check the target against step 2 before confirming — the
   write is destructive and irreversible.
4. Afterwards Windows may claim the drive "needs to be formatted".
   **Do not format it** — that prompt just means Windows cannot read
   the Linux filesystems. Eject the drive safely.
5. Write `synveil-release-v2.img` to the second stick the same way
   (verify its SHA-256 with certUtil first).

Linux alternative: `write-test-media.sh` in the package does the
same write with the digest pin, whole-removable-USB-only,
backing-traced mount/swap refusal, exact-name confirmation and
read-back verification enforced by the script:
`sudo bash write-test-media.sh --image synveil-x86_64.img --device /dev/sdX --expected-sha256 283b1974be9e292d6e28f5ec9848bf5427ffc9e8f5c690a16e502378df3e6c83`
(Replace `/dev/sdX` with the drive's whole-disk device; repeat with
the release image and its digest for the second stick.)

## Boot the test image

1. Drive plugged into a rear USB port, PC off.
2. Power on and open the **one-time boot menu**: tap `Esc` at the HP
   logo, then `F9` (Boot Device Options). Select the UEFI entry for
   the USB drive. Use the one-time menu every time — do not reorder
   the permanent boot order, so Windows keeps booting first by
   default.
3. If the firmware instead reports a **Secure Boot violation** /
   invalid signature: reboot into Setup (`Esc` → `F10`), find the
   Secure Boot setting (Security or Advanced → Secure Boot
   Configuration), disable Secure Boot, save and exit, then repeat
   step 2. Remember the setting's original value; you will restore
   it after the test. (See the BitLocker warning above — the
   recovery key demand, if it comes, happens at the next *Windows*
   boot.)
4. Expected: firmware text, a scrolling text console, then the
   Synveil enrollment screen (**FIRST USER SETUP**). The root
   filesystem runs from RAM and the TG01's 32 GB is ample, but the
   first boot does real work — under a couple of minutes is normal.
   A screen that stays black or frozen for more than ~3 minutes is
   a failure — note what was last visible and stop there.

## Run the test script

Work through these in order; each step either happens or it doesn't —
note which.

1. **Mismatch check (optional, 30 s):** at FIRST USER SETUP, type a
   new test password (invent one for this test only — never your
   Windows password), press Enter, then type a *different*
   confirmation and Enter. The setup must reject it (SETUP RETRY)
   and return to CREATE PASSWORD.
2. **Enroll:** type the test password, Enter; retype it exactly,
   Enter. The screen changes to LOCAL LOGIN.
3. **Log in:** type the password, Enter. The desktop appears: a demo
   window, a terminal, a **Synveil Files** window, a **Synveil
   System Updates** window, and — within about a minute under
   software rendering — **Chromium**, which autostarts on its New
   Tab page.
4. **Desktop checks:** drag a window by its title bar; click the
   terminal and type `exit` + Enter (it should close); note the
   Files window lists your home with a **Downloads** section.
5. **Browse and download:** in Chromium, visit an HTTPS site
   (networking is configured automatically by DHCP). Download a
   small file and confirm it lands in **Downloads** (the Files
   window shows it). Leave the file there — later steps check it
   survives.
6. **Cold reboot:** power off, power on, boot menu (`Esc`/`F9`) →
   the Synveil drive again. There must be **no enrollment** —
   straight to LOCAL LOGIN.
7. **Wrong password:** type a wrong password, Enter → LOGIN
   DENIED. Then the correct password → desktop again. Confirm the
   downloaded file is still in Downloads.
8. **Update to v2:** insert the second stick (the release image).
   In the **Synveil System Updates** window, click **Stage
   update**; when it reports the update staged, click **Restart**
   (log in again after the reboot). The PC boots v2 as a *trial*:
   the desktop background turns dark green and the Updates
   window shows the trial state. Click **Confirm update**. Your
   credential, browser profile and the downloaded file must all
   still be there.
9. **Roll back to v1:** in the Updates window, click **Roll
   back** and **Restart**; log in again. The desktop background
   returns to dark blue-grey and the Updates window shows v1
   confirmed again. The downloaded file and your login must
   still work.
10. Power off. Done.

## What to report back

- Pass/fail for each numbered step above, with the step number.
- Any firmware or error message, quoted exactly or photographed —
  especially Secure Boot messages and anything mentioning a key,
  signature or verification.
- If a step never appeared: what the screen showed last (photo
  helps), and how long you waited.
- Whether Windows booted normally afterwards, and whether it
  asked for the BitLocker recovery key.
- Anything odd about the picture itself: resolution looking
  wrong, flicker, no picture on one output but a picture on
  another.
- For the update test: the exact wording of the Updates window's
  status line at each stage, and whether the background colour
  changed as described.

## Expectations and limits (not test failures)

- **Display:** the kernel carries no NVIDIA or nouveau driver.
  The desktop runs on the firmware's framebuffer (simpledrm) at
  the resolution the firmware chose, with software rendering. It
  should be clearly usable; it will not feel as smooth as
  Windows, and only the firmware's primary output is driven.
- **Network:** networking is configured (DHCP) and was proven in
  QEMU. Whether this kernel drives the TG01's own network
  hardware (wired NIC or Wi-Fi) is **unverified** — if the
  browser cannot reach anything, note it and continue with the
  other steps; that is a finding, not a mistake on your part.
- **Browser privacy configuration:** Chromium ships with the
  vendor's phone-home endpoints null-routed at the OS name layer
  (component updates, Safe Browsing, translate and similar
  services are unreachable by design) and a managed policy that
  disables telemetry, variations and sync. One disclosed
  exception, by the owner's decision of 2026-10-27:
  **accounts.google.com is reachable, so Google sign-in works**
  in this browser — know that Chromium's identity service also
  contacts it unprompted at startup, and that this traffic
  leaving the machine is the accepted cost of the exception.
  The other nine vendor endpoints stay null-routed. Browser
  updates arrive only through Synveil's signed A/B releases.
- **Desktop scope:** the demo window, terminal, Files and System
  Updates windows, and Chromium. There is no launcher or
  settings app beyond those.
- **Mid-download behaviour:** cancelling or resuming an
  interrupted download in the browser is unproven (an
  insufficient-space download outcome is proven). If you try a
  large download, note what happens rather than treating an odd
  result as your error.
- **Password loss = rewrite the media.** There is deliberately
  no password-reset or recovery shell in this image (see ADR
  0010). The drive holds only a disposable test credential, so
  recovery from any failure of *this test* is: rewrite the media
  and start over. Rewriting disposable media is **not** an
  installed-system recovery mechanism — it works here only
  because the media is disposable; ADR 0010's independent
  recovery for an installed system remains unimplemented.
- **What protects the Windows installation — specifically, not
  absolutely.** (1) The running test image writes only to the
  test drive itself: it mounts for writing only the partitions
  the image itself provides — the state and data partitions,
  and, when you stage an update, its own inactive system slot —
  each found by its fixed GPT identity (PARTUUID/PARTNAME),
  never by guessing a device name. No formatter, partitioner or
  EFI-variable tool exists in the image. (2) The boot and update
  design writes **no firmware variables**: it boots from the ESP
  fallback path and chain-loads updates by kexec. Booting uses
  the one-time boot menu (Esc/F9): the firmware's permanent boot
  order, the Windows ESP and Windows Boot Manager are not
  modified by the test or by the image. (3) The one destructive
  step is the media write, before any boot. On Linux the
  packaged writer pins the image digest, requires a whole,
  removable, USB-attached target disk, refuses any disk that
  backs a mounted filesystem or swap — tracing through
  device-mapper (LUKS/LVM) to the underlying disk and failing
  closed when it cannot tell — requires typing the exact device
  name, and verifies the write by reading it back (refusal
  tests: `tests/write-test-media.py`). On Windows the protection
  is procedural, not enforced by software: verify the digest
  with certUtil, identify the target in Disk Management, unplug
  other USB storage, and double-check the target in Etcher/Rufus
  before confirming — a write to the wrong disk there would
  erase that disk, so the identification step matters. (4) The
  image is unsigned, so Secure Boot must be disabled for the
  test — a firmware change *you* make and later revert; it can
  make Windows ask for its BitLocker recovery key (see "Before
  you start").

## After the test

- If you disabled Secure Boot, re-enable it in Setup (`Esc` →
  `F10`) before returning the PC to normal use.
- Leave the drive as written (its state partition now holds your
  test credential) unless a retest with a fresh image is
  arranged.