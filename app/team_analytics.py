from __future__ import annotations

import pandas as pd


def enrich_team_summary(team_summary: pd.DataFrame) -> pd.DataFrame:
    data = team_summary.copy()

    data["conversion_rate"] = (
        data["goals"].div(data["shots"]).where(data["shots"].gt(0), 0).fillna(0)
    )
    data["shot_accuracy"] = data["shot_accuracy"].fillna(0)
    data["goals_minus_xg"] = data["goals_minus_xg"].fillna(
        data["goals"] - data["xg"]
    )

    return data


def filter_team_summary(
    team_summary: pd.DataFrame,
    edition_year: int | str | None = None,
) -> pd.DataFrame:
    data = enrich_team_summary(team_summary)

    if edition_year not in (None, "Todas"):
        data = data[data["edition_year"].eq(int(edition_year))]

    return data.copy()


def get_team_row(
    team_summary: pd.DataFrame,
    edition_year: int | str,
    team_name: str,
) -> pd.Series:
    data = filter_team_summary(team_summary, edition_year)
    team = data[data["team_name"].eq(team_name)]

    if team.empty:
        raise ValueError(f"Team not found: {team_name}")

    return team.iloc[0]


def build_team_rankings(
    team_summary: pd.DataFrame,
    metric: str,
    edition_year: int | str | None = None,
) -> pd.DataFrame:
    data = filter_team_summary(team_summary, edition_year)

    return data.sort_values(
        [metric, "xg", "goals", "shots"],
        ascending=False,
    ).reset_index(drop=True)


def build_team_match_log(
    match_team_summary: pd.DataFrame,
    edition_year: int | str,
    team_name: str,
) -> pd.DataFrame:
    data = match_team_summary.copy()
    data = data[
        data["edition_year"].eq(int(edition_year))
        & data["team_name"].eq(team_name)
    ].copy()

    data["opponent"] = data["home_team"].where(
        data["away_team"].eq(team_name),
        data["away_team"],
    )
    data["team_goals"] = data["home_score"].where(
        data["home_team"].eq(team_name),
        data["away_score"],
    )
    data["opponent_goals"] = data["away_score"].where(
        data["home_team"].eq(team_name),
        data["home_score"],
    )
    data["result"] = "E"
    data.loc[data["team_goals"].gt(data["opponent_goals"]), "result"] = "V"
    data.loc[data["team_goals"].lt(data["opponent_goals"]), "result"] = "D"
    data["rolling_xg"] = data.sort_values("match_date")["xg"].rolling(
        3,
        min_periods=1,
    ).mean()

    return data.sort_values(["match_date", "match_id"]).reset_index(drop=True)


def build_team_shot_profile(player_shots: pd.DataFrame, edition_year: int, team_name: str) -> pd.DataFrame:
    return player_shots[
        player_shots["edition_year"].eq(edition_year)
        & player_shots["team_name"].eq(team_name)
    ].copy()
