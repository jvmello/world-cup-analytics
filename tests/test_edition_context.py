import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from edition_context import (  # noqa: E402
    ADVANCED_EVENT_DATA,
    FIFA_PDF_DATA,
    SELECTED_EDITION_STATE,
    get_data_coverage,
    get_selected_edition,
    render_edition_selector,
    set_selected_edition,
)
from fifa_pdf_data import FifaPdfData  # noqa: E402


class EditionContextTest(unittest.TestCase):
    def test_selector_does_not_reassign_widget_state_after_instantiation(self) -> None:
        class WidgetState(dict):
            locked_keys: set[str]

            def __init__(self) -> None:
                super().__init__()
                self.locked_keys = set()

            def __setitem__(self, key: str, value: object) -> None:
                if key in self.locked_keys:
                    raise RuntimeError(f"Widget state {key} was reassigned")
                super().__setitem__(key, value)

        class StreamlitStub:
            def __init__(self) -> None:
                self.session_state = WidgetState()

            def selectbox(
                self,
                label: str,
                options: tuple[int, ...],
                key: str,
            ) -> int:
                del label
                selected = self.session_state[key]
                self.session_state.locked_keys.add(key)
                self.assert_option(selected, options)
                return selected

            @staticmethod
            def assert_option(selected: int, options: tuple[int, ...]) -> None:
                if selected not in options:
                    raise AssertionError("Selected edition is not an option")

        streamlit = StreamlitStub()

        selected = render_edition_selector(streamlit)
        selected_from_page = get_selected_edition(streamlit.session_state)

        self.assertEqual(selected, 2026)
        self.assertEqual(selected_from_page, 2026)

    def test_default_edition_is_2026_and_is_persisted(self) -> None:
        session_state = {}

        selected = get_selected_edition(session_state)

        self.assertEqual(selected, 2026)
        self.assertEqual(session_state[SELECTED_EDITION_STATE], 2026)

    def test_selected_edition_is_shared_through_session_state(self) -> None:
        session_state = {}

        set_selected_edition(session_state, "2026")

        self.assertEqual(get_selected_edition(session_state), 2026)

    def test_only_2022_and_2026_are_supported(self) -> None:
        with self.assertRaises(ValueError):
            set_selected_edition({}, 2018)

    def test_2022_has_advanced_event_coverage(self) -> None:
        coverage = get_data_coverage(2022)

        self.assertEqual(coverage.level, ADVANCED_EVENT_DATA)
        self.assertEqual(coverage.source, "StatsBomb")
        self.assertTrue(coverage.supports_event_data)

    def test_2026_reports_aggregate_fifa_coverage(self) -> None:
        coverage = get_data_coverage(2026, fifa_data_available=True)

        self.assertEqual(coverage.level, FIFA_PDF_DATA)
        self.assertEqual(coverage.source, "FIFA PDF")
        self.assertFalse(coverage.supports_event_data)
        self.assertTrue(coverage.available)

    def test_2026_without_generated_csvs_is_explicitly_unavailable(self) -> None:
        coverage = get_data_coverage(2026, fifa_data_available=False)

        self.assertFalse(coverage.available)
        self.assertIn("CSV", coverage.message)


class FifaPdfDataTest(unittest.TestCase):
    def test_loads_available_silver_csvs_without_requiring_all_datasets(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            pd.DataFrame(
                [
                    {
                        "document_id": "doc-1",
                        "match_id": "M07",
                        "home_team": "Brazil",
                        "away_team": "Morocco",
                        "home_score": 2,
                        "away_score": 1,
                    }
                ]
            ).to_csv(output_dir / "match_summary.csv", index=False)
            pd.DataFrame(
                [
                    {
                        "document_id": "doc-1",
                        "match_id": "M07",
                        "team_name": "Brazil",
                        "metric": "Attempts at goal",
                        "value": 12,
                    }
                ]
            ).to_csv(output_dir / "team_key_statistics.csv", index=False)

            data = FifaPdfData.load(output_dir)

        self.assertTrue(data.available)
        self.assertEqual(data.matches.iloc[0]["home_team"], "Brazil")
        self.assertEqual(data.team_metrics.iloc[0]["value"], 12)
        self.assertTrue(data.player_metrics.empty)

    def test_missing_directory_returns_empty_bundle(self) -> None:
        data = FifaPdfData.load(Path("/path/that/does/not/exist"))

        self.assertFalse(data.available)
        self.assertTrue(data.matches.empty)
        self.assertIn("CSV", data.availability_message)

    def test_csv_values_are_normalized_for_ui_filters(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            pd.DataFrame(
                [
                    {
                        "match_id": "M07",
                        "team": "Brazil",
                        "metric_name": "Possession",
                        "metric_value": "55%",
                    }
                ]
            ).to_csv(output_dir / "team_key_statistics.csv", index=False)

            data = FifaPdfData.load(output_dir)

        self.assertEqual(data.team_metrics.iloc[0]["team_name"], "Brazil")
        self.assertEqual(data.team_metrics.iloc[0]["metric"], "Possession")
        self.assertEqual(data.team_metrics.iloc[0]["value"], "55%")


if __name__ == "__main__":
    unittest.main()
