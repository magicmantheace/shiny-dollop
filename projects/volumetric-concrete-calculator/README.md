# Volumetric Concrete Mix Calculator

**Status:** MVP FUNCTIONAL — implementation complete and tested on Linux; Windows execution pending owner hardware.

**Priority:** 3 of 17 in the approved intake queue.
**Category:** Engineering support / Windows desktop
**Repository workspace:** `projects/volumetric-concrete-calculator/`

## Purpose

Calculate calibrated volumetric-truck material needs, stock use, and estimated production yield without claiming unverified strength results.

## MVP (implemented)

Enter a calibrated mix and desired cubic metres → reproducible cement, sand, stone, water (+ admixture) quantities, gate settings, and estimated remaining stock.

- Versioned calibration profiles (materials, gate calibrations, mix designs) in local SQLite
- Known-value calculation engine with typed units (m³/L/yd³, kg/t/lb)
- Waste allowance, starting-stock deduction, low-stock and shortfall warnings
- Truck capacity/payload inputs → **warnings only** (never compliance claims)
- Theoretical vs measured yield comparison
- Unit-aware CSV export; calibration envelope JSON export/import (v1.0.0, compatible with Concrete Operations Manager)
- Electron + React + TypeScript desktop UI; portable Windows zip builds

## What the numbers are (and are not)

- **Estimates.** Every quantity derives from operator-entered gate calibrations.
- **Mix design IDs are nominal only** (e.g. `NOM-25`) — never verified structural performance claims.
- **Truck warnings are estimates** against operator-entered limits — never legal payload or rated-capacity determinations.
- Measurement sources are recorded per calibration and surfaced with results.

## Run it

```bash
cd projects/volumetric-concrete-calculator/app
npm install
npm test        # 54 tests
npm run dev     # dev mode (needs display)
```

See [docs/WINDOWS_INSTALL.md](docs/WINDOWS_INSTALL.md) for the Windows portable build.

## Documentation

- [Product specification](docs/PRODUCT_SPEC.md)
- [Test plan](docs/TEST_PLAN.md) (with recorded results)
- [Implementation status](docs/IMPLEMENTATION_STATUS.md)
- [Calibration exchange format (v1.0.0)](docs/CALIBRATION_EXCHANGE_FORMAT.md)
- [Development handoff](docs/MUSE_HANDOFF.md)
- [Project instructions](AGENTS.md)

## Boundaries

Standalone application. Exports calibration data in the versioned JSON envelope consumed by Concrete Operations Manager; the two applications compile and run independently with no shared code.
