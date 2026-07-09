from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import re

import pandas as pd
from fastapi.testclient import TestClient

from webapp.catalog import DEFAULT_EDITION
from webapp.main import create_app
from webapp.thestatsapi_service import TheStatsApiBronzeService


def _write_parquet(root: Path, relative: str, rows: list[dict]) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def _write_csv(root: Path, relative: str, rows: list[dict]) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_json(root: Path, relative: str, payload: dict | list) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _data_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    matches = [
        {
            "match_id": 1,
            "edition_year": 1958,
            "match_date": "1958-06-29",
            "competition_stage": "Final",
            "home_team": "Brazil",
            "away_team": "Sweden",
            "home_score": 5,
            "away_score": 2,
            "stadium": "Rasunda",
        },
        {
            "match_id": 2,
            "edition_year": 2022,
            "match_date": "2022-12-18",
            "competition_stage": "Final",
            "home_team": "Argentina",
            "away_team": "France",
            "home_score": 3,
            "away_score": 3,
            "stadium": None,
        },
    ]
    _write_parquet(
        root,
        "gold/world_cup/gold_match_summary/gold_match_summary.parquet",
        matches,
    )
    _write_parquet(
        root,
        "silver/world_cup/metadata/world_cup_data_availability.parquet",
        [
            {
                "edition_year": 1958,
                "matches": 1,
                "has_match_data": True,
                "has_event_data": True,
                "has_shots": True,
                "has_xg": True,
                "has_shot_location": True,
            },
            {
                "edition_year": 2022,
                "matches": 64,
                "has_match_data": True,
                "has_event_data": True,
                "has_shots": True,
                "has_xg": True,
                "has_shot_location": True,
            },
        ],
    )
    _write_parquet(
        root,
        "gold/world_cup/gold_team_shot_summary/gold_team_shot_summary.parquet",
        [
            {
                "edition_year": 2022,
                "team_name": "Argentina",
                "shots": 15,
                "goals": 3,
                "shots_on_target": 8,
                "xg": 2.5,
                "shot_accuracy": 8 / 15,
            }
        ],
    )
    _write_parquet(
        root,
        "gold/world_cup/gold_player_offensive_summary/"
        "gold_player_offensive_summary.parquet",
        [
            {
                "edition_year": 2022,
                "team_name": "Argentina",
                "player_name": "Lionel Messi",
                "shots": 7,
                "goals": 2,
                "shots_on_target": 4,
                "xg": 1.8,
            }
        ],
    )
    _write_parquet(
        root,
        "gold/world_cup/gold_tournament_groups/gold_tournament_groups.parquet",
        [
            {
                "edition_year": 2026,
                "group_name": "C",
                "position": 1,
                "team_name": "Brazil",
                "data_status": "scheduled",
            },
            {
                "edition_year": 2026,
                "group_name": "C",
                "position": 2,
                "team_name": "Morocco",
                "data_status": "scheduled",
            },
        ],
    )
    _write_parquet(
        root,
        "gold/world_cup/gold_tournament_fixtures/"
        "gold_tournament_fixtures.parquet",
        [
            {
                "edition_year": 2026,
                "stage": "Group Stage",
                "group_name": "C",
                "match_number": 7,
                "home_team": "Brazil",
                "away_team": "Morocco",
                "home_score": None,
                "away_score": None,
                "match_date": None,
                "status": "scheduled",
            }
        ],
    )
    _write_csv(
        root,
        "silver/fifa_pdf/world_cup/2026/match_summary.csv",
        [
            {
                "edition": 2026,
                "match_id": "2026-match-7",
                "match_date": "2026-06-13",
                "group_name": "C",
                "home_team": "Brazil",
                "away_team": "Morocco",
                "home_score": 1,
                "away_score": 1,
                "stadium": "New York",
            }
        ],
    )
    _write_csv(
        root,
        "silver/fifa_pdf/world_cup/2026/team_key_statistics.csv",
        [
            {
                "match_id": "2026-match-7",
                "team_name": "Brazil",
                "metric_name": "attempts_at_goal",
                "value": 12,
                "unit": "count",
            }
        ],
    )
    _write_csv(
        root,
        "silver/fifa_pdf/world_cup/2026/phases_of_play.csv",
        [
            {
                "match_id": "2026-match-7",
                "team_name": "Brazil",
                "possession_state": "in_possession",
                "phase_name": "build_up",
                "percentage": 42,
            }
        ],
    )
    _write_csv(
        root,
        "silver/fifa_pdf/world_cup/2026/player_metrics.csv",
        [
            {
                "match_id": "2026-match-7",
                "team_name": "Brazil",
                "player_name": "ALISSON",
                "metric_group": "physical",
                "metric_name": "distance",
                "value": 5.2,
                "unit": "km",
            }
        ],
    )
    return root


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(data_root=_data_root(tmp_path), static_dir=None))


def test_catalog_is_descending_and_2026_is_default(tmp_path: Path) -> None:
    payload = _client(tmp_path).get("/api/editions").json()

    assert payload["default_year"] == DEFAULT_EDITION == 2026
    assert [item["year"] for item in payload["editions"]] == [2026, 2022, 1958]

    fifa = payload["editions"][0]
    statsbomb = payload["editions"][1]
    assert fifa["source"] == "FIFA PDF"
    assert fifa["capabilities"]["official_metrics"] is True
    assert fifa["capabilities"]["xg"] is False
    assert "official_metrics" in [menu["id"] for menu in fifa["menus"]]
    assert statsbomb["source"] == "StatsBomb"
    assert statsbomb["capabilities"]["xg"] is True


def test_public_navigation_separates_home_from_competition() -> None:
    app_js = (
        Path(__file__).parents[1] / "webapp/static/app.js"
    ).read_text(encoding="utf-8")

    assert 'const DEFAULT_PAGE = "overview";' in app_js
    assert '{ id: "overview", label: "Início" }' in app_js
    assert 'overview: "Início"' in app_js
    assert 'if (page === "overview") return `/${year || DEFAULT_YEAR}`;' in app_js


def test_health_and_edition_overviews(tmp_path: Path) -> None:
    client = _client(tmp_path)

    assert client.get("/api/health").json() == {
        "status": "ok",
        "default_year": 2026,
    }

    overview_2022 = client.get("/api/editions/2022/overview")
    assert overview_2022.status_code == 200
    assert overview_2022.json()["summary"]["matches"] == 1
    assert overview_2022.json()["summary"]["champion"] == "Argentina"

    overview_2026 = client.get("/api/editions/2026/overview")
    assert overview_2026.status_code == 200
    assert overview_2026.json()["summary"]["matches"] == 1
    assert overview_2026.json()["coverage"]["partial"] is True


def test_competition_teams_players_and_matches(tmp_path: Path) -> None:
    client = _client(tmp_path)

    competition = client.get("/api/editions/2026/competition").json()
    assert competition["groups"][0]["name"] == "C"
    assert competition["groups"][0]["teams"][0]["team_name"] == "Brazil"
    assert competition["fixtures"][0]["match_date"] is None

    teams = client.get("/api/editions/2022/teams").json()
    assert teams["items"][0]["team_name"] == "Argentina"

    players = client.get("/api/editions/2022/players").json()
    assert players["items"][0]["player_name"] == "Lionel Messi"

    matches = client.get("/api/editions/2026/matches").json()
    assert matches["items"][0]["match_id"] == "2026-match-7"


