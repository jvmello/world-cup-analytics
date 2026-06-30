from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .ingestion import default_ingestion
from .opening_match_smoke import FIXTURES_ROOT, match_id, read_fixture_rows


CONTEXT_ENDPOINTS = ("match_detail", "match_referee")
OVERVIEW_ENDPOINTS = ("match_stats",)
ANALYTICAL_ENDPOINTS = (
    "lineups",
    "match_stats",
    "player_stats",
    "events",
    "shotmap",
)
FINISHED_STATUSES = {
    "finished",
    "completed",
    "full_time",
    "after_extra_time",
    "after_penalties",
}


def _group_key(value: object) -> str:
    key = " ".join(str(value or "").casefold().split())
    if key.startswith("group "):
        return key.removeprefix("group ").strip()
    if key.startswith("grupo "):
        return key.removeprefix("grupo ").strip()
    return key


def select_group_stage_matches(
    rows: list[dict[str, Any]],
    *,
    groups: tuple[str, ...] = (),
    limit: int | None = None,
) -> list[dict[str, Any]]:
    wanted_groups = {_group_key(group) for group in groups if _group_key(group)}
    selected = [
        row
        for row in rows
        if _group_key(row.get("group_label"))
        and (
            not wanted_groups
            or _group_key(row.get("group_label")) in wanted_groups
        )
    ]
    selected.sort(
        key=lambda row: (
            str(row.get("utc_date") or row.get("kickoff_utc") or ""),
            str(match_id(row) or ""),
        )
    )
    if limit is not None:
        return selected[:limit]
    return selected


def endpoints_for_match(
    fixture: dict[str, Any],
    *,
    profile: str,
) -> tuple[str, ...]:
    if profile == "metadata":
        return CONTEXT_ENDPOINTS
    if profile not in {"overview", "available"}:
        raise ValueError(f"Unknown group-stage extraction profile: {profile}")

    status = str(fixture.get("status") or "").casefold()
    if status in FINISHED_STATUSES:
        if profile == "overview":
            return (*CONTEXT_ENDPOINTS, *OVERVIEW_ENDPOINTS)
        return (*CONTEXT_ENDPOINTS, *ANALYTICAL_ENDPOINTS)
    return CONTEXT_ENDPOINTS


def run_group_stage_batch(
    ingestion: Any,
    rows: list[dict[str, Any]],
    *,
    profile: str,
    force: bool,
    groups: tuple[str, ...] = (),
    limit: int | None = None,
    request_interval_seconds: float = 5.2,
    sleep_fn: Callable[[float], None] = time.sleep,
    progress_fn: Callable[[int, int, dict[str, Any], tuple[str, ...]], None]
    | None = None,
) -> dict[str, int]:
    selected = select_group_stage_matches(rows, groups=groups, limit=limit)
    counters: Counter[str] = Counter(matches_selected=len(selected))

    for index, fixture in enumerate(selected, start=1):
        selected_match_id = match_id(fixture)
        endpoints = endpoints_for_match(fixture, profile=profile)
        counters["matches_processed"] += 1
        counters["endpoints_planned"] += len(endpoints)
        if progress_fn:
            progress_fn(index, len(selected), fixture, endpoints)
        if not selected_match_id:
            counters["failed"] += len(endpoints)
            continue

        for endpoint_name in endpoints:
            try:
                result = ingestion.fetch_match_bundle(
                    selected_match_id,
                    force=force,
                    endpoints=(endpoint_name,),
                )
            except Exception:  # The next match must remain independently runnable.
                counters["failed"] += 1
                continue

            counters.update(result)
            request_was_made = not result.get("skipped")
            if request_was_made and request_interval_seconds > 0:
                sleep_fn(request_interval_seconds)

    return dict(counters)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch a resumable TheStatsAPI batch for World Cup 2026 groups."
    )
    parser.add_argument(
        "--profile",
        choices=("metadata", "overview", "available"),
        default="overview",
        help=(
            "metadata fetches context for every group match; overview adds "
            "match stats; available adds every analytical endpoint."
        ),
    )
    parser.add_argument(
        "--group",
        action="append",
        default=[],
        help="Restrict the batch to one group letter. May be repeated.",
    )
    parser.add_argument("--limit", type=int, help="Limit matches for a pilot run.")
    parser.add_argument(
        "--request-interval",
        type=float,
        default=5.2,
        help="Seconds between API requests. Skipped endpoints do not wait.",
    )
    parser.add_argument(
        "--refresh-fixtures",
        action="store_true",
        help="Refresh fixtures before selecting group-stage matches.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Fetch match endpoints again even when successful Bronze data exists.",
    )
    return parser


def _progress(
    index: int,
    total: int,
    fixture: dict[str, Any],
    endpoints: tuple[str, ...],
) -> None:
    group = fixture.get("group_label") or "-"
    status = fixture.get("status") or "unknown"
    print(
        f"[{index}/{total}] match_id={match_id(fixture)} "
        f"group={group} status={status} endpoints={len(endpoints)}",
        file=sys.stderr,
        flush=True,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    fixtures_root: Path = FIXTURES_ROOT,
) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be greater than zero")
    if args.request_interval < 0:
        raise SystemExit("--request-interval cannot be negative")

    ingestion = default_ingestion()
    if args.refresh_fixtures:
        core_result = ingestion.fetch_fixtures(force=True)
        core_result.update(ingestion.fetch_standings(force=False))
    else:
        core_result = ingestion.fetch_core(force=False)

    rows = read_fixture_rows(fixtures_root)
    summary = run_group_stage_batch(
        ingestion,
        rows,
        profile=args.profile,
        force=args.force,
        groups=tuple(args.group),
        limit=args.limit,
        request_interval_seconds=args.request_interval,
        progress_fn=_progress,
    )
    output = {
        "profile": args.profile,
        "groups": args.group or "all",
        "core_result": core_result,
        "batch_result": summary,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
