# META MUSE — SYNVEIL FIRST-BOOT DESKTOP DEVELOPMENT HANDOFF

**PRIORITY: CRITICAL — BEGIN IMPLEMENTATION IMMEDIATELY**

**Active project:** `projects/synveil/`
**Target repository:** `magicmantheace/shiny-dollop`
**Prepared branch:** `synveil/first-boot-desktop-muse`
**Imported source:** `magicmantheace/Synveil`, branch `development/first-boot-desktop`
**Pinned source commit:** `318a5c90ed20d13b86dc95f21c8e341099699584`
**Original upstream work:** Synveil PR #38 (unmerged in upstream at the time of import)
**Date:** 2026-10-23 (America/Edmonton)

## 1. Owner directive

Continue building Synveil into a **genuinely bootable, usable, and updateable operating system**, with a real authenticated, multiwindow graphical desktop. Target the earliest safe owner hardware test as soon as verified technical gates permit.

Work immediately on production code, integration and tests, not only planning.

**The immediate order of work is:**
1. Real desktop on the native Synveil image (not a framebuffer menu or only a Debian/XFCE experiment).
2. Secure first-user enrollment, PAM/seat-equivalent authentication and safe non-root desktop session.
3. Persistent, independent user/state storage and durable reboot/relogin.
4. Safe, explicit installer to a separately authorized external SSD with isolated EFI/system A/system B/data/recovery layout.
5. Signed inactive-slot image updates, rollback and recovery, including interrupted-update tests.
6. Graphical update controls and owner-ready first physical-boot documentation/artifact preparation.

**DO NOT divert into** new AI integration, AthenZ/Developmental-AI coupling, observers/telemetry expansion, optimizers, gaming applications, app store or unrelated infrastructure. Preserve existing work.

## 2. Scope and source of truth

Read **repository-root `AGENTS.md` first**, then this project's `AGENTS.md`, `README.md`, `ROADMAP.md`, `docs/VALIDATION.md`, `docs/FIRST_INSTALL.md`, `docs/adr/0013-first-boot-desktop-priority.md`, and the relevant desktop, native-core, security and boot architecture docs. Root workspace isolation rules take precedence if they conflict.

All implementation changes, tools, tests and artifacts must stay under `projects/synveil/`. Do not modify any other project, including the Universal Game Launcher, Crawl Spectator Desktop or the parked GitHub Command Center. Do not modify the standalone `magicmantheace/Synveil` repository. Do not create root build manifests or workflows.

The imported 363 original files match the exact pinned source commit's Git blob identities and executable modes. The source `.github/workflows` is now **nested** under `projects/synveil/` and does not execute as GitHub Actions for `shiny-dollop`; do not claim its CI is running. Root workflow changes require explicit owner approval.

Do not alter the existing native source-lock/reproducibility checks merely to make a test green. If Git root/commit identity or checkout path changes in the monorepo, adapt tooling transparently and add regression coverage without weakening provenance or supply-chain controls.

## 3. Current state: avoid false completion claims

At the pinned source revision, existing code and validation evidence include an independently built Synveil UEFI bootstrap/native image, native authenticated framebuffer prototypes, native Wayland/Weston work, and a separate disposable Debian/XFCE integration image that passed real UEFI/QEMU multiwindow behavior and test-profile authentication. The upstream project records more specific results in `docs/VALIDATION.md`.

These are **not interchangeable proofs**. The Debian/XFCE QEMU multiwindow guest is not a production-native, securely installed Synveil desktop. A framebuffer dashboard and a Files tile are not a compositor. No owner-verified physical USB boot, production-safe external SSD installer, fully validated A/B updater, or signed release is established by this imported snapshot.

Treat upstream evidence as historical. Tests must be run anew or clearly labeled **not rerun** in this different repository/commit/environment.

## 4. Immediate implementation plan

**Stage A — Baseline and environment.** Inspect the imported code and latest checkable gates; run fast static/unit/build checks. Diagnose native Weston/Wayland, seat broker, display/login, input, graphics, persistence and launch paths. Define minimal next runnable vertical slice and record exact commands, outputs, environment, and failures.

