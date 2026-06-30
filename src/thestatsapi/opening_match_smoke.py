from __future__ import annotations

import argparse
import json
import unicodedata
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .ingestion import default_ingestion


DEFAULT_HOME_TEAM = "Mexico"
DEFAULT_AWAY_TEAM = "South Africa"
FIXTURES_ROOT = Path("data/bronze/thestatsapi/world_cup/2026/fixtures")
TEAM_ALIASES = {
    "africa do sul": "south africa",
    "africa sul": "south africa",
    "mexico": "mexico",
}


def normalize_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    normalized = " ".join(text.casefold().split())
    return TEAM_ALIASES.get(normalized, normalized)


def team_name(match: dict[str, Any], side: str) -> str | None:
    value = match.get(f"{side}_team") or match.get(side)
    if isinstance(value, dict):
        return value.get("name")
    if isinstance(value, str):
        return value
    return None


def match_id(match: dict[str, Any]) -> str | None:
    value = match.get("id") or match.get("match_id") or match.get("fixture_id")
    return str(value) if value else None


def read_fixture_rows(fixtures_root: Path = FIXTURES_ROOT) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(fixtures_root.glob("page=*/response.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        data = payload.get("data") if isinstance(payload, dict) else payload
        if isinstance(data, list):
            rows.extend(item for item in data if isinstance(item, dict))
    return rows


def find_match_by_teams(
    rows: list[dict[str, Any]],
    *,
    home_team: str,
    away_team: str,
) -> dict[str, Any] | None:
    wanted_home = normalize_name(home_team)
    wanted_away = normalize_name(away_team)
    candidates = []
    for row in rows:
        home = normalize_name(team_name(row, "home"))
        away = normalize_name(team_name(row, "away"))
        if home == wanted_home and away == wanted_away:
            candidates.append(row)
    if not candidates:
        return None
    return sorted(candidates, key=lambda row: str(row.get("utc_date") or ""))[0]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch fixtures and the full TheStatsAPI bundle for the World Cup "
            "2026 opening match."
        )
    )
    parser.add_argument("--home-team", default=DEFAULT_HOME_TEAM)
    parser.add_argument("--away-team", default=DEFAULT_AWAY_TEAM)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force fixtures and match bundle requests even when Bronze exists.",
    )
    parser.add_argument(
        "--force-fixtures",
        action="store_true",
        help="Force only the schedule/fixtures request.",
    )
    parser.add_argument(
        "--force-bundle",
        action="store_true",
        help="Force only the match bundle requests.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    ingestion = default_ingestion()
    core_result = ingestion.fetch_core(
        force=args.force or args.force_fixtures
    )
    rows = read_fixture_rows()
    selected = find_match_by_teams(
        rows,
        home_team=args.home_team,
        away_team=args.away_team,
    )
    if not selected:
        raise SystemExit(
            f"Opening fixture not found: {args.home_team} x {args.away_team}"
        )

    selected_match_id = match_id(selected)
    if not selected_match_id:
        raise SystemExit(f"Opening fixture has no match id: {selected}")

    bundle_result = ingestion.fetch_match_bundle(
        selected_match_id,
        force=args.force or args.force_bundle,
    )
    summary = {
        "fixture": {
            "match_id": selected_match_id,
            "utc_date": selected.get("utc_date") or selected.get("kickoff_utc"),
            "home_team": team_name(selected, "home"),
            "away_team": team_name(selected, "away"),
            "status": selected.get("status"),
            "group_label": selected.get("group_label"),
            "score": selected.get("score"),
            "xg_available": selected.get("xg_available"),
        },
        "core_result": core_result,
        "bundle_result": bundle_result,
        "bronze_match_path": (
            "data/bronze/thestatsapi/world_cup/2026/matches/"
            f"match_id={selected_match_id}/"
        ),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
