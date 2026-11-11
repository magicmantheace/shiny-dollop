//! File-based bridge between the sim core and the Godot frontend.
//!
//! The frontend holds no sim rules: it writes a state file (the
//! canonical save) plus a commands file, calls this binary, and
//! renders the view JSON that comes back.
//!
//! Usage:
//!   bridge init <s1|s2|s3|s5> <out.json>
//!   bridge step <state.json> <commands.json> <ticks> <out.json>
//!
//! state.json / out.json: {"save": "<canonical sim json>", "view": {...}}
//! commands.json: a JSON array of command objects:
//!   {"cmd":"carve","pos":[x,y,z]}
//!   {"cmd":"lantern","pos":[x,y,z],"tier":1}
//!   {"cmd":"job","id":0,"job":"Miner"}
//!   {"cmd":"plant","pos":[x,y,z]}
//!   {"cmd":"craft_mask"}
//!   {"cmd":"light_the_way"} / {"cmd":"light_the_deep"}

use std::process::exit;

use serde_json::{json, Value};

use underreach_sim::scenario::{
    build_scenario, build_scenario_s2, build_scenario_s3, build_scenario_s5, light_the_deep,
    light_the_way,
};
use underreach_sim::sim::{Job, Sim};
use underreach_sim::world::{Cell, Pos};

fn pos(v: &Value) -> Option<Pos> {
    let a = v.as_array()?;
    if a.len() != 3 {
        return None;
    }
    Some(Pos::new(
        a[0].as_i64()? as i32,
        a[1].as_i64()? as i32,
        a[2].as_i64()? as i32,
    ))
}

fn job(s: &str) -> Option<Job> {
    match s {
        "Miner" => Some(Job::Miner),
        "Hauler" => Some(Job::Hauler),
        "Farmer" => Some(Job::Farmer),
        "Herbalist" => Some(Job::Herbalist),
        "Unassigned" => Some(Job::Unassigned),
        _ => None,
    }
}

fn apply(sim: &mut Sim, cmd: &Value) {
    match cmd.get("cmd").and_then(|c| c.as_str()) {
        Some("carve") => {
            if let Some(p) = cmd.get("pos").and_then(pos) {
                sim.carve(p);
            }
        }
        Some("lantern") => {
            if let Some(p) = cmd.get("pos").and_then(pos) {
                let tier = cmd.get("tier").and_then(|t| t.as_u64()).unwrap_or(1) as u8;
                sim.place_lantern(p, tier, 5_000.0);
            }
        }
        Some("job") => {
            if let (Some(id), Some(j)) = (
                cmd.get("id").and_then(|i| i.as_u64()),
                cmd.get("job").and_then(|j| j.as_str()).and_then(job),
            ) {
                sim.set_job(id as u32, j);
            }
        }
        Some("plant") => {
            if let Some(p) = cmd.get("pos").and_then(pos) {
                sim.plant_plot(p);
            }
        }
        Some("craft_mask") => {
            sim.craft_mask();
        }
        Some("light_the_way") => light_the_way(sim),
        Some("light_the_deep") => light_the_deep(sim),
        _ => {}
    }
}

