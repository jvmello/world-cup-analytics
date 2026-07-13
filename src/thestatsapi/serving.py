from __future__ import annotations

import argparse
import gc
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .config import WORLD_CUP_2026_EDITION, database_url_from_env
from webapp.thestatsapi_service import TheStatsApiBronzeService, json_safe, number


GOLD_TABLES = (
    "matches",
    "match_players",
    "match_shots",
    "players_agg",
    "teams_agg",
    "standings",
    "edition_summary",
    "api_payloads",
)


SCHEMA_STATEMENTS = (
    "CREATE SCHEMA IF NOT EXISTS gold",
    """
    CREATE TABLE IF NOT EXISTS gold.matches (
        edition_year INTEGER NOT NULL,
        match_id TEXT NOT NULL,
        match_date TIMESTAMPTZ,
        stage TEXT,
        group_name TEXT,
        status TEXT,
        venue_name TEXT,
        venue_city TEXT,
        referee TEXT,
        home_team_id TEXT,
        home_team_name TEXT,
        away_team_id TEXT,
        away_team_name TEXT,
        home_score NUMERIC,
        away_score NUMERIC,
        penalty_home_score NUMERIC,
        penalty_away_score NUMERIC,
        winner_name TEXT,
        decided_by TEXT,
        home_xg NUMERIC,
        away_xg NUMERIC,
        home_shots INTEGER,
        away_shots INTEGER,
        detail JSONB NOT NULL DEFAULT '{}'::jsonb,
        built_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (edition_year, match_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gold.match_players (
        edition_year INTEGER NOT NULL,
        match_id TEXT NOT NULL,
        player_id TEXT NOT NULL,
        team_id TEXT,
        team_name TEXT,
        player_name TEXT,
        position TEXT,
        resolved_position TEXT,
        benchmark_position TEXT,
        scope TEXT NOT NULL DEFAULT 'match',
        minutes_played NUMERIC,
        goals NUMERIC,
        assists NUMERIC,
        xg NUMERIC,
        xa NUMERIC,
        shots NUMERIC,
        rating NUMERIC,
        impact_score NUMERIC,
        stats JSONB NOT NULL DEFAULT '{}'::jsonb,
        built_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (edition_year, match_id, player_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gold.match_shots (
        edition_year INTEGER NOT NULL,
        match_id TEXT NOT NULL,
        shot_id TEXT NOT NULL,
        team_id TEXT,
        team_name TEXT,
        player_id TEXT,
        player_name TEXT,
        minute NUMERIC,
        x NUMERIC,
        y NUMERIC,
        xg NUMERIC,
        body_part TEXT,
        shot_type TEXT,
        shot_outcome TEXT,
        is_goal BOOLEAN,
        is_on_target BOOLEAN,
        is_penalty BOOLEAN,
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        built_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (edition_year, match_id, shot_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gold.players_agg (
        edition_year INTEGER NOT NULL,
        scope TEXT NOT NULL,
        player_id TEXT NOT NULL,
        player_name TEXT,
        team_id TEXT,
        team_name TEXT,
        position TEXT,
        resolved_position TEXT,
        benchmark_position TEXT,
        games INTEGER,
        minutes_played NUMERIC,
        goals NUMERIC,
        assists NUMERIC,
        xg NUMERIC,
        xa NUMERIC,
        shots NUMERIC,
        rating NUMERIC,
        impact_score NUMERIC,
        radar JSONB NOT NULL DEFAULT '[]'::jsonb,
        radar_dimensions JSONB NOT NULL DEFAULT '{}'::jsonb,
        benchmarks JSONB NOT NULL DEFAULT '{}'::jsonb,
        stats JSONB NOT NULL DEFAULT '{}'::jsonb,
        built_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (edition_year, scope, player_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gold.teams_agg (
        edition_year INTEGER NOT NULL,
        team_id TEXT NOT NULL,
        team_name TEXT,
        group_name TEXT,
        played INTEGER,
        wins INTEGER,
        draws INTEGER,
        losses INTEGER,
        points INTEGER,
        goals_for INTEGER,
        goals_against INTEGER,
        goal_difference INTEGER,
        xg NUMERIC,
        xga NUMERIC,
        xg_difference NUMERIC,
        shots INTEGER,
        stats JSONB NOT NULL DEFAULT '{}'::jsonb,
        built_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (edition_year, team_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gold.standings (
        edition_year INTEGER NOT NULL,
        group_name TEXT NOT NULL,
        position INTEGER NOT NULL,
        team_id TEXT NOT NULL,
        team_name TEXT,
        played INTEGER,
        wins INTEGER,
        draws INTEGER,
        losses INTEGER,
        points INTEGER,
        goals_for INTEGER,
        goals_against INTEGER,
        goal_difference INTEGER,
        classification_status TEXT,
        row JSONB NOT NULL DEFAULT '{}'::jsonb,
        built_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (edition_year, group_name, position, team_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gold.edition_summary (
        edition_year INTEGER PRIMARY KEY,
        matches INTEGER,
        finished INTEGER,
        teams INTEGER,
        players INTEGER,
        goals INTEGER,
        shots INTEGER,
        xg NUMERIC,
        summary JSONB NOT NULL DEFAULT '{}'::jsonb,
        built_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gold.api_payloads (
        edition_year INTEGER NOT NULL,
        endpoint TEXT NOT NULL,
        entity_id TEXT NOT NULL DEFAULT '',
        scope TEXT NOT NULL DEFAULT '',
        payload JSONB NOT NULL,
        built_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (edition_year, endpoint, entity_id, scope)
    )
    """,
)

TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "matches": (
        "edition_year", "match_id", "match_date", "stage", "group_name", "status",
        "venue_name", "venue_city", "referee", "home_team_id", "home_team_name",
        "away_team_id", "away_team_name", "home_score", "away_score",
        "penalty_home_score", "penalty_away_score", "winner_name", "decided_by",
        "home_xg", "away_xg", "home_shots", "away_shots", "detail",
    ),
    "match_players": (
        "edition_year", "match_id", "player_id", "team_id", "team_name",
        "player_name", "position", "resolved_position", "benchmark_position",
        "scope", "minutes_played", "goals", "assists", "xg", "xa", "shots",
        "rating", "impact_score", "stats",
    ),
    "match_shots": (
        "edition_year", "match_id", "shot_id", "team_id", "team_name",
        "player_id", "player_name", "minute", "x", "y", "xg", "body_part",
        "shot_type", "shot_outcome", "is_goal", "is_on_target", "is_penalty",
        "payload",
    ),
    "players_agg": (
        "edition_year", "scope", "player_id", "player_name", "team_id",
        "team_name", "position", "resolved_position", "benchmark_position",
        "games", "minutes_played", "goals", "assists", "xg", "xa", "shots",
        "rating", "impact_score", "radar", "radar_dimensions", "benchmarks",
        "stats",
    ),
    "teams_agg": (
        "edition_year", "team_id", "team_name", "group_name", "played", "wins",
        "draws", "losses", "points", "goals_for", "goals_against",
        "goal_difference", "xg", "xga", "xg_difference", "shots", "stats",
    ),
    "standings": (
        "edition_year", "group_name", "position", "team_id", "team_name",
        "played", "wins", "draws", "losses", "points", "goals_for",
        "goals_against", "goal_difference", "classification_status", "row",
    ),
    "edition_summary": (
        "edition_year", "matches", "finished", "teams", "players", "goals",
        "shots", "xg", "summary",
    ),
    "api_payloads": (
        "edition_year", "endpoint", "entity_id", "scope", "payload",
    ),
}


@dataclass(frozen=True)
class GoldServingBuild:
    year: int
    matches: list[dict[str, Any]]
    match_players: list[dict[str, Any]]
    match_shots: list[dict[str, Any]]
    players_agg: list[dict[str, Any]]
    teams_agg: list[dict[str, Any]]
    standings: list[dict[str, Any]]
    edition_summary: list[dict[str, Any]]
    api_payloads: list[dict[str, Any]]

    @property
    def counts(self) -> dict[str, int]:
        return {table: len(getattr(self, table)) for table in GOLD_TABLES}

    def rows_for(self, table: str) -> list[dict[str, Any]]:
        if table not in GOLD_TABLES:
            raise KeyError(f"Unknown gold table: {table}")
        return getattr(self, table)


def gold_schema_sql() -> str:
    return ";\n\n".join(statement.strip() for statement in SCHEMA_STATEMENTS) + ";\n"


