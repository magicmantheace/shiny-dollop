# Mesa/Vulkan Fold-In onto the Desktop Branch

Evidence for folding the graphics staging branch into
`synveil/first-boot-desktop-muse`: the Mesa + Vulkan
software stack (ADR 0027), originally proven in a separate
staging worktree at `3015ef6`, now lands on the desktop
branch alongside the S4 shell polish, and the **full
joined acceptance sweep** was re-run against the folded
images — joined, shell, Wine + graphics probe, observe,
audit v2, and the A/B update gate. The browser/files gate
was attempted four times and is **not** re-demonstrated to
completion in this environment; see its section below for
the full account.

## Fold mechanics

- `git merge --no-ff synveil/mesa-vulkan-staging` (tip
  `7ba1f48`) into `synveil/first-boot-desktop-muse` (was
  `1c79376`) → merge commit
  `11155998322c86749add1fd9ec14683eb9cdc8e8`. Merge-base
  was `3ce1cf1`. A merge, not a cherry-pick: the staging
  branch's three commits carry evidence bound to their
  SHAs, and the merge preserves that provenance.
- **Zero conflicts** (ort strategy). The only overlapping
  file was `tools/qmp_input.py`, auto-merged cleanly and
  verified: both the desktop branch's observe-history
  socket-wait fix and staging's `gfx-probe` command are
  present.
- 15 files, +1916/−25 — all graphics / userspace / docs /
  tests (distro graphics stage builders, the Wine weave,
  the guest probe, ADR 0027, the staging evidence bundle).
- **Frozen zone (ADR 0023) untouched:** no kernel, init,
  slot-selection / attempt-accounting, health /
  owner-confirm / rollback, update-transaction /
  signature-verification, or supervision / session files
  appear in the diff. The payload remains userspace
  through the existing mechanisms, as designed.

## Host tests

- `cargo test --workspace --all-targets --locked
  --offline`: **230 passed, 0 failed** (veil-core lib 193,
  synctl 10, veil-protocol 10, integration 17) — the same
  count as the polish pass; the fold changes no Rust.
- qmp-input host fixtures: **16 tests OK**.
- Pre-existing, unrelated: `cargo fmt --all --check`
  reports diffs in veil-core `audit.rs` / `audit_check.rs`
  (format drift under the 1.99 rustfmt). The fold touches
  no Rust; the drift was left as-is rather than
  reformatting unrelated files.

## Images

- Graphics stage rebuilt on the folded branch
  (`stage-validation.json`): marker
  `SYNVEIL_DISTRO_GRAPHICS_STAGED_NOT_BOOTED`, Mesa
  25.0.7-2+deb13u1, 54 pinned packages, **97 payload
  files, 220,473,743 bytes**, lavapipe + llvmpipe
  present. The stage `validation.json` and `assets.json`
  are **byte-identical** to the staging worktree's.
- Joined image (`joined-validation.json`): sha256
  `4c72d9c3719f7639633e1804ba62c625dc17e22daab9ae0ab59a454a094a6403`.
  Its component hashes — native_app `d047df0d…`,
  update_gui `eae26561…`, files_window `653d2994…`,
  component_assets `3e2f60c1…` — are **identical to the
  polish image** (`5cb40092…`); only the whole-image hash
  differs, because the kernel/initramfs rebuild binds the
  new commit. The fold changes no joined-image userspace,
  exactly as ADR 0027 predicted.
- Wine + graphics proof image (`image-validation.json`):
  sha256
  `c31a9c9eab866db4baf54df972fbe2bf1dd130366996015bf4b53795cd3e33e5`
  (1,152 MiB), source commit `1115599`. Graphics weave
  numbers identical to the staging run: 61 files copied,
  36 byte-identical to baseline, 29 link-checked;
  stage_validation_sha256 `70309b05…`.

## Gates (all run as `svrunner`, QEMU/TCG)

- **Joined:** `SYNVEIL_NATIVE_JOINED_QEMU_ENROLL_LOGIN_WESTON_PASS`,
  attempt 1.
- **Shell:** `SYNVEIL_SHELL_QEMU_PASS` (`shell-result.json`,
  `passed=true` on image `4c72d9c3…`) — including the
  polish assertions: drawn menu icons, tray network
  present-but-down, update slot hidden, minimize/restore,
  menu launch, relock.
- **Wine + graphics:** `SYNVEIL_WINE_QEMU_PASS`,
  attempt 1 (`result.json`, schema
  `synveil.wine-acceptance/v1`, `passed=true`,
  `probe_ok=true`). Notepad rect (513, 61, 731, 498),
  task buttons 0→4, typed pixel diff 550 — all matching
  the staging run.
- **Observe:** `SYNVEIL_OBSERVE_QEMU_PASS`
  (`observe-result.json`: `passed=true`, `attempts=2`).
  Attempt history, kept whole: run 1 failed (attempt 1
  reached history then stalled awaiting relock; attempts
  2–3 failed at graphical-auth-denied), run 2 was killed
  mid-flight by a host VM/runtime restart, run 3 failed
  fast at auth-denied, run 4 passed on attempt 2.
  Assessment: a load-dependent harness flake, not a fold
  regression — during runs 1–3 the host (1.5 shared CPUs)
  was saturated by an unrelated test suite (load average
  ~2.9), the observe harness runs the longest typed
  sequences of any gate and is the most timing-sensitive,
  its historical aggregation pass also needed 2 attempts,
  and the joined and shell gates had passed the identical
  enroll/login/relock flow on the
  byte-identical-userspace image immediately before.
