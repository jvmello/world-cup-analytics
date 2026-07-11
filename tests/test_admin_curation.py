from __future__ import annotations

import json
from pathlib import Path

import unittest

from fastapi.testclient import TestClient

from webapp.curation_repository import CurationRepository
from webapp.main import create_app
from webapp.player_positions import apply_player_override, assign_benchmark_cohorts

# ADMIN DISABLED FOR NOW (2026-07-09): the /api/admin/* routes and the /admin panel
# are commented out in webapp/main.py so they don't ship to production. Tests that
# exercise those routes stay skipped until re-enabling; pure curation tests still run.
# (unittest.skip instead of pytest.mark.skip: the `app` container runs the suite via
# unittest and has no pytest installed.)
ADMIN_DISABLED = unittest.skip(
    "Admin desativado por ora — rotas comentadas em webapp/main.py"
)


def _write_json(root: Path, relative: str, payload: object) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _admin_data_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    base = "bronze/thestatsapi/world_cup/2026"
    _write_json(
        root,
        f"{base}/fixtures/page=1/response.json",
        {
            "data": [{
                "id": "match-1", "utc_date": "2026-06-11T19:00:00Z",
                "group_label": "A", "status": "finished",
                "home_team": {"id": "team-1", "name": "Norway"},
                "away_team": {"id": "team-2", "name": "Brazil"},
                "score": {"home": 1, "away": 0},
            }]
        },
    )
    match = f"{base}/matches/match_id=match-1"
    _write_json(
        root,
        f"{match}/lineups/response.json",
        {
            "data": {
                "home": {
                    "id": "team-1", "name": "Norway", "formation": "4-3-3",
                    "starting_xi": [{"id": "player-1", "name": "Erling", "position": "F", "jersey_number": 9}],
                    "substitutes": [],
                },
                "away": {"id": "team-2", "name": "Brazil", "formation": "4-3-3", "starting_xi": [], "substitutes": []},
            }
        },
    )
    _write_json(
        root,
        f"{match}/player_stats/response.json",
        {
            "data": [{
                "player_id": "player-1", "player_name": "Erling", "team_id": "team-1",
                "position": "F", "started": True, "played": True, "minutes_played": 90,
                "rating": 8.1,
                "shooting": {"goals": 1, "total_shots": 4, "expected_goals": .8, "expected_assists": .05},
                "passing": {"assists": 0, "key_passes": 1, "total_crosses": 0, "total_passes": 20, "accurate_passes": 16},
                "general": {"touches": 35},
            }]
        },
    )
    _write_json(root, f"{match}/events/response.json", {"data": {"events": []}})
    _write_json(root, f"{match}/shotmap/response.json", {"data": []})
    _write_json(root, f"{match}/match_stats/response.json", {"data": {}})
    return root


def _player_override() -> dict[str, object]:
    return {
        "team_id": "team-1",
        "display_name_override": "Erling Haaland",
        "manual_position_group": "Atacante",
        "manual_position_role": "Centroavante",
        "manual_secondary_roles": ["Segundo atacante"],
        "manual_side": "Centro",
        "secondary_side": "Centro",
        "dominant_foot": "Esquerdo",
        "photo_url": "https://images.example.test/haaland.jpg",
        "photo_asset_path": None,
        "photo_credit": "Fotógrafo",
        "photo_source_url": "https://images.example.test/source",
        "photo_alt_text": "Erling Haaland em campo",
        "review_status": "reviewed",
        "review_notes": "Função confirmada pela curadoria.",
    }


def test_curation_repository_persists_json_fields_and_audit(tmp_path: Path) -> None:
    database = tmp_path / "curation.db"
    repository = CurationRepository(database)

    repository.upsert_player_override("player-1", _player_override(), updated_by="tester")
    reloaded = CurationRepository(database).get_player_override("player-1")

    assert reloaded is not None
    assert reloaded["manual_secondary_roles"] == ["Segundo atacante"]
    assert reloaded["manual_position_role"] == "Centroavante"
    assert reloaded["updated_by"] == "tester"
    assert repository.audit_log("player", "player-1")[0]["action"] == "upsert"

    repository.delete_player_override("player-1", updated_by="tester")
    assert repository.get_player_override("player-1") is None
    assert repository.audit_log("player", "player-1")[0]["action"] == "delete"


def test_manual_position_precedes_inference_and_changes_benchmark_cohort() -> None:
    players = []
    for index in range(5):
        player = {
            "player_id": f"player-{index}", "position": "F", "minutes_played": 90,
            "api_position_group": "Atacante", "primary_inferred_role": "Ponta",
            "resolved_position": "Ponta", "role_confidence": "medium",
        }
        override = {"manual_position_role": "Centroavante", "manual_side": "Centro"}
        players.append(apply_player_override(player, override))

    assigned = assign_benchmark_cohorts(players, minimum_sample=5)

    assert {player["resolved_position"] for player in assigned} == {"Centroavante"}
    assert {player["benchmark_position"] for player in assigned} == {"Centroavante"}
    assert {player["benchmark_label"] for player in assigned} == {"Média dos centroavantes"}
    assert all(player["primary_inferred_role"] == "Ponta" for player in assigned)


