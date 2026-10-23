import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).parents[1]
    / "unreal"
    / "CrawlPresentation"
    / "Content"
    / "Python"
    / "attack_variety.py"
)
SPEC = importlib.util.spec_from_file_location("crawl_attack_variety", MODULE_PATH)
attack_variety = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(attack_variety)


def test_selection_is_deterministic_for_same_event():
    slots = {
        "humanoid.combat.attack.default",
        "humanoid.combat.attack.02",
        "humanoid.combat.attack.03",
    }
    first = attack_variety.choose_attack_slot("event-123", "COMBAT_HIT", slots)
    second = attack_variety.choose_attack_slot("event-123", "COMBAT_HIT", slots)
    assert first == second


def test_unvalidated_variants_never_enter_selection_pool():
    slots = {"humanoid.combat.attack.default"}
    selected = attack_variety.choose_attack_slot("event-variant", "COMBAT_HIT", slots)
    assert selected == "humanoid.combat.attack.default"


def test_heavy_hit_can_use_charged_only_when_validated():
    slots = {
        "humanoid.combat.attack.default",
        "humanoid.combat.attack.charged",
    }
    outcomes = {
        attack_variety.choose_attack_slot(
            f"heavy-{index}",
            "COMBAT_HIT",
            slots,
            {"severity": "critical"},
        )
        for index in range(20)
    }
    assert outcomes <= slots
    assert "humanoid.combat.attack.charged" in outcomes


def test_enemy_slot_prefix_is_preserved():
    slots = {
        "enemy.biped.combat.attack.default",
        "enemy.biped.combat.attack.02",
    }
    selected = attack_variety.choose_attack_slot(
        "enemy-event",
        "COMBAT_HIT",
        slots,
        actor_kind="enemy",
    )
    assert selected.startswith("enemy.biped.combat.attack.")


def test_reaction_severity_tracks_profiled_attack_without_changing_outcome():
    assert attack_variety.choose_reaction_slot(
        "enemy", {}, "humanoid.combat.attack.default"
    ) == "enemy.biped.reaction.hit.light"
    assert attack_variety.choose_reaction_slot(
        "crawler", {}, "humanoid.combat.attack.03"
    ) == "humanoid.reaction.hit.medium"
    assert attack_variety.choose_reaction_slot(
        "crawler", {}, "humanoid.combat.attack.charged"
    ) == "humanoid.reaction.hit.heavy"


def test_different_stable_event_ids_exercise_more_than_one_valid_profile():
    slots = {
        "humanoid.combat.attack.default",
        "humanoid.combat.attack.02",
        "humanoid.combat.attack.03",
    }
    outcomes = {
        attack_variety.choose_attack_slot(f"event-{index}", "COMBAT_HIT", slots)
        for index in range(64)
    }
    assert outcomes <= slots
    assert len(outcomes) > 1


def test_empty_and_partial_optional_pools_fall_back_to_proven_attack_01():
    assert attack_variety.choose_attack_slot("empty", "COMBAT_HIT", set()) == (
        "humanoid.combat.attack.default"
    )
    assert attack_variety.choose_attack_slot(
        "partial",
        "COMBAT_HIT",
        {"humanoid.combat.attack.02"},
    ) == "humanoid.combat.attack.02"


def test_reaction_selection_is_deterministic_and_respects_validated_fallback():
    first = attack_variety.choose_reaction_slot(
        "crawler",
        attack_slot="humanoid.combat.attack.03",
        validated_slots={"humanoid.reaction.hit.default"},
    )
    second = attack_variety.choose_reaction_slot(
        "crawler",
        attack_slot="humanoid.combat.attack.03",
        validated_slots={"humanoid.reaction.hit.default"},
    )
    assert first == second == "humanoid.reaction.hit.default"


def test_diagnostic_cycle_contains_only_validated_profiles():
    slots = {
        "humanoid.combat.attack.default",
        "humanoid.combat.attack.03",
    }
    outcomes = [
        attack_variety.validation_cycle_attack_slot(index, "crawler", slots)
        for index in range(10)
    ]
    assert set(outcomes) == slots
