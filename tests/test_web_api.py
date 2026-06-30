from __future__ import annotations

from pathlib import Path
import json

import pandas as pd
from fastapi.testclient import TestClient

from webapp.catalog import DEFAULT_EDITION
from webapp.main import create_app


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
        "Possível vaga",
        "Fora agora",
    ):
        assert f'"{label}"' in render
    assert 'onAction: () => routeTo("teams", teamId)' in render
    assert 'onAction: () => routeTo("matches", match.match_id)' in render
    assert 'aria-selected' in render
    assert "competition-group-table" in styles
    assert "best-thirds-table" in styles
    assert "knockout-board" in styles
    assert "competition-row-qualified" in styles
    assert "competition-row-third" in styles
    assert "competition-row-out" in styles


def test_competition_uses_expandable_groups_tooltips_and_quick_views() -> None:
    app_js = (
        Path(__file__).parents[1] / "webapp/static/app.js"
    ).read_text(encoding="utf-8")
    competition = app_js[
        app_js.index("const GROUP_STAT_DEFINITIONS"):
        app_js.index("function renderPlayerDetail")
    ]

    assert 'node("details", { class: "competition-group-games" }' in competition
    assert 'text: "Ver jogos do grupo"' in competition
    assert "function teamGroupStatBreakdown" in competition
    assert "function showStatPopover" in competition
    assert '"GP": "gols pró, total de gols marcados."' in competition
    assert '"GC": "gols contra, total de gols sofridos."' in competition
    assert '"SG": "saldo de gols, gols pró menos gols contra."' in competition
    assert '"Pts": "pontos conquistados."' in competition
    assert "function openTeamQuickView" in competition
    assert "function openMatchQuickView" in competition
    assert 'actionLabel: "Ver seleção completa"' in competition
    assert 'actionLabel: "Ver partida completa"' in competition
    render = competition[
        competition.index("function renderCompetition"):
    ]
    assert 'section("Estatísticas gerais"' not in render


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


def test_2026_theme_uses_selective_neon_broadcast_tokens() -> None:
    root = Path(__file__).parents[1] / "webapp/static"
    styles = (root / "styles.css").read_text(encoding="utf-8")
    index = (root / "index.html").read_text(encoding="utf-8")

    for token in (
        "--wc26-bg: #070b1a",
        "--wc26-surface: #0d1328",
        "--wc26-border: #243a66",
        "--wc26-neon-cyan: #39dfff",
        "--wc26-neon-mint: #52ffd2",
        "--wc26-electric-blue: #2f6bff",
        "--wc26-glow-cyan:",
        "--wc26-glow-green:",
    ):
        assert token in styles
    assert 'content="#070b1a"' in index
    assert 'body[data-skin="2026"] .match-score-card' in styles
    assert 'body[data-skin="2026"] .impact-card' in styles
    assert 'body[data-skin="2026"] .player-metrics-table tbody tr.is-selected' in styles
    assert 'body[data-skin="2026"] .event-goal .event-icon' in styles
    assert "@media (prefers-reduced-motion: reduce)" in styles


def test_2026_skin_uses_neon_as_a_controlled_visual_accent() -> None:
    styles = (
        Path(__file__).parents[1] / "webapp/static/styles.css"
    ).read_text(encoding="utf-8")
    skin = styles[
        styles.index('body[data-skin="2026"] {'):
        styles.index("@media (max-width: 900px)")
    ]

    for token in (
        "--wc26-bg: #070b1a;",
        "--wc26-surface: #0d1328;",
        "--wc26-neon-cyan: #39dfff;",
        "--wc26-neon-mint: #52ffd2;",
        "--wc26-neon-yellow: #f8ff3d;",
        "--wc26-neon-magenta: #ff4fd8;",
        "--wc26-glow-cyan:",
        "--wc26-gradient-score:",
    ):
        assert token in skin

    assert 'body[data-skin="2026"] .nav-link[aria-current="page"]' in skin
    assert 'body[data-skin="2026"] .score' in skin
    assert 'body[data-skin="2026"] .impact-inline-score' in skin
    assert 'body[data-skin="2026"] .xg-point.is-goal' in skin
    assert 'body[data-skin="2026"] .event-var .event-icon' in skin
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
    assert "por 90" not in app_js.lower()

    modal = app_js[
        app_js.index("function playerPerformanceStory"):
        app_js.index("function playerExplorer")
    ]
    assert "function playerContextComparisons" in modal
    assert 'text: "Destaques da atuação"' in modal
    assert '"Drible e condução"' not in modal
    assert "Cobertura" not in modal
    assert "Confiança" not in modal


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
    ]
    assert "thestatsapi_match" not in [menu["id"] for menu in edition["menus"]]
    assert "availability" not in [menu["id"] for menu in edition["menus"]]

    competition = client.get("/api/editions/2026/competition").json()
    assert competition["groups"][0]["name"] == "A"
    assert len(competition["groups"][0]["teams"]) == 4
    assert len(competition["groups"][0]["matches"]) == 2
    assert competition["groups"][0]["matches"][0]["match_id"] == "mt_153637999"
    assert competition["groups"][0]["teams"][2]["classification_status"] == "Possível vaga"
    assert competition["groups"][0]["teams"][3]["classification_status"] == "Fora agora"
    assert competition["best_thirds"][0]["rank"] == 1
    assert competition["best_thirds"][0]["status"] == "Classificando"
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
    assert payload["match_story"][0] == "Mexico controlou a criação: 1.46 xG contra 0.07."
    assert payload["match_story"][1] == "A equipe também finalizou mais: 14 a 5."
    assert payload["player_impacts"][0]["player_name"] == "Raul"
    assert payload["player_impacts"][0]["radar"][0]["axis"] == "Ataque"
    assert payload["players"][0]["impact_score"] > 0
    assert payload["players"][0]["macroposition"] == "Centroavante"
    assert payload["players"][0]["radar_dimensions"]["Ataque"]["score"] is not None
    assert payload["players"][0]["radar_dimensions"]["Progressão"]["score"] is None
    assert all(axis["axis"] != "Progressão" for axis in payload["players"][0]["radar"])
    assert payload["players"][0]["assists"] == 0
    assert payload["players"][0]["shots_on_target"] is None
    assert payload["players"][0]["player_shots"][0]["shot_id"] == "sh_1"
    assert payload["players"][0]["player_events"][0]["type"] == "goal"
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
