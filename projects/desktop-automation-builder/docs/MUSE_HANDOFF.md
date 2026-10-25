# Muse implementation handoff — Desktop Automation Builder

**Priority:** 12/17. **Project:** `projects/desktop-automation-builder/`.
**Status:** MVP IMPLEMENTED AND REVIEW-READY (2026-10-23; last updated 2026-10-24, Codex cycle 4). Application code IS implemented in `app/` — do not re-choose a stack or re-implement the MVP. Branch: `desktop-automation-builder/mvp` (unmerged PR #16).

## What exists

- Electron 45 + React 19 + TypeScript strict + Vite app in `app/` (`node:sqlite` persistence, zod-validated IPC, flat `window.dab` API — canonical contract in `app/shared/types.ts` + `app/shared/errors.ts`).
- Step-list workflow editor: file-copy, file-move-to-trash (recoverable, `.dab-trash/`), folder-create, run-approved-script (explicit allowlist only, `shell: false`, 60s timeout, process-group termination on timeout/cancel/shutdown, surviving descendants terminated before a step completes, stdout/stderr retention bounded while collecting), and log-message steps.
- Sandboxed executor: every step path is confined to the workflow's `sandboxRoot` (lexical + realpath checks; escapes rejected with `PATH_OUTSIDE_SANDBOX`), dry-run preview with zero writes, explicit approval gate, durable per-step run logs, cancel, and retry-from-failed-step against the archived workflow version.
- Workflow versioning (every update archives a snapshot) and versioned export/import (`formatVersion: '1.0.0'`; imports never auto-run; duplicate step IDs rejected before persisting).

## Launch / verify

```bash
cd projects/desktop-automation-builder/app
npm ci
npm test            # full suite (see docs/IMPLEMENTATION_STATUS.md for current count)
npm run typecheck
npm run lint
npm run build       # renderer bundle + main/preload compile to dist/
npm run smoke       # packaged main self-check under Xvfb, prints SMOKE_OK
npx electron .      # launch the app
```

## Outstanding limitations (do not claim otherwise)

- No triggers/conditions, no network steps, no node-graph editor (step-list only), no auto-restart of interrupted runs.
- Windows 11 click-through, real script spawning on Windows (direct child kill there instead of POSIX process groups), and NSIS packaging are unverified — no Wine/Windows on the build VM. No code signing.
- See `docs/IMPLEMENTATION_STATUS.md` for the full implemented / verified / unverified split and the per-cycle Codex fix history.

## Guardrails (unchanged)

No unrestricted shell execution or invisible background persistence; no privileged/destructive actions without separate explicit approval. Work only inside `projects/desktop-automation-builder/`; never force-push or merge without owner approval. Use fixtures, never real personal data.