def build_gold_substrate(
    year: int = WORLD_CUP_2026_EDITION,
    *,
    data_root: Path | str = Path("data"),
    service: TheStatsApiBronzeService | None = None,
    include_api_payloads: bool = True,
) -> GoldServingBuild:
    service = service or TheStatsApiBronzeService(data_root)
    details = service._all_match_details(year)
    details_by_id = {
        str(detail["match"].get("match_id")): detail
        for detail in details
        if detail.get("match", {}).get("match_id")
    }
    fixtures = service.fixtures(year)
    matches = _match_rows(service, year, fixtures, details_by_id)
    standings_by_group = service.standings_by_group(year)
    standings = _standing_rows(year, standings_by_group)
    teams = service._curate_teams(service.team_rows(year, standings_by_group, details))
    players_agg = _player_scope_rows(service, year, details)
    summary = service.competition_summary(matches, players_agg, teams)
    substrate = {
        "matches": matches,
        "match_players": _match_player_rows(year, details),
        "match_shots": _match_shot_rows(year, details),
        "players_agg": players_agg,
        "teams_agg": _team_rows(year, teams),
        "standings": standings,
        "edition_summary": [_edition_summary_row(year, summary)],
    }
    return GoldServingBuild(
        year=year,
        api_payloads=_api_payload_rows(
            service,
            year,
            details=details,
            teams=teams,
            players_agg=players_agg,
            substrate=substrate,
        ) if include_api_payloads else [],
        **substrate,
    )


def rebuild_gold_serving(
    year: int = WORLD_CUP_2026_EDITION,
    *,
    data_root: Path | str = Path("data"),
    database_url: str | None = None,
) -> GoldServingBuild:
    service = TheStatsApiBronzeService(data_root)
    build = build_gold_substrate(
        year,
        data_root=data_root,
        service=service,
        include_api_payloads=False,
    )
    counts = GoldServingRepository(database_url).replace_year(
        build,
        api_payload_rows=_api_payload_rows_from_bronze(service, year),
    )
    # replace_year frees the substrate lists as it stages them, so the reported counts
    # come from what was actually inserted.
    return GoldServingBuild(
        year=build.year,
        **{table: [{} for _ in range(counts.get(table, 0))] for table in GOLD_TABLES},
    )


class GoldServingRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or database_url_from_env()
        if not self.database_url.startswith("postgres"):
            raise RuntimeError(
                "TheStatsAPI serving gold requires PostgreSQL. Configure "
                "THESTATSAPI_DATABASE_URL or POSTGRES_* with a postgresql:// URL."
            )

    def replace_year(
        self,
        build: GoldServingBuild,
        *,
        api_payload_rows: Iterable[dict[str, Any]] | None = None,
    ) -> dict[str, int]:
        import psycopg2
        import psycopg2.extras

        counts: dict[str, int] = {}
        with psycopg2.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                for statement in SCHEMA_STATEMENTS:
                    cur.execute(statement)
                for table in GOLD_TABLES:
                    staging = f"_staging_{table}"
                    cur.execute(f"DROP TABLE IF EXISTS gold.{staging}")
                    cur.execute(
                        f"CREATE TABLE gold.{staging} "
                        f"(LIKE gold.{table} INCLUDING DEFAULTS INCLUDING CONSTRAINTS)"
                    )
                    rows = api_payload_rows if table == "api_payloads" and api_payload_rows is not None else build.rows_for(table)
                    counts[table] = _insert_rows(cur, staging, rows, psycopg2.extras)
                    if table != "api_payloads":
                        # Staged in PostgreSQL — free the in-memory rows before the (heavy)
                        # api_payloads generator runs, keeping the peak footprint to one
                        # phase at a time on small hosts.
                        build.rows_for(table).clear()
                for table in GOLD_TABLES:
                    staging = f"_staging_{table}"
                    cur.execute(f"DELETE FROM gold.{table} WHERE edition_year = %s", (build.year,))
                    columns = ", ".join(TABLE_COLUMNS[table])
                    cur.execute(
                        f"INSERT INTO gold.{table} ({columns}) "
                        f"SELECT {columns} FROM gold.{staging} WHERE edition_year = %s",
                        (build.year,),
                    )
                    cur.execute(f"DROP TABLE gold.{staging}")
        return counts


