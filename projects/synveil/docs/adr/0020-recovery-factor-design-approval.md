# ADR 0020: Recovery-factor design approved — Option A (printed key, Argon2id record)

- Status: Accepted
- Date: 2026-10-27
- Supersedes: none
- Superseded by: none
- Related: [ADR 0010](0010-independent-owner-recovery.md) (tier 4),
  [recovery factor specification](../RECOVERY_FACTOR_SPEC.md),
  [ADR 0009](0009-source-built-argon2id-verifier.md),
  [ADR 0015](0015-first-owner-enrollment.md),
  [ADR 0017](0017-state-partition-identity.md)

## Context

ADR 0010 sequence D reserved the forgotten-password recovery-factor
design (its sequence item D and tier 4) for explicit owner approval
before any implementation. The draft specification
(`docs/RECOVERY_FACTOR_SPEC.md`, commit `af50cba`) presented three
design options and enumerated ten owner decisions (D1–D10 in its
section 12).

On 2026-10-27 the project owner was walked through the options and
the decision list in chat and approved, verbatim: **"Approve Option
A with the recommended defaults."** This ADR is the separate approval
record the specification requires (its section 13: gate D is
satisfied by the owner's explicit approval of a specification,
recorded as such). It authorizes implementation of the approved
design; it does not by itself mark tier 4 validated — validation
requires the guest evidence of specification section 11 at an exact
commit, per ADR 0010 gate E.

## Decision — the D1–D10 mapping as approved

- **D1 — Factor design: Option A.** A printed high-entropy recovery
  key whose verifier record is an Argon2id PHC record in a separate
  recovery record slot (specification section 4.1). Options B
  (wrapped capability) and C (hardware token) are not adopted.
- **D2 — Secret strength and format: as proposed.** 256-bit factor
  from operating-system entropy, encoded as grouped Crockford Base32
  with a non-secret check group (specification sections 4.1 and 6).
- **D3 — Custody medium: owner-held paper.** Enrollment offers a
  local print action per specification section 6 — an
  already-configured local printer only, never a network printer
  queue.
- **D4 — Confirmation method: as proposed.** The owner confirms
  recording by re-entering the final check group and a designated
  middle group, plus an explicit on-screen confirmation
  (specification section 6 step 3).
- **D5 — Declining enrollment: completion permitted.** Password
  enrollment MAY complete with no recovery factor enrolled. The
  resulting state is represented persistently and honestly as "no
  recovery factor enrolled — a forgotten password cannot be
  recovered", never as a silent default; later enrollment of a
  factor requires normal authentication (specification sections 6
  step 4 and 7).
- **D6 — Concurrent factors: exactly one.** Rotation revokes the
  previous factor (specification section 7).
- **D7 — Factor after a successful reset: automatically revoked.**
  A factor used for a successful password reset is revoked and must
  be re-enrolled in the new session (specification sections 5 and 9
  step 6, as recommended by the draft).
- **D8 — Installation anchor: per specification section 8's logical
  design.** The installation identifier is generated at first-owner
  enrollment, mixed into the verifier input in the domain-separated
  form `synveil-recovery-v1` ‖ installation identifier ‖ account
  identity ‖ normalized key, and also anchored in the installation
  control metadata outside the STATE credential directory (the same
  class of storage that holds A/B update control state). The exact
  storage and integrity mechanism remains subject to ADR 0010's
  separate review: the implementation must document the mechanism it
  chose and its limits in the validation record, and must not claim
  tier 4 "validated" beyond what the guest evidence shows.
- **D9 — Encrypted user data: login-only recovery accepted.**
  Credential recovery restores the login only; encrypted data whose
  keys are lost stays undecryptable (specification section 1.1). No
  separate data-key recovery design is required before tier 4 is
  implemented.
- **D10 — Hardware token future: not in scope.** A hardware-token
  factor is not part of this design; adding one later would require
  its own separately approved design.

## Rationale

The owner accepted the draft specification's recommendation
(its section 5): Option A is the only option that composes entirely
with primitives the project already has — the source-built Argon2id
verifier and PHC discipline of ADR 0009, STATE-partition credential
records under ADR 0017, and Rust privileged tooling — adding no new
cryptographic construction, no new runtime dependency, no hardware,
and no network service to the recovery environment's trusted base.

## Alternatives considered

Options B and C were presented in the specification (sections 4.2,
4.3, and the comparison in 4.4) and were not chosen, for the reasons
recorded there: B adds a novel wrapping construction and audit
surface with no owner-visible gain; C adds a CTAP/USB stack, a
hardware purchase and custody burden, and a single point of loss.

## Consequences

### Positive

- Tier 4 implementation is unblocked under ADR 0010 sequence D.
- The recovery record reuses the audited verifier family, so normal
  and recovery verification share one set of cost caps, parsers and
  denial semantics, as ADR 0010 and ADR 0009 require.

### Negative / tradeoffs

- The factor is a copyable bearer secret: custody of the printed key
  is entirely the owner's burden, and loss of both the password and
  the key is unrecoverable by design (specification sections 4.1
  and 7).
- The anchor's exact integrity mechanism (D8) is deliberately left
  to ADR 0010's separate review; until that review exists, the
  binding defeats transplantation and state-file-only presentation
  but not an attacker who can rewrite both the STATE credential
  store and the anchor with self-consistent values (specification
  section 8, explicit limits).

## Security implications

Implementation must preserve every hard exclusion of specification
section 1.1: no default token, no factor material in any image, no
network dependency, no password backdoor, no silently enrolled
factor, no AI-authored reset, fail-closed behaviour on corrupt or
mismatched recovery material, and no promise about encrypted user
data. Only synthetic test credentials and factors may be used in
development and validation; no real owner factor is ever generated
outside the owner's own enrollment on the owner's machine.

## Reversibility

The approval can be withdrawn by the owner at any time before a real
factor is enrolled; withdrawing it after implementation would leave
the code inert (no record exists until an owner confirms one at
enrollment). Changing the approved design (a different option, a
different factor format, or a different D1–D10 answer) requires a
new owner decision recorded the same way; the persistent record
format is versioned (`synveil-recovery-v1` binding domain) so a
future design does not silently reinterpret existing records.

## Validation

Specification section 11 lists thirteen tamper and acceptance tests
that must pass in the QEMU guest at an exact commit before tier 4
may be called validated. Until that guest evidence exists and is
recorded, the correct status is "approved and implemented but
unverified", and physical installation remains blocked per ADR 0010
gate E.
