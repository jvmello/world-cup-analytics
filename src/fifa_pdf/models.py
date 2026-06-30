from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PARSER_VERSION = "1.1.3"


@dataclass(frozen=True)
class ExtractedTable:
    table_number: int
    rows: list[list[str]]


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    raw_text: str
    domain: str
    width: float
    height: float
    tables: list[ExtractedTable] = field(default_factory=list)


@dataclass(frozen=True)
class ExtractedDocument:
    document_id: str
    sha256: str
    source_path: Path
    source_file: str
    edition: int
    page_count: int
    metadata: dict[str, Any]
    pages: list[ExtractedPage]
    parser_version: str = PARSER_VERSION


@dataclass(frozen=True)
class PipelineResult:
    processed: int = 0
    failed: int = 0
