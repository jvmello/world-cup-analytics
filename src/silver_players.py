from pathlib import Path

import pandas as pd

from config import WORLD_CUP_SEASONS


BRONZE_BASE_PATH = Path("data/bronze/statsbomb/world_cup")
SILVER_BASE_PATH = Path("data/silver/world_cup")


def read_parquet_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    return pd.read_parquet(path)


def build_silver_players() -> pd.DataFrame:
    all_players = []

    for season in WORLD_CUP_SEASONS:
        lineups_path = (
            BRONZE_BASE_PATH
            / str(season.edition_year)
            / "lineups.parquet"
        )

        lineups = read_parquet_if_exists(lineups_path)

        if lineups.empty:
            continue

        lineups["edition_year"] = season.edition_year

        selected_columns = [
            "player_id",
            "player_name",
            "player_nickname",
            "team_name",
            "jersey_number",
            "country",
            "edition_year",
        ]

        existing_columns = [
            column for column in selected_columns if column in lineups.columns
        ]

        players = lineups[existing_columns].copy()

        if "player_nickname" not in players.columns:
            players["player_nickname"] = None

        players["player_full_name"] = players["player_name"]

        players["player_display_name"] = players["player_nickname"].where(
            players["player_nickname"].notna()
            & players["player_nickname"].astype(str).str.strip().ne(""),
            players["player_full_name"],
        )

        all_players.append(players)

    if not all_players:
        return pd.DataFrame()

    players_df = pd.concat(all_players, ignore_index=True)

    players_df = players_df.drop_duplicates(
        subset=["edition_year", "player_id", "team_name"]
    )

    output_path = SILVER_BASE_PATH / "players" / "silver_world_cup_players.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    players_df.to_parquet(output_path, index=False)

    return players_df


if __name__ == "__main__":
    players = build_silver_players()
    print(players.head(30).to_string(index=False))
    print(f"Total players: {len(players)}")