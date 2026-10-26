# Bootable A/B OS updater with rollback — design (2026-10-25)

Status: **design accepted for implementation; not yet demonstrated.**
This document is the design contract for turning the signed
regular-file transaction fixture (`docs/VM_AB_UPDATE.md`,
`tools/ab_vm_update.py`) into a working bootable A/B updater for the
native joined image. It does not replace Synveil with another
distribution, and it does not weaken any existing boundary: the
credential authority, Argon2id protections, non-root sessions and
fail-closed authentication are untouched.

## Layout (extends ADR 0011)

One GPT disk, partitions identified by PARTUUID, never by enumeration
name:

| Partition | Contents | Written by updates? |
|---|---|---|
| ESP | `EFI/BOOT/BOOTX64.EFI` = recovery-status UKI (ADR 0010 tier A, read-only diagnostics); boot entries for slot A, slot B, recovery | No (entries only at install) |
| SYSTEM_A | FAT, `EFI/synveil/gen.efi` (one generation UKI) + `gen.json` identity | Only while inactive |
| SYSTEM_B | same | Only while inactive |
| STATE | ext4 — credentials, home, settings, **update control record + history** | Never by slot writes |
| DATA | owner files (downloads etc.) | Never |
| RECOVERY | reserved for the ADR 0010 recovery program | Never |

A *generation* is exactly the joined image's boot payload: one UKI
(kernel + initramfs rootfs, the same artifact `tools/native_joined.py`
produces per build). Generations are whole and immutable; a slot
holds one generation.

## Boot selection — UEFI one-shot BootNext

Synveil has no bootloader of its own and gains none. Selection uses
standard UEFI variables, which the hardware kernel already supports
(`CONFIG_EFIVAR_FS=y`):

- Install time creates three boot entries (A, B, recovery) and sets
  `BootOrder` = [confirmed slot, other slot, recovery]. The firmware
  default path (`EFI/BOOT/BOOTX64.EFI`, the recovery UKI) is the
  last-resort entry if variables are lost.
- A trial boot is requested by writing `BootNext` = candidate entry.
  `BootNext` is one-shot by UEFI definition: if the candidate fails
  in any way that returns control to the firmware (panic — the
  kernel cmdline carries `panic=-1` — power cut, or an explicit
  reboot from early init), the next boot follows `BootOrder`, i.e.
  the confirmed slot. No Synveil code needs to run for the fallback
  to happen.
- Promotion is explicit: only after the candidate's own health
  checks pass does it rewrite `BootOrder` to put itself first and
  mark itself confirmed in the control record.

## Attempt accounting — before control transfer, and before services

Two durable writes bracket every trial:

1. **Before the reboot into the candidate**, the updater (running on
   the confirmed system) persists the control record with
   `trial = {slot, version, sha256, attempts: 3}` (atomic
   tmp+rename+fsync on STATE) and only then sets `BootNext` and
   reboots. A crash between the record write and `BootNext` leaves a
   pending trial that the confirmed system reports and the owner can
   cancel — it never boots unaccounted.
2. **At the candidate's earliest init**, before the seat or desktop
   starts: mount STATE, read the record; if this boot is the trial
   slot, decrement `attempts` and persist+fsync *before* starting
   services. If `attempts` is already 0, reboot immediately (firmware
   falls back to the confirmed slot). A candidate that cannot even
   mount STATE or parse the record reboots without starting
   services — fail closed, fallback by firmware.

## Health confirmation

A trial generation confirms itself only when all of these are true
in the running candidate: STATE mounted read-write and the control
record re-read intact; the credential verifier answers a probe
against the existing credential (no re-enrollment); the seat broker
and display greeter are up; the session supervisor reports no
crash-loop; the generation's own identity (version + digest of the
running UKI as staged) matches the trial record. Confirmation
writes `confirmed = trial`, appends a history entry, promotes
`BootOrder`, and clears `BootNext` if still set. Any failure:
reboot unpromoted; attempts bound the retries; exhaustion leaves
the confirmed generation in charge, and the failed candidate stays
in its slot, marked in history, until an owner decision or a newer
stage overwrites it.

## Update transaction (running system)

Performed by the update service through the existing typed privilege
boundary (the desktop never gets a root shell; Priority 2 wires the
GUI to these actions):

