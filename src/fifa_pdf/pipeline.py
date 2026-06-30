from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

from .extractor import PdfExtractor
from .models import ExtractedDocument, PipelineResult
from .parsers import (
    issue_row,
    parse_attempts,
    parse_cover,
    parse_key_statistics,
    parse_phases_of_play,
    parse_player_metrics,
)
from .storage import CsvStore


class FifaPdfPipeline:
    def __init__(
        self,
        *,
        bronze_dir: Path | str,
        silver_dir: Path | str,
        extractor: PdfExtractor | None = None,
    ) -> None:
        self.extractor = extractor or PdfExtractor()
        self.store = CsvStore(bronze_dir, silver_dir)

    def process_directory(self, input_dir: Path | str, edition: int) -> PipelineResult:
        paths = sorted(Path(input_dir).glob("*.pdf"))
        return self.process_files(paths, edition=edition)

    def process_files(
        self, paths: Iterable[Path | str], edition: int
    ) -> PipelineResult:
        self.store.ensure_all()
        processed = 0
        failed = 0
        for raw_path in paths:
            path = Path(raw_path)
            try:
                document = self.extractor.extract(path, edition=edition)
                datasets = self.parse_document(document)
                for dataset, rows in datasets.items():
                    self.store.upsert(dataset, rows)
                processed += 1
            except Exception as exc:
                failed += 1
                document_id = self._best_effort_hash(path)
                self.store.upsert(
                    "extraction_issues",
                    [
                        issue_row(
                            document_id=document_id,
                            match_id="",
                            source_file=path.name,
                            page_number=0,
                            severity="error",
                            issue_type="document_processing_failed",
                            message=f"{type(exc).__name__}: {exc}",
                            confidence=0.0,
                        )
                    ],
                )
        return PipelineResult(processed=processed, failed=failed)

    @staticmethod
    def _best_effort_hash(path: Path) -> str:
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return hashlib.sha256(str(path).encode("utf-8")).hexdigest()

    def parse_document(
        self, document: ExtractedDocument
    ) -> dict[str, list[dict[str, object]]]:
        datasets: dict[str, list[dict[str, object]]] = {
            "documents": [],
            "pages": [],
            "raw_tables": [],
            "match_summary": [],
            "team_key_statistics": [],
            "phases_of_play": [],
            "attempts_at_goal": [],
            "player_metrics": [],
            "extraction_issues": [],
        }
        cover_page = next(
            (page for page in document.pages if page.domain == "cover"),
            document.pages[0] if document.pages else None,
        )
        if cover_page is None:
            raise ValueError("PDF contains no pages")
        match = parse_cover(
            cover_page.raw_text,
            document_id=document.document_id,
            source_file=document.source_file,
            page_number=cover_page.page_number,
            edition=document.edition,
        )
        match_id = str(match["match_id"])
        teams = (str(match["home_team"]), str(match["away_team"]))
        datasets["match_summary"].append(match)
        datasets["documents"].append(
            {
                "document_id": document.document_id,
                "match_id": match_id,
                "source_file": document.source_file,
                "page_number": 0,
                "confidence": 1.0,
                "sha256": document.sha256,
                "source_path": str(document.source_path),
                "edition": document.edition,
                "parser_version": document.parser_version,
                "status": "processed",
                "page_count": document.page_count,
                "metadata_json": json.dumps(
                    document.metadata, ensure_ascii=False, sort_keys=True
                ),
            }
        )

        for page in document.pages:
            common = {
                "document_id": document.document_id,
                "match_id": match_id,
                "source_file": document.source_file,
                "page_number": page.page_number,
                "confidence": 1.0 if page.raw_text else 0.5,
            }
            datasets["pages"].append(
                {
                    **common,
                    "domain": page.domain,
                    "width": page.width,
                    "height": page.height,
                    "raw_text": page.raw_text,
                }
            )
            for table in page.tables:
                for row_number, row in enumerate(table.rows):
                    for column_number, raw_value in enumerate(row):
                        datasets["raw_tables"].append(
                            {
                                **common,
                                "table_number": table.table_number,
                                "row_number": row_number,
                                "column_number": column_number,
                                "raw_value": raw_value,
                            }
                        )

            if page.domain == "key_statistics":
                rows, issues = parse_key_statistics(
                    page.raw_text,
                    teams=teams,
                    document_id=document.document_id,
                    match_id=match_id,
                    source_file=document.source_file,
                    page_number=page.page_number,
                )
                datasets["team_key_statistics"].extend(rows)
                datasets["extraction_issues"].extend(issues)
            elif page.domain == "phases_of_play":
                datasets["phases_of_play"].extend(
                    parse_phases_of_play(
                        page.raw_text,
                        teams=teams,
                        document_id=document.document_id,
                        match_id=match_id,
                        source_file=document.source_file,
                        page_number=page.page_number,
                    )
                )
            elif page.domain == "attempts_at_goal":
                team_name = self._team_from_page(page.raw_text, teams)
                rows, issues = parse_attempts(
                    page.raw_text,
                    team_name=team_name,
                    document_id=document.document_id,
                    match_id=match_id,
                    source_file=document.source_file,
                    page_number=page.page_number,
                )
                datasets["attempts_at_goal"].extend(rows)
                datasets["extraction_issues"].extend(issues)
            elif page.domain.startswith("player_"):
                team_name = self._team_from_page(page.raw_text, teams)
                rows, issues = parse_player_metrics(
                    page.raw_text,
                    domain=page.domain,
                    team_name=team_name,
                    document_id=document.document_id,
                    match_id=match_id,
                    source_file=document.source_file,
                    page_number=page.page_number,
                )
                datasets["player_metrics"].extend(rows)
                datasets["extraction_issues"].extend(issues)
            elif page.domain == "blank":
                datasets["extraction_issues"].append(
                    issue_row(
                        document_id=document.document_id,
                        match_id=match_id,
                        source_file=document.source_file,
                        page_number=page.page_number,
                        severity="warning",
                        issue_type="blank_page",
                        message="Page contains no extractable text",
                        confidence=0.5,
                    )
                )
            elif page.domain == "unknown":
                datasets["extraction_issues"].append(
                    issue_row(
                        document_id=document.document_id,
                        match_id=match_id,
                        source_file=document.source_file,
                        page_number=page.page_number,
                        severity="info",
                        issue_type="unsupported_domain",
                        message="Page preserved as raw data without a domain parser",
                        raw_value=page.raw_text[:500],
                        confidence=0.5,
                    )
                )
        return datasets

    _parse_document = parse_document

    @staticmethod
    def _team_from_page(text: str, teams: tuple[str, str]) -> str:
        for team in teams:
            if re_search_word(team, text):
                return team
        return ""


def re_search_word(value: str, text: str) -> bool:
    import re

    return re.search(rf"\b{re.escape(value)}\b", text, re.I) is not None
