from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from dotenv import load_dotenv

from .ingestion import default_ingestion


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch World Cup 2026 fixtures and standings from TheStatsAPI."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Fetch again even when a successful job and raw Bronze file exist.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    ingestion = default_ingestion()
    result = ingestion.fetch_core(force=args.force)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
