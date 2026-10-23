"""Versioned highlight scoring calibration for the base Underreach Alpha runtime.

The accepted 30.5.3 scorer was designed for the richer social/survival event
vocabulary available in later Underreach slices.  The base Alpha runtime emits
simpler but still narratively meaningful compound sequences such as encounter
trigger -> combat -> defeat -> reward -> progression.  This module preserves the
30.5.3 tier thresholds and authority boundary while adding deterministic floors
for those compound Alpha signals.

The calibration is deliberately a separate scoring policy.  Existing persisted
30.5.3 highlights are never rewritten under a different score identity.
"""
from __future__ import annotations

from typing import Any

from pydantic import ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import underreach_highlight_story_arc as base
from .runtime_checkpoint import payload_digest
from .underreach_media_event_export import MediaEnvelope
from .underreach_media_foundation import MediaEnvelopeRow, MediaPersistence


ALPHA_SCORING_PROFILE = "underreach.alpha-highlight-calibration.v1"


class AlphaHighlightPolicy(base.HighlightPolicy):
    """30.5 thresholds plus a digest-visible Alpha scoring identity."""

    model_config = ConfigDict(frozen=True)

    scoring_profile: str = ALPHA_SCORING_PROFILE


def _types(envelope: MediaEnvelope) -> tuple[str, ...]:
    return tuple(str(value).upper() for value in envelope.source_event_types)


def _has_any(types: tuple[str, ...], markers: tuple[str, ...]) -> bool:
    return any(any(marker in event_type for marker in markers) for event_type in types)


def _count_any(types: tuple[str, ...], markers: tuple[str, ...]) -> int:
    return sum(1 for event_type in types if any(marker in event_type for marker in markers))


def _active_party_context(envelope: MediaEnvelope) -> bool:
    context = envelope.party_context if isinstance(envelope.party_context, dict) else {}
    return bool(context.get("parties") or context.get("alliances"))


def _raise_floor(
    components: dict[str, int],
    reasons: list[str],
    component: str,
    floor: int,
    reason: str,
) -> None:
    bounded = max(0, min(base.SCORE_MAXIMA[component], int(floor)))
    if bounded > components[component]:
        components[component] = bounded
        reasons.append(reason)


def score_alpha_envelope(envelope: MediaEnvelope) -> tuple[base.HighlightScore, tuple[str, ...]]:
    """Re-score one immutable envelope for the event vocabulary emitted by Alpha.

    The original component scores remain the baseline.  Calibration only raises
    components when the envelope itself contains deterministic evidence for a
    compound story beat; it never uses an LLM, provider output, wall-clock state,
    or presentation feedback.
    """

    original, original_reasons = base.score_envelope(envelope)
    components = original.model_dump(mode="python", exclude={"total"})
    reasons = list(original_reasons)
    types = _types(envelope)

    combat_action = _has_any(types, ("COMBAT_HIT", "COMBAT", "ATTACK", "DAMAGE"))
    combat_hits = _count_any(types, ("COMBAT_HIT", "ATTACK", "DAMAGE"))
    enemy_defeated = _has_any(types, ("ENEMY_DEFEATED", "VICTORY", "ENEMY_KILLED", "KILL"))
    combat_resolved = _has_any(types, ("COMBAT_ENDED", "ENCOUNTER_RESOLVED"))
    encounter_triggered = _has_any(types, ("ENCOUNTER_TRIGGERED", "COMBAT_STARTED"))

    # Alpha does not normally emit BOSS/NEAR_DEATH labels for ordinary resolved
    # fights.  A complete, multi-hit encounter with a canonical defeat/resolution
    # is nevertheless substantially stronger than a lone COMBAT marker.
    if combat_action and enemy_defeated and combat_resolved:
        _raise_floor(
            components,
            reasons,
            "danger",
            16 if combat_hits >= 2 else 14,
            "danger:alpha_resolved_combat_sequence",
        )
    elif combat_action and enemy_defeated:
        _raise_floor(components, reasons, "danger", 13, "danger:alpha_combat_victory")

    acquisition_count = _count_any(types, ("ITEM_ACQUIRED", "LOOT_ACQUIRED", "GROUND_LOOT_ACQUIRED"))
    if acquisition_count >= 2 and components["rarity"] >= 6:
        _raise_floor(components, reasons, "rarity", 8, "rarity:alpha_multiple_meaningful_rewards")

    party_formed = _has_any(types, ("PARTY_FORMED", "ALLIANCE_FORMED"))
    active_party = _active_party_context(envelope)
    if party_formed:
        _raise_floor(components, reasons, "social_stakes", 12, "social:alpha_party_formation")
    elif combat_action and active_party and len(set(envelope.delver_ids)) >= 2:
        _raise_floor(components, reasons, "social_stakes", 12, "social:alpha_party_combat")

    advancement_count = _count_any(
        types,
        (
            "CRAWLER_ADVANCED",
            "LEVEL_GAINED",
            "ABILITY_UNLOCKED",
            "FLOOR_ADVANCED",
            "STRATUM_ADVANCED",
            "ADVANCEMENT",
        ),
    )
    if advancement_count >= 2:
        _raise_floor(components, reasons, "character_significance", 14, "character:alpha_multi_advancement")
    elif advancement_count == 1:
        _raise_floor(components, reasons, "character_significance", 10, "character:alpha_advancement")

    # Story continuity in the base Alpha runtime is encoded primarily by a
    # sequence of ordinary ledger events rather than later social-memory events.
    # Count distinct canonical phases instead of rewarding raw event volume.
    phases = {
        "trigger": encounter_triggered,
        "action": combat_action,
        "resolution": enemy_defeated or combat_resolved,
        "reward": acquisition_count > 0 or _has_any(types, ("RELIC", "CACHE", "LOOT")),
        "progression": advancement_count > 0,
        "social": party_formed or active_party,
    }
    phase_count = sum(1 for present in phases.values() if present)
    if phase_count >= 5:
        _raise_floor(components, reasons, "continuity", 15, "continuity:alpha_complete_story_chain")
    elif phase_count == 4:
        _raise_floor(components, reasons, "continuity", 12, "continuity:alpha_four_phase_story_chain")
    elif phase_count == 3:
        _raise_floor(components, reasons, "continuity", 9, "continuity:alpha_three_phase_story_chain")

    total = sum(int(value) for value in components.values())
    score = base.HighlightScore(**components, total=total)
    if score != original:
        reasons.append(f"scoring_profile:{ALPHA_SCORING_PROFILE}")
    return score, tuple(sorted(set(reasons)))


