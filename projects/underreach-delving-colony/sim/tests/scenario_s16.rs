//! S16 acceptance: the Crystal Dark's own gate mechanics —
//! thicker darkness in the band's deep zone answered by
//! crystal-heart lanterns fitted with ground lenses, sound-
//! hunting lurkers answered by quiet gear, brittle deep floors
//! answered by roped marked routes, and the crystal-cutting /
//! lens-grinding production jobs fed by crystal mined in the
//! band. Proven in the S7/S10 pattern: each hazard bites
//! unprotected, each answer stops exactly its own hazard, the
//! kit rules hold, nothing leaks into other bands, and the
//! slice stays deterministic.
//!
//! Choreography note: several proofs stage a delver at a face
//! stand or on a path step and pin them there (the S9/S10
//! staging pattern), because a free-running colony works the
//! shallow first face first — the band's deep character is
//! staged so the mechanics themselves are what is measured.

use underreach_sim::scenario::{build_scenario_gen_floor, open_current_floor, GEN_WORLD_SEED};
use underreach_sim::sim::{DelverState, Job, LedgerKind, Sim, YieldKind};
use underreach_sim::world::{Cell, Pos};

fn count(sim: &Sim, kind: LedgerKind) -> usize {
    sim.ledger.iter().filter(|e| e.kind == kind).count()
}

fn count_detail(sim: &Sim, kind: LedgerKind, needle: &str) -> usize {
    sim.ledger
        .iter()
        .filter(|e| e.kind == kind && e.detail.contains(needle))
        .count()
}

fn manhattan(a: Pos, b: Pos) -> i32 {
    (a.x - b.x).abs() + (a.y - b.y).abs() + (a.z - b.z).abs()
}

fn chebyshev(a: Pos, b: Pos) -> i32 {
    (a.x - b.x).abs().max((a.y - b.y).abs()).max((a.z - b.z).abs())
}

/// A carved deep-zone cell at Chebyshev distance exactly 2
/// from `from` — inside a crystal lantern's radius, outside a
/// plain lantern's *effective* radius in thick dark.
fn deep_cell_at_chebyshev_2(sim: &Sim, from: Pos) -> Pos {
    for y in 6..sim.world.sy as i32 {
        for x in 0..sim.world.sx as i32 {
            for z in 0..sim.world.sz as i32 {
                let p = Pos::new(x, y, z);
                if sim.world.get(p) == Some(Cell::Carved) && chebyshev(from, p) == 2 {
                    return p;
                }
            }
        }
    }
    panic!("no carved deep cell at Chebyshev 2 from {from:?}");
}

/// Two horizontally adjacent carved cells, both deep (y ≥ 7):
/// a step a delver can be staged across.
fn deep_adjacent_pair(sim: &Sim) -> (Pos, Pos) {
    for y in 7..sim.world.sy as i32 {
        for x in 0..sim.world.sx as i32 - 1 {
            for z in 0..sim.world.sz as i32 {
                let a = Pos::new(x, y, z);
                let b = Pos::new(x + 1, y, z);
                if sim.world.get(a) == Some(Cell::Carved)
                    && sim.world.get(b) == Some(Cell::Carved)
                {
                    return (a, b);
                }
            }
        }
    }
    panic!("no deep adjacent carved pair");
}

/// Stage delver 0 stepping from `a` onto `b` along a one-step
/// path, and tick once. Critters are cleared so only the floor
/// itself can act on the delver.
fn stage_step(sim: &mut Sim, a: Pos, b: Pos) {
    sim.critters.clear();
    sim.delvers[0].pos = a;
    sim.delvers[0].path = vec![b];
    sim.delvers[0].state = DelverState::ToCamp;
    sim.tick();
    assert_eq!(sim.delvers[0].pos, b, "the staged step landed");
}

// ---------------------------------------------------------------------------
// Crystal: the band's resource
// ---------------------------------------------------------------------------

