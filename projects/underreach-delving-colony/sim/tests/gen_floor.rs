//! S6 acceptance: procedural floor generation — purity of the
//! (world_seed, floor_index) function, the passage-network
//! guarantees the owner set (2026-11-12), and the colony loop
//! running end-to-end on a generated Floor 1.

use underreach_sim::gen::{
    carved_distances, generate_floor, theme_for_floor, world_hash, Band, ENTRY,
};
use underreach_sim::scenario::{build_scenario_gen, open_floor1, GEN_WORLD_SEED};
use underreach_sim::sim::{CritterKind, DelverState, LedgerKind, Sim};
use underreach_sim::world::{Cell, Pos};

fn count(sim: &Sim, kind: LedgerKind) -> usize {
    sim.ledger.iter().filter(|e| e.kind == kind).count()
}

/// The seed spread the network guarantees are verified over.
fn spread() -> Vec<u64> {
    let mut v: Vec<u64> = (1..=16).collect();
    v.push(GEN_WORLD_SEED);
    v
}

fn dist_to(floor: &underreach_sim::gen::Floor, p: Pos) -> i32 {
    let dist = carved_distances(&floor.world, ENTRY);
    floor.world.idx(p).map(|i| dist[i]).unwrap_or(-1)
}

#[test]
fn same_seed_same_floor_every_time() {
    for seed in [1u64, 42, GEN_WORLD_SEED] {
        let a = generate_floor(seed, 1);
        let b = generate_floor(seed, 1);
        assert_eq!(world_hash(&a.world), world_hash(&b.world), "seed {seed}");
        assert_eq!(a.layout, b.layout, "seed {seed}");
    }
}

#[test]
fn floor_independence_from_generation_order() {
    // Standalone.
    let standalone: Vec<_> = (1..=4).map(|i| generate_floor(99, i)).collect();
    // Sequential 1..=4.
    let sequential: Vec<_> = (1..=4).map(|i| generate_floor(99, i)).collect();
    // Interleaved, out of order.
    let mut interleaved = Vec::new();
    for i in [4u32, 2, 3, 1] {
        interleaved.push(((i - 1) as usize, generate_floor(99, i)));
    }
    for (k, f) in interleaved {
        assert_eq!(world_hash(&f.world), world_hash(&standalone[k].world), "floor {}", k + 1);
        assert_eq!(f.layout, standalone[k].layout, "floor {}", k + 1);
    }
    for i in 0..4 {
        assert_eq!(world_hash(&sequential[i].world), world_hash(&standalone[i].world));
        assert_eq!(sequential[i].layout, standalone[i].layout);
    }
}

#[test]
fn different_seeds_and_floors_differ() {
    let h1 = world_hash(&generate_floor(1, 1).world);
    let h2 = world_hash(&generate_floor(2, 1).world);
    let h3 = world_hash(&generate_floor(3, 1).world);
    assert_ne!(h1, h2);
    assert_ne!(h1, h3);
    assert_ne!(h2, h3);
    // Same seed, different floor: a different world too.
    assert_ne!(h1, world_hash(&generate_floor(1, 2).world));
}

