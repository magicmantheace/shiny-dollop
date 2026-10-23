"""Slice 9 gate: identical crawler templates must diverge into different builds
through different lived experience (XP), and identical experience must
reproduce identical builds deterministically.
"""
from __future__ import annotations

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.progression_system import award_experience, choose_progression, combat_modifiers


def _participants(tmp_path, seed):
    persistence = CrawlPersistence(f"sqlite:///{tmp_path / 'prog.db'}")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    crawl = service.create_seeded_crawl(
        seed=seed, crawler_ids=["twin_a", "twin_b", "twin_c"], floor_count=1
    )
    return crawl


def _identical_template(crawl, source_id, target_id):
    """Give target the exact same agent profile as source (identical templates)."""
    source = crawl.participants[source_id].agent
    target = crawl.participants[target_id]
    target.agent = source.model_copy(deep=True)


def test_identical_templates_diverge_through_experience(tmp_path):
    crawl = _participants(tmp_path, "divergence")
    _identical_template(crawl, "twin_a", "twin_b")
    veteran = crawl.participants["twin_a"]
    rookie = crawl.participants["twin_b"]

    veteran.gameplay.progression.specialization = "vanguard"
    rookie.gameplay.progression.specialization = "vanguard"

    award_experience(veteran, 500.0)  # several levels of lived combat
    award_experience(rookie, 10.0)  # barely anything

    veteran_choices = choose_progression(veteran, crawl_seed=crawl.seed)
    rookie_choices = choose_progression(rookie, crawl_seed=crawl.seed)

    assert veteran_choices != rookie_choices
    assert len(veteran.gameplay.progression.ability_ids) > len(
        rookie.gameplay.progression.ability_ids
    )
    # Builds are mechanically different, not just cosmetically.
    assert combat_modifiers(veteran) != combat_modifiers(rookie)


def test_identical_experience_reproduces_identical_builds(tmp_path):
    first = _participants(tmp_path, "determinism")
    _identical_template(first, "twin_a", "twin_c")
    first.participants["twin_a"].gameplay.progression.specialization = "hunter"
    first.participants["twin_c"].gameplay.progression.specialization = "hunter"
    award_experience(first.participants["twin_a"], 300.0)
    award_experience(first.participants["twin_c"], 300.0)
    first.participants["twin_a"].gameplay.progression.unspent_points = (
        first.participants["twin_c"].gameplay.progression.unspent_points
    )
    choices_a = choose_progression(first.participants["twin_a"], crawl_seed=first.seed)
    choices_c = choose_progression(first.participants["twin_c"], crawl_seed=first.seed)

    # Same seed, same template, same experience -> same build.
    assert first.participants["twin_a"].gameplay.progression.ability_ids == (
        first.participants["twin_c"].gameplay.progression.ability_ids
    )
    assert first.participants["twin_a"].gameplay.progression.choices_made == (
        first.participants["twin_c"].gameplay.progression.choices_made
    )
    assert choices_a == choices_c
