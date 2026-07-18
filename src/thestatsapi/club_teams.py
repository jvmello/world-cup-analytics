from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from dotenv import load_dotenv

from .ingestion import default_ingestion


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve club names (/football/teams/{team_id}) for every club_team_id "
            "seen in ingested player-stats. One call per distinct club, idempotent."
        )
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Fetch again even when a successful job and raw Bronze file exist.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=5.0,
        help="Pause between requests (rate limit da conta: ~12 requisições/min).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    ingestion = default_ingestion()
    result = ingestion.fetch_club_teams(force=args.force, pause_seconds=args.interval_seconds)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