#[test]
fn passage_network_guarantees_hold_across_seeds() {
    let theme = theme_for_floor(1);
    for seed in spread() {
        let floor = generate_floor(seed, 1);
        let layout = &floor.layout;
        // The entry camp is the room the scenarios have always
        // used, and the layout's entry is the BFS origin.
        assert_eq!(layout.entry, ENTRY);
        for x in 2..=6 {
            for z in 3..=5 {
                assert_eq!(
                    floor.world.get(Pos::new(x, 3, z)),
                    Some(Cell::Carved),
                    "seed {seed}: camp room intact"
                );
            }
        }
        // The descent: reachable by passages alone, at least
        // the theme's minimum network distance, and the
        // layout's recorded distance is the measured one.
        let d_descent = dist_to(&floor, layout.descent);
        assert!(d_descent >= 0, "seed {seed}: descent reachable");
        assert_eq!(d_descent as u32, layout.descent_network_distance, "seed {seed}");
        assert!(
            layout.descent_network_distance >= theme.descent_min_network_distance,
            "seed {seed}: descent distance {} < {}",
            layout.descent_network_distance,
            theme.descent_min_network_distance
        );
        assert!(
            layout.descent_cavern.contains(&layout.descent),
            "seed {seed}: the stairs sit inside the descent cavern"
        );
        // Connected cavities are reached; sealed ones are not.
        for c in &layout.cavities {
            let d = dist_to(&floor, c.centre);
            if c.connected {
                assert!(d >= 0, "seed {seed}: connected cavity {:?} reached", c.centre);
            } else {
                assert!(d < 0, "seed {seed}: sealed cavity {:?} stays sealed", c.centre);
            }
        }
        // Dens on the network: at least the floor's minimum,
        // none of them within the minimum distance of the entry.
        let dens_on: Vec<&_> = layout.cavities.iter().filter(|c| c.den && c.connected).collect();
        assert!(
            dens_on.len() >= theme.dens_on_network,
            "seed {seed}: {} on-network dens < {}",
            dens_on.len(),
            theme.dens_on_network
        );
        for den in &dens_on {
            let d = dist_to(&floor, den.centre);
            assert!(
                d >= theme.den_min_network_distance as i32,
                "seed {seed}: den at {:?} is {} steps from entry (< {})",
                den.centre,
                d,
                theme.den_min_network_distance
            );
            assert!(den.critter.is_some(), "seed {seed}: a den has a resident");
        }
        // Off-network dens are the minority.
        let dens_off = layout.cavities.iter().filter(|c| c.den && !c.connected).count();
        assert!(dens_off < dens_on.len(), "seed {seed}: sealed dens stay a minority");
        // The node graph holds a loop, not just a chain.
        assert!(
            layout.links.len() > layout.nodes.len() - 1,
            "seed {seed}: links {} vs nodes {} — no loop",
            layout.links.len(),
            layout.nodes.len()
        );
        // Faces: registered veins stand on carved space and
        // their rock is a resource cell in the world.
        assert!(!layout.faces.is_empty(), "seed {seed}: at least one workable face");
        assert!(layout.faces.len() <= theme.face_veins_max, "seed {seed}");
        for f in &layout.faces {
            assert_eq!(floor.world.get(f.stand), Some(Cell::Carved), "seed {seed}");
            assert_eq!(floor.world.get(f.rock), Some(Cell::Ore), "seed {seed}");
        }
        // Veins: the theme's count, with at least one pocket
        // sealed off-network (the richest stay in the rock).
        assert_eq!(layout.veins.len(), theme.veins, "seed {seed}");
        assert!(
            layout.veins.iter().any(|v| !v.is_face),
            "seed {seed}: at least one embedded pocket"
        );
    }
}

#[test]
fn hazard_pockets_are_embedded_as_cells() {
    let theme = theme_for_floor(1);
    for seed in [1u64, 2, 3, GEN_WORLD_SEED] {
        let floor = generate_floor(seed, 1);
        let mut loose = 0;
        let mut bad_air = 0;
        for h in &floor.layout.hazards {
            match h.kind {
                underreach_sim::gen::HazardKind::LooseRock => {
                    assert_eq!(floor.world.get(h.pos), Some(Cell::Loose), "seed {seed}");
                    loose += 1;
                }
                underreach_sim::gen::HazardKind::BadAir => {
                    assert_eq!(floor.world.get(h.pos), Some(Cell::BadAir), "seed {seed}");
                    assert!(h.pos.y >= 6, "seed {seed}: bad air pools deep");
                    bad_air += 1;
                }
            }
        }
        // The world's hazard cells are exactly the layout's —
        // generation accounts for everything it embeds.
        let mut world_loose = 0;
        let mut world_bad_air = 0;
        for y in 0..floor.world.sy as i32 {
            for x in 0..floor.world.sx as i32 {
                for z in 0..floor.world.sz as i32 {
                    match floor.world.get(Pos::new(x, y, z)) {
                        Some(Cell::Loose) => world_loose += 1,
                        Some(Cell::BadAir) => world_bad_air += 1,
                        _ => {}
                    }
                }
            }
        }
        assert_eq!(loose, world_loose, "seed {seed}");
        assert_eq!(bad_air, world_bad_air, "seed {seed}");
        assert!(loose >= 1 && loose <= theme.loose_count * theme.loose_size.1, "seed {seed}");
        assert!(
            bad_air >= 1 && bad_air <= theme.bad_air_count * theme.bad_air_size.1,
            "seed {seed}"
        );
    }
}

#[test]
fn generation_does_not_consume_the_runtime_rng() {
    // Generating floors is not a sim operation at all; the
    // scenario founded on a generated floor starts with its
    // runtime RNG exactly at the world seed, and the player's
    // opening script (lanterns only) draws nothing either.
    let mut sim = build_scenario_gen(GEN_WORLD_SEED);
    assert_eq!(sim.world_seed, GEN_WORLD_SEED);
    assert_eq!(sim.rng_state, GEN_WORLD_SEED);
    open_floor1(&mut sim);
    assert_eq!(sim.rng_state, GEN_WORLD_SEED, "opening the floor drew no runtime RNG");
    assert!(sim.floor.is_some(), "the sim carries its floor record");
}

