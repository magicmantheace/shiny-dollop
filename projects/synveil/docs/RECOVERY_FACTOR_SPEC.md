# Recovery factor specification for forgotten-password recovery

> **DRAFT — AWAITING EXPLICIT OWNER APPROVAL**
>
> This document is a draft specification only. It is submitted to the
> owner for the explicit approval that ADR 0010 reserves for the
> recovery-factor design. **No implementation is authorized by this
> draft**, and no code, enrollment flow, or image change may be made on
> the basis of this document alone. **This document does not modify
> ADR 0010**, does not change its Proposed status, and does not mark any
> ADR 0010 gate complete. If the owner approves a design, that approval
> must be recorded separately before implementation begins.

- Status: Draft — awaiting explicit owner approval; no implementation authorized
- Date: 2026-10-27
- Scope: ADR 0010 tier 4 (forgotten password) only, for future installed
  Synveil systems
- Related: [ADR 0010](adr/0010-independent-owner-recovery.md),
  [ADR 0009](adr/0009-source-built-argon2id-verifier.md),
  [ADR 0015](adr/0015-first-owner-enrollment.md),
  [ADR 0017](adr/0017-state-partition-identity.md)

## 1. Problem statement

ADR 0010 tier 4 addresses one condition only: the owner has forgotten
the password for the single local owner account and is otherwise in
possession of the machine. Tier 4 is distinct from tier 1 (unprivileged
diagnosis), tier 2 (authenticated maintenance), and tier 3 (state or
upgrade recovery). Graphics failure, a failed update, and a corrupt
state volume are not, by themselves, authorization to reset a password.

ADR 0010 requires that forgotten-password recovery:

- use a separately provisioned, high-entropy, owner-retained recovery
  factor established during trusted enrollment;
- be verified offline by the deterministic recovery environment; and
- make rotation and revocation of the factor require normal
  authentication, with any recovery request and any resulting account
  change explicitly confirmed and auditable.

ADR 0010 explicitly leaves the exact secret format, custody method,
credential-reset authority, and cryptographic binding to the installation
unresolved, pending an explicit owner-approved design. This draft is
that design proposal. It proposes; it does not decide.

### 1.1 What recovery must NOT do

The following are hard exclusions, taken from ADR 0010 and restated here
so that no option below can be read as permitting them:

- **No default token.** There is no factory, shared, test, or fallback
  recovery secret of any kind.
- **No factor material in the public image.** No recovery secret,
  recovery verifier record for a real owner, wrapped recovery
  capability, or recovery public key for a real owner ships in any
  public or test-media image. Factor material is created on the
  owner's machine, during the owner's enrollment, and nowhere else.
- **No network dependency.** Enrollment, verification, rotation, and
  recovery work fully offline. No cloud account, email reset, remote
  server, or network service participates at any point.
- **No password backdoor.** The recovery path is not a second, weaker
  way in. It verifies its own factor, through its own record, and can
  perform only the credential-reset operation defined in this
  specification. It is not a shell, a generic privileged command
  runner, or an alternate login for the ordinary password.
- **No silently enrolled factor.** A factor exists only if the owner
  saw it, recorded it, and explicitly confirmed that recording during
  trusted enrollment (see section 6). Enrollment code must never
  generate a factor the owner was not shown.
- **No AI-authored reset.** No model, planner, or AI component can
  create, approve, perform, or assert a password reset. Model output
  is not a recovery assertion, in line with ADR 0009's rule that model
  output is not a login assertion.
- **A corrupt state volume must not weaken the requirement.** If the
  STATE partition or the credential store on it is corrupt, missing,
  or cannot be authenticated, recovery verification fails closed.
  Corruption must not make an ordinary password sufficient to authorize
  a reset, and a copied state file alone must not be sufficient to
  authorize recovery on another installation (see section 8).
- **No promise about encrypted user data.** If user data is encrypted
  with keys that are lost, or that are bound to a forgotten password
  in a way this design does not preserve, recovery of the login
  credential does not decrypt that data. This specification claims
  credential recovery only, never data recovery.

### 1.2 Non-goals

- This draft does not design tiers 1–3 of ADR 0010, the installer,
  verified or signed boot, recovery-image authenticity, or
  anti-rollback. Those remain separate gates in ADR 0010.
- This draft does not change the ordinary password verifier, its
  Argon2id parameters, or its record format (ADR 0009).
- This draft does not introduce multi-user recovery. Synveil's initial
  credential record is one local owner account (ADR 0009, ADR 0015).

