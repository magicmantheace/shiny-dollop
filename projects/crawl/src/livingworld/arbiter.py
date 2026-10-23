"""The Arbiter-facing facade over deterministic intervention scheduling.

The current implementation delegates to the proven CrawlDirector machinery so
behavior and deterministic outcomes do not change during the naming migration.
Future Arbiter responsibilities can expand behind this public name without forcing
28B to adopt the legacy class name.
"""

from __future__ import annotations

from .crawl_director import CrawlDirector, director_metrics, remaining_budget


class Arbiter(CrawlDirector):
    """Public Underreach name for deterministic Descent intervention scheduling."""


arbiter_metrics = director_metrics
remaining_arbiter_budget = remaining_budget


__all__ = ["Arbiter", "arbiter_metrics", "remaining_arbiter_budget"]