#[test]
fn crystal_is_obtainable_in_the_crystal_dark() {
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 4);
    // The generator registers a crystal face (the deepest) and
    // embeds crystal clusters in the rock.
    let fi = sim
        .faces
        .iter()
        .position(|f| f.yield_kind == YieldKind::Crystal)
        .expect("floor 4 registers a crystal face");
    let face = sim.faces[fi].clone();
    assert_eq!(
        sim.world.get(face.rock),
        Some(Cell::Crystal),
        "the crystal face's rock is crystal in the world"
    );
    assert!(face.stand.y >= 6, "the crystal face stands in the deep zone");
    let mut embedded = 0;
    for y in 0..sim.world.sy as i32 {
        for x in 0..sim.world.sx as i32 {
            for z in 0..sim.world.sz as i32 {
                if sim.world.get(Pos::new(x, y, z)) == Some(Cell::Crystal) {
                    embedded += 1;
                }
            }
        }
    }
    assert!(
        embedded >= 6,
        "the face vein plus embedded clusters put crystal in the rock, got {embedded} cells"
    );

    // Mine it (staged at the stand, the S10 pattern): the face
    // cache fills with crystal-kind units.
    sim.place_lantern(face.stand, 1, 100_000.0);
    sim.delvers[0].pos = face.stand;
    sim.delvers[0].target_face = Some(fi);
    for _ in 0..400 {
        if sim.delvers[0].state != DelverState::Downed {
            sim.delvers[0].state = DelverState::Mining;
        }
        sim.tick();
        if sim.delvers[0].state != DelverState::Downed {
            sim.delvers[0].pos = face.stand;
        }
        if sim.faces[fi].cache >= 4 || sim.delvers[0].carrying >= 4 {
            break;
        }
    }
    assert!(
        sim.faces[fi].cache + sim.delvers[0].carrying >= 4,
        "crystal was mined at the crystal face (cache {}, carrying {})",
        sim.faces[fi].cache,
        sim.delvers[0].carrying
    );
    // Haul it home (staged deposit at the stockpile): the raw
    // crystal reaches the colony stores.
    if sim.delvers[0].carrying == 0 {
        let take = sim.faces[fi].cache.min(4);
        sim.faces[fi].cache -= take;
        sim.delvers[0].carrying = take;
        sim.delvers[0].carrying_kind = YieldKind::Crystal;
    }
    assert_eq!(sim.delvers[0].carrying_kind, YieldKind::Crystal);
    sim.delvers[0].pos = sim.stockpile;
    sim.delvers[0].state = DelverState::ToCamp;
    sim.delvers[0].path.clear();
    sim.tick();
    assert!(
        sim.stores.crystal >= 4,
        "raw crystal is in the stores, got {}",
        sim.stores.crystal
    );
    assert!(count_detail(&sim, LedgerKind::HaulDelivered, "raw crystal") >= 1);
}

// ---------------------------------------------------------------------------
// Production jobs: cutting and grinding
// ---------------------------------------------------------------------------

#[test]
fn cutting_and_grinding_jobs_produce_lenses_through_the_colony_jobs() {
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 4);
    // The colony hauled crystal down (staged stores, as the
    // obtainability proof above produces live).
    sim.stores.crystal = 3;
    assert!(sim.set_job(0, Job::CrystalCutter), "Bram takes the cutting job");
    assert!(sim.set_job(1, Job::LensGrinder), "Sella takes the grinding job");
    for _ in 0..400 {
        sim.tick();
        if sim.stores.lenses >= 2 {
            break;
        }
    }
    assert_eq!(sim.stores.crystal, 0, "the cutter worked through the raw crystal");
    assert!(
        sim.stores.lenses >= 2,
        "the grinder produced lenses, got {}",
        sim.stores.lenses
    );
    assert!(
        count_detail(&sim, LedgerKind::Crafted, "cut a raw crystal") >= 3,
        "cutting is ledgered as colony work"
    );
    assert!(
        count_detail(&sim, LedgerKind::Crafted, "ground a cut crystal") >= 2,
        "grinding is ledgered as colony work"
    );

    // Cut crystal also feeds quiet gear; a delver equips it at
    // camp automatically, like a mask.
    sim.stores.cut_crystals += 1;
    sim.stores.goods += 1;
    assert!(sim.craft_quiet_gear());
    for _ in 0..100 {
        sim.tick();
        if sim.delvers.iter().any(|d| d.quiet) {
            break;
        }
    }
    assert!(
        sim.delvers.iter().any(|d| d.quiet),
        "a delver equipped the quiet gear at camp"
    );
}

