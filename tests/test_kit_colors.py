from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from webapp.kit_colors import display_hex, kits_for, load_kit_colors  # noqa: E402

ROOT = str(Path(__file__).parents[1] / "kit_pallete")


class KitColorsTest(unittest.TestCase):
    def test_parses_every_published_phase_without_unknown_teams(self) -> None:
        mapping = load_kit_colors(ROOT)
        # 72 group + 16 R32 + 8 R16 + 4 QF published so far; new phases only add.
        self.assertGreaterEqual(len(mapping), 100)
        for entry in mapping.values():
            for kit in entry["teams"].values():
                self.assertRegex(kit["hex"], r"^#[0-9A-F]{6}$")

    def test_lookup_matches_quarter_final_and_group_stage(self) -> None:
        qf = kits_for("quarter_final", None, "France", "Morocco", root=ROOT)
        self.assertEqual(qf["France"]["hex"], "#A7D98B")
        self.assertEqual(qf["Morocco"]["hex"], "#E31B35")
        group = kits_for("Group Stage", "A", "Mexico", "South Africa", root=ROOT)
        self.assertEqual(group["Mexico"]["name"], "verde")

    def test_display_hex_lifts_dark_kits_only(self) -> None:
        self.assertNotEqual(display_hex("#111111"), "#111111")
        self.assertEqual(display_hex("#FFFFFF"), "#FFFFFF")

    def test_unknown_pair_returns_none(self) -> None:
        self.assertIsNone(kits_for("final", None, "France", "Morocco", root=ROOT))


if __name__ == "__main__":
    unittest.main()
