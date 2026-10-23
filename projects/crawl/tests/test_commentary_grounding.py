"""Commentary is real deterministic prose grounded in canonical events.

Every line must cite its source event IDs, the grounding validator must pass
for real scripts and reject fabricated ones, and identical events must
produce identical scripts.
"""
from __future__ import annotations

from livingworld.commentary_system import (
    CommentaryLine,
    CommentaryMode,
    GroundedCommentaryGenerator,
    validate_commentary_grounding,
)
from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService


def _real_events(tmp_path):
    persistence = CrawlPersistence(f"sqlite:///{tmp_path / 'commentary.db'}")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    crawl = service.create_seeded_crawl(
        seed="commentary-grounding", crawler_ids=["npc_a", "npc_b"], floor_count=2
    )
    service.start(crawl, tick=5)
    service.record_event(crawl, "CRAWLER_MOVED", "npc_a advanced", actor_ids=["npc_a"])
    service.record_event(crawl, "CRAWLER_DIED", "npc_b fell", actor_ids=["npc_b"])
    service.complete_current_floor(crawl, advance_ticks=3)
    return persistence.list_events(crawl.id, limit=500)


def test_commentary_lines_cite_canonical_events(tmp_path):
    events = _real_events(tmp_path)
    assert events, "need real events for a grounding test"
    generator = GroundedCommentaryGenerator()

    for mode in CommentaryMode:
        script = generator.generate(events, mode=mode)
        assert script.lines, f"no commentary lines in {mode}"
        authoritative = {e.id for e in events}
        for line in script.lines:
            assert line.source_event_ids, "line without citation"
            assert set(line.source_event_ids) <= authoritative
            assert line.factual
        assert validate_commentary_grounding(script, authoritative)


def test_commentary_is_deterministic(tmp_path):
    events = _real_events(tmp_path)
    generator = GroundedCommentaryGenerator()
    first = generator.generate(events, mode=CommentaryMode.PLAY_BY_PLAY)
    second = generator.generate(events, mode=CommentaryMode.PLAY_BY_PLAY)
    assert first.digest == second.digest
    assert [line.text for line in first.lines] == [line.text for line in second.lines]


def test_validator_rejects_fabricated_citations(tmp_path):
    events = _real_events(tmp_path)
    generator = GroundedCommentaryGenerator()
    script = generator.generate(events, mode=CommentaryMode.DOCUMENTARY)
    authoritative = {e.id for e in events}

    fabricated = generator._build(
        CommentaryMode.DOCUMENTARY,
        script.lines
        + (CommentaryLine(text="A dragon intervened.", source_event_ids=("event_that_never_happened",)),),
    )
    assert not validate_commentary_grounding(fabricated, authoritative)