## 2. Constraints inherited from existing decisions

Every option in section 4 must satisfy all of the following:

1. **Verifier primitive.** Password verification is the source-built
   Argon2id verifier of ADR 0009: Argon2id v=19, RustCrypto `argon2`
   with its typed PHC parser, default work factor 64 MiB memory, three
   passes, one lane, at least 16 unpredictable bytes of salt, strict
   caps on encoded cost and field lengths enforced before hashing, and
   corrupt or unavailable records treated exactly as denial. An option
   that needs a new cryptographic primitive must say so explicitly and
   count it as a cost.
2. **STATE-partition records.** Credential records live on the STATE
   partition identified by ADR 0017 (GPT partition name
   `Synveil State`, designated PARTUUID, ext4 label `SYNVEIL_STATE`),
   resolved by identity rather than device name, in a root-owned
   mode-0700 directory, as mode-0600, single-link records, with
   symlinks and pre-existing untrusted files refused. The recovery
   record is a separate record in that store, never a field added to
   the password record.
3. **Enrollment authority.** There is one authoritative owner
   credential path (ADR 0015). Recovery enrollment slots into the
   first-owner enrollment flow of ADR 0015; it does not create a
   second, competing credential authority, a LightDM/`/etc/shadow`
   password, or a parallel account.
4. **Recovery environment.** Verification runs in the deterministic,
   local, explicit recovery environment described by ADR 0010:
   entered deliberately at boot, independent of the compositor, seat
   broker, network, and inference engine, and sharing the same trusted
   credential verification rules as the normal session path while
   keeping its service lifecycle independent. Recovery must not rely
   on GPU acceleration, a local model, a cloud service, or a healthy
   desktop.
5. **Privileged tooling language.** New privileged tooling is Rust,
   per the project AGENTS.md preference for Rust in privileged
   services, policy code, IPC, and system tooling. Any option requiring
   substantial new non-Rust trusted code counts that as a cost.
6. **Fail closed.** Missing, corrupt, ambiguous, or mismatched
   recovery material is a denial, with read-only diagnostics (ADR 0010
   tier 1) as the only offer. No path initializes, reformats, or
   guesses a block device.

## 3. Terminology

- **Recovery factor:** the owner-retained secret or device presented
  in the recovery environment to authorize a password reset.
- **Recovery record:** the verifier material stored on the STATE
  partition against which the factor is checked. The record never
  contains the factor itself in recoverable form under options A or B,
  and contains only a public key under option C.
- **Installation binding:** data that ties a recovery record to this
  installation's credential store, so the record and factor do not
  work when transplanted to another installation (section 8).
- **Trusted enrollment:** the first-owner enrollment of ADR 0015,
  running locally on the owner's machine before any ordinary desktop
  session exists.

## 4. Design options

Three options are presented. Each subsection states the secret format
and entropy, where the verifier material lives, how offline
verification works in the initramfs recovery environment, strengths,
weaknesses, and what the option does **not** protect against.

### 4.1 Option A — Printed recovery key with an Argon2id verifier record

The factor is a random key the owner writes down or prints. Its
verifier record is an Argon2id PHC record, produced by the same
source-built verifier family as the password record, but stored in a
separate record slot reserved for recovery.

- **Secret format / entropy.** 256 bits generated from operating-system
  entropy (the kernel CSPRNG, as ADR 0009 enrollment already uses) at
  enrollment time, encoded for transcription as grouped Crockford
  Base32: 52 characters in groups of four, separated by hyphens, plus
  a final check group computed from the key by a non-secret checksum
  so a transcription error is caught locally before hashing. The check
  group is an error-detection aid only; it contributes no entropy and
  no security. No word list is introduced.
- **Where the verifier material lives.** A separate recovery record
  slot in the same root-owned credential directory on STATE as the
  password record (for example, a distinctly named single record file
  beside the password PHC record), mode 0600, single link, written
  atomically. The record contains the PHC string (Argon2id algorithm,
  version, cost parameters, a fresh per-factor salt of at least 16
  bytes, and the resulting hash), the record generation counter, and
  the installation-binding data of section 8. The factor itself is
  never written to any file.
