from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pdfplumber

from .models import ExtractedDocument, ExtractedPage, ExtractedTable
from .parsers import classify_page


logging.getLogger("pdfminer").setLevel(logging.ERROR)


class PdfExtractor:
    """Extract text and tables without discarding the original cell values."""

    def extract(self, path: Path | str, edition: int) -> ExtractedDocument:
        source_path = Path(path)
        payload = source_path.read_bytes()
        sha256 = hashlib.sha256(payload).hexdigest()
        pages: list[ExtractedPage] = []

        with pdfplumber.open(source_path) as pdf:
            metadata = dict(pdf.metadata or {})
            for page_number, page in enumerate(pdf.pages, start=1):
                raw_text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
                extracted_tables = []
                for table_number, table in enumerate(page.extract_tables() or []):
                    rows = [
                        ["" if cell is None else str(cell) for cell in row]
                        for row in table
                    ]
                    extracted_tables.append(
                        ExtractedTable(table_number=table_number, rows=rows)
                    )
                pages.append(
                    ExtractedPage(
                        page_number=page_number,
                        raw_text=raw_text,
                        domain=classify_page(raw_text),
                        width=float(page.width),
                        height=float(page.height),
                        tables=extracted_tables,
                    )
                )

        return ExtractedDocument(
            document_id=sha256,
            sha256=sha256,
            source_path=source_path,
            source_file=source_path.name,
            edition=edition,
            page_count=len(pages),
            metadata=metadata,
            pages=pages,
        )
