"""Asset provenance + review records and the candidate store (F5.2).

Migration 4 adds an append-only `reviews` table: who reviewed an
asset, what they decided (`approve` / `reject` / `needs_info`), an
optional note, and when. Reviews are RECORDS ONLY in this slice:

- recording a review never changes an asset's status;
- the ADR-008 promotion gates (`studio/promotion.py`) do not read
  reviews and are completely unaffected by them;
- there is deliberately no update or delete API — a changed mind is
  a new review row, and `latest_review` is how readers see the
  current position.

Wiring review decisions into promotion is explicitly NOT this slice.

`list_candidates` is the quarantined candidate store view: every
asset still at `candidate` status — exactly the assets the ADR-008
resolver refuses to load into the preview — with its F2.1 provenance
(`source` / `license`) and its latest review decision (or
``unreviewed``). An asset leaves the view only when its status
actually changes through the library's status machinery, never
because someone recorded a review.
"""
from __future__ import annotations

from .library import Library

DECISIONS = ("approve", "reject", "needs_info")

UNREVIEWED = "unreviewed"


class ReviewError(ValueError):
    """A review operation was refused, with a named reason."""


def _row_to_review(row) -> dict:
    return {
        "review_id": row["review_id"],
        "asset_id": row["asset_id"],
        "reviewer": row["reviewer"],
        "decision": row["decision"],
        "note": row["note"],
        "created_at": row["created_at"],
    }


def record_review(lib: Library, asset_id: str, reviewer: str,
                  decision: str, note: str | None = None) -> dict:
    """Append a review record for an existing asset; returns it.

    Raises ReviewError for an unknown asset, a decision outside
    DECISIONS, or a blank reviewer. The asset's status is untouched.
    """
    if lib.get_asset(asset_id) is None:
        raise ReviewError(f"unknown asset {asset_id!r}; cannot record a review")
    if decision not in DECISIONS:
        raise ReviewError(
            f"review decision must be one of {DECISIONS}, got {decision!r}")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ReviewError(f"reviewer must be a non-empty string, got {reviewer!r}")
    if note is not None and not isinstance(note, str):
        raise ReviewError(f"review note must be a string, got {note!r}")
    cur = lib.db.execute(
        "INSERT INTO reviews(asset_id, reviewer, decision, note) "
        "VALUES(?,?,?,?)", (asset_id, reviewer, decision, note))
    lib.db.commit()
    row = lib.db.execute(
        "SELECT * FROM reviews WHERE review_id=?",
        (int(cur.lastrowid),)).fetchone()
    return _row_to_review(row)


def latest_review(lib: Library, asset_id: str) -> dict | None:
    """The most recently recorded review for an asset, or None.

    Append order (review_id) decides, not the timestamp: two reviews
    recorded within the same second still order correctly.
    """
    row = lib.db.execute(
        "SELECT * FROM reviews WHERE asset_id=? "
        "ORDER BY review_id DESC LIMIT 1", (asset_id,)).fetchone()
    return _row_to_review(row) if row is not None else None


def review_history(lib: Library, asset_id: str) -> list[dict]:
    """All reviews for an asset, oldest first (append order)."""
    rows = lib.db.execute(
        "SELECT * FROM reviews WHERE asset_id=? ORDER BY review_id",
        (asset_id,)).fetchall()
    return [_row_to_review(row) for row in rows]


def list_candidates(lib: Library) -> list[dict]:
    """The quarantined candidate store: candidate-status assets with
    provenance and latest review decision, sorted by asset_id.

    Each entry is {"asset_id", "kind", "uri", "rig_id", "status",
    "source", "license", "review"} where `review` is the latest
    review's decision, or "unreviewed" when no review exists.
    """
    candidates = []
    for asset in lib.list_assets_full():
        if asset["status"] != "candidate":
            continue
        latest = latest_review(lib, asset["asset_id"])
        candidates.append({
            "asset_id": asset["asset_id"],
            "kind": asset["kind"],
            "uri": asset["uri"],
            "rig_id": asset.get("rig_id"),
            "status": asset["status"],
            "source": asset.get("source"),
            "license": asset.get("license"),
            "review": latest["decision"] if latest else UNREVIEWED,
        })
    return candidates
