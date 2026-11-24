//! Bridge acceptance: the file protocol the Godot frontend speaks.
//! init an S3 colony, send the light-the-way command in steps, and
//! the colony must produce goods through the bridge alone.

use std::process::Command;

fn run(args: &[&str]) {
    let out = Command::new(env!("CARGO_BIN_EXE_bridge"))
        .args(args)
        .output()
        .expect("bridge runs");
    assert!(
        out.status.success(),
        "bridge {:?} failed: {}",
        args,
        String::from_utf8_lossy(&out.stderr)
    );
}

#[test]
fn bridge_drives_a_colony_to_production() {
    let dir = std::env::temp_dir().join("underreach-bridge-test");
    std::fs::create_dir_all(&dir).unwrap();
    let state = dir.join("state.json");
    let cmds = dir.join("cmds.json");
    let out = dir.join("out.json");
    let (state_s, cmds_s, out_s) = (
        state.to_str().unwrap(),
        cmds.to_str().unwrap(),
        out.to_str().unwrap(),
    );

    run(&["init", "s3", state_s]);
    std::fs::write(&cmds, r#"[{"cmd":"light_the_way"}]"#).unwrap();
    run(&["step", state_s, cmds_s, "10", out_s]);
    std::fs::copy(&out, &state).unwrap();
    std::fs::write(&cmds, "[]").unwrap();
    for _ in 0..40 {
        run(&["step", state_s, cmds_s, "100", out_s]);
        std::fs::copy(&out, &state).unwrap();
    }
    let raw = std::fs::read_to_string(&state).unwrap();
    let v: serde_json::Value = serde_json::from_str(&raw).unwrap();
    let view = &v["view"];
    assert!(
        view["stores"]["goods"].as_u64().unwrap_or(0) >= 1,
        "the bridge-driven colony should produce goods, view stores: {}",
        view["stores"]
    );
    assert!(view["delvers"].as_array().map_or(0, |a| a.len()) >= 3);
    assert!(view["tick"].as_u64().unwrap_or(0) >= 4000);
}