1. Fetch release metadata + payload from the configured source
   (in QEMU proof: a local directory/virtio share; the transport is
   not the trust mechanism).
2. Authenticate: Ed25519 signature over the exact metadata bytes,
   verified against the **pinned publisher key** (below). Then
   verify the payload's SHA-256 and size against the metadata.
3. Refuse, before any write, on: bad signature; expired or
   not-yet-valid metadata; version not strictly greater than the
   confirmed version (**replay/downgrade refusal** — a re-offered
   old release is rejected even if validly signed); migration window
   violated (below); a trial already pending; confirmed slot failing
   its digest check (never build on a corrupt base).
4. Write the payload to the **inactive slot only**, fsync, read back
   and re-verify the digest from the slot itself. The running and
   confirmed slot is never opened for writing.
5. Persist the trial record (accounting rule 1), set `BootNext`,
   report "restart to try the update". Interruption at any point
   before step 5 leaves the system exactly as it was; interruption
   during step 4 leaves an unverifiable inactive slot that no record
   points at — it is inert.

## Publisher trust

- The verification key is **provisioned independently of any
  update**: it is pinned into the system generation at build time
  from the release-signing infrastructure, and an update can never
  introduce, replace, or extend trust. A release that supplies its
  own key is refused by construction (the verifier has no input for
  a key).
- The current key is a **development key**, identified as
  `synveil-dev-2026-01` in metadata and in every record; its private
  half exists only in the (git-ignored) fixture/proof area, never in
  Git, images, logs, or CI artifacts. Production requires a
  separately generated key provisioned the same way; the mechanism
  does not change.
- Rotation: a metadata field `next_key` may *announce* a successor
  fingerprint, but the successor becomes trusted only when a
  generation carrying it (pinned at build time) is itself confirmed
  — trust moves with confirmed generations, never with metadata
  alone. Revocation: a generation whose pinned key set excludes a
  compromised key refuses its signatures; because downgrades are
  refused, revocation takes effect with the next confirmed update
  and cannot be rolled back past.
- Signature verification is distinct from Secure Boot (the images
  remain unsigned for firmware purposes) and from reproducible-build
  claims (none are made).

## Migration compatibility

Metadata carries `state_format` (the STATE layout version the
generation writes) and `min_reader_state_format` (the oldest STATE
format the generation can read). Rules, checked at stage time and
again by the candidate at first boot:

- A generation may be staged only if it can read the current STATE
  format and its own writes remain readable by the confirmed
  generation (`candidate.min_reader_state_format <=
  confirmed.state_format` and vice versa) — i.e. **rollback must
  remain safe after the candidate has run**, not just before.
- If a candidate would raise STATE to a format the confirmed
  generation cannot read, staging is refused unless the metadata
  also declares `rollback_breaking: true`, which the updater always
  refuses in this milestone (the field exists so the refusal is
  explicit, not silent).
- Credentials are never migrated by an update: the credential store
  format is generation-independent, and a generation that cannot
  parse it fails health confirmation and falls back.

## Both slots unusable

If neither slot passes its digest check at boot-selection time,
there is no automatic choice to make: the firmware's fallback path
boots the recovery-status UKI from the ESP (read-only diagnostics,
ADR 0010 tier A). STATE and DATA are untouched by every failure
above, so the recoverable outcome is: diagnose from recovery, then
re-stage a known-good generation into a slot from local media (the
same verified stage path, driven from the recovery environment in a
later milestone) — credentials, home, settings, and history survive
because they were never inside a slot. Interactive installed-system
recovery beyond diagnostics remains ADR 0010's open program; this
design does not claim it.

## Fixtures vs installed operations

`tools/ab_vm_update.py` remains a host fixture. The transaction core
specified here is implemented once in
`tools/ab_update.py` (schema v2: pinned trust, validity window,
migration window, history, owner rollback, both-slots outcome) with
host tests, and mirrored in the guest by the update service and the
early-init accounting hook, which are separate code held to the same
record schema (`synveil.ab-control/v2`). Host-fixture results are
never presented as guest boot evidence; the QEMU proof (real
two-slot disk, real boots) is its own record under
`docs/validation/`.