- **Offline verification in the recovery environment.** The recovery
  environment resolves STATE by its ADR 0017 identity, mounts it,
  loads the recovery record, and strictly validates the PHC algorithm,
  version, and encoded cost caps before hashing, exactly as ADR 0009
  requires for the password record. The owner types the key on the
  local console with non-echoing input; the implementation normalizes
  the encoding (case, grouping, check group), rejects a bad check
  group as a transcription error without consuming an attempt, and
  otherwise computes Argon2id over the normalized key material
  combined with the installation-binding context of section 8, using
  the salt and parameters from the record. The outcome returned is
  only verified or denied. Failed attempts are throttled per boot and
  across boots by a persistent attempt counter in the recovery record
  area; a corrupt or unavailable record is a denial. On success, and
  only after the separate explicit confirmation of section 9, the
  environment may replace the password record.
- **Strengths.** It composes entirely with primitives the project
  already has: the pinned Argon2id verifier, PHC parsing and cost
  caps, STATE-partition records, and Rust privileged tooling. It adds
  no new cryptographic construction, no new runtime dependency, no
  hardware, and no network service. The trusted code added to the
  recovery environment is the smallest of the three options. Because
  the factor carries 256 bits of entropy, exposure of the verifier
  record does not enable a practical offline guessing attack against
  the factor, unlike a human-chosen password.
- **Weaknesses.** The factor is a bearer secret: anyone who obtains
  the written key and has the machine can reset the password. Custody
  is entirely the owner's burden; a photographed, copied, or poorly
  stored printout is fully equivalent to the original. Transcription
  of 52 characters is slow and error-prone even with grouping and a
  check group. Revocation is impossible while locked out (section 7).
- **What it does NOT protect against.** Theft or copying of the
  printed key; loss of both the password and the key (recovery is
  then impossible, by design); corruption or destruction of the STATE
  partition, which destroys the record; an attacker who can rewrite
  both the recovery record and its installation anchor, who can simply
  substitute their own factor (record and anchor integrity is a
  separate, separately reviewed problem, as ADR 0010 notes); a
  malicious or substituted recovery image (image authenticity is a
  separate release gate); or loss of encrypted user data whose keys
  are gone (section 1.1).

### 4.2 Option B — Recovery key as an unwrap share for a wrapped reset capability

The factor is again a printed random key, but there is no Argon2id
record of the key itself. Instead, enrollment creates a random
credential-reset capability — in effect, authority to replace the
password record exactly once — and stores it wrapped (encrypted) under
a key derived from the recovery key. Presenting the correct key is
proven by successfully unwrapping the capability.

- **Secret format / entropy.** Same presentation as option A: 256 bits
  from operating-system entropy, encoded as grouped Crockford Base32
  with a non-secret check group, so owner custody behaviour is
  identical across options A and B.
- **Where the verifier material lives.** A wrapped-capability record
  in the separate recovery slot on STATE: the key-derivation
  parameters and salt (Argon2id, if Argon2id is the chosen derivation
  function), a nonce, and the authenticated-encryption ciphertext of
  the reset capability, together with the generation counter and the
  installation-binding data of section 8, which is also bound into the
  wrapped data as associated data so a transplanted blob fails to
  unwrap. There is no hash of the factor to compare against; the
  unwrapped capability, or its failure to unwrap, is the verdict.
- **Offline verification in the recovery environment.** The recovery
  environment loads the wrapped record from STATE, derives the
  unwrapping key from the typed factor and the stored salt and
  parameters, and attempts authenticated decryption of the capability
  with the installation-binding data as associated data. Successful
  unwrapping with a valid authentication tag is the verified outcome;
  any failure — wrong key, corrupt blob, wrong installation — is a
  single undifferentiated denial. The unwrapped capability then
  authorizes exactly the one enumerated operation: replacement of the
  password record for the fixed owner account, after explicit
  confirmation, followed by destruction of the capability and an
  audit entry (section 9). Attempt throttling applies as in option A;
  unwrapping failures must be at least as expensive as option A's
  Argon2id verification so throttling cannot be bypassed by cheap
  trials.
- **Strengths.** Authorization is a capability, not a comparison: the
  recovery environment never holds a reusable verifier for the factor,
  and the capability can carry its own generation and single-use
  semantics, so a used or superseded capability is void by
  construction. Binding the installation context as associated data
  makes cross-installation transplantation fail inside the
  cryptography rather than by a surrounding check. Rotation can
  re-wrap a fresh capability without changing the password record's
  format.
