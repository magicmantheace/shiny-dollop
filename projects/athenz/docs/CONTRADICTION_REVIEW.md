# Contradiction candidates and owner adjudication (v0.3)

`athenz-contradiction-review` closes the v0.3 roadmap item "Semantic
contradiction matching and explicit owner adjudication UI". It widens
the older read-only [consistency audit](MEMORY_CONSISTENCY.md) in two
ways: detection covers more opposition shapes across approved identity
records, decisions and episodes, and a candidate can now be **resolved
by the owner** through a recorded adjudication instead of only being
displayed.

Detection proposes; only the owner adjudicates. Nothing in this tool
decides what is true, and nothing changes a record without an explicit
confirmed adjudication.

Run either:

```sh
athenz-contradiction-review scan
athenz-contradiction-review list
athenz-contradiction-review show 3 --confirm
athenz-contradiction-review adjudicate 3 --action confirm --keep a --confirm
athenz-contradiction-review adjudicate 3 --action dismiss --note "both true" --confirm
```

Or open **Desktop → Review memory → Review contradictions…**. The
desktop panel scans on open, lists actionable candidates, shows both
complete records with the matching signals, and applies the same
adjudication actions behind a confirmation dialog.

## What detection matches

Detection is deterministic lexical analysis over **approved** records
only, paired within their own table (identity with identity — and only
within the same kind — decisions with decisions, episodes with
episodes). A pair becomes a candidate only when a topical gate and an
opposition signal both fire:

- **Topical gate** — one of: identical structured slot (below),
  identical marker object, shared episode tags (recorded in the
  signals), or high token overlap (Jaccard ≥ 0.75 over content tokens
  with negation markers removed).
- **`negation-asymmetry`** — the two statements' content tokens are
  near-identical once negation markers are removed, and exactly one
  side is negated. Example: "I exercise every morning" versus "I do
  not exercise every morning".
- **`opposite-preference`** — documented first-person markers with the
  same object and opposite polarity: `I prefer/like/love/enjoy/want/
  choose X` versus `I avoid/dislike/hate/detest/reject X` or the
  negated positive form, plus `I always …` versus `I never …`.
- **`conflicting-slot`** — the same conservatively extracted slot with
  different values:
  - two approved decisions whose scenario token signatures are
    identical but whose choices differ;
  - a reversed preference pair: "prefer A over B" versus
    "prefer B over A";
  - the same `my favourite/favorite <slot> is …` slot with different
    values.

Free-text attribute extraction beyond those three slot shapes is
deliberately **not** attempted: identity and episode records are
free text, so arbitrary "same attribute, different value" claims
would be guesswork. Each candidate stores the pair, the route, the
opposed fragments, the shared tokens/slot and a deterministic score
(route base 0.80–0.90 plus a small overlap term). Candidates live in
the private profile database (`contradiction_candidates`); scanning
again never duplicates a pending candidate for the same pair and
signal, and candidates whose records have been deleted outright are
pruned so erased content does not linger as derived fragments.

Bounds are fail-closed, like the consistency audit: at most 1,500
approved records per table are scanned (a larger pool refuses rather
than scanning partially), a token shared by more than 200 records is
not used as a pairing gate, and one scan creates at most 500 new
candidates.

## Limits — read before trusting a result

- This is lexical matching, **not understanding**. It has no model, no
  embeddings and no notion of meaning beyond the patterns above.
- **False positives are expected.** Temporal change ("I trained
  daily" in 2024, "I do not train daily" in 2026), exceptions, and
  scope differences all look like contradictions to a token matcher.
  That is precisely why every candidate needs owner adjudication.
- **False negatives are guaranteed.** Paraphrases and synonyms
  ("I adore lapsang" versus "I can't stand lapsang"), implicit
  conflicts and multi-record inconsistencies are missed. A clean scan
  is not proof of consistency.

## Adjudication

Actions, each recorded in `contradiction_adjudications` with the
candidate's pair and route as provenance, the actor, the action, the
resolution, the owner's note and the timestamp:

- **confirm --keep a / --keep b** — the owner confirms a real
  contradiction. The losing record is superseded through the existing
  machinery: it leaves the approved set via the same status transition
  and append-only `superseded` event the episode conflict review
  uses, and the adjudication row names the superseded record.
- **confirm --keep-both** — both records stay approved; the note
  records why they coexist (an exception, a temporal change, …).
- **dismiss** — not a contradiction. The pair is not proposed again
  for the same signal.
- **defer** — no decision yet. The candidate stays actionable
  (marked deferred) and its records are untouched.

Safety properties:

- Adjudication requires `--confirm` (CLI) or the confirmation dialog
  (desktop); mutations without it are refused.
- The decision is re-validated inside the write transaction: if
  either record is no longer approved, the candidate is stale and the
  adjudication is refused with no writes.
- A candidate can be adjudicated once into a terminal state
  (confirmed/dismissed); defer keeps it open.
- Un-adjudicated candidates change nothing: no statuses, no events
  on the paired records, no prompt or training effects.
- `list` output is metadata only — ids, route, score, slot label. No
  record text or fragments. `show` prints complete private records
  and requires `--confirm`, following the episode conflict review.

## UI status

Shipped: the store and detection module
(`athenz/contradiction_review.py`), the
`athenz-contradiction-review` CLI, and the desktop **Review
contradictions…** panel in the Review memory tab
(`athenz/contradiction_panel.py`), which follows the existing
consistency-audit/conflict-review panel pattern exactly and is
asserted present by the desktop GUI self-test. There is no remaining
desktop follow-on for this item.
