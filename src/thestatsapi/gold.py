from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=(
            "Prepare the TheStatsAPI Gold step. This first integration stores "
            "raw Bronze JSON only; Gold contracts are intentionally pending "
            "Silver normalization."
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    print(
        "TheStatsAPI Gold is prepared but not materialized yet. "
        "Build Silver contracts from validated Bronze before publishing Gold."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