def _insert_rows(
    cur: Any,
    table: str,
    rows: Iterable[dict[str, Any]],
    extras: Any,
) -> int:
    base_table = table.removeprefix("_staging_")
    columns = TABLE_COLUMNS[base_table]
    template = "(" + ", ".join(["%s"] * len(columns)) + ")"
    sql = f"INSERT INTO gold.{table} ({', '.join(columns)}) VALUES %s"
    # Tables carrying multi-MB JSONB rows (full match detail / endpoint payloads) go in
    # tiny batches: a 100-row statement of those buffers hundreds of MB on both the client
    # and the PostgreSQL side, which OOM-kills the build on small hosts.
    chunk_size = 5 if base_table in {"api_payloads", "matches"} else 100
    count = 0
    chunk: list[dict[str, Any]] = []
    for row in rows:
        chunk.append(row)
        if len(chunk) < chunk_size:
            continue
        values = [
            tuple(_pg_value(row.get(column), extras) for column in columns)
            for row in chunk
        ]
        extras.execute_values(cur, sql, values, template=template, page_size=len(values))
        count += len(chunk)
        chunk = []
        if base_table == "api_payloads":
            gc.collect()
    if chunk:
        values = [
            tuple(_pg_value(row.get(column), extras) for column in columns)
            for row in chunk
        ]
        extras.execute_values(cur, sql, values, template=template, page_size=len(values))
        count += len(chunk)
        if base_table == "api_payloads":
            gc.collect()
    return count


def _pg_value(value: Any, extras: Any) -> Any:
    if isinstance(value, (dict, list)):
        return extras.Json(json_safe(value))
    return value


