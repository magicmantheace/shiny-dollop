# Calibration exchange format — v1.0.0 implementation notes

This project implements the **calibration data exchange envelope v1.0.0**
documented by Concrete Operations Manager (Project 2). The two applications
share **no code or dependencies** — this is an independent implementation
validated against the documented contract (format conformance only).

## Contract source

Project 2's `docs/CALIBRATION_EXCHANGE.md` (branch `concrete-operations-manager/mvp`).
This calculator's implementation lives in `app/engine/exchange.ts`; every
documented validation rule has a corresponding test in
`app/tests/unit/exchange.test.ts`.

## Mass/volume basis convention

The v1.0.0 contract says `measuredOutputPerUnit` is "mass or volume per gate
unit in the envelope's units" but does not carry an explicit per-material
basis flag. This calculator uses the following documented convention:

- **Mass-basis** (value in the envelope's mass unit): `cement`, `sand`,
  `gravel`, `other`
- **Volume-basis** (value in the envelope's volume unit): `water`, `admixture`

Concrete Operations Manager treats imported payloads as opaque, so this
convention only affects this calculator's own calculations and exports.

## Field mapping

| Internal field | Envelope field | Notes |
|---|---|---|
| `profile.profileName` | `profileName` | 1–200 chars, validated |
| `profile.units.volume` / `.mass` | `units.volume` / `units.mass` | exact enum match |
| — | `units.length` | always `'m'` on export (this calculator has no length quantities) |
| `material.materialId` / `.kind` / `.description` | `materials[]` | `materialId` 1–100 chars, unique |
| `calibration.gateSetting` | `calibrations[].gateSetting` | finite number |
| `calibration.measuredOutputPerUnit` | `calibrations[].measuredOutputPerUnit` | > 0 |
| `calibration.measuredAt` | `calibrations[].measuredAt` | optional, carried through |
| `calibration.source` | — | **not in the contract**; stays local to this app |
| `mix.mixDesignId` / `.note` | `mixes[].mixDesignId` / `.note` | — |
| — | `mixes[].nominalOnly` | **always `true`** on export; import rejects anything else |
| `component.targetPerM3` | `mixes[].components[].targetPerM3` | ≥ 0 |

## Import behavior

- Unknown **major** `formatVersion` → rejected.
- Unknown unit strings, undeclared `materialId` references, non-finite or
  out-of-range numerics, `nominalOnly !== true` → rejected with actionable messages.
- Payloads over 5 MB → rejected (import guard).
- Unknown material **kinds** → imported as `other` with the original kind
  recorded in the description, so no data is silently lost.

## Export behavior

Every export is re-validated against the contract before writing the file —
this calculator can never emit an envelope its counterpart would reject
(under the documented rules).