- **Weaknesses.** This option introduces a cryptographic construction
  the project does not currently have: an authenticated-encryption
  scheme, a key-derivation composition, nonce generation and storage,
  and capability semantics, all inside the initramfs trusted base,
  all requiring separate review. That is a materially larger audit
  surface than option A and a new runtime dependency decision for the
  trusted control plane. Failure modes are subtler: a nonce or
  associated-data error can silently void every enrolled factor.
  Owner-visible behaviour is identical to option A, so the owner gains
  no usability in exchange for this complexity.
- **What it does NOT protect against.** Everything option A does not
  protect against: theft or copying of the printed key (the key plus
  the wrapped blob, which sits on the machine, is sufficient);
  loss of both password and key; STATE corruption, which destroys the
  only copy of the wrapped capability; record-and-anchor substitution
  by an attacker who can rewrite STATE; a malicious recovery image;
  and loss of encrypted user data whose keys are gone. It also does
  not protect against a flaw in the new wrapping construction itself,
  which option A does not have because it has no such construction.

### 4.3 Option C — Hardware token (WebAuthn/FIDO2-style second factor)

The factor is a hardware authenticator. Enrollment registers the
token's public key; recovery requires a signature from the token over
a fresh challenge issued by the recovery environment.

- **Secret format / entropy.** There is no printed secret. The token
  internally generates a per-installation asymmetric key pair; the
  private key never leaves the token. Entropy and key generation are
  the token vendor's, not Synveil's, and are not inspectable by this
  project. Custody is custody of a physical object, optionally plus a
  token PIN.
- **Where the verifier material lives.** A separate recovery record
  slot on STATE containing only public material: the credential
  identifier, the public key, the registered installation-binding
  identifier (used as, or bound into, the relying-party identifier),
  and the signature counter. No secret is stored on the machine.
- **Offline verification in the recovery environment.** The recovery
  environment generates a fresh random challenge from operating-system
  entropy, asks the token over USB (CTAP/HID) to sign the challenge
  for the registered credential and installation identifier, and
  verifies the returned signature against the stored public key,
  checks the signature counter has not regressed, and requires a PIN
  verification or user-presence confirmation as registered. All of
  this must work with no network, no browser, and no WebAuthn server:
  the recovery environment itself must contain the transport, the
  protocol implementation, and the verification code.
- **Strengths.** The private key is non-exportable and cannot be
  photographed or copied from a printout; there is no bearer text to
  leak. A stolen verifier record yields only a public key. Per-attempt
  guessing is not applicable, and token PIN throttling, where the
  token supports it, is enforced by hardware.
- **Weaknesses.** This is the largest option by far: a CTAP/HID stack,
  USB device handling, and signature verification must be added to the
  deterministic initramfs recovery environment, none of which the
  project currently has, and much of it does not fit the Rust
  privileged-tooling preference as existing, auditable components.
  It requires the owner to buy, keep, and carry specific hardware;
  makes recovery depend on that hardware working, on USB behaviour in
  the recovery environment, and on vendor behaviour this project
  cannot audit. A single registered token is a single point of loss:
  lose the token while locked out and recovery is impossible, so a
  safe deployment would need two tokens enrolled, doubling cost and
  custody burden. Accessibility and replacement are owner problems
  this design cannot soften.
- **What it does NOT protect against.** Loss of the token (with no
  second token, lockout is total); theft of the token together with
  its PIN; STATE corruption, which destroys the public-key record;
  record substitution by an attacker who can rewrite STATE and the
  installation anchor (they register their own token); a malicious
  recovery image; and loss of encrypted user data whose keys are gone.
  It also does not protect against vendor or firmware failure of the
  token itself.

### 4.4 Comparison summary

| | A: Argon2id record | B: Wrapped capability | C: Hardware token |
|---|---|---|---|
| New cryptographic construction | None | Yes — AEAD wrap + capability | Yes — asymmetric + CTAP |
| New trusted code in recovery environment | Smallest | Medium | Largest |
| New runtime dependency | None | AEAD/KDF crates | CTAP/USB stack |
| Owner must obtain hardware | No | No | Yes |
| Factor can be copied by photograph | Yes | Yes | No |
| Works if owner loses the factor carrier | No | No | No (unless 2nd token) |
| Fits ADR 0009 verifier as-is | Yes | Partly (derivation only) | No |
| Record theft enables offline guessing | No (256-bit factor) | No (256-bit factor) | Not applicable |

## 5. Recommendation

**Option A — a printed high-entropy recovery key whose verifier record
is an Argon2id PHC record in a separate recovery record slot — is
recommended.**

Reasoning:

