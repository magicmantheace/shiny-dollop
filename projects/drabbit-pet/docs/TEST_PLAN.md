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
| Visual state | state→animation mapping (egg/egg-ready/idle/sleeping/sick/dead), transient eating/playing from events, resolution priority (base > transient > hopping > idle); bridge reactions add a bubble-only transient except `celebrate`, which maps to the playing bounce. |
| Bridge link | `desktop/tests/bridge-link.test.ts` (12): display-state parsing (junk/missing state → null, optional fields tolerated); reaction mapping (busy states + celebrate react, alert reacts even on first sighting, repeats/connecting/first-sighting calm stay quiet, busy→idle relaxes, alert→idle says "All clear"); the polling service against an injected reader + fake scheduler (reacts on change only; missing/corrupt file is a quiet no-op and recovery works; start/stop wiring); env-override path priority. |
| Build + smoke | `npm run build` clean (core tsc, main/preload tsc strict, Vite production build of both windows). `npm run smoke`: the real Electron binary launches under Xvfb, creates a fresh save in a throwaway userData, and loads both windows (`SMOKE_OK`). |
| **Owner-PC only** | Transparent window behaviour, perching/roaming feel on a real desktop, tray, always-on-top over real windows, multi-monitor, high-DPI — never claimed from VM runs. |

**Bridge link — owner-PC verification (2026-11-05):** the desktop
suite on the VM is **63 tests** (bridge-link 12 + visual-state 6
included) with core unchanged at 46. On the owner's PC the built
app was run with an isolated throwaway profile and
`DRABBIT_BRIDGE_STATE_FILE` pointed at a staged state file: the pet
window (PrintWindow capture) showed **no bubble** at an idle first
sighting, **"Pip is watching Muse work"** after the file flipped
to `working`, and **"⚠ Muse needs attention on the PC"** after a
flip to `alert`. The owner's real pet save was not touched. Live
pairing against the real bridge state file begins whenever the
bridge's production form is the GUI supervisor (owner's call);
until then the file simply doesn't exist and the link stays quiet.

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

## P4 — Android app (`android/app/src/test/`)

JVM unit tests (JUnit 4), run with `./gradlew :app:testDebugUnitTest`
in Android Studio. The build VM has **no JDK/Android SDK**, so in
this environment the suite ships as sources (status below) and the
wire contract is covered by the fixture evidence instead.

| Area | Coverage |
| --- | --- |
| Client parsing (fixtures) | Status parsing for baby / egg-ready / dead summaries captured from the real P3 server (exact field values, null adultForm/deathCause handling); hatch + feed-meal action outcomes (summary + events); request shape asserted (URL, `Authorization: Bearer`, `{kind}` body in the panel vocabulary). |
| Error mapping | 401 → BadToken, 403 → DesktopOnly, 409 → StateError (server code + message verbatim), 404/500 → ServerError, transport IOException → Unreachable, non-JSON or pet-less 200 → MalformedResponse. Error fixtures are the server's real error bodies. |
| Events cursor | Bootstrap (no `since` sent) → empty + cursor; delta returns only the new event and advances the cursor; caught-up returns empty with the same cursor; `since=0` returns the whole retained window. |
| CareRules matrix | Awake baby: core actions enabled, wake/medicine disabled with the core's reasons; asleep: wake + clean enabled (core allows clean asleep), feed/play disabled; sick: medicine enabled, even asleep; energy below the core's play floor (10) disables play; egg: only hatch, gated on readyToHatch; dead: everything disabled; NEW_EGG never offered in any state. |
| Settings | `ConnectionSettings.normalize` (scheme/whitespace stripping, port fallback to 8931, range checks), completeness, baseUrl building. (SettingsStore's SharedPreferences read/write is Android-runtime only.) |
| Formatting | Age strings at minute/hour/day boundaries; stage labels. |
| **Ran on this VM** | The **fixtures themselves**: 13 raw responses captured over real HTTP from the compiled P3 server (Node, temp-dir PetService, dummy token), plus an independent strict shape validation (exact key sets/types, cursor semantics, error codes) — all passing. The Kotlin suite has **not** been executed (no JDK); first run is owner-side in Android Studio. |
| **Owner-device only** | Gradle build + the test run above, install on the Pixel 9a, pairing against the real desktop server, UI behaviour on a physical phone. |

## Honesty rule

A test counts as evidence only for the layer it runs on. VM test
results never stand in for Windows desktop or Android device
behaviour; MUSE_HANDOFF.md records the split for every slice.