#[test]
fn a_crystal_lantern_needs_a_lens_and_draws_it_at_placement() {
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 4);
    let stand = sim.faces[2].stand; // the deep crystal face's stand
    sim.stores.fungal_oil = 1;
    // No lens in the stores: the placement fails whole — the
    // oil charge is not drawn for a lantern that cannot be fit.
    assert!(!sim.place_lantern(stand, 4, 100.0), "no lens, no crystal lantern");
    assert_eq!(sim.stores.fungal_oil, 1, "the failed fitting drew no oil");
    assert!(sim.lanterns.iter().all(|l| l.pos != stand));
    // With a lens: placement succeeds and consumes lens + oil.
    sim.stores.lenses = 1;
    assert!(sim.place_lantern(stand, 4, 100.0), "a lens fits the crystal lantern");
    assert_eq!(sim.stores.lenses, 0, "the lens was consumed by the fitting");
    assert_eq!(sim.stores.fungal_oil, 0, "the tier-2+ oil charge still applies");
    assert!(
        sim.lanterns.iter().any(|l| l.pos == stand && l.tier == 4),
        "the crystal-heart lantern stands at the face"
    );
}

// ---------------------------------------------------------------------------
// Thicker darkness
// ---------------------------------------------------------------------------

#[test]
fn lenses_counter_the_thick_darkness_where_a_plain_lantern_falls_short() {
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 4);
    let stand = sim.faces[2].stand; // (16, 9, 4) — deep zone
    assert!(sim.thick_dark_at(stand), "the deep face stands in thick dark");
    assert!(
        !sim.thick_dark_at(sim.stockpile),
        "the camp shallows are not thick dark"
    );
    let q = deep_cell_at_chebyshev_2(&sim, stand);
    // A plain tier-1 lantern at the stand: its radius-3 light
    // is drunk down to 1 in the deep zone, so the cell two
    // steps away stays dark — first light cannot be planted
    // there with a plain lantern.
    assert!(sim.place_lantern(stand, 1, 100_000.0));
    let qi = sim.world.idx(q).unwrap();
    assert!(
        !sim.lit[qi],
        "a plain lantern's light falls short in the thick dark at {q:?}"
    );
    // The same stand, a crystal-heart lantern (lens fitted):
    // its focused light keeps the full radius and the cell is
    // lit — the gate opens.
    sim.stores.lenses = 1;
    sim.stores.fungal_oil = 1;
    assert!(sim.place_lantern(stand, 4, 100_000.0));
    assert!(
        sim.lit[qi],
        "the crystal-heart lantern lights {q:?} through the thick dark"
    );
}

#[test]
fn thick_darkness_does_not_leak_to_other_bands() {
    // Floor 5 (Magma Roots): the same geometry, no darkness
    // model — a plain lantern lights its full radius in the
    // deep zone there.
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 5);
    assert!(!sim.crystal_dark_here());
    let stand = sim.faces[0].stand; // (8, 6, 2) — floor 5's deep zone
    assert!(stand.y >= 6);
    let q = deep_cell_at_chebyshev_2(&sim, stand);
    assert!(sim.place_lantern(stand, 1, 100_000.0));
    let qi = sim.world.idx(q).unwrap();
    assert!(
        sim.lit[qi],
        "no radius penalty off the Crystal Dark: {q:?} is lit by a plain lantern"
    );
}

// ---------------------------------------------------------------------------
// Sound hunters and quiet gear
// ---------------------------------------------------------------------------

