from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .pipeline import FifaPdfPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Process FIFA post-match PDF reports into auditable CSV layers."
    )
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--input-dir", type=Path)
    inputs.add_argument("--file", type=Path)
    parser.add_argument("--edition", type=int, required=True, choices=(2026,))
    parser.add_argument("--bronze-dir", type=Path)
    parser.add_argument("--silver-dir", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_dir = args.input_dir or Path("data/pdf/inbox")
    bronze_dir = args.bronze_dir or Path(
        f"data/bronze/fifa_pdf/world_cup/{args.edition}"
    )
    silver_dir = args.silver_dir or Path(
        f"data/silver/fifa_pdf/world_cup/{args.edition}"
    )
    pipeline = FifaPdfPipeline(bronze_dir=bronze_dir, silver_dir=silver_dir)
    if args.file:
        result = pipeline.process_files([args.file], edition=args.edition)
    else:
        result = pipeline.process_directory(input_dir, edition=args.edition)
    print(
        f"FIFA PDF pipeline: processed={result.processed} failed={result.failed} "
        f"bronze={bronze_dir} silver={silver_dir}"
    )
    return 1 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
