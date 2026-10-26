# Owner first-boot test — HP Pavilion TG01 + external USB SSD

This is a **boot test of a prebuilt test image** on a dedicated external
SSD. It is not an install: nothing is installed anywhere, the SSD's
previous contents are erased by the media write, and the Windows disk,
its ESP and the firmware boot order are not modified. The image has
been boot-validated end to end in QEMU (enrollment, login, desktop,
persistence); it has never been booted on physical hardware — that is
what this test establishes, one way or the other.

Image identity (verify before writing, and again if anything looks
off): `synveil-test-media` package, image SHA-256
`6b10b482239ca3e771bd20d85a5f4e0dc414a00fc34334408eb134b150bacfc3`,
source commit `124abbc`, build target `hardware`. Validation evidence:
[joined-hardware record](validation/joined-hardware-124abbc/README.md).

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
2. **The external SSD will be completely erased** by the media write.
   Use a dedicated drive with nothing on it you need.
3. **Plug the monitor into the RTX 3060.** The i5-10400F has no
   integrated GPU, so the motherboard's video outputs are inactive;
   only the graphics card's outputs carry a picture. Use a wired USB
   keyboard and mouse.

## Write the test media

Windows (on the TG01 itself is fine):

1. Copy the package folder to the PC and verify the image:
   `certUtil -hashfile synveil-x86_64.img SHA256` must print exactly
   the SHA-256 above. If it differs, stop — the copy is corrupt.
2. Note the SSD's disk number, model and capacity in Disk Management
   (`diskmgmt.msc`). Unplug any other USB storage so there is exactly
   one candidate target.
3. Write with balenaEtcher (select the image, select **that** drive,
   Flash; Etcher's automatic validation should pass) or Rufus (choose
   the image and, when asked, **DD mode**, not ISO mode). Double-check
   the target against step 2 before confirming — the write is
   destructive and irreversible.
4. Afterwards Windows may claim the drive "needs to be formatted".
   **Do not format it** — that prompt just means Windows cannot read
   the Linux filesystem. Eject the drive safely.

Linux alternative: `tools/write-test-media.sh` in the project does
the same write with the digest pin, removable/USB, mount and
confirmation guards enforced by the script:
`sudo bash tools/write-test-media.sh --image synveil-x86_64.img --device /dev/sdX --expected-sha256 6b10b482239ca3e771bd20d85a5f4e0dc414a00fc34334408eb134b150bacfc3`
(Replace `/dev/sdX` with the SSD's whole-disk device.)

## Boot the test image

1. SSD plugged into a rear USB port, PC off.
2. Power on and open the **one-time boot menu**: tap `Esc` at the HP
   logo, then `F9` (Boot Device Options). Select the UEFI entry for
   the USB SSD. Use the one-time menu every time — do not reorder the
   permanent boot order, so Windows keeps booting first by default.
3. If the firmware instead reports a **Secure Boot violation** /
   invalid signature: reboot into Setup (`Esc` → `F10`), find the
   Secure Boot setting (Security or Advanced → Secure Boot
   Configuration), disable Secure Boot, save and exit, then repeat
   step 2. Remember the setting's original value; you will restore it
   after the test. (See the BitLocker warning above — the recovery
   key demand, if it comes, happens at the next *Windows* boot.)
4. Expected: firmware text, a scrolling text console, then the Synveil
   enrollment screen (**FIRST USER SETUP**). Under a minute is normal.
   A screen that stays black or frozen for more than ~2 minutes is a
   failure — note what was last visible and stop there.

## Run the test script

Work through these in order; each step either happens or it doesn't —
note which.

1. **Mismatch check (optional, 30 s):** at FIRST USER SETUP, type a
   new test password (invent one for this test only — never your
   Windows password), press Enter, then type a *different*
   confirmation and Enter. The setup must reject it (SETUP RETRY) and
   return to CREATE PASSWORD.
2. **Enroll:** type the test password, Enter; retype it exactly,
   Enter. The screen changes to LOCAL LOGIN.
3. **Log in:** type the password, Enter. The desktop appears with two
   windows (a demo window and a terminal).
4. **Desktop checks:** drag a window by its title bar; drag a corner
   to resize; click the terminal and type `exit` + Enter (it should
   close); press `Esc` with the other window focused (session ends
   and the login screen returns — this is the relock working).
5. **Cold reboot:** power off, power on, boot menu (`Esc`/`F9`) →
   SSD again. This time there must be **no enrollment** — straight to
   LOCAL LOGIN.
6. **Wrong password:** type a wrong password, Enter → LOGIN DENIED.
   Then the correct password → desktop again.
7. Power off. Done.

## What to report back

- Pass/fail for each numbered step above, with the step number.
- Any firmware or error message, quoted exactly or photographed —
  especially Secure Boot messages and anything mentioning a key,
  signature or verification.
- If a step never appeared: what the screen showed last (photo
  helps), and how long you waited.
- Whether Windows booted normally afterwards, and whether it asked
  for the BitLocker recovery key.
- Anything odd about the picture itself: resolution looking wrong,
  flicker, no picture on one output but a picture on another.

## Expectations and limits (not test failures)

- **Display:** the kernel carries no NVIDIA or nouveau driver. The
  desktop runs on the firmware's framebuffer (simpledrm) at the
  resolution the firmware chose, with software rendering. It should
  be clearly usable; it will not feel as smooth as Windows, and only
  the firmware's primary output is driven.
- **Network:** this test image does not configure networking. No
  network is expected and none is needed for the test.
- **Desktop scope:** two windows (demo + terminal). There is no
  launcher, file manager or settings app yet.
- **Password loss = rewrite the media.** There is deliberately no
  password-reset or recovery shell in this image (see ADR 0010). The
  SSD holds only a disposable test credential, so recovery from any
  failure is: rewrite the media and start over. Nothing on the
  Windows disk can be affected by anything the test image does: it
  never writes outside its own SSD, and its state lives on the
  partition the image itself provides.

## After the test

- If you disabled Secure Boot, re-enable it in Setup (`Esc` → `F10`)
  before returning the PC to normal use.
- Leave the SSD as written (its state partition now holds your test
  credential) unless a retest with a fresh image is arranged.
