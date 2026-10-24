# Calibration data exchange format

**Version:** 1.0.0 · **Status:** documented contract, implemented in Concrete Operations Manager MVP
**Counterpart:** Volumetric Mix Calculator (Project 3) — independent implementation, no shared code or dependencies.

## Purpose

A versioned JSON envelope for moving volumetric calibration data between the two
applications. Concrete Operations Manager treats imported payloads as **opaque**:
it validates the envelope, stores the profile, and can export it back out, but
never interprets calibration semantics. The Mix Calculator owns the semantics.

## Envelope

Top-level JSON object. All field names are case-sensitive.

| Field | Type | Required | Description |
|---|---|---|---|
| `formatVersion` | string | yes | Semver `X.Y.Z` of this contract, e.g. `"1.0.0"`. Readers must reject unknown **major** versions. |
| `profileName` | string | yes | Human-readable profile name, 1–200 chars. |
| `exportedAt` | string | yes | RFC 3339 timestamp of export. |
| `exporter` | string | yes | Identifies the producing application, 1–200 chars. |
| `units` | object | yes | `volume`: `m3` \| `L` \| `yd3`; `mass`: `kg` \| `t` \| `lb`; `length`: `m` \| `mm`. All numeric fields are interpreted in these units. |
| `materials` | array | yes | ≥1 material descriptor: `{ materialId, kind, description? }`. `kind`: `cement` \| `sand` \| `gravel` \| `water` \| `admixture` \| `other`. |
| `calibrations` | array | yes | Gate calibration rows: `{ materialId, gateSetting, measuredOutputPerUnit, measuredAt? }`. `gateSetting` is the calculator's own dial/position unit (opaque number); `measuredOutputPerUnit` is mass or volume per gate unit in the envelope's units, must be > 0. |
| `mixes` | array | no | Mix designs: `{ mixDesignId, note?, nominalOnly: true, components: [{ materialId, targetPerM3 }] }`. `targetPerM3` is the target quantity of that material per cubic metre/yard (in envelope units), ≥ 0. |

## Material IDs

`materialId` values are opaque strings (1–100 chars), unique within one envelope.
Every `materialId` referenced by `calibrations[]` or `mixes[].components[]` **must**
be declared in `materials[]`; undeclared references fail validation.

## Mix design IDs — nominal only

`nominalOnly` must be literally `true`. A mix design ID (e.g. `"C25/30"`) is a
**nominal design identifier only** — it is never a verified structural
performance claim. Concrete Operations Manager surfaces this label everywhere a
mix ID is shown, and any consumer of this format must do the same.

## Validation rules (enforced by Concrete Operations Manager on import)

1. `formatVersion` matches `^\d+\.\d+\.\d+$`.
2. `units` enums are exact; unknown unit strings are rejected.
3. `materials` is non-empty; `materialId`s are unique.
4. All `calibrations[].materialId` and `mixes[].components[].materialId` reference declared materials.
5. Numeric fields are finite; `measuredOutputPerUnit` > 0; `targetPerM3` ≥ 0.
6. Payload size ≤ 5 MB (import guard).

## Versioning policy

- **Patch** (1.0.x): clarifications only; readers accept.
- **Minor** (1.x.0): additive optional fields; readers ignore unknown fields and keep working.
- **Major** (2.0.0): breaking changes; readers must reject envelopes whose major version they do not implement.

## Example

```json
{
  "formatVersion": "1.0.0",
  "profileName": "Plant A — winter 2026",
  "exportedAt": "2026-10-23T10:00:00.000Z",
  "exporter": "Volumetric Mix Calculator 0.1.0",
  "units": { "volume": "m3", "mass": "kg", "length": "m" },
  "materials": [
    { "materialId": "cement-type10", "kind": "cement", "description": "Type 10 Portland" },
    { "materialId": "sand-washed", "kind": "sand" }
  ],
  "calibrations": [
    { "materialId": "cement-type10", "gateSetting": 42, "measuredOutputPerUnit": 12.5 }
  ],
  "mixes": [
    {
      "mixDesignId": "C25/30",
      "nominalOnly": true,
      "components": [{ "materialId": "cement-type10", "targetPerM3": 320 }]
    }
  ]
}
```

## In-app support (Concrete Operations Manager)

Settings → Calibration profiles: **Import…** validates the envelope against the
schema above and stores the payload; **Export** writes the stored JSON back to
disk; **Remove** deletes the profile. Import/export round-trips are covered by
automated tests (`tests/integration/calibration.test.ts`).
