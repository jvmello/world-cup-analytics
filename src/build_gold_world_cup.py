from pathlib import Path

import pandas as pd


SILVER_BASE_PATH = Path("data/silver/world_cup")
GOLD_BASE_PATH = Path("data/gold/world_cup")


def read_parquet_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    return pd.read_parquet(path)


def write_gold(df: pd.DataFrame, name: str) -> None:
    output_path = GOLD_BASE_PATH / name / f"{name}.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)


def build_gold_match_summary() -> pd.DataFrame:
    matches = read_parquet_if_exists(
        SILVER_BASE_PATH / "matches" / "silver_world_cup_matches.parquet"
    )

    if matches.empty:
        return pd.DataFrame()

    selected_columns = [
        "match_id",
        "edition_year",
        "match_date",
        "kick_off",
        "competition_stage",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "stadium",
        "referee",
        "data_granularity",
    ]

    existing_columns = [column for column in selected_columns if column in matches.columns]
    gold = matches[existing_columns].copy()

    write_gold(gold, "gold_match_summary")

    return gold


def build_gold_team_shot_summary() -> pd.DataFrame:
    shots = read_parquet_if_exists(
        SILVER_BASE_PATH / "shots" / "silver_world_cup_shots.parquet"
    )

    if shots.empty:
        return pd.DataFrame()

    filtered = shots[shots["has_xg"].fillna(False)].copy()

    if filtered.empty:
        return pd.DataFrame()

    gold = (
        filtered.groupby(["edition_year", "team_name"], as_index=False)
        .agg(
            shots=("shot_id", "count"),
            goals=("is_goal", "sum"),
            shots_on_target=("is_on_target", "sum"),
            xg=("statsbomb_xg", "sum"),
            avg_xg_per_shot=("statsbomb_xg", "mean"),
        )
    )

    gold["goals_minus_xg"] = gold["goals"] - gold["xg"]
    gold["shot_accuracy"] = gold["shots_on_target"] / gold["shots"]

    write_gold(gold, "gold_team_shot_summary")

    return gold


def build_gold_player_shot_summary() -> pd.DataFrame:
    shots = read_parquet_if_exists(
        SILVER_BASE_PATH / "shots" / "silver_world_cup_shots.parquet"
    )

    if shots.empty:
        return pd.DataFrame()

    filtered = shots[
        shots["has_xg"].fillna(False) & shots["player_name"].notna()
    ].copy()

    if filtered.empty:
        return pd.DataFrame()

    gold = (
        filtered.groupby(["edition_year", "team_name", "player_name"], as_index=False)
        .agg(
            shots=("shot_id", "count"),
            goals=("is_goal", "sum"),
            shots_on_target=("is_on_target", "sum"),
            xg=("statsbomb_xg", "sum"),
            avg_xg_per_shot=("statsbomb_xg", "mean"),
        )
    )

    gold["goals_minus_xg"] = gold["goals"] - gold["xg"]
    gold["shot_accuracy"] = gold["shots_on_target"] / gold["shots"]

    write_gold(gold, "gold_player_shot_summary")

    return gold


def build_gold_match_team_shot_summary() -> pd.DataFrame:
    shots = read_parquet_if_exists(
        SILVER_BASE_PATH / "shots" / "silver_world_cup_shots.parquet"
    )

    if shots.empty:
        return pd.DataFrame()

    filtered = shots[shots["has_xg"].fillna(False)].copy()

    if filtered.empty:
        return pd.DataFrame()

    group_columns = [
        "edition_year",
        "match_id",
        "match_date",
        "competition_stage",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "team_name",
    ]

    existing_group_columns = [
        column for column in group_columns if column in filtered.columns
    ]

    gold = (
        filtered.groupby(existing_group_columns, as_index=False)
        .agg(
            shots=("shot_id", "count"),
            goals=("is_goal", "sum"),
            shots_on_target=("is_on_target", "sum"),
            xg=("statsbomb_xg", "sum"),
            avg_xg_per_shot=("statsbomb_xg", "mean"),
        )
    )

    gold["goals_minus_xg"] = gold["goals"] - gold["xg"]
    gold["shot_accuracy"] = gold["shots_on_target"] / gold["shots"]

    write_gold(gold, "gold_match_team_shot_summary")

    return gold


def build_gold_xg_timeline() -> pd.DataFrame:
    shots = read_parquet_if_exists(
        SILVER_BASE_PATH / "shots" / "silver_world_cup_shots.parquet"
    )

    if shots.empty:
        return pd.DataFrame()

    filtered = shots[
        shots["has_xg"].fillna(False)
        & shots["minute"].notna()
        & shots["second"].notna()
    ].copy()

    if filtered.empty:
        return pd.DataFrame()

    filtered["elapsed_minute"] = (
        filtered["minute"].astype(float)
        + filtered["second"].astype(float) / 60
    )

    filtered = filtered.sort_values(
        ["edition_year", "match_id", "team_name", "period", "minute", "second"]
    )

    filtered["cumulative_xg"] = (
        filtered.groupby(["edition_year", "match_id", "team_name"])["statsbomb_xg"]
        .cumsum()
    )

    selected_columns = [
        "edition_year",
        "match_id",
        "match_date",
        "competition_stage",
        "home_team",
        "away_team",
        "team_name",
        "player_name",
        "period",
        "minute",
        "second",
        "elapsed_minute",
        "statsbomb_xg",
        "cumulative_xg",
        "shot_outcome",
        "is_goal",
    ]

    existing_columns = [column for column in selected_columns if column in filtered.columns]
    gold = filtered[existing_columns].copy()

    write_gold(gold, "gold_xg_timeline")

    return gold


def main() -> None:
    match_summary = build_gold_match_summary()
    team_summary = build_gold_team_shot_summary()
    player_summary = build_gold_player_shot_summary()
    match_team_summary = build_gold_match_team_shot_summary()
    xg_timeline = build_gold_xg_timeline()

    print(f"gold_match_summary rows: {len(match_summary)}")
    print(f"gold_team_shot_summary rows: {len(team_summary)}")
    print(f"gold_player_shot_summary rows: {len(player_summary)}")
    print(f"gold_match_team_shot_summary rows: {len(match_team_summary)}")
    print(f"gold_xg_timeline rows: {len(xg_timeline)}")


if __name__ == "__main__":
    main()