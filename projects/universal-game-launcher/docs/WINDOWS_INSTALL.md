# Installing Universal Game Launcher on Windows 11

> Status: the installer is built with electron-builder (NSIS, x64). It is
> **unsigned** — Windows SmartScreen will show a warning on first install.
> Only install a build you made yourself from this source tree.

## Install steps

1. On the machine that will run the launcher, build the installer:
   - Install Node.js 22+ and open a terminal in `projects/universal-game-launcher/app`.
   - `npm ci`
   - `npm run package:win`
   - The installer lands at `release/Universal Game Launcher-0.1.0-win-x64.exe`.
2. Copy that `.exe` to the Windows 11 machine and double-click it.
3. If SmartScreen warns "Windows protected your PC": click **More info** →
   **Run anyway**. (Expected: the app is unsigned. See "Why unsigned?" below.)
4. Choose an install folder (default is fine) and whether to create desktop /
   Start Menu shortcuts. No administrator rights are needed.

## First run — what to expect per source

The launcher never moves, edits, or deletes your games. It only reads local
information and remembers what you tell it.

| Source | First run |
|---|---|
| **Manual** | Always available. Click **Add game**, pick a trusted `.exe`. The launcher remembers the path you chose — it never scans your disk on its own. |
| **Steam** | Click **Scan Steam** in Settings. Requires the Steam client installed; games are read from `libraryfolders.vdf`. Per-game launch uses the client's `steam://` links. |
| **Epic** | Click **Scan Epic** in Settings. Requires the Epic Games Launcher installed; games are read from `%ProgramData%\Epic\EpicGamesLauncher\Data\Manifests\*.item`. Cards show **Open Epic Games Launcher** — the game itself is started from inside the Epic client, and the launcher honestly reports "launch requested" rather than pretending to track it. |
| **Battle.net** | Settings shows **Open Battle.net** when `Battle.net.exe` is found in its standard install folder. Games are registered manually (Add game); per-game launch from the launcher is not supported. |

### When a client is missing

Each source row in Settings shows its own status:
- **Detected** — the client was found; scanning/launching works.
- **Not detected** — the client isn't installed (or is somewhere unusual). The
  launcher keeps working for everything else; install the client and rescan.
- A failed scan never touches the rest of your library — failures are isolated
  per source and reported on that source's row.

## Play-time tracking

- Tracking is **on** by default and can be toggled in Settings → Playback.
- When off: nothing is recorded and no background watchers run.
- "Launch requested" entries (Epic/Battle.net client handoffs) never invent
  playtime — the session ends the moment the request is handed off.
- **Clear play history** (Settings → Playback, with confirmation) deletes only
  the launcher's own records. It never touches game files, saves, or clients.

## Uninstall / data removal

1. **Uninstall the app:** Settings → Apps → Installed apps → *Universal Game
   Launcher* → Uninstall. This removes the program files and shortcuts.
2. **Remove your data** (library, sessions, covers, settings): delete the
   folder `%APPDATA%\Universal Game Launcher\` (the app's own user-data
   directory). The uninstaller intentionally leaves this behind so
   reinstalling keeps your library — delete it yourself if you want a fully
   clean slate.

## Why unsigned?

Code-signing certificates cost money and tie the build to a publisher
identity. This project ships unsigned by design (no release without the
owner's approval). An unsigned installer triggers SmartScreen exactly once;
the installed app runs normally afterwards. If you want a signed build,
acquire a certificate and configure `win.certificateFile` in
`electron-builder.yml`.

## Troubleshooting

- **Installer won't start / shows a SmartScreen block:** use *More info →
  Run anyway* (unsigned build, expected).
- **Steam/Epic scan finds nothing:** make sure the client is installed and has
  been run at least once (manifests are written on first launch of the
  client). Check the source row in Settings for the exact reason.
- **A game shows "missing":** its install folder moved or was uninstalled.
  Re-scan the source or edit the path in the game's details.
- **App won't launch after an update:** delete
  `%APPDATA%\Universal Game Launcher\` only as a last resort — this erases
  your library and history.
