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

## P2 — desktop pet (`desktop/`)

Automated: vitest suites in `desktop/tests/`, run with
`npm --prefix desktop test`. The Electron-free modules are the test
surface; the GUI itself is not faked in tests.

| Area | Coverage |
| --- | --- |
| Save store | Round-trip byte-identical; missing file → fresh; corrupt file → recovery with the corrupt bytes preserved at the renamed-aside path and a fresh egg returned; valid-JSON/invalid-shape also recovers; atomic write leaves no `.tmp`. |
| Tick service | Fresh egg persisted once at startup; a tick that changes nothing writes nothing; crossing the incubation boundary persists and emits `egg_ready`; scheduler wiring (5 s default, start/stop, no double-schedule); a dead pet is never advanced or persisted; `onChanged` fires only on change. |
| Roaming planner | Bounds respected under adversarial randomness (always-right / scripted-left), out-of-bounds starts clamped; never moves while asleep, panel-open, paused, an egg, or dead; hop → arrive exactly on target → sit; sit bias gives long idle sits. |
| IPC action mapping | Payload validation accepts all nine UI kinds and rejects malformed payloads (`bad_payload`); each kind maps to the right core action with exact need deltas (snack +8, meal +35/clamp, play −7 energy…); wrong-stage/state actions raise the core's typed errors (`not_ready`, `asleep`, `not_sick`, `not_dead`, `is_egg`); clean is allowed while asleep; medicine cures an injected sick pet; new-egg starts generation 2. |
| Visual state | state→animation mapping (egg/egg-ready/idle/sleeping/sick/dead), transient eating/playing from events, resolution priority (base > transient > hopping > idle). |
| Build + smoke | `npm run build` clean (core tsc, main/preload tsc strict, Vite production build of both windows). `npm run smoke`: the real Electron binary launches under Xvfb, creates a fresh save in a throwaway userData, and loads both windows (`SMOKE_OK`). |
| **Owner-PC only** | Transparent window behaviour, perching/roaming feel on a real desktop, tray, always-on-top over real windows, multi-monitor, high-DPI — never claimed from VM runs. |

## P3 — companion server (`desktop/tests/companion-*.test.ts`)

Automated: vitest suites driving the **real HTTP server** on
ephemeral ports against a temp-dir PetService — no Electron, no
mocked transport. Run with `npm --prefix desktop test` (21 tests).

| Area | Coverage |
| --- | --- |
| Config store | Missing file → defaults (disabled, nothing written); save/load round-trip with no `.tmp` left; corrupt JSON and invalid shape → renamed-aside recovery with bytes preserved; injected in-memory fs works; token generator is long, url-safe, unique. |
| Auth | No token and wrong token → 401 `unauthorized`; stats count requests + auth failures and record last client + start time. Token comparison is constant-time. |
| Status | 200 with `{ ok, serverNow, pet }`; pet key set matches PetSummary exactly; values match the service's state. |
| Remote actions | A remote feed-meal mutates the one shared state (the IPC door sees the same pet) and its response equals the IPC dispatcher's outcome on a twin pet (summary deep-equal, same event kinds); wrong-stage medicine → 409 `not_sick`, byte-identical error to IPC; `new-egg` → 403 `desktop_only` even when the pet is dead, and starts nothing. |
| Events cursor | Bootstrap (no `since`) returns no events + the current cursor; after an action, `since=<cursor>` returns exactly the new events and a larger cursor; polling at the cursor returns empty; `since=0` returns the whole retained log incl. `hatched`; malformed `since` → 400 `bad_query`. |
| Protocol edges | Unknown routes inside and outside `/v1` → 404 `not_found`; non-JSON body → 400 `bad_json`; unknown kind → 400 `bad_payload`; body over 64 KB → 413 `too_large`; stop frees the port for a new server. |
| Service lifecycle | Starts disabled with no token; first enable mints the token and serves the real pet; regeneration makes the old token 401 immediately while the new one works; disable stops the server and frees the port; a port conflict lands in a panel-visible `error` state (EADDRINUSE) with the switch left on, and a retry after freeing the port succeeds. |
| **Owner-side only** | Real LAN/Tailscale reachability from a phone; Windows Firewall behaviour on first enable. Never claimed from VM runs. |

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
