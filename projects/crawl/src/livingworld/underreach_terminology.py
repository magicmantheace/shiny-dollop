"""Canonical public vocabulary for the Underreach product identity.

The simulation was originally implemented with ``crawl``/``crawler``/``floor``
identifiers. Those names remain valid compatibility and persistence details until
a separately versioned data migration is performed. New public APIs, UI, media,
and future feature code should use the vocabulary in this module instead.

This separation is intentional: changing persisted identifiers or historical
ledger event types in-place would damage replay compatibility and deterministic
fingerprints. Public projections can use original terminology immediately without
rewriting simulation truth.
"""

from __future__ import annotations

from types import MappingProxyType


UNDERREACH_NAME = "The Underreach"
DESCENT_NAME = "The Descent"
DESCENDER_NAME = "Descender"
STRATUM_NAME = "Stratum"
SECTOR_NAME = "Sector"
CYCLE_NAME = "Cycle"
HOUSE_NAME = "House"
PATRON_NAME = "Patron"
BOON_NAME = "Boon"
CACHE_NAME = "Cache"
RELIC_NAME = "Relic"
REFUGE_NAME = "Refuge"
ARBITER_NAME = "The Arbiter"
FEED_NAME = "The Feed"
LEDGER_NAME = "The Ledger"
ECHO_NAME = "Echo"
ECHO_REEL_NAME = "Echo Reel"


PUBLIC_TERMS = MappingProxyType(
    {
        "world": UNDERREACH_NAME,
        "competition": DESCENT_NAME,
        "participant": DESCENDER_NAME,
        "layer": STRATUM_NAME,
        "subarea": SECTOR_NAME,
        "season": CYCLE_NAME,
        "sponsor_organization": HOUSE_NAME,
        "individual_backer": PATRON_NAME,
        "sponsored_support": BOON_NAME,
        "loot_reward": CACHE_NAME,
        "rare_item": RELIC_NAME,
        "safe_area": REFUGE_NAME,
        "rules_authority": ARBITER_NAME,
        "broadcast": FEED_NAME,
        "record": LEDGER_NAME,
        "highlight": ECHO_NAME,
        "highlight_reel": ECHO_REEL_NAME,
    }
)


# Historical ledger event strings are not rewritten in storage. The Feed projects
# these prefixes into the new vocabulary while preserving the canonical event ID.
_PUBLIC_EVENT_PREFIXES = (
    ("CRAWLER_", "DESCENDER_"),
    ("FLOOR_", "STRATUM_"),
    ("CRAWL_", "DESCENT_"),
)
_LEGACY_EVENT_PREFIXES = tuple((public, legacy) for legacy, public in _PUBLIC_EVENT_PREFIXES)


_PUBLIC_PARTICIPATION_STATUS = MappingProxyType(
    {
        "active": "active",
        "dead": "fallen",
        "eliminated": "eliminated",
        "advanced": "advanced",
    }
)

_PUBLIC_LOCATION_KIND = MappingProxyType(
    {
        "entrance": "entrance",
        "zone": "sector",
        "room": "sector",
        "safe_area": "refuge",
        "exit": "exit",
    }
)


def public_event_type(event_type: str) -> str:
    """Return the Feed-facing name for a canonical legacy ledger event type."""

    value = str(event_type).upper()
    for legacy_prefix, public_prefix in _PUBLIC_EVENT_PREFIXES:
        if value.startswith(legacy_prefix):
            return public_prefix + value[len(legacy_prefix):]
    return value


def legacy_event_type(event_type: str) -> str:
    """Translate a public event filter back to the stored ledger vocabulary."""

    value = str(event_type).upper()
    for public_prefix, legacy_prefix in _LEGACY_EVENT_PREFIXES:
        if value.startswith(public_prefix):
            return legacy_prefix + value[len(public_prefix):]
    return value


def public_participation_status(status: str) -> str:
    """Translate internal participation state into its public Descender label."""

    value = str(status).lower()
    return _PUBLIC_PARTICIPATION_STATUS.get(value, value)


def public_location_kind(kind: str) -> str:
    """Translate internal map-location categories into Underreach vocabulary."""

    value = str(kind).lower()
    return _PUBLIC_LOCATION_KIND.get(value, value)


def public_protocol(protocol: str) -> str:
    """Project new public protocol names without mutating stored artifacts."""

    value = str(protocol)
    return "underreach." + value[len("crawl."):] if value.startswith("crawl.") else value
