from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from dotenv import load_dotenv

from .config import MATCH_BUNDLE_ENDPOINTS
from .ingestion import default_ingestion


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch a World Cup 2026 match bundle from TheStatsAPI."
    )
    parser.add_argument("--match-id", required=True, help="TheStatsAPI match_id.")
    parser.add_argument(
        "--endpoint",
        action="append",
        choices=MATCH_BUNDLE_ENDPOINTS,
        help=(
            "Fetch only this endpoint. Can be passed multiple times. "
            "Defaults to the whole bundle."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Fetch again even when successful jobs and raw Bronze files exist.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    endpoints = tuple(args.endpoint) if args.endpoint else MATCH_BUNDLE_ENDPOINTS
    ingestion = default_ingestion()
    result = ingestion.fetch_match_bundle(
        args.match_id,
        force=args.force,
        endpoints=endpoints,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
