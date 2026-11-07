// SPDX-License-Identifier: MPL-2.0
use serde_json::{Value, json};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::os::unix::fs::{DirBuilderExt, OpenOptionsExt};
use std::process::Command;

#[test]
fn offline_cli_exports_verifies_and_refuses_replacement_or_bad_arguments() {
    let root = std::env::temp_dir().join(format!("synveil-export-cli-{}", std::process::id()));
    fs::DirBuilder::new().mode(0o700).create(&root).unwrap();
    let copies = root.join("copies");
    fs::DirBuilder::new().mode(0o700).create(&copies).unwrap();
    let source = root.join("journal");
    let copy = copies.join("snapshot");
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(&source)
        .unwrap();
    writeln!(
        file,
        "{}",
        veil_core::audit::record("request", json!({"private": "secret"}))
    )
    .unwrap();
    drop(file);
    let tool = env!("CARGO_BIN_EXE_veil-audit");
    let exported = Command::new(tool)
        .arg("export")
        .arg("--path")
        .arg(&source)
        .arg("--output")
        .arg(&copy)
        .output()
        .unwrap();
    assert!(exported.status.success());
    let receipt: Value = serde_json::from_slice(&exported.stdout).unwrap();
    assert!(!String::from_utf8_lossy(&exported.stdout).contains("secret"));
    let digest = receipt["digest"].as_str().unwrap();
    let verified = Command::new(tool)
        .arg("verify")
        .arg("--path")
        .arg(&copy)
        .arg("--digest")
        .arg(digest)
        .output()
        .unwrap();
    assert!(verified.status.success());
    let saved = fs::read(&copy).unwrap();
    let refused = Command::new(tool)
        .arg("export")
        .arg("--path")
        .arg(&source)
        .arg("--output")
        .arg(&copy)
        .output()
        .unwrap();
    assert!(!refused.status.success());
    assert_eq!(fs::read(&copy).unwrap(), saved);
    for arguments in [
        vec!["export"],
        vec!["verify", "--digest", "private-input"],
        vec!["check", "--output", "private-input"],
        vec!["check", "--path", "a", "--path", "b"],
        vec!["check", "--snapshot", "private-input"],
        vec!["export", "--authorization", "private-input"],
        vec!["release-archive"],
        vec!["release-archive", "--path", "a", "--path", "b"],
    ] {
        let result = Command::new(tool).args(arguments).output().unwrap();
        assert!(!result.status.success());
        assert!(!String::from_utf8_lossy(&result.stderr).contains("private-input"));
    }
    let archive = source.with_file_name("journal.1");
    fs::copy(&source, &archive).unwrap();
    let intent = copies.join("release.json");
    let released = Command::new(tool)
        .arg("release-archive")
        .arg("--path")
        .arg(&source)
        .arg("--snapshot")
        .arg(&copy)
        .arg("--authorization")
        .arg(&intent)
        .arg("--digest")
        .arg(digest)
        .output()
        .unwrap();
    assert!(released.status.success());
    let released_report: Value = serde_json::from_slice(&released.stdout).unwrap();
    assert_eq!(released_report["released"], true);
    assert!(!archive.exists());
    assert_eq!(fs::read(&source).unwrap(), saved);
    assert_eq!(fs::read(&copy).unwrap(), saved);
    assert!(!String::from_utf8_lossy(&released.stdout).contains("secret"));
    assert!(intent.exists());
    fs::remove_dir_all(root).unwrap();
}

