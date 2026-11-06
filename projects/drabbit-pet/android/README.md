# android/ — Kotlin companion app (P4)

The phone half of Drabbit Pet: a thin client of the desktop pet's
companion server (protocol: `../docs/DESIGN.md`, as built in P3).
Kotlin + Jetpack Compose, a single `:app` module,
`applicationId = ca.wilkins.drabbit` (the owner's personal namespace —
rename freely, nothing in the protocol depends on it), minSdk 26,
compile/target SDK 35.

The app holds **no simulation and no authoritative pet state** — the
pet lives on the PC; the phone is a window onto it. Networking is
`HttpURLConnection` and JSON is `org.json` (both ship with Android),
so beyond AndroidX/Compose there are no third-party runtime
dependencies.

## What it does

- **Connect screen** — PC address (same Wi-Fi, or the PC's Tailscale
  address), port (default **8931**), pairing token. Saved settings
  prefill the form, and a complete saved connection is retried
  automatically on launch.
- **Pet screen** — the drabbit drawn with Compose Canvas in the same
  fur palette as the desktop (egg / sleeping / sick / gone states
  included), name/stage/mood/age/generation, the five need bars plus
  health and care score, a mess indicator, care buttons whose
  enabled state mirrors the core's own rules (`model/CareRules.kt`),
  and the recent-events list.
- **Polling** — while the pet screen is in the foreground it refreshes
  status + events every 15 s using the server's event cursor (first
  sync takes the retained window, then deltas), plus a manual
  Refresh. A failed poll keeps the last known state under a
  "PC offline" banner instead of blanking the pet.
- **Errors in plain language** — unreachable PC, rejected token,
  desktop-only action, and the server's own state refusals (e.g.
  "Not sick — medicine would just be mean.") are surfaced as-is or
  translated, never swallowed.
- **Deliberately absent** — "start a new egg". Beginning the next
  generation is a desktop-side decision; the server refuses it
  remotely with 403 `desktop_only`, and the app never offers it.

## Pairing walkthrough

1. On the PC, open the desktop pet's care panel → **Companion**
   section → turn the companion **on**. Note the address it shows and
   the pairing token (Show/Copy).
2. On the phone (same Wi-Fi as the PC, or Tailscale running so the
   PC's Tailscale address is reachable), open this app.
3. Enter the PC's address (LAN IP like `192.168.1.20`, or its
   Tailscale name/IP), port `8931`, and the token. Tap **Connect**.
4. The pet appears. The token is stored only in the app's private
   storage on the phone; if it is ever regenerated on the desktop,
   the app notices the 401 and returns to this form.

The companion speaks plain HTTP on your own network, gated by the
token — that's why the manifest sets `usesCleartextTraffic`. Don't
port-forward it to the internet; LAN/Tailscale is the intended reach.

## Building and running (owner's PC)

There is no Android SDK on the build VM (see Verification), so the
first build happens in **Android Studio** on the owner's PC:

1. Install Android Studio (it bundles JDK 17 + the Android SDK).
   Open this `android/` folder as the project and let it sync
   (SDK platform 35 will be offered/installed).
2. The repo ships `gradle/wrapper/gradle-wrapper.properties` but no
   wrapper JAR/scripts — they could not be generated on the VM
   (no JDK/Gradle there). Android Studio will offer to create the
   Gradle wrapper on first open; accept (or run
   `gradle wrapper --gradle-version 8.9` with any local Gradle 8.9).
3. Connect the Pixel 9a with USB debugging on (or use an emulator),
   press **Run ▶** — or **Build > Build App Bundle(s) / APK(s) >
   Build APK(s)** for an installable file.
4. Unit tests, once the wrapper exists: `./gradlew :app:testDebugUnitTest`.

## Verification (honest split, 2026-11-04)

**This VM has no JDK, no Android SDK, no Gradle** (`java`,
`sdkmanager`, `adb`, `kotlinc`, `gradle` all absent) — so the Gradle
build and the JVM unit tests were **not run** here. They ship as
complete sources, ready for the Android Studio build above.

What **was** verified here, against the real thing rather than the
paper protocol:

- The P3 companion server was booted headlessly in Node from the
  compiled `desktop/dist` over a temp-dir PetService with a dummy
  token, and driven over real HTTP. **13 raw responses were captured
  verbatim as the unit tests' fixtures**
  (`app/src/test/resources/fixtures/`): egg-ready and baby status,
  hatch and feed-meal action responses, the events bootstrap / delta /
  caught-up / full-window pages, a dead pet's status, and the 401 /
  403 `desktop_only` / 409 `not_sick` / 404 error bodies.
- An independent shape check (Python, strict key sets + types) passed
  on all 13 fixtures: the PetSummary key set matches
  `desktop/src/shared/summary.ts` exactly (16 fields), event objects
  are `{t, kind, detail}`, cursor semantics are the documented count
  cursor (bootstrap 4 → delta 5 → caught-up empty).
- The Kotlin sources passed a delimiter-balance smoke check. That is
  **not** a compile — the first real compile is the Android Studio
  sync on the owner's PC, and any fallout from it is P4 follow-up,
  not a surprise to hide.

**Owner-device only, still open:** the Gradle build itself, the JVM
unit tests running green, install on the Pixel 9a, first real pairing
against the desktop over LAN/Tailscale, and the UI's behaviour on a
physical phone.

## Layout

| Path | Contents |
| --- | --- |
| `app/src/main/java/ca/wilkins/drabbit/net/` | `HttpTransport` (interface + `HttpURLConnection` impl), `DrabbitClient` (protocol + error mapping), `DrabbitError` |
| `.../model/` | `PetSummary`/`PetEvent` wire model, `WireParsing` (org.json), `CareRules` (button rules mirroring the core), `Format` |
| `.../data/` | `ConnectionSettings` (normalization) + `SettingsStore` (SharedPreferences) |
| `.../ui/` | `PetViewModel` (session, 15 s polling, actions), Connect + Pet screens, `DrabbitCanvas`, theme |
| `app/src/test/` | JVM unit tests: client parsing + error mapping over the captured fixtures, events cursor, CareRules matrix, settings normalization, age formatting |
