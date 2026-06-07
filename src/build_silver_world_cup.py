from pathlib import Path
from typing import Any

import pandas as pd

from config import WORLD_CUP_SEASONS


BRONZE_BASE_PATH = Path("data/bronze/statsbomb/world_cup")
SILVER_BASE_PATH = Path("data/silver/world_cup")


def read_parquet_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    return pd.read_parquet(path)


def get_list_value(value: Any, index: int) -> float | None:
    if isinstance(value, list) and len(value) > index:
        return value[index]

    return None


def column_or_none(df: pd.DataFrame, column: str) -> pd.Series:
    if column in df.columns:
        return df[column]

    return pd.Series([None] * len(df), index=df.index)


def build_silver_matches_for_edition(edition_year: int) -> pd.DataFrame:
    matches_path = BRONZE_BASE_PATH / str(edition_year) / "matches.parquet"
    matches = read_parquet_if_exists(matches_path)

    if matches.empty:
        return pd.DataFrame()

    selected_columns = [
        "match_id",
        "edition_year",
        "competition_id",
        "season_id",
        "match_date",
        "kick_off",
        "competition",
        "season",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "match_status",
        "match_week",
        "competition_stage",
        "stadium",
        "referee",
        "home_managers",
        "away_managers",
        "data_version",
        "shot_fidelity_version",
        "xy_fidelity_version",
    ]

    existing_columns = [column for column in selected_columns if column in matches.columns]
    silver = matches[existing_columns].copy()

    silver["has_match_data"] = True
    silver["data_granularity"] = "match"

    return silver


def build_silver_events_for_edition(edition_year: int) -> pd.DataFrame:
    events_path = BRONZE_BASE_PATH / str(edition_year) / "events.parquet"
    events = read_parquet_if_exists(events_path)

    if events.empty:
        return pd.DataFrame()

    silver = pd.DataFrame()

    silver["event_id"] = column_or_none(events, "id")
    silver["match_id"] = column_or_none(events, "match_id")
    silver["edition_year"] = edition_year
    silver["event_index"] = column_or_none(events, "index")
    silver["period"] = column_or_none(events, "period")
    silver["timestamp"] = column_or_none(events, "timestamp")
    silver["minute"] = column_or_none(events, "minute")
    silver["second"] = column_or_none(events, "second")
    silver["event_type"] = column_or_none(events, "type")
    silver["team_name"] = column_or_none(events, "team")
    silver["player_name"] = column_or_none(events, "player")
    silver["position_name"] = column_or_none(events, "position")
    silver["possession"] = column_or_none(events, "possession")
    silver["possession_team"] = column_or_none(events, "possession_team")
    silver["play_pattern"] = column_or_none(events, "play_pattern")
    silver["under_pressure"] = column_or_none(events, "under_pressure")

    silver["x"] = column_or_none(events, "location").apply(lambda value: get_list_value(value, 0))
    silver["y"] = column_or_none(events, "location").apply(lambda value: get_list_value(value, 1))

    silver["has_event_data"] = True
    silver["data_granularity"] = "event"

    output_path = SILVER_BASE_PATH / "events" / f"edition_year={edition_year}.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    silver.to_parquet(output_path, index=False)

    return silver


