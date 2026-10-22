# Universal PC Game Launcher — product requirements

**Requirements baseline:** 2026-10-22  
**Target:** Windows 11 x64, single-user, offline-first desktop application.  
**Mission:** combine multiple PC game libraries into one fast, customizable home, safely launch owned/installed games, and track local play activity.

## Success definition

A user with Steam, Epic Games Launcher, Battle.net and locally installed executables should be able to use this as their primary **library and launch dashboard** rather than searching through many shortcuts. **Vendor clients may still be needed** for authentication, DRM, updates, multiplayer and game startup; this app must respect them. Never promise proprietary service integration without a viable documented or empirically validated local mechanism.

## Features, ordered by utility

### F1. Install/start application
- Modern, original Windows-style desktop UI with navigation: **Library**, **Recently Played**, **Favorites**, **Settings**.
- Works with local data even with no network; no account, subscriptions, adware or telemetry.
- Startup uses a local DB and presents clear empty/onboarding state; no fake game catalog.
- An easy-to-use Windows x64 installer and clean uninstall; app can run without admin rights after installation.

### F2. Library management (critical)
- **Add a Game** opens a real OS file picker and accepts an explicitly selected local `.exe` or validated `.lnk` target; choose working directory and optional launch arguments with safe, structured handling.
- Edit a game: display title, source, launch target, icon/cover, genre/tags, favorites, hidden, manual category and notes if straightforward.
- Remove from library **does not uninstall, delete or modify installed game files**. Confirmation must say that.
- Show a searchable library grid/list, sort by A–Z, added, last played and playtime; filter by source, favorites and installed/missing status.
- Prevent duplicates using a stable composite ID from source/installation ID (and canonical path where relevant), not only game title. Same game installed in two launchers may appear as separate playable entries; user can choose whether to group/alias later.
- On re-scan, preserve user metadata and historical play sessions; never silently resurrect explicitly excluded games.

### F3. Steam discovery and launching
- Auto-detect common Steam install locations and additional libraries using locally available configuration/manifests. Prefer documented or widely understood local formats; account for multiple drives.
- Read `libraryfolders.vdf` and installed `appmanifest_*.acf` defensively. Resolve game name, AppID and installation location when available; handle malformed, missing and partial manifests without crashing.
- Associate Steam title with installed AppID. Launch through **validated Steam `steam://rungameid/<appid>`** or another supported official mechanism, not direct invocation of protected games unless explicitly provided as manual game.
- Clearly indicate whether Steam is installed/reachable. Do not claim a launch succeeded simply because a protocol handoff returned.
- Don't require Steam Web API keys or credentials.

### F4. Epic Games discovery and launching
- Discover **local installed Epic Games Launcher manifest information** in appropriate Windows program-data locations. Handle absent, malformed and outdated manifests safely; parse only whitelisted fields needed for display and launch.
- Prefer a verified native Epic launcher deep-link scheme / documented integration to launch a selected installed item. Verify exact URI format in the implementation environment; do not invent app IDs or schemes.
- If reliable per-game launching is unavailable, show the game and provide a clearly labeled **Open Epic Games Launcher** fallback (not a misleading Play action). When user supplies and validates a local executable as a manual entry, support that separately.
- No scraping private accounts, no Epic credentials or unauthorized entitlement APIs.

### F5. Battle.net discovery and launching
- Best-effort local discovery from vendor-managed installation metadata and known installed game locations; keep support as an adapter with individually documented detection mechanisms.
- Some Blizzard/Activision titles may not have stable public game-specific deep links. Only implement direct launches verified on actual client installs; otherwise offer **Open Battle.net** and clear instructions/status.
- Do not parse credential files, bypass ownership, kill vendor launchers or make unsupported game-ID assumptions.
- UI must distinguish discovered-but-not-directly-launchable, missing-client and properly launchable entries; do not misreport completeness.