/// Stage a lone sound hunter at the easternmost den of floor 4
/// and delver 0 at a carved cell 13–16 Manhattan steps away.
/// Returns (sim, hunter spawn, staging cell).
fn staged_hunter(quiet: bool) -> (Sim, Pos, Pos) {
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 4);
    sim.critters.clear();
    let den = *sim
        .floor
        .as_ref()
        .unwrap()
        .dens
        .iter()
        .max_by_key(|p| p.x)
        .unwrap();
    let spawn = sim.spawn_critter(underreach_sim::sim::CritterKind::DeepLurker, den);
    let hunter = sim.critters.iter().find(|c| c.id == spawn).unwrap().pos;
    // A carved cell the hunter can hear an unquiet delver at,
    // but not a quiet one: distance 13–16, so +QUIET_NOISE
    // pushes a quiet delver past SOUND_HUNTER_RANGE.
    let mut stage = None;
    for y in 0..sim.world.sy as i32 {
        for x in 0..sim.world.sx as i32 {
            for z in 0..sim.world.sz as i32 {
                let p = Pos::new(x, y, z);
                let d = manhattan(hunter, p);
                if sim.world.get(p) == Some(Cell::Carved) && (13..=16).contains(&d) {
                    stage = Some(p);
                }
            }
        }
    }
    let stage = stage.expect("a staging cell within earshot of the den");
    sim.delvers[0].quiet = quiet;
    sim.delvers[0].pos = stage;
    (sim, hunter, stage)
}

#[test]
fn quiet_gear_measurably_reduces_sound_hunter_detection() {
    // Unquiet: the hunter hears Bram across the dark and
    // closes on him.
    let (mut sim, hunter, stage) = staged_hunter(false);
    let before = manhattan(hunter, stage);
    for _ in 0..60 {
        sim.tick();
        sim.delvers[0].pos = stage;
    }
    let lurker = &sim.critters[0];
    assert_ne!(lurker.pos, hunter, "the hunter moved toward the sound");
    assert!(
        manhattan(lurker.pos, stage) < before,
        "the hunter closed: {} -> {}",
        before,
        manhattan(lurker.pos, stage)
    );

    // Quiet: the same staging, the same hunter — Bram sounds
    // four steps farther off, past earshot, and the hunter
    // never engages at all.
    let (mut sim, hunter, stage) = staged_hunter(true);
    for _ in 0..60 {
        sim.tick();
        sim.delvers[0].pos = stage;
    }
    assert_eq!(
        sim.critters[0].pos, hunter,
        "a quiet delver is not heard: the hunter never moved"
    );
}

#[test]
fn sound_hunting_does_not_leak_to_other_bands() {
    // Floor 5: critters hunt as they always have — nearest
    // delver, any distance, quiet gear or not.
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 5);
    sim.critters.clear();
    let den = *sim
        .floor
        .as_ref()
        .unwrap()
        .dens
        .iter()
        .max_by_key(|p| p.x)
        .unwrap();
    sim.spawn_critter(underreach_sim::sim::CritterKind::DeepLurker, den);
    let hunter = sim.critters[0].pos;
    let mut stage = None;
    for y in 0..sim.world.sy as i32 {
        for x in 0..sim.world.sx as i32 {
            for z in 0..sim.world.sz as i32 {
                let p = Pos::new(x, y, z);
                let d = manhattan(hunter, p);
                if sim.world.get(p) == Some(Cell::Carved) && (13..=16).contains(&d) {
                    stage = Some(p);
                }
            }
        }
    }
    let stage = stage.expect("a staging cell on floor 5");
    sim.delvers[0].quiet = true; // quiet gear means nothing off its band
    sim.delvers[0].pos = stage;
    for _ in 0..60 {
        sim.tick();
        sim.delvers[0].pos = stage;
    }
    assert_ne!(
        sim.critters[0].pos, hunter,
        "off the Crystal Dark the hunter closes on even a quiet delver"
    );
}

// ---------------------------------------------------------------------------
// Brittle floors and marked routes
// ---------------------------------------------------------------------------

