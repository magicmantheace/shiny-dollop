"""Persistent asset registry. All inserts are parameterized and status-gated."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from .schema import validate_asset, validate_character, validate_scene

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "studio.sqlite3"
DDL = ROOT / "database" / "schema.sql"

class Library:
    def __init__(self, path: Path = DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path))
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")

    def close(self) -> None:
        self.db.close()

    def init(self) -> None:
        self.db.executescript(DDL.read_text(encoding="utf-8"))
        self.db.commit()

    def put_asset(self, asset: dict) -> None:
        validate_asset(asset)
        self.db.execute(
            "INSERT INTO assets(asset_id, kind, uri, rig_id, status, tags_json, metadata_json) "
            "VALUES(?,?,?,?,?,?,?) ON CONFLICT(asset_id) DO UPDATE SET "
            "kind=excluded.kind,uri=excluded.uri,rig_id=excluded.rig_id,status=excluded.status,"
            "tags_json=excluded.tags_json,metadata_json=excluded.metadata_json",
            (asset["asset_id"], asset["kind"], asset["uri"], asset.get("rig_id"), asset["status"],
             json.dumps(asset["tags"]), json.dumps(asset["metadata"])),
        )
        self.db.commit()

    def put_character(self, character: dict) -> None:
        validate_character(character)
        self.db.execute(
            "INSERT INTO characters(character_id, rig_id, status, recipe_json) VALUES(?,?,?,?) "
            "ON CONFLICT(character_id) DO UPDATE SET rig_id=excluded.rig_id,"
            "status=excluded.status,recipe_json=excluded.recipe_json",
            (character["character_id"], character["rig_id"], character["status"], json.dumps(character)),
        )
        self.db.commit()

    def put_scene(self, scene: dict) -> None:
        validate_scene(scene)
        self.db.execute(
            "INSERT INTO scenes(scene_id, scene_json) VALUES(?,?) "
            "ON CONFLICT(scene_id) DO UPDATE SET scene_json=excluded.scene_json",
            (scene["scene_id"], json.dumps(scene)),
        )
        self.db.commit()

    def list_assets(self, approved_only: bool = False) -> list[dict]:
        sql = "SELECT asset_id,kind,uri,rig_id,status,tags_json FROM assets"
        if approved_only:
            sql += " WHERE status='approved'"
        sql += " ORDER BY asset_id"
        return [dict(x) for x in self.db.execute(sql).fetchall()]

    def get_asset(self, asset_id: str) -> dict | None:
        row = self.db.execute(
            "SELECT asset_id,kind,uri,rig_id,status,tags_json,metadata_json "
            "FROM assets WHERE asset_id=?", (asset_id,)).fetchone()
        if row is None:
            return None
        asset = dict(row)
        asset["tags"] = json.loads(asset.pop("tags_json"))
        asset["metadata"] = json.loads(asset.pop("metadata_json"))
        return asset

    def get_asset_by_uri(self, uri: str) -> dict | None:
        row = self.db.execute(
            "SELECT asset_id FROM assets WHERE uri=?", (uri,)).fetchone()
        return self.get_asset(row["asset_id"]) if row else None

    def list_assets_full(self) -> list[dict]:
        ids = [r["asset_id"] for r in self.db.execute(
            "SELECT asset_id FROM assets ORDER BY asset_id").fetchall()]
        return [self.get_asset(asset_id) for asset_id in ids]

    def list_characters(self) -> list[dict]:
        rows = self.db.execute(
            "SELECT recipe_json FROM characters ORDER BY character_id").fetchall()
        return [json.loads(r["recipe_json"]) for r in rows]

    def get_character(self, character_id: str) -> dict | None:
        row = self.db.execute(
            "SELECT recipe_json FROM characters WHERE character_id=?",
            (character_id,)).fetchone()
        return json.loads(row["recipe_json"]) if row else None

    def set_asset_status(self, asset_id: str, status: str) -> None:
        self.db.execute("UPDATE assets SET status=? WHERE asset_id=?",
                        (status, asset_id))
        self.db.commit()

    def set_character_status(self, character_id: str, status: str) -> None:
        character = self.get_character(character_id)
        if character is None:
            raise KeyError(f"unknown character {character_id}")
        character["status"] = status
        self.db.execute(
            "UPDATE characters SET status=?, recipe_json=? WHERE character_id=?",
            (status, json.dumps(character), character_id))
        self.db.commit()

    def record_validation(self, asset_id: str | None, check_name: str,
                          passed: bool, detail: str) -> None:
        self.db.execute(
            "INSERT INTO validation_runs(asset_id, check_name, passed, detail) "
            "VALUES(?,?,?,?)",
            (asset_id, check_name, 1 if passed else 0, detail))
        self.db.commit()
