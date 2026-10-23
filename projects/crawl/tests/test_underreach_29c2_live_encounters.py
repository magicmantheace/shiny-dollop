import copy
import json

import pytest

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.monster_encounters import build_encounter_plan
from livingworld.stratum_environment import build_stratum_environment_manifest
from livingworld.stratum_theme import build_stratum_theme_manifest
from livingworld.underreach_live_encounters import (
    CANONICAL_PROTOCOL,
    PRESENTATION_PROTOCOL,
    build_live_encounter_proof,
    promote_encounter,
    rebuild_digest,
    validate_live_encounter_proof,
    validate_presentation_against_truth,
)


def test_same_inputs_reproduce_exact_canonical_proof():
    first = build_live_encounter_proof("underreach-29c2-determinism")
    second = build_live_encounter_proof("underreach-29c2-determinism")
    assert first == second
    assert first["digest"] == rebuild_digest(first)


def test_protocol_marks_canonical_truth_and_non_authoritative_presentation():
    proof = build_live_encounter_proof("underreach-29c2-boundary")
    assert proof["protocol"] == CANONICAL_PROTOCOL
    assert proof["authoritative"] is True
    assert proof["presentation"]["protocol"] == PRESENTATION_PROTOCOL
    assert proof["presentation"]["authoritative"] is False
    assert proof["presentation"]["canonical_digest"] == proof["canonical_digest"]


def test_promotion_preserves_29c1_identity_and_requires_explicit_boundary():
    environment = build_stratum_environment_manifest("underreach-29c2-promotion", 0, sector_count=12)
    themed = build_stratum_theme_manifest(environment, "ancient_stoneworks")
    plan = build_encounter_plan(environment, themed)
    source = sorted(plan["encounters"], key=lambda item: item["encounter_id"])[0]

    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    crawl = service.create_seeded_crawl(seed="underreach-29c2-promotion", crawler_ids=["descender_000"], floor_count=1)
    service.start(crawl)
    encounter = promote_encounter(crawl, plan, source, participant_npc_ids=["descender_000"])

    assert encounter.trigger["source_plan_digest"] == plan["digest"]
    assert encounter.trigger["source_encounter_id"] == source["encounter_id"]
    assert encounter.trigger["source_sector_id"] == source["sector_id"]
    assert sorted(encounter.enemies) == sorted(member["member_id"] for member in source["members"])
    assert encounter.location_id in crawl.floors[crawl.current_floor].locations
    assert encounter.location_id != source["sector_id"]


def test_promotion_rejects_non_member_source_encounter():
    environment = build_stratum_environment_manifest("underreach-29c2-reject", 0, sector_count=12)
    themed = build_stratum_theme_manifest(environment, "ancient_stoneworks")
    plan = build_encounter_plan(environment, themed)
    source = copy.deepcopy(plan["encounters"][0])
    source["encounter_id"] = "not-in-plan"

    service = CrawlLifecycleService()
    crawl = service.create_seeded_crawl(seed="underreach-29c2-reject", crawler_ids=["descender_000"], floor_count=1)
    service.start(crawl)
    with pytest.raises(ValueError):
        promote_encounter(crawl, plan, source, participant_npc_ids=["descender_000"])


def test_ledger_contains_promotion_start_end_and_unique_ids():
    proof = build_live_encounter_proof("underreach-29c2-ledger")
    events = proof["canonical_truth"]["ledger_events"]
    types = [event["event_type"] for event in events]
    assert "UNDERREACH_ENCOUNTER_PROMOTED" in types
    assert "COMBAT_STARTED" in types
    assert "COMBAT_ENDED" in types
    ids = [event["id"] for event in events]
    assert len(ids) == len(set(ids))
    assert proof["presentation"]["ledger_event_ids"] == ids


def test_resolution_exactly_matches_final_enemy_and_descender_state():
    proof = build_live_encounter_proof("underreach-29c2-final-state")
    truth = proof["canonical_truth"]
    resolution = truth["resolution"]
    defeated = sorted(enemy_id for enemy_id, state in truth["enemy_final"].items() if not state["alive"])
    dead = sorted(npc_id for npc_id, state in truth["participant_final"].items() if state["status"] == "dead")
    assert sorted(resolution["defeated_enemy_ids"]) == defeated
    assert sorted(resolution["crawler_deaths"]) == dead


def test_presentation_cannot_invent_defeat_or_death():
    proof = build_live_encounter_proof("underreach-29c2-tamper")
    truth = dict(proof["canonical_truth"])
    truth["canonical_digest"] = proof["canonical_digest"]

    altered = copy.deepcopy(proof["presentation"])
    altered["defeated_enemy_ids"] = sorted(set(altered["defeated_enemy_ids"] + ["invented_monster"]))
    with pytest.raises(ValueError):
        validate_presentation_against_truth(altered, truth)

    altered = copy.deepcopy(proof["presentation"])
    altered["dead_descender_ids"] = sorted(set(altered["dead_descender_ids"] + ["invented_descender"]))
    with pytest.raises(ValueError):
        validate_presentation_against_truth(altered, truth)


def test_json_round_trip_preserves_full_proof_validation():
    proof = build_live_encounter_proof("underreach-29c2-json")
    restored = json.loads(json.dumps(proof))
    assert validate_live_encounter_proof(restored)
    assert restored["digest"] == rebuild_digest(restored)


def test_canonical_truth_tampering_is_rejected():
    proof = build_live_encounter_proof("underreach-29c2-canonical-tamper")
    altered = copy.deepcopy(proof)
    altered["canonical_truth"]["resolution"]["outcome"] = "invented"
    with pytest.raises(ValueError):
        validate_live_encounter_proof(altered)


def test_multiple_themes_run_through_same_canonical_boundary():
    digests = []
    for theme in ("ancient_stoneworks", "flooded_catacombs", "ember_foundry"):
        proof = build_live_encounter_proof("underreach-29c2-theme", theme=theme)
        assert validate_live_encounter_proof(proof)
        assert proof["canonical_truth"]["source_encounter"]["theme"] == theme
        digests.append(proof["digest"])
    assert len(set(digests)) == 3


def test_25_seed_stress_is_valid_and_deterministic():
    for index in range(25):
        seed = f"underreach-29c2-stress-{index:03d}"
        first = build_live_encounter_proof(seed)
        second = build_live_encounter_proof(seed)
        assert first == second
        assert validate_live_encounter_proof(first)