def test_official_metrics_are_available_only_when_materialized(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    response = client.get("/api/editions/2026/official-metrics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["team_metrics"][0]["metric_name"] == "attempts_at_goal"
    assert payload["phases_of_play"][0]["percentage"] == 42
    assert payload["player_metrics"][0]["value"] == 5.2

    response = client.get("/api/editions/2022/official-metrics")
    assert response.status_code == 200
    assert response.json()["available"] is False
    assert response.json()["team_metrics"] == []


def test_statsbomb_shots_endpoint_uses_granular_gold(tmp_path: Path) -> None:
    root = _data_root(tmp_path)
    _write_parquet(
        root,
        "gold/world_cup/gold_player_shots/gold_player_shots.parquet",
        [
            {
                "edition_year": 2022,
                "shot_id": "shot-1",
                "player_name": "Lionel Messi",
                "team_name": "Argentina",
                "statsbomb_xg": 0.42,
                "is_goal": True,
                "x": 108.0,
                "y": 40.0,
                "minute": 12,
            }
        ],
    )
    client = TestClient(create_app(data_root=root, static_dir=None))

    response = client.get("/api/editions/2022/shots")

    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["summary"]["shots"] == 1
    assert payload["summary"]["goals"] == 1
    assert payload["summary"]["xg"] == 0.42
    assert payload["items"][0]["player_name"] == "Lionel Messi"
    assert payload["shot_map"][0]["x"] == 108.0
    assert payload["player_leaders"][0]["player_name"] == "Lionel Messi"
    assert payload["xg_flow"][0]["cumulative_xg"] == 0.42
    assert payload["team_summary"][0]["team_name"] == "Argentina"


def test_analytical_contracts_feed_dashboard_visualizations(tmp_path: Path) -> None:
    client = _client(tmp_path)

    overview = client.get("/api/editions/2022/overview").json()
    assert overview["highlights"]["top_team"]["team_name"] == "Argentina"
    assert overview["highlights"]["top_player"]["player_name"] == "Lionel Messi"

    teams = client.get("/api/editions/2022/teams").json()
    assert teams["summary"]["teams"] == 1
    assert teams["rankings"]["xg"][0]["team_name"] == "Argentina"

    players = client.get("/api/editions/2022/players").json()
    assert players["summary"]["players"] == 1
    assert players["leaders"]["goals"][0]["player_name"] == "Lionel Messi"
    assert players["scatter"][0]["xg"] == 1.8

    matches = client.get("/api/editions/2022/matches").json()
    assert matches["summary"]["matches"] == 1
    assert matches["stage_distribution"][0]["stage"] == "Final"


def test_fifa_metrics_are_pivoted_for_comparison_charts(tmp_path: Path) -> None:
    root = _data_root(tmp_path)
    _write_csv(
        root,
        "silver/fifa_pdf/world_cup/2026/team_key_statistics.csv",
        [
            {
                "match_id": "2026-match-7",
                "team_name": "Brazil",
                "metric_name": "attempts_at_goal",
                "value": 12,
                "unit": "count",
            },
            {
                "match_id": "2026-match-7",
                "team_name": "Morocco",
                "metric_name": "attempts_at_goal",
                "value": 8,
                "unit": "count",
            },
        ],
    )
    client = TestClient(create_app(data_root=root, static_dir=None))

    payload = client.get("/api/editions/2026/official-metrics").json()

    assert payload["scoreboard"]["home_team"] == "Brazil"
    comparison = payload["team_comparison"][0]
    assert comparison["metric"] == "attempts_at_goal"
    assert comparison["Brazil"] == 12
    assert comparison["Morocco"] == 8


def test_availability_is_separate_from_analytical_views(tmp_path: Path) -> None:
    payload = _client(tmp_path).get("/api/editions/2022/availability").json()

    assert payload["year"] == 2022
    assert payload["source"] == "StatsBomb"
    assert any(item["id"] == "shots" for item in payload["capabilities"])
    assert all("file" not in item for item in payload["capabilities"])


def test_history_marks_incomplete_historical_samples(tmp_path: Path) -> None:
    payload = _client(tmp_path).get("/api/history").json()

    assert payload["default_year"] == 2026
    assert payload["partial_advanced_coverage"] is True
    by_year = {item["year"]: item for item in payload["editions"]}
    assert by_year[1958]["coverage"]["partial"] is True
    assert by_year[1958]["champion"] == "Brazil"
    assert by_year[2022]["coverage"]["partial"] is False


def test_invalid_edition_returns_404_without_fallback(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/editions/2014/overview")

    assert response.status_code == 404
    assert response.json()["detail"]["year"] == 2014
    assert response.json()["detail"]["default_year"] == 2026


def test_missing_files_return_explicit_empty_state(tmp_path: Path) -> None:
    root = _data_root(tmp_path)
    (
        root
        / "gold/world_cup/gold_player_offensive_summary/"
        "gold_player_offensive_summary.parquet"
    ).unlink()
    client = TestClient(create_app(data_root=root, static_dir=None))

    payload = client.get("/api/editions/2022/players").json()
    assert payload["available"] is False
    assert payload["items"] == []
    assert payload["notice"]


def test_json_serialization_converts_nan_and_nat_to_null(tmp_path: Path) -> None:
    client = _client(tmp_path)

    match = client.get("/api/editions/2022/matches").json()["items"][0]
    assert match["stadium"] is None


def test_static_directory_is_served_when_present(tmp_path: Path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<h1>World Cup</h1>", encoding="utf-8")

    client = TestClient(
        create_app(data_root=_data_root(tmp_path), static_dir=static_dir)
    )

    response = client.get("/")
    assert response.status_code == 200
    assert "World Cup" in response.text
    assert response.headers["cache-control"] == "no-store"

    clean_route = client.get("/2026/competition")
    assert clean_route.status_code == 200
    assert "World Cup" in clean_route.text
    assert clean_route.headers["cache-control"] == "no-store"

    missing_route = client.get("/dev/data-status")
    assert missing_route.status_code == 404


def test_match_center_frontend_keeps_events_product_focused() -> None:
    app_js = (
        Path(__file__).parents[1] / "webapp/static/app.js"
    ).read_text(encoding="utf-8")

    assert 'section("Momentos do jogo"' in app_js
    assert app_js.count('section("Visão geral da partida"') == 1
    assert 'text: "Ver timeline completa"' in app_js
    assert 'goal: "Gol"' in app_js
    assert 'yellow_card: "Cartão amarelo"' in app_js
    assert 'substitution: "Substituição"' in app_js
    assert 'section("Tipos de evento"' not in app_js
    assert 'section("Comparação completa"' not in app_js
    assert 'teamLabel(goal.team_name, "team-label goal-team")' not in app_js


def test_match_context_only_renders_available_referee() -> None:
    app_js = (
        Path(__file__).parents[1] / "webapp/static/app.js"
    ).read_text(encoding="utf-8")
    score_card = app_js[
        app_js.index("function scoreCard"):
        app_js.index("function routeTo")
    ]

    assert 'const referee = first(match, ["referee", "main_referee"], null);' in score_card
    assert 'const venueCity = first(match, ["venue_city"], null);' in score_card
    assert 'const stadiumLabel = stadium && venueCity ? `${stadium} · ${venueCity}` : stadium;' in score_card
    assert 'referee ? ["Árbitro", referee] : null' in score_card
    assert "Árbitro não informado" not in score_card


def test_match_center_frontend_uses_editorial_hierarchy() -> None:
    app_js = (
        Path(__file__).parents[1] / "webapp/static/app.js"
    ).read_text(encoding="utf-8")
    render = app_js[
        app_js.index("function renderTheStatsApiMatch"):
        app_js.index("function renderAvailability")
    ]

    expected_order = [
        'matchCenterHero(match)',
        'section("História do jogo"',
        'section("Top impactos da partida"',
        'section("Visão geral da partida"',
        'section("Finalizações & xG"',
        'section("Jogadores da partida"',
        'section("Momentos do jogo"',
        'section("Escalações"',
    ]
    positions = [render.index(marker) for marker in expected_order]

    assert positions == sorted(positions)
    assert 'section("Mapa de chutes"' not in render
    assert 'section("Fluxo de xG"' not in render
    assert 'section("Métricas da partida"' not in render
    assert 'matchMoments(data.events || [], match)' in render
    assert "impact_summary" not in render[:render.index("els.view.replaceChildren")]


def test_match_center_frontend_exposes_product_context_and_compact_analysis() -> None:
    root = Path(__file__).parents[1] / "webapp/static"
    app_js = (root / "app.js").read_text(encoding="utf-8")
    styles = (root / "styles.css").read_text(encoding="utf-8")
    surface = app_js[
        app_js.index("function scoreCard"):
        app_js.index("function renderAvailability")
    ]

    for marker in (
        "match-status",
        "match-subnav-link",
        "IntersectionObserver",
        "comparison-team-legend",
        "Menor é melhor",
        "overview-complete-table",
        "xg-goal-label",
        "Ver perfil completo",
        "lineup-unit",
    ):
        assert marker in surface or marker in styles
    assert 'starPoints(cx, cy, 6, 0.22)' in surface
    assert 'comparisonBars(rows, "comparison-stack-secondary")' not in surface
    assert 'text: "Gols não informados"' not in surface
    assert 'body.is-match-center[data-skin="2026"] .pitch-wrap' in styles
    assert 'body.is-match-center[data-skin="2026"] .player-table-wrap' in styles


def test_match_center_frontend_fixes_substitution_position_date_and_scroll() -> None:
    root = Path(__file__).parents[1] / "webapp/static"
    app_js = (root / "app.js").read_text(encoding="utf-8")
    styles = (root / "styles.css").read_text(encoding="utf-8")

    assert "entrou no lugar de" in app_js
    assert 'text: "Entra:' not in app_js, "the old 'Entra: X · Sai: Y' wording should be gone"

    lineup_unit_body = app_js[app_js.index("function lineupUnit"):app_js.index("function lineupUnit") + 400]
    assert "lineupPositionCode" in lineup_unit_body, "tactical grouping and the position badge must share the same resolved source"
    lineup_row_body = app_js[app_js.index("function lineupPlayerRow"):app_js.index("function lineupPlayerRow") + 600]
    assert "lineupPositionCode" in lineup_row_body
    assert "positionLabel(player.position)" not in lineup_row_body, "the badge must not fall back to the raw api position independently of the tactical grouping"

    assert "withHorizontalScrollFade(table" in app_js
    assert "scroll-fade-edge" in styles

    format_match_date_body = app_js[app_js.index("function formatMatchDate"):app_js.index("function formatMatchDate") + 600]
    assert 'month: "2-digit"' not in format_match_date_body, "match header date must use a friendly month, not raw numeric DD/MM/YYYY"
    assert 'month: "short"' in format_match_date_body

    for metric in ("big_chances_missed", "offsides", "dispossessed", "fouls", "yellow_cards", "red_cards"):
        assert f'"{metric}"' in app_js[app_js.index("LOWER_IS_BETTER_METRICS"):app_js.index("LOWER_IS_BETTER_METRICS") + 200]


def test_score_pill_is_restricted_to_match_detail_hero() -> None:
    """The score-pill (green pill, black bold digits) is a strong visual statement reserved for
    the Match Detail hero header. Every other surface (Partidas calendar row, Home "Quem
    avançou"/"Próximos encaixes", Competição bracket cards, the archive match-card list) must use
    the simplified colored-text score (scoreText) instead, so the pill never appears more than once
    per screen and never collides with a kickoff time on scoreless cards."""
    root = Path(__file__).parents[1] / "webapp/static"
    app_js = (root / "app.js").read_text(encoding="utf-8")
    styles = (root / "styles.css").read_text(encoding="utf-8")

    assert "function scorePill(" in app_js
    assert "function scoreText(" in app_js

    # scorePill must only be called from the hero branch of scoreCard (Match Detail header)
    pill_calls = re.findall(r"(?<!function )scorePill\(([^)]*)\)", app_js)
    assert len(pill_calls) == 1, f"scorePill must be called exactly once, found {len(pill_calls)}"
    assert '"lg"' in pill_calls[0]  # only the hero (large) call site remains

    # every other former pill call site must now use the plain-text score
    assert "scoreText(match?.home_score, match?.away_score" in app_js  # scoreCard non-hero
    assert "scoreText(item.match.home_score, item.match.away_score" in app_js  # Quem avançou
    assert 'scoreText(match?.home_score, match?.away_score, { homeName: match?.home_team' in app_js  # matchCalendarRow
    assert "scoreText(match.home_score, match.away_score" in app_js  # knockoutMatchCard
    assert "scorePill(match.home_score, match.away_score" not in app_js  # homeBracketMatch, knockoutMatchCard no longer use the pill
    assert "scorePill(item.match.home_score" not in app_js  # Quem avançou no longer uses the pill

    assert 'class: "score"' not in app_js, "the old plain-text score span must be gone, replaced by the shared score components"
    assert "class: `score-pill" in app_js

    assert "--score-pill-bg: #5dcaa5" in styles
    assert "--score-pill-fg: #0a0a0a" in styles
    assert ".score-pill {" in styles
    assert "background: var(--score-pill-bg)" in styles
    assert "color: var(--score-pill-fg)" in styles
    assert ".score-text {" in styles
    assert "color: var(--score-pill-bg)" in styles

    # the teal must stay scoped to the score pill, not leak into a general-purpose accent
    assert "--accent: var(--score-pill-bg)" not in styles
    assert "--wc26-teal: var(--score-pill-bg)" not in styles

    # keep the ":" separator between the two numbers, and a flat teal fill (no gradient)
    scorepill_fn = app_js[app_js.index("function scorePill("):app_js.index("function scorePill(") + 500]
    assert 'text: ":"' in scorepill_fn
    assert 'background: var(--wc26-teal)' in styles
    assert 'background: var(--wc26-gradient-score)' not in styles

    # goal minute badges reuse the same teal token, not the green accent
    assert 'background: var(--wc26-teal);\n  color: var(--wc26-bg);\n  box-shadow: 0 0 10px rgba(79, 191, 166' in styles

    # the score-text component reuses the same teal token under the 2026 skin
    assert 'body[data-skin="2026"] .score-text' in styles


def test_player_stats_panel_shows_opponent_unifies_timeline_and_labels_rating() -> None:
    root = Path(__file__).parents[1] / "webapp/static"
    app_js = (root / "app.js").read_text(encoding="utf-8")
    styles = (root / "styles.css").read_text(encoding="utf-8")

    # 1. opponent shown in the sticky modal header (visible across every internal section)
    header_body = app_js[app_js.index("function openPlayerModal"):app_js.index("function playerExplorer(")]
    assert "player.opponent_name" in header_body
    assert "vs" in header_body

    # 2. individual shot map: rotated/cropped view, no team-color legend, orientation confirmed
    #    empirically against goal_mouth_coordinates.x == 0 (see playerShotMap / SHOT_RESULT_TO_EVENT_TYPE)
    assert "function playerShotMap(" in app_js
    shotmap_body = app_js[app_js.index("function playerShotMap("):app_js.index("function playerShotMap(") + 1800]
    assert 'viewBox: `0 0 ${width} ${height}`' in shotmap_body
    assert "home" not in shotmap_body.split("aria-label")[0]  # no per-team legend wiring
    assert "Cor = seleção" not in shotmap_body

    # 3. shots + events unified into one unduplicated timeline
    assert "function playerTimelineEntries(" in app_js
    assert "function playerActionsPanel(" in app_js
    assert "function playerShotsPanel(" not in app_js, "the old split shots panel must be gone"
    assert "function playerEventsPanel(" not in app_js, "the old split events panel must be gone"
    assert "SHOT_RESULT_TO_EVENT_TYPE" in app_js
    # shotmap.result values actually observed in the bronze data — every one must be mapped
    for result_value in ("save", "block", "miss", "post"):
        assert f'{result_value}:' in app_js[app_js.index("SHOT_RESULT_TO_EVENT_TYPE"):app_js.index("SHOT_RESULT_TO_EVENT_TYPE") + 200]

    # backend: shot-covered event types excluded from a player's events, substitution matches
    # both the incoming AND outgoing player
    service_src = (Path(__file__).parents[1] / "webapp/thestatsapi_service.py").read_text(encoding="utf-8")
    assert "SHOT_COVERED_EVENT_TYPES" in service_src
    for shot_type in ("goal", "shot_on_target", "shot_off_target", "shot_blocked", "penalty_scored", "penalty_missed", "penalty_saved"):
        assert f'"{shot_type}"' in service_src[service_src.index("SHOT_COVERED_EVENT_TYPES"):service_src.index("SHOT_COVERED_EVENT_TYPES") + 400]
    assert 'event.get("player_out_name") == api_player_name' in service_src
    assert '"opponent_name": opponent_name' in service_src

    # 4. Rating (source field) vs Perfil contextual (derived score) have distinguishing tooltips
    quick_metrics_body = app_js[app_js.index("function playerQuickMetrics("):app_js.index("function playerQuickMetrics(") + 500]
    assert "Perfil contextual" in quick_metrics_body and "calculado pelo produto" in quick_metrics_body
    assert '"Rating", player.rating,' in quick_metrics_body and "fonte de dados" in quick_metrics_body
    assert "metric.title" in app_js


def test_player_modal_uses_tabs_instead_of_one_long_scroll() -> None:
    """Regression: "Ver estatísticas completas" was one continuous long scroll. Converted to real
    click-to-switch tabs (same role="tab"/aria-selected/is-active convention already used by
    profilePlayerTabs on the Profile screen), grouped as Resumo / Ataque & Criação / Passe, Duelos
    & Disciplina / Finalizações. The header stays outside the tab content so it's always visible."""
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")
    styles = (Path(__file__).parents[1] / "webapp/static/styles.css").read_text(encoding="utf-8")

    assert "function playerModalTabDefinitions(" in app_js
    tab_defs = app_js[app_js.index("function playerModalTabDefinitions("):app_js.index("function openPlayerModal(")]
    for label in ("Resumo", "Ataque & Criação", "Passe, Duelos & Disciplina", "Finalizações"):
        assert f'"{label}"' in tab_defs

    modal_body = app_js[app_js.index("function openPlayerModal("):app_js.index("function playerExplorer(")]
    assert 'role: "tab"' in modal_body
    assert '"aria-selected": String(key === activeTab)' in modal_body
    assert 'class: key === activeTab ? "is-active" : ""' in modal_body
    # header (identity, opponent, story) sits outside the tab-swapped content, in render order
    content_array = modal_body[modal_body.index("const content = ["):]
    assert content_array.index('class: "player-modal-header"') < content_array.index("tabsNav,")
    assert content_array.index("tabsNav,") < content_array.index("tabContent,")

    # sections are grouped, not a single flat list — attack/creation split from pass/duels/discipline
    detailed_sections_body = app_js[app_js.index("function playerDetailedSections("):app_js.index("function playerQuickMetrics(")]
    assert "attackCreation" in detailed_sections_body
    assert "passDuelsDiscipline" in detailed_sections_body

    assert ".player-modal-tabs {" in styles
    assert ".player-modal-tabs button.is-active {" in styles


def test_player_modal_shot_map_is_compact_with_a_numeric_summary() -> None:
    """Regression: the individual shot map (100x50 viewBox, offensive-half crop) had a lot of dead
    space below the box since real shot x-coordinates cluster under ~33 (p99 measured against
    real bronze shotmap data) while the crop extended to 50. Tightened to a 100x38 viewBox and
    added a Finalizações/Gols/xG numeric summary below the map, reusing fields already computed
    elsewhere in the panel. Also confirm marker size is a real function of xG (not just visually
    similar) and that no glow/neon effect was introduced."""
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")
    styles = (Path(__file__).parents[1] / "webapp/static/styles.css").read_text(encoding="utf-8")

    shot_map_body = app_js[app_js.index("function playerShotMap("):app_js.index("function playerShotMap(") + 2200]
    assert "const width = 100, height = 38;" in shot_map_body
    assert "const size = Math.max(1, Math.min(3.2, 1 + xg * 4));" in shot_map_body

    # size is a genuine function of xg: low/high xG values must map to visibly different sizes
    def marker_size(xg):
        return max(1, min(3.2, 1 + xg * 4))
    assert marker_size(0.03) < marker_size(0.46) < marker_size(0.82)
    assert round(marker_size(0.03), 2) == 1.12
    assert round(marker_size(0.82), 2) == 3.2  # clamped ceiling

    assert "function shotSummary(" in app_js
    summary_body = app_js[app_js.index("function shotSummary("):app_js.index("function shotSummary(") + 600]
    assert '"Finalizações", shots.length' in summary_body
    assert '"Gols", goals' in summary_body
    assert '"xG", xg' in summary_body
    actions_panel_body = app_js[app_js.index("function playerActionsPanel("):app_js.index("function openPlayerModal(")]
    assert "shotSummary(player.player_shots || [])" in actions_panel_body

    # the profile screen's shot map panel is the same component (shared function, same crop, same
    # max-height CSS) — it now also renders the summary, computed from whatever shots are currently
    # filtered (not the player's raw season totals), so it stays correct under the mode/body/type
    # filters that only exist in the profile context
    shot_map_panel_body = app_js[app_js.index("function playerShotMapPanel("):app_js.index("function playerShotMinuteChart(")]
    assert "shotSummary(filtered)" in shot_map_panel_body
    assert ".player-actions-section .pitch-wrap svg { max-height:" not in styles
    assert ".player-pitch-wrap svg { max-height: 360px; }" in styles

    # no glow/neon on the shot map — flat solid colors only, matching the rest of the product
    assert ".player-shot-summary" in styles
    assert "glow" not in styles[styles.index(".player-shot-summary"):styles.index(".player-shot-summary") + 400]
    assert "neon" not in shot_map_body.lower()


def test_shot_breakdown_charts_are_pie_charts() -> None:
    """"Perfil das finalizações" (Jogadores) and "Perfil coletivo" (Seleções) showed body-part/
    shot-type breakdowns as numbered horizontal bar lists. Converted both to pie charts (the only
    two reachable places this composition-style breakdown is shown — the benchmark-compared
    distributionWithBenchmark() on the Profile screen is a different chart type, with a benchmark
    overlay a pie can't represent, so it was deliberately left as a bar)."""
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")
    styles = (Path(__file__).parents[1] / "webapp/static/styles.css").read_text(encoding="utf-8")

    assert "function pieChart(" in app_js
    pie_chart_body = app_js[app_js.index("function pieChart("):app_js.index("function horizontalBars(")]
    assert "Math.cos(angle)" in pie_chart_body and "Math.sin(angle)" in pie_chart_body
    assert "pie-legend" in pie_chart_body

    player_shot_breakdown_body = app_js[app_js.index("function playerShotBreakdown("):app_js.index("function playerCreationProfile(")]
    assert "pieChart(breakdowns[key], \"goals\"" in player_shot_breakdown_body
    assert "horizontalBars(" not in player_shot_breakdown_body

    team_collective_body = app_js[app_js.index("function teamCollectiveProfile("):app_js.index("function teamRankingExplorer(")]
    assert 'pieChart(rows, "amount"' in team_collective_body
    assert "team-collective-row" not in team_collective_body
    assert "team-collective-row" not in styles, "the now-unused bar-row CSS for team-collective must be removed, not left dead"

    # the benchmark-compared distribution chart (Profile screen) is untouched — different purpose
    assert "function distributionWithBenchmark(" in app_js
    benchmark_body = app_js[app_js.index("function distributionWithBenchmark("):app_js.index("function teamMatchProductionChart(")]
    assert "player-distribution-bars" in benchmark_body

    assert ".pie-chart-wrap" in styles
    assert ".pie-slice" in styles


def test_creation_profile_lists_sort_descending_by_metric() -> None:
    """Regression: playerCreationProfile()'s two Top-8 lists (key_passes, accurate_crosses)
    filtered eligible players but never sorted them before handing off to horizontalBars(), which
    does not sort internally (it trusts the caller) — so a player with fewer key_passes could
    appear above one with more (e.g. Haaland with 3 above Mbappé with 6)."""
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")
    body = app_js[app_js.index("function playerCreationProfile("):app_js.index("function playerCreationProfile(") + 700]
    assert ".sort((left, right) => number(right[metric]) - number(left[metric]))" in body
    # horizontalBars() itself doesn't sort — confirms callers must pre-sort, as playerCreationProfile now does
    horizontal_bars_body = app_js[app_js.index("function horizontalBars("):app_js.index("function horizontalBars(") + 600]
    assert "sort" not in horizontal_bars_body


def test_comparison_map_restores_per90_scatter_option() -> None:
    """Regression: the "Mapa de comparação" toggle had 5 modes but none normalized for minutes
    played — the first "Gols × xG" mode plots raw totals, not per-90, even though per-90 is an
    established product-wide convention specifically to avoid bias from playing time. Restored a
    6th "Gols por 90 × xG por 90" option using the existing generic scatter machinery."""
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")
    assert '"Gols por 90 × xG por 90"' in app_js
    per90_config = app_js[app_js.index("per90: {"):app_js.index("per90: {") + 400]
    assert "player.goals_per_90" in per90_config
    assert "player.xg_per_90" in per90_config
    comparison_map_body = app_js[app_js.index("function playerComparisonMap("):app_js.index("function playerOverviewExperience(")]
    assert 'playerSecondaryScatterPlot(rows, "per90", onSelect)' in comparison_map_body


def test_players_table_is_sortable_by_any_column() -> None:
    """Regression: "Lista de jogadores" was always sorted by minutes_played desc with plain-text
    headers. Rewritten to reuse the exact sortable-table pattern already correct in Match Detail's
    playerExplorer() — sort-button/sort-indicator, aria-sort, numeric columns default desc on
    first click, text columns (Jogador/Seleção/Pos.) default asc, single active sort column."""
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")
    body = app_js[app_js.index("function playerOverviewTable("):app_js.index("function profileStandingLabel(")]
    assert "sort-button" in body
    assert "sort-indicator" in body
    assert '"aria-sort"' in body
    for key in ("player_name", "team_name", "position", "minutes_played", "goals", "assists", "xg", "xa", "shots", "defensive_actions", "rating"):
        assert f'key: "{key}"' in body
    assert 'direction: rows.length && typeof column.value(rows[0]) === "number" ? "desc" : "asc"' in body


def test_players_page_adds_goalkeeper_tab_qualified_toggle_and_new_charts() -> None:
    root = Path(__file__).parents[1] / "webapp/static"
    app_js = (root / "app.js").read_text(encoding="utf-8")

    # 1 & 2: Goleiros never showed up in Rankings because the default "Qualificados" filter
    # required >=3 shots, which no goalkeeper ever registers — confirmed empirically (0/56
    # qualified keepers had shots >= 3). Goalkeepers must be exempt from the shots threshold.
    filtered_body = app_js[app_js.index("function filtered()"):app_js.index("function filtered()") + 900]
    assert "isGoalkeeper" in filtered_body
    assert 'positionLabel(player.position) === "GOL"' in filtered_body
    assert "filters.qualified" in filtered_body

    # explicit Qualificados/Todos toggle, defaulting to Qualificados
    overview_body = app_js[app_js.index("function playerOverviewExperience"):app_js.index("function playerOverviewExperience") + 2000]
    assert "qualified: true" in overview_body
    assert '"Qualificados"' in overview_body and '"Todos"' in overview_body
    assert "overview-qualified-toggle" in overview_body

    # 3 & 5: two new scatter options, sourced from real player_stats groups (duels, shooting)
    assert '"shot_efficiency"' in app_js
    assert '"duels"' in app_js
    scatter_configs = app_js[app_js.index("function playerDuelsDisputed"):app_js.index("function playerSecondaryScatterPlot(")]
    assert "player.shot_conversion" in scatter_configs
    assert "player.duels_won" in scatter_configs and "player.duels_lost" in scatter_configs
    comparison_map_body = app_js[app_js.index("function playerComparisonMap"):app_js.index("function playerOverviewExperience")]
    assert '"shot_efficiency"' in comparison_map_body
    assert '"duels"' in comparison_map_body

    # 4: position production unified selector now includes defending-group metrics
    position_body = app_js[app_js.index("function playerPositionDistribution"):app_js.index("function playerPositionDistribution") + 600]
    for metric in ("tackles", "interceptions", "clearances", "defensive_actions"):
        assert f'"{metric}"' in position_body

    # 6: new creation profile block mirroring the shot-breakdown two-column structure
    assert "function playerCreationProfile(" in app_js
    creation_body = app_js[app_js.index("function playerCreationProfile("):app_js.index("function playerCreationProfile(") + 700]
    assert "key_passes" in creation_body
    assert "accurate_crosses" in creation_body
    assert '"Perfil de criação"' in app_js


def test_ranking_labels_use_correct_singular_plural_agreement() -> None:
    """Regression: "Rankings de Seleções > Defesa" showed "1 gols" instead of "1 gol" — the shared
    analysisMetricValue() (used by both Rankings de jogadores and Rankings de seleções) appended a
    fixed plural unit string regardless of the value. Fixed via a centralized singularizeUnit()
    helper reused everywhere a definition-style unit gets composed with a count, including the
    Home "Líderes da Copa" panel (homeRankingValue) and the Curiosidades/discovery cards
    (discoveryValue) — not just the one place the bug was reported."""
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")

    assert "function singularizeUnit(" in app_js
    singular_body = app_js[app_js.index("const UNIT_SINGULAR_FORMS"):app_js.index("function singularizeUnit(") + 200]
    for plural, singular in [("gols", "gol"), ("chutes", "chute"), ("passes", "passe"), ("desarmes", "desarme"), ("cortes", "corte"), ("duelos", "duelo"), ("defesas", "defesa"), ("vermelhos", "vermelho"), ("eventos", "evento")]:
        assert f"{plural}: \"{singular}\"" in singular_body

    metric_value_body = app_js[app_js.index("function analysisMetricValue("):app_js.index("function analysisMetricValue(") + 400]
    assert "singularizeUnit(value, definition.unit)" in metric_value_body

    ranking_value_body = app_js[app_js.index("function homeRankingValue("):app_js.index("function homeRankingValueClass(")]
    assert "singularizeUnit(parsed," in ranking_value_body

    discovery_value_body = app_js[app_js.index("function discoveryValue("):app_js.index("function openDiscoveryQuickView(")]
    assert "singularizeUnit(value, metric.unit)" in discovery_value_body


def test_rankings_use_documented_alphabetical_tie_break() -> None:
    """Regression: two teams tied on a ranking's primary metric (e.g. Mexico and Spain both at 0
    goals conceded) had no defined tie-break, so their relative order depended on incidental array
    order from the API — it looked arbitrary. analysisMetricRows() (shared by Rankings de
    jogadores and Rankings de seleções) and teamProductionOverview() now both fall back to
    alphabetical (pt-BR) order by name whenever the primary metric ties, via one shared helper."""
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")

    assert "function rankingTieBreakName(" in app_js
    tie_break_body = app_js[app_js.index("function rankingTieBreakName("):app_js.index("function rankingTieBreakName(") + 200]
    assert "player_name" in tie_break_body and "team_name" in tie_break_body

    metric_rows_body = app_js[app_js.index("function analysisMetricRows("):app_js.index("function analysisMetricValue(")]
    assert "rankingTieBreakName(left).localeCompare(rankingTieBreakName(right)" in metric_rows_body

    production_overview_body = app_js[app_js.index("function teamProductionOverview("):app_js.index("function teamCollectiveProfile(")]
    assert "rankingTieBreakName(left.team).localeCompare(rankingTieBreakName(right.team)" in production_overview_body


def test_team_rows_aggregate_discipline_and_stage_membership() -> None:
    """Regression: the Seleções screen had no "Disciplina" ranking category and no way to filter
    by phase, even though match_stats.overview already carries fouls/yellow_cards/red_cards per
    team and fixtures already carry stage_name. Confirm team_rows() aggregates both."""
    service = TheStatsApiBronzeService()
    standings = {
        "A": [
            {"team_id": "bra", "team_name": "Brazil", "group_name": "A", "played": 2, "goals_for": 3, "goals_against": 1},
            {"team_id": "fra", "team_name": "France", "group_name": "A", "played": 2, "goals_for": 2, "goals_against": 2},
        ]
    }
    details = [
        {
            "match": {"home_team": "Brazil", "away_team": "France", "stage": "group_stage"},
            "players": [], "shot_map": [],
            "team_summary": [{"team_name": "Brazil", "shots": 8, "goals": 2}, {"team_name": "France", "shots": 4, "goals": 1}],
            "stats_comparison": [
                {"metric": "fouls", "section": "overview", "Brazil": 10, "France": 14},
                {"metric": "yellow_cards", "section": "overview", "Brazil": 1, "France": 3},
                {"metric": "red_cards", "section": "overview", "Brazil": 0, "France": 1},
            ],
        },
        {
            "match": {"home_team": "Brazil", "away_team": "France", "stage": "round_of_32"},
            "players": [], "shot_map": [],
            "team_summary": [{"team_name": "Brazil", "shots": 6, "goals": 1}, {"team_name": "France", "shots": 5, "goals": 1}],
            "stats_comparison": [
                {"metric": "fouls", "section": "overview", "Brazil": 6, "France": 8},
                {"metric": "yellow_cards", "section": "overview", "Brazil": 1, "France": 1},
                {"metric": "red_cards", "section": "overview", "Brazil": 0, "France": 0},
            ],
        },
    ]

    teams = service.team_rows(2026, standings, details)
    brazil = next(row for row in teams if row["team_name"] == "Brazil")
    france = next(row for row in teams if row["team_name"] == "France")

    assert brazil["fouls"] == 16 and brazil["fouls_per_game"] == 8.0
    assert brazil["yellow_cards"] == 2 and brazil["yellow_cards_per_game"] == 1.0
    assert brazil["red_cards"] == 0
    assert france["red_cards"] == 1
    # stage membership, ordered by tournament progression, using the same translation as the
    # rest of the product (matches/competition screens)
    assert brazil["stages"] == ["Fase de grupos", "Fase de 32"]
    assert france["stages"] == ["Fase de grupos", "Fase de 32"]

    # the ranking-rows helper must not exclude zero for ascending ("lower is better") metrics —
    # otherwise every team with 0 red cards (the common, best case) would vanish from the ranking
    root = Path(__file__).parents[1] / "webapp/static"
    app_js = (root / "app.js").read_text(encoding="utf-8")
    metric_rows_body = app_js[app_js.index("function analysisMetricRows("):app_js.index("function analysisMetricRows(") + 700]
    assert "definition.ascending || value !== 0" in metric_rows_body

    # frontend: Disciplina category + Fase filter wired in
    assert '{ category: "Disciplina"' in app_js
    assert '"fouls_per_game"' in app_js and '"yellow_cards_per_game"' in app_js
    team_experience_body = app_js[app_js.index("function teamAnalysisExperience"):app_js.index("function teamAnalysisExperience") + 2200]
    assert 'stage: "all"' in team_experience_body
    assert 'node("span", { text: "Fase" })' in team_experience_body
    ranking_explorer_body = app_js[app_js.index("function teamRankingExplorer"):app_js.index("function teamAnalysisExperience")]
    assert '"Disciplina"' in ranking_explorer_body


def test_radar_leader_and_nearest_by_radar_helpers() -> None:
    """Regression: radar leader reference line (adendo #5) and "Comparáveis" suggestion (adendo
    #6) are derived purely from the radar scores already computed for benchmarking peers — no
    new data. Confirm the max-per-axis and nearest-neighbour math directly."""
    peers = [
        {"player_id": "p1", "player_name": "Peer One", "team_name": "A", "radar": [{"axis": "Ataque", "value": 80}, {"axis": "Defesa", "value": 20}, {"axis": "Passe", "value": 50}]},
        {"player_id": "p2", "player_name": "Peer Two", "team_name": "B", "radar": [{"axis": "Ataque", "value": 60}, {"axis": "Defesa", "value": 90}, {"axis": "Passe", "value": 55}]},
    ]
    leader = TheStatsApiBronzeService._radar_leader(peers)
    assert {axis["axis"]: axis["value"] for axis in leader} == {"Ataque": 80, "Defesa": 90, "Passe": 55}

    summary = {"player_id": "self", "radar": [{"axis": "Ataque", "value": 62}, {"axis": "Defesa", "value": 88}, {"axis": "Passe", "value": 54}]}
    nearest = TheStatsApiBronzeService._nearest_by_radar(summary, peers, id_key="player_id", name_key="player_name")
    assert nearest[0]["name"] == "Peer Two"  # closer on Ataque/Defesa/Passe than Peer One
    assert nearest[0]["id"] == "p2"


def test_profile_screens_get_rotated_shot_map_full_radar_and_adendo_features() -> None:
    root = Path(__file__).parents[1] / "webapp/static"
    app_js = (root / "app.js").read_text(encoding="utf-8")
    styles = (root / "styles.css").read_text(encoding="utf-8")
    service_src = (Path(__file__).parents[1] / "webapp/thestatsapi_service.py").read_text(encoding="utf-8")

    # 1: both profiles reuse the same rotated/cropped playerShotMap (built for match-detail),
    # not the old horizontal shared shotMap() with its team-mirroring hack
    shot_panel_body = app_js[app_js.index("function playerShotMapPanel("):app_js.index("function playerShotMap(shots")]
    assert "playerShotMap(filtered" in shot_panel_body
    assert "120 - rawX" not in shot_panel_body and "120 - number(shot.x)" not in shot_panel_body
    assert "function playerShotMap(shots, { color = null } = {})" in app_js
    team_shot_body = app_js[app_js.index("function teamShotExperience("):app_js.index("function teamShotExperience(") + 500]
    assert "teamColor(" in team_shot_body, "team profile must keep a single team color on its shot map"

    # 2 & 3: no radar axis without a matching metric block — 6 outfield player blocks, 5 team blocks
    player_groups_body = app_js[app_js.index('node("div", { class: "profile-metric-groups" }, (isGoalkeeper'):app_js.index("profileComparablesBlock(data.comparable_players")]
    for title in ("Finalização", "Criação", "Participação", "Passe", "Defesa"):
        assert f'"{title}"' in player_groups_body
    assert "duelsGroup()" in player_groups_body
    duels_group_body = app_js[app_js.index("const duelsGroup ="):app_js.index("const duelsGroup =") + 700]
    assert '"Duelos"' in duels_group_body
    assert '"Passe": (("pass_accuracy"' not in service_src, "Passe axis must be folded into Controle, not left as a separate unlabeled axis"
    assert '"Controle": (("average_possession"' in service_src

    # 5: radar leader line wired into radarChart and both profile radar features
    radar_chart_signature = app_js[app_js.index("function radarChart("):app_js.index("function radarChart(") + 200]
    assert "leader" in radar_chart_signature
    assert "radar-leader-line" in app_js and "radar-leader-line" in styles
    assert "leaderRadar" in app_js
    assert "data.leader_radar" in app_js
    assert '"leader_radar": self._radar_leader(peers)' in service_src
    assert "all_team_radars" in service_src

    # 6: Comparáveis block wired for both entity types
    assert "function profileComparablesBlock(" in app_js
    assert 'profileComparablesBlock(data.comparable_players, "player")' in app_js
    assert 'profileComparablesBlock(data.comparable_teams, "team")' in app_js
    assert '"comparable_players": self._nearest_by_radar' in service_src
    assert '"comparable_teams": self._nearest_by_radar' in service_src

    # 7: shot-quality (xG per shot) histogram, distinct from and alongside the per-minute one
    assert "function playerShotQualityChart(" in app_js
    quality_body = app_js[app_js.index("function playerShotQualityChart("):app_js.index("function playerShotQualityChart(") + 900]
    assert "Baixo" in quality_body and "Médio" in quality_body and "Alto" in quality_body
    assert "playerShotMinuteChart(shots" in app_js and "playerShotQualityChart(shots)" in app_js

    # 8: small-sample badge on extreme percentile displays
    assert "function metricWithComparison(" in app_js
    metric_with_comparison_body = app_js[app_js.index("function metricWithComparison("):app_js.index("function metricWithComparison(") + 1400]
    assert "entityGames" in metric_with_comparison_body
    assert "profile-sample-badge" in metric_with_comparison_body
    assert 'standingText !== "Próximo da média"' in metric_with_comparison_body
    assert "entityGames: number(player.games)" in app_js
    assert "entityGames: number(team.played)" in app_js


def test_competition_frontend_has_group_and_knockout_product_views() -> None:
    root = Path(__file__).parents[1] / "webapp/static"
    app_js = (root / "app.js").read_text(encoding="utf-8")
    styles = (root / "styles.css").read_text(encoding="utf-8")
    render = app_js[
        app_js.index("const GROUP_STAT_DEFINITIONS"):
        app_js.index("function renderHistory")
    ]

    for label in (
        "Fase de grupos",
        "Mata-mata",
        "Melhores terceiros",
        "Competição",
        "Fase de 32",
        "Pos",
        "Seleção",
        "J",
        "V",
        "E",
        "D",
        "GP",
        "GC",
        "SG",
        "Pts",
        "Última vaga",
        "Classificado",
        "Classificado como melhor terceiro",
        "Eliminado",
        "Possível vaga",
        "Fora agora",
    ):
        assert f'"{label}"' in render
    assert 'goToProfile("team", teamId)' in render
    assert 'routeTo("matches", match.match_id)' in render
    assert 'aria-selected' in render
    assert 'text: "Melhores terceiros"' in render
    assert 'text: "Mata-mata"' in render
    assert 'text: "12 grupos · 24 vagas diretas · 8 melhores terceiros"' in render
    assert '"16 avos"' not in render
    assert '"Vencedor da partida' not in render
    assert "competition-group-table" in styles
    assert "best-thirds-table" in styles
    assert "knockout-board" in styles
    assert "competition-row-qualified" in styles
    assert "competition-row-third" in styles
    assert "competition-row-out" in styles


def test_competition_uses_full_width_group_games_tooltips_and_direct_navigation() -> None:
    app_js = (
        Path(__file__).parents[1] / "webapp/static/app.js"
    ).read_text(encoding="utf-8")
    competition = app_js[
        app_js.index("const GROUP_STAT_DEFINITIONS"):
        app_js.index("function renderPlayerDetail")
    ]

    assert 'node("details", { class: "competition-group-games" }' not in competition
    assert 'text: "Ver jogos do grupo"' in competition
    assert "function competitionGroupRow" in competition
    assert "function competitionGroupGamesPanel" in competition
    assert "competition-group-row" in competition
    assert "competition-group-games-panel" in competition
    assert "competition-group-toggle" in competition
    assert "function teamGroupStatBreakdown" in competition
    assert "function showStatPopover" in competition
    assert '"GP": "gols pró, total de gols marcados."' in competition
    assert '"GC": "gols contra, total de gols sofridos."' in competition
    assert '"SG": "saldo de gols, gols pró menos gols contra."' in competition
    assert '"Pts": "pontos conquistados."' in competition
    assert "function openTeamQuickView" in competition
    assert "function openMatchQuickView" in competition
    assert 'goToProfile("team", teamId)' in competition
    assert 'routeTo("matches", match.match_id)' in competition
    assert "function competitionKickoffLabel" in competition
    assert "homeMatchIsLive(match)" in competition
    assert 'return "Aguardando resultado"' in competition
    assert 'text: "As 8 melhores seleções em 3º lugar avançam para a Fase de 32."' in competition
    assert 'text: "Critério exibido: pontos, saldo de gols e gols pró."' in competition
    assert "knockout-result-note" in competition
    assert "Mata-mata em andamento" in competition
    render = competition[
        competition.index("function renderCompetition"):
    ]
    assert 'section("Estatísticas gerais"' not in render


def test_completed_group_stage_uses_final_public_classification_statuses() -> None:
    standings = {
        "A": [
            {"team_id": "a1", "position": 1, "classification_status": "Classificando"},
            {"team_id": "a2", "position": 2, "classification_status": "Classificando"},
            {"team_id": "a3", "position": 3, "classification_status": "Possível vaga"},
            {"team_id": "a4", "position": 4, "classification_status": "Fora agora"},
        ],
        "B": [
            {"team_id": "b1", "position": 1, "classification_status": "Classificando"},
            {"team_id": "b2", "position": 2, "classification_status": "Classificando"},
            {"team_id": "b3", "position": 3, "classification_status": "Possível vaga"},
            {"team_id": "b4", "position": 4, "classification_status": "Fora agora"},
        ],
    }
    thirds = [
        {"team_id": "a3", "rank": 8, "status": "Classificado"},
        {"team_id": "b3", "rank": 9, "status": "Eliminado"},
    ]

    TheStatsApiBronzeService._finalize_group_statuses(standings, thirds)

    assert [team["classification_status"] for team in standings["A"]] == [
        "Classificado", "Classificado", "Classificado como melhor terceiro", "Eliminado",
    ]
    assert standings["B"][2]["classification_status"] == "Eliminado"


def test_matches_frontend_is_a_compact_public_calendar() -> None:
    root = Path(__file__).parents[1] / "webapp/static"
    app_js = (root / "app.js").read_text(encoding="utf-8")
    styles = (root / "styles.css").read_text(encoding="utf-8")
    matches_surface = app_js[
        app_js.index("function matchStageLabel"):
        app_js.index("function renderShots")
    ]
    render = app_js[
        app_js.index("function renderMatches"):
        app_js.index("function renderShots")
    ]

    for function_name in (
        "matchStageLabel",
        "matchCalendarRow",
        "matchCalendarGroups",
        "matchPublicStatus",
        "matchFilterBar",
    ):
        assert f"function {function_name}" in app_js
    for label in (
        "Partidas", "Calendário", "Por data", "Por fase", "Limpar filtros",
        "Hoje", "Próximos jogos", "Encerrados", "Horários em Brasília",
        "Fase de grupos", "Fase de 32", "Oitavas", "Quartas", "Semifinais",
        "Disputa de 3º lugar", "Final", "A definir", "Aguardando resultado",
        "Mais filtros",
    ):
        assert f'"{label}"' in render or f'"{label}"' in app_js
    assert 'dashboardShell("Partidas"' in render
    assert "matches-summary-strip" in render
    assert "matches-calendar-list" in matches_surface
    assert "matches-filter-bar" in matches_surface
    assert "matches-filter-pills" in matches_surface
    assert "matches-grouping-control" in render
    assert "score-grid" not in render
    assert "matchCard(" not in render
    assert '"Partida por partida"' not in render
    assert '"Gols não informados"' not in render
    assert '"Abrir partida"' not in render
    assert '"Distribuição por fase"' not in render
    assert "function matchStageDistribution" not in app_js
    assert 'routeTo("matches", match.match_id)' in matches_surface
    assert "row.addEventListener(\"click\"" in matches_surface, "the entire calendar row must be clickable, not just the arrow icon"
    assert 'goToProfile("team", teamId)' in matches_surface
    assert 'body[data-page="matches"][data-skin="2026"] .matches-calendar-row' in styles
    assert 'body[data-page="matches"][data-skin="2026"] .matches-filter-bar' in styles
    assert 'body[data-page="matches"][data-skin="2026"] .matches-filter-pills button' in styles
    assert "word-break: normal" in styles


def test_matches_adapter_resolves_public_stages_and_future_sides() -> None:
    rows = [
        {
            "match_id": "r32",
            "match_date": "2026-06-28T19:00:00Z",
            "stage": "round_of_32",
            "home_team": "Brazil",
            "home_team_id": "bra",
            "away_team": "Japan",
            "away_team_id": "jpn",
            "home_score": 2,
            "away_score": 1,
            "status": "finished",
        },
        {
            "match_id": "r16",
            "match_date": "2026-07-04T19:00:00Z",
            "stage": "round_of_16",
            "home_team": "W73",
            "away_team": "W74",
            "home_score": None,
            "away_score": None,
            "status": "scheduled",
        },
    ]

    public = TheStatsApiBronzeService._public_match_items(rows)

    assert public[0]["stage_label"] == "Fase de 32"
    assert public[1]["stage_label"] == "Oitavas"
    assert public[1]["home_team"] == "Brazil"
    assert public[1]["home_defined"] is True
    assert public[1]["away_team"] == "A definir"
    assert public[1]["away_defined"] is False
    assert all(not str(item.get("home_team", "")).startswith("W") for item in public)


def test_match_center_frontend_has_internal_nav_and_clear_filters() -> None:
    app_js = (
        Path(__file__).parents[1] / "webapp/static/app.js"
    ).read_text(encoding="utf-8")

    assert 'aria-label": "Navegação da partida"' in app_js
    for anchor in (
        "#match-summary",
        "#match-finalizations",
        "#match-players",
        "#match-moments",
        "#match-lineups",
    ):
        assert anchor in app_js
    assert "Exibindo ${filtered.length} de ${rows.length} chutes" in app_js
    assert 'text: `Filtro ativo: ${activeFilters.join(" · ")}`' in app_js
    assert "axisLabel(point.axis)" in app_js
    assert 'point.axis.abbr || point.axis.axis' not in app_js
    assert "Math.max(0, number(item.cumulative_xg) || 0)" in app_js


def test_2026_theme_uses_black_editorial_world_cup_tokens() -> None:
    root = Path(__file__).parents[1] / "webapp/static"
    styles = (root / "styles.css").read_text(encoding="utf-8")
    index = (root / "index.html").read_text(encoding="utf-8")

    for token in (
        "--wc26-bg: #000000",
        "--wc26-bg-soft: #050505",
        "--wc26-surface: #0b0b0b",
        "--wc26-surface-alt: #121212",
        "--wc26-border: #2a2a2a",
        "--wc26-green: #8fbd46",
        "--wc26-teal: #4fbfa6",
        "--wc26-blue: #5578bd",
        '--wc26-display-font: "Nimbus Sans"',
        "--wc26-display-stroke: 0.5px",
        "--wc26-glow-cyan: none",
        "--wc26-glow-green: none",
    ):
        assert token in styles
    assert 'content="#000000"' in index
    assert '<strong>Analytics</strong>' in index
    assert '<small>World Cup 2026</small>' in index
    assert 'body[data-skin="2026"] .match-score-card' in styles
    assert 'body[data-skin="2026"] .impact-card' in styles
    assert 'body[data-skin="2026"] .player-metrics-table tbody tr.is-selected' in styles
    assert 'body[data-skin="2026"] .event-goal .event-icon' in styles
    assert "@media (prefers-reduced-motion: reduce)" in styles


def test_2026_skin_uses_color_as_a_controlled_editorial_accent() -> None:
    styles = (
        Path(__file__).parents[1] / "webapp/static/styles.css"
    ).read_text(encoding="utf-8")
    skin = styles[
        styles.index('body[data-skin="2026"] {'):
        styles.index("@media (max-width: 900px)")
    ]

    for token in (
        "--wc26-bg: #000000;",
        "--wc26-surface: #0b0b0b;",
        "--wc26-red: #c94f4a;",
        "--wc26-yellow: #d4b84c;",
        "--wc26-green: #8fbd46;",
        "--wc26-teal: #4fbfa6;",
        "--wc26-glow-cyan: none;",
        "--wc26-gradient-score:",
    ):
        assert token in skin

    assert 'body[data-skin="2026"] .nav-link[aria-current="page"]' in skin
    assert 'body[data-skin="2026"] .score' in skin
    assert 'body[data-skin="2026"] .impact-inline-score' in skin
    assert 'body[data-skin="2026"] .xg-point.is-goal' in skin
    assert 'body[data-skin="2026"] .event-var .event-icon' in skin
    assert "font-family: var(--wc26-display-font);" in skin
    assert "font-stretch: normal;" in skin
    assert "-webkit-text-stroke: var(--wc26-display-stroke) currentColor;" in skin
    assert "Impact," not in skin
    assert "border: 4px solid var(--cup-blue);" not in skin


def test_match_center_radar_uses_readable_portuguese_labels() -> None:
    app_js = (
        Path(__file__).parents[1] / "webapp/static/app.js"
    ).read_text(encoding="utf-8")

    for label in ("Ataque", "Criação", "Passe", "Defesa", "Participação"):
        assert f'"{label}"' in app_js


def test_match_center_has_full_width_score_and_pointed_chart_goals() -> None:
    root = Path(__file__).parents[1] / "webapp/static"
    app_js = (root / "app.js").read_text(encoding="utf-8")
    styles = (root / "styles.css").read_text(encoding="utf-8")
    hero = app_js[
        app_js.index("function matchCenterHero"):
        app_js.index("function matchSubnav")
    ]

    assert 'node("h1"' not in hero
    assert "starPoints(" in app_js
    assert 'class: `xg-point team-${teamIndex % 2} is-goal`' in app_js
    assert "xG final" in app_js
    assert ".match-center-hero { display: grid; width: 100%;" in styles
    assert ".comparison-row:hover" in styles
    assert ".bar-row:hover" in styles


def test_match_subnav_uses_internal_hashes_without_legacy_routing() -> None:
    root = Path(__file__).parents[1] / "webapp/static"
    app_js = (root / "app.js").read_text(encoding="utf-8")
    styles = (root / "styles.css").read_text(encoding="utf-8")

    assert 'location.hash.startsWith("#/")' in app_js
    assert "scrollToInternalAnchor" in app_js
    assert "state.pathname === location.pathname" in app_js
    assert ".match-subnav { position: sticky; z-index: 8; top: 0; display: flex; width: 100%;" in styles
    assert ".xg-point { fill: var(--team-color, var(--accent)); stroke: #fff;" in styles
    assert 'body[data-skin="2026"] .xg-point.is-goal' in styles


def test_lineup_omits_missing_jersey_number_instead_of_a_placeholder_dash() -> None:
    """Regression: some real lineup entries genuinely have no jersey_number in the source data
    (confirmed in bronze lineups responses, e.g. a null jersey_number) — the UI showed a visible
    "–" for these instead of following the project's "nullable fields omitted" convention. The
    lineup row is a fixed 3-column grid (32px/1fr/34px), so the shirt-number element must stay in
    the DOM to keep the name/position columns aligned, but must render nothing visible when the
    number is unavailable."""
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")
    styles = (Path(__file__).parents[1] / "webapp/static/styles.css").read_text(encoding="utf-8")

    lineup_row = app_js[app_js.index("function lineupPlayerRow("):app_js.index("function lineupPlayerRow(") + 700]
    assert "hasJerseyNumber" in lineup_row
    assert 'metricAvailable(player.jersey_number)' in lineup_row
    assert '"–"' not in lineup_row and "'–'" not in lineup_row
    assert ".shirt-number.is-unavailable { visibility: hidden; }" in styles


def test_match_players_and_shots_are_fully_interactive() -> None:
    root = Path(__file__).parents[1] / "webapp/static"
    app_js = (root / "app.js").read_text(encoding="utf-8")
    styles = (root / "styles.css").read_text(encoding="utf-8")

    for abbreviation in ("GOL", "DEF", "MEI", "ATA"):
        assert f'"{abbreviation}"' in app_js
    assert "function positionLabel" in app_js
    assert "sort-button" in app_js
    assert 'aria-sort' in app_js
    assert "function shotDetail" in app_js
    assert "shot-detail" in styles
    assert "player.player_id && number(player.minutes_played) > 0" in app_js
    assert "function substitutionEntryMinutes" in app_js
    assert "function substitutionPairs" not in app_js
    assert "lineup-player-substitution" not in styles
    assert "function openPlayerModal" in app_js
    assert "function makePlayerSurfaceInteractive" in app_js
    assert "impactPanel(data.player_impacts, data.players || [])" in app_js
    assert "lineupPanel(data.lineups?.home, data.players || [], data.events || [])" in app_js
    assert "is-player-interactive" in styles
    assert "showModal" in app_js
    assert "player-modal" in styles
    assert "por 100" not in app_js.lower()

    modal = app_js[
        app_js.index("function playerPerformanceStory"):
        app_js.index("function playerExplorer")
    ]
    assert "function playerContextComparisons" in modal
    assert 'text: "Destaques da atuação"' in modal
    assert '"Drible e condução"' not in modal
    assert "Cobertura" not in modal
    assert "Confiança" not in modal


def test_analytical_pages_separate_overviews_from_individual_profiles() -> None:
    root = Path(__file__).parents[1] / "webapp/static"
    app_js = (root / "app.js").read_text(encoding="utf-8")
    styles = (root / "styles.css").read_text(encoding="utf-8")
    players_render = app_js[
        app_js.index("function renderPlayers"):
        app_js.index("function compactAnalysisSummary")
    ]
    teams_render = app_js[
        app_js.index("function renderTeams"):
        app_js.index("function renderPlayers")
    ]
    teams_experience = app_js[
        app_js.index("function teamAnalysisExperience"):
        app_js.index("function teamComparisonScatter")
    ]

    assert '{ id: "teams", label: "Seleções" }' in app_js
    assert '{ id: "profile", label: "Perfil" }' in app_js
    assert 'profile: "Perfil"' in app_js
    assert "playerOverviewExperience" in players_render
    assert 'dashboardShell("Jogadores",' in players_render
    assert "playerProfileView" not in players_render
    assert "entityCard" not in players_render
    assert "teamAnalysisExperience" in teams_render
    assert 'dashboardShell("Seleções",' in teams_render
    assert "entityCard" not in teams_render
    for function_name in (
        "playerOverviewExperience",
        "playerScatterPlot",
        "analysisScatterPlot",
        "playerSecondaryScatterPlot",
        "playerPositionDistribution",
        "playerShotBreakdown",
        "playerEditionHighlights",
        "playerComparisonMap",
        "playerRankingExplorer",
        "playerOverviewTable",
        "playerRankingPanels",
        "teamAnalysisExperience",
        "teamComparisonScatter",
        "teamSecondaryScatterPlot",
        "teamEditionHighlights",
        "teamComparisonMap",
        "teamComparisonInsights",
        "teamProductionOverview",
        "teamCollectiveProfile",
        "teamRankingExplorer",
        "renderProfile",
        "profilePlayerSelector",
        "profileTeamSelector",
        "playerProfileView",
        "teamProfileView",
        "metricWithComparison",
        "profileStandingLabel",
        "profileQuickRead",
        "playerRadarFeature",
        "playerShotExperience",
        "playerMatchLogCards",
        "teamProfileTabs",
        "teamProfileQuickRead",
        "teamRadarFeature",
        "teamShotExperience",
        "teamMatchLogTable",
        "distributionWithBenchmark",
        "teamMatchProductionChart",
        "playerShotMapPanel",
        "playerShotMinuteChart",
        "playerShotDistributions",
    ):
        assert f"function {function_name}" in app_js
    for label_text in (
        "Buscar jogador", "Posição", "Seleção", "Minutos mínimos",
        "Finalizações mínimas", "Edição inteira", "Fase de grupos",
        "Mata-mata", "Geral", "Finalizações", "Distribuição",
    ):
        assert f'"{label_text}"' in app_js
    assert "scatter-reference-line" in app_js
    assert "function scatterEntityMarker" in app_js
    assert 'kind: "player"' in app_js
    assert 'kind: "team"' in app_js
    assert "scatter-marker-image" in app_js
    assert "scatter-marker-hitbox" in app_js
    assert ".scatter-entity-marker" in styles
    assert ".scatter-marker-image" in styles
    for label_text in (
        "xG × xA", "Finalizações × xG", "Produção por posição",
        "Gols × xG", "Finalizações feitas × sofridas",
        "Gols por 90", "xG por 90", "Ações defensivas por 90",
    ):
        assert label_text in app_js
    assert "function playerRankingExplorer" in app_js
    assert "analysis-table-disclosure" in app_js
    assert "radar-benchmark-area" in app_js
    assert "Média da posição" in app_js
    assert "Média da Copa" in app_js
    team_profile = app_js[
        app_js.index("function teamProfileView"):
        app_js.index("function renderPlayerDetail")
    ]
    assert "Principais jogadores" not in team_profile
    assert "playerOverviewTable" not in team_profile
    assert 'activeTab === "match_log"' in team_profile
    assert 'activeTab === "shots"' in team_profile
    assert "Percentil 100" not in team_profile
    assert 'standingUniverse: "das seleções"' in app_js
    assert "team-profile-tabs" in styles
    assert "team-match-card" in styles
    assert 'goToProfile("player"' in app_js
    assert 'goToProfile("team"' in app_js
    assert "isGoalkeeper" in app_js
    assert "radar.length < 4 || benchmarkRadar.length < 4" in app_js
    assert "value !== 0" in app_js
    profile_tabs = app_js[
        app_js.index("function profilePlayerTabs"):
        app_js.index("function profilePlayerSelector")
    ]
    assert '"Jogo a jogo"' in profile_tabs
    assert '"radar"' not in profile_tabs
    assert '"distribution"' not in profile_tabs
    player_profile = app_js[
        app_js.index("function playerProfileView"):
        app_js.index("function playerMatchLogTable")
    ]
    assert "Percentil 100" not in player_profile
    assert 'activeTab === "match_log"' in player_profile
    assert "playerRadarFeature" in player_profile
    assert "playerShotExperience" in player_profile
    assert "profile-radar-feature" in styles
    assert "player-match-card.is-dnp" in styles
    assert 'section("Destaques da edição"' in app_js
    assert 'section("Mapa de comparação"' in app_js
    assert 'section("Produção por posição"' in app_js
    assert 'section("Perfil das finalizações"' in app_js
    assert 'regular: "Bola rolando"' in app_js
    assert '"set-piece": "Bola parada"' in app_js
    assert '"fast-break": "Contra-ataque"' in app_js
    assert '"throw-in-set-piece": "Lateral ensaiado"' in app_js
    assert "creationHost" not in players_render
    assert "volumeHost" not in players_render
    assert 'minMinutes: 90, minShots: 3, minGames: 1' in app_js
    assert 'body[data-page="players"][data-skin="2026"] .page-head' in styles
    assert ".player-editorial-highlights" in styles
    assert ".player-comparison-switch" in styles
    assert 'section("Destaques da edição"' in teams_experience
    assert 'section("Mapa de comparação"' in teams_experience
    assert 'section("Produção ofensiva e defensiva"' in teams_experience
    assert 'section("Perfil coletivo"' in teams_experience
    assert "efficiencyHost" not in teams_experience
    assert "volumeHost" not in teams_experience
    assert "possessionHost" not in teams_experience
    assert 'body[data-page="teams"][data-skin="2026"] .page-head' in styles
    assert ".team-editorial-highlights" in styles
    assert ".team-comparison-map" in styles
    assert ".team-collective-profile" in styles
    assert "meta instanceof Node" in app_js
    assert 'body[data-skin="2026"] .home-ranking-entity,' in styles
    for selector in (
        ".players-control-panel", ".players-analysis-layout",
        ".players-overview-table", ".teams-analysis-layout",
        ".team-comparison-scatter", ".profile-mode-tabs",
        ".profile-selector-panel", ".player-profile-summary",
    ):
        assert selector in styles


def test_analytical_adapters_calculate_per_90_and_collective_metrics(monkeypatch) -> None:
    player = TheStatsApiBronzeService._merge_player_rows([
        {
            "player_id": "p1", "player_name": "Player", "minutes_played": 90,
            "goals": 1, "assists": 1, "shots": 3, "xg": 1.0, "xa": .4,
            "key_passes": 2, "tackles": 1, "interceptions": 1,
            "clearances": 1, "duels_won": 2,
        },
        {
            "player_id": "p1", "player_name": "Player", "minutes_played": 90,
            "goals": 1, "assists": 0, "shots": 2, "xg": .5, "xa": .2,
            "key_passes": 1, "tackles": 1, "interceptions": 0,
            "clearances": 1, "duels_won": 2,
        },
    ])

    assert player["goal_involvements"] == 3
    assert player["goals_per_90"] == 1
    assert player["xg_per_90"] == .75
    assert player["xa_per_90"] == .3
    assert player["defensive_actions"] == 5
    assert player["defensive_actions_per_90"] == 2.5

    service = TheStatsApiBronzeService()
    standings = {
        "A": [
            {"team_id": "bra", "team_name": "Brazil", "group_name": "A", "played": 1, "goals_for": 2, "goals_against": 1},
            {"team_id": "fra", "team_name": "France", "group_name": "A", "played": 1, "goals_for": 1, "goals_against": 2},
        ]
    }
    details = [{
        "match": {"home_team": "Brazil", "away_team": "France"},
        "players": [],
        "shot_map": [],
        "team_summary": [
            {"team_name": "Brazil", "shots": 8, "goals": 2},
            {"team_name": "France", "shots": 4, "goals": 1},
        ],
        "stats_comparison": [
            {"metric": "expected_goals", "section": "overview", "Brazil": 1.8, "France": .7},
            {"metric": "total_shots", "section": "overview", "Brazil": 8, "France": 4},
            {"metric": "shots_on_target", "section": "overview", "Brazil": 3, "France": 2},
            {"metric": "passes", "section": "overview", "Brazil": 100, "France": 80},
            {"metric": "accurate_passes", "section": "overview", "Brazil": 90, "France": 60},
            {"metric": "ball_possession", "section": "overview", "Brazil": 60, "France": 40},
            {"metric": "ball_recoveries", "section": "defending", "Brazil": 40, "France": 35},
            {"metric": "tackles", "section": "defending", "Brazil": 12, "France": 15},
        ],
    }]
    teams = service.team_rows(2026, standings, details)
    brazil = next(row for row in teams if row["team_name"] == "Brazil")

    assert brazil["shots_against"] == 4
    assert brazil["shots_on_target"] == 3
    assert brazil["average_possession"] == 60
    assert brazil["pass_accuracy"] == 90
    assert brazil["goals_per_game"] == 2
    assert brazil["xg_per_game"] == 1.8

    monkeypatch.setattr(service, "_all_match_details", lambda year: details)
    monkeypatch.setattr(service, "standings_by_group", lambda year: standings)
    team_profile = service.team_detail(2026, "bra")
    assert team_profile["benchmarks"]["metrics"]["xg"]["sample_size"] == 2
    assert team_profile["benchmarks"]["metrics"]["xga"]["direction"] == "lower"
    assert len(team_profile["radar"]) >= 4
    assert all(axis["value"] == 50 for axis in team_profile["benchmark_radar"])
    assert len(team_profile["shot_benchmark"]["minute_bins"]) == 7
    teams_payload = service.teams(2026)
    assert teams_payload["shot_breakdowns"] == {"body_part": [], "shot_type": []}


def test_player_detail_aggregates_metrics_and_supports_contexts(monkeypatch) -> None:
    service = TheStatsApiBronzeService()
    player = {
        "player_id": "p1", "player_name": "Player One", "team_id": "t1",
        "team_name": "Brazil", "position": "F",
    }
    details = [
        {
            "match": {
                "match_id": "group-1", "match_date": "2026-06-12T19:00:00Z",
                "group_name": "A", "stage": "Group Stage", "home_team": "Brazil",
                "away_team": "France", "home_score": 1, "away_score": 0,
            },
            "players": [
                {**player, "minutes_played": 90, "goals": 1, "shots": 2, "xg": .8, "passes": 20, "accurate_passes": 18, "rating": 7.5},
                {**player, "player_id": "peer", "player_name": "Peer", "minutes_played": 90, "goals": 0, "shots": 1, "xg": .2, "passes": 12, "accurate_passes": 10, "rating": 6.5},
            ],
            "shot_map": [{"player_id": "p1", "match_id": "group-1", "minute": 20, "xg": .8}],
        },
        {
            "match": {
                "match_id": "knockout-1", "match_date": "2026-06-28T19:00:00Z",
                "group_name": None, "stage": "round_of_32", "home_team": "Brazil",
                "away_team": "Japan", "home_score": 2, "away_score": 1,
            },
            "players": [
                {**player, "minutes_played": 60, "goals": 1, "shots": 3, "xg": 1.1, "passes": 10, "accurate_passes": 8, "rating": 8.0},
                {**player, "player_id": "peer", "player_name": "Peer", "minutes_played": 60, "goals": 0, "shots": 2, "xg": .4, "passes": 8, "accurate_passes": 6, "rating": 6.8},
            ],
            "shot_map": [{"player_id": "p1", "match_id": "knockout-1", "minute": 70, "xg": 1.1}],
        },
        {
            "match": {
                "match_id": "group-dnp", "match_date": "2026-06-20T19:00:00Z",
                "group_name": "A", "stage": "Group Stage", "home_team": "Brazil",
                "away_team": "Norway", "home_score": 0, "away_score": 0,
            },
            "players": [
                {**player, "played": False, "minutes_played": 0, "goals": 0, "shots": 0, "xg": 0, "passes": 0, "accurate_passes": 0, "rating": 0},
            ],
            "shot_map": [],
        },
    ]
    monkeypatch.setattr(service, "_all_match_details", lambda year: details)

    full = service.player_detail(2026, "p1")
    group = service.player_detail(2026, "p1", scope="group_stage")
    match = service.player_detail(2026, "p1", scope="match", match_id="knockout-1")

    assert full["summary"]["minutes_played"] == 150
    assert full["summary"]["goals"] == 2
    assert full["summary"]["shots"] == 5
    assert full["summary"]["passes"] == 30
    assert full["summary"]["accurate_passes"] == 26
    assert full["summary"]["pass_accuracy"] == 86.7
    assert full["summary"]["games"] == 2
    assert full["summary"]["rating"] == 7.75
    assert full["benchmarks"]["label"] == "Média dos atacantes"
    assert full["benchmarks"]["metrics"]["xg"]["sample_size"] == 2
    assert [axis["axis"] for axis in full["benchmark_radar"]] == [axis["axis"] for axis in full["radar"]]
    assert len(full["match_log"]) == 3
    assert [row["match_id"] for row in full["match_log"]] == ["group-1", "group-dnp", "knockout-1"]
    assert full["match_log"][1]["participated"] is False
    assert full["match_log"][1]["opponent"] == "Norway"
    assert {row["stage"] for row in full["match_log"]} == {"Group Stage", "round_of_32"}
    assert group["summary"]["minutes_played"] == 90
    assert group["context"]["scope"] == "group_stage"
    assert match["summary"]["minutes_played"] == 60
    assert match["context"]["match_id"] == "knockout-1"
    assert len(match["shot_map"]) == 1


def test_player_surfaces_use_resolved_positions_without_internal_diagnostics() -> None:
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")

    assert "function resolvedPlayerPosition" in app_js
    assert "inferred_positions" in app_js
    assert '"Grupo bruto"' in app_js
    assert '"Posição inferida"' in app_js
    assert "role_confidence" not in app_js
    assert "role_source" not in app_js


def test_about_page_is_reachable_and_credits_data_source_and_author() -> None:
    """New "Sobre" nav item is a secondary/utility link (not competing with the main
    Início/Competição/Partidas/... nav), routing to a static credits page — no data fetch, no
    edition/year scoping. Must credit TheStatsAPI as the data source and name the author, matching
    the editorial pageHead pattern used by every other internal screen. (The "Arquivo histórico"
    link this was originally placed alongside was later removed at the user's request — see
    test_history_link_is_removed_but_about_link_remains — "Sobre" is now the only secondary link.)"""
    root = Path(__file__).parents[1] / "webapp/static"
    app_js = (root / "app.js").read_text(encoding="utf-8")
    index_html = (root / "index.html").read_text(encoding="utf-8")
    main_src = (Path(__file__).parents[1] / "webapp/main.py").read_text(encoding="utf-8")

    # nav placement: static secondary link, not inside the main menu
    assert '<a class="history-link" href="/about">Sobre' in index_html

    # mobile nav fallback (JS-injected) mirrors the same secondary placement
    assert 'href: "/about", text: "Sobre"' in app_js

    # routing: recognized without a year prefix, like history
    assert 'parts[0] === "about" || parts[0] === "sobre"' in app_js
    assert 'if (page === "about") return "/about";' in app_js

    # navigate(): renders statically, no API fetch, bypasses the edition-menu availability check
    navigate_body = app_js[app_js.index("async function navigate("):app_js.index("els.select.addEventListener(")]
    assert 'if (state.page === "about")' in navigate_body
    assert "renderAbout();" in navigate_body

    # content: TheStatsAPI credit + author name, using the shared pageHead component
    assert "function renderAbout(" in app_js
    about_body = app_js[app_js.index("function renderAbout("):app_js.index("function renderError(")]
    assert 'pageHead("Créditos", "Sobre"' in about_body
    assert "TheStatsAPI" in about_body
    assert "João Vitor Machado de Mello" in about_body

    # backend: /about must not 404 through the SPA catch-all fallback
    assert 'first_segment in ("history", "about")' in main_src


def test_history_link_is_removed_but_about_link_remains() -> None:
    """Regression: with only the 2026 edition ready, the "Arquivo histórico" nav link (which only
    makes sense once other past-edition archives exist) was removed from both the static desktop
    header and the JS-injected mobile-menu fallback. "Sobre" stays — it's not edition-dependent."""
    root = Path(__file__).parents[1] / "webapp/static"
    app_js = (root / "app.js").read_text(encoding="utf-8")
    index_html = (root / "index.html").read_text(encoding="utf-8")

    assert "Arquivo histórico" not in index_html
    assert "Arquivo histórico" not in app_js
    assert 'href="/history"' not in index_html

    # "Sobre" remains in both the static header and the mobile fallback
    assert '<a class="history-link" href="/about">Sobre' in index_html
    render_nav_body = app_js[app_js.index("function renderNav("):app_js.index("function showLoading(")]
    assert 'href: "/about", text: "Sobre"' in render_nav_body


def test_edition_select_is_disabled_with_a_single_edition() -> None:
    """Regression: the edition <select> let the user pick a year even though only 2026 has data —
    switching would silently break. Disabled it directly in the markup (JS only repopulates the
    <option> children on load, never touches the disabled attribute, so it stays disabled)."""
    index_html = (Path(__file__).parents[1] / "webapp/static/index.html").read_text(encoding="utf-8")
    styles = (Path(__file__).parents[1] / "webapp/static/styles.css").read_text(encoding="utf-8")

    select_tag = index_html[index_html.index('<select id="edition-select"'):index_html.index("</select>")]
    assert "disabled" in select_tag
    assert "select:disabled" in styles


def test_ui_ux_audit_hero_titles_and_status_vocabulary() -> None:
    """Regression batch from the 2026-07-06 UI/UX audit ticket, part 1: hero title sizing and
    status vocabulary. Perfil and Sobre had no .page-head h1 override (rendered at raw hero scale,
    ~100px, unlike every other internal screen); Início's mobile hero had no size reduction either.
    Separately, Home used its own homeMatchStatus() ("Programado") while Partidas/Competição used
    competitionMatchStatus() ("Agendado"/"Hoje") for the identical "not yet started" match state —
    unified onto the single shared function."""
    styles = (Path(__file__).parents[1] / "webapp/static/styles.css").read_text(encoding="utf-8")
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")

    assert 'body[data-page="profile"][data-skin="2026"] .page-head h1,\nbody[data-page="about"][data-skin="2026"] .page-head h1 {' in styles
    assert 'body[data-page="overview"][data-skin="2026"] .page-head h1 { font-size: 42px; }' in styles
    assert 'body[data-page="profile"][data-skin="2026"] .page-head h1,\n  body[data-page="about"][data-skin="2026"] .page-head h1 { font-size: 42px; }' in styles

    assert "function homeMatchStatus" not in app_js
    home_bracket_body = app_js[app_js.index("function homeBracketMatch("):app_js.index("function homePulse(")]
    assert "competitionMatchStatus(match)" in home_bracket_body
    compact_row_body = app_js[app_js.index("function compactMatchRow("):app_js.index("function homeRankingEntity(")]
    assert "competitionMatchStatus(match)" in compact_row_body


def test_ui_ux_audit_match_detail_and_profile_fixes() -> None:
    """Regression batch, part 2: Match Detail's subnav skipped "Top impactos da partida" and
    "Visão geral da partida" (rendered with no anchor between Resumo and Finalizações & xG) —
    added a "Visão geral" anchor/link. "História do jogo" silently capped at 5 lines with no
    indicator (and the backend hard-truncated with lines[:5], making the frontend blind to any
    excess) — backend now returns the full list, frontend shows a "+N" note when truncating.
    Perfil's player/team search showed a blank list on no matches and silently dropped results
    past 80 with no notice."""
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")
    service_src = (Path(__file__).parents[1] / "webapp/thestatsapi_service.py").read_text(encoding="utf-8")

    subnav_body = app_js[app_js.index("function matchSubnav("):app_js.index("function activateMatchSubnav(")]
    assert '["Visão geral", "#match-overview"]' in subnav_body
    assert 'section("Visão geral da partida", null, matchOverview(data, match), "wide-chart match-overview", "match-overview")' in app_js

    assert "return lines[:5]" not in service_src
    story_panel_body = app_js[app_js.index("function matchStoryPanel("):app_js.index("function comparisonBars(")]
    assert "story-more" in story_panel_body

    assert "profile-selector-empty" in app_js
    assert "profile-selector-truncated" in app_js
    assert "Nenhum jogador encontrado" in app_js
    assert "Nenhuma seleção encontrada" in app_js


def test_ui_ux_audit_jogadores_and_scatter_fixes() -> None:
    """Regression batch, part 3: Jogadores' numeric filters (Minutos/Finalizações/Jogos mínimos)
    stayed enabled and editable even when "Todos" was active, with no effect; the confusingly
    internal-sounding "Grupo bruto" filter label was renamed; "Perfil das finalizações"/"Perfil
    coletivo" pie charts silently showed edition-wide data regardless of active filters — labeled
    explicitly rather than rebuilt as a filtered feature (no per-filter shot data exists in the
    API today); dense scatter point clouds (default Qualificados filter can still leave 100+
    points) got an opacity de-clutter treatment."""
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")
    styles = (Path(__file__).parents[1] / "webapp/static/styles.css").read_text(encoding="utf-8")

    overview_body = app_js[app_js.index("function playerOverviewExperience("):app_js.index("function teamEditionHighlights(")]
    assert "numberInputs.forEach(input => { input.disabled = !filters.qualified; });" in overview_body
    assert '"Posição (grupo amplo)"' in overview_body
    assert '"Posição (detalhada)"' in overview_body
    assert '"Grupo bruto"' not in overview_body

    assert 'section("Perfil das finalizações", "Dados de toda a Copa' in app_js
    assert 'section("Perfil coletivo", "Dados de toda a Copa' in app_js

    assert "function scatterEntityMarker(" in app_js
    marker_body = app_js[app_js.index("function scatterEntityMarker("):app_js.index("function scatterEntityMarker(") + 700]
    assert "is-dense" in marker_body
    assert ".scatter-entity-marker.is-dense" in styles


def test_ui_ux_audit_accessibility_and_dead_code_cleanup() -> None:
    """Regression batch, part 4: tab-like controls (role="tab") had no arrow-key navigation;
    clickable rows on Partidas/Competição had outline: none on :focus-visible with only a faint
    background tint; role="link" rows (which don't natively support Space activation per ARIA
    practice) also responded to Space; three fully dead functions (never called from anywhere)
    were removed; homeHighlights() was fully built (backend already supplies data.highlights) but
    never wired into Home."""
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")
    styles = (Path(__file__).parents[1] / "webapp/static/styles.css").read_text(encoding="utf-8")

    assert "function attachTabListKeyNav(" in app_js
    assert app_js.count("attachTabListKeyNav(node(") >= 10

    assert "outline: 2px solid var(--accent); outline-offset: -2px;" in styles
    assert "outline: 2px solid var(--wc26-teal);" in styles

    for dead_function in ("playerAnalysisExperience", "teamOverviewTable", "analysisRankingExplorer"):
        assert f"function {dead_function}" not in app_js

    assert "function homeHighlights" in app_js
    overview_render = app_js[app_js.index("function renderOverview("):app_js.index("function homeSummaryStrip(")]
    assert "homeHighlights(data.highlights || {}, leaders)" in overview_render
    assert 'section("Destaques da Copa"' in overview_render

    # role="link" rows keep Enter but drop Space; role="button" rows keep both (unaffected)
    match_calendar_row_body = app_js[app_js.index("function matchCalendarRow("):app_js.index("function matchCalendarDayLabel(")]
    assert 'if (event.key === "Enter") { event.preventDefault(); routeTo("matches", match.match_id); }' in match_calendar_row_body
    knockout_match_card_body = app_js[app_js.index("function knockoutMatchCard("):app_js.index("function withHorizontalScrollFade(")]
    assert 'if (event.key === "Enter") {\n          event.preventDefault();\n          routeTo("matches", match.match_id);' in knockout_match_card_body


def test_2026_home_is_a_compact_editorial_match_center() -> None:
    root = Path(__file__).parents[1] / "webapp/static"
    app_js = (root / "app.js").read_text(encoding="utf-8")
    styles = (root / "styles.css").read_text(encoding="utf-8")

    overview = app_js[
        app_js.index("function renderOverview"):
        app_js.index("function renderTeams")
    ]

    for function_name in (
        "homeSummaryStrip",
        "homeCompetitionProgress",
        "homePulse",
        "homeFriendlyKickoff",
        "homeBracketSummary",
        "compactMatchRow",
        "homeRankingPanel",
        "homeDiscoveryLab",
        "homeDiscoveryCategoryCard",
        "openDiscoveryCategoryView",
        "homeDiscoveryMetricPanel",
        "openPlayerQuickView",
        "openHomeTeamQuickView",
        "openRankingQuickView",
    ):
        assert f"function {function_name}" in app_js

    for heading in (
        "Pulso da Copa",
        "Caminho do mata-mata",
        "Líderes da Copa",
        "Explorar estatísticas",
    ):
        assert heading in overview

    assert "home-summary-strip" in app_js
    # The stale pulse headline ("N vagas nas oitavas...") was removed on 2026-07-09:
    # the phase strip alone states where the tournament is.
    assert "function homePulseHeadline" not in app_js
    assert "home-pulse-headline" not in app_js
    assert "home-competition-progress" in app_js
    assert "home-match-row" in app_js
    assert "home-ranking-row" in app_js
    for tab in ("Jogadores", "Seleções", "Partidas", "Curiosidades"):
        assert f'"{tab}"' in overview
    assert "flagNode" in overview
    assert "openMatchQuickView" in overview
    assert "data.pulse" in overview
    assert "data.knockout_summary" in overview
    assert "data.discoveries" in overview
    assert "const fragment = document.createDocumentFragment();" in overview
    assert "dashboardShell(" not in overview
    assert "score-grid" not in overview
    assert "horizontalBars" not in overview
    assert 'section("Últimos resultados"' not in overview
    assert 'section("Próximos jogos"' not in overview
    summary_strip = app_js[
        app_js.index("function homeSummaryStrip"):
        app_js.index("function knockoutSideNode")
    ]
    for metric in ("summary.shot_conversion", "summary.clean_sheets", "summary.goals", "summary.goals_per_match", "summary.xg_per_match", "summary.shots", "summary.xg", "summary.players"):
        assert metric in summary_strip
    assert not any(
        term in overview
        for term in (
            "match_id:",
            "player_id:",
            "team_id:",
            "fetch_status",
            "endpoint_status",
        )
    )

    assert 'body[data-page="overview"][data-skin="2026"] .home-summary-strip' in styles
    assert 'body[data-page="overview"][data-skin="2026"] .home-match-row' in styles
    assert 'body[data-page="overview"][data-skin="2026"] .home-ranking-panel' in styles
    assert 'body[data-page="overview"][data-skin="2026"] .home-pulse' in styles
    assert 'body[data-page="overview"][data-skin="2026"] .home-bracket-summary' in styles
    assert 'body[data-page="overview"][data-skin="2026"] .discovery-category-grid' in styles
    assert 'body[data-page="overview"][data-skin="2026"] .discovery-category-card' in styles
    discovery = app_js[
        app_js.index("function homeDiscoveryLab"):
        app_js.index("function homeHighlights")
    ]
    assert 'text: "Ver ranking completo"' in discovery
    assert "rows.slice(0, 5)" in discovery
    assert 'role: "tablist"' not in discovery
    assert "white-space: nowrap" in styles
    assert "text-overflow: ellipsis" in styles
    assert "@media (max-width: 640px)" in styles


def test_home_summary_replaces_pipeline_counts_with_narrative_metrics() -> None:
    """Regression: "Partidas" (100) and "Encerradas" (75) in "Resumo da edição" were pipeline
    status counts, not editorial data, and "Encerradas" duplicated the phase already shown in
    "Pulso da Copa" right below. Replace them with "Conversão média" (goals/shots, the same
    formula already used for "Conversão de chutes") and "Clean sheets" (finished matches where at
    least one side didn't concede), computed from data already in competition_summary()."""
    service = TheStatsApiBronzeService()
    fixtures = [
        {"status": "finished", "home_score": 2, "away_score": 0},
        {"status": "finished", "home_score": 1, "away_score": 1},
        {"status": "scheduled", "home_score": None, "away_score": None},
    ]
    teams = [{"shots": 10, "xg": 1.5}, {"shots": 15, "xg": 2.0}]

    summary = service.competition_summary(fixtures, players=[], teams=teams)

    assert summary["goals"] == 4
    assert summary["shots"] == 25
    assert summary["shot_conversion"] == round(4 / 25 * 100, 1)
    assert summary["clean_sheets"] == 1  # only the 2-0 match had a side keep a clean sheet

    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")
    summary_strip = app_js[app_js.index("function homeSummaryStrip"):app_js.index("function knockoutSideNode")]
    assert '"Conversão média"' in summary_strip
    assert '"Clean sheets"' in summary_strip
    assert '"Partidas"' not in summary_strip
    assert '"Encerrados"' not in summary_strip
    assert "summary.shot_conversion" in summary_strip
    assert "summary.clean_sheets" in summary_strip


def test_home_agenda_placeholder_matches_use_ellipsis_not_overlap() -> None:
    """Regression: "Agenda de hoje" rendered a placeholder team name (e.g. "Vencedor de Holanda
    x Marrocos") as raw text directly on a display:flex `.home-match-team` span. Flex containers
    don't apply text-overflow: ellipsis to their own raw text content, so the long placeholder
    overflowed the grid column and visually collided with the time/score in the center column.
    Fix: nest the placeholder text in a child span, matching the structure teamLabel() already
    uses for real team names, so the existing ellipsis rule (`.home-match-team span:last-child`)
    applies uniformly."""
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")
    compact_side = app_js[app_js.index("function compactMatchSide("):app_js.index("function compactMatchSideLabel(")]
    assert 'node("span", { text: placeholderText })' in compact_side
    assert 'node("span", { class: `${className} is-placeholder`, title: placeholderText }' in compact_side


def test_home_summary_cards_stay_neutral_and_bracket_avoids_score_duplication() -> None:
    """Regression: "Resumo da edição" metric cards (Partidas, Encerrados, Gols...) had a
    per-item colored top border (nth-child rainbow) even though they're neutral metric
    categories, not competition groups with their own identity. And "Caminho do mata-mata"
    duplicated the exact score already shown by "Quem avançou" for the same recently-decided
    matches — it must stay purely structural (matchup + kickoff time/status)."""
    styles = (Path(__file__).parents[1] / "webapp/static/styles.css").read_text(encoding="utf-8")
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")

    assert "home-summary-metric:nth-child" not in styles

    bracket_match = app_js[app_js.index("function homeBracketMatch("):app_js.index("function homePulse(")]
    assert "scorePill" not in bracket_match
    assert "hasScore" not in bracket_match
    assert "home-bracket-center" in bracket_match


def test_competition_group_cards_get_a_stable_per_group_color() -> None:
    """Regression: group cards only had a thin neutral border with no visual identity per group.
    Give each group (A-L) a full 4-side border, +5px thicker than the base 1px border, in a color
    unique to that group — purely decorative, reused consistently by the group card, Melhores
    Terceiros and the "Grupo X" tags in Partidas."""
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")
    styles = (Path(__file__).parents[1] / "webapp/static/styles.css").read_text(encoding="utf-8")

    assert "function groupTag(" in app_js
    assert 'groupTag(match.group_name)' in app_js  # Partidas calendar row
    assert 'groupTag(team.group_name)' in app_js  # Melhores Terceiros table

    assert '"data-group": group.name' in app_js  # competition group card carries the same hook

    for letter in "ABCDEFGHIJKL":
        assert f"--group-color-{letter.lower()}:" in styles
        assert f'[data-group="{letter}"]' in styles

    assert ".competition-group-card { --group-color: var(--line); min-width: 0; overflow: hidden; border: 6px solid var(--group-color);" in styles
    assert ".group-tag {" in styles


def test_matches_screen_never_shows_a_blank_confrontation_side() -> None:
    """Regression: a future knockout match (e.g. the 09/jul quarter-final "Vencedor de Canada x
    Paraguay" vs "A definir") rendered one side completely blank. Root cause was the same class of
    bug as the Home "Agenda de hoje" overlap: matchTeamLink() and knockoutSideNode() put the
    placeholder text directly on a display:flex container instead of a nested child span, so
    text-overflow/line-clamp rules (which only target the nested span) never applied and the long
    placeholder could collapse to near-zero width in the flex row. Also: the bracket-side resolver
    must always resolve to "Vencedor de X x Y" (previous matchup known) or "A definir" (nothing
    resolved yet) — never the old "Aguardando definição" wording, and never blank."""
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")
    service_src = (Path(__file__).parents[1] / "webapp/thestatsapi_service.py").read_text(encoding="utf-8")

    match_team_link = app_js[app_js.index("function matchTeamLink("):app_js.index("function matchCalendarRow(")]
    assert 'node("span", { class: "matches-calendar-team is-placeholder", title: display }, [node("span", { text: display })])' in match_team_link

    knockout_side_node = app_js[app_js.index("function knockoutSideNode("):app_js.index("function homeFriendlyKickoff(")]
    assert 'node("span", { text: placeholderText })' in knockout_side_node
    assert 'text: translateTeamsInText(side?.placeholder || "A definir")' not in knockout_side_node

    assert '"Aguardando definição"' not in service_src
    assert '"placeholder": placeholder or ("A definir" if not defined else None)' in service_src


def test_matches_calendar_score_placeholder_does_not_repeat_status_badge() -> None:
    """Regression: a scheduled/undecided match showed "A definir" twice on the same row — once as
    the central score placeholder and once as the status badge. The score column must use a
    neutral "×" (the same no-score symbol already used by scoreCard/knockoutMatchCard) and leave
    "A definir" exclusively to the status badge."""
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")
    match_calendar_row = app_js[app_js.index("function matchCalendarRow("):app_js.index("function matchCalendarDayLabel(")]
    assert 'const score = hasScore && (finished || live) ? `${formatValue(match.home_score)}–${formatValue(match.away_score)}` : "×";' in match_calendar_row
    assert '"A definir" : "×"' not in match_calendar_row


def test_match_status_vocabulary_is_shared_between_matches_and_knockout() -> None:
    """Regression check: Partidas' filter options and Mata-mata's status badges must draw from the
    exact same vocabulary. Both `matchPublicStatus` (Partidas) and the knockout bracket cards call
    the same `competitionMatchStatus()` function, so there is only one status vocabulary to keep in
    sync — confirm no legacy variant ("Aguardando atualização") lingers anywhere."""
    app_js = (Path(__file__).parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")
    service_src = (Path(__file__).parents[1] / "webapp/thestatsapi_service.py").read_text(encoding="utf-8")

    match_public_status = app_js[app_js.index("function matchPublicStatus("):app_js.index("function matchTeamLink(")]
    assert "competitionMatchStatus(match)" in match_public_status

    assert "Aguardando atualização" not in app_js
    assert "Aguardando atualização" not in service_src
    for source in (app_js, service_src):
        assert "Aguardando resultado" in source


def test_2026_home_rankings_use_central_modal_and_semantic_xg_balance() -> None:
    root = Path(__file__).parents[1] / "webapp/static"
    app_js = (root / "app.js").read_text(encoding="utf-8")
    styles = (root / "styles.css").read_text(encoding="utf-8")
    overview = app_js[
        app_js.index("function renderOverview"):
        app_js.index("function renderTeams")
    ]

    for title in (
        '"Gols"',
        '"xG"',
        '"Assistências"',
        '"Finalizações"',
        '"Maior xG"',
        '"Saldo de xG"',
    ):
        assert title in overview
    assert '"Gols marcados"' not in overview
    assert '"Maior xG total"' not in overview

    assert 'layout: "modal"' in overview
    assert "ranking-detail-head" in overview
    assert "ranking-detail-column" in overview
    assert "homeRankingValueClass" in overview
    assert "is-positive" in overview
    assert "is-negative" in overview
    assert 'round_of_32: "Fase de 32"' in overview
    assert '"16 avos"' not in overview
    assert 'text: "Ver ranking completo"' in overview
    assert 'text: "Horários em Brasília"' in overview
    assert "homeMatchIsLive" in overview
    assert '.quick-view-overlay.is-modal' in styles
    assert '.quick-view-drawer.is-modal' in styles
    assert '.home-ranking-value.is-positive' in styles
    assert '.home-ranking-value.is-negative' in styles


def test_home_time_and_xg_ranking_contracts_are_complete() -> None:
    service = TheStatsApiBronzeService()
    penalty_summary = service._match_summary(
        {
            "id": "penalties",
            "home_team": {"id": "ger", "name": "Germany"},
            "away_team": {"id": "par", "name": "Paraguay"},
            "score": {"home": 1, "away": 1, "final_score": {"home": 4, "away": 5}},
        },
        {},
    )
    assert penalty_summary["penalty_home_score"] == 4
    assert penalty_summary["penalty_away_score"] == 5

    stale_live = {
        "status": "in_progress",
        "match_date": "2026-06-29T01:00:00Z",
        "home_score": 1,
        "away_score": 1,
    }
    now = datetime(2026, 6, 30, 12, tzinfo=timezone.utc)

    assert service._is_effectively_finished(stale_live, now=now) is True
    assert str(service._local_match_date(stale_live)) == "2026-06-28"

    teams = [
        {"team_name": f"Team {index}", "xg_difference": 6 - index}
        for index in range(12)
    ]
    ranking = service.team_leaders(teams)["xg_difference"]

    assert len(ranking) == 12
    assert ranking[0]["xg_difference"] == 6
    assert ranking[-1]["xg_difference"] == -5


def test_match_story_describes_equal_displayed_xg_as_balanced() -> None:
    story = TheStatsApiBronzeService._match_story(
        {"home_team": "Haiti", "away_team": "Scotland"},
        [{"metric": "expected_goals", "Haiti": 1.054, "Scotland": 1.051}],
        [],
        [],
    )

    assert story[0] == "A criação foi equilibrada: 1,05 xG para cada lado."
    assert all("controlou a criação" not in line for line in story)


def test_match_story_uses_pt_br_decimal_separator_everywhere() -> None:
    """Regression: the match narrative embedded raw Python float repr directly into text (e.g.
    "0.44 xG"), bypassing the pt-BR comma-decimal convention used everywhere else in the product.
    Every numeric value inserted into narrative text — not just card/table values — must go
    through the same formatter."""
    story = TheStatsApiBronzeService._match_story(
        {"home_team": "Netherlands", "away_team": "Morocco"},
        [
            {"metric": "expected_goals", "Netherlands": 1.313, "Morocco": 0.442},
            {"metric": "total_shots", "Netherlands": 14, "Morocco": 6},
            {"metric": "ball_recoveries", "Netherlands": 38, "Morocco": 30},
        ],
        [],
        [
            {"minute": 12, "player_name": "Cody Gakpo", "team_name": "Netherlands", "is_goal": True, "xg": 0.44},
        ],
    )
    assert not any(re.search(r"\d\.\d", line) for line in story), story
    assert any("1,31 xG contra 0,44" in line for line in story)
    assert any("0,44 xG aos 12" in line for line in story)


def test_match_story_consolidates_repeated_scorer_minutes() -> None:
    """Regression: when the same player scores twice, the narrative repeated their name
    ("marcados por Jogador aos X' e Jogador aos Y'") instead of consolidating into "marcados por
    Jogador, aos X' e Y'." Different scorers must still be listed normally (name repeated once
    each, joined by "e"), consolidation only applies to a repeated single scorer."""
    consolidated = TheStatsApiBronzeService._match_story(
        {"home_team": "Argentina", "away_team": "Chile"},
        [],
        [],
        [
            {"minute": 9, "player_name": "Julián Álvarez", "team_name": "Argentina", "is_goal": True, "xg": 0.3},
            {"minute": 54, "player_name": "Julián Álvarez", "team_name": "Argentina", "is_goal": True, "xg": 0.5},
        ],
    )
    assert any(line == "Os gols foram marcados por Julián Álvarez, aos 9' e 54'." for line in consolidated)
    assert not any(line.count("Álvarez") > 1 for line in consolidated)

    mixed = TheStatsApiBronzeService._match_story(
        {"home_team": "Argentina", "away_team": "Chile"},
        [],
        [],
        [
            {"minute": 9, "player_name": "Julián Álvarez", "team_name": "Argentina", "is_goal": True, "xg": 0.3},
            {"minute": 40, "player_name": "Lionel Messi", "team_name": "Argentina", "is_goal": True, "xg": 0.2},
        ],
    )
    assert any("Julián Álvarez aos 9' e Lionel Messi aos 40'" in line for line in mixed)


def test_match_impact_prioritizes_decisive_actions_over_goalkeeper_distribution() -> None:
    match = {
        "home_team": "Mexico",
        "away_team": "South Africa",
        "home_score": 2,
        "away_score": 0,
    }
    scorer = {
        "player_name": "Raúl Jiménez",
        "team_name": "Mexico",
        "macroposition": "Centroavante",
        "rating": 7.93,
        "goals": 1,
        "xg": 0.81,
        "shots": 4,
        "shots_on_target": 2,
        "key_passes": 2,
        "duels_won": 6,
    }
    defeated_keeper = {
        "player_name": "Ronwen Williams",
        "team_name": "South Africa",
        "macroposition": "Goleiro",
        "rating": 6.58,
        "saves": 2,
        "accurate_passes": 28,
        "passes": 40,
        "clearances": 3,
    }

    scorer_impact = TheStatsApiBronzeService._match_impact(scorer, match)
    keeper_impact = TheStatsApiBronzeService._match_impact(defeated_keeper, match)

    assert scorer_impact["score"] > keeper_impact["score"]
    assert scorer_impact["category"] == "Decisivo"
    assert "1 gol" in scorer_impact["reasons"]
    assert keeper_impact["category"] == "Destaque defensivo"
    assert all("passes certos" not in reason for reason in keeper_impact["reasons"])


def test_apply_position_inference_is_shared_between_match_detail_and_reference_pool() -> None:
    """Regression: the reference pool used to build match-center radar percentiles never ran
    per-match position inference, so it could only ever bucket players into the four raw API
    groups. Wingers/attacking-mids/fullbacks resolved to finer inferred buckets at lookup time
    and never found a match, leaving their radar empty. _apply_position_inference must be the
    same call used for both the current match's players and the reference pool."""
    lineups = {
        "home": {
            "id": "team-1",
            "name": "Team One",
            "formation": "4-3-3",
            "starting_xi": [{"id": "keeper", "position": "G"}],
            "substitutes": [],
        }
    }
    player_rows = [{"player_id": "keeper", "player_name": "Keeper", "team_id": "team-1", "position": "G", "minutes_played": 90}]

    enriched = TheStatsApiBronzeService._apply_position_inference("match-1", lineups, player_rows, [])

    assert enriched[0]["inferred_role"] == "Goleiro"
    assert enriched[0]["role_confidence"] == "high"
    assert enriched[0]["resolved_position"] == "Goleiro"


def test_events_resolve_outgoing_substitute_via_minutes_played() -> None:
    """Regression: TheStatsAPI substitution events only report who came ON, so "Momentos do jogo"
    showed just "Player entrou" with no indication of who left. Cross-reference the substitution
    minute against teammates whose minutes_played stopped there to recover who went out — even
    when several subs happen for the same team at the same minute."""
    service = TheStatsApiBronzeService()
    match = {"match_id": "m1"}
    events_payload = {
        "events": [
            {
                "type": "substitution",
                "minute": 61,
                "team": {"id": "team-1", "name": "South Africa"},
                "player": {"id": "in-1", "name": "Themba Zwane"},
            },
            {
                "type": "substitution",
                "minute": 75,
                "team": {"id": "team-1", "name": "South Africa"},
                "player": {"id": "in-2", "name": "Substitute Two"},
            },
            {
                "type": "substitution",
                "minute": 75,
                "team": {"id": "team-1", "name": "South Africa"},
                "player": {"id": "in-3", "name": "Substitute Three"},
            },
        ]
    }
    player_rows = [
        {"player_id": "in-1", "player_name": "Themba Zwane", "team_id": "team-1", "minutes_played": 29},
        {"player_id": "out-1", "player_name": "Jayden Adams", "team_id": "team-1", "minutes_played": 61},
        {"player_id": "out-2", "player_name": "Starter Two", "team_id": "team-1", "minutes_played": 75},
        {"player_id": "out-3", "player_name": "Starter Three", "team_id": "team-1", "minutes_played": 76},
        {"player_id": "keeper", "player_name": "Keeper", "team_id": "team-1", "minutes_played": 90},
    ]

    rows = service._events(match, events_payload, player_rows)

    by_minute = {row["minute"]: row for row in rows}
    assert by_minute[61]["player_in_name"] == "Themba Zwane"
    assert by_minute[61]["player_out_name"] == "Jayden Adams"
    outgoing_at_75 = {rows[1]["player_out_name"], rows[2]["player_out_name"]}
    assert outgoing_at_75 == {"Starter Two", "Starter Three"}, "each simultaneous substitution must resolve to a distinct outgoing player"


def test_match_story_uses_goals_and_does_not_promote_raw_impact_leader() -> None:
    story = TheStatsApiBronzeService._match_story(
        {"home_team": "Mexico", "away_team": "South Africa"},
        [
            {"metric": "expected_goals", "Mexico": 1.46, "South Africa": 0.07},
            {"metric": "total_shots", "Mexico": 16, "South Africa": 3},
        ],
        [{"player_name": "Ronwen Williams", "impact_score": 70.1, "macroposition": "Goleiro"}],
        [
            {"minute": 9, "player_name": "Julián Quiñones", "team_name": "Mexico", "is_goal": True, "xg": 0.22},
            {"minute": 67, "player_name": "Raúl Jiménez", "team_name": "Mexico", "is_goal": True, "xg": 0.49},
        ],
    )

    assert any("Julián Quiñones" in line and "Raúl Jiménez" in line for line in story)
    assert all("principal nome" not in line for line in story)
    assert all("Ronwen Williams" not in line for line in story)


def test_home_pulse_reports_knockout_consequences_and_next_matchups() -> None:
    service = TheStatsApiBronzeService()
    fixtures = [
        {
            "match_id": "m1",
            "stage": "round_of_32",
            "status": "finished",
            "match_date": "2026-06-28T19:00:00Z",
            "home_team": "Brazil",
            "home_team_id": "bra",
            "away_team": "Japan",
            "away_team_id": "jpn",
            "home_score": 2,
            "away_score": 1,
        },
        {
            "match_id": "penalties",
            "stage": "round_of_32",
            "status": "finished",
            "match_date": "2026-06-29T20:30:00Z",
            "home_team": "Germany",
            "home_team_id": "ger",
            "away_team": "Paraguay",
            "away_team_id": "par",
            "home_score": 1,
            "away_score": 1,
            "penalty_home_score": 4,
            "penalty_away_score": 5,
        },
        {
            "match_id": "m2",
            "stage": "round_of_32",
            "status": "scheduled",
            "match_date": "2026-07-01T19:00:00Z",
            "home_team": "France",
            "away_team": "Sweden",
            "home_score": None,
            "away_score": None,
        },
        {
            "match_id": "m3",
            "stage": "round_of_16",
            "status": "scheduled",
            "match_date": "2026-07-04T19:00:00Z",
            "home_team": "W73",
            "home_team_id": None,
            "away_team": "W75",
            "home_score": None,
            "away_score": None,
        },
    ]

    pulse = service.home_pulse(fixtures, now=datetime(2026, 6, 30, 12, tzinfo=timezone.utc))

    assert pulse["current_phase"] == "Fase de 32"
    penalty_result = next(item for item in pulse["classified_recent"] if item["winner_name"] == "Paraguay")
    assert penalty_result["eliminated_name"] == "Germany"
    assert penalty_result["decided_by"] == "penalties"
    assert penalty_result["score_label"] == "1–1 (5–4 nos pênaltis)"
    assert penalty_result["narrative"] == "Paraguay avançou nos pênaltis após empate por 1–1 contra Germany."
    brazil_result = next(item for item in pulse["classified_recent"] if item["winner_name"] == "Brazil")
    assert brazil_result["narrative"] == "Brazil avançou após vencer Japan por 2–1."
    assert pulse["next_matchups"][0]["home"]["team_name"] == "Brazil"
    assert pulse["next_matchups"][0]["away"]["placeholder"] == "Vencedor de France x Sweden"
    assert "partida 75" not in str(pulse)


def test_home_pulse_resolves_winner_placeholders_in_todays_matches() -> None:
    """Regression: "Agenda de hoje" used the raw fixtures list (home_team="W73") while
    "Próximos encaixes" resolved the same knockout matches through knockout_state — so a
    round_of_16 match scheduled for today showed the literal code instead of the known winner
    name or a "Vencedor de X x Y" placeholder."""
    service = TheStatsApiBronzeService()
    fixtures = [
        {
            "match_id": "m1",
            "stage": "round_of_32",
            "status": "finished",
            "match_date": "2026-06-28T19:00:00Z",
            "home_team": "Brazil",
            "home_team_id": "bra",
            "away_team": "Japan",
            "away_team_id": "jpn",
            "home_score": 2,
            "away_score": 1,
        },
        {
            "match_id": "m2",
            "stage": "round_of_32",
            "status": "scheduled",
            "match_date": "2026-07-01T19:00:00Z",
            "home_team": "France",
            "away_team": "Sweden",
            "home_score": None,
            "away_score": None,
        },
        {
            "match_id": "m3",
            "stage": "round_of_16",
            "status": "scheduled",
            "match_date": "2026-07-04T19:00:00Z",
            "home_team": "W73",
            "home_team_id": None,
            "away_team": "W74",
            "home_score": None,
            "away_score": None,
        },
    ]

    pulse = service.home_pulse(fixtures, now=datetime(2026, 7, 4, 12, tzinfo=timezone.utc))

    today_match = next(item for item in pulse["today_matches"] if item["match_id"] == "m3")
    assert today_match["home"]["team_name"] == "Brazil"
    assert today_match["home"]["defined"] is True
    assert today_match["away"]["placeholder"] == "Vencedor de France x Sweden"
    assert today_match["away"]["defined"] is False
    assert today_match["home_team"] == "W73", "raw fixture fields stay untouched — only home/away are added"


def test_home_discoveries_are_distinct_and_apply_minimum_samples() -> None:
    service = TheStatsApiBronzeService()
    players = [
        {"player_id": "p1", "player_name": "Eligible", "team_name": "Brazil", "minutes_played": 180, "goals": 3, "shots": 10, "xg": 2, "xg_per_shot": .2},
        {"player_id": "p2", "player_name": "Tiny sample", "team_name": "France", "minutes_played": 10, "goals": 1, "shots": 1, "xg": .9, "xg_per_shot": .9},
    ]
    teams = [
        {"team_id": "t1", "team_name": "Brazil", "played": 3, "goals_for": 6, "shots": 30, "xg": 5, "xga": 2},
        {"team_id": "t2", "team_name": "France", "played": 1, "goals_for": 3, "shots": 5, "xg": 1, "xga": .2},
    ]
    details = [
        {
            "match": {"match_id": "m1", "home_team": "Brazil", "away_team": "France", "home_score": 2, "away_score": 1, "match_date": "2026-06-20T19:00:00Z"},
            "summary": {"events": 42, "shots": 18},
            "shot_map": [{"minute": 8, "is_goal": True, "is_on_target": True}, {"minute": 88, "is_goal": True, "is_on_target": True}],
            "events": [{"type": "yellow_card"}],
            "stats_comparison": [{"metric": "expected_goals", "Brazil": 1.8, "France": 1.2}],
        }
    ]

    discoveries = service.home_discoveries(players, teams, details)

    assert set(discoveries) == {"players", "teams", "matches", "curiosities"}
    player_metric = next(item for item in discoveries["players"] if item["id"] == "goals_per_90")
    assert player_metric["eligibility"] == "Mínimo de 120 minutos e 1 gol"
    assert player_metric["title"] == "Gols por 90"
    assert player_metric["rows"][0]["value"] == 1.5
    assert [row["player_name"] for row in player_metric["rows"]] == ["Eligible"]
    on_target = next(item for item in discoveries["matches"] if item["id"] == "most_on_target")
    assert on_target["unit"] == "no alvo"
    balanced = next(item for item in discoveries["matches"] if item["id"] == "most_balanced_xg")
    assert balanced["unit"] == "diferença de xG"
    assert any(item["id"] == "goals_minus_xg" for item in discoveries["teams"])
    assert all(item["description"] for group in discoveries.values() for item in group)


def test_home_discoveries_keep_every_eligible_row_for_expanded_rankings() -> None:
    players = [
        {
            "player_id": f"p{index}",
            "player_name": f"Player {index}",
            "team_name": "Brazil",
            "minutes_played": 180,
            "goals": index + 1,
            "shots": 10,
            "xg": 2,
        }
        for index in range(12)
    ]

    discoveries = TheStatsApiBronzeService.home_discoveries(players, [], [])
    goals_per_90 = next(
        metric for metric in discoveries["players"] if metric["id"] == "goals_per_90"
    )

    assert len(goals_per_90["rows"]) == 12


def test_thestatsapi_opening_match_sample_feeds_web_contract(
    tmp_path: Path,
) -> None:
    root = _data_root(tmp_path)
    _write_json(
        root,
        "bronze/thestatsapi/world_cup/2026/fixtures/page=1/response.json",
        {
            "data": [
                {
                    "id": "mt_153637999",
                    "utc_date": "2026-06-11T19:00:00.000Z",
                    "group_label": "A",
                    "home_team": {"id": "tm_mx", "name": "Mexico"},
                    "away_team": {"id": "tm_za", "name": "South Africa"},
                    "score": {"home": 2, "away": 0},
                    "status": "finished",
                    "xg_available": True,
                },
                {
                    "id": "mt_future",
                    "utc_date": "2026-06-12T22:00:00.000Z",
                    "group_label": "A",
                    "home_team": {"id": "tm_ca", "name": "Canada"},
                    "away_team": {"id": "tm_us", "name": "United States"},
                    "score": {"home": None, "away": None},
                    "status": "scheduled",
                    "xg_available": False,
                },
                {
                    "id": "mt_round_32",
                    "utc_date": "2026-06-28T19:00:00.000Z",
                    "group_label": None,
                    "stage_name": None,
                    "matchday": 6,
                    "home_team": {"id": "tm_mx", "name": "Mexico"},
                    "away_team": {"id": "tm_placeholder", "name": "3C/3E/3F"},
                    "score": {"home": None, "away": None},
                    "status": "scheduled",
                    "xg_available": False,
                }
            ]
        },
    )
    match_root = (
        "bronze/thestatsapi/world_cup/2026/matches/"
        "match_id=mt_153637999"
    )
    _write_json(
        root,
        f"{match_root}/lineups/response.json",
        {
            "data": {
                "match_id": "mt_153637999",
                "confirmed": True,
                "home": {
                    "id": "tm_mx",
                    "name": "Mexico",
                    "formation": "4-3-3",
                    "starting_xi": [
                        {"id": "pl_1", "name": "Raul", "position": "F"}
                    ],
                    "substitutes": [],
                },
                "away": {
                    "id": "tm_za",
                    "name": "South Africa",
                    "formation": "4-2-3-1",
                    "starting_xi": [
                        {"id": "pl_2", "name": "Ronwen", "position": "G"}
                    ],
                    "substitutes": [],
                },
            }
        },
    )
    _write_json(
        root,
        f"{match_root}/match_stats/response.json",
        {
            "data": {
                "match_id": "mt_153637999",
                "overview": {
                    "expected_goals": {"all": {"home": 1.46, "away": 0.07}},
                    "total_shots": {"all": {"home": 14, "away": 5}},
                },
            }
        },
    )
    _write_json(
        root,
        f"{match_root}/player_stats/response.json",
        {
            "data": [
                {
                    "player_id": "pl_1",
                    "player_name": "Raul",
                    "team_id": "tm_mx",
                    "position": "F",
                    "started": True,
                    "minutes_played": 90,
                    "rating": 7.3,
                    "shooting": {
                        "goals": 1,
                        "total_shots": 3,
                        "expected_goals": 0.7,
                    },
                    "passing": {"assists": 0, "key_passes": 1},
                    "general": {"touches": 40},
                }
            ]
        },
    )
    _write_json(
        root,
        f"{match_root}/events/response.json",
        {
            "data": {
                "match_id": "mt_153637999",
                "coverage": "full",
                "events": [
                    {
                        "sequence": 1,
                        "minute": 9,
                        "extra_time": 0,
                        "period": "first_half",
                        "type": "goal",
                        "team": {"name": "Mexico"},
                        "player": {"name": "Raul"},
                    }
                ],
            }
        },
    )
    _write_json(
        root,
        f"{match_root}/shotmap/response.json",
        {
            "data": [
                {
                    "id": "sh_1",
                    "minute": 9,
                    "team_name": "Mexico",
                    "player_name": "Raul",
                    "x": 11.0,
                    "y": 50.0,
                    "expected_goals": 0.4,
                    "result": "goal",
                    "is_goal": True,
                    "is_on_target": True,
                },
                {
                    "id": "sh_2",
                    "minute": 20,
                    "team_name": "South Africa",
                    "player_name": "Ronwen",
                    "x": 20.0,
                    "y": 50.0,
                    "expected_goals": -0.07,
                    "result": "miss",
                    "is_goal": False,
                    "is_on_target": False,
                },
            ]
        },
    )
    _write_json(
        root,
        f"{match_root}/match_referee/response.json",
        {
            "data": {
                "match_id": "mt_153637999",
                "referee": {
                    "id": "ref_1",
                    "name": "César Arturo Ramos",
                    "country": "Mexico",
                },
                "main_referee": None,
                "officials": None,
                "assistant_referees": None,
                "fourth_official": None,
                "var": None,
                "avar": None,
            }
        },
    )
    _write_json(
        root,
        f"{match_root}/match_detail/response.json",
        {
            "data": {
                "id": "mt_153637999",
                "competition_id": "comp_6107",
                "season_id": "sn_118868",
                "utc_date": "2026-06-11T19:00:00.000Z",
                "home_team": {"id": "tm_mx", "name": "Mexico"},
                "away_team": {"id": "tm_za", "name": "South Africa"},
                "score": {"home": 2, "away": 0},
                "venue": {
                    "name": "Estadio Azteca",
                    "city": "Mexico City",
                },
                "referee": {
                    "id": "ref_1",
                    "name": "César Arturo Ramos",
                },
            }
        },
    )
    for endpoint in (
        "lineups",
        "match_stats",
        "player_stats",
        "events",
        "shotmap",
        "match_referee",
        "match_detail",
    ):
        _write_json(
            root,
            f"{match_root}/{endpoint}/metadata.json",
            {
                "endpoint_name": endpoint,
                "fetch_status": "success",
                "http_status": 200,
                "request_url": f"https://api.test/{endpoint}",
                "response_hash": endpoint,
                "fetched_at": "2026-06-24T00:00:00+00:00",
            },
        )

    client = TestClient(create_app(data_root=root, static_dir=None))

    catalog = client.get("/api/editions").json()
    edition = next(item for item in catalog["editions"] if item["year"] == 2026)
    assert edition["source"] == "TheStatsAPI"
    assert edition["capabilities"]["thestatsapi_match"] is True
    assert [menu["id"] for menu in edition["menus"]] == [
        "overview",
        "competition",
        "matches",
        "players",
        "teams",
        "profile",
    ]
    assert "thestatsapi_match" not in [menu["id"] for menu in edition["menus"]]
    assert "availability" not in [menu["id"] for menu in edition["menus"]]

    profiles = client.get("/api/editions/2026/profiles").json()
    assert profiles["available"] is True
    assert profiles["players"][0]["player_id"] == "pl_1"
    assert profiles["teams"][0]["team_id"] == "tm_mx"

    competition = client.get("/api/editions/2026/competition").json()
    assert competition["groups"][0]["name"] == "A"
    assert len(competition["groups"][0]["teams"]) == 4
    assert len(competition["groups"][0]["matches"]) == 2
    assert competition["groups"][0]["matches"][0]["match_id"] == "mt_153637999"
    assert competition["groups"][0]["teams"][2]["classification_status"] == "Possível vaga"
    assert competition["groups"][0]["teams"][3]["classification_status"] == "Fora agora"
    assert competition["best_thirds"][0]["rank"] == 1
    assert competition["best_thirds"][0]["status"] == "Dentro no momento"
    assert [round_["name"] for round_ in competition["knockout"]["rounds"]] == [
        "Fase de 32",
        "Oitavas",
        "Quartas",
        "Semifinais",
        "Disputa de 3º lugar",
        "Final",
    ]
    round_32 = competition["knockout"]["rounds"][0]["matches"][0]
    assert round_32["match_id"] == "mt_round_32"
    assert round_32["home"]["team_name"] == "Mexico"
    assert round_32["home"]["defined"] is True
    assert round_32["away"]["placeholder"] == "Melhor terceiro"
    assert round_32["away"]["defined"] is False
    assert competition["knockout"]["rounds"][2]["matches"] == []

    home = client.get("/api/editions/2026/overview").json()
    assert "groups" not in home
    assert home["recent_matches"][0]["match_id"] == "mt_153637999"
    assert home["upcoming_matches"][0]["match_id"] in {
        "mt_future",
        "mt_round_32",
    }
    assert set(home["leaders"]) == {"players", "teams", "matches"}

    matches = client.get("/api/editions/2026/matches").json()
    assert matches["items"][0]["match_id"] == "mt_153637999"

    payload = client.get("/api/editions/2026/matches/mt_153637999").json()
    assert payload["available"] is True
    assert payload["match"]["home_team"] == "Mexico"
    assert payload["match"]["stadium"] == "Estadio Azteca"
    assert payload["match"]["venue"] == "Estadio Azteca"
    assert payload["match"]["venue_city"] == "Mexico City"
    assert payload["match"]["referee"] == "César Arturo Ramos"
    assert payload["match"]["main_referee"] is None
    assert payload["match"]["officials"] is None
    assert payload["match"]["assistant_referees"] is None
    assert payload["match"]["fourth_official"] is None
    assert payload["match"]["var"] is None
    assert payload["match"]["avar"] is None
    assert payload["match"]["goals"][0]["player_name"] == "Raul"
    assert payload["match"]["goals"][0]["minute"] == 9
    assert payload["summary"]["events"] == 1
    assert payload["shot_map"][0]["is_goal"] is True
    assert payload["shot_map"][1]["xg"] == 0
    assert all(row["cumulative_xg"] >= 0 for row in payload["xg_flow"])
    assert payload["stats_comparison"][0]["Mexico"] == 1.46
    assert payload["comparison_bars"][0]["metric"] == "expected_goals"
    assert payload["comparison_bars"][0]["home_pct"] == 100.0
    assert payload["match_story"][0] == "Mexico controlou a criação: 1,46 xG contra 0,07."
    assert payload["match_story"][1] == "A equipe também finalizou mais: 14 a 5."
    assert payload["player_impacts"][0]["player_name"] == "Raul"
    assert payload["player_impacts"][0]["radar"][0]["axis"] == "Ataque"
    assert payload["players"][0]["impact_score"] > 0
    assert payload["players"][0]["macroposition"] == "Centroavante"
    assert payload["players"][0]["api_position_group"] == "Atacante"
    assert payload["players"][0]["inferred_role"] == "Centroavante"
    assert payload["players"][0]["resolved_position"] == "Centroavante"
    assert payload["players"][0]["role_source"] == "statistics_profile"
    assert payload["players"][0]["role_confidence"] == "medium"
    assert payload["players"][0]["radar_dimensions"]["Ataque"]["score"] is not None
    assert payload["players"][0]["radar_dimensions"]["Progressão"]["score"] is None
    assert all(axis["axis"] != "Progressão" for axis in payload["players"][0]["radar"])
    assert payload["players"][0]["assists"] == 0
    assert payload["players"][0]["shots_on_target"] is None
    assert payload["players"][0]["player_shots"][0]["shot_id"] == "sh_1"
    # The minute-9 goal is covered by player_shots (with xG/body-part detail); it must not also
    # show up in player_events, or the player's unified timeline would show it twice.
    assert payload["players"][0]["player_events"] == []
    assert payload["players"][0]["opponent_name"] == "South Africa"
    assert payload["xg_flow"][-1]["minute"] == 90
    assert payload["xg_flow"][-1]["is_terminal"] is True

    opening_payload = client.get("/api/editions/2026/thestatsapi-match").json()
    assert opening_payload["match"]["match_id"] == "mt_153637999"

    player = client.get("/api/editions/2026/players/pl_1").json()
    assert player["available"] is True
    assert player["player"]["player_name"] == "Raul"
    assert player["summary"]["goals"] == 1

    team = client.get("/api/editions/2026/teams/tm_mx").json()
    assert team["available"] is True
    assert team["team"]["team_name"] == "Mexico"
    assert team["team"]["xg"] == 1.46


def test_thestatsapi_official_standings_take_precedence_over_fixture_projection(
    tmp_path: Path,
) -> None:
    root = _data_root(tmp_path)
    _write_json(
        root,
        "bronze/thestatsapi/world_cup/2026/standings/response.json",
        {
            "data": [
                {
                    "team": {"id": "tm_mx", "name": "Mexico"},
                    "group_label": "A",
                    "position": 1,
                    "matches_played": 3,
                    "wins": 2,
                    "draws": 1,
                    "losses": 0,
                    "goals_for": 6,
                    "goals_against": 2,
                    "goal_difference": 4,
                    "points": 7,
                },
                {
                    "team": {"id": "tm_za", "name": "South Africa"},
                    "group_label": None,
                    "position": 49,
                    "matches_played": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "goals_for": 0,
                    "goals_against": 0,
                    "goal_difference": 0,
                    "points": 0,
                },
            ]
        },
    )
    _write_json(
        root,
        "bronze/thestatsapi/world_cup/2026/fixtures/page=1/response.json",
        {
            "data": [
                {
                    "id": "mt_1",
                    "group_label": "A",
                    "status": "scheduled",
                    "home_team": {"id": "tm_mx", "name": "Mexico"},
                    "away_team": {"id": "tm_za", "name": "South Africa"},
                }
            ]
        },
    )

    payload = TestClient(create_app(data_root=root, static_dir=None)).get(
        "/api/editions/2026/competition"
    ).json()

    assert [group["name"] for group in payload["groups"]] == ["A"]
    assert payload["groups"][0]["teams"] == [
        {
            "team_id": "tm_mx",
            "team_name": "Mexico",
            "group_name": "A",
            "played": 3,
            "wins": 2,
            "draws": 1,
            "losses": 0,
            "goals_for": 6,
            "goals_against": 2,
            "goal_difference": 4,
            "points": 7,
            "position": 1,
            "classification_status": "Classificando",
        }
    ]
    assert payload["groups"][0]["matches"][0]["match_id"] == "mt_1"