@ADMIN_DISABLED
def test_admin_feature_flag_key_crud_and_public_resolution(tmp_path: Path) -> None:
    data_root = _admin_data_root(tmp_path)
    database = tmp_path / "admin.db"
    disabled = TestClient(create_app(data_root=data_root, static_dir=None, admin_enabled=False, admin_db_path=database))
    assert disabled.get("/api/admin/config").status_code == 404

    client = TestClient(
        create_app(
            data_root=data_root,
            static_dir=None,
            admin_enabled=True,
            admin_api_key="secret",
            admin_db_path=database,
        )
    )
    assert client.get("/api/admin/config").json()["requires_key"] is True
    assert client.get("/api/admin/teams").status_code == 401
    headers = {"X-Admin-Key": "secret", "X-Admin-Actor": "tester"}

    teams = client.get("/api/admin/teams", headers=headers).json()
    assert teams["items"][0]["team_id"] == "team-1"
    roster = client.get("/api/admin/teams/team-1", headers=headers).json()
    assert roster["players"][0]["player_id"] == "player-1"
    player = client.get("/api/admin/players/player-1", headers=headers).json()
    assert player["api_position_group"] == "Atacante"
    assert player["inferred_position_role"] == "Centroavante"

    saved = client.put(
        "/api/admin/players/player-1/overrides",
        headers=headers,
        json={**_player_override(), "manual_position_role": "Ponta direita", "manual_side": "Direita"},
    )
    assert saved.status_code == 200
    assert saved.json()["manual_position_role"] == "Ponta direita"
    public = client.get("/api/editions/2026/players/player-1").json()
    assert public["player"]["resolved_position"] == "Ponta direita"
    assert public["player"]["player_name"] == "Erling Haaland"
    assert public["benchmarks"]["label"] in {"Média das pontas direitas", "Média dos atacantes"}

    invalid = client.put(
        "/api/admin/players/player-1/overrides",
        headers=headers,
        json={**_player_override(), "manual_position_role": "Camisa 10 inventado"},
    )
    assert invalid.status_code == 422

    removed = client.delete("/api/admin/players/player-1/overrides", headers=headers)
    assert removed.status_code == 204
    reverted = client.get("/api/editions/2026/players/player-1").json()
    assert reverted["player"]["resolved_position"] == "Centroavante"


@ADMIN_DISABLED
def test_admin_spa_is_separate_from_public_navigation(tmp_path: Path) -> None:
    static = Path(__file__).parents[1] / "webapp/static"
    disabled = TestClient(create_app(data_root=_admin_data_root(tmp_path), static_dir=static, admin_enabled=False, admin_db_path=tmp_path / "off.db"))
    enabled = TestClient(create_app(data_root=_admin_data_root(tmp_path), static_dir=static, admin_enabled=True, admin_db_path=tmp_path / "on.db"))

    assert disabled.get("/admin/teams").status_code == 404
    page = enabled.get("/admin/teams")
    assert page.status_code == 200
    assert "World Cup Analytics · Curadoria" in page.text
    public_index = (static / "index.html").read_text(encoding="utf-8")
    assert 'href="/admin' not in public_index

    admin_js = (static / "admin.js").read_text(encoding="utf-8")
    admin_css = (static / "admin.css").read_text(encoding="utf-8")
    public_js = (static / "app.js").read_text(encoding="utf-8")
    for contract in ("renderTeams", "renderTeam", "renderPlayers", "renderPlayer", "photoPreview", "manual_position_role"):
        assert contract in admin_js
    assert "playerPhotoNode" in public_js
    assert "@media (max-width: 600px)" in admin_css


def test_admin_surface_is_fully_disabled_for_now(tmp_path: Path) -> None:
    """Lock for the temporary shutdown: even with admin_enabled=True and a configured
    key, no admin route or panel asset may respond."""
    static = Path(__file__).parents[1] / "webapp/static"
    client = TestClient(
        create_app(
            data_root=_admin_data_root(tmp_path),
            static_dir=static,
            admin_enabled=True,
            admin_api_key="uma-chave-qualquer",
            admin_db_path=tmp_path / "on.db",
        )
    )
    assert client.get("/api/admin/config").status_code == 404
    assert client.get("/api/admin/players").status_code == 404
    assert client.get("/api/admin/teams").status_code == 404
    assert client.put("/api/admin/players/pl_1/overrides", json={}).status_code in (404, 405)
    assert client.get("/admin").status_code == 404
    assert client.get("/admin/teams").status_code == 404
    assert client.get("/static/admin.html").status_code == 404
    assert client.get("/static/admin.js").status_code == 404
    assert client.get("/static/admin.css").status_code == 404
    # the public surface stays intact
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/api/health").status_code == 200
