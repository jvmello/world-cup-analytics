from __future__ import annotations

from collections.abc import Sequence

from .serving import main as serving_main


def main(argv: Sequence[str] | None = None) -> int:
    return serving_main(list(argv) if argv is not None else None)


if __name__ == "__main__":
    raise SystemExit(main())
