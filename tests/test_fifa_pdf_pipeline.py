import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fifa_pdf.cli import build_parser  # noqa: E402
from fifa_pdf.extractor import PdfExtractor  # noqa: E402
from fifa_pdf.parsers import (  # noqa: E402
    classify_page,
    normalize_private_digits,
    parse_attempts,
    parse_cover,
    parse_key_statistics,
    parse_phases_of_play,
    parse_player_metrics,
)
from fifa_pdf.pipeline import FifaPdfPipeline  # noqa: E402
from fifa_pdf.publication import PRODUCT_NAMES, publish_match_pdf  # noqa: E402
from fifa_pdf.snapshot import create_snapshot  # noqa: E402
from fifa_pdf.storage import DATASETS  # noqa: E402


PDF_BASE = ROOT / "data" / "pdf" / "PMSR-M07-BRA-V-MAR.pdf"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class ParserContractTest(unittest.TestCase):
    def test_cover_parser_builds_canonical_match_summary(self) -> None:
        text = (
            "Brazil 1 - 1 Morocco\n"
            "Group C - Match 7\n"
            "13 June 2026\n"
            "18:00 Kick O\x00\n"
            "New York/New Jersey Stadium\n"
            "POST MATCH SUMMARY REPORT"
        )

        row = parse_cover(
            text,
            document_id="doc-1",
            source_file="match.pdf",
            page_number=1,
            edition=2026,
        )

        self.assertEqual(row["match_id"], "2026-match-7-brazil-morocco")
        self.assertEqual(row["home_team"], "Brazil")
        self.assertEqual(row["away_team"], "Morocco")
        self.assertEqual(row["home_score"], 1)
        self.assertEqual(row["away_score"], 1)
        self.assertEqual(row["group_name"], "C")
        self.assertEqual(row["match_number"], 7)
        self.assertEqual(row["match_date"], "2026-06-13")
        self.assertEqual(row["kickoff_time"], "18:00")
        self.assertEqual(row["stadium"], "New York/New Jersey Stadium")
        self.assertEqual(row["confidence"], 1.0)

    def test_page_classifier_recognizes_supported_domains(self) -> None:
        cases = {
            "POST MATCH SUMMARY REPORT": "cover",
            "Match Summary - Key Statistics": "key_statistics",
            "Brazil Phases of Play Morocco": "phases_of_play",
            "Attempts at Goal Brazil": "attempts_at_goal",
            "In Possession - Distributions Brazil": "player_in_possession",
            "Out of Possession Morocco": "player_out_of_possession",
            "Physical Data Brazil": "player_physical",
            "A future unsupported layout": "unknown",
        }

        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(classify_page(text), expected)

    def test_key_statistics_parser_emits_long_form_bilateral_rows(self) -> None:
        text = (
            "Match Summary - Key Statistics\n"
            "1 1\nBrazil Morocco\n"
            "1 Goals 1\n"
            "0.99 xG (Expected Goals) 1.33\n"
            "12 (5) Attempts at Goal (On Target) 14 (3)\n"
            "514 (457) Total Passes (Complete) 503 (431)\n"
            "113.7 km Total Distance Covered 114.9 km"
        )

        rows, issues = parse_key_statistics(
            text,
            teams=("Brazil", "Morocco"),
            document_id="doc-1",
            match_id="match-1",
            source_file="match.pdf",
            page_number=3,
        )

        by_key = {(row["team_name"], row["metric_name"]): row for row in rows}
        self.assertEqual(by_key[("Brazil", "goals")]["value"], 1)
        self.assertEqual(by_key[("Morocco", "expected_goals")]["value"], 1.33)
        self.assertEqual(by_key[("Brazil", "attempts_at_goal")]["value"], 12)
        self.assertEqual(by_key[("Brazil", "attempts_on_target")]["value"], 5)
        self.assertEqual(by_key[("Morocco", "passes_complete")]["value"], 431)
        self.assertEqual(by_key[("Brazil", "total_distance_km")]["value"], 113.7)
        self.assertEqual(issues, [])

    def test_phases_parser_tracks_possession_state_for_both_teams(self) -> None:
        text = (
            "Brazil Phases of Play Morocco\n"
            "IN POSSESSION\n"
            "46% Build Up Unopposed 31%\n"
            "12% Build Up Opposed 14%\n"
            "OUT OF POSSESSION\n"
            "7% High Press 4%\n"
            "16% Mid Block 39%"
        )

        rows = parse_phases_of_play(
            text,
            teams=("Brazil", "Morocco"),
            document_id="doc-1",
            match_id="match-1",
            source_file="match.pdf",
            page_number=4,
        )

        by_key = {
            (row["team_name"], row["possession_state"], row["phase_name"]): row
            for row in rows
        }
        self.assertEqual(
            by_key[("Brazil", "in_possession", "build_up_unopposed")]["percentage"],
            46,
        )
        self.assertEqual(
            by_key[("Morocco", "out_of_possession", "mid_block")]["percentage"],
            39,
        )

    def test_attempt_parser_keeps_outcome_body_part_and_delivery(self) -> None:
        text = (
            "Attempts at Goal Brazil\n"
            "Time Player Outcome Body Part Delivery Type\n"
            "31 7 VINICIUS JUNIOR On Target - Goal Right Foot Ball Progression\n"
            "47 4 MARQUINHOS Off Target Head Corner\n"
            "51 25IGOR THIAGO On Target - Saved Left Foot Other"
        )

        rows, issues = parse_attempts(
            text,
            team_name="Brazil",
            document_id="doc-1",
            match_id="match-1",
            source_file="match.pdf",
            page_number=15,
        )

        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["minute"], 31)
        self.assertEqual(rows[0]["shirt_number"], 7)
        self.assertEqual(rows[0]["player_name"], "VINICIUS JUNIOR")
        self.assertEqual(rows[0]["outcome"], "On Target - Goal")
        self.assertEqual(rows[0]["body_part"], "Right Foot")
        self.assertEqual(rows[0]["delivery_type"], "Ball Progression")
        self.assertEqual(rows[1]["body_part"], "Head")
        self.assertEqual(issues, [])

    def test_private_digit_normalization_and_physical_player_metrics(self) -> None:
        encoded = "\ue072\ue071\ue072\ue071\ue074\ue094\ue078"
        self.assertEqual(normalize_private_digits(encoded), "10103.7")

        text = (
            "Physical Data Brazil\n"
            "# Player Total Distance Zone 1 Zone 2 Zone 3 Zone 4 Zone 5 "
            "High Speed Runs Sprints Top Speed\n"
            "7 VINICIUS JUNIOR "
            "\ue072\ue071\ue072\ue071\ue074\ue094\ue078 "
            "\ue075\ue076\ue075\ue076\ue094\ue072 "
            "\ue074\ue071\ue072\ue07a\ue094\ue076 "
            "\ue072\ue076\ue072\ue079\ue094\ue077 "
            "\ue078\ue075\ue073\ue094\ue07a "
            "\ue073\ue078\ue078\ue094\ue077 "
            "\ue072\ue072\ue078\ue094\ue071 "
            "\ue077\ue071\ue094\ue071 "
            "\ue074\ue075\ue094\ue072"
        )

        rows, issues = parse_player_metrics(
            text,
            domain="player_physical",
            team_name="Brazil",
            document_id="doc-1",
            match_id="match-1",
            source_file="match.pdf",
            page_number=50,
        )

        by_metric = {row["metric_name"]: row for row in rows}
        self.assertEqual(by_metric["total_distance_m"]["player_name"], "VINICIUS JUNIOR")
        self.assertEqual(by_metric["total_distance_m"]["value"], 10103.7)
        self.assertEqual(by_metric["top_speed_kmh"]["value"], 34.1)
        self.assertEqual(by_metric["total_distance_m"]["raw_value"], encoded)
        self.assertEqual(issues, [])


