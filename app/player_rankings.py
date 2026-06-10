from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class RankingMetric:
    label: str
    column: str
    description: str


RANKING_METRICS = [
    RankingMetric("xG", "xg", "Maior soma de expected goals."),
    RankingMetric("Gols", "goals", "Maior número de gols."),
    RankingMetric("Finalizações", "shots", "Maior volume de chutes."),
    RankingMetric("Gols - xG", "goals_minus_xg", "Maior overperformance contra xG."),
    RankingMetric("xG/finalização", "avg_xg_per_shot", "Melhor qualidade média de chance."),
    RankingMetric("Precisão", "shot_accuracy", "Maior proporção de chutes no alvo."),
    RankingMetric("Conversão", "conversion_rate", "Maior proporção de gols por chute."),
    RankingMetric("Grandes chances", "big_chances", "Mais finalizações com xG >= 0.30."),
]


def metric_options() -> list[str]:
    return [metric.label for metric in RANKING_METRICS]


def metric_column(label: str) -> str:
    for metric in RANKING_METRICS:
        if metric.label == label:
            return metric.column

    raise ValueError(f"Unknown ranking metric: {label}")


def enrich_player_summary(summary: pd.DataFrame) -> pd.DataFrame:
    data = summary.copy()

    if "player_display_name" not in data.columns:
        data["player_display_name"] = data["player_name"]

    data["conversion_rate"] = (
        data["goals"].div(data["shots"]).where(data["shots"].gt(0), 0).fillna(0)
    )

    data["shot_accuracy"] = data["shot_accuracy"].fillna(0)
    data["goals_minus_xg"] = data["goals_minus_xg"].fillna(
        data["goals"] - data["xg"]
    )

    return data


def filter_players(
    summary: pd.DataFrame,
    edition_year: int | str | None = None,
    team_name: str | None = None,
    min_shots: int = 1,
) -> pd.DataFrame:
    data = enrich_player_summary(summary)

    if edition_year not in (None, "Todas"):
        data = data[data["edition_year"].eq(int(edition_year))]

    if team_name not in (None, "Todas"):
        data = data[data["team_name"].eq(team_name)]

    return data[data["shots"].ge(min_shots)].copy()


def build_leaderboard(
    summary: pd.DataFrame,
    metric: str,
    edition_year: int | str | None = None,
    team_name: str | None = None,
    min_shots: int = 1,
    limit: int = 25,
) -> pd.DataFrame:
    column = metric_column(metric)
    data = filter_players(summary, edition_year, team_name, min_shots)

    sort_columns = [column, "xg", "goals", "shots"]
    sort_columns = list(dict.fromkeys(sort_columns))

    return (
        data.sort_values(sort_columns, ascending=False)
        .head(limit)
        .reset_index(drop=True)
    )


def build_team_profiles(summary: pd.DataFrame, edition_year: int | str) -> pd.DataFrame:
    data = filter_players(summary, edition_year=edition_year, min_shots=1)

    if data.empty:
        return data

    teams = (
        data.groupby("team_name", as_index=False)
        .agg(
            players=("player_name", "count"),
            shots=("shots", "sum"),
            goals=("goals", "sum"),
            xg=("xg", "sum"),
            shots_on_target=("shots_on_target", "sum"),
            big_chances=("big_chances", "sum"),
        )
        .sort_values(["xg", "goals", "shots"], ascending=False)
    )

    teams["avg_xg_per_shot"] = (
        teams["xg"].div(teams["shots"]).where(teams["shots"].gt(0), 0).fillna(0)
    )
    teams["shot_accuracy"] = (
        teams["shots_on_target"]
        .div(teams["shots"])
        .where(teams["shots"].gt(0), 0)
        .fillna(0)
    )
    teams["conversion_rate"] = (
        teams["goals"].div(teams["shots"]).where(teams["shots"].gt(0), 0).fillna(0)
    )

    return teams
