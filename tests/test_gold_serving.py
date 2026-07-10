from __future__ import annotations

import json
from pathlib import Path

from thestatsapi.serving import (
    GOLD_TABLES,
    GoldServingBuild,
    build_gold_substrate,
    gold_schema_sql,
)
from webapp.data_service import DataService
from webapp.thestatsapi_service import TheStatsApiBronzeService


def _write_json(root: Path, relative: str, payload: dict | list) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _sample_bronze(root: Path) -> Path:
    data_root = root / "data"
    base = data_root / "bronze/thestatsapi/world_cup/2026"
    _write_json(
        data_root,
        "bronze/thestatsapi/world_cup/2026/fixtures/page=1/response.json",
        {
            "data": [
                {
                    "id": "mt_1",
                    "utc_date": "2026-06-11T19:00:00Z",
                    "group_label": "A",
                    "stage_name": "Group Stage",
                    "status": "finished",
                    "matchday": 1,
                    "venue": {"name": "Estadio Azteca", "city": "Mexico City"},
                    "home_team": {"id": "tm_mex", "name": "Mexico"},
                    "away_team": {"id": "tm_rsa", "name": "South Africa"},
                    "score": {"home": 2, "away": 0},
                }
            ]
        },
    )
    _write_json(
        data_root,
        "bronze/thestatsapi/world_cup/2026/standings/response.json",
        {
            "data": [
                {
                    "group_label": "A",
                    "team": {"id": "tm_mex", "name": "Mexico"},
                    "matches_played": 1,
                    "wins": 1,
                    "draws": 0,
                    "losses": 0,
                    "goals_for": 2,
                    "goals_against": 0,
                    "goal_difference": 2,
                    "points": 3,
                    "position": 1,
                },
                {
                    "group_label": "A",
                    "team": {"id": "tm_rsa", "name": "South Africa"},
                    "matches_played": 1,
                    "wins": 0,
                    "draws": 0,
                    "losses": 1,
                    "goals_for": 0,
                    "goals_against": 2,
                    "goal_difference": -2,
                    "points": 0,
                    "position": 2,
                },
            ]
        },
    )
    match_base = base / "matches/match_id=mt_1"
    _write_json(
        data_root,
        "bronze/thestatsapi/world_cup/2026/matches/match_id=mt_1/lineups/response.json",
        {
            "data": {
                "home": {
                    "id": "tm_mex",
                    "name": "Mexico",
                    "formation": "4-3-3",
                    "starting_xi": [{"player_id": "p_1", "player_name": "Raul"}],
                    "substitutes": [],
                },
                "away": {
                    "id": "tm_rsa",
                    "name": "South Africa",
                    "formation": "4-2-3-1",
                    "starting_xi": [{"player_id": "p_2", "player_name": "Mokoena"}],
                    "substitutes": [],
                },
            }
        },
    )
    _write_json(
        data_root,
        "bronze/thestatsapi/world_cup/2026/matches/match_id=mt_1/match_stats/response.json",
        {
            "data": {
                "overview": {
                    "expected_goals": {"all": {"home": 1.7, "away": 0.4}},
                    "total_shots": {"all": {"home": 12, "away": 5}},
                    "shots_on_target": {"all": {"home": 5, "away": 1}},
                },
                "passes": {
                    "accurate_passes": {"all": {"home": 410, "away": 250}},
                    "total_passes": {"all": {"home": 480, "away": 320}},
                },
                "defending": {
                    "ball_recoveries": {"all": {"home": 38, "away": 31}},
                    "tackles": {"all": {"home": 12, "away": 17}},
                },
            }
        },
    )
    _write_json(
        data_root,
        "bronze/thestatsapi/world_cup/2026/matches/match_id=mt_1/player_stats/response.json",
        {
            "data": [
                {
                    "player_id": "p_1",
                    "player_name": "Raul",
                    "team_id": "tm_mex",
                    "position": "F",
                    "started": True,
                    "played": True,
                    "minutes_played": 90,
                    "rating": 8.1,
                    "shooting": {
                        "goals": 1,
                        "total_shots": 4,
                        "shots_on_target": 2,
                        "expected_goals": 0.9,
                        "expected_assists": 0.1,
                    },
                    "passing": {
                        "assists": 0,
                        "key_passes": 2,
                        "total_passes": 21,
                        "accurate_passes": 18,
                    },
                    "defending": {"tackles": 1, "interceptions": 0, "clearances": 0},
                    "duels": {"duel_won": 4, "aerial_won": 1},
                    "general": {"touches": 40},
                },
                {
                    "player_id": "p_2",
                    "player_name": "Mokoena",
                    "team_id": "tm_rsa",
                    "position": "M",
                    "started": True,
                    "played": True,
                    "minutes_played": 90,
                    "rating": 6.5,
                    "shooting": {
                        "goals": 0,
                        "total_shots": 1,
                        "shots_on_target": 0,
                        "expected_goals": 0.1,
                    },
                    "passing": {
                        "assists": 0,
                        "key_passes": 1,
                        "total_passes": 35,
                        "accurate_passes": 28,
                    },
                    "defending": {"tackles": 3, "interceptions": 2, "clearances": 1},
                    "duels": {"duel_won": 5, "aerial_won": 0},
                    "general": {"touches": 52},
                },
            ]
        },
    )
    _write_json(
        data_root,
        "bronze/thestatsapi/world_cup/2026/matches/match_id=mt_1/events/response.json",
        {"data": {"events": [{"sequence": 1, "minute": 15, "type": "goal", "team": {"name": "Mexico"}, "player": {"name": "Raul"}}]}},
    )
    _write_json(
        data_root,
        "bronze/thestatsapi/world_cup/2026/matches/match_id=mt_1/shotmap/response.json",
        {
            "data": [
                {
                    "id": "shot_1",
                    "team_id": "tm_mex",
                    "team_name": "Mexico",
                    "player_id": "p_1",
                    "player_name": "Raul",
                    "minute": 15,
                    "x": 88,
                    "y": 50,
                    "expected_goals": 0.4,
                    "result": "Goal",
                    "body_part": "Right Foot",
                    "situation": "Open Play",
                    "is_goal": True,
                    "is_on_target": True,
                    "is_penalty": False,
                },
            ]
        },
    )
    _write_json(
        data_root,
        "bronze/thestatsapi/world_cup/2026/matches/match_id=mt_1/match_detail/response.json",
        {"data": {"venue": {"name": "Estadio Azteca", "city": "Mexico City"}}},
    )
    _write_json(
        data_root,
        "bronze/thestatsapi/world_cup/2026/matches/match_id=mt_1/match_referee/response.json",
        {"data": {"referee": {"name": "Test Referee"}}},
    )
    assert match_base.exists()
    return data_root


