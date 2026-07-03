from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


PLAYER_FIELDS = (
    "team_id",
    "display_name_override",
    "manual_position_group",
    "manual_position_role",
    "manual_secondary_roles",
    "manual_side",
    "secondary_side",
    "dominant_foot",
    "photo_url",
    "photo_asset_path",
    "photo_credit",
    "photo_source_url",
    "photo_alt_text",
    "review_status",
    "review_notes",
)

TEAM_FIELDS = (
    "display_name_override",
    "short_name_override",
    "flag_asset_path",
    "primary_color",
    "secondary_color",
    "status_notes",
    "review_status",
)

DDL = (
    """
    CREATE TABLE IF NOT EXISTS admin_player_overrides (
        player_id TEXT PRIMARY KEY,
        team_id TEXT,
        display_name_override TEXT,
        manual_position_group TEXT,
        manual_position_role TEXT,
        manual_secondary_roles TEXT NOT NULL DEFAULT '[]',
        manual_side TEXT,
        secondary_side TEXT,
        dominant_foot TEXT,
        photo_url TEXT,
        photo_asset_path TEXT,
        photo_credit TEXT,
        photo_source_url TEXT,
        photo_alt_text TEXT,
        review_status TEXT NOT NULL DEFAULT 'pending',
        review_notes TEXT,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_by TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS admin_team_overrides (
        team_id TEXT PRIMARY KEY,
        display_name_override TEXT,
        short_name_override TEXT,
        flag_asset_path TEXT,
        primary_color TEXT,
        secondary_color TEXT,
        status_notes TEXT,
        review_status TEXT NOT NULL DEFAULT 'pending',
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_by TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS admin_curation_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        action TEXT NOT NULL,
        before_json TEXT,
        after_json TEXT,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_by TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_admin_audit_entity ON admin_curation_audit_log(entity_type, entity_id, id DESC)",
)


class CurationRepository:
    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=15)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _ensure_schema(self) -> None:
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            for statement in DDL:
                connection.execute(statement)

    @staticmethod
    def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        data = dict(row)
        if "manual_secondary_roles" in data:
            try:
                data["manual_secondary_roles"] = json.loads(data["manual_secondary_roles"] or "[]")
            except (TypeError, json.JSONDecodeError):
                data["manual_secondary_roles"] = []
        for key in ("before_json", "after_json"):
            if key in data and data[key]:
                try:
                    data[key] = json.loads(data[key])
                except (TypeError, json.JSONDecodeError):
                    pass
        return data

    def get_player_override(self, player_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM admin_player_overrides WHERE player_id = ?",
                (player_id,),
            ).fetchone()
        return self._decode(row)

    def list_player_overrides(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM admin_player_overrides ORDER BY updated_at DESC, player_id"
            ).fetchall()
        return [decoded for row in rows if (decoded := self._decode(row))]

    def player_overrides_map(self) -> dict[str, dict[str, Any]]:
        return {str(row["player_id"]): row for row in self.list_player_overrides()}

    def upsert_player_override(
        self,
        player_id: str,
        values: dict[str, Any],
        *,
        updated_by: str | None = None,
    ) -> dict[str, Any]:
        before = self.get_player_override(player_id)
        payload = {field: values.get(field) for field in PLAYER_FIELDS}
        payload["manual_secondary_roles"] = json.dumps(
            payload.get("manual_secondary_roles") or [], ensure_ascii=False
        )
        columns = ", ".join(("player_id", *PLAYER_FIELDS, "updated_by"))
        placeholders = ", ".join("?" for _ in range(len(PLAYER_FIELDS) + 2))
        updates = ", ".join(
            f"{field} = excluded.{field}" for field in (*PLAYER_FIELDS, "updated_by")
        )
        with self.connect() as connection:
            connection.execute(
                f"""
                INSERT INTO admin_player_overrides ({columns}, updated_at)
                VALUES ({placeholders}, CURRENT_TIMESTAMP)
                ON CONFLICT(player_id) DO UPDATE SET
                    {updates}, updated_at = CURRENT_TIMESTAMP
                """,
                (player_id, *(payload[field] for field in PLAYER_FIELDS), updated_by),
            )
        after = self.get_player_override(player_id) or {}
        self._audit("player", player_id, "upsert", before, after, updated_by)
        return after

    def delete_player_override(
        self,
        player_id: str,
        *,
        updated_by: str | None = None,
    ) -> bool:
        before = self.get_player_override(player_id)
        if before is None:
            return False
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM admin_player_overrides WHERE player_id = ?",
                (player_id,),
            )
        self._audit("player", player_id, "delete", before, None, updated_by)
        return True

    def get_team_override(self, team_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM admin_team_overrides WHERE team_id = ?",
                (team_id,),
            ).fetchone()
        return self._decode(row)

    def list_team_overrides(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM admin_team_overrides ORDER BY updated_at DESC, team_id"
            ).fetchall()
        return [decoded for row in rows if (decoded := self._decode(row))]

    def team_overrides_map(self) -> dict[str, dict[str, Any]]:
        return {str(row["team_id"]): row for row in self.list_team_overrides()}

    def upsert_team_override(
        self,
        team_id: str,
        values: dict[str, Any],
        *,
        updated_by: str | None = None,
    ) -> dict[str, Any]:
        before = self.get_team_override(team_id)
        payload = {field: values.get(field) for field in TEAM_FIELDS}
        columns = ", ".join(("team_id", *TEAM_FIELDS, "updated_by"))
        placeholders = ", ".join("?" for _ in range(len(TEAM_FIELDS) + 2))
        updates = ", ".join(
            f"{field} = excluded.{field}" for field in (*TEAM_FIELDS, "updated_by")
        )
        with self.connect() as connection:
            connection.execute(
                f"""
                INSERT INTO admin_team_overrides ({columns}, updated_at)
                VALUES ({placeholders}, CURRENT_TIMESTAMP)
                ON CONFLICT(team_id) DO UPDATE SET
                    {updates}, updated_at = CURRENT_TIMESTAMP
                """,
                (team_id, *(payload[field] for field in TEAM_FIELDS), updated_by),
            )
        after = self.get_team_override(team_id) or {}
        self._audit("team", team_id, "upsert", before, after, updated_by)
        return after

    def delete_team_override(
        self,
        team_id: str,
        *,
        updated_by: str | None = None,
    ) -> bool:
        before = self.get_team_override(team_id)
        if before is None:
            return False
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM admin_team_overrides WHERE team_id = ?",
                (team_id,),
            )
        self._audit("team", team_id, "delete", before, None, updated_by)
        return True

    def _audit(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
        updated_by: str | None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO admin_curation_audit_log (
                    entity_type, entity_id, action, before_json, after_json, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entity_type,
                    entity_id,
                    action,
                    json.dumps(before, ensure_ascii=False) if before is not None else None,
                    json.dumps(after, ensure_ascii=False) if after is not None else None,
                    updated_by,
                ),
            )

    def audit_log(self, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM admin_curation_audit_log
                WHERE entity_type = ? AND entity_id = ?
                ORDER BY id DESC
                """,
                (entity_type, entity_id),
            ).fetchall()
        return [decoded for row in rows if (decoded := self._decode(row))]
