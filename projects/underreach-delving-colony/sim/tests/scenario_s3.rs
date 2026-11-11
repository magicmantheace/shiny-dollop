//! S3 acceptance: the dark bites — combat, a rescue on the clock,
//! a loss when no rescue comes, and stranding when the light dies.

use underreach_sim::scenario::{build_scenario, build_scenario_s3, light_the_way, CAMP_LANTERN};
use underreach_sim::sim::{
    CritterKind, Delver, Job, LedgerKind, Sim, Stores,
};
use underreach_sim::world::{Cell, Pos, World};

fn count(sim: &Sim, kind: LedgerKind) -> usize {
    sim.ledger.iter().filter(|e| e.kind == kind).count()
}

/// A bare carved corridor, optionally lit, for choreographed tests.
fn corridor_sim(lit: bool, delvers: Vec<Delver>) -> Sim {
    let mut world = World::new(12, 3, 3, Cell::Stone);
    for x in 0..12 {
        world.carve(Pos::new(x, 1, 1));
    }
    let mut sim = Sim::new(
        world,
        delvers,
        Pos::new(0, 1, 1),
        vec![Pos::new(0, 1, 1)],
        vec![],
        Pos::new(0, 1, 1),
        Stores {
            ore: 0,
            goods: 0,
            food: 10,
        },
        0x5EED_0010,
        u64::MAX,
        true,
    );
    if lit {
        sim.place_lantern(Pos::new(1, 1, 1), 3, 1_000_000.0);
        sim.place_lantern(Pos::new(8, 1, 1), 3, 1_000_000.0);
    }
    sim
}

#[test]
fn delver_kills_a_rat_in_the_dark() {
    // No lanterns at all: no light damage, no way home — the fight
    // is purely Bram's.
    let bram = Delver::new(0, "Bram", Pos::new(0, 1, 1), Job::Miner);
    let mut sim = corridor_sim(false, vec![bram]);
    sim.spawn_critter(CritterKind::GloamRat, Pos::new(1, 1, 1));
    for _ in 0..300 {
        sim.tick();
    }
    assert!(sim.critters.is_empty(), "the rat should be dead");
    assert_eq!(count(&sim, LedgerKind::CreatureSlain), 1);
    assert!(
        sim.ledger
            .iter()
            .any(|e| e.kind == LedgerKind::CreatureSlain && e.detail.contains("Bram slew")),
        "the kill should be credited to Bram"
    );
    let bram = &sim.delvers[0];
    assert!(bram.combat_xp > 0);
    assert!(
        bram.hp < 100.0 && bram.hp > 30.0,
        "Bram should be bitten but standing, hp={}",
        bram.hp
    );
}

#[test]
fn downed_delver_is_rescued_on_the_clock() {
    let mut bram = Delver::new(0, "Bram", Pos::new(10, 1, 1), Job::Miner);
    bram.hp = 6.0;
    let hale = Delver::new(1, "Hale", Pos::new(1, 1, 1), Job::Hauler);
    let mut sim = corridor_sim(true, vec![bram, hale]);
    sim.spawn_critter(CritterKind::DeepLurker, Pos::new(11, 1, 1));
    let mut rescued = false;
    for _ in 0..600 {
        sim.tick();
        if count(&sim, LedgerKind::DelverRescued) >= 1 {
            rescued = true;
            break;
        }
    }
    assert_eq!(count(&sim, LedgerKind::DelverDowned), 1);
    assert!(rescued, "Hale should carry Bram home before the clock runs out");
    assert_eq!(sim.delvers.len(), 2, "nobody is lost");
    let bram = sim.delvers.iter().find(|d| d.name == "Bram").unwrap();
    assert!(bram.hp >= 30.0, "rescued Bram is patched up, hp={}", bram.hp);
}

#[test]
fn downed_alone_is_lost_when_the_clock_runs_out() {
    let mut bram = Delver::new(0, "Bram", Pos::new(10, 1, 1), Job::Miner);
    bram.hp = 5.0;
    let mut sim = corridor_sim(true, vec![bram]);
    sim.spawn_critter(CritterKind::DeepLurker, Pos::new(11, 1, 1));
    for _ in 0..1100 {
        sim.tick();
    }
    assert_eq!(count(&sim, LedgerKind::DelverDowned), 1);
    assert_eq!(count(&sim, LedgerKind::DelverLost), 1);
    assert!(sim.delvers.is_empty(), "a lone downed delver is lost");
    assert!(
        sim.ledger
            .iter()
            .any(|e| e.kind == LedgerKind::DelverLost && e.detail.contains("Bram")),
        "the Ledger keeps the lost delver's name"
    );
}

#[test]
fn when_the_light_dies_the_way_home_closes() {
    let mut sim = build_scenario();
    light_the_way(&mut sim);
    // Let Bram get to the face.
    for _ in 0..400 {
        sim.tick();
        if sim.delvers[0].pos == Pos::new(14, 8, 4) {
            break;
        }
    }
    assert_eq!(sim.delvers[0].pos, Pos::new(14, 8, 4));
    // Kill every lantern but the camp's.
    for e in sim.lanterns.iter_mut() {
        if e.pos != CAMP_LANTERN {
            e.fuel = 0.0;
        }
    }
    sim.refresh_light();
    for _ in 0..100 {
        sim.tick();
    }
    assert!(
        sim.delvers[0].dark_clock.is_some(),
        "Bram should be on the dark clock"
    );
    for _ in 0..700 {
        sim.tick();
    }
    assert_eq!(count(&sim, LedgerKind::DelverLost), 1);
    assert!(sim.delvers.is_empty());
}

#[test]
fn s3_colony_produces_under_threat_and_stays_deterministic() {
    let mut a = build_scenario_s3();
    light_the_way(&mut a);
    let mut b = build_scenario_s3();
    light_the_way(&mut b);
    for _ in 0..1500 {
        a.tick();
        b.tick();
    }
    assert_eq!(a.state_hash(), b.state_hash(), "same inputs, same world");
    for _ in 0..4500 {
        a.tick();
    }
    assert!(
        a.stores.goods >= 2,
        "the colony should keep producing under threat, goods={}",
        a.stores.goods
    );
    // Save/load continuation mid-slice.
    let saved = a.save_json();
    let hash = a.state_hash();
    let mut loaded = Sim::load_json(&saved);
    assert_eq!(loaded.state_hash(), hash);
    for _ in 0..300 {
        a.tick();
        loaded.tick();
    }
    assert_eq!(a.state_hash(), loaded.state_hash());
}
