# Crawl Sentinel validation

`crawl-repository.json` is the checked-in Project Sentinel configuration for the first Crawl tester cutover from Mira.

## Mira parity

The initial `crawl-repository` profile intentionally mirrors the checked-in Mira Crawl validator configuration in `magicmantheace/Mira`:

- repository: `https://github.com/magicmantheace/Crawl.git`
- watched branch: `away/2026-09-roadmap-integration`
- poll cadence: 300 seconds
- Python executable assumption: `python`
- compile gate: `python -m compileall -q src tests`
- compile timeout: 900 seconds
- pytest gate: `python -m pytest -q -x --tb=line`
- pytest timeout: 7200 seconds
- stages execute sequentially and pytest depends on compile passing
- no dependency-install stage is added; Mira likewise assumes the validator environment is already prepared
- validation never pushes the watched/source branch

Sentinel itself supplies the exact-remote-SHA resolution, detached clean checkout, immutable canonical result, sealed logs/evidence, retry-safe publication, and exact-SHA reuse rules. Those responsibilities therefore do not appear as validation stages in this file.

## Intentional cutover difference

Mira publishes to `validation/mira-crawl-local`. Sentinel publishes to:

`validation/sentinel-crawl-local`

The separate result branch preserves Mira's historical validation records and prevents the two testers from writing into the same publication namespace during cutover.

Completion hooks are initially disabled because Mira's Crawl validator does not invoke a downstream completion hook. They can be enabled after Sentinel is confirmed as the active tester.

## Install on the current Windows Sentinel host

After pulling Crawl, copy the checked-in config into Sentinel's project directory:

```powershell
Copy-Item .\config\sentinel\crawl-repository.json D:\Project-Sentinel\projects\crawl.json -Force
```

Run one exact-SHA validation pass:

```powershell
D:\Project-Sentinel\app\.venv\Scripts\project-sentinel.exe `
  --config D:\Project-Sentinel\projects\crawl.json `
  --once
```

For unattended operation, use the normal Sentinel service/fleet scheduler with `D:\Project-Sentinel\projects` as the project-config directory.

## Authority

Sentinel is the tester/referee only. ChatGPT remains the builder. A Crawl SHA is considered validated only by Sentinel's immutable canonical result for that exact SHA; mutable latest-state files or the validation branch do not redefine that result.
