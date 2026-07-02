from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from webapp.thestatsapi_service import TheStatsApiBronzeService


MATCH_FIELDS = (
    "match_id", "player_id", "player_name", "team_id", "team_name",
    "api_position_group", "formation", "is_starter", "minutes_played",
    "inferred_role", "inferred_side", "role_source", "role_confidence",
    "slot_index", "slot_label", "formation_mapped", "lineup_order_reliable",
)
TOURNAMENT_FIELDS = (
    "player_id", "player_name", "team_id", "team_name", "api_position_group",
    "primary_inferred_role", "primary_inferred_side", "secondary_inferred_roles",
    "role_minutes_breakdown", "role_source_summary", "role_confidence",
    "is_multifunctional", "total_minutes", "review_status", "resolved_position",
    "benchmark_position", "benchmark_label", "benchmark_sample_size",
)


def _select(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: row.get(field) for field in fields}


def build_position_report(
    year: int,
    details: list[dict[str, Any]],
    tournament_players: list[dict[str, Any]],
) -> dict[str, Any]:
    match_roles = [
        _select(player, MATCH_FIELDS)
        for detail in details
        for player in detail.get("players", [])
        if player.get("player_id")
    ]
    tournament_roles = [
        _select(player, TOURNAMENT_FIELDS)
        for player in tournament_players
        if player.get("player_id")
    ]
    confidence = Counter(str(row.get("role_confidence") or "unknown") for row in tournament_roles)
    sources = Counter(str(row.get("role_source") or "unknown") for row in match_roles)
    reviews = Counter(str(row.get("review_status") or "unknown") for row in tournament_roles)
    return {
        "year": year,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "match_roles": len(match_roles),
            "players": len(tournament_roles),
            "lineup_order_reliable": sum(bool(row.get("lineup_order_reliable")) for row in match_roles),
            "formation_unmapped": sum(not bool(row.get("formation_mapped")) for row in match_roles),
            "confidence": dict(sorted(confidence.items())),
            "sources": dict(sorted(sources.items())),
            "review_status": dict(sorted(reviews.items())),
        },
        "player_match_position_roles": match_roles,
        "player_tournament_position_summary": tournament_roles,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate the internal TheStatsAPI player-position inference report.")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = TheStatsApiBronzeService(args.data_root)
    details = service._all_match_details(args.year)
    players = service._aggregate_player_analytics(service._aggregate_players(details))
    report = build_position_report(args.year, details, players)
    output = args.output or Path("artifacts/diagnostics") / f"player_position_inference_{args.year}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Position inference report: {output}")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
