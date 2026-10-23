"""Underreach-facing names for story highlights and rendered highlight packages."""

from __future__ import annotations

from typing import Any

from .highlight_reels import HighlightOutput, HighlightPackage, HighlightReelAssembler
from .story_highlights import StoryArc, StoryArcDetector


EchoOutput = HighlightOutput
EchoPackage = HighlightPackage
EchoReelAssembler = HighlightReelAssembler
Echo = StoryArc
EchoDetector = StoryArcDetector


def public_echo(echo: StoryArc) -> dict[str, Any]:
    """Project a detected story arc into the public Echo vocabulary."""

    return {
        "echo_id": echo.id,
        "echo_type": echo.story_type,
        "score": round(echo.score, 4),
        "start_tick": echo.start_tick,
        "end_tick": echo.end_tick,
        "stratum_numbers": list(echo.floor_numbers),
        "descender_ids": list(echo.participant_ids),
        "ledger_event_ids": list(echo.event_ids),
        "explanation": echo.explanation,
        "evidence": list(echo.evidence),
        "canonical": True,
    }


__all__ = [
    "Echo",
    "EchoDetector",
    "EchoOutput",
    "EchoPackage",
    "EchoReelAssembler",
    "public_echo",
]
