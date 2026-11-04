# Drabbit Pet — Test Plan

## P1 — pet brain (`core/`)

Automated: vitest suite in `core/tests/`, run with
`npm --prefix core test`. All times are simulated timestamps; no test
touches a real clock.

| Area | Coverage |
| --- | --- |
| Decay math | Needs after known intervals match PET_DESIGN rates per stage; asleep modifiers (energy regen, 30% other decay); clamping at 0/100. |
| Determinism / offline catch-up | Advancing 24 h in one jump, in 1 h chunks, and in 1 min ticks produces byte-identical serialized state. Same inputs → byte-identical `serialize` output across runs. |
| Egg | No needs decay in egg; `readyToHatch` at exactly 10 min; `hatch` before ready throws; hatch sets baby state and hatch values. |
| Stage transitions | baby→child at 1 h, child→teen at 7 h, teen→adult at 19 h of age, each with a `stage` event. |
| Actions | feed (meal/snack effects, clamping, overfeed penalty, snack-on-full care penalty), play (effects + energy precondition), clean (messes cleared, cleanliness restored), sleep/wake (incl. auto-sleep on exhaustion, auto-wake when rested), medicine (cures sickness; throws when healthy). Invalid-stage and asleep rejections throw typed errors. |
| Sickness | Onset occurs under at-risk conditions (deterministic roll for a fixed pet id); sickness health drain; medicine cure restores and logs `cured`. |
| Messes | Mess events occur over a long awake window for a fixed pet id; mess drops cleanliness by 8; clean removes them. |
| Death & rebirth | Total neglect kills within days, records cause and `died` event; acting on a dead pet throws; `startNewEgg` archives the ancestor, increments generation, returns a fresh egg. |
| Adult forms | careScore forced into each band (≥70 / 40–69 / <40) at the teen→adult transition yields radiant / content / scruffy. |
| Persistence | serialize→parse→serialize round-trip is byte-identical; parse rejects garbage and unknown future schema versions; envelope carries lineage. |
| Demo | `npm --prefix core run demo` runs a scripted egg→adult lifecycle with periodic care and prints a readable diary; must exit 0. (Manual check, not a unit test.) |

## P2 — desktop pet (planned)

- Unit: state→sprite-state mapping, care panel wiring against core.
- Headless build on the VM (`npm run build` / package smoke).
- **Owner-PC only:** transparent window behaviour, perch rendering,
  tray, always-on-top, multi-monitor — never claimed from VM runs.

## P3 — companion server (planned)

- Headless integration tests (server + core, no Electron): missing /
  wrong token → 401; status shape matches DESIGN; a remote feed
  action mutates the one shared pet state; events endpoint honours
  `since`.
- **Owner-side only:** real LAN/Tailscale reachability from the phone.

## P4 — Android app (planned)

- Unit tests for client/state logic (status parsing, error states,
  action request building).
- APK build only if an Android SDK exists on the build machine;
  otherwise recorded as owner-PC / Android Studio verification.
- **Owner-device only:** pairing against the real desktop server,
  UI behaviour on a physical phone.

## Honesty rule

A test counts as evidence only for the layer it runs on. VM test
results never stand in for Windows desktop or Android device
behaviour; MUSE_HANDOFF.md records the split for every slice.
