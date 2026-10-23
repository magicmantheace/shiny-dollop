# Underreach Remote Development Runner

The remote development runner is designed for SSH/Termius use from a phone. Long jobs are launched in a detached Windows PowerShell process so they continue when the SSH session disconnects.

## Branch

The initial runner was added on:

`chore/underreach-remote-dev-runner`

## Quick start

From PowerShell:

```powershell
Set-Location D:\CrawlTesting
git fetch origin
git switch chore/underreach-remote-dev-runner
git pull --ff-only
.\scripts\underreach-dev.ps1 help
```

## Commands

### Status

```powershell
.\scripts\underreach-dev.ps1 status
```

Show the latest job.

To find a job by partial name:

```powershell
.\scripts\underreach-dev.ps1 status population
```

### List recent jobs

```powershell
.\scripts\underreach-dev.ps1 list
```

### Pull the current branch

```powershell
.\scripts\underreach-dev.ps1 pull
```

This uses `git pull --ff-only`. It never resets or cleans the working tree.

### Run the full Python test suite detached

```powershell
.\scripts\underreach-dev.ps1 test
```

Optional job name:

```powershell
.\scripts\underreach-dev.ps1 test 29b1-tests
```

You may disconnect Termius immediately after the job starts.

### Start Underreach detached

```powershell
.\scripts\underreach-dev.ps1 start
```

Profiles:

```powershell
.\scripts\underreach-dev.ps1 start -Profile qa
.\scripts\underreach-dev.ps1 start -Profile alpha
.\scripts\underreach-dev.ps1 start -Profile headless
```

### Resume Underreach detached

```powershell
.\scripts\underreach-dev.ps1 resume
```

### Request a clean Underreach shutdown

```powershell
.\scripts\underreach-dev.ps1 stop
```

### Run any repository PowerShell validation script detached

```powershell
.\scripts\underreach-dev.ps1 run-script scripts\run-underreach-character-validation.ps1
```

Arguments can be passed using `-ArgumentList`:

```powershell
.\scripts\underreach-dev.ps1 run-script scripts\run-underreach-character-validation.ps1 -ArgumentList '-SkipBlender'
```

The runner intentionally restricts `run-script` to `.ps1` files inside the repository.

### Tail the latest job log

```powershell
.\scripts\underreach-dev.ps1 tail
```

Choose the number of lines:

```powershell
.\scripts\underreach-dev.ps1 tail -TailLines 100
```

Or select a job by partial name:

```powershell
.\scripts\underreach-dev.ps1 tail 29b1 -TailLines 100
```

## Job storage

Each detached job gets its own directory under:

`unreal\CrawlPresentation\Generated\dev-runner`

A directory contains:

- `spec.json` — immutable launch specification
- `status.json` — machine-readable current/final status
- `output.log` — combined command output

The status protocol is:

`underreach.dev-runner-status.v1`

The job protocol is:

`underreach.dev-runner-job.v1`

## Safety rules

- `pull` uses fast-forward only.
- The runner never calls `git reset`, `git clean`, or `git stash`.
- `run-script` accepts only repository-local `.ps1` files.
- Long jobs are detached from SSH rather than tied to the Termius connection.
- Underreach shutdown uses the existing clean stop-request mechanism.
- The runner does not use GitHub Actions.

## Recommended phone workflow

```powershell
cd D:\CrawlTesting
.\scripts\underreach-dev.ps1 pull
.\scripts\underreach-dev.ps1 run-script scripts\<validation-script>.ps1
```

Disconnect Termius if desired.

Later:

```powershell
cd D:\CrawlTesting
.\scripts\underreach-dev.ps1 status
.\scripts\underreach-dev.ps1 tail
```

Send the final status/report back to the development chat for diagnosis or the next change.
