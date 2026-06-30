from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description=(
            "Prepare the TheStatsAPI Silver step. This first integration stores "
            "raw Bronze JSON only; Silver contracts are intentionally pending "
            "real response validation."
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    print(
        "TheStatsAPI Silver is prepared but not materialized yet. "
        "Validate real Bronze response shapes before normalizing."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