### F6. Artwork and customization
- Prefer game icons from local Windows shortcut/executable resources where available, or user-selected cover art.
- Online cover art optional and **opt-in**, with proper source/attribution/terms. No hotlinking unauthorized proprietary images as mandatory functionality.
- Cache scaled artwork locally, bound disk usage, handle absent covers with a tasteful placeholder.
- Theme toggle (dark/light/system), game card size/density where practical and keyboard focus states.

### F7. Launch and running state
- One clear Play button per launchable entry; verify path or native launcher availability before attempting.
- Manual entries use OS APIs with structured executable path and arguments, no unsanitized command-line string interpolation, no command shell.
- Vendor entries use validated protocol or vendor launch executable; accept explicit user action before opening vendor client.
- Show Launching, Running (when actually observed), Not detected, Failed or Unknown state accurately. Do not mislabel "URI sent" as "game is running".
- User can add optional preferred working directory/launch parameters; document risks; reject malformed or unsafe data.
- Never ask to run elevated, never patch or hook games, never inject processes, never read game memory. Respect anti-cheat constraints.

### F8. Playtime and recent sessions
- For **manual executable entries**, track time from process start until tracked child/executable exit when reliably observable. Stop session on exit and persist elapsed time; if child spawns another process, avoid falsely claiming continuous gameplay unless verified tracking exists.
- For vendor protocol launches, if process identity cannot be reliably correlated to the title, label session as **launch requested / tracking unavailable**; optionally allow user-maintained time/notes. Do not fake minutes.
- Track session source, start/end in UTC, duration and confidence/method (observed/manual/unavailable). Use monotonic elapsed-time within a process session for duration, correct for suspend/resume where feasible.
- Persist on restart/crash with session recovery markers; never convert abandoned pending sessions into fabricated multi-day playtime.
- Display total tracked time and last-played date only from defensible recorded sessions, with indicators when partial.
- Offer privacy option to disable tracking or clear history.

### F9. Settings / scans
- Per-source enable/disable; show detection method, discovery paths and last successful scan.
- Scan now button, selected-folder scan action and exclusion rules; no full-disk scanning by default.
- Rescans are idempotent; explain unavailable permission/parse errors.
- No autonomous downloads, installs, game updates, account sign-ins or cloud sync.
- Export/import JSON of **nonsecret library metadata and user prefs** (stretch but useful). Never export full local tokens (none required).
- Opt-in "minimize on launch" setting; never force-close store client.

## Honest MVP scope

**Must ship:** F1, F2, Steam (F3), Epic inventory with verified launch or honest fallback (F4), Battle.net best-effort inventory with fallback (F5), local artwork/custom covers (F6), safe launching (F7), trustworthy manual executable session tracking (F8), manual and source scans/settings (F9).

**Post-MVP only:** store account/cloud library lists, game installation or updates, achievements, cloud saves, per-title cross-store merging, rich multiplayer presence, controller-first ten-foot UI, streaming, account sync or store purchasing.

## UX details

- Game tiles show title, launcher source, installed/missing, favorite, appropriate Play/Open Launcher action and last played if known.
- Library empty state: "No games yet — Add a game or scan launchers".
- Vendor absent: "Steam/Epic/Battle.net not found on this PC" rather than silent failure.
- Offline state does not erase library; avoid sign-in requirements for our application.
- Errors offer retry, source-specific troubleshooting and actionable detail without exposing unrelated file paths/log secrets.
- UI remains responsive with 500+ entries; parse manifests off renderer thread, use pagination or virtualized grids where necessary.
- App identity and icons must be original, not copied from gaming storefronts.

## Excluded / safety constraints

No DRM bypass, mods/cheats injection, anti-cheat evasion, credential collection, game binary patching, registry writes for detection, altering game installations, deleting user files, uploading library inventories to a server, monetization or bundled adware.

## Acceptance tests

See `docs/TEST_PLAN.md`. Milestones in `docs/IMPLEMENTATION_PLAN.md` define priority; passing only the manual-add demo is not completion of the full requested MVP.
