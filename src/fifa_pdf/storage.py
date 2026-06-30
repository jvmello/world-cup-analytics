from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any, Iterable


COMMON = [
    "document_id",
    "match_id",
    "source_file",
    "page_number",
    "confidence",
]

DATASETS = {
    "documents": {
        "layer": "bronze",
        "fields": COMMON
        + [
            "sha256",
            "source_path",
            "edition",
            "parser_version",
            "status",
            "page_count",
            "metadata_json",
        ],
        "key": ("document_id",),
    },
    "pages": {
        "layer": "bronze",
        "fields": COMMON + ["domain", "width", "height", "raw_text"],
        "key": ("document_id", "page_number"),
    },
    "raw_tables": {
        "layer": "bronze",
        "fields": COMMON
        + ["table_number", "row_number", "column_number", "raw_value"],
        "key": (
            "document_id",
            "page_number",
            "table_number",
            "row_number",
            "column_number",
        ),
    },
    "match_summary": {
        "layer": "silver",
        "fields": COMMON
        + [
            "edition",
            "group_name",
            "match_number",
            "match_date",
            "kickoff_time",
            "stadium",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "data_coverage_level",
        ],
        "key": ("document_id", "match_id"),
    },
    "team_key_statistics": {
        "layer": "silver",
        "fields": COMMON
        + ["team_name", "metric_name", "value", "unit", "raw_value"],
        "key": ("document_id", "match_id", "team_name", "metric_name"),
    },
    "phases_of_play": {
        "layer": "silver",
        "fields": COMMON
        + [
            "team_name",
            "possession_state",
            "phase_name",
            "percentage",
            "raw_value",
        ],
        "key": (
            "document_id",
            "match_id",
            "team_name",
            "possession_state",
            "phase_name",
        ),
    },
    "attempts_at_goal": {
        "layer": "silver",
        "fields": COMMON
        + [
            "attempt_id",
            "team_name",
            "minute",
            "shirt_number",
            "player_name",
            "outcome",
            "body_part",
            "delivery_type",
            "raw_value",
        ],
        "key": ("document_id", "attempt_id"),
    },
    "player_metrics": {
        "layer": "silver",
        "fields": COMMON
        + [
            "team_name",
            "shirt_number",
            "player_name",
            "metric_group",
            "metric_name",
            "value",
            "unit",
            "raw_value",
        ],
        "key": (
            "document_id",
            "match_id",
            "team_name",
            "shirt_number",
            "metric_group",
            "metric_name",
        ),
    },
    "extraction_issues": {
        "layer": "silver",
        "fields": COMMON
        + [
            "issue_id",
            "severity",
            "issue_type",
            "message",
            "raw_value",
        ],
        "key": ("issue_id",),
    },
}


class CsvStore:
    def __init__(self, bronze_dir: Path | str, silver_dir: Path | str) -> None:
        self.bronze_dir = Path(bronze_dir)
        self.silver_dir = Path(silver_dir)

    def ensure_all(self) -> None:
        for dataset in DATASETS:
            self.upsert(dataset, [])

    @staticmethod
    def _csv_value(value: Any) -> str:
        if value is None:
            return ""
        return str(value).replace("\x00", "\\x00")

    def upsert(self, dataset: str, rows: Iterable[dict[str, Any]]) -> None:
        config = DATASETS[dataset]
        directory = self.bronze_dir if config["layer"] == "bronze" else self.silver_dir
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{dataset}.csv"
        fields = config["fields"]
        key_fields = config["key"]
        merged: dict[tuple[str, ...], dict[str, str]] = {}

        if path.exists():
            with path.open(encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    merged[tuple(row.get(field, "") for field in key_fields)] = row

        for source_row in rows:
            row = {
                field: self._csv_value(source_row.get(field))
                for field in fields
            }
            key = tuple(row[field] for field in key_fields)
            merged[key] = row

        temporary = path.with_suffix(".csv.tmp")
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(merged[key] for key in sorted(merged))
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