fn view(sim: &Sim) -> Value {
    let mut carved: Vec<Value> = Vec::new();
    let mut lit: Vec<Value> = Vec::new();
    for y in 0..sim.world.sy as i32 {
        for x in 0..sim.world.sx as i32 {
            for z in 0..sim.world.sz as i32 {
                let p = Pos::new(x, y, z);
                if sim.world.get(p) == Some(Cell::Carved) {
                    carved.push(json!([x, y, z]));
                    if let Some(i) = sim.world.idx(p) {
                        if sim.lit.get(i).copied().unwrap_or(false) {
                            lit.push(json!([x, y, z]));
                        }
                    }
                }
            }
        }
    }
    let delvers: Vec<Value> = sim
        .delvers
        .iter()
        .map(|d| {
            json!({
                "id": d.id, "name": d.name,
                "pos": [d.pos.x, d.pos.y, d.pos.z],
                "job": format!("{:?}", d.job),
                "state": format!("{:?}", d.state),
                "hp": d.hp, "energy": d.energy, "hunger": d.hunger,
                "morale": d.morale, "spore": d.spore, "masked": d.masked,
                "carrying": d.carrying,
                "carrying_kind": format!("{:?}", d.carrying_kind),
                "mining_xp": d.mining_xp, "hauling_xp": d.hauling_xp,
                "farming_xp": d.farming_xp, "combat_xp": d.combat_xp,
                "dark_clock": d.dark_clock,
            })
        })
        .collect();
    let critters: Vec<Value> = sim
        .critters
        .iter()
        .map(|c| {
            json!({
                "id": c.id, "kind": format!("{:?}", c.kind),
                "pos": [c.pos.x, c.pos.y, c.pos.z], "hp": c.hp,
            })
        })
        .collect();
    let lanterns: Vec<Value> = sim
        .lanterns
        .iter()
        .map(|l| json!({"pos": [l.pos.x, l.pos.y, l.pos.z], "tier": l.tier, "fuel": l.fuel}))
        .collect();
    let faces: Vec<Value> = sim
        .faces
        .iter()
        .map(|f| {
            json!({
                "rock": [f.rock.x, f.rock.y, f.rock.z],
                "stand": [f.stand.x, f.stand.y, f.stand.z],
                "ore": f.ore, "cache": f.cache,
                "yield": format!("{:?}", f.yield_kind),
            })
        })
        .collect();
    let plots: Vec<Value> = sim
        .plots
        .iter()
        .map(|p| json!({"pos": [p.pos.x, p.pos.y, p.pos.z], "growth": p.growth}))
        .collect();
    let ledger: Vec<Value> = sim
        .ledger
        .iter()
        .rev()
        .take(25)
        .map(|e| json!({"tick": e.tick, "kind": format!("{:?}", e.kind), "detail": e.detail}))
        .collect();
    json!({
        "tick": sim.tick_count,
        "dims": [sim.world.sx, sim.world.sy, sim.world.sz],
        "carved": carved,
        "lit": lit,
        "lanterns": lanterns,
        "faces": faces,
        "plots": plots,
        "delvers": delvers,
        "critters": critters,
        "stockpile": [sim.stockpile.x, sim.stockpile.y, sim.stockpile.z],
        "beds": sim.beds.iter().map(|b| json!([b.x, b.y, b.z])).collect::<Vec<_>>(),
        "gate": [sim.gate.x, sim.gate.y, sim.gate.z],
        "stores": {
            "ore": sim.stores.ore, "goods": sim.stores.goods, "food": sim.stores.food,
            "fungal_oil": sim.stores.fungal_oil, "masks": sim.stores.masks,
        },
        "ledger": ledger,
    })
}

fn write_out(sim: &Sim, path: &str) {
    let out = json!({"save": sim.save_json(), "view": view(sim)});
    std::fs::write(path, out.to_string()).expect("write output file");
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(|s| s.as_str()) {
        Some("init") => {
            let sim = match args.get(2).map(|s| s.as_str()) {
                Some("s1") => build_scenario(),
                Some("s2") => build_scenario_s2(),
                Some("s3") => build_scenario_s3(),
                Some("s5") => build_scenario_s5(),
                _ => {
                    eprintln!("unknown scenario (want s1|s2|s3|s5)");
                    exit(2);
                }
            };
            write_out(&sim, &args[3]);
        }
        Some("step") => {
            let state_raw = std::fs::read_to_string(&args[2]).expect("read state file");
            let state: Value = serde_json::from_str(&state_raw).expect("state json parses");
            let save = state.get("save").and_then(|s| s.as_str()).expect("state has save");
            let mut sim = Sim::load_json(save);
            let cmds_raw = std::fs::read_to_string(&args[3]).unwrap_or_else(|_| "[]".into());
            let cmds: Value = serde_json::from_str(&cmds_raw).unwrap_or(json!([]));
            if let Some(arr) = cmds.as_array() {
                for c in arr {
                    apply(&mut sim, c);
                }
            }
            let ticks: u64 = args[4].parse().expect("ticks is a number");
            for _ in 0..ticks {
                sim.tick();
            }
            write_out(&sim, &args[5]);
        }
        _ => {
            eprintln!("usage: bridge init <s1|s2|s3|s5> <out.json> | bridge step <state.json> <commands.json> <ticks> <out.json>");
            exit(2);
        }
    }
}
