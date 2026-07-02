from __future__ import annotations

import math
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .catalog import DEFAULT_EDITION, edition_catalog
from .thestatsapi_service import TheStatsApiBronzeService


EXPECTED_MATCHES = {
    1958: 35,
    1962: 32,
    1970: 32,
    1974: 38,
    1986: 52,
    1990: 52,
    2018: 64,
    2022: 64,
    2026: 104,
}

KNOWN_CHAMPIONS = {
    1958: "Brazil",
    1962: "Brazil",
    1970: "Brazil",
    1974: "West Germany",
    1986: "Argentina",
    1990: "West Germany",
    2018: "France",
    2022: "Argentina",
}


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, np.ndarray)):
        return [json_safe(item) for item in value]
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


class DataService:
    def __init__(self, data_root: Path | str = Path("data")) -> None:
        self.data_root = Path(data_root)
        self.thestatsapi = TheStatsApiBronzeService(data_root)

    def catalog(self) -> dict[str, Any]:
        return edition_catalog(self.data_root)

    def years(self) -> list[int]:
        return [item["year"] for item in self.catalog()["editions"]]

    def edition(self, year: int) -> dict[str, Any] | None:
        return next(
            (
                item
                for item in self.catalog()["editions"]
                if item["year"] == year
            ),
            None,
        )

    def _has_thestatsapi(self, year: int) -> bool:
        return year == 2026 and self.thestatsapi.available(year)

    def _read_parquet(self, relative: str) -> pd.DataFrame:
        path = self.data_root / relative
        if not path.exists():
            return pd.DataFrame()
        try:
            return pd.read_parquet(path)
        except (OSError, ValueError):
            return pd.DataFrame()

    def _read_csv(self, year: int, filename: str) -> pd.DataFrame:
        path = (
            self.data_root
            / "silver/fifa_pdf/world_cup"
            / str(year)
            / filename
        )
        if not path.exists():
            return pd.DataFrame()
        try:
            return pd.read_csv(path)
        except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
            return pd.DataFrame()

    @staticmethod
    def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
        return json_safe(frame.to_dict(orient="records"))

    @staticmethod
    def _for_year(frame: pd.DataFrame, year: int) -> pd.DataFrame:
        if frame.empty:
            return frame
        column = "edition_year" if "edition_year" in frame.columns else "edition"
        if column not in frame.columns:
            return frame.iloc[0:0]
        return frame[pd.to_numeric(frame[column], errors="coerce").eq(year)].copy()

    def matches_frame(self, year: int) -> pd.DataFrame:
        fifa = self._read_csv(year, "match_summary.csv")
        if not fifa.empty:
            return self._for_year(fifa, year)
        matches = self._read_parquet(
            "gold/world_cup/gold_match_summary/gold_match_summary.parquet"
        )
        return self._for_year(matches, year)

    def teams_frame(self, year: int) -> pd.DataFrame:
        frame = self._for_year(
            self._read_parquet(
                "gold/world_cup/gold_team_shot_summary/"
                "gold_team_shot_summary.parquet"
            ),
            year,
        )
        if frame.empty and year == 2026:
            metrics = self._read_csv(year, "team_key_statistics.csv")
            if not metrics.empty and {
                "team_name",
                "metric_name",
                "value",
            }.issubset(metrics.columns):
                frame = (
                    metrics.pivot_table(
                        index="team_name",
                        columns="metric_name",
                        values="value",
                        aggfunc="sum",
                    )
                    .reset_index()
                    .rename_axis(None, axis=1)
                )
        return frame

    def players_frame(self, year: int) -> pd.DataFrame:
        frame = self._for_year(
            self._read_parquet(
                "gold/world_cup/gold_player_offensive_summary/"
                "gold_player_offensive_summary.parquet"
            ),
            year,
        )
        if frame.empty and year == 2026:
            metrics = self._read_csv(year, "player_metrics.csv")
            if not metrics.empty and {
                "team_name",
                "player_name",
                "metric_name",
                "value",
            }.issubset(metrics.columns):
                frame = (
                    metrics.pivot_table(
                        index=["team_name", "player_name"],
                        columns="metric_name",
                        values="value",
                        aggfunc="sum",
                    )
                    .reset_index()
                    .rename_axis(None, axis=1)
                )
        return frame

    @staticmethod
    def _rank(
        frame: pd.DataFrame,
        metric: str,
        *,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        if frame.empty or metric not in frame.columns:
            return []
        ranked = frame.copy()
        ranked[metric] = pd.to_numeric(ranked[metric], errors="coerce")
        ranked = ranked.dropna(subset=[metric]).sort_values(
            metric, ascending=False
        )
        return DataService._records(ranked.head(limit))

    def coverage(self, year: int, match_count: int | None = None) -> dict[str, Any]:
        edition = self.edition(year) or {}
        actual = len(self.matches_frame(year)) if match_count is None else match_count
        availability = self._for_year(
            self._read_parquet(
                "silver/world_cup/metadata/"
                "world_cup_data_availability.parquet"
            ),
            year,
        )
        if not availability.empty and "matches" in availability.columns:
            reported = pd.to_numeric(
                availability.iloc[0]["matches"], errors="coerce"
            )
            if pd.notna(reported):
                actual = int(reported)
        expected = EXPECTED_MATCHES.get(year)
        partial = expected is None or actual < expected
        return {
            "source": edition.get("source"),
            "level": edition.get("coverage_level"),
            "partial": partial,
            "label": (
                "Cobertura histórica/avançada parcial"
                if partial
                else "Cobertura materializada completa"
            ),
        }

    def overview(self, year: int) -> dict[str, Any]:
        if self._has_thestatsapi(year):
            return self.thestatsapi.overview(year)
        matches = self.matches_frame(year)
        team_metrics = self.teams_frame(year)
        player_metrics = self.players_frame(year)
        teams = set()
        for column in ("home_team", "away_team"):
            if column in matches.columns:
                teams.update(str(value) for value in matches[column].dropna())
        goals = None
        if {"home_score", "away_score"}.issubset(matches.columns):
            scores = matches[["home_score", "away_score"]].apply(
                pd.to_numeric, errors="coerce"
            )
            goals = (
                int(scores.sum(axis=1, min_count=2).sum())
                if not scores.empty and scores.notna().all(axis=1).any()
                else None
            )
        return json_safe(
            {
                "year": year,
                "coverage": self.coverage(year, len(matches)),
                "summary": {
                    "matches": len(matches),
                    "goals": goals,
                    "teams": len(teams),
                    "champion": self._champion(year, matches),
                    "goals_per_match": (
                        round(goals / len(matches), 2)
                        if goals is not None and len(matches)
                        else None
                    ),
                },
                "highlights": {
                    "top_team": (
                        self._rank(
                            team_metrics,
                            "xg"
                            if "xg" in team_metrics.columns
                            else "attempts_at_goal",
                            limit=1,
                        )
                        or [None]
                    )[0],
                    "top_player": (
                        self._rank(
                            player_metrics,
                            "goals"
                            if "goals" in player_metrics.columns
                            else "attempts_at_goal",
                            limit=1,
                        )
                        or [None]
                    )[0],
                    "team_ranking": self._rank(
                        team_metrics,
                        "xg"
                        if "xg" in team_metrics.columns
                        else "attempts_at_goal",
                        limit=8,
                    ),
                    "player_ranking": self._rank(
                        player_metrics,
                        "goals"
                        if "goals" in player_metrics.columns
                        else "attempts_at_goal",
                        limit=8,
                    ),
                },
                "available": not matches.empty,
                "notice": None if not matches.empty else "Dados da edição ausentes.",
            }
        )

    def _champion(self, year: int, matches: pd.DataFrame) -> str | None:
        if year in KNOWN_CHAMPIONS:
            return KNOWN_CHAMPIONS[year]
        if matches.empty or "competition_stage" not in matches.columns:
            return None
        finals = matches[matches["competition_stage"].astype(str).eq("Final")]
        if finals.empty:
            return None
        final = finals.iloc[-1]
        home, away = final.get("home_score"), final.get("away_score")
        if pd.isna(home) or pd.isna(away) or home == away:
            return None
        return str(final["home_team"] if home > away else final["away_team"])

    def competition(self, year: int) -> dict[str, Any]:
        if self._has_thestatsapi(year):
            return self.thestatsapi.competition(year)
        groups = self._for_year(
            self._read_parquet(
                "gold/world_cup/gold_tournament_groups/"
                "gold_tournament_groups.parquet"
            ),
            year,
        )
        fixtures = self._for_year(
            self._read_parquet(
                "gold/world_cup/gold_tournament_fixtures/"
                "gold_tournament_fixtures.parquet"
            ),
            year,
        )
        grouped = []
        if not groups.empty and "group_name" in groups.columns:
            sort_columns = [
                column
                for column in ("group_name", "position")
                if column in groups.columns
            ]
            for name, frame in groups.sort_values(sort_columns).groupby(
                "group_name", sort=True
            ):
                grouped.append(
                    {"name": str(name), "teams": self._records(frame)}
                )
        if fixtures.empty:
            fixtures = self.matches_frame(year)
        available = bool(grouped) or not fixtures.empty
        return {
            "year": year,
            "available": available,
            "groups": grouped,
            "fixtures": self._records(fixtures),
            "notice": None if available else "Estrutura da competição ausente.",
        }

    def teams(self, year: int) -> dict[str, Any]:
        if self._has_thestatsapi(year):
            return self.thestatsapi.teams(year)
        frame = self.teams_frame(year)
        available = not frame.empty
        ranking_metrics = (
            "xg",
            "goals",
            "shots",
            "shots_on_target",
            "shot_accuracy",
            "attempts_at_goal",
            "attempts_on_target",
            "pass_completion_pct",
            "total_distance_km",
        )
        return {
            "year": year,
            "available": available,
            "summary": {
                "teams": int(frame["team_name"].nunique())
                if "team_name" in frame.columns
                else len(frame),
                "shots": self._numeric_total(frame, "shots"),
                "goals": self._numeric_total(frame, "goals"),
                "xg": self._numeric_total(frame, "xg"),
            },
            "rankings": {
                metric: self._rank(frame, metric)
                for metric in ranking_metrics
                if metric in frame.columns
            },
            "items": self._records(frame),
            "notice": None if available else "Dados de times ausentes.",
        }

    def players(self, year: int) -> dict[str, Any]:
        if self._has_thestatsapi(year):
            return self.thestatsapi.players(year)
        frame = self.players_frame(year)
        available = not frame.empty
        leader_metrics = (
            "goals",
            "xg",
            "shots",
            "shots_on_target",
            "goals_minus_xg",
            "attempts_at_goal",
            "passes_completed",
            "total_distance_m",
            "top_speed_kmh",
            "tackles_won",
        )
        scatter_columns = [
            column
            for column in (
                "player_name",
                "team_name",
                "shots",
                "goals",
                "xg",
                "goals_minus_xg",
                "attempts_at_goal",
                "passes_completed",
            )
            if column in frame.columns
        ]
        return {
            "year": year,
            "available": available,
            "summary": {
                "players": int(frame["player_name"].nunique())
                if "player_name" in frame.columns
                else len(frame),
                "goals": self._numeric_total(frame, "goals"),
                "shots": self._numeric_total(frame, "shots"),
                "xg": self._numeric_total(frame, "xg"),
            },
            "leaders": {
                metric: self._rank(frame, metric)
                for metric in leader_metrics
                if metric in frame.columns
            },
            "scatter": self._records(frame[scatter_columns])
            if scatter_columns
            else [],
            "items": self._records(frame),
            "notice": None if available else "Dados de jogadores ausentes.",
        }

    def matches(self, year: int) -> dict[str, Any]:
        if self._has_thestatsapi(year):
            return self.thestatsapi.matches(year)
        frame = self.matches_frame(year)
        available = not frame.empty
        distribution = []
        stage_column = next(
            (
                column
                for column in ("competition_stage", "stage", "group_name")
                if column in frame.columns
            ),
            None,
        )
        if stage_column:
            distribution = [
                {"stage": str(stage), "matches": int(count)}
                for stage, count in frame[stage_column]
                .fillna("Não informada")
                .value_counts()
                .items()
            ]
        goals = None
        if {"home_score", "away_score"}.issubset(frame.columns):
            scores = frame[["home_score", "away_score"]].apply(
                pd.to_numeric, errors="coerce"
            )
            goals = float(scores.sum().sum()) if not scores.empty else None
        return {
            "year": year,
            "available": available,
            "summary": {
                "matches": len(frame),
                "goals": int(goals) if goals is not None else None,
                "goals_per_match": (
                    round(goals / len(frame), 2)
                    if goals is not None and len(frame)
                    else None
                ),
            },
            "stage_distribution": distribution,
            "items": self._records(frame),
            "notice": None if available else "Dados de partidas ausentes.",
        }

    @staticmethod
    def _numeric_total(frame: pd.DataFrame, column: str) -> float | int | None:
        if frame.empty or column not in frame.columns:
            return None
        total = pd.to_numeric(frame[column], errors="coerce").sum(min_count=1)
        if pd.isna(total):
            return None
        return int(total) if float(total).is_integer() else round(float(total), 2)

    def shots(self, year: int) -> dict[str, Any]:
        if self._has_thestatsapi(year):
            return self.thestatsapi.shots(year)
        frame = self._for_year(
            self._read_parquet(
                "gold/world_cup/gold_player_shots/"
                "gold_player_shots.parquet"
            ),
            year,
        )
        if frame.empty:
            thestatsapi_shots = self.thestatsapi.shots(year)
            if thestatsapi_shots["available"]:
                return thestatsapi_shots
            return {
                "year": year,
                "available": False,
                "summary": {},
                "items": [],
                "notice": "Finalizações granulares ausentes para esta edição.",
            }

        numeric_xg = pd.to_numeric(
            frame.get("statsbomb_xg", pd.Series(dtype=float)),
            errors="coerce",
        )
        goals = pd.Series(False, index=frame.index)
        if "is_goal" in frame.columns:
            goals = frame["is_goal"].fillna(False).astype(bool)
        map_columns = [
            column
            for column in (
                "shot_id",
                "match_id",
                "match_date",
                "competition_stage",
                "home_team",
                "away_team",
                "home_score",
                "away_score",
                "team_name",
                "player_name",
                "minute",
                "x",
                "y",
                "statsbomb_xg",
                "shot_outcome",
                "body_part",
                "shot_type",
                "is_goal",
                "is_on_target",
            )
            if column in frame.columns
        ]
        player_group_columns = [
            column for column in ("player_name", "team_name") if column in frame.columns
        ]
        player_leaders: list[dict[str, Any]] = []
        if player_group_columns:
            aggregation: dict[str, tuple[str, str]] = {}
            if "shot_id" in frame.columns:
                aggregation["shots"] = ("shot_id", "count")
            else:
                frame = frame.assign(_shot_count=1)
                aggregation["shots"] = ("_shot_count", "sum")
            if "is_goal" in frame.columns:
                aggregation["goals"] = ("is_goal", "sum")
            if "statsbomb_xg" in frame.columns:
                aggregation["xg"] = ("statsbomb_xg", "sum")
            leaders = frame.groupby(player_group_columns, as_index=False).agg(
                **aggregation
            )
            player_leaders = self._records(
                leaders.sort_values(
                    [column for column in ("goals", "xg", "shots") if column in leaders],
                    ascending=False,
                ).head(12)
            )

        breakdowns = {}
        for column in ("body_part", "shot_type", "play_pattern", "shot_outcome"):
            if column in frame.columns:
                breakdowns[column] = [
                    {"label": str(label), "value": int(value)}
                    for label, value in frame[column]
                    .fillna("Não informado")
                    .value_counts()
                    .items()
                ]

        team_summary: list[dict[str, Any]] = []
        if "team_name" in frame.columns:
            aggregation = {"shots": ("team_name", "size")}
            if "is_goal" in frame.columns:
                aggregation["goals"] = ("is_goal", "sum")
            if "is_on_target" in frame.columns:
                aggregation["shots_on_target"] = ("is_on_target", "sum")
            if "statsbomb_xg" in frame.columns:
                aggregation["xg"] = ("statsbomb_xg", "sum")
            grouped = frame.groupby("team_name", as_index=False).agg(
                **aggregation
            )
            team_summary = self._records(
                grouped.sort_values(
                    [column for column in ("xg", "goals", "shots") if column in grouped],
                    ascending=False,
                )
            )

        xg_flow: list[dict[str, Any]] = []
        if {
            "team_name",
            "statsbomb_xg",
            "minute",
        }.issubset(frame.columns):
            flow_columns = [
                column
                for column in (
                    "match_id",
                    "home_team",
                    "away_team",
                    "team_name",
                    "minute",
                    "second",
                    "statsbomb_xg",
                    "is_goal",
                )
                if column in frame.columns
            ]
            flow = frame[flow_columns].copy()
            flow["minute"] = pd.to_numeric(flow["minute"], errors="coerce")
            flow["statsbomb_xg"] = pd.to_numeric(
                flow["statsbomb_xg"], errors="coerce"
            )
            flow = flow.dropna(subset=["minute", "statsbomb_xg"])
            sort_columns = [
                column for column in ("minute", "second") if column in flow.columns
            ]
            flow = flow.sort_values(sort_columns)
            flow_groups = [
                column
                for column in ("match_id", "team_name")
                if column in flow.columns
            ]
            flow["cumulative_xg"] = flow.groupby(flow_groups)[
                "statsbomb_xg"
            ].cumsum()
            xg_flow = self._records(flow)

        return {
            "year": year,
            "available": True,
            "summary": {
                "shots": len(frame),
                "goals": int(goals.sum()),
                "xg": float(numeric_xg.sum()) if not numeric_xg.empty else None,
                "players": (
                    int(frame["player_name"].nunique())
                    if "player_name" in frame.columns
                    else None
                ),
            },
            "shot_map": self._records(frame[map_columns])
            if map_columns
            else [],
            "player_leaders": player_leaders,
            "team_summary": team_summary,
            "xg_flow": xg_flow,
            "breakdowns": breakdowns,
            "items": self._records(frame.head(500)),
            "notice": (
                "A tabela exibe até 500 finalizações; os indicadores usam "
                "todas as linhas da edição."
            ),
        }

    def thestatsapi_match(self, year: int) -> dict[str, Any]:
        return self.thestatsapi.opening_match(year)

    def profiles(self, year: int) -> dict[str, Any]:
        if self._has_thestatsapi(year):
            return self.thestatsapi.profiles(year)
        return {
            "year": year,
            "available": False,
            "players": [],
            "teams": [],
            "notice": "Perfis detalhados ainda não estão disponíveis para esta edição.",
        }

    def match_detail(self, year: int, match_id: str) -> dict[str, Any]:
        if self._has_thestatsapi(year):
            return self.thestatsapi.match_detail(year, match_id)
        return {
            "year": year,
            "available": False,
            "notice": "Detalhe de partida disponível apenas para partidas com estatísticas preparadas.",
        }

    def player_detail(
        self,
        year: int,
        player_id: str,
        scope: str = "all",
        match_id: str | None = None,
    ) -> dict[str, Any]:
        if self._has_thestatsapi(year):
            return self.thestatsapi.player_detail(
                year,
                player_id,
                scope=scope,
                match_id=match_id,
            )
        return {
            "year": year,
            "available": False,
            "notice": "Detalhe de jogador disponível apenas quando há estatísticas preparadas.",
        }

    def team_detail(self, year: int, team_id: str) -> dict[str, Any]:
        if self._has_thestatsapi(year):
            return self.thestatsapi.team_detail(year, team_id)
        return {
            "year": year,
            "available": False,
            "notice": "Detalhe de seleção disponível apenas quando há estatísticas preparadas.",
        }

    def _collection(
        self, year: int, frame: pd.DataFrame, missing_notice: str
    ) -> dict[str, Any]:
        available = not frame.empty
        return {
            "year": year,
            "available": available,
            "items": self._records(frame),
            "notice": None if available else missing_notice,
        }

    def official_metrics(self, year: int) -> dict[str, Any]:
        teams = self._read_csv(year, "team_key_statistics.csv")
        phases = self._read_csv(year, "phases_of_play.csv")
        players = self._read_csv(year, "player_metrics.csv")
        available = any(not frame.empty for frame in (teams, phases, players))
        matches = self.matches_frame(year)
        scoreboard = None
        selected_match_id = None
        if not matches.empty:
            match = matches.iloc[0]
            selected_match_id = match.get("match_id")
            scoreboard = {
                key: json_safe(match.get(key))
                for key in (
                    "match_id",
                    "match_date",
                    "group_name",
                    "home_team",
                    "away_team",
                    "home_score",
                    "away_score",
                    "stadium",
                )
                if key in matches.columns
            }

        comparison_teams = teams
        comparison_phases = phases
        comparison_players = players
        if selected_match_id is not None:
            for name, frame in (
                ("teams", teams),
                ("phases", phases),
                ("players", players),
            ):
                if not frame.empty and "match_id" in frame.columns:
                    selected = frame[
                        frame["match_id"].astype(str).eq(str(selected_match_id))
                    ].copy()
                    if name == "teams":
                        comparison_teams = selected
                    elif name == "phases":
                        comparison_phases = selected
                    else:
                        comparison_players = selected

        team_comparison = []
        if not comparison_teams.empty and {
            "team_name",
            "metric_name",
            "value",
        }.issubset(comparison_teams.columns):
            pivot = comparison_teams.pivot_table(
                index=["metric_name", "unit"],
                columns="team_name",
                values="value",
                aggfunc="sum",
            ).reset_index().rename(columns={"metric_name": "metric"})
            pivot.columns.name = None
            if scoreboard:
                home_team = scoreboard.get("home_team")
                away_team = scoreboard.get("away_team")
                pivot["home_value"] = pivot.get(home_team)
                pivot["away_value"] = pivot.get(away_team)
            team_comparison = self._records(pivot)

        phase_comparison = []
        if not comparison_phases.empty and {
            "team_name",
            "phase_name",
            "percentage",
        }.issubset(comparison_phases.columns):
            pivot = comparison_phases.pivot_table(
                index=["possession_state", "phase_name"],
                columns="team_name",
                values="percentage",
                aggfunc="mean",
            ).reset_index()
            pivot.columns.name = None
            if scoreboard:
                home_team = scoreboard.get("home_team")
                away_team = scoreboard.get("away_team")
                pivot["home_value"] = pivot.get(home_team)
                pivot["away_value"] = pivot.get(away_team)
            phase_comparison = self._records(pivot)

        player_leaders = {}
        if not comparison_players.empty and {
            "player_name",
            "team_name",
            "metric_name",
            "value",
        }.issubset(comparison_players.columns):
            for metric in (
                "goals",
                "attempts_at_goal",
                "passes_completed",
                "total_distance_m",
                "top_speed_kmh",
                "tackles_won",
                "possession_regains",
            ):
                selected = comparison_players[
                    comparison_players["metric_name"].eq(metric)
                ].copy()
                if selected.empty:
                    continue
                selected["value"] = pd.to_numeric(
                    selected["value"], errors="coerce"
                )
                player_leaders[metric] = self._records(
                    selected.sort_values("value", ascending=False)[
                        ["player_name", "team_name", "value", "unit"]
                    ].head(10)
                )

        return {
            "year": year,
            "available": available,
            "scoreboard": scoreboard,
            "team_comparison": team_comparison,
            "phase_comparison": phase_comparison,
            "player_leaders": player_leaders,
            "team_metrics": self._records(teams),
            "phases_of_play": self._records(phases),
            "player_metrics": self._records(players),
            "notice": (
                None
                if available
                else "Métricas oficiais ainda não estão disponíveis para esta edição."
            ),
        }

    def availability(self, year: int) -> dict[str, Any]:
        edition = self.edition(year) or {}
        labels = {
            "overview": "Resumo do torneio",
            "competition": "Estrutura da competição",
            "teams": "Métricas de equipes",
            "players": "Métricas de jogadores",
            "matches": "Partidas",
            "shots": "Finalizações granulares",
            "xg": "Expected goals",
            "official_metrics": "Métricas oficiais FIFA",
            "phases_of_play": "Fases de jogo",
            "physical_metrics": "Métricas físicas",
        }
        return {
            "year": year,
            "source": edition.get("source"),
            "coverage": self.coverage(year),
            "capabilities": [
                {
                    "id": key,
                    "label": labels.get(key, key.replace("_", " ").title()),
                    "available": bool(value),
                }
                for key, value in edition.get("capabilities", {}).items()
            ],
        }

    def history(self) -> dict[str, Any]:
        editions = []
        for year in self.years():
            overview = self.overview(year)
            editions.append(
                {
                    "year": year,
                    **overview["summary"],
                    "coverage": overview["coverage"],
                }
            )
        return {
            "default_year": DEFAULT_EDITION,
            "partial_advanced_coverage": any(
                item["coverage"]["partial"] for item in editions
            ),
            "coverage_label": "Amostra histórica avançada parcial",
            "editions": editions,
        }
