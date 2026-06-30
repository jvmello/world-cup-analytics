from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .models import PARSER_VERSION
from .pipeline import FifaPdfPipeline
from .storage import DATASETS


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _row_count(path: Path) -> int:
    with path.open(encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _safe_run_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value):
        raise ValueError(
            "run_id must contain only letters, numbers, dots, underscores, or hyphens"
        )
    return value


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _git_context(project_root: Path) -> dict[str, object]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def create_snapshot(
    *,
    source_file: Path | str,
    edition: int,
    output_root: Path | str = Path("data/runs/fifa_pdf"),
    run_id: str | None = None,
) -> Path:
    source = Path(source_file).resolve()
    selected_run_id = _safe_run_id(run_id or _default_run_id())
    run_dir = Path(output_root) / str(edition) / selected_run_id
    if run_dir.exists():
        raise FileExistsError(f"Snapshot directory already exists: {run_dir}")

    bronze_dir = run_dir / "bronze"
    silver_dir = run_dir / "silver"
    run_dir.mkdir(parents=True)
    started_at = datetime.now(timezone.utc)

    pipeline = FifaPdfPipeline(
        bronze_dir=bronze_dir,
        silver_dir=silver_dir,
    )
    result = pipeline.process_files([source], edition=edition)
    finished_at = datetime.now(timezone.utc)

    products: dict[str, dict[str, object]] = {}
    for name, config in DATASETS.items():
        layer = str(config["layer"])
        product = run_dir / layer / f"{name}.csv"
        products[f"{layer}/{name}"] = {
            "layer": layer,
            "dataset": name,
            "path": product.relative_to(run_dir).as_posix(),
            "row_count": _row_count(product),
            "column_count": len(config["fields"]),
            "fields": list(config["fields"]),
            "primary_key": list(config["key"]),
            "byte_size": product.stat().st_size,
            "sha256": _sha256(product),
        }

    document_rows = []
    documents_path = bronze_dir / "documents.csv"
    with documents_path.open(encoding="utf-8", newline="") as handle:
        document_rows = list(csv.DictReader(handle))
    document = document_rows[0] if document_rows else {}
    source_hash = _sha256(source)
    status = "succeeded" if result.failed == 0 and result.processed == 1 else "failed"
    project_root = Path(__file__).resolve().parents[2]
    requirements = project_root / "requirements.txt"
    issues_path = silver_dir / "extraction_issues.csv"
    issues_by_severity: dict[str, int] = {}
    issues_by_type: dict[str, int] = {}
    with issues_path.open(encoding="utf-8", newline="") as handle:
        issue_rows = list(csv.DictReader(handle))
    for issue in issue_rows:
        severity = issue.get("severity", "")
        issue_type = issue.get("issue_type", "")
        issues_by_severity[severity] = issues_by_severity.get(severity, 0) + 1
        issues_by_type[issue_type] = issues_by_type.get(issue_type, 0) + 1

    manifest = {
        "run_id": selected_run_id,
        "status": status,
        "edition": edition,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round(
            (finished_at - started_at).total_seconds(), 3
        ),
        "parser_version": document.get("parser_version") or PARSER_VERSION,
        "document_id": document.get("document_id") or source_hash,
        "match_id": document.get("match_id") or None,
        "source": {
            "path": str(source),
            "file_name": source.name,
            "sha256": source_hash,
            "byte_size": source.stat().st_size,
        },
        "parameters": {
            "edition": edition,
            "source_file": str(source),
            "output_root": str(Path(output_root)),
            "run_id": selected_run_id,
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "pdfplumber": importlib.metadata.version("pdfplumber"),
            "requirements_sha256": (
                _sha256(requirements) if requirements.exists() else None
            ),
            "git": _git_context(project_root),
        },
        "quality": {
            "issues_total": len(issue_rows),
            "issues_by_severity": dict(sorted(issues_by_severity.items())),
            "issues_by_type": dict(sorted(issues_by_type.items())),
        },
        "summary": {
            "processed": result.processed,
            "failed": result.failed,
            "dataset_count": len(products),
            "total_rows": sum(
                int(product["row_count"]) for product in products.values()
            ),
        },
        "datasets": products,
        "command": (
            "python -m fifa_pdf.snapshot "
            f"--file {source} --edition {edition} "
            f"--output-root {Path(output_root)} --run-id {selected_run_id}"
        ),
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [
        f"run_id={selected_run_id}",
        f"status={status}",
        f"edition={edition}",
        f"source={source}",
        f"source_sha256={source_hash}",
        f"document_id={manifest['document_id']}",
        f"match_id={manifest['match_id'] or ''}",
        f"parser_version={manifest['parser_version']}",
        f"started_at={manifest['started_at']}",
        f"finished_at={manifest['finished_at']}",
        f"duration_seconds={manifest['duration_seconds']}",
        f"processed={result.processed}",
        f"failed={result.failed}",
        f"issues_total={manifest['quality']['issues_total']}",
        "",
        "products:",
    ]
    lines.extend(
        (
            f"- {key}: rows={product['row_count']} "
            f"sha256={product['sha256']} path={product['path']}"
        )
        for key, product in sorted(products.items())
    )
    (run_dir / "execution.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    if status != "succeeded":
        raise RuntimeError(
            f"FIFA PDF snapshot failed; audit package saved at {run_dir}"
        )
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the FIFA PDF parser and save an immutable audit snapshot."
    )
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--edition", required=True, type=int, choices=(2026,))
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/runs/fifa_pdf"),
    )
    parser.add_argument("--run-id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dir = create_snapshot(
        source_file=args.file,
        edition=args.edition,
        output_root=args.output_root,
        run_id=args.run_id,
    )
    print(f"FIFA PDF snapshot saved: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
