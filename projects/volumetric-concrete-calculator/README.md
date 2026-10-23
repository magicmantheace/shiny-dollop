# Volumetric Concrete Mix Calculator

**Status:** PLANNED — project definition only; no working application is implemented by this intake commit.

**Priority:** 3 of 17 in the approved intake queue.
**Category:** Engineering support / Windows desktop
**Repository workspace:** `projects/volumetric-concrete-calculator/`

## Purpose

Calculate calibrated volumetric-truck material needs, stock use, and estimated production yield without claiming unverified strength results.

## First usable release (MVP)

Enter a calibrated mix and desired cubic metres and obtain reproducible cement, sand, stone, water and estimated remaining-stock quantities.

## Full intended capabilities

- Versioned mix/calibration profiles
- Cement, sand, stone, water, and admixture quantities
- Adjustable target volume and waste allowance
- Onboard inventory and silo balance estimate
- Payload and capacity warning inputs
- Measured-versus-theoretical yield comparison
- Unit-aware CSV and JSON exports

## Proposed implementation direction

Offline calculation engine with typed units and a simple desktop UI; portable JSON/CSV calibration exchange. Muse must confirm feasibility before committing to framework choices.

## Dependencies and boundaries

Export format usable by Concrete Operations Manager; applications must compile and run independently.

Do not assert structural concrete strength, code compliance, legal truck payload, or tested mix adequacy from estimates. Mark assumptions and measurement sources.

## Muse start point

Read the repository-root `AGENTS.md`, then [this project's instructions](AGENTS.md) and [development handoff](docs/MUSE_HANDOFF.md). Implement the smallest working end-to-end milestone; document genuine test results. See [specification](docs/PRODUCT_SPEC.md), [test plan](docs/TEST_PLAN.md), and [status](docs/IMPLEMENTATION_STATUS.md).