#[test]
fn an_unroped_crossing_brings_the_brittle_floor_down_and_a_roped_one_does_not() {
    // Unroped: the step onto the brittle cell collapses it —
    // the cell fills with rubble and the delver is hurt.
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 4);
    let (a, b) = deep_adjacent_pair(&sim);
    assert!(sim.brittle_at(b), "the deep cell is brittle before the crossing");
    stage_step(&mut sim, a, b);
    assert_eq!(sim.delvers[0].hp, 65.0, "the fall dealt its damage");
    assert_eq!(
        sim.world.get(b),
        Some(Cell::Stone),
        "the brittle cell is rubble after the fall"
    );
    assert_eq!(count(&sim, LedgerKind::BrittleCollapse), 1, "the fall is ledgered");

    // Roped: rope laid on the same cell first — the marked
    // route crosses safely, the floor holds, nobody is hurt.
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 4);
    let (a, b) = deep_adjacent_pair(&sim);
    sim.stores.goods += 1;
    assert!(sim.place_rope(b), "the route is marked before the crossing");
    assert!(!sim.brittle_at(b), "a roped cell is no longer brittle");
    stage_step(&mut sim, a, b);
    assert_eq!(sim.delvers[0].hp, 100.0, "the roped crossing hurt nobody");
    assert_eq!(
        sim.world.get(b),
        Some(Cell::Carved),
        "the roped floor holds"
    );
    assert_eq!(count(&sim, LedgerKind::BrittleCollapse), 0);
}

#[test]
fn brittle_floors_do_not_leak_to_other_bands() {
    // Floor 5's deep floors are hot, not brittle: the same
    // staged step costs nothing and breaks nothing there.
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 5);
    let (a, b) = deep_adjacent_pair(&sim);
    assert!(!sim.brittle_at(b), "no brittleness off the Crystal Dark");
    stage_step(&mut sim, a, b);
    assert_eq!(sim.delvers[0].hp, 100.0);
    assert_eq!(sim.world.get(b), Some(Cell::Carved));
    assert_eq!(count(&sim, LedgerKind::BrittleCollapse), 0);
}

#[test]
fn ropes_and_quiet_gear_follow_the_kit_rules() {
    let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 4);
    let camp = sim.stockpile; // carved
    let rock = Pos::new(0, 5, 0); // solid stone
    // A broke, crystal-less colony lays and crafts nothing.
    assert_eq!(sim.stores.goods, 0);
    assert!(!sim.place_rope(camp));
    assert!(!sim.craft_quiet_gear());
    // Rope refuses solid rock even with goods in hand.
    sim.stores.goods = 2;
    assert!(!sim.place_rope(rock));
    assert_eq!(sim.stores.goods, 2);
    // Quiet gear needs its cut crystal as well as its goods.
    assert!(!sim.craft_quiet_gear(), "no cut crystal, no quiet gear");
    sim.stores.cut_crystals = 1;
    assert!(sim.craft_quiet_gear());
    assert_eq!(sim.stores.goods, 1);
    assert_eq!(sim.stores.cut_crystals, 0);
    assert_eq!(sim.stores.quiet_gear, 1);
    // Rope costs 1 goods; no laying a second rope on its cell.
    assert!(sim.place_rope(camp));
    assert_eq!(sim.stores.goods, 0);
    assert!(!sim.place_rope(camp));
    assert_eq!(sim.ropes.len(), 1);
}

// ---------------------------------------------------------------------------
// Determinism
// ---------------------------------------------------------------------------

#[test]
fn s16_stays_deterministic_on_floor_4() {
    let run = || {
        let mut sim = build_scenario_gen_floor(GEN_WORLD_SEED, 4);
        open_current_floor(&mut sim);
        // Exercise the new save fields in the roundtrip: a rope
        // on the camp route, crystal in the stores, a cutter.
        sim.stores.goods += 1;
        sim.stores.crystal = 2;
        assert!(sim.place_rope(sim.stockpile));
        assert!(sim.set_job(0, Job::CrystalCutter));
        for _ in 0..1500 {
            sim.tick();
        }
        sim
    };
    let mut a = run();
    let b = run();
    assert_eq!(a.state_hash(), b.state_hash(), "twin-run identical");
    assert_eq!(
        a.stores.cut_crystals, 2,
        "the cutter worked both staged crystals during the run"
    );
    let saved = a.save_json();
    let mut loaded = Sim::load_json(&saved);
    assert_eq!(loaded.state_hash(), a.state_hash(), "load reproduces the hash");
    assert_eq!(loaded.ropes, a.ropes, "the marked route survives the roundtrip");
    for _ in 0..300 {
        a.tick();
        loaded.tick();
    }
    assert_eq!(a.state_hash(), loaded.state_hash(), "continuation identical");
}
