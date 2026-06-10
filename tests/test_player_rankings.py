import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from player_rankings import (  # noqa: E402
    build_leaderboard,
    build_team_profiles,
    enrich_player_summary,
    filter_players,
)


class PlayerRankingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.summary = pd.DataFrame(
            [
                {
                    "edition_year": 2022,
                    "team_name": "Argentina",
                    "player_name": "Lionel Messi",
                    "shots": 10,
                    "goals": 4,
                    "shots_on_target": 7,
                    "xg": 3.1,
                    "avg_xg_per_shot": 0.31,
                    "big_chances": 4,
                    "goals_minus_xg": 0.9,
                    "shot_accuracy": 0.7,
                },
                {
                    "edition_year": 2022,
                    "team_name": "France",
                    "player_name": "Kylian Mbappe",
                    "shots": 12,
                    "goals": 3,
                    "shots_on_target": 5,
                    "xg": 4.2,
                    "avg_xg_per_shot": 0.35,
                    "big_chances": 5,
                    "goals_minus_xg": -1.2,
                    "shot_accuracy": 0.417,
                },
                {
                    "edition_year": 2018,
                    "team_name": "France",
                    "player_name": "Antoine Griezmann",
                    "shots": 0,
                    "goals": 0,
                    "shots_on_target": 0,
                    "xg": 0.0,
                    "avg_xg_per_shot": 0.0,
                    "big_chances": 0,
                    "goals_minus_xg": 0.0,
                    "shot_accuracy": None,
                },
            ]
        )

    def test_enrich_adds_display_name_and_safe_conversion(self) -> None:
        result = enrich_player_summary(self.summary)

        self.assertIn("player_display_name", result.columns)
        self.assertEqual(result.loc[0, "player_display_name"], "Lionel Messi")
        self.assertEqual(result.loc[2, "conversion_rate"], 0)
        self.assertEqual(result.loc[2, "shot_accuracy"], 0)

    def test_filter_players_by_edition_team_and_volume(self) -> None:
        result = filter_players(
            self.summary,
            edition_year=2022,
            team_name="France",
            min_shots=5,
        )

        self.assertEqual(result["player_name"].tolist(), ["Kylian Mbappe"])

    def test_build_leaderboard_sorts_by_selected_metric(self) -> None:
        result = build_leaderboard(
            self.summary,
            metric="xG",
            edition_year=2022,
            min_shots=1,
            limit=2,
        )

        self.assertEqual(
            result["player_name"].tolist(),
            ["Kylian Mbappe", "Lionel Messi"],
        )

    def test_build_team_profiles_adds_rates(self) -> None:
        result = build_team_profiles(self.summary, edition_year=2022)

        france = result[result["team_name"].eq("France")].iloc[0]
        self.assertAlmostEqual(france["conversion_rate"], 0.25)
        self.assertAlmostEqual(france["shot_accuracy"], 5 / 12)


if __name__ == "__main__":
    unittest.main()
