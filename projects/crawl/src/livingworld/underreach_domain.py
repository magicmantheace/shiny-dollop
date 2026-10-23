"""Underreach-facing names for the established deterministic domain model.

These are compatibility aliases, not duplicate models. Existing persisted fields,
JSON snapshots, event IDs, and replay fingerprints therefore remain unchanged while
new feature code can stop introducing Crawl-era terminology.
"""

from __future__ import annotations

from .crawl_domain import (
    Crawl,
    CrawlEvent,
    CrawlFloor,
    CrawlLocation,
    CrawlStatus,
    CrawlerParticipation,
    FloorStatus,
    LocationKind,
    ParticipationStatus,
)


Descent = Crawl
LedgerEvent = CrawlEvent
Stratum = CrawlFloor
Sector = CrawlLocation
DescentStatus = CrawlStatus
StratumStatus = FloorStatus
DescenderParticipation = CrawlerParticipation
DescenderParticipationStatus = ParticipationStatus
SectorKind = LocationKind


__all__ = [
    "Descent",
    "LedgerEvent",
    "Stratum",
    "Sector",
    "DescentStatus",
    "StratumStatus",
    "DescenderParticipation",
    "DescenderParticipationStatus",
    "SectorKind",
]