1. It is the only option that composes with primitives the project has
   already chosen and is already building: the source-built Argon2id
   verifier and PHC discipline of ADR 0009, STATE-partition credential
   records under ADR 0017, and Rust privileged tooling. ADR 0010 and
   ADR 0009 both require normal and recovery verification to share the
   same trusted verification rules; option A satisfies that literally,
   with one verifier family and one set of cost caps, parsers, and
   denial semantics to audit.
2. It adds no new network or cloud dependency, no new cryptographic
   construction, and no hardware dependency, keeping the initramfs
   recovery trusted base as small as the current architecture allows.
   Options B and C each enlarge that base — B with a novel wrapping
   construction, C with a protocol and transport stack — without
   improving the owner-visible outcome for the single-owner,
   single-machine case ADR 0010 tier 4 addresses.
3. Its principal weakness, that the factor is a copyable bearer secret,
   is shared by option B and is mitigated, not eliminated, by option C
   at the cost of hardware loss risk. For a single owner retaining a
   printed key with their other physical recovery material, the
   residual risk is explicit and understandable, and this draft states
   it rather than designing around it with unreviewed machinery.
4. Option B remains a credible future evolution — for example if
   single-use capability semantics are later required — and option C
   remains a credible future *additional* factor. Neither is needed to
   satisfy tier 4, and adopting option A now does not silently enrol
   either of them later; each would need its own owner-approved design.

This recommendation is part of the draft. It takes effect only if the
owner approves it (decision D1 in section 11).

## 6. Custody flow at enrollment

The custody step slots into the first-owner enrollment flow of
ADR 0015, after the owner's password has been entered, confirmed, and
its record committed, and before enrollment is reported complete.
The steps, in order:

1. **Separate, explicit step.** After password enrollment, the
   enrollment interface states, in plain language, that a recovery key
   is about to be created, that it will be shown exactly once, that it
   is the only way to reset a forgotten password, and that Synveil
   cannot show it again or replace it while the owner is locked out.
   The owner must explicitly choose to proceed. Generation never
   happens as a side effect of password enrollment.
2. **Generation and single display.** The factor is generated from
   operating-system entropy inside the trusted enrollment context,
   displayed once on the local screen in its grouped encoding, with a
   print action offered if a local printer is already configured.
   The factor is never sent to a network printer queue by this flow,
   never written to disk, a log, shell history, browser data,
   telemetry, or AI memory, and intermediate buffers are cleared when
   the step ends, consistent with ADR 0015's protections for the
   password itself.
3. **Owner confirmation of recording.** Enrollment does not proceed
   until the owner confirms the key is recorded, by re-entering the
   final check group and a designated middle group of the key (a
   transcription check that the key in hand matches the key shown,
   without re-typing all 52 characters), and by an explicit on-screen
   confirmation that they have recorded the complete key. Only after
   this confirmation is the recovery record computed and atomically
   committed to its STATE slot. The confirmation event — not the key —
   is audit-logged (section 9).
4. **If the owner declines.** If the owner declines at step 1, no
   factor is generated and no recovery record is written. Whether
   password enrollment may still complete in that state is an owner
   decision (D5 in section 11). Under either answer, the resulting
   state must be represented honestly and persistently as "no recovery
   factor enrolled — a forgotten password cannot be recovered", never
   as a silent default, and a later enrollment of a factor is possible
   only after normal authentication (section 7).
5. **If the owner loses the key before confirmation.** If the owner
   reports, before confirming, that the displayed key was not recorded
   or was lost, the unconfirmed factor is discarded: it was never
   committed, so nothing needs revoking. A fresh factor is generated
   and displayed instead, returning to step 2. There is no limit
   benefit to an attacker here — no record exists until a confirmation
   commits one — but the interface must not accumulate discarded keys
   on screen, in scrollback, or in any buffer that survives the step.
6. **No re-display, ever.** After the confirmation in step 3, no
   interface — enrollment, desktop settings, maintenance, or recovery —
   may display the factor again. This is a property of the design, not
   a policy promise: under option A only the Argon2id record is stored,
   so the factor cannot be re-derived or re-shown by any Synveil
   component. Interfaces may show only that a factor is enrolled, its
   generation counter, and the date it was enrolled or last rotated.

## 7. Rotation and revocation

Rotation and revocation are the same operation in this design: replacing
the recovery record so the previous factor no longer verifies. Per
ADR 0010, both require **normal authentication** — a logged-in owner
session, or authentication through the ordinary password verifier in
the maintenance environment. The recovery factor itself can never
authorize its own replacement outside the password-reset flow of
section 9, and no AI component can request or perform a rotation.

