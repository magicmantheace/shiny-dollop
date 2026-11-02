# Local connectors and the opt-in/disable control plane (v0.8)

`athenz-connectors` is the single control plane for AthenZ's local
integrations — the v0.8 gate: *per-integration opt-in and disable
controls*. A connector is a named integration between AthenZ and
something on the owner's own machine: a local capability (offline
voice transcription) or a bounded local resource (a directory of
notes).

**Boundary: connectors in this slice are LOCAL ONLY.** No connector
here opens a network connection, talks to a remote service or leaves
the machine. Any network integration is a separate future design
requiring its own review; nothing in this framework pre-approves one.

**Default is off.** With no opt-in recorded, the gate refuses every
use of every integration, and AthenZ behaves exactly as it did before
connectors existed. A remembered preference, a plan and a model's own
idea are never permission — only an opt-in recorded through the
explicit owner action below enables anything, and only the tiers it
names.

## The control model

Each integration has a **descriptor** (what it is) and **state**
(whether the owner allows it). Descriptors for code-defined
integrations live in code (`athenz/local_connectors.py`); the owner
can also register additional descriptors through the store API
(`register_integration`, itself `--confirm`-gated). State lives in
the private profile database — never in a repository — and is read
from the store at every check. Nothing is cached in memory, so a
change made by any process is honored by the next check in every
process.

| Field | Meaning |
| --- | --- |
| `id` | Stable integration id, e.g. `voice-transcription`, `local-notes`. |
| `kind` | What sort of integration it is (`speech-to-text`, `local-files`, …). |
| declared tiers | The capability tiers the integration offers: `read` and/or `write`, declared separately. |
| `state` | `not_opted_in` (the default), `enabled` or `disabled`. |
| approved tiers | The tiers the owner has approved. Read and write are approved **independently**. |
| `config` | Per-integration owner configuration (for `local-notes`: its one directory). |
| provenance | How the current state arose (`owner-opt-in`, `owner-disable`, or the voice legacy seed). |

### Per-tier opt-in

Opting in is an explicit owner action and requires `--confirm`:

```sh
athenz-connectors opt-in local-notes --tier read --directory ~/Notes --confirm
```

Approving `read` never approves `write`. A write attempt under a
read-only opt-in is refused with the distinct reason
`tier_not_approved`, and approving `write` later is a second,
separate opt-in. An integration cannot be opted into a tier it does
not declare.

### Disable

```sh
athenz-connectors disable local-notes     # no --confirm, by design
```

Disable is frictionless and **immediate**: it takes effect on the
very next gate check, in any process, because checks always read the
store. Disable also **clears the approved tiers**. Re-enabling is
therefore a fresh opt-in that must approve tiers again, one by one —
a disable can never be silently undone with the old approvals intact.

### The voice legacy rule (one-way, voice only)

`voice-transcription` predates this registry: the owner validated
that exact offline transcription flow on their own hardware in
October 2026, under its own per-use `--confirm` and privacy gates.
Breaking an already-approved flow the first time the registry runs
would be the registry inventing a revocation the owner never made.
So the **first time the registry is consulted** on a profile,
`voice-transcription` is seeded `enabled` (read tier) with
provenance `legacy-owner-validated`, and the seeding is written to
the audit log like every other state change.

This is a one-way grandfathering, not a precedent:

- **Every other integration** — builtin or owner-registered — starts
  `not_opted_in`, with no exceptions.
- Once the owner disables voice, it behaves exactly like any other
  integration: re-enable needs an explicit opt-in (`--confirm`), and
  only the tiers named in that opt-in are approved.
- The legacy seed changes nothing about the voice flow's own gates:
  `athenz-voice transcribe` still requires its per-use `--confirm`,
  an existing local WAV and an existing local model, and still stores
  nothing.

## The gate

Connector code must call `LocalConnectorStore.require(id, tier)`
before every use. The check returns `allowed` plus a specific
machine-readable `reason` — never a bare no:

`allowed`, `unknown_integration`, `not_opted_in`, `disabled`,
`tier_not_approved`.

**Every decision — allow and refuse — is audit-logged**, together
with every state change (`seeded`, `registered`, `opted_in`,
`disabled`):

```sh
athenz-connectors list
athenz-connectors show local-notes
athenz-connectors audit                      # recent events, all integrations
athenz-connectors audit --integration voice-transcription
```

## The local-notes reference connector

`local-notes` is a real, working connector — the reference
implementation for future ones:

- **Read tier**: list and read `.txt` / `.md` / `.markdown` files
  from the ONE directory named at opt-in time (`--directory`, stored
  in the profile). The directory is not searched recursively and
  cannot be changed by connector code — only by a new owner opt-in.
- **Confinement**: note names are bare file names. Separators, `..`
  and absolute paths are refused; symbolic links are refused rather
  than followed; the resolved target must remain inside the
  configured directory. A symlink planted inside the directory that
  points outside it gains nothing.
- **Bounds**: note reads and writes are capped at 256 KiB, and only
  regular files count.
- **Write tier** (separately approved): `append` creates a **new**
  note file with the given text — creation is exclusive, so an
  existing file is never overwritten, truncated or appended to; the
  attempt is refused and the existing bytes are untouched.

```sh
athenz-connectors opt-in local-notes --tier read --directory ~/Notes --confirm
athenz-connectors notes list
athenz-connectors notes read shopping.md
athenz-connectors opt-in local-notes --tier write --confirm
athenz-connectors notes append ideas.md --text "Synthetic note text"
```

## Voice wiring

`athenz-voice transcribe` and `athenz-voice evaluate` (both perform
transcription) consult the gate for `voice-transcription` / `read`
before any transcription work begins. A disabled integration refuses
with a message naming the integration state and the re-enable
command; no model is loaded and no audio is read. `inspect`,
`inspect-model` and `score-text` perform no transcription and are not
gated. The library functions in `athenz/voice.py` are unchanged —
the gate lives at the CLI entry point, alongside the existing
per-use `--confirm`.

## What this does not do

- No network access of any kind, for any connector, in this slice.
- No background listener, scheduler or auto-enable: state changes
  only through the owner's explicit CLI actions above.
- No descriptor can widen itself: an integration's declared tiers
  are fixed by its descriptor, and opt-in cannot approve an
  undeclared tier.
- Disabling a connector does not delete its configuration or audit
  history; it refuses use. Erasure remains the profile tools' job.