def _match_rows(
    service: TheStatsApiBronzeService,
    year: int,
    fixtures: list[dict[str, Any]],
    details_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    seen: set[str] = set()
    for fixture in sorted(fixtures, key=lambda item: str(item.get("utc_date") or "")):
        summary = service._match_summary(fixture, {})
        match_id = str(summary.get("match_id"))
        detail = details_by_id.get(match_id)
        if detail:
            summary.update(service._match_derived(detail))
        rows.append(_match_row(year, summary, detail))
        seen.add(match_id)
    for match_id, detail in sorted(details_by_id.items()):
        if match_id in seen:
            continue
        rows.append(_match_row(year, detail["match"], detail))
    return rows


def _match_row(
    year: int,
    match: dict[str, Any],
    detail: dict[str, Any] | None,
) -> dict[str, Any]:
    metrics = {
        str(row.get("metric")): row
        for row in (detail or {}).get("stats_comparison", [])
    }
    home = match.get("home_team")
    away = match.get("away_team")
    xg = metrics.get("expected_goals") or {}
    shots = metrics.get("total_shots") or {}
    return {
        "edition_year": year,
        "match_id": str(match.get("match_id")),
        "match_date": match.get("match_date"),
        "stage": match.get("stage"),
        "group_name": match.get("group_name"),
        "status": match.get("status"),
        "venue_name": match.get("venue") or match.get("stadium"),
        "venue_city": match.get("venue_city"),
        "referee": match.get("referee") or match.get("main_referee"),
        "home_team_id": match.get("home_team_id"),
        "home_team_name": home,
        "away_team_id": match.get("away_team_id"),
        "away_team_name": away,
        "home_score": number(match.get("home_score")),
        "away_score": number(match.get("away_score")),
        "penalty_home_score": number(match.get("penalty_home_score")),
        "penalty_away_score": number(match.get("penalty_away_score")),
        "winner_name": match.get("winner_name"),
        "decided_by": match.get("decided_by"),
        "home_xg": number(xg.get(home)),
        "away_xg": number(xg.get(away)),
        "home_shots": number(shots.get(home)),
        "away_shots": number(shots.get(away)),
        "detail": {
            "summary": (detail or {}).get("summary"),
            "stats_comparison": (detail or {}).get("stats_comparison", []),
            "comparison_bars": (detail or {}).get("comparison_bars", []),
            "match_story": (detail or {}).get("match_story", []),
            "lineups": (detail or {}).get("lineups", {}),
            "events": (detail or {}).get("events", []),
            "team_summary": (detail or {}).get("team_summary", []),
            "xg_flow": (detail or {}).get("xg_flow", []),
        },
    }


def _match_player_rows(year: int, details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for detail in details:
        match_id = str(detail["match"].get("match_id"))
        for index, player in enumerate(detail.get("players", []), start=1):
            player_id = str(player.get("player_id") or f"{match_id}:player:{index}")
            rows.append(
                {
                    "edition_year": year,
                    "match_id": match_id,
                    "player_id": player_id,
                    "team_id": player.get("team_id"),
                    "team_name": player.get("team_name"),
                    "player_name": player.get("player_name"),
                    "position": player.get("position"),
                    "resolved_position": player.get("resolved_position"),
                    "benchmark_position": player.get("benchmark_position"),
                    "scope": "match",
                    "minutes_played": number(player.get("minutes_played")),
                    "goals": number(player.get("goals")),
                    "assists": number(player.get("assists")),
                    "xg": number(player.get("xg")),
                    "xa": number(player.get("xa")),
                    "shots": number(player.get("shots")),
                    "rating": number(player.get("rating")),
                    "impact_score": number(player.get("impact_score")),
                    "stats": player,
                }
            )
    return rows


def _match_shot_rows(year: int, details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for detail in details:
        match_id = str(detail["match"].get("match_id"))
        for index, shot in enumerate(detail.get("shot_map", []), start=1):
            rows.append(
                {
                    "edition_year": year,
                    "match_id": match_id,
                    "shot_id": str(shot.get("shot_id") or f"{match_id}:shot:{index}"),
                    "team_id": shot.get("team_id"),
                    "team_name": shot.get("team_name"),
                    "player_id": shot.get("player_id"),
                    "player_name": shot.get("player_name"),
                    "minute": number(shot.get("minute")),
                    "x": number(shot.get("x")),
                    "y": number(shot.get("y")),
                    "xg": number(shot.get("xg")),
                    "body_part": shot.get("body_part"),
                    "shot_type": shot.get("shot_type"),
                    "shot_outcome": shot.get("shot_outcome"),
                    "is_goal": shot.get("is_goal"),
                    "is_on_target": shot.get("is_on_target"),
                    "is_penalty": shot.get("is_penalty"),
                    "payload": shot,
                }
            )
    return rows


def _player_scope_rows(
    service: TheStatsApiBronzeService,
    year: int,
    details: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    scopes = {
        "all": details,
        "group_stage": [detail for detail in details if _is_group_match(detail["match"])],
        "knockout": [detail for detail in details if not _is_group_match(detail["match"])],
    }
    for scope, scoped_details in scopes.items():
        if not scoped_details:
            continue
        players = service._aggregate_player_analytics(
            service._aggregate_players(scoped_details)
        )
        rows.extend(_player_rows(year, scope, players))
    return rows


def _player_rows(year: int, scope: str, players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for player in players:
        player_id = player.get("player_id")
        if not player_id:
            continue
        rows.append(
            {
                "edition_year": year,
                "scope": scope,
                "player_id": str(player_id),
                "player_name": player.get("player_name"),
                "team_id": player.get("team_id"),
                "team_name": player.get("team_name"),
                "position": player.get("position"),
                "resolved_position": player.get("resolved_position"),
                "benchmark_position": player.get("benchmark_position"),
                "games": number(player.get("games")),
                "minutes_played": number(player.get("minutes_played")),
                "goals": number(player.get("goals")),
                "assists": number(player.get("assists")),
                "xg": number(player.get("xg")),
                "xa": number(player.get("xa")),
                "shots": number(player.get("shots")),
                "rating": number(player.get("rating")),
                "impact_score": number(player.get("impact_score") or player.get("profile_score")),
                "radar": player.get("radar") or [],
                "radar_dimensions": player.get("radar_dimensions") or {},
                "benchmarks": player.get("benchmarks") or {},
                "stats": player,
            }
        )
    return rows


def _team_rows(year: int, teams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for team in teams:
        team_id = team.get("team_id")
        if not team_id:
            continue
        rows.append(
            {
                "edition_year": year,
                "team_id": str(team_id),
                "team_name": team.get("team_name"),
                "group_name": team.get("group_name"),
                "played": number(team.get("played")),
                "wins": number(team.get("wins")),
                "draws": number(team.get("draws")),
                "losses": number(team.get("losses")),
                "points": number(team.get("points")),
                "goals_for": number(team.get("goals_for")),
                "goals_against": number(team.get("goals_against")),
                "goal_difference": number(team.get("goal_difference")),
                "xg": number(team.get("xg")),
                "xga": number(team.get("xga")),
                "xg_difference": number(team.get("xg_difference")),
                "shots": number(team.get("shots")),
                "stats": team,
            }
        )
    return rows


def _standing_rows(
    year: int,
    standings_by_group: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = []
    for group_name, group_rows in standings_by_group.items():
        for index, row in enumerate(group_rows, start=1):
            position = number(row.get("position")) or index
            team_id = row.get("team_id") or f"{group_name}:{position}:{row.get('team_name')}"
            rows.append(
                {
                    "edition_year": year,
                    "group_name": str(group_name),
                    "position": int(position),
                    "team_id": str(team_id),
                    "team_name": row.get("team_name"),
                    "played": number(row.get("played")),
                    "wins": number(row.get("wins")),
                    "draws": number(row.get("draws")),
                    "losses": number(row.get("losses")),
                    "points": number(row.get("points")),
                    "goals_for": number(row.get("goals_for")),
                    "goals_against": number(row.get("goals_against")),
                    "goal_difference": number(row.get("goal_difference")),
                    "classification_status": row.get("classification_status"),
                    "row": row,
                }
            )
    return rows


def _edition_summary_row(year: int, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "edition_year": year,
        "matches": number(summary.get("matches")),
        "finished": number(summary.get("finished")),
        "teams": number(summary.get("teams")),
        "players": number(summary.get("players")),
        "goals": number(summary.get("goals")),
        "shots": number(summary.get("shots")),
        "xg": number(summary.get("xg")),
        "summary": summary,
    }


def _api_payload_rows(
    service: TheStatsApiBronzeService,
    year: int,
    *,
    details: list[dict[str, Any]],
    teams: list[dict[str, Any]],
    players_agg: list[dict[str, Any]],
    substrate: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    return list(
        _iter_api_payload_rows(
            service,
            year,
            details=details,
            teams=teams,
            players_agg=players_agg,
            substrate=substrate,
        )
    )


def _api_payload_rows_from_bronze(
    service: TheStatsApiBronzeService,
    year: int,
) -> Iterable[dict[str, Any]]:
    def add(
        endpoint: str,
        payload: dict[str, Any],
        *,
        entity_id: Any = "",
        scope: str = "",
    ) -> dict[str, Any]:
        return {
            "edition_year": year,
            "endpoint": endpoint,
            "entity_id": str(entity_id or ""),
            "scope": scope,
            "payload": json_safe(payload),
        }

    yield add("overview", service.overview(year))
    yield add("competition", service.competition(year))
    yield add("matches", service.matches(year))
    yield add("teams", service.teams(year))
    yield add("players", service.players(year))
    yield add("profiles", service.profiles(year))
    yield add("shots", service.shots(year))
    yield add("thestatsapi_match", service.opening_match(year))
    data_service = _legacy_data_service(service.data_root)
    yield add("official_metrics", data_service.official_metrics(year))
    yield add("availability", data_service.availability(year))

    details = service._all_match_details(year)
    standings_by_group = service.standings_by_group(year)
    teams = service._curate_teams(service.team_rows(year, standings_by_group, details))
    players_agg = _player_scope_rows(service, year, details)
    substrate = {
        "match_players": _match_player_rows(year, details),
    }
    yield from _iter_api_payload_rows(
        service,
        year,
        details=details,
        teams=teams,
        players_agg=players_agg,
        substrate=substrate,
        include_collection_payloads=False,
    )


def _iter_api_payload_rows(
    service: TheStatsApiBronzeService,
    year: int,
    *,
    details: list[dict[str, Any]],
    teams: list[dict[str, Any]],
    players_agg: list[dict[str, Any]],
    substrate: dict[str, list[dict[str, Any]]],
    include_collection_payloads: bool = True,
) -> Iterable[dict[str, Any]]:

    def add(
        endpoint: str,
        payload: dict[str, Any],
        *,
        entity_id: Any = "",
        scope: str = "",
    ) -> dict[str, Any]:
        return {
            "edition_year": year,
            "endpoint": endpoint,
            "entity_id": str(entity_id or ""),
            "scope": scope,
            "payload": json_safe(payload),
        }

    if include_collection_payloads:
        yield add("overview", service.overview(year))
        yield add("competition", service.competition(year))
        yield add("matches", service.matches(year))
        yield add("teams", service.teams(year))
        yield add("players", service.players(year))
        yield add("profiles", service.profiles(year))
        yield add("shots", service.shots(year))
        yield add("thestatsapi_match", service.opening_match(year))
        data_service = _legacy_data_service(service.data_root)
        yield add("official_metrics", data_service.official_metrics(year))
        yield add("availability", data_service.availability(year))

    bundled_match_ids = set()
    for detail in details:
        match_id = detail.get("match", {}).get("match_id")
        if match_id:
            bundled_match_ids.add(match_id)
            yield add("match_detail", detail, entity_id=match_id)

    # Scheduled fixtures with no bundle yet still get a match_detail row — a lightweight
    # pre-match comparison instead of the endpoint being silently missing from gold.
    teams_by_id = {str(team.get("team_id")): team for team in teams if team.get("team_id")}
    for fixture in service.fixtures(year):
        match = service._match_summary(fixture, {})
        match_id = match.get("match_id")
        if not match_id or match_id in bundled_match_ids:
            continue
        prognosis = service._build_fixture_prognosis(
            year, match, teams_by_id.get(match.get("home_team_id")), teams_by_id.get(match.get("away_team_id"))
        )
        if prognosis:
            yield add("match_detail", prognosis, entity_id=match_id)

    team_ids = sorted({str(team.get("team_id")) for team in teams if team.get("team_id")})
    for team_id in team_ids:
        yield add(
            "team_detail",
            service._team_detail_from_details(year, team_id, details),
            entity_id=team_id,
        )

    scope_details = {
        "all": details,
        "group_stage": [detail for detail in details if _is_group_match(detail["match"])],
        "knockout": [detail for detail in details if not _is_group_match(detail["match"])],
    }
    scoped_players_cache: dict[str, list[dict[str, Any]]] = {
        scope: service._aggregate_player_analytics(
            service._aggregate_players(scoped_details)
        )
        for scope, scoped_details in scope_details.items()
        if scoped_details
    }
    player_ids_by_scope: dict[str, set[str]] = {
        scope: {
            str(row.get("player_id"))
            for row in scoped_players
            if row.get("player_id")
        }
        for scope, scoped_players in scoped_players_cache.items()
    }
    for scope, player_ids in sorted(player_ids_by_scope.items()):
        for player_id in sorted(player_ids):
            yield add(
                "player_detail",
                service._player_detail_from_details(
                    year,
                    player_id,
                    details,
                    scope=scope,
                    scoped_players=scoped_players_cache[scope],
                ),
                entity_id=player_id,
                scope=scope,
            )

    match_scope_cache: dict[str, list[dict[str, Any]]] = {}
    detail_by_match_id = {
        str(detail["match"].get("match_id")): detail
        for detail in details
        if detail.get("match", {}).get("match_id")
    }
    for row in substrate["match_players"]:
        player_id = row.get("player_id")
        match_id = row.get("match_id")
        if not player_id or not match_id:
            continue
        match_id = str(match_id)
        if match_id not in match_scope_cache:
            match_detail = detail_by_match_id.get(match_id)
            match_scope_cache[match_id] = service._aggregate_player_analytics(
                service._aggregate_players([match_detail] if match_detail else [])
            )
        yield add(
            "player_detail",
            service._player_detail_from_details(
                year,
                str(player_id),
                [detail_by_match_id[match_id]] if match_id in detail_by_match_id else details,
                scope="match",
                match_id=match_id,
                scoped_players=match_scope_cache[match_id],
            ),
            entity_id=player_id,
            scope=f"match:{match_id}",
        )


class _NoGoldPayloads:
    def get_payload(
        self,
        year: int,
        endpoint: str,
        *,
        entity_id: str | None = None,
        scope: str | None = None,
    ) -> None:
        return None


def _legacy_data_service(data_root: Path) -> Any:
    from webapp.data_service import DataService

    return DataService(data_root, gold_payload_repository=_NoGoldPayloads())


def _is_group_match(match: dict[str, Any]) -> bool:
    return bool(match.get("group_name")) or "group" in str(match.get("stage") or "").casefold()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build TheStatsAPI World Cup 2026 serving gold substrate from local Bronze."
    )
    parser.add_argument("--year", type=int, default=WORLD_CUP_2026_EDITION)
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--database-url", default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only read Bronze and print row counts; do not write PostgreSQL.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build = (
        build_gold_substrate(args.year, data_root=args.data_root)
        if args.dry_run
        else rebuild_gold_serving(
            args.year,
            data_root=args.data_root,
            database_url=args.database_url,
        )
    )
    action = "validated" if args.dry_run else "materialized"
    counts = ", ".join(f"{table}={count}" for table, count in build.counts.items())
    print(f"TheStatsAPI serving gold {action} for {args.year}: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