def test_build_gold_substrate_collects_phase_one_tables(tmp_path: Path) -> None:
    data_root = _sample_bronze(tmp_path)

    build = build_gold_substrate(2026, data_root=data_root)

    assert isinstance(build, GoldServingBuild)
    assert build.counts == {
        "matches": 1,
        "match_players": 2,
        "match_shots": 1,
        "players_agg": 4,
        "teams_agg": 2,
        "standings": 2,
        "edition_summary": 1,
        "api_payloads": 19,
    }
    assert build.matches[0]["match_id"] == "mt_1"
    assert build.matches[0]["venue_name"] == "Estadio Azteca"
    assert build.matches[0]["detail"]["stats_comparison"]
    assert build.match_players[0]["scope"] == "match"
    assert build.match_players[0]["stats"]["player_name"]
    assert build.match_shots[0]["shot_id"] == "shot_1"
    assert {row["scope"] for row in build.players_agg} == {"all", "group_stage"}
    assert build.teams_agg[0]["stats"]["team_name"]
    assert build.edition_summary[0]["summary"]["matches"] == 1
    service = TheStatsApiBronzeService(data_root)
    payloads = {
        (row["endpoint"], row["entity_id"], row["scope"]): row["payload"]
        for row in build.api_payloads
    }
    assert payloads[("overview", "", "")] == service.overview(2026)
    assert payloads[("match_detail", "mt_1", "")] == service.match_detail(2026, "mt_1")
    assert payloads[("team_detail", "tm_mex", "")] == service.team_detail(2026, "tm_mex")
    assert payloads[("player_detail", "p_1", "all")] == service.player_detail(2026, "p_1")
    assert payloads[("player_detail", "p_1", "match:mt_1")] == service.player_detail(
        2026,
        "p_1",
        scope="match",
        match_id="mt_1",
    )


def test_gold_schema_covers_phase_one_tables() -> None:
    sql = gold_schema_sql()

    for table in GOLD_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS gold.{table}" in sql
    assert "CREATE TABLE IF NOT EXISTS gold.api_payloads" in sql
    assert "PRIMARY KEY (edition_year, endpoint, entity_id, scope)" in sql


class FakeGoldPayloads:
    def __init__(self, payloads: dict[tuple[int, str, str, str], dict]) -> None:
        self.payloads = payloads
        self.calls: list[tuple[int, str, str, str]] = []

    def get_payload(
        self,
        year: int,
        endpoint: str,
        *,
        entity_id: str | None = None,
        scope: str | None = None,
    ) -> dict | None:
        key = (year, endpoint, entity_id or "", scope or "")
        self.calls.append(key)
        return self.payloads.get(key)


def test_data_service_serves_gold_payload_when_materialized(tmp_path: Path) -> None:
    data_root = _sample_bronze(tmp_path)
    expected = {"year": 2026, "available": True, "source": "gold-test"}
    repo = FakeGoldPayloads({(2026, "overview", "", ""): expected})
    service = DataService(
        data_root,
        admin_db_path=tmp_path / "admin.db",
        gold_payload_repository=repo,
    )

    assert service.overview(2026) == expected
    assert repo.calls == [(2026, "overview", "", "")]


def test_data_service_cutover_does_not_fall_back_to_bronze_when_gold_payload_is_missing(
    tmp_path: Path,
) -> None:
    data_root = _sample_bronze(tmp_path)
    repo = FakeGoldPayloads({})
    service = DataService(
        data_root,
        admin_db_path=tmp_path / "admin.db",
        gold_payload_repository=repo,
    )

    payload = service.match_detail(2026, "mt_1")

    assert payload["available"] is False
    assert payload["notice"] == "Partida não encontrada no recorte publicado."
    assert repo.calls == [(2026, "match_detail", "mt_1", "")]


def test_data_service_keeps_legacy_bronze_path_for_isolated_test_roots(
    tmp_path: Path,
) -> None:
    data_root = _sample_bronze(tmp_path)
    service = DataService(data_root, admin_db_path=tmp_path / "admin.db")

    assert service.match_detail(2026, "mt_1") == TheStatsApiBronzeService(
        data_root,
        curation_repository=service.curation,
    ).match_detail(2026, "mt_1")


def test_data_service_maps_match_scope_player_detail_to_gold_payload(
    tmp_path: Path,
) -> None:
    data_root = _sample_bronze(tmp_path)
    expected = {"year": 2026, "available": True, "player": {"player_id": "p_1"}}
    repo = FakeGoldPayloads({(2026, "player_detail", "p_1", "match:mt_1"): expected})
    service = DataService(
        data_root,
        admin_db_path=tmp_path / "admin.db",
        gold_payload_repository=repo,
    )

    assert service.player_detail(2026, "p_1", scope="match", match_id="mt_1") == expected
