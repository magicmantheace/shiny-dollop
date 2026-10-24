# Product specification — Windows Game Performance Profiles

**Intake status:** Approved project concept; implementation not started.
**Priority:** 8/17
**Audience/target platform:** Windows gaming utility

## Problem and outcome

Apply reversible, consented per-game performance settings and show before/after resource observations.

## MVP user workflow and acceptance contract

Define one low-risk profile, preview proposed changes, activate with approval, and fully restore prior settings.

The MVP is accepted only when a tester can complete the workflow using an actual running build, inspect the resulting data/artifact, restart when relevant, and reproduce the result. Showing an interface or a unit test alone is not an MVP.

## Requirements — initial and subsequent milestones

1. **Per-game named profiles** — implement with persisted, validated state and meaningful user feedback where relevant.
2. **Process and resource telemetry** — implement with persisted, validated state and meaningful user feedback where relevant.
3. **Safe power-plan presets where supported** — implement with persisted, validated state and meaningful user feedback where relevant.
4. **Window/process identification** — implement with persisted, validated state and meaningful user feedback where relevant.
5. **Opt-in changes and automatic rollback** — implement with persisted, validated state and meaningful user feedback where relevant.
6. **Before/after resource comparison** — implement with persisted, validated state and meaningful user feedback where relevant.
7. **Restore-all and failure diagnostics** — implement with persisted, validated state and meaningful user feedback where relevant.

## Data model and architecture considerations

Windows desktop UI with narrow OS APIs; capability probing and change journal for rollback.

Use a clearly versioned and documented local storage/export format. Define entities and transitions from the MVP workflow, not guessed integrations. Include migration and backup/restore behavior before treating persisted data as production-ready.

## Integration strategy

Standalone; optional data import from game metadata manager.

No other application's source or database may be modified as part of this project. Where useful, exchange versioned export/import contracts and independently owned fixtures.

## Nonfunctional and safety requirements

Read-only recommendations by default. No overclocking, driver patching, security-service shutdown, or anti-cheat interference.

- Prefer offline operation and no paid API dependency.
- Optimize for a Windows 11 desktop (i5-10400F, RTX 3060 12 GB, 32 GB RAM), where relevant.
- Avoid destructive defaults, unapproved network calls, or hidden data collection.
- Make errors actionable; provide accessible keyboard navigation and recovery paths.
- Use original/licensed assets and scrub private example data.

## Completion criteria

1. Runnable build and reproducible install or launch instructions.
2. End-to-end MVP workflow exercised with recorded evidence.
3. Focused automated tests and relevant platform manual tests executed.
4. Clear distinction between implemented, verified, planned and blocked features.
5. Scoped pull request left unmerged for review.

## Appendix — As-built MVP (2026-10-23, renderer / Worker B)

What the intake spec asked for vs what the renderer actually implements. Backend (Electron main, preload, engine) was built in parallel by Worker A on the same branch; the contract below is the shared `app/shared/gpp-types.ts`.

**Built (renderer):**
- Per-game named profiles with create / edit / delete — spec item 1. Profiles list shows capability badges per change kind and an applied/not-applied badge derived from the journal (the contract has no separate applied flag; journal entries with no `rolledBackAt` are the source of truth).
- Opt-in changes and automatic rollback — spec item 5. Preview modal lists every planned change (kind, target, from → to, reversible badge, unsupported reasons); Activate requires an explicit approval checkbox plus all-supported; unsupported changes block activation. Progress events stream during activation; failures show the error and the automatic-rollback notice.
- Restore-all and failure diagnostics — spec item 7. Per-profile rollback and a global "Restore all changes" button, both with confirm dialogs and result reports (counts + journal entry ids + error lists).
- Before/after resource comparison — spec item 6, minimal form. Snapshots are point-in-time CPU % / memory MB observations with a two-snapshot delta comparison. Every snapshot is labeled "approximate — point-in-time estimate, not a benchmark".
- Safe power-plan presets where supported — spec item 3, minimal form. The editor takes a GUID with format validation and a "pick your own plan via `powercfg /list`" warning; supported/unsupported comes from backend capability probing, surfaced as badges.
- Change journal view — every entry with before → after, applied-at, rolled-back-at.

**Partially built / backend-dependent:**
- Process and resource telemetry — spec item 2. Only point-in-time snapshots; no continuous telemetry, no charts.
- Window/process identification — spec item 4. The editor takes a process name / exe path as text; nothing enumerates windows or processes.

**Deferred (explicitly not in this milestone):** per-game auto-detection, telemetry charts, scheduled profiles.

**Design decisions worth keeping:** the renderer never touches the OS directly — all twelve operations go through `window.gpp`; `{ error }` responses become thrown errors with the action name attached; a missing bridge produces one actionable message. Client-side validation (GUID shape, exe names/paths, priority allow-list) runs before any IPC call, and the backend re-validates independently.
