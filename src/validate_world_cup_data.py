from pathlib import Path

import pandas as pd

from config import WORLD_CUP_SEASONS


BRONZE_BASE_PATH = Path("data/bronze/statsbomb/world_cup")
SILVER_BASE_PATH = Path("data/silver/world_cup")


def read_parquet_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    return pd.read_parquet(path)


def build_data_availability_report() -> pd.DataFrame:
    rows = []

    for season in WORLD_CUP_SEASONS:
        edition_year = season.edition_year

        matches = read_parquet_if_exists(
            BRONZE_BASE_PATH / str(edition_year) / "matches.parquet"
        )
        events = read_parquet_if_exists(
            BRONZE_BASE_PATH / str(edition_year) / "events.parquet"
        )
        lineups = read_parquet_if_exists(
            BRONZE_BASE_PATH / str(edition_year) / "lineups.parquet"
        )
        frames = read_parquet_if_exists(
            BRONZE_BASE_PATH / str(edition_year) / "frames_360.parquet"
        )

        shots = pd.DataFrame()

        if not events.empty and "type" in events.columns:
            shots = events[events["type"] == "Shot"].copy()

        rows.append(
            {
                "edition_year": edition_year,
                "matches": len(matches),
                "events": len(events),
                "lineups": len(lineups),
                "shots": len(shots),
                "has_match_data": not matches.empty,
                "has_event_data": not events.empty,
                "has_lineups": not lineups.empty,
                "has_shots": not shots.empty,
                "has_xg": (
                    "shot_statsbomb_xg" in shots.columns
                    and shots["shot_statsbomb_xg"].notna().any()
                )
                if not shots.empty
                else False,
                "has_shot_location": (
                    "location" in shots.columns
                    and shots["location"].notna().any()
                )
                if not shots.empty
                else False,
                "has_360": not frames.empty,
            }
        )

    report = pd.DataFrame(rows)

    output_path = SILVER_BASE_PATH / "metadata" / "world_cup_data_availability.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report.to_parquet(output_path, index=False)

    return report


def main() -> None:
    report = build_data_availability_report()

    print("\nWorld Cup data availability")
    print(report.to_string(index=False))


if __name__ == "__main__":
    main()