- **What rotates, under the recommended option A.** Exactly one thing:
  the recovery record in its separate STATE slot. Rotation generates a
  fresh factor (fresh 256-bit value), a fresh salt of at least 16
  bytes, and a fresh Argon2id PHC record; increments the generation
  counter; and atomically replaces the old record. The old factor is
  denied from that moment. The password record does not change unless
  the owner separately changes the password. (Under option B, rotation
  would instead destroy the old wrapped capability and wrap a fresh
  capability under a fresh factor; under option C, it would replace
  the registered public key and credential identifier. The
  owner-visible flow is the same.) Custody for the new factor follows
  section 6 steps 2–3 exactly: single display, owner confirmation of
  recording, and only then atomic replacement — so a failed or
  abandoned rotation leaves the previous factor in force, never a
  half-rotated state with no valid factor.
- **Audit entries.** Rotation writes audit entries for the request
  (authenticated identity, timestamp, prior generation), the owner's
  explicit confirmation, and the completion (new generation), in the
  same durable audit discipline as other privileged actions. Entries
  contain no factor material, no hash, and no salt.
- **Lost factor while logged in.** This is the recoverable case. The
  owner, normally authenticated, rotates as above. The lost factor is
  revoked by the replacement. Usability of the machine was never lost;
  only the recovery safety net was, until rotation restores it.
- **Lost factor while locked out.** This is the unrecoverable case,
  and this draft states it without softening: with the password
  forgotten *and* the factor lost, there is no recovery. No Synveil
  component may reset the password, rotate the factor, or enrol a new
  factor in that state. The only offers are read-only diagnostics
  (ADR 0010 tier 1) and whatever reinstallation path exists outside
  this specification, with the data consequences that implies.

## 8. Cryptographic binding to the installation

A recovery factor and its record must work on this installation and
fail everywhere else. Two distinct attacks are addressed:

- **Transplant attack:** a recovery record copied from installation X
  is placed on installation Y, and X's factor is presented on Y.
- **State-file attack:** a copy of this installation's STATE credential
  files is presented to a recovery environment as sufficient
  authorization on its own. ADR 0010 forbids this outcome: a copied
  state file must not be sufficient.

The binding design proposed here, for the recommended option A, is:

1. **Installation identifier.** At first-owner enrollment, the trusted
   enrollment context generates a random installation identifier of
   256 bits from operating-system entropy. It is not derived from
   hardware serial numbers, is not a secret by itself, and is never
   the PARTUUID: ADR 0017 is explicit that the STATE PARTUUID is a
   role label, not a secret and not a signature, so it cannot serve
   as the binding value.
2. **Binding inside the verifier input.** The recovery record's
   Argon2id computation is performed not over the recovery key alone
   but over a domain-separated encoding that includes the installation
   identifier and the fixed owner account identity — in form:
   `synveil-recovery-v1` ‖ installation identifier ‖ account identity
   ‖ normalized recovery key. The PHC record stores the parameters and
   salt as usual. A record transplanted to another installation is
   therefore checked against the wrong binding context and fails,
   even if every other field is intact, because the recovery
   environment recomputes with *its* installation's identifier.
3. **Independent anchor.** The installation identifier is also stored
   in a second location independent of the STATE credential directory:
   in the installation's control metadata outside STATE (the same
   class of storage that holds A/B update control state), written at
   enrollment and read by the recovery environment before verification.
   Verification requires the identifier in the recovery record, the
   identifier in the anchor, and the identifier used in the Argon2id
   recomputation to be one and the same value. This is the "independent
   trust anchor" whose storage and integrity design ADR 0010 requires
   to be separately reviewed; this draft proposes its logical role and
   placement class, and the exact storage and integrity mechanism
   remains subject to that review and to owner decision D8.
4. **Consequences.** Presenting only a copied STATE credential
   directory fails, because the anchor is absent or belongs to a
   different installation. Presenting another installation's complete
   record fails, because its binding context differs. Presenting this
   installation's factor on another installation fails, because that
   installation's record was computed under a different identifier.

