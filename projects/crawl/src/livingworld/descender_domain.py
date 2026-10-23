"""Underreach-facing aliases for autonomous participant state.

The deterministic profile generator deliberately remains the same implementation
so existing seeds continue to produce identical personalities and skills.
"""

from __future__ import annotations

from .crawler_domain import (
    CrawlerAgentState,
    CrawlerMemory,
    CrawlerNeeds,
    CrawlerPreferences,
    CrawlerRelationship,
    CrawlerSkills,
    CrawlerTraits,
    LocationKnowledge,
    build_crawler_agent,
)


DescenderAgentState = CrawlerAgentState
DescenderMemory = CrawlerMemory
DescenderNeeds = CrawlerNeeds
DescenderPreferences = CrawlerPreferences
DescenderRelationship = CrawlerRelationship
DescenderSkills = CrawlerSkills
DescenderTraits = CrawlerTraits
SectorKnowledge = LocationKnowledge
build_descender_agent = build_crawler_agent


__all__ = [
    "DescenderAgentState",
    "DescenderMemory",
    "DescenderNeeds",
    "DescenderPreferences",
    "DescenderRelationship",
    "DescenderSkills",
    "DescenderTraits",
    "SectorKnowledge",
    "build_descender_agent",
]