class ExtractorContractTest(unittest.TestCase):
    def test_extractor_preserves_page_text_tables_and_stable_hash(self) -> None:
        expected_hash = hashlib.sha256(PDF_BASE.read_bytes()).hexdigest()

        document = PdfExtractor().extract(PDF_BASE, edition=2026)

        self.assertEqual(document.document_id, expected_hash)
        self.assertEqual(document.sha256, expected_hash)
        self.assertEqual(document.page_count, 52)
        self.assertEqual(document.pages[0].domain, "cover")
        self.assertIn("Brazil 1 - 1 Morocco", document.pages[0].raw_text)
        self.assertTrue(document.pages[2].tables)
        self.assertEqual(document.pages[-1].raw_text, "")


class PipelineIntegrationTest(unittest.TestCase):
    def test_real_pdf_outputs_are_complete_auditable_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bronze = root / "bronze"
            silver = root / "silver"
            pipeline = FifaPdfPipeline(bronze_dir=bronze, silver_dir=silver)

            first = pipeline.process_files([PDF_BASE], edition=2026)
            counts_first = {
                path.name: len(read_csv(path))
                for path in sorted([*bronze.glob("*.csv"), *silver.glob("*.csv")])
            }
            second = pipeline.process_files([PDF_BASE], edition=2026)
            counts_second = {
                path.name: len(read_csv(path))
                for path in sorted([*bronze.glob("*.csv"), *silver.glob("*.csv")])
            }

            self.assertEqual(first.processed, 1)
            self.assertEqual(second.processed, 1)
            self.assertEqual(counts_first, counts_second)
            self.assertEqual(set(counts_first), {
                "attempts_at_goal.csv",
                "documents.csv",
                "extraction_issues.csv",
                "match_summary.csv",
                "pages.csv",
                "phases_of_play.csv",
                "player_metrics.csv",
                "raw_tables.csv",
                "team_key_statistics.csv",
            })
            self.assertEqual(counts_first["documents.csv"], 1)
            self.assertEqual(counts_first["pages.csv"], 52)
            self.assertGreater(counts_first["raw_tables.csv"], 0)
            self.assertEqual(counts_first["match_summary.csv"], 1)
            self.assertGreaterEqual(counts_first["team_key_statistics.csv"], 20)
            self.assertEqual(counts_first["phases_of_play.csv"], 34)
            self.assertEqual(counts_first["attempts_at_goal.csv"], 26)
            self.assertGreater(counts_first["player_metrics.csv"], 0)

            match = read_csv(silver / "match_summary.csv")[0]
            self.assertEqual(match["home_team"], "Brazil")
            self.assertEqual(match["away_team"], "Morocco")
            self.assertEqual(match["edition"], "2026")

            for csv_path in [*bronze.glob("*.csv"), *silver.glob("*.csv")]:
                rows = read_csv(csv_path)
                if rows:
                    self.assertTrue(
                        {
                            "document_id",
                            "match_id",
                            "source_file",
                            "page_number",
                            "confidence",
                        }.issubset(rows[0]),
                        csv_path.name,
                    )

    def test_batch_isolates_invalid_pdf_and_records_issue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            invalid = root / "broken.pdf"
            invalid.write_bytes(b"not a pdf")
            pipeline = FifaPdfPipeline(
                bronze_dir=root / "bronze",
                silver_dir=root / "silver",
            )

            result = pipeline.process_files([invalid, PDF_BASE], edition=2026)
            issues = read_csv(root / "silver" / "extraction_issues.csv")

            self.assertEqual(result.processed, 1)
            self.assertEqual(result.failed, 1)
            self.assertTrue(
                any(
                    row["source_file"] == "broken.pdf"
                    and row["severity"] == "error"
                    for row in issues
                )
            )

    def test_csv_storage_escapes_null_bytes_from_pdf_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pipeline = FifaPdfPipeline(
                bronze_dir=root / "bronze",
                silver_dir=root / "silver",
            )

            pipeline.process_files([PDF_BASE], edition=2026)

            pages = read_csv(root / "bronze" / "pages.csv")
            cover = next(row for row in pages if row["page_number"] == "1")
            self.assertNotIn("\x00", cover["raw_text"])
            self.assertIn("\\x00", cover["raw_text"])

    def test_snapshot_saves_manifest_and_all_parsed_products(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = create_snapshot(
                source_file=PDF_BASE,
                edition=2026,
                output_root=Path(temp_dir),
                run_id="test-run",
            )

            manifest = json.loads(
                (run_dir / "manifest.json").read_text(encoding="utf-8")
            )

            self.assertEqual(manifest["run_id"], "test-run")
            self.assertEqual(manifest["status"], "succeeded")
            self.assertEqual(manifest["source"]["sha256"], manifest["document_id"])
            self.assertEqual(manifest["summary"]["processed"], 1)
            self.assertEqual(manifest["summary"]["failed"], 0)
            self.assertEqual(manifest["datasets"]["bronze/pages"]["row_count"], 52)
            self.assertEqual(
                manifest["datasets"]["silver/attempts_at_goal"]["row_count"],
                26,
            )
            self.assertEqual(len(manifest["datasets"]), 9)
            self.assertGreaterEqual(manifest["quality"]["issues_total"], 1)
            self.assertIn("python", manifest["environment"])
            self.assertTrue((run_dir / "execution.txt").exists())

            for dataset in manifest["datasets"].values():
                product = run_dir / dataset["path"]
                self.assertTrue(product.exists())
                self.assertEqual(
                    hashlib.sha256(product.read_bytes()).hexdigest(),
                    dataset["sha256"],
                )

    def test_publication_creates_partitioned_sports_products(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = publish_match_pdf(
                source_file=PDF_BASE,
                edition=2026,
                output_root=Path(temp_dir),
            )

            expected = Path(temp_dir) / "year=2026" / "match=7"
            self.assertEqual(result.path, expected)
            self.assertEqual(result.status, "published")
            self.assertEqual(
                {path.stem for path in expected.glob("*.csv")},
                set(PRODUCT_NAMES),
            )
            self.assertTrue((expected / "_manifest.json").exists())

            for path in expected.glob("*.csv"):
                with path.open(encoding="utf-8", newline="") as handle:
                    fields = csv.DictReader(handle).fieldnames or []
                self.assertNotIn("document_id", fields)
                self.assertNotIn("source_file", fields)
                self.assertNotIn("sha256", fields)

            dictionary = read_csv(expected / "data_dictionary.csv")
            self.assertEqual(
                {row["product"] for row in dictionary},
                set(PRODUCT_NAMES) - {"data_dictionary"},
            )

            manifest = json.loads(
                (expected / "_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["version"], 1)
            self.assertEqual(manifest["match_number"], 7)

            repeated = publish_match_pdf(
                source_file=PDF_BASE,
                edition=2026,
                output_root=Path(temp_dir),
            )
            self.assertEqual(repeated.status, "unchanged")
            repeated_manifest = json.loads(
                (expected / "_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(repeated_manifest["version"], 1)


class CliContractTest(unittest.TestCase):
    def test_cli_defaults_follow_edition_layer_paths(self) -> None:
        parser = build_parser()

        directory_args = parser.parse_args(
            ["--input-dir", "data/pdf/inbox", "--edition", "2026"]
        )
        file_args = parser.parse_args(
            [
                "--file",
                "data/pdf/PMSR-M07-BRA-V-MAR.pdf",
                "--edition",
                "2026",
            ]
        )

        self.assertEqual(directory_args.input_dir, Path("data/pdf/inbox"))
        self.assertIsNone(directory_args.file)
        self.assertEqual(file_args.file, PDF_BASE.relative_to(ROOT))
        self.assertEqual(directory_args.edition, 2026)
        self.assertIsNone(directory_args.bronze_dir)
        self.assertIsNone(directory_args.silver_dir)


class DataDictionaryContractTest(unittest.TestCase):
    def test_dictionary_csv_covers_every_dataset_specific_field(self) -> None:
        dictionary_path = ROOT / "docs" / "fifa_pdf_data_dictionary.csv"
        rows = read_csv(dictionary_path)
        common = {row["field"] for row in rows if row["dataset"] == "*"}

        for dataset, config in DATASETS.items():
            documented = common | {
                row["field"] for row in rows if row["dataset"] == dataset
            }
            self.assertTrue(
                set(config["fields"]).issubset(documented),
                f"Missing fields for {dataset}: "
                f"{sorted(set(config['fields']) - documented)}",
            )


if __name__ == "__main__":
    unittest.main()