**Interaction with STATE corruption.** If STATE is corrupt, the record
is unavailable or fails strict parsing, and verification is denied —
full stop. The anchor does not become a fallback verifier: the anchor
holds no hash and cannot verify a factor by itself. If the anchor is
corrupt or disagrees with the record, verification is likewise denied,
even if the presented factor is genuine; the recovery environment
offers read-only diagnostics only, and must not initialize, reformat,
or "repair" either store as part of a recovery attempt. This is a
deliberate availability cost: integrity disagreement is treated as
tampering until a normally authenticated owner resolves it, and a
locked-out owner in that state has diagnostics, not recovery.

**Explicit limits of the binding.** The binding defeats transplantation
and state-file-only presentation. It does not defeat an attacker who
possesses the owner's factor *and* this machine — that combination is
the intended authorization. It does not defeat an attacker who can
rewrite both STATE and the anchor with self-consistent values of their
own; preventing that requires the anchor integrity mechanism and,
ultimately, the verified-boot gates that ADR 0010 keeps separate.
This draft does not claim otherwise.

## 9. Using the factor: the password-reset flow

For completeness, the flow this factor exists to serve, stated so the
owner approves the authority, not just the secret:

1. The owner explicitly selects the recovery entry at boot. Boot
   failure alone never enters this flow (ADR 0010).
2. The recovery environment resolves and mounts STATE by its ADR 0017
   identity, loads the recovery record and the anchor, and checks the
   binding agreement of section 8 before accepting any input.
3. The owner enters the recovery factor locally, with non-echoing
   input, subject to the throttling of section 4.1.
4. On a verified outcome, the environment displays exactly what will
   happen — the password for the fixed owner account will be replaced;
   user data will not be touched — and requires a separate explicit
   confirmation before anything changes.
5. The owner enters and confirms a new password, subject to the same
   entry protections as ADR 0015 enrollment. The password record is
   atomically replaced through the same credential authority.
6. The recovery event, the verification outcome, and the password
   record replacement are audit-logged (section 10), with no secret
   material. Whether the used factor remains valid after a successful
   reset, or is automatically revoked and must be re-enrolled in the
   new session, is owner decision D7; this draft recommends automatic
   revocation, so a factor that may have been observed during recovery
   does not remain a standing reset authority.
7. The user-data partition is not mounted for writing, migrated, or
   otherwise altered by any step of this flow.

## 10. Audit requirements

The following events must produce durable audit entries, in the
project's existing audit discipline for privileged actions
(initiating cause, parameters in non-secret form, result), and must
never contain the factor, the password, any hash, or any salt:

- recovery factor enrollment confirmed (generation, timestamp);
- recovery factor enrollment declined, and each discarded unconfirmed
  factor (count only);
- recovery verification attempt: denied (including corrupt record,
  binding mismatch, and throttling lockout, distinguished by category
  but never by factor-dependent detail) and verified;
- password reset by recovery: explicit confirmation recorded, password
  record replaced, and factor retained or revoked per decision D7;
- recovery factor rotation requested, confirmed, and completed
  (prior and new generation);
- recovery attempted with no factor enrolled.

Audit entries are written to the same protected store discipline as
other credential events; a recovery flow that cannot write its audit
entries must not proceed with the reset.

## 11. Tamper and acceptance tests required before validation

Host fixtures alone are not validation. Per ADR 0010 gate E,
implementation of this design may be called validated only when guest
QEMU evidence exists at an exact commit, recorded with the complete
guest evidence for that commit. The following tests are required, and
each must pass in the guest, not only on the host:

1. **Wrong factor denied.** A syntactically valid but incorrect
   recovery key is denied, no session or reset capability is produced,
   the attempt is throttled, and the denial is audit-logged.
2. **Correct factor succeeds, once.** The enrolled factor verifies,
   the explicit confirmation is required before any change, and the
   new password — and only the new password — then opens a normal
   non-root session after a cold reboot.
3. **Factor from another installation denied.** Two installations with
   distinct installation identifiers are enrolled; each installation's
   factor and record are presented to the other, in both directions,
   and all cross-presentations are denied.
4. **Copied state file insufficient.** Only the STATE credential
   directory of an installation is copied to a fresh recovery
   environment (no matching anchor); recovery is denied even with the
   genuine factor.
5. **Corrupt verifier record denied.** The recovery record is
   corrupted in representative ways (bit flip in the hash, inflated
   encoded cost parameters, truncated PHC string, wrong permissions,
   symlink substitution); every case is denied without a crash,
   without a resource-exhaustion hang, and without any fallback path
   opening.
6. **Corrupt or mismatched anchor denied.** The installation anchor is
   removed, corrupted, or replaced with another installation's value;
   verification is denied even with the genuine factor and an intact
   record, and no store is initialized or reformatted in response.