#[test]
fn offline_cli_verifies_v2_export_against_its_receipt() {
    use std::io::{BufReader, Write as _};
    use std::os::unix::net::UnixStream;
    use std::time::{Duration, Instant};
    let root = std::env::temp_dir().join(format!("synveil-export-v2-{}", std::process::id()));
    fs::DirBuilder::new().mode(0o700).create(&root).unwrap();
    let copies = root.join("copies");
    fs::DirBuilder::new().mode(0o700).create(&copies).unwrap();
    // Produce a genuine chained v2 journal with the real core.
    let socket = root.join("core.sock");
    let journal = root.join("core-audit.jsonl");
    let core = Command::new(env!("CARGO_BIN_EXE_veil-core"))
        .arg("--once")
        .arg("--socket")
        .arg(&socket)
        .env("SYNVEIL_AUDIT_PATH", &journal)
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .unwrap();
    let deadline = Instant::now() + Duration::from_secs(10);
    let mut stream = loop {
        if let Ok(stream) = UnixStream::connect(&socket) {
            break stream;
        }
        assert!(Instant::now() < deadline, "core never accepted connections");
        std::thread::sleep(Duration::from_millis(10));
    };
    stream
        .set_read_timeout(Some(Duration::from_secs(5)))
        .unwrap();
    let request = veil_protocol::Request::new("audit-test", "status", json!({}));
    stream
        .write_all(&veil_protocol::encode_line(&request).unwrap())
        .unwrap();
    let mut reader = BufReader::new(stream.try_clone().unwrap());
    let response =
        veil_protocol::decode_response(&veil_protocol::read_frame(&mut reader).unwrap().unwrap())
            .unwrap();
    assert!(response.ok);
    drop(reader);
    drop(stream);
    let output = core.wait_with_output().unwrap();
    assert!(output.status.success());
    let journal_bytes = fs::read(&journal).unwrap();
    assert!(String::from_utf8_lossy(&journal_bytes).contains("synveil.audit/v2"));

    let tool = env!("CARGO_BIN_EXE_veil-audit");
    let copy = copies.join("snapshot");
    let exported = Command::new(tool)
        .arg("export")
        .arg("--path")
        .arg(&journal)
        .arg("--output")
        .arg(&copy)
        .output()
        .unwrap();
    assert!(exported.status.success());
    let receipt: Value = serde_json::from_slice(&exported.stdout).unwrap();
    let chain = &receipt["chain"];
    for key in ["anchor", "head_digest"] {
        let value = chain[key].as_str().unwrap();
        assert_eq!(value.len(), 128);
        assert!(
            value
                .bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
        );
    }
    assert!(chain["chained_records"].as_u64().unwrap() >= 1);
    assert_eq!(chain["records"], receipt["records"]);
    // The receipt the owner retains is the export stdout, verbatim.
    let receipt_path = copies.join("receipt.json");
    fs::write(&receipt_path, &exported.stdout).unwrap();
    let verified = Command::new(tool)
        .arg("verify")
        .arg("--path")
        .arg(&copy)
        .arg("--receipt")
        .arg(&receipt_path)
        .output()
        .unwrap();
    assert!(verified.status.success());
    // The legacy digest path still verifies the same snapshot.
    let verified = Command::new(tool)
        .arg("verify")
        .arg("--path")
        .arg(&copy)
        .arg("--digest")
        .arg(receipt["digest"].as_str().unwrap())
        .output()
        .unwrap();
    assert!(verified.status.success());
    // A truncated copy fails receipt verification.
    let text = String::from_utf8(fs::read(&copy).unwrap()).unwrap();
    let line_count = text.lines().count();
    assert!(line_count > 1, "core journal should hold several records");
    let truncated = text
        .lines()
        .take(line_count - 1)
        .map(|line| format!("{line}\n"))
        .collect::<String>();
    fs::write(&copy, truncated).unwrap();
    let refused = Command::new(tool)
        .arg("verify")
        .arg("--path")
        .arg(&copy)
        .arg("--receipt")
        .arg(&receipt_path)
        .output()
        .unwrap();
    assert!(!refused.status.success());
    fs::write(&copy, &journal_bytes).unwrap();
    // A receipt naming the wrong anchor fails against the intact copy.
    let mut wrong = receipt.clone();
    wrong["chain"]["anchor"] = json!("1".repeat(128));
    fs::write(&receipt_path, format!("{wrong}\n")).unwrap();
    let refused = Command::new(tool)
        .arg("verify")
        .arg("--path")
        .arg(&copy)
        .arg("--receipt")
        .arg(&receipt_path)
        .output()
        .unwrap();
    assert!(!refused.status.success());
    // Argument discipline: receipt is verify-only and exclusive.
    for arguments in [
        vec!["verify", "--receipt", "private-input"],
        vec!["export", "--receipt", "private-input"],
        vec!["check", "--receipt", "private-input"],
        vec!["release-archive", "--receipt", "private-input"],
    ] {
        let result = Command::new(tool).args(arguments).output().unwrap();
        assert!(!result.status.success());
        assert!(!String::from_utf8_lossy(&result.stderr).contains("private-input"));
    }
    let both = Command::new(tool)
        .arg("verify")
        .arg("--path")
        .arg(&copy)
        .arg("--digest")
        .arg(receipt["digest"].as_str().unwrap())
        .arg("--receipt")
        .arg(&receipt_path)
        .output()
        .unwrap();
    assert!(!both.status.success());
    fs::remove_dir_all(root).unwrap();
}
