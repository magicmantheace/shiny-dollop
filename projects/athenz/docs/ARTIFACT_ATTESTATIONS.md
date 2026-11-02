# Verified artifact IDs and test attestations (v0.3)

`athenz-artifact-attestations` closes the v0.3 roadmap item
"Verified artifact IDs and reproducible external test attestations."
It answers two questions about any file whose bytes matter — a build
output, a portable bundle, an exported model:

1. *Which exact bytes are we talking about?* — the artifact ID.
2. *What test result was actually observed for those bytes, and can
   the record of it be trusted not to have been edited since?* — the
   attestations, and `verify`.

## Artifact identity

An artifact's ID is the **SHA-256 of its exact bytes**. Anyone with
the file can reproduce the ID; nobody needs this tool to check it.
Registering a file records, in the private profile database:

| Field | Meaning |
| --- | --- |
| `artifact_id` | SHA-256 hex digest of the file's bytes. The primary key. |
| `name` | Display name (default: the file name). |
| `size` | Byte size at registration. |
| `media_type` | Guessed from the file name (`mimetypes`); `application/octet-stream` when unknown. It is a hint, never used for verification. |
| `source` | Owner note on where the artifact came from. |
| `location` | The path where the bytes were registered. A reference only — the bytes are **never copied into the database**. |
| `created_at` | Registration time. |
| `record_digest` | Digest of the canonical serialization of the identity fields above (location excluded — see below). |

The registry lives in the profile database alongside the other
private stores and is never written into a repository.

## Attestations

An attestation binds an artifact ID to **one suite run this tool
performed**. There is deliberately no way to type a result in by
hand: `attest` runs the suite itself and records what happened.

```sh
athenz-artifact-attestations register --path dist/athenz-portable.zip \
    --source "portable build, post-v1-development"
athenz-artifact-attestations attest \
    --artifact <artifact-id> --suite-dir tests-portable
```

`attest` refuses when the artifact is unregistered, when its file is
missing at the recorded location, or when the file's current bytes
no longer hash to the artifact ID — an attestation is never issued
against bytes other than the ones the ID names.

### How a run is recorded

The CLI spawns a subprocess (`python -m athenz.artifact_attestations_cli
_run-suite`) that discovers and runs `unittest` tests in the given
directory with the given pattern (default `test*.py`), then reports
back one JSON document. A suite timeout or a runner malfunction
records **nothing** — there is no partial or estimated attestation.

Each stored attestation carries:

| Field | Meaning |
| --- | --- |
| `suite_name` | The runner kind: `unittest-discover`. |
| `suite_target` | The directory discovery ran against. |
| `suite_fingerprint` | SHA-256 over the runner name/version, the command template and the target + pattern. Reproducible: the same runner against the same target yields the same fingerprint. |
| `result` | `tests_run`, `passed`, `failures`, `errors`, `failed` (failures + errors), `skipped`, `successful`, the failing test ids (capped, with a truncation flag) and the run duration. |
| `result_digest` | SHA-256 of the canonical result payload. |
| `environment` | Fingerprint captured from the **runner's own runtime**: platform, Python implementation and version, machine. |
| `record_digest` | SHA-256 of the canonical serialization of the whole attestation record. |
| `created_at` | When the run was recorded. |

Attestations are **append-only** through this API: there is no edit
or delete. A **failing suite is recorded as failed** — its counts,
its failing test ids and `successful: false`. Nothing rounds a
failure up.

## Verification

```sh
athenz-artifact-attestations verify <artifact-id>
```

Verification **recomputes everything and trusts no stored hash**:

- the registry entry's `record_digest` is recomputed
  (`registry_status`: `ok` / `record_tampered`);
- the artifact file at the recorded location is re-hashed
  (`artifact_status`: `present` / `missing`; `current_artifact_id`
  and `identity_match` report what the bytes actually are now);
- every attestation's `result_digest` and `record_digest` are
  recomputed.

Each attestation is then reported with one status, in this
precedence order:

| Status | Meaning |
| --- | --- |
| `record_tampered` | The stored attestation no longer matches its own digests — the record was edited after issuance. |
| `artifact_missing` | No file exists at the recorded location, so there are no bytes to check the attestation against. |
| `artifact_mismatch` | Bytes are present but hash to a different ID than the one attested. |
| `suite_result_failed` | The record is intact and the bytes match, but the recorded run itself failed. This is a statement about the artifact, not about the record. |
| `valid` | Record intact, bytes match, recorded run passed. |

`ok` is true only when the registry record is intact, the bytes are
present and match, and every attestation is `valid`.

## What an attestation does and does not prove

An attestation proves that a specific result was recorded, bound to
exact bytes, in a self-consistent record whose **later** tampering
is detectable, and that the bytes offered today are (or are not) the
bytes that record names.

It does **not** prove the runner was honest at issuance time. A
malicious or broken issuing environment could record a fabricated
result whose digests are perfectly self-consistent. External
verification detects tampering and mismatch; it cannot manufacture
trust in the original runner. That matches this codebase's standing
position: local observed results are not independent or
cryptographic attestations, and no signature or trusted-hardware
claim is made anywhere in this feature.

## Export and import ("external")

```sh
athenz-artifact-attestations export <artifact-id> --out bundle-attestations.json
# in another profile:
athenz-artifact-attestations import --file bundle-attestations.json
```

The export document (format tag `athenz-artifact-attestations/v1`) contains exactly the
artifact's identity fields and its attestation records. It contains
**no recorded location** (a path is per-profile bookkeeping, which
is also why location is excluded from the registry record digest)
and no other profile data.

Import re-verifies **every** digest on ingest — the registry record
digest, and each attestation's result and record digests, plus that
every attestation names the exported artifact. Any inconsistency
rejects the document **wholesale**: nothing is imported. Importing
an artifact that is already registered in the target profile is
also refused. The imported entry has no location; `verify` reports
`artifact_missing` until the owner registers the artifact's bytes in
that profile, which binds a location to the same ID (registration
only ever sets a location after recomputing the file's hash and
matching it to the ID).

## CLI summary

| Command | Effect |
| --- | --- |
| `register --path F [--name N] [--source S]` | Hash `F` and record it under its artifact ID. Idempotent per byte content. |
| `attest --artifact ID --suite-dir D [--pattern P] [--timeout S]` | Run the suite in `D` now; append the real result as an attestation. |
| `verify ID` | Recompute all digests and the artifact hash; report per-attestation status. |
| `list` | Registered artifacts with attestation counts. |
| `export ID [--out F]` | Emit the portable JSON document. |
| `import --file F` | Verify and ingest an export document, or reject it whole. |
