import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from team_analytics import (  # noqa: E402
    build_team_match_log,
    build_team_rankings,
    enrich_team_summary,
    get_team_row,
)


class TeamAnalyticsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.summary = pd.DataFrame(
            [
                {
                    "edition_year": 2022,
                    "team_name": "Argentina",
                    "shots": 20,
                    "goals": 5,
                    "shots_on_target": 10,
                    "xg": 4.5,
                    "avg_xg_per_shot": 0.225,
                    "goals_minus_xg": 0.5,
                    "shot_accuracy": 0.5,
                },
                {
                    "edition_year": 2022,
                    "team_name": "France",
                    "shots": 18,
                    "goals": 6,
                    "shots_on_target": 9,
                    "xg": 3.8,
                    "avg_xg_per_shot": 0.211,
                    "goals_minus_xg": 2.2,
                    "shot_accuracy": 0.5,
                },
            ]
        )
        self.match_log = pd.DataFrame(
            [
                {
                    "edition_year": 2022,
                    "match_id": 1,
                    "match_date": "2022-12-01",
                    "home_team": "Argentina",
                    "away_team": "France",
                    "home_score": 2,
                    "away_score": 1,
                    "team_name": "Argentina",
                    "shots": 10,
                    "goals": 2,
                    "xg": 1.2,
                }
            ]
        )

    def test_enrich_team_summary_adds_conversion(self) -> None:
        result = enrich_team_summary(self.summary)

        self.assertAlmostEqual(result.iloc[0]["conversion_rate"], 0.25)

    def test_get_team_row_finds_selected_team(self) -> None:
        row = get_team_row(self.summary, 2022, "France")

        self.assertEqual(row["goals"], 6)

    def test_rankings_sort_by_metric(self) -> None:
        result = build_team_rankings(self.summary, "xg", 2022)

        self.assertEqual(result.iloc[0]["team_name"], "Argentina")

    def test_match_log_adds_opponent_and_result(self) -> None:
        result = build_team_match_log(self.match_log, 2022, "Argentina")

        self.assertEqual(result.iloc[0]["opponent"], "France")
        self.assertEqual(result.iloc[0]["result"], "V")


if __name__ == "__main__":
    unittest.main()
