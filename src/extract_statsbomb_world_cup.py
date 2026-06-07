from pathlib import Path

import pandas as pd
from statsbombpy import sb

from config import WORLD_CUP_SEASONS, WorldCupSeason


BRONZE_BASE_PATH = Path("data/bronze/statsbomb/world_cup")


def safe_write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def extract_matches(season: WorldCupSeason) -> pd.DataFrame:
    print(f"Extracting matches for World Cup {season.edition_year}")

    matches = sb.matches(
        competition_id=season.competition_id,
        season_id=season.season_id,
    )

    matches["edition_year"] = season.edition_year
    matches["competition_id"] = season.competition_id
    matches["season_id"] = season.season_id

    output_path = BRONZE_BASE_PATH / str(season.edition_year) / "matches.parquet"
    safe_write_parquet(matches, output_path)

    return matches


def extract_events(season: WorldCupSeason, matches: pd.DataFrame) -> pd.DataFrame:
    all_events = []

    for match_id in matches["match_id"].dropna().unique().tolist():
        print(f"Extracting events for {season.edition_year} match_id={match_id}")

        try:
            events = sb.events(match_id=match_id)
            events["match_id"] = match_id
            events["edition_year"] = season.edition_year
            all_events.append(events)
        except Exception as error:
            print(f"Error extracting events for match_id={match_id}: {error}")

    if not all_events:
        return pd.DataFrame()

    events_df = pd.concat(all_events, ignore_index=True)

    output_path = BRONZE_BASE_PATH / str(season.edition_year) / "events.parquet"
    safe_write_parquet(events_df, output_path)

    return events_df


def extract_lineups(season: WorldCupSeason, matches: pd.DataFrame) -> pd.DataFrame:
    all_lineups = []

    for match_id in matches["match_id"].dropna().unique().tolist():
        print(f"Extracting lineups for {season.edition_year} match_id={match_id}")

        try:
            lineups_by_team = sb.lineups(match_id=match_id)

            for team_name, lineup_df in lineups_by_team.items():
                lineup_df = lineup_df.copy()
                lineup_df["match_id"] = match_id
                lineup_df["edition_year"] = season.edition_year
                lineup_df["team_name"] = team_name
                all_lineups.append(lineup_df)

        except Exception as error:
            print(f"Error extracting lineups for match_id={match_id}: {error}")

    if not all_lineups:
        return pd.DataFrame()

    lineups_df = pd.concat(all_lineups, ignore_index=True)

    output_path = BRONZE_BASE_PATH / str(season.edition_year) / "lineups.parquet"
    safe_write_parquet(lineups_df, output_path)

    return lineups_df


def extract_360_frames_if_available(
    season: WorldCupSeason,
    matches: pd.DataFrame,
) -> pd.DataFrame:
    all_frames = []

    for match_id in matches["match_id"].dropna().unique().tolist():
        print(f"Trying 360 frames for {season.edition_year} match_id={match_id}")

        try:
            frames = sb.frames(match_id=match_id)
            frames["match_id"] = match_id
            frames["edition_year"] = season.edition_year
            all_frames.append(frames)
        except Exception as error:
            print(f"No 360 frames for match_id={match_id}: {error}")

    if not all_frames:
        return pd.DataFrame()

    frames_df = pd.concat(all_frames, ignore_index=True)

    output_path = BRONZE_BASE_PATH / str(season.edition_year) / "frames_360.parquet"
    safe_write_parquet(frames_df, output_path)

    return frames_df


def extract_season(season: WorldCupSeason) -> None:
    matches = extract_matches(season)
    events = extract_events(season, matches)
    lineups = extract_lineups(season, matches)
    frames = extract_360_frames_if_available(season, matches)

    print(
        f"Finished {season.edition_year}: "
        f"matches={len(matches)}, "
        f"events={len(events)}, "
        f"lineups={len(lineups)}, "
        f"frames_360={len(frames)}"
    )


def main() -> None:
    for season in WORLD_CUP_SEASONS:
        extract_season(season)


if __name__ == "__main__":
    main()