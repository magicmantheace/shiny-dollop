# Project instructions — muse-pc-bridge

These rules apply inside `projects/muse-pc-bridge/`. The repository
root `AGENTS.md` wins on any conflict.

## Scope

1. Work only inside this folder. Do not modify other projects or the
   repository root beyond registering this project in the root README
   index.
2. **Python standard library only.** No third-party dependencies, no
   virtualenv manifests, no package installs — for the agent, the
   client, and the tests.
3. The agent targets Windows 11 on the owner's PC; keep POSIX
   (Linux/macOS) dev support working so tests can run off-Windows.

## Secrets and local state — hard rules

4. **Never commit** `config.json`, any real token, audit logs
   (`logs/`), or file-root contents (`bridge-files/`). They are
   git-ignored on purpose; if a change would add them, stop.
5. Never print the token anywhere except the one-time `--init`
   console output on the owner's PC. Never write it to the audit log,
   a doc, a test, or a commit message. Tests use an obvious dummy
   token only.
6. Hand-off of the real token/IP happens out-of-band between the
   owner and Muse — never through this repository.

## Security posture — owner's decisions, do not relitigate silently

7. **Full shell access is the owner's explicit choice (2026-11-04).**
   Do not add a command allowlist, approval prompts, or exec
   restrictions without the owner's direction. If you believe a
   change is needed, raise it in `docs/MUSE_HANDOFF.md` instead of
   shipping it.
8. **The audit log is non-negotiable.** Every `/v1/*` request —
   including auth failures — plus server start/stop must be audited.
   Any change that could drop, reorder, or redact audit entries
   (beyond the existing 500-char command truncation in summaries)
   needs the owner's explicit approval.
9. Default binding guidance stays tailnet-only. Wildcard binds must
   keep the loud startup warning.
10. File endpoints stay confined to `allowed_file_root` (no absolute
    paths, no drive letters, no `..` escapes). Exec is full-shell by
    design; the file root is a convenience boundary, not a sandbox —
    keep the docs honest about that distinction.

## Verification honesty

11. **Never claim Windows or Tailscale validation from Linux VM
    tests.** VM runs prove protocol/auth/audit logic on POSIX only.
    Windows execution, PowerShell/cmd behavior, the `.cmd` launcher,
    the autostart task, and the tailnet link are verified only when
    run on the owner's PC, and `docs/MUSE_HANDOFF.md` must say which
    actually happened.
12. After substantive changes: run
    `python -m unittest discover -s tests -v`, and update this
    project's README, `docs/MUSE_HANDOFF.md`, and
    `docs/TEST_PLAN.md` with real results (counts and platform),
    separating verified / unverified / planned work.
13. Use project-prefixed branches, commits, and PR titles
    (`muse-pc-bridge: ...`). Do not auto-merge or force-push.
