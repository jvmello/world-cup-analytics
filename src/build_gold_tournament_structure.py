from __future__ import annotations

from pathlib import Path

import pandas as pd


GOLD_BASE_PATH = Path("data/gold/world_cup")

WORLD_CUP_2026_GROUPS = {
    "A": ["Mexico", "South Africa", "South Korea", "Czechia"],
    "B": ["Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland"],
    "C": ["Brazil", "Morocco", "Haiti", "Scotland"],
    "D": ["United States", "Paraguay", "Australia", "Turkey"],
    "E": ["Germany", "Curaçao", "Ivory Coast", "Ecuador"],
    "F": ["Netherlands", "Japan", "Sweden", "Tunisia"],
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Cape Verde", "Saudi Arabia", "Uruguay"],
    "I": ["France", "Senegal", "Iraq", "Norway"],
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "DR Congo", "Uzbekistan", "Colombia"],
    "L": ["England", "Croatia", "Ghana", "Panama"],
}

ROUND_ROBIN_PAIRINGS = [
    (0, 1),
    (2, 3),
    (0, 2),
    (3, 1),
    (3, 0),
    (1, 2),
]

KNOCKOUT_TEMPLATE_2026 = [
    ("Round of 32", 16),
    ("Round of 16", 8),
    ("Quarter-finals", 4),
    ("Semi-finals", 2),
    ("3rd Place Final", 1),
    ("Final", 1),
]


def write_gold(df: pd.DataFrame, name: str) -> None:
    output_path = GOLD_BASE_PATH / name / f"{name}.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)


def build_gold_tournament_groups() -> pd.DataFrame:
    rows = []

    for group_name, teams in WORLD_CUP_2026_GROUPS.items():
        for position, team_name in enumerate(teams, start=1):
            rows.append(
                {
                    "edition_year": 2026,
                    "competition": "FIFA World Cup",
                    "stage": "Group Stage",
                    "group_name": group_name,
                    "position": position,
                    "team_name": team_name,
                    "data_status": "scheduled",
                }
            )

    gold = pd.DataFrame(rows)
    write_gold(gold, "gold_tournament_groups")

    return gold


def build_gold_tournament_fixtures() -> pd.DataFrame:
    rows = []
    match_number = 1

    for group_name, teams in WORLD_CUP_2026_GROUPS.items():
        for round_number, (home_index, away_index) in enumerate(
            ROUND_ROBIN_PAIRINGS,
            start=1,
        ):
            rows.append(
                {
                    "edition_year": 2026,
                    "competition": "FIFA World Cup",
                    "stage": "Group Stage",
                    "group_name": group_name,
                    "round_number": round_number,
                    "match_number": match_number,
                    "home_team": teams[home_index],
                    "away_team": teams[away_index],
                    "home_score": pd.NA,
                    "away_score": pd.NA,
                    "match_date": pd.NA,
                    "status": "scheduled",
                }
            )
            match_number += 1

    for stage, slots in KNOCKOUT_TEMPLATE_2026:
        for slot in range(1, slots + 1):
            rows.append(
                {
                    "edition_year": 2026,
                    "competition": "FIFA World Cup",
                    "stage": stage,
                    "group_name": pd.NA,
                    "round_number": slot,
                    "match_number": match_number,
                    "home_team": "TBD",
                    "away_team": "TBD",
                    "home_score": pd.NA,
                    "away_score": pd.NA,
                    "match_date": pd.NA,
                    "status": "placeholder",
                }
            )
            match_number += 1

    gold = pd.DataFrame(rows)
    write_gold(gold, "gold_tournament_fixtures")

    return gold


def main() -> None:
    groups = build_gold_tournament_groups()
    fixtures = build_gold_tournament_fixtures()

    print(f"gold_tournament_groups rows: {len(groups)}")
    print(f"gold_tournament_fixtures rows: {len(fixtures)}")


if __name__ == "__main__":
    main()
