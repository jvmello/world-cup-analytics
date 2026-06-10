import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from world_cup_history import (  # noqa: E402
    build_champions,
    build_competition_group_tables,
    build_competition_knockouts,
    build_group_fixtures,
    build_group_table,
    build_knockout_matches,
    build_scheduled_group_tables,
    build_top_scorers,
    infer_match_winner,
)


class WorldCupHistoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.matches = pd.DataFrame(
            [
                {
                    "match_id": 1,
                    "edition_year": 2022,
                    "match_date": "2022-11-20",
                    "competition_stage": "Group Stage",
                    "home_team": "A",
                    "away_team": "B",
                    "home_score": 2,
                    "away_score": 1,
                    "stadium": "One",
                },
                {
                    "match_id": 2,
                    "edition_year": 2022,
                    "match_date": "2022-12-18",
                    "competition_stage": "Final",
                    "home_team": "A",
                    "away_team": "C",
                    "home_score": 3,
                    "away_score": 3,
                    "stadium": "Two",
                },
            ]
        )
        self.player_shots = pd.DataFrame(
            [
                {
                    "match_id": 2,
                    "period": 5,
                    "shot_type": "Penalty",
                    "team_name": "A",
                    "is_goal": True,
                },
                {
                    "match_id": 2,
                    "period": 5,
                    "shot_type": "Penalty",
                    "team_name": "A",
                    "is_goal": True,
                },
                {
                    "match_id": 2,
                    "period": 5,
                    "shot_type": "Penalty",
                    "team_name": "C",
                    "is_goal": True,
                },
            ]
        )
        self.players = pd.DataFrame(
            [
                {
                    "edition_year": 2022,
                    "team_name": "A",
                    "player_name": "Player One",
                    "goals": 3,
                    "shots": 8,
                    "xg": 2.4,
                    "goals_minus_xg": 0.6,
                },
                {
                    "edition_year": 2022,
                    "team_name": "C",
                    "player_name": "Player Two",
                    "goals": 4,
                    "shots": 7,
                    "xg": 1.9,
                    "goals_minus_xg": 2.1,
                },
            ]
        )

    def test_infer_match_winner_uses_penalties_for_draws(self) -> None:
        winner = infer_match_winner(self.matches.iloc[1], self.player_shots)

        self.assertEqual(winner.winner, "A")
        self.assertEqual(winner.source, "penalties")

    def test_build_champions_handles_penalty_final(self) -> None:
        champions = build_champions(self.matches, self.player_shots)

        self.assertEqual(champions.iloc[0]["champion"], "A")
        self.assertEqual(champions.iloc[0]["runner_up"], "C")

    def test_build_group_table_computes_points(self) -> None:
        table = build_group_table(self.matches, 2022)

        team_a = table[table["team_name"].eq("A")].iloc[0]
        self.assertEqual(team_a["points"], 3)
        self.assertEqual(team_a["goal_difference"], 1)

    def test_build_knockout_matches_adds_winner(self) -> None:
        knockouts = build_knockout_matches(self.matches, self.player_shots, 2022)

        self.assertEqual(knockouts.iloc[0]["winner"], "A")

    def test_build_top_scorers_orders_by_goals(self) -> None:
        scorers = build_top_scorers(self.players, 2022, limit=2)

        self.assertEqual(scorers.iloc[0]["player_display_name"], "Player Two")

    def test_scheduled_groups_start_with_zeroed_table(self) -> None:
        groups = pd.DataFrame(
            [
                {
                    "edition_year": 2026,
                    "group_name": "A",
                    "position": 1,
                    "team_name": "Mexico",
                },
                {
                    "edition_year": 2026,
                    "group_name": "A",
                    "position": 2,
                    "team_name": "South Africa",
                },
            ]
        )

        table = build_scheduled_group_tables(groups)

        self.assertEqual(table["points"].sum(), 0)
        self.assertEqual(table["played"].sum(), 0)

    def test_competition_groups_prefers_scheduled_gold(self) -> None:
        groups = pd.DataFrame(
            [
                {
                    "edition_year": 2026,
                    "group_name": "A",
                    "position": 1,
                    "team_name": "Mexico",
                }
            ]
        )

        table = build_competition_group_tables(self.matches, 2026, groups)

        self.assertEqual(table.iloc[0]["group_name"], "A")
        self.assertEqual(table.iloc[0]["team_name"], "Mexico")

    def test_competition_knockouts_uses_placeholders(self) -> None:
        fixtures = pd.DataFrame(
            [
                {
                    "edition_year": 2026,
                    "stage": "Round of 32",
                    "round_number": 1,
                    "match_number": 1,
                    "home_team": "TBD",
                    "away_team": "TBD",
                    "status": "placeholder",
                }
            ]
        )

        table = build_competition_knockouts(
            self.matches,
            self.player_shots,
            2026,
            fixtures,
        )

        self.assertEqual(table.iloc[0]["competition_stage"], "Round of 32")
        self.assertEqual(table.iloc[0]["winner"], "TBD")

    def test_group_fixtures_infers_group_name(self) -> None:
        fixtures = build_group_fixtures(self.matches, 2022)

        self.assertEqual(fixtures.iloc[0]["group_name"], "A")
        self.assertEqual(fixtures.iloc[0]["score"], "2 x 1")

    def test_group_fixtures_prefers_scheduled_fixture_gold(self) -> None:
        scheduled = pd.DataFrame(
            [
                {
                    "edition_year": 2026,
                    "stage": "Group Stage",
                    "group_name": "A",
                    "round_number": 1,
                    "match_number": 1,
                    "home_team": "Mexico",
                    "away_team": "South Africa",
                    "home_score": pd.NA,
                    "away_score": pd.NA,
                }
            ]
        )

        fixtures = build_group_fixtures(self.matches, 2026, scheduled)

        self.assertEqual(fixtures.iloc[0]["group_name"], "A")
        self.assertEqual(fixtures.iloc[0]["score"], "x")


if __name__ == "__main__":
    unittest.main()
