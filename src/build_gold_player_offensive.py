from pathlib import Path

import pandas as pd


SILVER_SHOTS_PATH = Path(
    "data/silver/world_cup/shots/silver_world_cup_shots.parquet"
)

SILVER_PLAYERS_PATH = Path(
    "data/silver/world_cup/players/silver_world_cup_players.parquet"
)

GOLD_BASE_PATH = Path("data/gold/world_cup")


def write_gold(df: pd.DataFrame, name: str) -> None:
    output_path = GOLD_BASE_PATH / name / f"{name}.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)


def require_column(df: pd.DataFrame, column: str) -> None:
    if column not in df.columns:
        raise ValueError(f"Required column not found: {column}")


def normalize_shots(shots: pd.DataFrame) -> pd.DataFrame:
    shots = shots.copy()

    required_columns = [
        "shot_id",
        "match_id",
        "edition_year",
        "team_name",
        "player_name",
        "statsbomb_xg",
        "x",
        "y",
        "is_goal",
        "is_on_target",
    ]

    for column in required_columns:
        require_column(shots, column)

    shots["statsbomb_xg"] = pd.to_numeric(
        shots["statsbomb_xg"],
        errors="coerce",
    )

    shots["has_xg"] = shots["statsbomb_xg"].notna()
    shots["has_location"] = shots["x"].notna() & shots["y"].notna()

    shots["is_goal"] = shots["is_goal"].fillna(False).astype(bool)
    shots["is_on_target"] = shots["is_on_target"].fillna(False).astype(bool)

    return shots


def build_gold_player_shots() -> pd.DataFrame:
    if not SILVER_SHOTS_PATH.exists():
        raise FileNotFoundError(
            f"Silver shots table not found: {SILVER_SHOTS_PATH}"
        )
    
    if not SILVER_PLAYERS_PATH.exists():
        raise FileNotFoundError(
            f"Silver players table not found: {SILVER_PLAYERS_PATH}"
        )

    shots = pd.read_parquet(SILVER_SHOTS_PATH)
    shots = normalize_shots(shots)
    players = pd.read_parquet(SILVER_PLAYERS_PATH)

    shots = shots.merge(
        players[
            [
                "edition_year",
                "player_id",
                "team_name",
                "player_display_name",
                "player_full_name",
                "player_nickname",
                "jersey_number",
            ]
        ],
        on=["edition_year", "player_id", "team_name"],
        how="left",
    )

    shots["player_display_name"] = shots["player_display_name"].fillna(
        shots["player_name"]
    )

    print(f"Silver shots rows: {len(shots)}")
    print(f"Rows with player_name: {shots['player_name'].notna().sum()}")
    print(f"Rows with team_name: {shots['team_name'].notna().sum()}")
    print(f"Rows with xG: {shots['has_xg'].sum()}")
    print(f"Rows with location: {shots['has_location'].sum()}")

    filtered = shots[
        shots["player_name"].notna()
        & shots["team_name"].notna()
        & shots["has_xg"]
        & shots["has_location"]
    ].copy()

    print(f"Filtered player shots rows: {len(filtered)}")

    if filtered.empty:
        print("No player shots after filtering. Writing empty output.")
        write_gold(filtered, "gold_player_shots")
        return filtered

    selected_columns = [
        "shot_id",
        "match_id",
        "edition_year",
        "player_id",
        "team_id",
        "match_date",
        "competition_stage",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "team_name",
        "player_name",
        "position_name",
        "period",
        "minute",
        "second",
        "x",
        "y",
        "end_x",
        "end_y",
        "end_z",
        "statsbomb_xg",
        "shot_outcome",
        "body_part",
        "shot_type",
        "technique",
        "play_pattern",
        "is_goal",
        "is_on_target",
        "has_xg",
        "has_location",
    ]

    existing_columns = [
        column for column in selected_columns if column in filtered.columns
    ]

    gold = filtered[existing_columns].copy()

    write_gold(gold, "gold_player_shots")

    return gold


def build_gold_player_offensive_summary(
    player_shots: pd.DataFrame,
) -> pd.DataFrame:
    if player_shots.empty:
        summary = pd.DataFrame()
        write_gold(summary, "gold_player_offensive_summary")
        return summary

    summary = (
        player_shots.groupby(
            ["edition_year", "team_name", "player_name"],
            as_index=False,
        )
        .agg(
            shots=("shot_id", "count"),
            goals=("is_goal", "sum"),
            shots_on_target=("is_on_target", "sum"),
            xg=("statsbomb_xg", "sum"),
            avg_xg_per_shot=("statsbomb_xg", "mean"),
            big_chances=("statsbomb_xg", lambda values: (values >= 0.30).sum()),
        )
    )

    summary["xg"] = summary["xg"].round(2)
    summary["avg_xg_per_shot"] = summary["avg_xg_per_shot"].round(3)
    summary["goals_minus_xg"] = (summary["goals"] - summary["xg"]).round(2)
    summary["shot_accuracy"] = (
        summary["shots_on_target"] / summary["shots"]
    ).round(3)

    summary = summary.sort_values(
        ["edition_year", "xg", "goals", "shots"],
        ascending=[False, False, False, False],
    )

    write_gold(summary, "gold_player_offensive_summary")

    return summary


def main() -> None:
    player_shots = build_gold_player_shots()
    player_summary = build_gold_player_offensive_summary(player_shots)

    print(f"gold_player_shots rows: {len(player_shots)}")
    print(f"gold_player_offensive_summary rows: {len(player_summary)}")

    if not player_summary.empty:
        print(player_summary.head(20).to_string(index=False))


if __name__ == "__main__":
    main()