from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .player_analytics import (
    build_reference_distribution,
    calculate_player_radar,
    macroposition_for,
)


SOURCE = "TheStatsAPI"
DEFAULT_OPENING_MATCH_ID = "mt_153637999"


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def number(value: Any) -> float | int | None:
    try:
        if value is None or value == "":
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return int(parsed) if parsed.is_integer() else round(parsed, 3)


class TheStatsApiBronzeService:
    """Processed web contracts derived from TheStatsAPI Bronze raw files."""

    def __init__(self, data_root: Path | str = Path("data")) -> None:
        self.data_root = Path(data_root)

    def available(self, year: int) -> bool:
        return bool(self.fixtures(year))

    def competition(self, year: int) -> dict[str, Any]:
        fixtures = self.match_items(year)
        standings = self.standings_by_group(year)
        best_thirds = self.best_third_placed_teams(year, standings)
        matches_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for match in fixtures:
            group_name = match.get("group_name")
            if group_name:
                matches_by_group[str(group_name)].append(match)
        return json_safe(
            {
                "year": year,
                "available": bool(fixtures),
                "groups": [
                    {
                        "name": name,
                        "teams": rows,
                        "matches": matches_by_group.get(name, []),
                    }
                    for name, rows in standings.items()
                ],
                "best_thirds": best_thirds,
                "knockout": self.knockout_state(fixtures),
                "notice": (
                    None
                    if fixtures
                    else "Calendário e estatísticas da Copa 2026 ainda não estão disponíveis."
                ),
            }
        )

    def overview(self, year: int) -> dict[str, Any]:
        fixtures = self.match_items(year)
        standings = self.standings_by_group(year)
        match_details = self._all_match_details(year)
        player_rows = self._aggregate_players(match_details)
        team_rows = self.team_rows(year, standings, match_details)
        player_leaders = self.player_leaders(player_rows)
        team_leaders = self.team_leaders(team_rows)
        match_leaders = self.match_rankings(fixtures)
        finished = sorted(
            (match for match in fixtures if match.get("status") == "finished"),
            key=lambda match: str(match.get("match_date") or ""),
            reverse=True,
        )
        upcoming = sorted(
            (match for match in fixtures if match.get("status") != "finished"),
            key=lambda match: str(match.get("match_date") or ""),
        )
        today = datetime.now(timezone.utc).date().isoformat()
        matches_today = [
            match
            for match in fixtures
            if str(match.get("match_date") or "").startswith(today)
        ]

        compact_players = {
            metric: [self._compact_player(row) for row in rows]
            for metric, rows in player_leaders.items()
        }
        compact_teams = {
            metric: [self._compact_team(row) for row in rows]
            for metric, rows in team_leaders.items()
        }
        compact_matches = {
            metric: [self._compact_match(row) for row in rows]
            for metric, rows in match_leaders.items()
        }
        return json_safe(
            {
                "year": year,
                "available": bool(fixtures),
                "summary": self.competition_summary(
                    fixtures, player_rows, team_rows
                ),
                "matches_today": matches_today,
                "recent_matches": finished[:6],
                "upcoming_matches": upcoming[:6],
                "leaders": {
                    "players": compact_players,
                    "teams": compact_teams,
                    "matches": compact_matches,
                },
                "highlights": {
                    "top_team": (compact_teams.get("xg") or [None])[0],
                    "top_player": (compact_players.get("goals") or [None])[0],
                    "team_ranking": compact_teams.get("xg", []),
                    "player_ranking": compact_players.get("goals", []),
                },
                "notice": None if fixtures else "Dados da edição ainda não disponíveis.",
            }
        )

    @staticmethod
    def _compact_player(row: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "player_id",
            "player_name",
            "team_id",
            "team_name",
            "position",
            "games",
            "minutes_played",
            "goals",
            "assists",
            "shots",
            "shots_on_target",
            "xg",
            "xa",
            "rating",
        )
        return {key: row.get(key) for key in keys if row.get(key) is not None}

    @staticmethod
    def _compact_team(row: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "team_id",
            "team_name",
            "group_name",
            "played",
            "points",
            "goals_for",
            "goals_against",
            "goal_difference",
            "shots",
            "xg",
            "xga",
            "xg_difference",
        )
        return {key: row.get(key) for key in keys if row.get(key) is not None}

    @staticmethod
    def _compact_match(row: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "match_id",
            "match_date",
            "group_name",
            "stage",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "status",
            "shots",
            "xg_total",
        )
        return {key: row.get(key) for key in keys if row.get(key) is not None}

    def matches(self, year: int) -> dict[str, Any]:
        items = self.match_items(year)
        return json_safe(
            {
                "year": year,
                "source": SOURCE,
                "available": bool(items),
                "summary": {
                    "matches": len(items),
                    "finished": sum(1 for item in items if item.get("status") == "finished"),
                    "goals": sum(
                        int(item.get("home_score") or 0) + int(item.get("away_score") or 0)
                        for item in items
                        if item.get("status") == "finished"
                    ),
                },
                "filters": self.match_filters(items),
                "stage_distribution": [
                    {"stage": stage, "matches": count}
                    for stage, count in Counter(
                        item.get("stage") or item.get("group_name") or "Não informada"
                        for item in items
                    ).items()
                ],
                "items": items,
                "notice": None if items else "Calendário da Copa 2026 ainda não está disponível.",
            }
        )

    def match_detail(self, year: int, match_id: str) -> dict[str, Any]:
        detail = self._match_detail(year, match_id)
        if not detail:
            return {
                "year": year,
                "available": False,
                "notice": "Partida não encontrada no recorte atual.",
            }
        return json_safe(detail)

    def players(self, year: int) -> dict[str, Any]:
        rows = self._aggregate_players(self._all_match_details(year))
        return json_safe(
            {
                "year": year,
                "source": SOURCE,
                "available": bool(rows),
                "summary": {
                    "players": len(rows),
                    "goals": self._total(rows, "goals"),
                    "shots": self._total(rows, "shots"),
                    "xg": self._total(rows, "xg"),
                },
                "leaders": self.player_leaders(rows),
                "filters": {
                    "teams": sorted({row["team_name"] for row in rows if row.get("team_name")}),
                    "positions": sorted({row["position"] for row in rows if row.get("position")}),
                },
                "scatter": rows,
                "items": rows,
                "notice": None if rows else "Estatísticas de jogadores ainda não estão disponíveis.",
            }
        )

    def player_detail(self, year: int, player_id: str) -> dict[str, Any]:
        details = self._all_match_details(year)
        logs = []
        shots = []
        for detail in details:
            match = detail["match"]
            for player in detail["players"]:
                if player.get("player_id") == player_id:
                    logs.append({**player, "match": self._match_label(match), "match_id": match["match_id"]})
            for shot in detail["shot_map"]:
                if shot.get("player_id") == player_id:
                    shots.append(shot)
        if not logs:
            return {"year": year, "available": False, "notice": "Jogador não encontrado."}
        summary = self._merge_player_rows(logs)
        macroposition = macroposition_for(summary.get("position"))
        reference = build_reference_distribution(
            [player for detail in details for player in detail.get("players", [])]
        )
        analytics = calculate_player_radar(
            summary,
            reference,
            macroposition,
        )
        summary.update(
            {
                "macroposition": macroposition,
                "profile_score": analytics.get("profile_score"),
                "radar": analytics.get("radar", []),
                "radar_dimensions": analytics.get("dimensions", {}),
            }
        )
        return json_safe(
            {
                "year": year,
                "source": SOURCE,
                "available": True,
                "player": summary,
                "summary": summary,
                "match_log": logs,
                "shots": shots,
                "shot_map": shots,
                "radar": analytics.get("radar", []),
                "radar_dimensions": analytics.get("dimensions", {}),
            }
        )

    def teams(self, year: int) -> dict[str, Any]:
        details = self._all_match_details(year)
        rows = self.team_rows(year, self.standings_by_group(year), details)
        return json_safe(
            {
                "year": year,
                "source": SOURCE,
                "available": bool(rows),
                "summary": {
                    "teams": len(rows),
                    "goals": self._total(rows, "goals_for"),
                    "xg": self._total(rows, "xg"),
                },
                "rankings": self.team_leaders(rows),
                "items": rows,
                "notice": None if rows else "Seleções ainda não estão disponíveis.",
            }
        )

    def team_detail(self, year: int, team_id: str) -> dict[str, Any]:
        details = self._all_match_details(year)
        standings = self.standings_by_group(year)
        teams = self.team_rows(year, standings, details)
        team = next((row for row in teams if row.get("team_id") == team_id), None)
        if not team:
            return {"year": year, "available": False, "notice": "Seleção não encontrada."}
        matches = []
        players = []
        shots = []
        for detail in details:
            match = detail["match"]
            if team["team_name"] in (match.get("home_team"), match.get("away_team")):
                matches.append(self._team_match_row(team["team_name"], detail))
            players.extend([row for row in detail["players"] if row.get("team_id") == team_id])
            shots.extend([shot for shot in detail["shot_map"] if shot.get("team_id") == team_id])
        return json_safe(
            {
                "year": year,
                "source": SOURCE,
                "available": True,
                "team": team,
                "summary": team,
                "matches": matches,
                "players": sorted(players, key=lambda row: (row.get("minutes_played") or 0, row.get("rating") or 0), reverse=True),
                "shots": shots,
                "shot_map": shots,
            }
        )

    def shots(self, year: int) -> dict[str, Any]:
        details = self._all_match_details(year)
        shots = [shot for detail in details for shot in detail["shot_map"]]
        if not shots:
            return {
                "year": year,
                "available": False,
                "summary": {},
                "shot_map": [],
                "player_leaders": [],
                "team_summary": [],
                "xg_flow": [],
                "breakdowns": {},
                "items": [],
                "notice": "Mapa de finalizações ainda não está disponível para esta edição.",
            }
        return json_safe(
            {
                "year": year,
                "available": True,
                "summary": {
                    "shots": len(shots),
                    "goals": sum(1 for shot in shots if shot.get("is_goal")),
                    "xg": round(sum(float(shot.get("statsbomb_xg") or 0) for shot in shots), 2),
                    "players": len({shot.get("player_id") for shot in shots if shot.get("player_id")}),
                },
                "shot_map": shots,
                "player_leaders": self._shot_player_leaders(shots),
                "team_summary": self._team_summary(shots),
                "xg_flow": self._xg_flow(shots),
                "breakdowns": self._shot_breakdowns(shots),
                "items": shots,
                "notice": None,
            }
        )

    def opening_match(self, year: int) -> dict[str, Any]:
        return self.match_detail(year, DEFAULT_OPENING_MATCH_ID)

    def fixtures(self, year: int) -> list[dict[str, Any]]:
        rows = []
        for path in sorted((self._root(year) / "fixtures").glob("page=*/response.json")):
            data = self._payload(path).get("data", [])
            if isinstance(data, list):
                rows.extend(item for item in data if isinstance(item, dict))
        return rows

    def match_items(self, year: int) -> list[dict[str, Any]]:
        details = {detail["match"]["match_id"]: detail for detail in self._all_match_details(year)}
        rows = []
        for fixture in sorted(self.fixtures(year), key=lambda item: str(item.get("utc_date") or "")):
            match = self._match_summary(fixture, {})
            detail = details.get(match["match_id"])
            if detail:
                match.update(self._match_derived(detail))
            rows.append(match)
        return rows

    def standings_by_group(self, year: int) -> dict[str, list[dict[str, Any]]]:
        official = self._official_standings(year)
        if official:
            return official

        teams: dict[str, dict[str, Any]] = {}
        for fixture in self.fixtures(year):
            group = fixture.get("group_label")
            if not group:
                continue
            for side in ("home", "away"):
                team = fixture.get(f"{side}_team") if isinstance(fixture.get(f"{side}_team"), dict) else {}
                team_id = team.get("id")
                if not team_id:
                    continue
                teams.setdefault(
                    team_id,
                    {
                        "team_id": team_id,
                        "team_name": team.get("name"),
                        "group_name": group,
                        "played": 0,
                        "wins": 0,
                        "draws": 0,
                        "losses": 0,
                        "goals_for": 0,
                        "goals_against": 0,
                        "goal_difference": 0,
                        "points": 0,
                    },
                )
            if fixture.get("status") != "finished":
                continue
            score = fixture.get("score") if isinstance(fixture.get("score"), dict) else {}
            home_score = number(score.get("home"))
            away_score = number(score.get("away"))
            if home_score is None or away_score is None:
                continue
            home_id = fixture.get("home_team", {}).get("id")
            away_id = fixture.get("away_team", {}).get("id")
            if not home_id or not away_id:
                continue
            self._apply_result(teams[home_id], home_score, away_score)
            self._apply_result(teams[away_id], away_score, home_score)

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in teams.values():
            row["goal_difference"] = row["goals_for"] - row["goals_against"]
            grouped[row["group_name"]].append(row)
        ordered = {}
        for group in sorted(grouped):
            rows = sorted(
                grouped[group],
                key=lambda item: (item["points"], item["goal_difference"], item["goals_for"], item["team_name"] or ""),
                reverse=True,
            )
            for index, row in enumerate(rows, start=1):
                row["position"] = index
                row["classification_status"] = self._classification_status(
                    index,
                    row.get("qualification_status"),
                )
            ordered[group] = rows
        return ordered

    def _official_standings(self, year: int) -> dict[str, list[dict[str, Any]]]:
        data = self._payload(self._root(year) / "standings/response.json").get(
            "data", []
        )
        if not isinstance(data, list):
            return {}

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in data:
            if not isinstance(item, dict):
                continue
            group = item.get("group_label") or item.get("group")
            team = item.get("team") if isinstance(item.get("team"), dict) else {}
            if not group or not team.get("name"):
                continue
            row = {
                "team_id": team.get("id") or item.get("team_id"),
                "team_name": team.get("name"),
                "group_name": str(group),
                "played": number(item.get("matches_played")) or 0,
                "wins": number(item.get("wins")) or 0,
                "draws": number(item.get("draws")) or 0,
                "losses": number(item.get("losses")) or 0,
                "goals_for": number(item.get("goals_for")) or 0,
                "goals_against": number(item.get("goals_against")) or 0,
                "goal_difference": number(item.get("goal_difference")) or 0,
                "points": number(item.get("points")) or 0,
                "position": number(item.get("position")),
            }
            if item.get("qualification_status"):
                row["qualification_status"] = item["qualification_status"]
            grouped[str(group)].append(row)

        ordered: dict[str, list[dict[str, Any]]] = {}
        for group in sorted(grouped):
            rows = sorted(
                grouped[group],
                key=lambda row: (
                    row.get("position") is None,
                    row.get("position") or 999,
                ),
            )
            for index, row in enumerate(rows, start=1):
                row["position"] = row.get("position") or index
                row["classification_status"] = self._classification_status(
                    int(row["position"]),
                    row.get("qualification_status"),
                )
            ordered[group] = rows
        return ordered

    def best_third_placed_teams(
        self,
        year: int,
        standings: dict[str, list[dict[str, Any]]] | None = None,
    ) -> list[dict[str, Any]]:
        standings = standings or self.standings_by_group(year)
        thirds = [rows[2].copy() for rows in standings.values() if len(rows) >= 3]
        ranked = sorted(
            thirds,
            key=lambda item: (item["points"], item["goal_difference"], item["goals_for"], item["team_name"] or ""),
            reverse=True,
        )
        for index, row in enumerate(ranked, start=1):
            row["rank"] = index
            if index <= 7:
                row["status"] = "Classificando"
            elif index == 8:
                row["status"] = "Última vaga"
            else:
                row["status"] = "Fora agora"
        return ranked

    def team_rows(
        self,
        year: int,
        standings: dict[str, list[dict[str, Any]]],
        details: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows = [row.copy() for group in standings.values() for row in group]
        by_name = {row["team_name"]: row for row in rows}
        for detail in details:
            for team in detail["team_summary"]:
                row = by_name.get(team.get("team_name"))
                if not row:
                    continue
                row["shots"] = (row.get("shots") or 0) + int(team.get("shots") or 0)
                row["goals"] = (row.get("goals") or 0) + int(team.get("goals") or 0)
            match = detail["match"]
            xg_rows = {item.get("metric"): item for item in detail["stats_comparison"]}
            xg = xg_rows.get("expected_goals")
            if xg:
                home = match.get("home_team")
                away = match.get("away_team")
                if home in by_name:
                    by_name[home]["xg"] = round(float(by_name[home].get("xg") or 0) + float(xg.get(home) or 0), 2)
                    by_name[home]["xga"] = round(float(by_name[home].get("xga") or 0) + float(xg.get(away) or 0), 2)
                if away in by_name:
                    by_name[away]["xg"] = round(float(by_name[away].get("xg") or 0) + float(xg.get(away) or 0), 2)
                    by_name[away]["xga"] = round(float(by_name[away].get("xga") or 0) + float(xg.get(home) or 0), 2)
        for row in rows:
            row["xg"] = round(float(row.get("xg") or 0), 2)
            row["xga"] = round(float(row.get("xga") or 0), 2)
            row["xg_difference"] = round(row["xg"] - row["xga"], 2)
        return sorted(rows, key=lambda item: (item.get("points") or 0, item.get("xg") or 0), reverse=True)

    def _all_match_details(self, year: int) -> list[dict[str, Any]]:
        reference = build_reference_distribution(self._reference_player_rows(year))
        details = []
        for root in sorted((self._root(year) / "matches").glob("match_id=*")):
            match_id = root.name.split("=", 1)[-1]
            detail = self._match_detail(year, match_id, reference)
            if detail and detail.get("available"):
                details.append(detail)
        return details

    def _reference_player_rows(self, year: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for root in sorted((self._root(year) / "matches").glob("match_id=*")):
            players = self._payload(root / "player_stats/response.json").get("data", [])
            lineups = self._payload(root / "lineups/response.json").get("data", {})
            rows.extend(self._players(players, lineups))
        return rows

    def _match_detail(
        self,
        year: int,
        match_id: str,
        reference_distribution: dict[str, dict[str, dict[str, Any]]] | None = None,
    ) -> dict[str, Any] | None:
        fixture = self._fixture(year, match_id)
        root = self._match_root(year, match_id)
        if not fixture and not root.exists():
            return None
        lineups = self._payload(root / "lineups/response.json").get("data", {})
        stats = self._payload(root / "match_stats/response.json").get("data", {})
        players_raw = self._payload(root / "player_stats/response.json").get("data", [])
        events_payload = self._payload(root / "events/response.json").get("data", {})
        shots_raw = self._payload(root / "shotmap/response.json").get("data", [])
        details_raw = self._payload(
            root / "match_detail/response.json"
        ).get("data", {})
        officials_raw = self._payload(
            root / "match_referee/response.json"
        ).get("data", {})
        detail_officials = self._match_officials(details_raw)
        referee_officials = self._match_officials(officials_raw)
        officials = {
            key: referee_officials.get(key) or detail_officials.get(key)
            for key in detail_officials
        }
        match = self._match_summary(
            fixture,
            lineups,
            match_id,
            details=details_raw,
            officials=officials,
        )
        shot_map = self._shot_map(match, shots_raw)
        event_rows = self._events(match, events_payload)
        player_rows = self._players(players_raw, lineups)
        stats_comparison = self._stats_comparison(match, stats)
        reference = reference_distribution or build_reference_distribution(
            self._reference_player_rows(year)
        )
        player_rows = self._enrich_match_players(player_rows, reference)
        for player in player_rows:
            player_id = player.get("player_id")
            player_name = player.get("player_name")
            player["player_shots"] = [
                shot
                for shot in shot_map
                if (player_id and shot.get("player_id") == player_id)
                or (player_name and shot.get("player_name") == player_name)
            ]
            player["player_events"] = [
                event
                for event in event_rows
                if player_name and event.get("player_name") == player_name
            ]
        match_detail = {
            **match,
            **self._match_derived_from_parts(shot_map, stats_comparison),
            "goals": self._match_goals(shot_map, event_rows),
        }
        return {
            "year": year,
            "source": SOURCE,
            "available": bool(match.get("match_id")),
            "match": match_detail,
            "summary": {
                "shots": len(shot_map),
                "goals": sum(1 for shot in shot_map if shot.get("is_goal")),
                "xg": round(sum(float(shot.get("statsbomb_xg") or 0) for shot in shot_map), 2),
                "events": len(event_rows),
                "players": len(player_rows),
            },
            "endpoint_status": self._endpoint_status(root),
            "stats_comparison": stats_comparison,
            "comparison_bars": self._comparison_bars(match, stats_comparison),
            "match_story": self._match_story(match, stats_comparison, player_rows, shot_map),
            "lineups": self._lineups(lineups),
            "player_impacts": self._player_impacts(player_rows),
            "player_leaders": self.player_leaders(player_rows),
            "players": player_rows,
            "events": event_rows,
            "event_breakdown": self._event_breakdown(event_rows),
            "shot_map": shot_map,
            "team_summary": self._team_summary(shot_map),
            "xg_flow": self._xg_flow(shot_map),
            "notice": None,
        }

    def _root(self, year: int) -> Path:
        return self.data_root / "bronze/thestatsapi/world_cup" / str(year)

    def _match_root(self, year: int, match_id: str = DEFAULT_OPENING_MATCH_ID) -> Path:
        return self._root(year) / "matches" / f"match_id={match_id}"

    def _payload(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {"data": payload}

    def _fixture(self, year: int, match_id: str) -> dict[str, Any]:
        for row in self.fixtures(year):
            if str(row.get("id") or row.get("match_id")) == match_id:
                return row
        return {}

    @staticmethod
    def _team_name(value: Any) -> str | None:
        if isinstance(value, dict):
            return value.get("name")
        if isinstance(value, str):
            return value
        return None

    def _match_summary(
        self,
        fixture: dict[str, Any],
        lineups: dict[str, Any],
        fallback_match_id: str = DEFAULT_OPENING_MATCH_ID,
        details: dict[str, Any] | None = None,
        officials: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        detail_values = details if isinstance(details, dict) else {}
        source = {
            **fixture,
            **{key: value for key, value in detail_values.items() if value is not None},
        }
        home = source.get("home_team") or lineups.get("home") or {}
        away = source.get("away_team") or lineups.get("away") or {}
        score = source.get("score") if isinstance(source.get("score"), dict) else {}
        venue_name, venue_city = self._venue_parts(
            source.get("venue") or source.get("stadium")
        )
        officials = officials or self._match_officials(source)
        fixture_referee = self._official_name(source.get("referee"))
        return {
            "match_id": source.get("id") or source.get("match_id") or fallback_match_id,
            "match_date": source.get("utc_date"),
            "group_name": source.get("group_label"),
            "stage": source.get("stage_name") or "Group Stage",
            "home_team_id": home.get("id") if isinstance(home, dict) else None,
            "away_team_id": away.get("id") if isinstance(away, dict) else None,
            "home_team": self._team_name(home),
            "away_team": self._team_name(away),
            "home_score": score.get("home"),
            "away_score": score.get("away"),
            "status": source.get("status"),
            "matchday": source.get("matchday"),
            "xg_available": source.get("xg_available"),
            "venue": venue_name,
            "stadium": venue_name,
            "venue_city": venue_city,
            "referee": officials.get("referee") or fixture_referee,
            "main_referee": officials.get("main_referee"),
            "officials": officials.get("officials"),
            "assistant_referees": officials.get("assistant_referees"),
            "fourth_official": officials.get("fourth_official"),
            "var": officials.get("var"),
            "avar": officials.get("avar"),
        }

    @staticmethod
    def _venue_parts(value: Any) -> tuple[str | None, str | None]:
        if isinstance(value, str):
            return value.strip() or None, None
        if isinstance(value, dict):
            name = value.get("name") or value.get("stadium_name")
            city = value.get("city") or value.get("city_name")
            return (
                str(name).strip() if name else None,
                str(city).strip() if city else None,
            )
        return None, None

    @staticmethod
    def _official_name(value: Any) -> str | None:
        if isinstance(value, str):
            return value.strip() or None
        if isinstance(value, dict):
            name = value.get("name") or value.get("full_name")
            return str(name).strip() if name else None
        return None

    @classmethod
    def _official_names(cls, value: Any) -> list[str] | None:
        values = value if isinstance(value, list) else [value]
        names = [cls._official_name(item) for item in values]
        filtered = [name for name in names if name]
        return filtered or None

    @classmethod
    def _match_officials(cls, payload: Any) -> dict[str, Any]:
        data = payload if isinstance(payload, dict) else {}
        return {
            "referee": cls._official_name(data.get("referee")),
            "main_referee": cls._official_name(data.get("main_referee")),
            "officials": cls._official_names(data.get("officials")),
            "assistant_referees": cls._official_names(
                data.get("assistant_referees")
            ),
            "fourth_official": cls._official_name(data.get("fourth_official")),
            "var": cls._official_name(data.get("var")),
            "avar": cls._official_names(data.get("avar")),
        }

    @staticmethod
    def _side_value(value: Any, side: str) -> float | int | None:
        if isinstance(value, dict):
            if "all" in value and isinstance(value["all"], dict):
                return value["all"].get(side)
            return value.get(side)
        return None

    def _stats_comparison(
        self,
        match: dict[str, Any],
        stats: dict[str, Any],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        home = match.get("home_team") or "Home"
        away = match.get("away_team") or "Away"
        for section in ("overview", "shots", "passes", "attack", "defending", "duels", "goalkeeping"):
            section_data = stats.get(section, {})
            if not isinstance(section_data, dict):
                continue
            for metric, value in section_data.items():
                home_value = self._side_value(value, "home")
                away_value = self._side_value(value, "away")
                if home_value is None and away_value is None:
                    continue
                rows.append({"metric": metric, "section": section, home: home_value, away: away_value})
        return rows

    def _lineups(self, lineups: dict[str, Any]) -> dict[str, Any]:
        result = {}
        for side, data in (("home", lineups.get("home", {})), ("away", lineups.get("away", {}))):
            if not isinstance(data, dict):
                continue
            result[side] = {
                "team_id": data.get("id"),
                "team_name": data.get("name"),
                "formation": data.get("formation"),
                "starting_xi": data.get("starting_xi") or [],
                "substitutes": data.get("substitutes") or [],
            }
        return result

    def _players(self, players: Any, lineups: dict[str, Any]) -> list[dict[str, Any]]:
        if not isinstance(players, list):
            return []
        team_names = {}
        for side in ("home", "away"):
            data = lineups.get(side, {})
            if isinstance(data, dict):
                team_names[data.get("id")] = data.get("name")
        rows = []
        for player in players:
            if not isinstance(player, dict):
                continue
            shooting = player.get("shooting", {}) if isinstance(player.get("shooting"), dict) else {}
            passing = player.get("passing", {}) if isinstance(player.get("passing"), dict) else {}
            general = player.get("general", {}) if isinstance(player.get("general"), dict) else {}
            duels = player.get("duels", {}) if isinstance(player.get("duels"), dict) else {}
            defending = player.get("defending", {}) if isinstance(player.get("defending"), dict) else {}
            goalkeeping = player.get("goalkeeping", {}) if isinstance(player.get("goalkeeping"), dict) else {}

            def metric(section: dict[str, Any], key: str) -> float | int | None:
                return number(section.get(key)) if key in section else None

            goals = metric(shooting, "goals")
            shots = metric(shooting, "total_shots")
            xg = metric(shooting, "expected_goals")
            passes = metric(passing, "total_passes")
            accurate_passes = metric(passing, "accurate_passes")
            total_long_balls = metric(passing, "total_long_balls")
            accurate_long_balls = metric(passing, "accurate_long_balls")
            total_crosses = metric(passing, "total_crosses")
            accurate_crosses = metric(passing, "accurate_crosses")
            rows.append(
                {
                    "player_id": player.get("player_id"),
                    "player_name": player.get("player_name"),
                    "team_id": player.get("team_id"),
                    "team_name": team_names.get(player.get("team_id")),
                    "position": player.get("position"),
                    "started": player.get("started"),
                    "played": player.get("played"),
                    "minutes_played": number(player.get("minutes_played")),
                    "rating": number(player.get("rating")),
                    "goals": goals,
                    "shots": shots,
                    "shots_on_target": metric(shooting, "shots_on_target"),
                    "shots_off_target": metric(shooting, "shots_off_target"),
                    "blocked_shots": metric(shooting, "blocked_shots"),
                    "xg": xg,
                    "np_xg": metric(shooting, "np_expected_goals"),
                    "xa": metric(shooting, "expected_assists"),
                    "big_chances_created": metric(shooting, "big_chances_created"),
                    "goals_minus_xg": round(float(goals) - float(xg), 2) if goals is not None and xg is not None else None,
                    "xg_per_shot": round(float(xg) / float(shots), 3) if xg is not None and shots else None,
                    "assists": metric(passing, "assists"),
                    "key_passes": metric(passing, "key_passes"),
                    "passes": passes,
                    "accurate_passes": accurate_passes,
                    "pass_accuracy": round(float(accurate_passes) / float(passes) * 100, 1) if accurate_passes is not None and passes else None,
                    "total_long_balls": total_long_balls,
                    "accurate_long_balls": accurate_long_balls,
                    "long_pass_accuracy": round(float(accurate_long_balls) / float(total_long_balls) * 100, 1) if accurate_long_balls is not None and total_long_balls else None,
                    "total_crosses": total_crosses,
                    "accurate_crosses": accurate_crosses,
                    "cross_accuracy": round(float(accurate_crosses) / float(total_crosses) * 100, 1) if accurate_crosses is not None and total_crosses else None,
                    "duels_won": metric(duels, "duel_won"),
                    "duels_lost": metric(duels, "duel_lost"),
                    "aerial_won": metric(duels, "aerial_won"),
                    "successful_dribbles": metric(duels, "won_contest"),
                    "dispossessed": metric(duels, "dispossessed"),
                    "tackles": metric(defending, "tackles"),
                    "interceptions": metric(defending, "interceptions"),
                    "clearances": metric(defending, "clearances"),
                    "touches": metric(general, "touches"),
                    "possession_lost": metric(general, "possession_lost"),
                    "fouls": metric(general, "fouls"),
                    "fouls_suffered": metric(general, "was_fouled"),
                    "offsides": metric(general, "offsides"),
                    "yellow_cards": metric(general, "yellow_cards"),
                    "red_cards": metric(general, "red_cards"),
                    "saves": metric(goalkeeping, "saves"),
                }
            )
        return rows

    def _enrich_match_players(
        self,
        players: list[dict[str, Any]],
        reference_distribution: dict[str, dict[str, dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        if not players:
            return []
        enriched = []
        for row in players:
            macroposition = macroposition_for(row.get("position"))
            analytics = calculate_player_radar(
                row,
                reference_distribution,
                macroposition,
            )
            impact = analytics.get("profile_score")
            enriched.append(
                {
                    **row,
                    "macroposition": macroposition,
                    "impact_score": impact,
                    "profile_score": analytics.get("profile_score"),
                    "radar": analytics.get("radar", []),
                    "radar_dimensions": analytics.get("dimensions", {}),
                    "impact_summary": self._player_impact_summary(row, impact) if impact is not None else None,
                }
            )
        return sorted(enriched, key=lambda item: item.get("impact_score") or 0, reverse=True)

    @staticmethod
    def _player_impact_summary(row: dict[str, Any], impact: float) -> str:
        strengths = [
            ("ataque", float(row.get("goals") or 0) * 2 + float(row.get("xg") or 0) + float(row.get("shots") or 0) * 0.25),
            ("criação", float(row.get("xa") or 0) + float(row.get("key_passes") or 0) * 0.35 + float(row.get("assists") or 0) * 2),
            ("passe", float(row.get("accurate_passes") or 0) / 25 + float(row.get("pass_accuracy") or 0) / 100),
            ("defesa", float(row.get("tackles") or 0) + float(row.get("interceptions") or 0) + float(row.get("duels_won") or 0) * 0.25),
        ]
        strength = max(strengths, key=lambda item: item[1])[0]
        return (
            f"Impacto derivado {impact:.1f}/100 na partida, com destaque em {strength}. "
            "Índice calculado a partir de chute, criação, passe, defesa, participação e rating."
        )

    @staticmethod
    def _comparison_bars(match: dict[str, Any], stats: list[dict[str, Any]]) -> list[dict[str, Any]]:
        home = match.get("home_team") or "Home"
        away = match.get("away_team") or "Away"
        preferred = (
            "expected_goals",
            "total_shots",
            "shots_on_target",
            "big_chances_missed",
            "accurate_passes",
            "total_passes",
            "ball_recoveries",
            "tackles",
            "interceptions",
            "duels_won_percentage",
            "dribbles_percentage",
            "saves",
        )
        by_metric = {row.get("metric"): row for row in stats}
        rows = []
        for metric in preferred:
            row = by_metric.get(metric)
            if not row:
                continue
            home_value = number(row.get(home))
            away_value = number(row.get(away))
            if home_value is None and away_value is None:
                continue
            maximum = max(float(home_value or 0), float(away_value or 0), 1)
            rows.append(
                {
                    "metric": metric,
                    "label": metric.replace("_", " ").title(),
                    "section": row.get("section"),
                    "home_team": home,
                    "away_team": away,
                    "home_value": home_value,
                    "away_value": away_value,
                    "home_pct": round(float(home_value or 0) / maximum * 100, 1),
                    "away_pct": round(float(away_value or 0) / maximum * 100, 1),
                }
            )
        return rows

    @staticmethod
    def _match_story(
        match: dict[str, Any],
        stats: list[dict[str, Any]],
        players: list[dict[str, Any]],
        shots: list[dict[str, Any]],
    ) -> list[str]:
        home = match.get("home_team") or "Mandante"
        away = match.get("away_team") or "Visitante"
        by_metric = {row.get("metric"): row for row in stats}
        lines: list[str] = []

        def values(metric: str) -> tuple[float | int, float | int] | None:
            row = by_metric.get(metric)
            if not row:
                return None
            left = number(row.get(home))
            right = number(row.get(away))
            if left is None or right is None:
                return None
            return left, right

        xg = values("expected_goals")
        creation_team = None
        if xg:
            team = home if xg[0] >= xg[1] else away
            creation_team = team
            value, other = xg if team == home else (xg[1], xg[0])
            lines.append(f"{team} controlou a criação: {value} xG contra {other}.")

        shots_values = values("total_shots")
        target_values = values("shots_on_target")
        if shots_values:
            team = home if shots_values[0] >= shots_values[1] else away
            value, other = shots_values if team == home else (shots_values[1], shots_values[0])
            subject = "A equipe também" if team == creation_team else team
            detail = f"{subject} finalizou mais: {value} a {other}"
            if target_values:
                target, target_other = target_values if team == home else (target_values[1], target_values[0])
                detail += f", com {target} chutes no alvo contra {target_other}"
            lines.append(f"{detail}.")

        recoveries = values("ball_recoveries")
        if recoveries:
            team = home if recoveries[0] >= recoveries[1] else away
            value, other = recoveries if team == home else (recoveries[1], recoveries[0])
            if team != creation_team:
                lines.append(f"{team} teve algum respiro sem bola, liderando em recuperações por {value} a {other}.")
            else:
                lines.append(f"A equipe também recuperou mais bolas: {value} a {other}.")

        top_player = next((row for row in players if row.get("impact_score") is not None), None)
        if top_player:
            lines.append(
                f"{top_player.get('player_name')} foi o principal nome da partida, com impacto de "
                f"{top_player.get('impact_score')}/100."
            )
        top_shot = max(shots, key=lambda shot: float(shot.get("xg") or 0), default=None)
        if top_shot:
            lines.append(
                f"A chance mais clara foi de {top_shot.get('player_name')}, "
                f"com {top_shot.get('xg')} xG aos {top_shot.get('minute')}'."
            )
        return lines[:5]

    @staticmethod
    def _player_impacts(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            [
                {
                    "player_id": row.get("player_id"),
                    "player_name": row.get("player_name"),
                    "team_id": row.get("team_id"),
                    "team_name": row.get("team_name"),
                    "position": row.get("position"),
                    "impact_score": row.get("impact_score"),
                    "impact_summary": row.get("impact_summary"),
                    "radar": row.get("radar"),
                    "goals": row.get("goals"),
                    "xg": row.get("xg"),
                    "xa": row.get("xa"),
                    "shots": row.get("shots"),
                    "key_passes": row.get("key_passes"),
                    "accurate_passes": row.get("accurate_passes"),
                    "pass_accuracy": row.get("pass_accuracy"),
                    "tackles": row.get("tackles"),
                    "interceptions": row.get("interceptions"),
                    "duels_won": row.get("duels_won"),
                    "rating": row.get("rating"),
                }
                for row in players
                if row.get("impact_score") is not None
            ],
            key=lambda item: item.get("impact_score") or 0,
            reverse=True,
        )

    def _events(self, match: dict[str, Any], events_payload: dict[str, Any]) -> list[dict[str, Any]]:
        events = events_payload.get("events", []) if isinstance(events_payload, dict) else []
        rows = []
        for event in events if isinstance(events, list) else []:
            if not isinstance(event, dict):
                continue
            team = event.get("team") if isinstance(event.get("team"), dict) else {}
            player = event.get("player") if isinstance(event.get("player"), dict) else {}
            rows.append(
                {
                    "match_id": match.get("match_id"),
                    "sequence": event.get("sequence"),
                    "minute": event.get("minute"),
                    "extra_time": event.get("extra_time"),
                    "period": event.get("period"),
                    "type": event.get("type"),
                    "team_name": team.get("name"),
                    "player_name": player.get("name"),
                }
            )
        return rows

    @staticmethod
    def _match_goals(shots: list[dict[str, Any]], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        goals = [
            {
                "minute": shot.get("minute"),
                "team_id": shot.get("team_id"),
                "team_name": shot.get("team_name"),
                "player_id": shot.get("player_id"),
                "player_name": shot.get("player_name"),
                "source": "shotmap",
            }
            for shot in shots
            if shot.get("is_goal")
        ]
        if goals:
            return sorted(goals, key=lambda row: row.get("minute") or 0)
        return sorted(
            [
                {
                    "minute": event.get("minute"),
                    "team_name": event.get("team_name"),
                    "player_name": event.get("player_name"),
                    "source": "events",
                }
                for event in events
                if event.get("type") == "goal"
            ],
            key=lambda row: row.get("minute") or 0,
        )

    def _shot_map(self, match: dict[str, Any], shots: Any) -> list[dict[str, Any]]:
        rows = []
        for shot in shots if isinstance(shots, list) else []:
            if not isinstance(shot, dict):
                continue
            raw_xg = number(shot.get("expected_goals"))
            shot_xg = max(0.0, float(raw_xg)) if raw_xg is not None else 0.0
            rows.append(
                {
                    "shot_id": shot.get("id"),
                    "match_id": match.get("match_id"),
                    "home_team": match.get("home_team"),
                    "away_team": match.get("away_team"),
                    "home_score": match.get("home_score"),
                    "away_score": match.get("away_score"),
                    "team_id": shot.get("team_id"),
                    "team_name": shot.get("team_name"),
                    "player_id": shot.get("player_id"),
                    "player_name": shot.get("player_name"),
                    "minute": shot.get("minute"),
                    "x": shot.get("x"),
                    "y": shot.get("y"),
                    "statsbomb_xg": shot_xg,
                    "xg": shot_xg,
                    "shot_outcome": shot.get("result"),
                    "body_part": shot.get("body_part"),
                    "shot_type": shot.get("situation"),
                    "is_goal": shot.get("is_goal"),
                    "is_on_target": shot.get("is_on_target"),
                    "is_penalty": shot.get("is_penalty"),
                }
            )
        return rows

    @staticmethod
    def _apply_result(row: dict[str, Any], goals_for: int | float, goals_against: int | float) -> None:
        row["played"] += 1
        row["goals_for"] += int(goals_for)
        row["goals_against"] += int(goals_against)
        if goals_for > goals_against:
            row["wins"] += 1
            row["points"] += 3
        elif goals_for == goals_against:
            row["draws"] += 1
            row["points"] += 1
        else:
            row["losses"] += 1

    @staticmethod
    def _classification_status(
        position: int,
        qualification_status: Any = None,
    ) -> str:
        provider_status = str(qualification_status or "").strip().casefold()
        if provider_status:
            if any(value in provider_status for value in ("qualified", "classificado")):
                return "Classificado"
            if any(value in provider_status for value in ("eliminated", "eliminado")):
                return "Eliminado"
        if position <= 2:
            return "Classificando"
        if position == 3:
            return "Possível vaga"
        return "Fora agora"

    @classmethod
    def knockout_state(cls, fixtures: list[dict[str, Any]]) -> dict[str, Any]:
        round_specs = (
            ("round_of_32", "Fase de 32"),
            ("round_of_16", "Oitavas"),
            ("quarter_finals", "Quartas"),
            ("semi_finals", "Semifinais"),
            ("third_place", "Disputa de 3º lugar"),
            ("final", "Final"),
        )
        matches_by_round: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for fixture in fixtures:
            round_key = cls._knockout_round(fixture)
            if not round_key:
                continue
            matches_by_round[round_key].append(cls._knockout_match(fixture))

        rounds = [
            {
                "id": round_key,
                "name": label,
                "matches": sorted(
                    matches_by_round.get(round_key, []),
                    key=lambda item: str(item.get("kickoff_at") or ""),
                ),
            }
            for round_key, label in round_specs
        ]
        available = any(round_["matches"] for round_ in rounds)
        incomplete = any(
            not side.get("defined")
            for round_ in rounds
            for match in round_["matches"]
            for side in (match["home"], match["away"])
        ) or any(not round_["matches"] for round_ in rounds)
        return {
            "available": available,
            "rounds": rounds,
            "notice": (
                "Confrontos serão atualizados conforme a fase de grupos avançar."
                if incomplete
                else None
            ),
        }

    @staticmethod
    def _knockout_round(fixture: dict[str, Any]) -> str | None:
        if fixture.get("group_name"):
            return None
        stage = str(fixture.get("stage") or "").strip().casefold().replace("-", "_").replace(" ", "_")
        aliases = {
            "round_of_32": "round_of_32",
            "fase_de_32": "round_of_32",
            "round_of_16": "round_of_16",
            "oitavas": "round_of_16",
            "quarter_finals": "quarter_finals",
            "quarterfinals": "quarter_finals",
            "quartas": "quarter_finals",
            "semi_finals": "semi_finals",
            "semifinals": "semi_finals",
            "semifinais": "semi_finals",
            "third_place": "third_place",
            "third_place_playoff": "third_place",
            "disputa_de_3º_lugar": "third_place",
            "final": "final",
        }
        if stage in aliases:
            return aliases[stage]
        if number(fixture.get("matchday")) == 6:
            return "round_of_32"
        return None

    @classmethod
    def _knockout_match(cls, fixture: dict[str, Any]) -> dict[str, Any]:
        return {
            "match_id": fixture.get("match_id"),
            "status": fixture.get("status"),
            "kickoff_at": fixture.get("match_date"),
            "home_score": fixture.get("home_score"),
            "away_score": fixture.get("away_score"),
            "home": cls._knockout_side(
                fixture.get("home_team"), fixture.get("home_team_id")
            ),
            "away": cls._knockout_side(
                fixture.get("away_team"), fixture.get("away_team_id")
            ),
        }

    @staticmethod
    def _knockout_side(team_name: Any, team_id: Any) -> dict[str, Any]:
        name = str(team_name or "").strip()
        placeholder = None
        group_position = re.fullmatch(r"([12])([A-L])", name, re.IGNORECASE)
        reversed_position = re.fullmatch(r"([A-L])([12])", name, re.IGNORECASE)
        winner = re.fullmatch(r"W(\d+)", name, re.IGNORECASE)
        if re.fullmatch(r"3[A-L](?:/3[A-L])+", name, re.IGNORECASE):
            placeholder = "Melhor terceiro"
        elif group_position:
            placeholder = f"{group_position.group(1)}º Grupo {group_position.group(2).upper()}"
        elif reversed_position:
            placeholder = f"{reversed_position.group(2)}º Grupo {reversed_position.group(1).upper()}"
        elif winner:
            placeholder = f"Vencedor da partida {winner.group(1)}"
        defined = bool(name and not placeholder)
        return {
            "team_name": name if defined else None,
            "team_id": team_id if defined else None,
            "placeholder": placeholder or ("Aguardando definição" if not defined else None),
            "defined": defined,
        }

    @staticmethod
    def competition_summary(fixtures: list[dict[str, Any]], players: list[dict[str, Any]], teams: list[dict[str, Any]]) -> dict[str, Any]:
        finished = [item for item in fixtures if item.get("status") == "finished"]
        goals = sum(int(item.get("home_score") or 0) + int(item.get("away_score") or 0) for item in finished)
        return {
            "matches": len(fixtures),
            "finished": len(finished),
            "teams": len(teams),
            "players": len(players),
            "goals": goals,
            "goals_per_match": round(goals / len(finished), 2) if finished else None,
            "shots": sum(int(team.get("shots") or 0) for team in teams),
            "xg": round(sum(float(team.get("xg") or 0) for team in teams), 2),
        }

    @staticmethod
    def match_filters(items: list[dict[str, Any]]) -> dict[str, list[str]]:
        return {
            "groups": sorted({str(item.get("group_name")) for item in items if item.get("group_name")}),
            "stages": sorted({str(item.get("stage")) for item in items if item.get("stage")}),
            "teams": sorted({team for item in items for team in (item.get("home_team"), item.get("away_team")) if team}),
            "statuses": sorted({str(item.get("status")) for item in items if item.get("status")}),
        }

    @staticmethod
    def _match_label(match: dict[str, Any]) -> str:
        return f"{match.get('home_team')} {match.get('home_score')}–{match.get('away_score')} {match.get('away_team')}"

    @staticmethod
    def _match_derived(detail: dict[str, Any]) -> dict[str, Any]:
        return detail["match"] | detail.get("summary", {})

    @staticmethod
    def _match_derived_from_parts(shots: list[dict[str, Any]], stats: list[dict[str, Any]]) -> dict[str, Any]:
        xg_row = next((row for row in stats if row.get("metric") == "expected_goals"), {})
        return {"shots": len(shots), "xg_total": round(sum(float(shot.get("xg") or 0) for shot in shots), 2), "expected_goals": xg_row}

    @staticmethod
    def _merge_player_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
        first = rows[0].copy()
        for metric in ("minutes_played", "goals", "assists", "shots", "shots_on_target", "xg", "xa", "key_passes", "yellow_cards", "red_cards"):
            first[metric] = round(sum(float(row.get(metric) or 0) for row in rows), 3)
        first["games"] = len(rows)
        first["rating"] = round(sum(float(row.get("rating") or 0) for row in rows if row.get("rating") is not None) / max(1, sum(1 for row in rows if row.get("rating") is not None)), 2)
        first["xg_per_shot"] = round(first["xg"] / first["shots"], 3) if first["shots"] else None
        first["goals_minus_xg"] = round(first["goals"] - first["xg"], 2)
        return first

    def _aggregate_players(self, details: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for detail in details:
            for player in detail["players"]:
                if player.get("player_id"):
                    grouped[player["player_id"]].append(player)
        return sorted([self._merge_player_rows(rows) for rows in grouped.values()], key=lambda row: (row.get("goals") or 0, row.get("xg") or 0), reverse=True)

    @staticmethod
    def _team_match_row(team_name: str, detail: dict[str, Any]) -> dict[str, Any]:
        match = detail["match"]
        opponent = match.get("away_team") if match.get("home_team") == team_name else match.get("home_team")
        return {**match, "opponent": opponent}

    @staticmethod
    def _team_summary(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"shots": 0, "goals": 0, "xg": 0.0})
        for shot in shots:
            team = shot.get("team_name") or "Unknown"
            grouped[team]["team_name"] = team
            grouped[team]["shots"] += 1
            grouped[team]["goals"] += 1 if shot.get("is_goal") else 0
            grouped[team]["xg"] += float(shot.get("xg") or 0)
        return [{**row, "xg": round(float(row["xg"]), 2)} for row in sorted(grouped.values(), key=lambda item: item["xg"], reverse=True)]

    @staticmethod
    def _shot_player_leaders(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {"shots": 0, "goals": 0, "xg": 0.0})
        for shot in shots:
            key = (shot.get("player_name") or "Unknown", shot.get("team_name") or "Unknown")
            grouped[key]["player_name"] = key[0]
            grouped[key]["team_name"] = key[1]
            grouped[key]["shots"] += 1
            grouped[key]["goals"] += 1 if shot.get("is_goal") else 0
            grouped[key]["xg"] += float(shot.get("xg") or 0)
        return [{**row, "xg": round(float(row["xg"]), 2)} for row in sorted(grouped.values(), key=lambda item: (item["xg"], item["shots"]), reverse=True)]

    @staticmethod
    def _xg_flow(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
        totals: dict[str, float] = defaultdict(float)
        rows = []
        for shot in sorted(shots, key=lambda item: item.get("minute") or 0):
            team = shot.get("team_name") or "Unknown"
            totals[team] += max(0.0, float(shot.get("xg") or 0))
            rows.append({**shot, "cumulative_xg": round(totals[team], 3)})
        if rows:
            final_minute = max(90, max(int(row.get("minute") or 0) for row in rows))
            for team, value in totals.items():
                rows.append(
                    {
                        "team_name": team,
                        "minute": final_minute,
                        "cumulative_xg": round(value, 3),
                        "is_terminal": True,
                    }
                )
        return rows

    @staticmethod
    def _shot_breakdowns(shots: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        return {
            column: [{"label": label, "value": value} for label, value in Counter(str(shot.get(column) or "Não informado") for shot in shots).most_common()]
            for column in ("body_part", "shot_type", "shot_outcome")
        }

    @staticmethod
    def _event_breakdown(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"label": label, "value": value} for label, value in Counter(str(event.get("type") or "unknown") for event in events).most_common()]

    @staticmethod
    def player_leaders(players: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        metrics = ("goals", "xg", "shots", "shots_on_target", "xg_per_shot", "goals_minus_xg", "assists", "rating")
        return {metric: sorted([row for row in players if row.get(metric) is not None], key=lambda row: row.get(metric) or 0, reverse=True)[:10] for metric in metrics}

    @staticmethod
    def team_leaders(teams: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        metrics = ("xg", "xga", "xg_difference", "shots", "goals_for", "points")
        return {metric: sorted([row for row in teams if row.get(metric) is not None], key=lambda row: row.get(metric) or 0, reverse=True)[:10] for metric in metrics}

    @staticmethod
    def match_rankings(matches: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        return {
            "xg_total": sorted(matches, key=lambda row: row.get("xg_total") or 0, reverse=True)[:10],
            "shots": sorted(matches, key=lambda row: row.get("shots") or 0, reverse=True)[:10],
        }

    @staticmethod
    def _total(rows: list[dict[str, Any]], metric: str) -> float | int:
        total = round(sum(float(row.get(metric) or 0) for row in rows), 2)
        return int(total) if float(total).is_integer() else total

    @staticmethod
    def _endpoint_status(root: Path) -> list[dict[str, Any]]:
        rows = []
        for metadata_path in sorted(root.glob("*/metadata.json")):
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            rows.append(
                {
                    "endpoint_name": metadata.get("endpoint_name") or metadata_path.parent.name,
                    "fetch_status": metadata.get("fetch_status"),
                    "http_status": metadata.get("http_status"),
                    "request_url": metadata.get("request_url"),
                    "response_hash": metadata.get("response_hash"),
                    "fetched_at": metadata.get("fetched_at"),
                }
            )
        return rows