7. **Revoked factor denied after rotation.** A factor is enrolled,
   then rotated under normal authentication; the old factor is denied
   and the new factor verifies, across a cold reboot.
8. **Used factor behaves as decided.** After a successful reset, the
   used factor's subsequent status matches decision D7 (denied, if
   automatic revocation is approved; verified, if retention is
   approved).
9. **Recovery audit entries present.** After enrollment, a denied
   attempt, a successful reset, and a rotation, the audit store
   contains entries for each event with the fields of section 10 and
   no secret material anywhere in the log.
10. **No serial bypass.** With the recovery flow armed and at every
    stage of it, the locked serial console executes no root commands,
    and there is no path from the serial console, a kernel argument,
    or the test-only developer override to a password reset.
11. **Recovery does not alter the user-data partition.** The DATA /
    user-home partition's contents are hashed before and after a
    denied attempt, a successful reset, and a rotation; the hashes are
    identical in all three cases.
12. **No factor re-display.** After enrollment, every interface that
    reports recovery status is exercised and shows enrollment state,
    generation, and dates only; no interface returns the factor, and
    logs and state files contain no factor or factor-derived plaintext.
13. **No network required or used.** The complete enrollment,
    verification, reset, and rotation flows are exercised with
    networking absent, and succeed or fail identically to the networked
    case.

Until guest evidence for these tests exists at an exact commit, the
correct status for any implementation of this design is "implemented
but unverified", and physical installation remains blocked in line
with ADR 0010 gate E.

## 12. Open questions for the owner — decision list

Nothing in this section is decided by this draft. Implementation may
not begin until the owner has answered each decision, and the answers
must be recorded outside this draft's own claims. Each item is phrased
as the choice the owner must make:

- **D1 — Factor design:** Choose Option A (printed recovery key with an Argon2id verifier record, recommended), Option B (printed recovery key unwrapping a wrapped credential-reset capability), Option C (hardware-token / WebAuthn-style factor), or reject all three options.
- **D2 — Secret strength and format:** For Options A or B, approve the proposed 256-bit factor encoded as grouped Crockford Base32 with a non-secret check group, or specify a different entropy or encoding.
- **D3 — Custody medium:** Choose whether the owner records the factor on paper only, on paper plus a second owner-held copy in a separate location, or by another owner-specified medium — and whether Synveil may offer a local print action during enrollment.
- **D4 — Confirmation method:** Choose how the owner confirms recording at enrollment: re-entering the check group plus a designated middle group as proposed, re-entering the complete factor, or an explicit on-screen attestation without re-entry.
- **D5 — Declining enrollment:** Choose whether password enrollment may complete with no recovery factor enrolled (with a persistent "forgotten password cannot be recovered" state), or whether first-owner enrollment must not complete until a recovery factor is enrolled and confirmed.
- **D6 — Concurrent factors:** Choose whether exactly one recovery factor is active at a time (rotation revokes the previous factor, as proposed), or whether two concurrently valid factors are permitted.
- **D7 — Factor after a successful reset:** Choose whether a factor used for a successful password reset is automatically revoked and must be re-enrolled in the new session (recommended), or remains valid until rotated.
- **D8 — Installation anchor storage:** Choose the storage location and integrity mechanism for the installation-binding anchor outside the STATE credential directory, or direct that it receive a separate design review before any implementation.
- **D9 — Encrypted user data:** Choose whether credential recovery is accepted as login-only (encrypted data whose keys are lost stays undecryptable, as stated in this draft), or whether a separate data-key recovery design must be specified and approved before tier 4 is implemented.
- **D10 — Hardware token future:** Choose whether a hardware-token factor may later be added as an optional additional factor under a separate owner-approved design, or whether hardware-token recovery is excluded for the foreseeable design.

## 13. Explicit non-decision

This draft does not approve or implement password resets, recovery-key
enrollment, a recovery-factor verifier, an installation anchor, factor
rotation, a physical installer, serial-root access, or an AI emergency
bypass. It does not modify ADR 0010, ADR 0009, ADR 0015, or ADR 0017,
and it does not satisfy ADR 0010 gate D by itself: gate D is satisfied
by the owner's explicit approval of a specification, recorded as such,
not by the existence of this draft. Until that approval exists, the
correct description of Synveil forgotten-password recovery remains the
one in ADR 0010: proposed, unresolved, and unimplemented.