def build_silver_shots_for_edition(edition_year: int) -> pd.DataFrame:
    matches_path = BRONZE_BASE_PATH / str(edition_year) / "matches.parquet"
    events_path = BRONZE_BASE_PATH / str(edition_year) / "events.parquet"
    frames_path = BRONZE_BASE_PATH / str(edition_year) / "frames_360.parquet"

    matches = read_parquet_if_exists(matches_path)
    events = read_parquet_if_exists(events_path)
    frames = read_parquet_if_exists(frames_path)

    if events.empty or "type" not in events.columns:
        return pd.DataFrame()

    shots = events[events["type"] == "Shot"].copy()

    if shots.empty:
        return pd.DataFrame()

    match_context_columns = [
        "match_id",
        "match_date",
        "kick_off",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "competition_stage",
        "stadium",
        "referee",
    ]

    existing_match_columns = [
        column for column in match_context_columns if column in matches.columns
    ]

    match_context = matches[existing_match_columns].drop_duplicates("match_id")

    silver = shots.merge(
        match_context,
        on="match_id",
        how="left",
    )

    silver["shot_id"] = column_or_none(silver, "id")
    silver["edition_year"] = edition_year

    silver["team_name"] = column_or_none(silver, "team")
    silver["player_name"] = column_or_none(silver, "player")
    silver["position_name"] = column_or_none(silver, "position")

    silver["x"] = column_or_none(silver, "location").apply(lambda value: get_list_value(value, 0))
    silver["y"] = column_or_none(silver, "location").apply(lambda value: get_list_value(value, 1))

    silver["end_x"] = column_or_none(silver, "shot_end_location").apply(
        lambda value: get_list_value(value, 0)
    )
    silver["end_y"] = column_or_none(silver, "shot_end_location").apply(
        lambda value: get_list_value(value, 1)
    )
    silver["end_z"] = column_or_none(silver, "shot_end_location").apply(
        lambda value: get_list_value(value, 2)
    )

    silver["statsbomb_xg"] = column_or_none(silver, "shot_statsbomb_xg")
    silver["statsbomb_xg2"] = column_or_none(silver, "shot_statsbomb_xg2")
    silver["shot_outcome"] = column_or_none(silver, "shot_outcome")
    silver["body_part"] = column_or_none(silver, "shot_body_part")
    silver["shot_type"] = column_or_none(silver, "shot_type")
    silver["technique"] = column_or_none(silver, "shot_technique")
    silver["first_time"] = column_or_none(silver, "shot_first_time")
    silver["one_on_one"] = column_or_none(silver, "shot_one_on_one")
    silver["open_goal"] = column_or_none(silver, "shot_open_goal")
    silver["deflected"] = column_or_none(silver, "shot_deflected")
    silver["aerial_won"] = column_or_none(silver, "shot_aerial_won")
    silver["key_pass_id"] = column_or_none(silver, "shot_key_pass_id")
    silver["freeze_frame"] = column_or_none(silver, "shot_freeze_frame")

    silver["is_goal"] = silver["shot_outcome"].astype(str).str.lower().eq("goal")

    silver["is_on_target"] = silver["shot_outcome"].astype(str).isin(
        ["Goal", "Saved", "Saved to Post"]
    )

    silver["has_xg"] = silver["statsbomb_xg"].notna()
    silver["has_location"] = silver["x"].notna() & silver["y"].notna()
    silver["has_end_location"] = silver["end_x"].notna() & silver["end_y"].notna()
    silver["has_freeze_frame"] = silver["freeze_frame"].notna()
    silver["has_360"] = not frames.empty

    silver["data_granularity"] = "shot"

    selected_columns = [
        "shot_id",
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
        "period",
        "timestamp",
        "minute",
        "second",
        "team_name",
        "player_name",
        "position_name",
        "x",
        "y",
        "end_x",
        "end_y",
        "end_z",
        "statsbomb_xg",
        "statsbomb_xg2",
        "shot_outcome",
        "body_part",
        "shot_type",
        "technique",
        "play_pattern",
        "first_time",
        "one_on_one",
        "open_goal",
        "deflected",
        "aerial_won",
        "key_pass_id",
        "is_goal",
        "is_on_target",
        "has_xg",
        "has_location",
        "has_end_location",
        "has_freeze_frame",
        "has_360",
        "data_granularity",
    ]

    existing_columns = [column for column in selected_columns if column in silver.columns]
    silver = silver[existing_columns]

    output_path = SILVER_BASE_PATH / "shots" / f"edition_year={edition_year}.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    silver.to_parquet(output_path, index=False)

    return silver


def build_all_silver_matches() -> None:
    all_matches = []

    for season in WORLD_CUP_SEASONS:
        silver_matches = build_silver_matches_for_edition(season.edition_year)

        if not silver_matches.empty:
            all_matches.append(silver_matches)

    if not all_matches:
        return

    matches_df = pd.concat(all_matches, ignore_index=True)

    output_path = SILVER_BASE_PATH / "matches" / "silver_world_cup_matches.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    matches_df.to_parquet(output_path, index=False)


def build_all_silver_events_and_shots() -> None:
    all_events = []
    all_shots = []

    for season in WORLD_CUP_SEASONS:
        silver_events = build_silver_events_for_edition(season.edition_year)
        silver_shots = build_silver_shots_for_edition(season.edition_year)

        if not silver_events.empty:
            all_events.append(silver_events)

        if not silver_shots.empty:
            all_shots.append(silver_shots)

    if all_events:
        events_df = pd.concat(all_events, ignore_index=True)
        output_path = SILVER_BASE_PATH / "events" / "silver_world_cup_events.parquet"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        events_df.to_parquet(output_path, index=False)

    if all_shots:
        shots_df = pd.concat(all_shots, ignore_index=True)
        output_path = SILVER_BASE_PATH / "shots" / "silver_world_cup_shots.parquet"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shots_df.to_parquet(output_path, index=False)


def main() -> None:
    build_all_silver_matches()
    build_all_silver_events_and_shots()


if __name__ == "__main__":
    main()