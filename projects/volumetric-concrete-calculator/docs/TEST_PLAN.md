# Test plan — Volumetric Concrete Mix Calculator

**Current test status:** NOT RUN. This document defines future acceptance; no test results are implied.

## Required automated and integration scenarios

- Known-value volume and quantity calculations
- Unit conversion and decimal rounding cases
- Prevent zero/negative or implausible calibration values
- Check inventory deductions and threshold warnings
- Round-trip versioned calibration data

## Cross-cutting tests

- Validate malformed, missing, oversized and unauthorized inputs.
- Confirm persistence, restart behavior, schema versioning, and export/import consistency where relevant.
- Exercise cancellation, timeouts, incomplete operations and recovery behavior.
- Confirm tests use temporary fixtures and do not read owner's private or production data.
- Verify deterministic calculations and no accidental state changes in read-only actions.

## End-to-end MVP verification

Enter a calibrated mix and desired cubic metres and obtain reproducible cement, sand, stone, water and estimated remaining-stock quantities.

Run this workflow against a real application build using disposable data; record actual commands, OS environment, relevant results and any platform-only gaps. If the workflow requires Windows or local AI services unavailable in the worker environment, mark it **implemented but unverified** rather than passing.

## Mandatory verification record

For each run, capture: commit SHA, command, execution environment, passed/failed/skipped counts, observed UI/CLI behavior, defect links, and next action. Keep logs free of credentials and personal data.

No release or owner-acceptance claim before end-to-end demonstration.

---

## Recorded results — MVP pass 2026-10-23 (branch `volumetric-concrete-calculator/mvp`)

Environment: Linux VM, Node v24.22.1, Electron 45. All commands run from `projects/volumetric-concrete-calculator/app`.

| Check | Command | Result |
|---|---|---|
| Unit/integration tests | `npm test` (`vitest run`) | **54/54 pass** (4 files: units, calculator, exchange, workflow) |
| Typecheck | `npm run typecheck` (renderer + main + preload) | clean, 0 errors |
| Lint | `npm run lint` (`eslint .`) | clean, 0 errors |
| Build | `npm run build` | green (renderer + main + preload) |
| Window smoke | `xvfb-run -a npm run smoke` | **PASS** — real Electron window boots and quits cleanly |

### MVP acceptance workflow (recorded)

`app/tests/integration/workflow.test.ts` executes the acceptance contract against the real engine code paths with a synthetic fixture profile:

- Input: mix `NOM-25` (nominal ID only), 8 m³, 5% waste, starting stock cement 10000 / sand 30000 / stone 30000 / water 8000 / admix 200 kg-L.
- Output: cement **2688.0 kg** (gate 336.0), sand **6720.0 kg**, stone **8820.0 kg**, water **1386.0 L** (gate 277.2), admixture **10.08 L**; remaining stock cement 7312.0 kg, etc.; **zero warnings**; byte-identical across repeated runs (determinism asserted).
- CSV export contains unit-labelled columns and the estimate/nominal-only disclaimer block.
- Calibration envelope export validates against the v1.0.0 contract (all 6 documented rules + nominalOnly).

### Coverage of the required scenarios

- Known-value volume/quantity calculations: ✅ (cement 2688 kg, water 1386 L asserted exactly)
- Unit conversion and decimal rounding: ✅ (m³/L/yd³, kg/t/lb round-trips; display-only rounding)
- Zero/negative/implausible calibration rejection: ✅ (8 invalid-input cases)
- Inventory deductions and threshold warnings: ✅ (shortfall + low-stock)
- Round-trip versioned calibration data: ✅ (export → validate → import → identical results)
- Malformed/missing/oversized inputs: ✅ (exchange validation: bad semver, unknown units, undeclared materialIds, non-finite numerics, >5 MB guard, nominalOnly≠true)
- Persistence/restart/schema: migration v1; calculations history persisted in SQLite (restart behavior exercised via history list)
- Deterministic calculations: ✅ asserted byte-identical
- Synthetic fixtures only: ✅ (`tests/fixtures.ts`, no real data)

### Platform gaps (honest)

- Desktop click-through of the built app on **Windows 11 not executed** — no Windows hardware on this VM. Marked pending in `docs/IMPLEMENTATION_STATUS.md`, never claimed.
- NSIS installer not attempted (no Wine); portable zip is the Windows deliverable.
