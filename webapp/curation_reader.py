from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CurationSnapshotReader:
    """Read-only counterpart to CurationRepository: same player_overrides_map()/
    team_overrides_map() shape, but backed by the JSON snapshots CurationRepository
    exports on every write (see _export_snapshot()) instead of opening the SQLite
    file directly. No sqlite3 import, no WAL, no locking — safe for a process that
    must never be able to write curation data (the future api-public instance)."""

    def __init__(self, database_path: Path | str) -> None:
        database_path = Path(database_path)
        self.players_snapshot_path = database_path.parent / "overrides_players.json"
        self.teams_snapshot_path = database_path.parent / "overrides_teams.json"

    @staticmethod
    def _load(path: Path) -> dict[str, dict[str, Any]]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def player_overrides_map(self) -> dict[str, dict[str, Any]]:
        return self._load(self.players_snapshot_path)

    def team_overrides_map(self) -> dict[str, dict[str, Any]]:
        return self._load(self.teams_snapshot_path)
