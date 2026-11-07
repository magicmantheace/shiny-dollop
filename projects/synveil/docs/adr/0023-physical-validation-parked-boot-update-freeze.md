# ADR 0023: Physical validation parked by owner decision; boot and update mechanisms frozen

- Status: Accepted
- Date: 2026-11-05
- Supersedes: none. ADR 0013 remains Accepted; this ADR parks the
  physical remainder of its priority gate and lifts its deferral of
  later-phase work for QEMU-scoped development. It does not mark any
  ADR 0013 item complete.
- Superseded by: none
- Related: [ADR 0013](0013-first-boot-desktop-priority.md)
  (first-boot desktop priority),
  [ADR 0022](0022-weston-subsurface-assert-and-pixbuf-data.md)
  (the fixpass package this decision freezes around),
  `docs/AB_UPDATER.md`, `docs/PHYSICAL_BOOT.md`,
  `docs/FIRST_INSTALL.md`, `docs/VALIDATION.md`, `ROADMAP.md`.

## Context

ADR 0013 (2026-10-20) made a physical UEFI-bootable multiwindow
desktop with persistent A/B slots, signed whole-image updates,
health-checked rollback, and graphical update controls the critical
priority, and deferred observer, policy, evaluator, and AthenZ work
until those gates met acceptance.

That programme is complete at the QEMU-demonstrated level:

- The native Weston desktop provides owner enrollment, authenticated
  login, terminal, files, settings, and Chromium on the source-built
  image.
- The A/B updater (`docs/AB_UPDATER.md`) selects slots inside
  Synveil's own boot path with no firmware-variable writes, accounts
  boot attempts before control transfer, and confirms updates with
  the two-key (health + owner) rule. Graphical update controls drive
  stage, trial reboot, confirm, and rollback.
- On 2026-11-04 the full sequence was exercised on the owner's
  machine (HP Pavilion TG01) under QEMU 11.1 / WHPX against the
  ADR 0022 fixpass package (source `a236213`, image SHA-256
  `f45a79c3bdf0690b3670ef0971f0457e5511d4a1e659724b05d45c8bea767f38`):
  enrollment and login, multi-session desktop soak, and the complete
  update round trip — stage v2, trial boot, confirm v2, cold-boot
  persistence, rollback to v1 slot A, confirm v1.

What remains open under ADR 0013's literal gate is exclusively
physical:

- Physical UEFI USB boot on the TG01, owner validated.
- Installation onto a dedicated external SSD with isolated A/B
  slots and persistent data.
- Interrupted-update and power-loss behaviour on real media.
- Physical validation of the desktop/login item above.

On 2026-11-05 the owner directed that the physical side be parked,
asked what development would look like without it, and approved the
arrangement recorded here. The owner also accepted the stated cost:
hardware unknowns (TG01 firmware behaviour, the RTX 3060 display
path — the desktop has only rendered on virtual GPUs — and
real-media write/power behaviour) remain undiscovered, and the
failure-search space grows with every subsystem built meanwhile.
The freeze below caps the boot/update portion of that cost.

## Decision

1. **Physical validation is PARKED.** The four physical items
   listed in Context are parked by owner decision: not complete,
   not abandoned. They keep their unchecked state in `ROADMAP.md`,
   annotated as parked under this ADR. No claim of physical boot,
   physical installation, or real-media update behaviour may be
   made; all validation claims remain QEMU-scoped, per
   `docs/VALIDATION.md`. The mandatory gates in
   `docs/PHYSICAL_BOOT.md` remain in force for any future unparking.

2. **Boot and update mechanisms are FROZEN** at the fixpass state
   (source `a236213`; branch tip `aab9b27` at the time of this
   ADR). The frozen zone is:
   - kernel and boot configuration, and the ESP/bootloader
     arrangement;
   - the bootstrap `/init` and state-partition identity/mount
     behaviour (ADR 0017, ADR 0019);
   - slot selection and boot-attempt accounting;
   - trial-boot, health-check, owner-confirm, and rollback logic;
   - the update transaction, signature verification, and publisher
     trust handling in `docs/AB_UPDATER.md`;
   - the supervision and session infrastructure the desktop and
     services start through, and the graphical update controls'
     behaviour contract.

   A change inside the frozen zone requires the owner's explicit
   approval, and an approved change is not treated as validated
   until the full QEMU acceptance has been re-run and recorded:
   boot to the authenticated desktop plus the complete update
   round trip including rollback (the 2026-11-04 sequence).

3. **Payload is not frozen.** Userspace services and applications
   delivered through the existing supervision and session
   mechanisms may be added and evolved freely: the Phase 3
   observer, the Phase 4 policy/action engine, the Phase 5
   evaluator, and later the AthenZ resident service. Their state
   lives on the data partition under their own formats. Any
   payload change that alters the shipped image must pass the
   standing joined QEMU acceptance — boots to the authenticated
   desktop, update round trip green — before it is accepted, so
   the frozen mechanisms are continuously re-proven against the
   growing payload.

4. **Boot features stay parked with physical.** Work that is a
   boot feature by nature remains parked alongside the physical
   items: the Phase 11 recovery boot entry and AI-disabled safe
   mode, and any Phase 10 change to the update generation or slot
   scheme.

5. **AthenZ updates are a separate system.** A future AthenZ /
   developmental-AI candidate-update mechanism (Phase 6) is not
   the OS image updater. It may not reuse or modify the frozen
   updater, and anything it would need from the boot path inherits
   this freeze.

6. **Security exception.** The freeze is change control, not a
   prohibition on repair. A genuine defect inside the frozen zone
   (for example in signature verification or slot selection) may
   be fixed with the owner's approval, subject to Decision 2's
   re-validation requirement. The publisher key remains the
   flagged development key `synveil-dev-2026-01`; production key
   handling is part of the parked physical/install work.

7. **Working queue.** Development resumes at the earliest
   incomplete, non-parked dependency: completion of the Phase 2
   durable audit record format, then Phase 3 observer completion,
   then Phase 4, in roadmap order. PR #17 remains unmerged;
   nothing in this ADR authorizes a merge.

No firmware variables are written by this decision. No sandbox,
TLS, or connection behaviour changes.

## Consequences

- The boot/update system that eventually meets physical hardware
  is the exact mechanism set validated on 2026-11-04, no matter
  how much payload grows around it; Decision 3's acceptance
  re-runs keep that claim earned rather than assumed.
- Unparking remains available at any time by owner decision, at
  the cost recorded in Context. The parked items' acceptance
  evidence requirements are unchanged when that day comes.
- Claims discipline is unchanged: QEMU-demonstrated is the
  strongest claim any current Synveil capability may carry, and
  the roadmap's physical checkboxes stay unchecked until physical
  evidence exists.
