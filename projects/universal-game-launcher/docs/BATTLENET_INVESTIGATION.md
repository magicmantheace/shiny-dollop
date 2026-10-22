# Battle.net integration — investigation notes

**Date:** 2026-10-22
**Outcome:** detect-client + manual-registration path. No per-game discovery,
no deep links. This document records exactly what was checked and why each
candidate mechanism was accepted or rejected.

## What was accepted

- **Client presence via executable.** Battle.net installs
  `Battle.net.exe` under `%ProgramFiles(x86)%\Battle.net\` (64-bit Windows)
  or `%ProgramFiles%\Battle.net\`. Verifying the file exists is a reliable,
  read-only, non-secret check. Accepted.
- **Opening the client** by spawning the validated executable path with
  `shell: false` and no arguments. The path is constructed by our own probe
  from well-known locations (never from user input or manifests), then
  re-validated (absolute, ends in `Battle.net.exe`, is a file) before spawn.
  No URI scheme is involved, so nothing is forged.

## What was rejected

- **`%ProgramData%\Battle.net\Agent\product.db`.** This is Blizzard's
  internal agent database in an undocumented proprietary binary format. It
  is not documented by Blizzard, community parsers disagree, and the format
  changes between agent versions. Parsing it risks misidentifying games or
  crashing on format drift. Rejected: guessing game identities from an
  undocumented binary is exactly the "invented data" this project forbids.
- **Install-folder sniffing** (e.g. `C:\Program Files (x86)\World of
  Warcraft`). Folder names are not a stable game identity: users rename
  folders, multiple products share publishers, and non-Blizzard software can
  sit nearby. Rejected: folder names are not game identities.
- **Registry keys.** No stable, documented Battle.net install-path key was
  verified. Rejected: not relied upon (would be guessing).
- **Per-game URI schemes** (e.g. `battlenet://...`). No per-game launch URI
  is documented by Blizzard or verified against a real client in this
  project. Rejected: inventing a scheme would violate the "never forge
  unsupported vendor protocol commands" rule.
- **Credential or token files.** Never inspected, per project policy.

## Resulting behavior

- `probe()` reports installed/unavailable with the checked paths.
- `scan()` completes with zero games and an explanatory warning: per-game
  discovery is unsupported; add Battle.net games with Add Game (manual) or
  open the client from Settings.
- The Settings source row shows an **Open Battle.net** button when the
  client is detected. It spawns the validated client executable and reports
  success/failure honestly; it never claims a game is running.
- Manually added Battle.net game executables keep working through the
  normal manual launch flow (direct spawn, observed session tracking).