**Stage B — Native multiwindow desktop.** Connect an established compositor (Weston and software-rendered fallback preferred per ADR 0013) to the native image. Show a real panel/launcher, movable/resizable independent terminal, file manager and settings windows. Preserve virtual terminal switching, keyboard and mouse, usable window focus, logout/relogin and software-rendered fallback. The existing Debian/XFCE experiment can serve as an isolated reference/control but is not the release deliverable. Ensure a familiar Windows-like navigation model using original Synveil branding, not copied Windows assets.

**Stage C — Authentication and persistence.** Build real non-root first-user onboarding without baked secrets or demo passwords. Reject incorrect credentials. Enforce session revocation and display-lock/relogin. Prove an independent second cold boot preserves credentials, configuration and the user's home files, while the immutable system remains separate. Keep developer serial/root test fixtures isolated from production artifacts.

**Stage D — Install and owner hardware readiness.** Prepare a non-destructive, offline artifact/image for UEFI x86_64. The supported target is HP Pavilion TG01, Intel i5-10400F, NVIDIA RTX 3060 12 GB, 32 GB RAM, UEFI; initial GOP/simpleDRM without accelerated NVIDIA is acceptable. USB HID, NVMe/AHCI and removable media must be validated. Disk-selection/partition plans must be read-only previews or disposable QEMU storage until the owner gives separate explicit authorization for a specific target disk. **Never write to the Windows system disk, change firmware security settings or modify boot configuration without authorization.** Include independent recovery.

**Stage E — A/B updates and rollback.** Implement a verified manifest/signature trust anchor, inactive-slot staging, digest and signature validation, PARTUUID-bound layout, durable commit/boot-attempt accounting, bounded health checks, interrupted-write simulation, successful activation and automatic/manual rollback while preserving the data partition. Reject invalid, unsigned, stale or incomplete updates. Exercise all transitions on **disposable** VM disks before any hardware update.

**Stage F — Graphical controls and delivery.** Provide usable desktop update status, preview, approval, progress, restart, history, and rollback, with truthful error states. Package reproducible test artifacts, checksums, recovery steps and first-boot instructions. Do not falsely call an experimental unsigned VM image an install-ready release.

## 5. Acceptance gates (must be demonstrated)

- QEMU UEFI boots the actual native Synveil image into a usable multiwindow graphical desktop with working keyboard and pointer.
- A new human account can enroll securely, log in as non-root, lock/logout, reject a bad password and reauthenticate.
- Two independent cold boots demonstrate persisted credentials, home files and settings; recorded evidence binds to the exact tested commit.
- An image can be installed to disposable A/B/data/recovery disks with verified identities and no Windows host-disk writes.
- Signed image update stages to the inactive slot; corruption, interruption, bad signatures and failed boot trigger safe rejection or rollback while retaining persistent data.
- Recovery works when the compositor, AI services, current slot or update flow fails.
- Graphical update controls perform real supported operations against approved test targets rather than mock data.
- Owner physical hardware compatibility is *unverified* until the owner participates; do not invent that validation.

## 6. Execution and Git discipline

Use this prepared `synveil/first-boot-desktop-muse` branch as the working starting point, or a properly derived `synveil/*` implementation branch. Check the live destination branch before every push; never force-push or overwrite another worker's changes. Commit verified, focused vertical slices and open/update a reviewable PR. Leave PRs unmerged until owner approval.

Build and run relevant Python/static/Rust/native/UEFI QEMU tests using supported local tooling. Existing upstream workflows copied to a nested `.github` directory are documentation only until separate CI setup is authorized.

Maintain `docs/IMPORT_PROVENANCE.md` and an implementation status log in this project, clearly separating implemented, validated, blocked and owner-hardware-only stages.

**Start coding now.** Prioritize the earliest unfinished native desktop/Wayland integration gate, not more telemetry or architectural rewrites. Proceed through subsequent dependencies when a vertical slice passes. Report commits, test evidence, blockers and next task; do not promise background work or claim success without verification.