class AlphaHighlightStoryArcService(base.HighlightStoryArcService):
    """30.5.3 persistence semantics with the versioned Alpha scorer."""

    def __init__(self, media: MediaPersistence, *, policy: AlphaHighlightPolicy | None = None) -> None:
        super().__init__(media, policy=policy or AlphaHighlightPolicy())

    def evaluate(self, envelope: MediaEnvelope) -> base.HighlightEvaluation:
        self._require_envelope(envelope)
        score, reason_codes = score_alpha_envelope(envelope)
        tier = base.tier_for_score(score.total, self.policy)
        with self._lock:
            with Session(self.media.engine) as session:
                arcs = [
                    self._upsert_arc(session, envelope, arc_type, subjects)
                    for arc_type, subjects in base._arc_specs(envelope)
                ]
                arc_ids = tuple(sorted(arc.arc_id for arc in arcs))
                selected = score.total >= self.policy.chronicle_min
                highlight_id: str | None = None
                if selected:
                    highlight_id = base._stable_id("media_highlight", envelope.envelope_id, self.policy.digest)
                    body = {
                        "protocol": base.PROTOCOL,
                        "implementation_version": base.IMPLEMENTATION_VERSION,
                        "phase": base.PHASE,
                        "highlight_id": highlight_id,
                        "envelope_id": envelope.envelope_id,
                        "crawl_id": envelope.crawl_id,
                        "source_event_ids": list(envelope.source_event_ids),
                        "delver_ids": list(envelope.delver_ids),
                        "score": score.model_dump(mode="json"),
                        "output_tier": tier.value,
                        "reason_codes": list(reason_codes),
                        "arc_ids": list(arc_ids),
                        "policy_digest": self.policy.digest,
                        "presentation_can_mutate_simulation": False,
                        "llm_decision_used": False,
                        "unreal_dependency": False,
                        "provider_invocation_used": False,
                    }
                    highlight = base.MediaHighlight.model_validate({**body, "digest": payload_digest(body)})
                    base.validate_highlight(highlight, self.policy)
                    row = session.get(base.MediaHighlightRow, highlight_id)
                    payload = highlight.model_dump(mode="json")
                    if row is None:
                        session.add(
                            base.MediaHighlightRow(
                                highlight_id=highlight.highlight_id,
                                envelope_id=highlight.envelope_id,
                                crawl_id=highlight.crawl_id,
                                policy_digest=highlight.policy_digest,
                                total_score=highlight.score.total,
                                output_tier=highlight.output_tier.value,
                                payload=payload,
                                digest=highlight.digest,
                            )
                        )
                    elif row.digest != highlight.digest or row.payload != payload:
                        raise base.HighlightStoryArcError(
                            "Alpha highlight identity resolved to different deterministic payload"
                        )
                session.commit()

        evaluation_body: dict[str, Any] = {
            "envelope_id": envelope.envelope_id,
            "selected": selected,
            "score": score.model_dump(mode="json"),
            "output_tier": tier.value,
            "reason_codes": list(reason_codes),
            "arc_ids": list(arc_ids),
            "highlight_id": highlight_id,
            "policy_digest": self.policy.digest,
        }
        return base.HighlightEvaluation.model_validate(
            {**evaluation_body, "digest": payload_digest(evaluation_body)}
        )

    def reindex_unhighlighted(self, *, crawl_id: str | None = None) -> tuple[MediaEnvelope, ...]:
        """Apply this scoring profile to historical envelopes without rewriting old highlights.

        Envelopes that already have any persisted highlight are intentionally
        skipped.  This prevents two scoring identities from producing competing
        Chronicle highlights for the same immutable envelope.
        """

        existing = {item.envelope_id for item in self.list_highlights(crawl_id=crawl_id)}
        with Session(self.media.engine) as session:
            statement = select(MediaEnvelopeRow)
            if crawl_id is not None:
                statement = statement.where(MediaEnvelopeRow.crawl_id == crawl_id)
            rows = session.scalars(statement.order_by(MediaEnvelopeRow.envelope_id)).all()
            envelopes = [MediaEnvelope.model_validate(row.payload) for row in rows]

        selected: list[MediaEnvelope] = []
        for envelope in sorted(envelopes, key=lambda item: (item.export_tick, item.envelope_id)):
            if envelope.envelope_id in existing:
                continue
            evaluation = self.evaluate(envelope)
            if evaluation.selected:
                selected.append(envelope)
                existing.add(envelope.envelope_id)
        return tuple(selected)


__all__ = [
    "ALPHA_SCORING_PROFILE",
    "AlphaHighlightPolicy",
    "AlphaHighlightStoryArcService",
    "score_alpha_envelope",
]