- **Audit v2:** `SYNVEIL_AUDIT_V2_NATIVE_PASS`. (The
  first attempt died on a host file permission —
  `svrunner` could not execute the root-built
  `target/debug/veil-audit`; fixed with `chmod a+rx`.)
- **A/B update:** `SYNVEIL_AB_QEMU_PROOF_PASS`
  (`ab-build-receipt.json`, `ab-smoke-receipt.json`):
  all nine scenarios pass — S0-provision-enroll,
  S1-stage-v2, S2-trial-v2-confirmed,
  S3-owner-rollback-v1, S4-failing-candidate-fallback,
  S5-invalid-signature-refused, S6-interrupted-stage,
  S6b-stage-after-interrupt,
  S7-corrupt-slots-fail-closed — with
  `gate_violations: []`. Generations: v1 `62b9817e…`,
  v2 `dcd74a48…`, v3 `c4f18196…`; publisher
  `synveil-dev-2026-01` (development key, as expected).
  Attempt 1 failed at S1 on host file permissions
  (QEMU could not open the root-built
  `release-v2.img`, mode 660); fixed with `chmod -R a+rX`
  and re-run clean. S4 logged one login-type retry,
  absorbed by the harness's own retry.

## Probe report (in-guest, firsthand, folded image)

```text
GFX_PROBE_START
GFX_VULKAN_DEVICE name="llvmpipe (LLVM 19.1.7, 128 bits)" type=4 api=1.4.305
GFX_VULKAN_OK devices=1 driver=lavapipe
GFX_EGL_OK vendor="Mesa Project" version="1.5"
GFX_GL_OK vendor="Mesa" renderer="llvmpipe (LLVM 19.1.7, 128 bits)" version="4.5 (Compatibility Profile) Mesa 25.0.7-2+deb13u1"
GFX_PROBE_OK
```

(The `libEGL warning: DRI2 / /dev/dri/card0` lines in the
raw probe log are the expected surfaceless-platform
fallback noise, unchanged from the staging proof.)

## Browser/files gate — not re-demonstrated here

The browser proof disk was rebuilt from the folded tree
(`browser-build-receipt.json`, source `1115599`;
generations `c1ff9b68…` / `08680a36…` / `1de54649…`),
and the gate (`tests/smoke-native-browser.py`) was run
four times:

- **Runs 1–2 progressed deep on the folded disk** — page
  proofs, payload downloads, update staging and rollback
  phases all executed — but neither reached a receipt:
  run 1 was killed mid-boot by a host VM/runtime restart;
  run 2 was stopped by the operator's 60-minute wrapper
  while still progressing.
- **Runs 3–4 failed** (`browser-receipt-run3.json`,
  `browser-receipt-run4.json`: `demonstrated=false`) with
  the harness's wall-clock waits expiring under sustained
  host load (~2.2–2.5 average on 1.5 shared CPUs). The
  guest-side evidence shows the image behaving correctly:
  run 4's guest serial logs carry the full readiness
  sequence — `SYNVEIL_NETWORK_READY`,
  `SYNVEIL_DISPLAY_READY`, confirmed boot on slot A /
  generation v1 — in every boot, and run 3's in-guest
  Chromium netlog shows the browser up; the harness
  recorded the markers as unseen after its waits lapsed.
  No guest, fixture, or product fault was identified.

The gate's last **full** pass remains the polish
lineage's — 2026-11-09, source `04d5ec4`,
`demonstrated=true` (`browser-receipt-polish-04d5ec4.json`,
included for reference). Re-running this gate on the
folded lineage under an uncontended host remains open;
nothing in the fold changes the browser image's inputs
beyond the rebuilt-from-source generations.

## Proven

- The fold is mechanical and conflict-free; the frozen
  zone is untouched; provenance of the staging evidence
  is preserved in history.
- The sealed Mesa/Vulkan payload is byte-identical to
  the staging seal and present, byte-verified, in the
  folded Wine proof image.
- Vulkan (lavapipe, API 1.4.305) and OpenGL 4.5 / EGL 1.5
  (llvmpipe) initialize in the guest on the folded
  branch, under QEMU/TCG (software rendering).
- The full joined acceptance on the folded images:
  joined enroll/login/Weston, the S4 shell with its
  polish assertions, Wine GDI behaviour, observe with
  history aggregation, audit v2, and the A/B update
  proof (all nine scenarios, zero gate violations) —
  the update machinery is unregressed with the graphics
  payload on the branch.

## Not proven / not claimed

- The browser/files gate end-to-end on the folded
  lineage (see above); it stands proven on the polish
  lineage at `04d5ec4`.
- No Direct3D: DXVK / vkd3d-proton are **not** staged —
  this payload is their prerequisite, not their proof.
- No game or 3D workload of any kind was run.
- No real-GPU behaviour or performance: everything above
  is CPU software rendering under QEMU/TCG.
- No 32-bit graphics stack (the payload is x86_64 only).
- No physical hardware validation (TG01 untested; the
  ADR 0023 park is unchanged).
