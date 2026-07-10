from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from thestatsapi.sync import bundled_match_ids, pending_finished_matches  # noqa: E402


def _fixture(match_id: str, status: str, utc_date: str, home: str = "A", away: str = "B") -> dict:
    return {
        "id": match_id,
        "status": status,
        "utc_date": utc_date,
        "home_team": {"id": f"tm_{home}", "name": home},
        "away_team": {"id": f"tm_{away}", "name": away},
    }


class PendingFinishedMatchesTest(unittest.TestCase):
    def test_selects_only_finished_matches_without_bundle_in_date_order(self) -> None:
        rows = [
            _fixture("mt_3", "finished", "2026-07-10T19:00:00Z", "Spain", "Belgium"),
            _fixture("mt_1", "finished", "2026-07-09T20:00:00Z", "France", "Morocco"),
            _fixture("mt_2", "scheduled", "2026-07-11T21:00:00Z"),
            _fixture("mt_4", "after_penalties", "2026-07-08T20:00:00Z"),
            _fixture("mt_5", "finished", "2026-07-01T20:00:00Z"),
        ]
        pending = pending_finished_matches(rows, bundled={"mt_5"})

        self.assertEqual([row["id"] for row in pending], ["mt_4", "mt_1", "mt_3"])

    def test_ignores_rows_without_match_id(self) -> None:
        pending = pending_finished_matches(
            [{"status": "finished", "utc_date": "2026-07-09T20:00:00Z"}],
            bundled=set(),
        )
        self.assertEqual(pending, [])

    def test_bundled_match_ids_requires_player_stats_marker(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw_root:
            data_root = Path(raw_root)
            matches = data_root / "bronze/thestatsapi/world_cup/2026/matches"
            complete = matches / "match_id=mt_ok/player_stats"
            complete.mkdir(parents=True)
            (complete / "response.json").write_text("{}", encoding="utf-8")
            partial = matches / "match_id=mt_partial/match_detail"
            partial.mkdir(parents=True)
            (partial / "response.json").write_text("{}", encoding="utf-8")

            self.assertEqual(bundled_match_ids(data_root, 2026), {"mt_ok"})


if __name__ == "__main__":
    unittest.main()