#[test]
fn save_load_reproduces_the_generated_floor() {
    let mut sim = build_scenario_gen(GEN_WORLD_SEED);
    open_floor1(&mut sim);
    for _ in 0..500 {
        sim.tick();
    }
    let saved = sim.save_json();
    let hash = sim.state_hash();
    let mut loaded = Sim::load_json(&saved);
    assert_eq!(loaded.state_hash(), hash);
    assert_eq!(loaded.floor, sim.floor, "the floor record survives the save");
    assert_eq!(loaded.world_seed, GEN_WORLD_SEED);
    for _ in 0..300 {
        sim.tick();
        loaded.tick();
    }
    assert_eq!(sim.state_hash(), loaded.state_hash());
}

#[test]
fn floor1_supports_the_colony_loop() {
    let mut sim = build_scenario_gen(GEN_WORLD_SEED);
    // Phase 1 — the dark refuses: the first face stands beyond
    // the camp lantern's reach, down the passages.
    for _ in 0..200 {
        sim.tick();
    }
    assert_eq!(sim.stores.goods, 0);
    assert_eq!(count(&sim, LedgerKind::HaulDelivered), 0);
    assert!(count(&sim, LedgerKind::RouteBlocked) >= 1, "the refusal is ledgered");
    // Phase 2 — the player carries light down the passages.
    open_floor1(&mut sim);
    assert!(
        sim.ledger
            .iter()
            .any(|e| e.kind == LedgerKind::FirstLight && e.detail.contains("depth 8")
                || (e.kind == LedgerKind::FirstLight && e.detail.contains("depth 7"))
                || (e.kind == LedgerKind::FirstLight && e.detail.contains("depth 9"))),
        "opening the floor lights new depths"
    );
    for _ in 0..6000 {
        sim.tick();
    }
    assert!(
        count(&sim, LedgerKind::HaulDelivered) >= 3,
        "deliveries: {}",
        count(&sim, LedgerKind::HaulDelivered)
    );
    assert!(sim.stores.goods >= 2, "goods={}", sim.stores.goods);
    assert_eq!(count(&sim, LedgerKind::DelverLost), 0, "nobody is lost on the opened floor");
    assert!(sim.delvers.len() >= 3, "the colony stands");
}

#[test]
fn rescue_works_on_the_generated_floor() {
    let mut sim = build_scenario_gen(GEN_WORLD_SEED);
    open_floor1(&mut sim);
    let stand = sim.faces[0].stand;
    // Bram works the face, hurt; a deep lurker comes out of the
    // rock beside him (choreography follows the S3 corridor
    // proof, staged on generated geometry).
    let lurker_pos = stand
        .neighbors6()
        .iter()
        .copied()
        .find(|p| sim.world.get(*p) == Some(Cell::Carved) && *p != sim.stockpile)
        .expect("the stand has a carved neighbour");
    sim.delvers[0].pos = stand;
    sim.delvers[0].hp = 6.0;
    sim.delvers[0].state = DelverState::Idle;
    sim.spawn_critter(CritterKind::DeepLurker, lurker_pos);
    let mut rescued = false;
    for _ in 0..1500 {
        sim.tick();
        if count(&sim, LedgerKind::DelverRescued) >= 1 {
            rescued = true;
            break;
        }
    }
    assert_eq!(count(&sim, LedgerKind::DelverDowned), 1, "the lurker downs Bram");
    assert!(rescued, "a rescuer carries Bram home down the lit passages");
    assert_eq!(count(&sim, LedgerKind::DelverLost), 0);
    assert!(sim.delvers.len() >= 3, "the colony stands");
}

#[test]
fn stub_bands_generate_through_the_same_generator() {
    // Floor 2 (Fungal Reaches): a stub theme — it generates
    // through the same code, with its second resource present,
    // and carries no balance claims (`built` stays false).
    assert!(!theme_for_floor(2).built);
    let f2 = generate_floor(7, 2);
    assert_eq!(f2.layout.band, Band::FungalReaches);
    let mut fungal = 0;
    for y in 0..f2.world.sy as i32 {
        for x in 0..f2.world.sx as i32 {
            for z in 0..f2.world.sz as i32 {
                if f2.world.get(Pos::new(x, y, z)) == Some(Cell::FungalNode) {
                    fungal += 1;
                }
            }
        }
    }
    assert!(fungal > 0, "the Fungal Reaches embed fungal nodes");
    assert_eq!(generate_floor(7, 5).layout.band, Band::MagmaRoots);
    // Below the Magma Roots the bands recombine (owner decision 9).
    assert_eq!(generate_floor(7, 6).layout.band, Band::FungalReaches);
}
