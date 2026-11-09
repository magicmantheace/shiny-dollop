-- Persistent local library. Version 1 foundation; future migrations required.
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS assets (
  asset_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  uri TEXT NOT NULL,
  rig_id TEXT,
  status TEXT NOT NULL CHECK(status IN ('candidate','approved','retired')),
  tags_json TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_assets_kind_status ON assets(kind, status);
CREATE INDEX IF NOT EXISTS idx_assets_rig ON assets(rig_id);
CREATE TABLE IF NOT EXISTS characters (
  character_id TEXT PRIMARY KEY,
  rig_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('candidate','approved','retired')),
  recipe_json TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS scenes (
  scene_id TEXT PRIMARY KEY,
  scene_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS validation_runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  asset_id TEXT,
  check_name TEXT NOT NULL,
  passed INTEGER NOT NULL CHECK(passed IN (0,1)),
  detail TEXT,
  ran_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(asset_id) REFERENCES assets(asset_id)
);
CREATE TABLE IF NOT EXISTS asset_dependencies (
  asset_id TEXT NOT NULL,
  dependency_id TEXT NOT NULL,
  PRIMARY KEY(asset_id,dependency_id),
  FOREIGN KEY(asset_id) REFERENCES assets(asset_id),
  FOREIGN KEY(dependency_id) REFERENCES assets(asset_id)
);
