from __future__ import annotations

from pathlib import Path

from webapp.curation_reader import CurationSnapshotReader
from webapp.curation_repository import CurationRepository


def test_snapshot_reader_sees_writes_made_through_curation_repository(tmp_path: Path) -> None:
    """CurationRepository (SQLite, full read/write — the future api-admin's only writer)
    exports a JSON snapshot on every save; CurationSnapshotReader (no sqlite3 import at
    all, the future api-public's reader) must see the same data through that snapshot,
    with no direct dependency on the SQLite file itself."""
    db_path = tmp_path / "world_cup_admin.db"
    repo = CurationRepository(db_path)
    reader = CurationSnapshotReader(db_path)

    assert reader.player_overrides_map() == {}
    assert reader.team_overrides_map() == {}

    # AdminService always fills review_status before calling the repository
    # (defaults to "pending" — see admin_service.py); mirror that here since we're
    # calling CurationRepository directly, bypassing that validation layer.
    repo.upsert_player_override(
        "pl_1",
        {"display_name_override": "Test Player", "review_status": "pending"},
        updated_by="tester",
    )
    repo.upsert_team_override(
        "tm_1",
        {"display_name_override": "Test Team", "review_status": "pending"},
        updated_by="tester",
    )

    players = reader.player_overrides_map()
    teams = reader.team_overrides_map()
    assert players["pl_1"]["display_name_override"] == "Test Player"
    assert teams["tm_1"]["display_name_override"] == "Test Team"

    repo.delete_player_override("pl_1", updated_by="tester")
    assert "pl_1" not in reader.player_overrides_map()


def test_snapshot_reader_tolerates_missing_or_corrupt_files(tmp_path: Path) -> None:
    db_path = tmp_path / "world_cup_admin.db"
    reader = CurationSnapshotReader(db_path)
    assert reader.player_overrides_map() == {}  # snapshot files don't exist yet

    db_path.parent.mkdir(parents=True, exist_ok=True)
    (db_path.parent / "overrides_players.json").write_text("not json", encoding="utf-8")
    assert reader.player_overrides_map() == {}
