from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .player_analytics import (
    build_reference_distribution,
    calculate_player_radar,
    macroposition_for,
)
from .curation_repository import CurationRepository
from .player_positions import (
    apply_player_override,
    assign_benchmark_cohorts,
    infer_match_positions,
    radar_profile_group,
    summarize_tournament_positions,
)


SOURCE = "TheStatsAPI"
DEFAULT_OPENING_MATCH_ID = "mt_153637999"
HOME_TIMEZONE = ZoneInfo("America/Sao_Paulo")

# Shot outcomes already carried by the shotmap product (with richer detail: xG, body part,
# on-target vs blocked vs post) — excluded from a player's events timeline to avoid showing the
# same finalization twice (once via events/timeline, once via shotmap).
SHOT_COVERED_EVENT_TYPES = {
    "goal", "shot_on_target", "shot_off_target", "shot_blocked",
    "penalty_scored", "penalty_missed", "penalty_saved",
}


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

    def __init__(
        self,
        data_root: Path | str = Path("data"),
        *,
        curation_repository: CurationRepository | None = None,
    ) -> None:
        self.data_root = Path(data_root)
        self.curation_repository = curation_repository

    def available(self, year: int) -> bool:
        return bool(self.fixtures(year))

    def competition(self, year: int) -> dict[str, Any]:
        fixtures = self.match_items(year)
        standings = self.standings_by_group(year)
        group_fixtures = [match for match in fixtures if match.get("group_name")]
        group_stage_complete = bool(group_fixtures) and all(
            match.get("home_score") is not None
            and match.get("away_score") is not None
            and self._is_effectively_finished(match)
            for match in group_fixtures
        )
        best_thirds = self.best_third_placed_teams(
            year, standings, group_stage_complete=group_stage_complete
        )
        if group_stage_complete:
            self._finalize_group_statuses(standings, best_thirds)
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
                "group_stage_complete": group_stage_complete,
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
        now = datetime.now(timezone.utc)
        finished = sorted(
            (match for match in fixtures if self._is_effectively_finished(match, now=now)),
            key=lambda match: str(match.get("match_date") or ""),
            reverse=True,
        )
        upcoming = sorted(
            (match for match in fixtures if not self._is_effectively_finished(match, now=now)),
            key=lambda match: str(match.get("match_date") or ""),
        )
        today = now.astimezone(HOME_TIMEZONE).date()
        matches_today = [
            match
            for match in fixtures
            if self._local_match_date(match) == today
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
        pulse = self.home_pulse(fixtures, now=now)
        knockout_summary = self.home_knockout_summary(fixtures, pulse=pulse)
        discoveries = self.home_discoveries(player_rows, team_rows, match_details)
        eliminated = self._eliminated_team_names(fixtures)
        featured_team = next(
            (row for row in compact_teams.get("xg", []) if row.get("team_name") not in eliminated),
            (compact_teams.get("xg") or [None])[0],
        )
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
                "pulse": pulse,
                "knockout_summary": knockout_summary,
                "discoveries": discoveries,
                "highlights": {
                    # A statistically dominant but already-eliminated team is not "defining the
                    # Cup" anymore — the featured team is the strongest xG side still alive.
                    "top_team": featured_team,
                    "top_player": (compact_players.get("goals") or [None])[0],
                    "team_ranking": compact_teams.get("xg", []),
                    "player_ranking": compact_players.get("goals", []),
                },
                "notice": None if fixtures else "Dados da edição ainda não disponíveis.",
            }
        )

    @classmethod
    def home_pulse(
        cls,
        fixtures: list[dict[str, Any]],
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        knockout = cls.knockout_state(fixtures)
        populated = [round_ for round_ in knockout["rounds"] if round_["matches"]]
        current_index = next(
            (
                index
                for index, round_ in enumerate(populated)
                if any(
                    not cls._is_effectively_finished(match, now=reference)
                    for match in round_["matches"]
                )
            ),
            max(len(populated) - 1, 0),
        )
        current_round = populated[current_index] if populated else None
        next_round = (
            populated[current_index + 1]
            if populated and current_index + 1 < len(populated)
            else None
        )
        resolved_knockout_by_id = {
            resolved_match.get("match_id"): resolved_match
            for round_ in knockout["rounds"]
            for resolved_match in round_["matches"]
            if resolved_match.get("match_id")
        }
        today = reference.astimezone(HOME_TIMEZONE).date()
        today_matches = [
            cls._with_resolved_sides(match, resolved_knockout_by_id)
            for match in fixtures
            if cls._local_match_date(match) == today
        ]

        classified = []
        for round_ in populated:
            for match in round_["matches"]:
                if not cls._is_effectively_finished(match, now=reference):
                    continue
                home_score = number(match.get("home_score"))
                away_score = number(match.get("away_score"))
                winner_name = match.get("winner_name")
                decided_by = match.get("decided_by")
                if home_score is None or away_score is None or not winner_name:
                    continue
                home_won = winner_name == match["home"].get("team_name")
                winner = match["home"] if home_won else match["away"]
                eliminated = match["away"] if home_won else match["home"]
                eliminated_name = eliminated.get("team_name")
                if not winner_name or not eliminated_name:
                    continue
                if decided_by == "penalties":
                    narrative = (
                        f"{winner_name} avançou nos pênaltis após empate por "
                        f"{int(home_score)}–{int(away_score)} contra {eliminated_name}."
                    )
                else:
                    winner_score = home_score if home_won else away_score
                    eliminated_score = away_score if home_won else home_score
                    narrative = (
                        f"{winner_name} avançou após vencer {eliminated_name} "
                        f"por {int(winner_score)}–{int(eliminated_score)}."
                    )
                classified.append(
                    {
                        "match": match,
                        "phase": round_["name"],
                        "winner_name": winner_name,
                        "winner_id": winner.get("team_id"),
                        "eliminated_name": eliminated_name,
                        "eliminated_id": eliminated.get("team_id"),
                        "decided_by": decided_by,
                        "score_label": match.get("score_label"),
                        "narrative": narrative,
                    }
                )
        classified.sort(
            key=lambda item: str(item["match"].get("kickoff_at") or ""),
            reverse=True,
        )
        return {
            "current_phase": current_round["name"] if current_round else None,
            "today_matches": today_matches,
            "classified_recent": classified[:4],
            "next_phase": next_round["name"] if next_round else None,
            "next_matchups": (next_round or current_round or {}).get("matches", [])[:4],
        }

    @staticmethod
    def _with_resolved_sides(
        fixture: dict[str, Any],
        resolved_knockout_by_id: dict[Any, dict[str, Any]],
    ) -> dict[str, Any]:
        """Attach the same resolved home/away placeholder objects the bracket uses, so "Agenda de
        hoje" never shows raw winner codes (W75) for knockout matches whose opponents aren't
        decided yet — group-stage fixtures (never placeholders) pass through unchanged."""
        resolved = resolved_knockout_by_id.get(fixture.get("match_id"))
        if not resolved:
            return fixture
        return {**fixture, "home": resolved["home"], "away": resolved["away"]}

    @classmethod
    def home_knockout_summary(
        cls,
        fixtures: list[dict[str, Any]],
        *,
        pulse: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        pulse = pulse or cls.home_pulse(fixtures)
        knockout = cls.knockout_state(fixtures)
        visible_rounds = [
            round_
            for round_ in knockout["rounds"]
            if round_["matches"]
            and round_["name"] in {pulse.get("current_phase"), pulse.get("next_phase")}
        ]
        return {
            "current_phase": pulse.get("current_phase"),
            "next_phase": pulse.get("next_phase"),
            "rounds": visible_rounds,
        }

    @classmethod
    def home_discoveries(
        cls,
        players: list[dict[str, Any]],
        teams: list[dict[str, Any]],
        details: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        def player_rows(rows: list[dict[str, Any]], value_fn: Any) -> list[dict[str, Any]]:
            return [
                {**cls._compact_player(row), "value": round(float(value_fn(row)), 2)}
                for row in rows
            ]

        def team_metric_rows(rows: list[dict[str, Any]], value_fn: Any) -> list[dict[str, Any]]:
            return [
                {**cls._compact_team(row), "value": round(float(value_fn(row)), 2)}
                for row in rows
            ]

        eligible_minutes = [
            row
            for row in players
            if float(row.get("minutes_played") or 0) >= 120
            and float(row.get("goals") or 0) >= 1
        ]
        eligible_shooters = [
            row for row in players if float(row.get("shots") or 0) >= 5
        ]
        eligible_teams = [
            row for row in teams if float(row.get("played") or 0) >= 3
        ]

        goals_per_90 = sorted(
            player_rows(
                eligible_minutes,
                lambda row: float(row.get("goals") or 0)
                / float(row.get("minutes_played") or 1)
                * 90,
            ),
            key=lambda row: row["value"],
            reverse=True,
        )
        xg_per_shot = sorted(
            player_rows(
                eligible_shooters,
                lambda row: float(row.get("xg") or 0) / float(row.get("shots") or 1),
            ),
            key=lambda row: row["value"],
            reverse=True,
        )
        conversion = sorted(
            player_rows(
                eligible_shooters,
                lambda row: float(row.get("goals") or 0) / float(row.get("shots") or 1) * 100,
            ),
            key=lambda row: row["value"],
            reverse=True,
        )

        lowest_xga = sorted(
            team_metric_rows(eligible_teams, lambda row: row.get("xga") or 0),
            key=lambda row: row["value"],
        )
        shots_per_game = sorted(
            team_metric_rows(
                eligible_teams,
                lambda row: float(row.get("shots") or 0) / float(row.get("played") or 1),
            ),
            key=lambda row: row["value"],
            reverse=True,
        )
        goals_minus_xg = sorted(
            team_metric_rows(
                eligible_teams,
                lambda row: float(row.get("goals_for") or 0) - float(row.get("xg") or 0),
            ),
            key=lambda row: row["value"],
            reverse=True,
        )

        match_rows = []
        goal_rows = []
        for detail in details:
            match = detail.get("match") or {}
            if not match.get("match_id"):
                continue
            shots = detail.get("shot_map") or []
            events = detail.get("events") or []
            xg_row = next(
                (row for row in detail.get("stats_comparison") or [] if row.get("metric") == "expected_goals"),
                None,
            )
            xg_values = [
                float(value or 0)
                for key, value in (xg_row or {}).items()
                if key not in {"metric", "unit", "section"}
            ]
            match_rows.append(
                {
                    **cls._compact_match(match),
                    "events_total": len(events),
                    "shots_on_target": sum(1 for shot in shots if shot.get("is_on_target")),
                    "xg_gap": round(abs(xg_values[0] - xg_values[1]), 2) if len(xg_values) >= 2 else None,
                }
            )
            for shot in shots:
                if shot.get("is_goal") and number(shot.get("minute")) is not None:
                    goal_rows.append({**cls._compact_match(match), **shot, "value": number(shot.get("minute"))})

        most_events = sorted(
            [{**row, "value": row["events_total"]} for row in match_rows if row["events_total"]],
            key=lambda row: row["value"],
            reverse=True,
        )
        most_on_target = sorted(
            [{**row, "value": row["shots_on_target"]} for row in match_rows if row["shots_on_target"]],
            key=lambda row: row["value"],
            reverse=True,
        )
        balanced = sorted(
            [{**row, "value": row["xg_gap"]} for row in match_rows if row["xg_gap"] is not None],
            key=lambda row: row["value"],
        )
        earliest = sorted(goal_rows, key=lambda row: row["value"])
        latest = sorted(goal_rows, key=lambda row: row["value"], reverse=True)

        def metric(
            metric_id: str,
            title: str,
            description: str,
            eligibility: str,
            entity: str,
            unit: str,
            rows: list[dict[str, Any]],
        ) -> dict[str, Any]:
            return {
                "id": metric_id,
                "title": title,
                "description": description,
                "eligibility": eligibility,
                "entity": entity,
                "unit": unit,
                "rows": rows,
            }

        return {
            "players": [
                metric("goals_per_90", "Gols por 90", "Frequência de gols ajustada a 90 minutos em campo.", "Mínimo de 120 minutos e 1 gol", "player", "gols/90", goals_per_90),
                metric("xg_per_shot", "xG por finalização", "Qualidade média das chances finalizadas.", "Mínimo de 5 finalizações", "player", "xG", xg_per_shot),
                metric("shot_conversion", "Conversão de chutes", "Percentual de finalizações transformadas em gol.", "Mínimo de 5 finalizações", "player", "%", conversion),
            ],
            "teams": [
                metric("lowest_xga", "Menos xG cedido", "Defesas que concederam chances de menor qualidade.", "Mínimo de 3 jogos", "team", "xG", lowest_xga),
                metric("shots_per_game", "Finalizações por jogo", "Volume ofensivo médio por partida.", "Mínimo de 3 jogos", "team", "chutes", shots_per_game),
                metric("goals_minus_xg", "Gols - xG", "Diferença entre gols marcados e gols esperados.", "Mínimo de 3 jogos", "team", "gols - xG", goals_minus_xg),
            ],
            "matches": [
                metric("most_events", "Maior volume de eventos", "Partidas com mais ações registradas.", "Somente jogos com eventos disponíveis", "match", "eventos", most_events),
                metric("most_on_target", "Mais chutes no alvo", "Jogos que mais exigiram os goleiros.", "Somente jogos com mapa de chutes", "match", "no alvo", most_on_target),
                metric("most_balanced_xg", "Jogo mais equilibrado", "Menor diferença de xG entre as seleções.", "Somente jogos com xG para as duas equipes", "match", "diferença de xG", balanced),
            ],
            "curiosities": [
                metric("earliest_goal", "Gol mais cedo", "Os gols marcados mais próximos do início.", "Somente gols com minuto informado", "match", "min", earliest),
                metric("latest_goal", "Gol mais tardio", "Os gols marcados mais próximos do fim.", "Somente gols com minuto informado", "match", "min", latest),
            ],
        }

    @staticmethod
    def _match_datetime(match: dict[str, Any]) -> datetime | None:
        value = match.get("match_date") or match.get("kickoff_at")
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @classmethod
    def _local_match_date(cls, match: dict[str, Any]) -> Any:
        parsed = cls._match_datetime(match)
        return parsed.astimezone(HOME_TIMEZONE).date() if parsed else None

    @classmethod
    def _is_effectively_finished(
        cls,
        match: dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> bool:
        if str(match.get("status") or "").lower() == "finished":
            return True
        parsed = cls._match_datetime(match)
        has_score = all(
            match.get(key) is not None for key in ("home_score", "away_score")
        )
        reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        return bool(parsed and has_score and parsed <= reference - timedelta(hours=4))

    @staticmethod
    def _eliminated_team_names(fixtures: list[dict[str, Any]]) -> set[str]:
        """Teams knocked out of the tournament: losers of decided knockout matches."""
        eliminated: set[str] = set()
        for match in fixtures:
            if match.get("group_name"):
                continue
            home_score = number(match.get("home_score"))
            away_score = number(match.get("away_score"))
            if home_score is None or away_score is None:
                continue
            if home_score != away_score:
                loser = match.get("home_team") if away_score > home_score else match.get("away_team")
            else:
                penalty_home = number(match.get("penalty_home_score"))
                penalty_away = number(match.get("penalty_away_score"))
                if penalty_home is None or penalty_away is None or penalty_home == penalty_away:
                    continue
                loser = match.get("home_team") if penalty_away > penalty_home else match.get("away_team")
            if loser:
                eliminated.add(str(loser))
        return eliminated

    @staticmethod
    def _compact_player(row: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "player_id",
            "player_name",
            "team_id",
            "team_name",
            "position",
            "resolved_position",
            "games",
            "minutes_played",
            "goals",
            "assists",
            "shots",
            "shots_on_target",
            "xg",
            "xa",
            "rating",
            "photo_url",
            "photo_asset_path",
            "photo_credit",
            "photo_source_url",
            "photo_alt_text",
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
        source_items = self.match_items(year)
        items = self._public_match_items(source_items)
        finished = [item for item in items if item.get("public_status") == "Encerrado"]
        upcoming = [
            item for item in items
            if item.get("public_status") in {"Agendado", "Hoje", "A definir"}
        ]
        goals = sum(
            int(item.get("home_score") or 0) + int(item.get("away_score") or 0)
            for item in finished
        )
        knockout = self.knockout_state(source_items)
        stage_counts = Counter(item.get("stage") or "not_informed" for item in items)
        stage_order = (
            "Group Stage", "round_of_32", "round_of_16", "quarter_final",
            "quarter_finals", "semi_final", "semi_finals", "third_place", "final",
        )
        return json_safe(
            {
                "year": year,
                "source": SOURCE,
                "available": bool(items),
                "summary": {
                    "matches": len(items),
                    "finished": len(finished),
                    "upcoming": len(upcoming),
                    "goals": goals,
                    "goals_per_match": round(goals / len(finished), 2) if finished else None,
                    "current_phase": knockout.get("current_phase"),
                },
                "filters": self.match_filters(items),
                "stage_distribution": [
                    {
                        "stage": stage,
                        "stage_label": self._public_stage_label(stage),
                        "matches": stage_counts[stage],
                    }
                    for stage in stage_order
                    if stage_counts.get(stage)
                ],
                "items": items,
                "notice": None if items else "Calendário da Copa 2026 ainda não está disponível.",
            }
        )

    @classmethod
    def _public_match_items(cls, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        knockout = cls.knockout_state(rows)
        knockout_by_id = {
            str(match.get("match_id")): match
            for round_ in knockout.get("rounds", [])
            for match in round_.get("matches", [])
            if match.get("match_id")
        }
        public_rows = []
        for row in rows:
            result = row.copy()
            result["stage_label"] = cls._public_stage_label(row.get("stage"))
            parsed = cls._match_datetime(row)
            result["local_date"] = parsed.astimezone(HOME_TIMEZONE).date().isoformat() if parsed else None
            bracket_match = knockout_by_id.get(str(row.get("match_id")))
            if bracket_match:
                for side_name in ("home", "away"):
                    side = bracket_match.get(side_name) or {}
                    defined = bool(side.get("defined") and side.get("team_name"))
                    result[f"{side_name}_team"] = (
                        side.get("team_name") if defined else side.get("placeholder") or "A definir"
                    )
                    result[f"{side_name}_team_id"] = side.get("team_id") if defined else None
                    result[f"{side_name}_defined"] = defined
                for field in (
                    "winner_name", "decided_by", "score_label",
                    "penalty_home_score", "penalty_away_score",
                ):
                    result[field] = bracket_match.get(field)
            else:
                result["home_defined"] = bool(result.get("home_team"))
                result["away_defined"] = bool(result.get("away_team"))
            result["public_status"] = cls._public_match_status(result, parsed)
            public_rows.append(result)
        return public_rows

    @staticmethod
    def _public_match_status(row: dict[str, Any], kickoff: datetime | None) -> str:
        status = str(row.get("status") or "").strip().casefold()
        now = datetime.now(timezone.utc)
        stale = bool(kickoff and now - kickoff.astimezone(timezone.utc) > timedelta(hours=4))
        has_score = row.get("home_score") is not None and row.get("away_score") is not None
        if status in {"live", "in progress", "ao vivo"}:
            if stale:
                return "Encerrado" if has_score else "Aguardando resultado"
            return "Ao vivo"
        if status in {"finished", "finalizado", "encerrado"}:
            return "Encerrado"
        if stale and not has_score:
            return "Aguardando resultado"
        if not row.get("home_defined") or not row.get("away_defined"):
            return "A definir"
        if kickoff and kickoff.astimezone(HOME_TIMEZONE).date() == now.astimezone(HOME_TIMEZONE).date():
            return "Hoje"
        return "Agendado"

    @staticmethod
    def _public_stage_label(value: Any) -> str:
        normalized = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
        labels = {
            "group_stage": "Fase de grupos",
            "round_of_32": "Fase de 32",
            "round_of_16": "Oitavas",
            "quarter_final": "Quartas",
            "quarter_finals": "Quartas",
            "semi_final": "Semifinais",
            "semi_finals": "Semifinais",
            "third_place": "Disputa de 3º lugar",
            "final": "Final",
        }
        return labels.get(normalized, "Fase não informada")

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
        details = self._all_match_details(year)
        rows = self._aggregate_player_analytics(self._aggregate_players(details))
        shots = [shot for detail in details for shot in detail.get("shot_map", [])]
        return json_safe(
            {
                "year": year,
                "source": SOURCE,
                "available": bool(rows),
                "summary": {
                    "players": len(rows),
                    "goals": self._total(rows, "goals"),
                    "assists": self._total(rows, "assists"),
                    "shots": self._total(rows, "shots"),
                    "xg": self._total(rows, "xg"),
                    "xa": self._total(rows, "xa"),
                },
                "leaders": self.player_leaders(rows),
                "filters": {
                    "teams": sorted({row["team_name"] for row in rows if row.get("team_name")}),
                    "positions": sorted({row["position"] for row in rows if row.get("position")}),
                    "position_groups": sorted({row["api_position_group"] for row in rows if row.get("api_position_group")}),
                    "inferred_positions": sorted({row["resolved_position"] for row in rows if row.get("resolved_position")}),
                },
                "scatter": rows,
                "shot_breakdowns": self._player_shot_breakdowns(shots),
                "items": rows,
                "notice": None if rows else "Estatísticas de jogadores ainda não estão disponíveis.",
            }
        )

    def player_detail(
        self,
        year: int,
        player_id: str,
        scope: str = "all",
        match_id: str | None = None,
    ) -> dict[str, Any]:
        details = self._all_match_details(year)
        return self._player_detail_from_details(
            year,
            player_id,
            details,
            scope=scope,
            match_id=match_id,
        )

    def _player_detail_from_details(
        self,
        year: int,
        player_id: str,
        details: list[dict[str, Any]],
        scope: str = "all",
        match_id: str | None = None,
        scoped_players: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        scope = scope if scope in {"all", "group_stage", "knockout", "match"} else "all"
        player_matches = [
            detail
            for detail in details
            if any(player.get("player_id") == player_id for player in detail.get("players", []))
        ]
        available_matches = [
            {
                "match_id": detail["match"].get("match_id"),
                "label": self._match_label(detail["match"]),
                "match_date": detail["match"].get("match_date"),
                "stage": detail["match"].get("stage"),
                "group_name": detail["match"].get("group_name"),
            }
            for detail in player_matches
        ]

        def in_scope(detail: dict[str, Any]) -> bool:
            match = detail.get("match") or {}
            if scope == "match":
                return bool(match_id) and str(match.get("match_id")) == str(match_id)
            is_group = bool(match.get("group_name")) or "group" in str(match.get("stage") or "").casefold()
            if scope == "group_stage":
                return is_group
            if scope == "knockout":
                return not is_group
            return True

        scoped_details = [detail for detail in details if in_scope(detail)]
        logs = []
        shots = []
        for detail in scoped_details:
            match = detail["match"]
            for player in detail["players"]:
                if player.get("player_id") == player_id:
                    participated = (
                        float(player.get("minutes_played") or 0) > 0
                        and player.get("played") is not False
                    )
                    team_name = player.get("api_team_name") or player.get("team_name")
                    opponent = (
                        match.get("away_team")
                        if team_name == match.get("home_team")
                        else match.get("home_team")
                    )
                    logs.append(
                        {
                            **player,
                            "match": self._match_label(match),
                            "match_id": match.get("match_id"),
                            "match_date": match.get("match_date"),
                            "stage": match.get("stage"),
                            "group_name": match.get("group_name"),
                            "opponent": opponent,
                            "participated": participated,
                        }
                    )
            for shot in detail["shot_map"]:
                if shot.get("player_id") == player_id:
                    shots.append(shot)
        logs.sort(key=lambda row: (str(row.get("match_date") or "9999"), str(row.get("match_id") or "")))
        if not logs:
            return {
                "year": year,
                "available": False,
                "notice": "Não há dados do jogador neste recorte.",
                "context": {"scope": scope, "match_id": match_id},
                "available_matches": available_matches,
            }
        if scoped_players is None:
            scoped_players = self._aggregate_player_analytics(
                self._aggregate_players(scoped_details)
            )
        summary = next((row for row in scoped_players if row.get("player_id") == player_id), None)
        if summary is None:
            return {
                "year": year,
                "available": False,
                "notice": "Não há dados do jogador neste recorte.",
                "context": {"scope": scope, "match_id": match_id},
                "available_matches": available_matches,
            }
        macroposition = summary.get("radar_profile_group") or macroposition_for(summary.get("position"))
        benchmark_position = summary.get("benchmark_position") or macroposition
        peers = [row for row in scoped_players if row.get("benchmark_position") == benchmark_position and float(row.get("minutes_played") or 0) >= 30]
        benchmark_label = summary.get("benchmark_label") or self._position_benchmark_label(macroposition)
        benchmarks = self._metric_benchmarks(
            peers,
            summary,
            {
                "minutes_played": "higher", "games": "higher", "goals": "higher", "assists": "higher", "xg": "higher", "xa": "higher",
                "shots": "higher", "shots_on_target": "higher", "xg_per_shot": "higher",
                "shot_conversion": "higher", "goals_per_90": "higher", "assists_per_90": "higher",
                "xg_per_90": "higher", "xa_per_90": "higher", "shots_per_90": "higher",
                "key_passes": "higher", "key_passes_per_90": "higher", "accurate_passes": "higher",
                "pass_accuracy": "higher", "long_pass_accuracy": "higher", "defensive_actions": "higher",
                "defensive_actions_per_90": "higher", "duels_won": "higher", "aerial_won": "higher", "tackles": "higher",
                "interceptions": "higher", "clearances": "higher", "saves": "higher",
                "saves_per_90": "higher", "goal_involvements": "higher",
                "goal_involvements_per_90": "higher", "rating": "higher",
            },
            benchmark_label,
        )
        reference = build_reference_distribution(scoped_players)
        reference_metrics = reference.get(benchmark_position, {})
        mean_player = {metric: values.get("mean") for metric, values in reference_metrics.items()}
        mean_player["minutes_played"] = 90
        benchmark_radar = calculate_player_radar(
            mean_player,
            reference,
            macroposition,
            reference_key=str(benchmark_position),
        ).get("radar", [])
        scoped_shots = [shot for detail in scoped_details for shot in detail.get("shot_map", [])]
        peer_ids = {row.get("player_id") for row in peers if row.get("player_id")}
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
                "radar": summary.get("radar", []),
                "benchmark_radar": benchmark_radar,
                "leader_radar": self._radar_leader(peers),
                "radar_dimensions": summary.get("radar_dimensions", {}),
                "benchmarks": benchmarks,
                "shot_benchmark": self._shot_profile_benchmark(scoped_shots, peer_ids, player_id),
                "context": {"scope": scope, "match_id": match_id},
                "available_matches": available_matches,
                "comparable_players": self._nearest_by_radar(summary, peers, id_key="player_id", name_key="player_name"),
            }
        )

    def profiles(self, year: int) -> dict[str, Any]:
        details = self._all_match_details(year)
        players = self._aggregate_player_analytics(self._aggregate_players(details))
        teams = self._curate_teams(
            self.team_rows(year, self.standings_by_group(year), details)
        )
        return json_safe(
            {
                "year": year,
                "available": bool(players or teams),
                "players": players,
                "teams": teams,
                "filters": {
                    "player_teams": sorted({row["team_name"] for row in players if row.get("team_name")}),
                    "positions": sorted({row["position"] for row in players if row.get("position")}),
                    "position_groups": sorted({row["api_position_group"] for row in players if row.get("api_position_group")}),
                    "inferred_positions": sorted({row["resolved_position"] for row in players if row.get("resolved_position")}),
                    "groups": sorted({row["group_name"] for row in teams if row.get("group_name")}),
                },
            }
        )

    def teams(self, year: int) -> dict[str, Any]:
        details = self._all_match_details(year)
        rows = self._curate_teams(
            self.team_rows(year, self.standings_by_group(year), details)
        )
        shots = [shot for detail in details for shot in detail.get("shot_map", [])]
        return json_safe(
            {
                "year": year,
                "source": SOURCE,
                "available": bool(rows),
                "summary": {
                    "teams": len(rows),
                    "goals": self._total(rows, "goals_for"),
                    "xg": self._total(rows, "xg"),
                    "shots": self._total(rows, "shots"),
                    "goals_per_match": self._team_goals_per_match(rows),
                },
                "rankings": self.team_leaders(rows),
                "shot_breakdowns": self._player_shot_breakdowns(shots),
                "items": rows,
                "notice": None if rows else "Seleções ainda não estão disponíveis.",
            }
        )

    def team_detail(self, year: int, team_id: str) -> dict[str, Any]:
        details = self._all_match_details(year)
        return self._team_detail_from_details(year, team_id, details)

    def _team_detail_from_details(
        self,
        year: int,
        team_id: str,
        details: list[dict[str, Any]],
    ) -> dict[str, Any]:
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
        matches.sort(
            key=lambda row: (str(row.get("match_date") or "9999"), str(row.get("match_id") or ""))
        )
        team_metric_directions = {
            "played": "higher", "wins": "higher",
            "goals_for": "higher", "goals_against": "lower", "goal_difference": "higher",
            "xg": "higher", "xga": "lower", "xg_difference": "higher",
            "shots": "higher", "shots_against": "lower", "shots_on_target": "higher",
            "goals_per_game": "higher", "goals_against_per_game": "lower",
            "xg_per_game": "higher", "xga_per_game": "lower", "shots_per_game": "higher",
            "shots_against_per_game": "lower", "conversion": "higher", "pass_accuracy": "higher",
            "average_possession": "higher", "recoveries_per_game": "higher", "tackles_per_game": "higher",
            "goals_minus_xg": "higher",
        }
        benchmarks = self._metric_benchmarks(teams, team, team_metric_directions, "Média da Copa")
        radar = self._team_profile_radar(benchmarks)
        all_team_radars = [
            {"team_id": row.get("team_id"), "team_name": row.get("team_name"), "radar": self._team_profile_radar(self._metric_benchmarks(teams, row, team_metric_directions, "Média da Copa"))}
            for row in teams
        ]
        all_shots = [shot for detail in details for shot in detail.get("shot_map", [])]
        team_ids = {row.get("team_id") for row in teams if row.get("team_id")}
        curated_team = self._curate_teams([team])[0]
        return json_safe(
            {
                "year": year,
                "source": SOURCE,
                "available": True,
                "team": curated_team,
                "summary": curated_team,
                "matches": matches,
                "players": sorted(players, key=lambda row: (row.get("minutes_played") or 0, row.get("rating") or 0), reverse=True),
                "shots": shots,
                "shot_map": shots,
                "benchmarks": benchmarks,
                "radar": radar,
                "benchmark_radar": [{"axis": axis["axis"], "value": 50} for axis in radar],
                "leader_radar": self._radar_leader(all_team_radars),
                "shot_benchmark": self._shot_profile_benchmark(all_shots, team_ids, team_id, entity_key="team_id"),
                "comparable_teams": self._nearest_by_radar(
                    {"team_id": team_id, "radar": radar},
                    all_team_radars,
                    id_key="team_id", name_key="team_name",
                ),
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
        *,
        group_stage_complete: bool = False,
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
            if group_stage_complete and index <= 8:
                row["status"] = "Classificado"
            elif group_stage_complete:
                row["status"] = "Eliminado"
            elif index <= 7:
                row["status"] = "Dentro no momento"
            elif index == 8:
                row["status"] = "Última vaga"
            else:
                row["status"] = "Fora agora"
        return ranked

    @staticmethod
    def _finalize_group_statuses(
        standings: dict[str, list[dict[str, Any]]],
        best_thirds: list[dict[str, Any]],
    ) -> None:
        qualified_thirds = {
            str(team.get("team_id"))
            for team in best_thirds
            if number(team.get("rank")) is not None and number(team.get("rank")) <= 8
        }
        for teams in standings.values():
            for team in teams:
                position = number(team.get("position"))
                if position is not None and position <= 2:
                    team["classification_status"] = "Classificado"
                elif position == 3 and str(team.get("team_id")) in qualified_thirds:
                    team["classification_status"] = "Classificado como melhor terceiro"
                else:
                    team["classification_status"] = "Eliminado"

    def team_rows(
        self,
        year: int,
        standings: dict[str, list[dict[str, Any]]],
        details: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows = [row.copy() for group in standings.values() for row in group]
        by_name = {row["team_name"]: row for row in rows}
        cumulative_metrics = {
            "shots_on_target": "shots_on_target",
            "passes": "passes",
            "accurate_passes": "accurate_passes",
            "ball_recoveries": "recoveries",
            "tackles": "tackles",
            "interceptions": "interceptions",
            "clearances": "clearances",
            "fouls": "fouls",
            "yellow_cards": "yellow_cards",
            "red_cards": "red_cards",
        }
        for detail in details:
            for team in detail["team_summary"]:
                row = by_name.get(team.get("team_name"))
                if not row:
                    continue
                row["shots"] = (row.get("shots") or 0) + int(team.get("shots") or 0)
                row["goals"] = (row.get("goals") or 0) + int(team.get("goals") or 0)
            match = detail["match"]
            # Campaign record derived from every played match (group + knockout). The standings
            # base rows only cover the group stage, so once knockout bundles exist the standings
            # `played` would divide metrics accumulated over more matches than it counts.
            home_score = number(match.get("home_score"))
            away_score = number(match.get("away_score"))
            if home_score is not None and away_score is not None:
                for team, scored, conceded in (
                    (match.get("home_team"), home_score, away_score),
                    (match.get("away_team"), away_score, home_score),
                ):
                    row = by_name.get(team)
                    if not row:
                        continue
                    row["campaign_played"] = int(row.get("campaign_played") or 0) + 1
                    row["campaign_goals_for"] = int(row.get("campaign_goals_for") or 0) + int(scored)
                    row["campaign_goals_against"] = int(row.get("campaign_goals_against") or 0) + int(conceded)
                    outcome = "wins" if scored > conceded else "losses" if scored < conceded else "draws"
                    row[f"campaign_{outcome}"] = int(row.get(f"campaign_{outcome}") or 0) + 1
            xg_rows: dict[str, dict[str, Any]] = {}
            for item in detail["stats_comparison"]:
                xg_rows.setdefault(str(item.get("metric")), item)
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
            home = match.get("home_team")
            away = match.get("away_team")
            stage_label = self._public_stage_label(match.get("stage"))
            for team, opponent in ((home, away), (away, home)):
                row = by_name.get(team)
                if not row:
                    continue
                if stage_label != "Fase não informada":
                    row.setdefault("stages", set()).add(stage_label)
                for metric, field in cumulative_metrics.items():
                    value = number((xg_rows.get(metric) or {}).get(team))
                    if value is not None:
                        row[field] = round(float(row.get(field) or 0) + float(value), 3)
                possession = number((xg_rows.get("ball_possession") or {}).get(team))
                if possession is not None:
                    row["possession_total"] = float(row.get("possession_total") or 0) + float(possession)
                    row["possession_games"] = int(row.get("possession_games") or 0) + 1
                opponent_shots = number((xg_rows.get("total_shots") or {}).get(opponent))
                if opponent_shots is not None:
                    row["shots_against"] = int(row.get("shots_against") or 0) + int(opponent_shots)
                opponent_on_target = number((xg_rows.get("shots_on_target") or {}).get(opponent))
                if opponent_on_target is not None:
                    row["shots_on_target_against"] = int(row.get("shots_on_target_against") or 0) + int(opponent_on_target)
        for row in rows:
            campaign_played = int(row.pop("campaign_played", 0) or 0)
            campaign = {key: int(row.pop(f"campaign_{key}", 0) or 0) for key in ("wins", "draws", "losses", "goals_for", "goals_against")}
            # Only replace the standings record when the played matches cover at least the group
            # stage — if bundles are missing, the group-only standings stay authoritative.
            if campaign_played >= int(row.get("played") or 0):
                row["played"] = campaign_played
                row.update(campaign)
            row["xg"] = round(float(row.get("xg") or 0), 2)
            row["xga"] = round(float(row.get("xga") or 0), 2)
            row["xg_difference"] = round(row["xg"] - row["xga"], 2)
            played = int(row.get("played") or 0)
            shots = int(row.get("shots") or 0)
            passes = float(row.get("passes") or 0)
            row["goal_difference"] = int(row.get("goals_for") or 0) - int(row.get("goals_against") or 0)
            row["shot_difference"] = shots - int(row.get("shots_against") or 0)
            row["goals_minus_xg"] = round(float(row.get("goals_for") or 0) - row["xg"], 2)
            row["goals_per_game"] = round(float(row.get("goals_for") or 0) / played, 2) if played else None
            row["goals_against_per_game"] = round(float(row.get("goals_against") or 0) / played, 2) if played else None
            row["xg_per_game"] = round(row["xg"] / played, 2) if played else None
            row["xga_per_game"] = round(row["xga"] / played, 2) if played else None
            row["shots_per_game"] = round(shots / played, 2) if played else None
            row["shots_against_per_game"] = round(float(row.get("shots_against") or 0) / played, 2) if played else None
            row["conversion"] = round(float(row.get("goals_for") or 0) / shots * 100, 1) if shots else None
            row["pass_accuracy"] = round(float(row.get("accurate_passes") or 0) / passes * 100, 1) if passes else None
            row["average_possession"] = round(float(row.get("possession_total") or 0) / int(row.get("possession_games") or 1), 1) if row.get("possession_games") else None
            row["recoveries_per_game"] = round(float(row.get("recoveries") or 0) / played, 2) if played else None
            row["tackles_per_game"] = round(float(row.get("tackles") or 0) / played, 2) if played else None
            row["fouls_per_game"] = round(float(row.get("fouls") or 0) / played, 2) if played else None
            row["yellow_cards_per_game"] = round(float(row.get("yellow_cards") or 0) / played, 2) if played else None
            row.pop("possession_total", None)
            row.pop("possession_games", None)
            stage_order = ["Fase de grupos", "Fase de 32", "Oitavas", "Quartas", "Semifinais", "Disputa de 3º lugar", "Final"]
            row["stages"] = sorted(row.get("stages") or set(), key=lambda label: stage_order.index(label) if label in stage_order else len(stage_order))
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
            match_id = root.name.split("=", 1)[-1]
            players = self._payload(root / "player_stats/response.json").get("data", [])
            lineups = self._payload(root / "lineups/response.json").get("data", {})
            events_payload = self._payload(root / "events/response.json").get("data", {})
            raw_events = events_payload.get("events", []) if isinstance(events_payload, dict) else []
            player_rows = self._players(players, lineups)
            rows.extend(self._apply_position_inference(match_id, lineups, player_rows, raw_events))
        return rows

    @staticmethod
    def _apply_position_inference(
        match_id: str,
        lineups: dict[str, Any],
        player_rows: list[dict[str, Any]],
        raw_events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Attach per-match inferred position fields so radar lookups can classify by role, not just raw API position."""
        inferred_positions = {
            row["player_id"]: row
            for row in infer_match_positions(match_id, lineups, player_rows, raw_events)
            if row.get("player_id")
        }
        for player in player_rows:
            inference = inferred_positions.get(player.get("player_id"), {})
            player.update(inference)
            player["resolved_position"] = (
                inference.get("inferred_role")
                if inference.get("role_confidence") in {"high", "medium"}
                else inference.get("api_position_group") or player.get("position")
            )
        return player_rows

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
        player_rows = self._players(players_raw, lineups)
        event_rows = self._events(match, events_payload, player_rows)
        raw_events = events_payload.get("events", []) if isinstance(events_payload, dict) else []
        player_rows = self._apply_position_inference(match_id, lineups, player_rows, raw_events)
        player_rows = self._curate_players(player_rows)
        stats_comparison = self._stats_comparison(match, stats)
        reference = reference_distribution or build_reference_distribution(
            self._reference_player_rows(year)
        )
        player_rows = self._enrich_match_players(player_rows, reference, match)
        for player in player_rows:
            player_id = player.get("player_id")
            player_name = player.get("player_name")
            api_player_name = player.get("api_player_name") or player_name
            player["player_shots"] = [
                shot
                for shot in shot_map
                if (player_id and shot.get("player_id") == player_id)
                or (api_player_name and shot.get("player_name") == api_player_name)
            ]
            player["player_events"] = [
                event
                for event in event_rows
                if str(event.get("type") or "").lower() not in SHOT_COVERED_EVENT_TYPES
                and api_player_name
                and (
                    event.get("player_name") == api_player_name
                    or event.get("player_out_name") == api_player_name
                )
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
            "penalties": self._penalties(shots_raw),
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
        final_score = score.get("final_score") if isinstance(score.get("final_score"), dict) else {}
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
            "penalty_home_score": final_score.get("home"),
            "penalty_away_score": final_score.get("away"),
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
        match: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not players:
            return []
        home_team = (match or {}).get("home_team")
        away_team = (match or {}).get("away_team")
        enriched = []
        for row in players:
            macroposition = radar_profile_group(row)
            analytics = calculate_player_radar(
                row,
                reference_distribution,
                macroposition,
            )
            impact = self._match_impact(row, match or {})
            team_name = row.get("team_name")
            opponent_name = away_team if team_name == home_team else home_team if team_name == away_team else None
            enriched.append(
                {
                    **row,
                    "macroposition": macroposition,
                    "impact_score": impact.get("score"),
                    "impact_category": impact.get("category"),
                    "impact_reasons": impact.get("reasons", []),
                    "profile_score": analytics.get("profile_score"),
                    "radar": analytics.get("radar", []),
                    "radar_dimensions": analytics.get("dimensions", {}),
                    "impact_summary": self._player_impact_summary(impact),
                    "opponent_name": opponent_name,
                }
            )
        return sorted(enriched, key=lambda item: item.get("impact_score") or 0, reverse=True)

    @staticmethod
    def _player_impact_summary(impact: dict[str, Any]) -> str | None:
        score = impact.get("score")
        if score is None:
            return None
        reasons = impact.get("reasons") or []
        detail = " · ".join(reasons[:3])
        return f"{impact.get('category')}: {score:.1f}/100{f' · {detail}' if detail else ''}."

    @staticmethod
    def _match_impact(row: dict[str, Any], match: dict[str, Any]) -> dict[str, Any]:
        """Score decisive match actions without reusing the positional radar percentile."""
        value = lambda key: float(number(row.get(key)) or 0)
        role = str(row.get("macroposition") or macroposition_for(row.get("position")))
        minutes = value("minutes_played")
        if minutes <= 0 and value("rating") <= 0:
            return {"score": 0.0, "category": "Participação", "reasons": []}

        rating = value("rating")
        score = max(0.0, min(38.0, (rating - 5.0) * 10.0))
        goals = value("goals")
        assists = value("assists")
        xg = value("xg")
        xa = value("xa")
        shots_on_target = value("shots_on_target")
        key_passes = value("key_passes")
        defensive_actions = sum(value(key) for key in ("tackles", "interceptions", "clearances", "recoveries"))
        duels = value("duels_won")

        if role == "Goleiro":
            team = row.get("team_name")
            home = match.get("home_team")
            conceded = value("goals_conceded")
            if not row.get("goals_conceded") and team in {home, match.get("away_team")}:
                conceded = float(match.get("away_score") or 0) if team == home else float(match.get("home_score") or 0)
            saves = value("saves")
            score = max(0.0, min(24.0, (rating - 5.0) * 8.0))
            score += saves * 6.0 + min(defensive_actions * 0.8, 5.0)
            score += min(value("accurate_passes") * 0.08, 3.0)
            if minutes > 0 and conceded == 0:
                score += 8.0
            score -= conceded * 6.0
            reasons = []
            if saves:
                reasons.append(f"{saves:g} {'defesa' if saves == 1 else 'defesas'}")
            if conceded == 0 and minutes > 0:
                reasons.append("sem sofrer gol")
            if defensive_actions:
                reasons.append(f"{defensive_actions:g} ações defensivas")
            return {
                "score": round(max(0.0, min(100.0, score)), 1),
                "category": "Destaque defensivo",
                "reasons": reasons[:3],
            }

        score += goals * 24.0 + assists * 18.0 + xg * 8.0 + xa * 12.0
        score += shots_on_target * 2.5 + key_passes * 2.0
        if role in {"Zagueiro", "Lateral/Ala"}:
            score += defensive_actions * 1.5 + duels * 0.7 + min(value("accurate_passes") * 0.06, 4.0)
        elif role == "Volante/Meio-campista":
            score += defensive_actions * 1.0 + duels * 0.6 + min(value("accurate_passes") * 0.08, 5.0)
        else:
            score += duels * 0.4 + value("successful_dribbles") * 0.8

        reasons = []
        candidates = [
            (goals > 0, f"{goals:g} {'gol' if goals == 1 else 'gols'}"),
            (assists > 0, f"{assists:g} {'assistência' if assists == 1 else 'assistências'}"),
            (xg > 0, f"{xg:g} xG"),
            (xa > 0, f"{xa:g} xA"),
            (shots_on_target > 0, f"{shots_on_target:g} no alvo"),
            (key_passes > 0, f"{key_passes:g} passes para finalização"),
            (defensive_actions > 0, f"{defensive_actions:g} ações defensivas"),
            (duels > 0, f"{duels:g} duelos vencidos"),
        ]
        reasons.extend(label for available, label in candidates if available)
        if goals or assists:
            category = "Decisivo"
        elif xg or xa or shots_on_target or key_passes:
            category = "Destaque ofensivo"
        elif role in {"Zagueiro", "Lateral/Ala"}:
            category = "Destaque defensivo"
        else:
            category = "Destaque da partida"
        return {
            "score": round(max(0.0, min(100.0, score)), 1),
            "category": category,
            "reasons": reasons[:3],
        }

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
    def _pt_br_number(value: Any) -> str:
        """Format a number for embedding directly into narrative text, matching the pt-BR comma
        decimal separator and 2-decimal precision used everywhere else in the product (frontend's
        Intl.NumberFormat with maximumFractionDigits: 2)."""
        parsed = number(value)
        if parsed is None:
            return str(value)
        if isinstance(parsed, int):
            return str(parsed)
        return f"{round(parsed, 2):g}".replace(".", ",")

    @classmethod
    def _match_story(
        cls,
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
            displayed_home = round(float(xg[0]), 2)
            displayed_away = round(float(xg[1]), 2)
            if displayed_home == displayed_away:
                lines.append(
                    f"A criação foi equilibrada: {cls._pt_br_number(displayed_home)} xG para cada lado."
                )
            else:
                team = home if xg[0] > xg[1] else away
                creation_team = team
                value, other = xg if team == home else (xg[1], xg[0])
                lines.append(f"{team} controlou a criação: {cls._pt_br_number(value)} xG contra {cls._pt_br_number(other)}.")

        shots_values = values("total_shots")
        target_values = values("shots_on_target")
        if shots_values:
            team = home if shots_values[0] >= shots_values[1] else away
            value, other = shots_values if team == home else (shots_values[1], shots_values[0])
            subject = "A equipe também" if team == creation_team else team
            detail = f"{subject} finalizou mais: {cls._pt_br_number(value)} a {cls._pt_br_number(other)}"
            if target_values:
                target, target_other = target_values if team == home else (target_values[1], target_values[0])
                detail += f", com {cls._pt_br_number(target)} chutes no alvo contra {cls._pt_br_number(target_other)}"
            lines.append(f"{detail}.")

        recoveries = values("ball_recoveries")
        if recoveries:
            team = home if recoveries[0] >= recoveries[1] else away
            value, other = recoveries if team == home else (recoveries[1], recoveries[0])
            if team != creation_team:
                lines.append(f"{team} teve algum respiro sem bola, liderando em recuperações por {cls._pt_br_number(value)} a {cls._pt_br_number(other)}.")
            else:
                lines.append(f"A equipe também recuperou mais bolas: {cls._pt_br_number(value)} a {cls._pt_br_number(other)}.")

        goals = sorted(
            [shot for shot in shots if shot.get("is_goal") and shot.get("player_name")],
            key=lambda shot: number(shot.get("minute")) or 0,
        )
        if goals:
            grouped_goals: list[dict[str, Any]] = []
            for goal in goals[:3]:
                player_name = goal.get("player_name")
                minute = int(number(goal.get("minute")) or 0)
                existing = next((entry for entry in grouped_goals if entry["player_name"] == player_name), None)
                if existing:
                    existing["minutes"].append(minute)
                else:
                    grouped_goals.append({"player_name": player_name, "minutes": [minute]})
            def describe_scorer(entry: dict[str, Any]) -> str:
                minutes_text = " e ".join(f"{minute}'" for minute in entry["minutes"])
                if len(entry["minutes"]) > 1:
                    return f"{entry['player_name']}, aos {minutes_text}"
                return f"{entry['player_name']} aos {minutes_text}"

            descriptions = [describe_scorer(entry) for entry in grouped_goals]
            total_goals = sum(len(entry["minutes"]) for entry in grouped_goals)
            if total_goals == 1:
                lines.append(f"O gol da partida foi marcado por {descriptions[0]}.")
            else:
                lines.append(f"Os gols foram marcados por {' e '.join(descriptions)}.")
        top_shot = max(shots, key=lambda shot: float(shot.get("xg") or 0), default=None)
        if top_shot:
            lines.append(
                f"A chance mais clara foi de {top_shot.get('player_name')}, "
                f"com {cls._pt_br_number(top_shot.get('xg'))} xG aos {int(number(top_shot.get('minute')) or 0)}'."
            )
        return lines

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
                    "resolved_position": row.get("resolved_position"),
                    "macroposition": row.get("macroposition"),
                    "impact_score": row.get("impact_score"),
                    "impact_category": row.get("impact_category"),
                    "impact_reasons": row.get("impact_reasons"),
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

    def _events(
        self,
        match: dict[str, Any],
        events_payload: dict[str, Any],
        player_rows: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        events = events_payload.get("events", []) if isinstance(events_payload, dict) else []
        events = events if isinstance(events, list) else []
        outgoing_by_index = self._resolve_substitution_outgoing(events, player_rows or [])
        rows = []
        for index, event in enumerate(events):
            if not isinstance(event, dict):
                continue
            team = event.get("team") if isinstance(event.get("team"), dict) else {}
            player = event.get("player") if isinstance(event.get("player"), dict) else {}
            player_in = event.get("player_in") if isinstance(event.get("player_in"), dict) else {}
            player_out = event.get("player_out") if isinstance(event.get("player_out"), dict) else {}
            assist = event.get("assist") if isinstance(event.get("assist"), dict) else {}
            outgoing = outgoing_by_index.get(index)
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
                    "player_in_name": player_in.get("name") or (player.get("name") if event.get("type") == "substitution" else None),
                    "player_out_name": player_out.get("name") or (outgoing.get("player_name") if outgoing else None),
                    "assist_name": assist.get("name"),
                    "decision": event.get("decision") or event.get("outcome"),
                    "detail": event.get("detail") or event.get("description"),
                    "xg": number(event.get("expected_goals") or event.get("xg")),
                }
            )
        return rows

    @staticmethod
    def _resolve_substitution_outgoing(
        events: list[dict[str, Any]],
        player_rows: list[dict[str, Any]],
    ) -> dict[int, dict[str, Any]]:
        """TheStatsAPI substitution events only report the incoming player. Infer who went out by
        matching the substitution minute against teammates whose minutes_played stopped there —
        the closest, not-yet-assigned candidate on the same team wins."""
        by_team: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for row in player_rows:
            team_id = row.get("team_id")
            minutes = number(row.get("minutes_played"))
            if team_id is not None and minutes is not None and minutes < 90:
                by_team[team_id].append(row)
        assigned: set[Any] = set()
        resolved: dict[int, dict[str, Any]] = {}
        for index, event in enumerate(events):
            if not isinstance(event, dict) or event.get("type") != "substitution":
                continue
            team = event.get("team") if isinstance(event.get("team"), dict) else {}
            team_id = team.get("id")
            minute = number(event.get("minute"))
            incoming = event.get("player") if isinstance(event.get("player"), dict) else {}
            incoming_id = incoming.get("id")
            if team_id is None or minute is None:
                continue
            candidates = [
                row for row in by_team.get(team_id, [])
                if row.get("player_id") not in assigned
                and row.get("player_id") != incoming_id
                and abs((number(row.get("minutes_played")) or 0) - minute) <= 3
            ]
            if not candidates:
                continue
            best = min(candidates, key=lambda row: abs((number(row.get("minutes_played")) or 0) - minute))
            assigned.add(best.get("player_id"))
            resolved[index] = best
        return resolved

    @staticmethod
    def _match_goals(shots: list[dict[str, Any]], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # The shot map only carries the minute, so same-minute goals (common in stoppage
        # time, which the provider reports as plain 90') tie. The event timeline carries a
        # `sequence` — use it as the within-minute tiebreak so goals keep the real order.
        goal_sequences: dict[tuple[Any, str], Any] = {}
        for event in events:
            if str(event.get("type") or "") not in {"goal", "own_goal", "penalty_scored"}:
                continue
            key = (event.get("minute"), str(event.get("player_name") or "").casefold())
            goal_sequences.setdefault(key, event.get("sequence"))

        def order_key(row: dict[str, Any]) -> tuple[float, float]:
            sequence = number(row.get("sequence"))
            return (float(row.get("minute") or 0), sequence if sequence is not None else float("inf"))

        goals = [
            {
                "minute": shot.get("minute"),
                "team_id": shot.get("team_id"),
                "team_name": shot.get("team_name"),
                "player_id": shot.get("player_id"),
                "player_name": shot.get("player_name"),
                "xg": shot.get("xg"),
                "sequence": goal_sequences.get(
                    (shot.get("minute"), str(shot.get("player_name") or "").casefold())
                ),
                "source": "shotmap",
            }
            for shot in shots
            if shot.get("is_goal")
        ]
        if goals:
            return sorted(goals, key=order_key)
        return sorted(
            [
                {
                    "minute": event.get("minute"),
                    "team_name": event.get("team_name"),
                    "player_name": event.get("player_name"),
                    "sequence": event.get("sequence"),
                    "source": "events",
                }
                for event in events
                if event.get("type") == "goal"
            ],
            key=order_key,
        )

    @staticmethod
    def _penalties(shots: Any) -> list[dict[str, Any]]:
        """Every penalty kick of the match (shootout and in-game), with goal-mouth placement.

        Shootout kicks are kept out of the shot map and of every xG aggregate — the provider
        assigns a flat ~0.82 xG to each kick, which would pollute match/player numbers. In-game
        penalties keep counting in the shot map and xG; here they only gain the placement view."""
        kicks = []
        for shot in shots if isinstance(shots, list) else []:
            if not isinstance(shot, dict):
                continue
            situation = str(shot.get("situation") or "").casefold()
            shootout = situation == "shootout"
            if not shootout and not shot.get("is_penalty") and situation != "penalty":
                continue
            mouth = shot.get("goal_mouth_coordinates") if isinstance(shot.get("goal_mouth_coordinates"), dict) else {}
            raw_xg = number(shot.get("expected_goals"))
            kicks.append(
                {
                    "team_id": shot.get("team_id"),
                    "team_name": shot.get("team_name"),
                    "player_id": shot.get("player_id"),
                    "player_name": shot.get("player_name"),
                    "minute": shot.get("minute"),
                    "phase": "shootout" if shootout else "in_game",
                    "is_goal": bool(shot.get("is_goal")),
                    "result": shot.get("result"),
                    "body_part": shot.get("body_part"),
                    "xg": None if shootout else (max(0.0, float(raw_xg)) if raw_xg is not None else None),
                    "goal_mouth_location": shot.get("goal_mouth_location"),
                    "goal_mouth_y": number(mouth.get("y")),
                    "goal_mouth_z": number(mouth.get("z")),
                }
            )
        kicks.sort(key=lambda row: row.get("minute") or 0)
        for order, kick in enumerate(kicks, start=1):
            kick["order"] = order
        return kicks

    def _shot_map(self, match: dict[str, Any], shots: Any) -> list[dict[str, Any]]:
        rows = []
        for shot in shots if isinstance(shots, list) else []:
            if not isinstance(shot, dict):
                continue
            # Shootout kicks live in their own section (see _shootout), never in the map.
            if str(shot.get("situation") or "").casefold() == "shootout":
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
        fixtures_by_round: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for fixture in fixtures:
            round_key = cls._knockout_round(fixture)
            if not round_key:
                continue
            fixtures_by_round[round_key].append(fixture)

        match_number_starts = {
            "round_of_32": 73,
            "round_of_16": 89,
            "quarter_finals": 97,
            "semi_finals": 101,
            "third_place": 103,
            "final": 104,
        }
        winner_matchups: dict[str, dict[str, Any]] = {}
        matches_by_round: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for round_key, _ in round_specs:
            ordered = sorted(
                fixtures_by_round.get(round_key, []),
                key=lambda item: str(item.get("match_date") or item.get("utc_date") or ""),
            )
            for index, fixture in enumerate(ordered):
                match = cls._knockout_match(fixture, winner_matchups=winner_matchups)
                matches_by_round[round_key].append(match)
                match_number = match_number_starts[round_key] + index
                home_label = cls._knockout_side_label(match["home"])
                away_label = cls._knockout_side_label(match["away"])
                if home_label and away_label:
                    winner_side = None
                    if match.get("winner_name"):
                        winner_side = next(
                            (
                                side
                                for side in (match["home"], match["away"])
                                if side.get("team_name") == match["winner_name"]
                            ),
                            None,
                        )
                    winner_matchups[str(match_number)] = {
                        "matchup": f"{home_label} x {away_label}",
                        "winner": winner_side,
                    }

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
        group_matches = [match for match in fixtures if match.get("group_name")]
        group_stage_complete = bool(group_matches) and all(
            match.get("home_score") is not None
            and match.get("away_score") is not None
            and cls._is_effectively_finished(match)
            for match in group_matches
        )
        knockout_started = any(
            cls._is_effectively_finished(match)
            or str(match.get("status") or "").casefold() in {"live", "in_progress"}
            for round_ in rounds
            for match in round_["matches"]
        )
        current_round = next(
            (
                round_
                for round_ in rounds
                if round_["matches"]
                and any(not cls._is_effectively_finished(match) for match in round_["matches"])
            ),
            next((round_ for round_ in reversed(rounds) if round_["matches"]), None),
        )
        if knockout_started:
            notice = "Mata-mata em andamento: acompanhe classificados e próximos confrontos."
        elif group_stage_complete:
            notice = "Confrontos definidos para a Fase de 32."
        elif incomplete:
            notice = "Confrontos serão atualizados conforme a fase de grupos avançar."
        else:
            notice = "Caminho final da Copa definido até a decisão."
        return {
            "available": available,
            "rounds": rounds,
            "current_phase": current_round.get("name") if current_round else None,
            "group_stage_complete": group_stage_complete,
            "started": knockout_started,
            "notice": notice,
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
            "quarter_final": "quarter_finals",
            "quarterfinals": "quarter_finals",
            "quartas": "quarter_finals",
            "semi_finals": "semi_finals",
            "semi_final": "semi_finals",
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
    def _knockout_match(
        cls,
        fixture: dict[str, Any],
        *,
        winner_matchups: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        home = cls._knockout_side(
            fixture.get("home_team"), fixture.get("home_team_id"), winner_matchups
        )
        away = cls._knockout_side(
            fixture.get("away_team"), fixture.get("away_team_id"), winner_matchups
        )
        home_score = number(fixture.get("home_score"))
        away_score = number(fixture.get("away_score"))
        penalty_home = number(fixture.get("penalty_home_score"))
        penalty_away = number(fixture.get("penalty_away_score"))
        winner_name = None
        decided_by = None
        score_label = None
        if home_score is not None and away_score is not None:
            if home_score != away_score:
                home_won = home_score > away_score
                winner_name = (home if home_won else away).get("team_name")
                winner_score, loser_score = (home_score, away_score) if home_won else (away_score, home_score)
                score_label = f"{int(winner_score)}–{int(loser_score)}"
                decided_by = "regular"
            elif penalty_home is not None and penalty_away is not None and penalty_home != penalty_away:
                home_won = penalty_home > penalty_away
                winner_name = (home if home_won else away).get("team_name")
                winner_penalties, loser_penalties = (penalty_home, penalty_away) if home_won else (penalty_away, penalty_home)
                score_label = (
                    f"{int(home_score)}–{int(away_score)} "
                    f"({int(winner_penalties)}–{int(loser_penalties)} nos pênaltis)"
                )
                decided_by = "penalties"
        return {
            "match_id": fixture.get("match_id"),
            "status": fixture.get("status"),
            "kickoff_at": fixture.get("match_date"),
            "home_score": fixture.get("home_score"),
            "away_score": fixture.get("away_score"),
            "penalty_home_score": fixture.get("penalty_home_score"),
            "penalty_away_score": fixture.get("penalty_away_score"),
            "home": home,
            "away": away,
            "winner_name": winner_name,
            "decided_by": decided_by,
            "score_label": score_label,
        }

    @staticmethod
    def _knockout_side(
        team_name: Any,
        team_id: Any,
        winner_matchups: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
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
            source = (winner_matchups or {}).get(winner.group(1)) or {}
            resolved_winner = source.get("winner")
            if resolved_winner and resolved_winner.get("team_name"):
                return {
                    "team_name": resolved_winner["team_name"],
                    "team_id": resolved_winner.get("team_id"),
                    "placeholder": None,
                    "defined": True,
                }
            matchup = source.get("matchup")
            placeholder = f"Vencedor de {matchup}" if matchup else "A definir"
        defined = bool(name and not placeholder)
        return {
            "team_name": name if defined else None,
            "team_id": team_id if defined else None,
            "placeholder": placeholder or ("A definir" if not defined else None),
            "defined": defined,
        }

    @staticmethod
    def _knockout_side_label(side: dict[str, Any]) -> str | None:
        return side.get("team_name") if side.get("defined") else None

    @staticmethod
    def competition_summary(fixtures: list[dict[str, Any]], players: list[dict[str, Any]], teams: list[dict[str, Any]]) -> dict[str, Any]:
        finished = [item for item in fixtures if item.get("status") == "finished"]
        goals = sum(int(item.get("home_score") or 0) + int(item.get("away_score") or 0) for item in finished)
        shots = sum(int(team.get("shots") or 0) for team in teams)
        clean_sheets = sum(
            1 for item in finished
            if int(item.get("home_score") or 0) == 0 or int(item.get("away_score") or 0) == 0
        )
        xg_total = round(sum(float(team.get("xg") or 0) for team in teams), 2)
        # Only players who actually stepped on the pitch count for the edition summary.
        active_players = sum(1 for row in players if float(row.get("minutes_played") or 0) > 0)
        return {
            "matches": len(fixtures),
            "finished": len(finished),
            "teams": len(teams),
            "players": active_players,
            "goals": goals,
            "goals_per_match": round(goals / len(finished), 2) if finished else None,
            "shots": shots,
            "shot_conversion": round(goals / shots * 100, 1) if shots else None,
            "clean_sheets": clean_sheets,
            "xg": xg_total,
            "xg_per_match": round(xg_total / len(finished), 2) if finished else None,
        }

    @staticmethod
    def match_filters(items: list[dict[str, Any]]) -> dict[str, list[str]]:
        return {
            "groups": sorted({str(item.get("group_name")) for item in items if item.get("group_name")}),
            "stages": sorted({str(item.get("stage")) for item in items if item.get("stage")}),
            "dates": sorted({str(item.get("local_date")) for item in items if item.get("local_date")}),
            "teams": sorted({
                item.get(f"{side}_team")
                for item in items
                for side in ("home", "away")
                if item.get(f"{side}_defined") and item.get(f"{side}_team")
            }),
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
        active_rows = [
            row for row in rows
            if float(row.get("minutes_played") or 0) > 0
            and row.get("played") is not False
        ]
        aggregate_rows = active_rows or rows
        first = aggregate_rows[0].copy()
        sum_metrics = (
            "minutes_played", "goals", "assists", "shots", "shots_on_target",
            "shots_off_target", "blocked_shots", "xg", "np_xg", "xa",
            "big_chances_created", "key_passes", "passes", "accurate_passes",
            "total_long_balls", "accurate_long_balls", "total_crosses",
            "accurate_crosses", "duels_won", "duels_lost", "aerial_won",
            "successful_dribbles", "dispossessed", "tackles", "interceptions",
            "clearances", "touches", "possession_lost", "fouls",
            "fouls_suffered", "offsides", "yellow_cards", "red_cards", "saves",
        )
        for metric in sum_metrics:
            values = [float(row[metric]) for row in active_rows if row.get(metric) is not None]
            first[metric] = round(sum(values), 3) if values else None
        first["games"] = len(active_rows)
        first["played"] = bool(active_rows)
        ratings = [
            float(row["rating"])
            for row in active_rows
            if row.get("rating") is not None and float(row.get("rating") or 0) > 0
        ]
        first["rating"] = round(sum(ratings) / len(ratings), 2) if ratings else None
        first["pass_accuracy"] = (
            round(float(first["accurate_passes"]) / float(first["passes"]) * 100, 1)
            if first.get("accurate_passes") is not None and first.get("passes") else None
        )
        first["long_pass_accuracy"] = (
            round(float(first["accurate_long_balls"]) / float(first["total_long_balls"]) * 100, 1)
            if first.get("accurate_long_balls") is not None and first.get("total_long_balls") else None
        )
        first["cross_accuracy"] = (
            round(float(first["accurate_crosses"]) / float(first["total_crosses"]) * 100, 1)
            if first.get("accurate_crosses") is not None and first.get("total_crosses") else None
        )
        first["xg_per_shot"] = (
            round(float(first["xg"]) / float(first["shots"]), 3)
            if first.get("xg") is not None and first.get("shots") else None
        )
        first["goals_minus_xg"] = (
            round(float(first["goals"]) - float(first["xg"]), 2)
            if first.get("goals") is not None and first.get("xg") is not None else None
        )
        minutes = float(first.get("minutes_played") or 0)

        def per_90(metric: str) -> float | None:
            value = first.get(metric)
            return round(float(value) / minutes * 90, 3) if value is not None and minutes > 0 else None

        first["goal_involvements"] = int(first.get("goals") or 0) + int(first.get("assists") or 0)
        first["defensive_actions"] = sum(float(first.get(metric) or 0) for metric in ("tackles", "interceptions", "clearances"))
        if float(first["defensive_actions"]).is_integer():
            first["defensive_actions"] = int(first["defensive_actions"])
        first["shot_conversion"] = round(float(first.get("goals") or 0) / float(first["shots"]) * 100, 1) if first.get("shots") else None
        for metric in ("goals", "assists", "xg", "xa", "shots", "key_passes", "duels_won", "saves"):
            first[f"{metric}_per_90"] = per_90(metric)
        first["goal_involvements_per_90"] = round(float(first["goal_involvements"]) / minutes * 90, 3) if minutes > 0 else None
        first["defensive_actions_per_90"] = round(float(first["defensive_actions"]) / minutes * 90, 3) if minutes > 0 else None
        first.update(summarize_tournament_positions(active_rows))
        return first

    def _aggregate_players(self, details: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for detail in details:
            for player in detail["players"]:
                if player.get("player_id"):
                    grouped[player["player_id"]].append(player)
        return sorted([self._merge_player_rows(rows) for rows in grouped.values()], key=lambda row: (row.get("goals") or 0, row.get("xg") or 0), reverse=True)

    def _curate_players(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.curation_repository:
            return [apply_player_override(row, None) for row in rows]
        player_overrides = self.curation_repository.player_overrides_map()
        team_overrides = self.curation_repository.team_overrides_map()
        curated = []
        for row in rows:
            result = apply_player_override(
                row,
                player_overrides.get(str(row.get("player_id"))),
            )
            team_override = team_overrides.get(str(row.get("team_id")))
            if team_override and team_override.get("display_name_override"):
                result["api_team_name"] = row.get("team_name")
                result["team_name"] = team_override["display_name_override"]
            curated.append(result)
        return curated

    def _curate_teams(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.curation_repository:
            return rows
        overrides = self.curation_repository.team_overrides_map()
        curated = []
        for row in rows:
            result = row.copy()
            override = overrides.get(str(row.get("team_id")))
            if override:
                result["api_team_name"] = row.get("team_name")
                if override.get("display_name_override"):
                    result["team_name"] = override["display_name_override"]
                for field in ("short_name_override", "flag_asset_path", "primary_color", "secondary_color"):
                    if override.get(field):
                        result[field] = override[field]
            curated.append(result)
        return curated

    def _aggregate_player_analytics(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cohort_rows = assign_benchmark_cohorts(self._curate_players(rows))
        reference = build_reference_distribution(cohort_rows)
        enriched = []
        for row in cohort_rows:
            macroposition = row.get("radar_profile_group") or radar_profile_group(row)
            analytics = calculate_player_radar(
                row,
                reference,
                macroposition,
                reference_key=row.get("benchmark_position"),
            )
            enriched.append(
                {
                    **row,
                    "macroposition": macroposition,
                    "impact_score": analytics.get("profile_score"),
                    "profile_score": analytics.get("profile_score"),
                    "radar": analytics.get("radar", []),
                    "radar_dimensions": analytics.get("dimensions", {}),
                }
            )
        return enriched

    @staticmethod
    def _team_match_row(team_name: str, detail: dict[str, Any]) -> dict[str, Any]:
        match = detail["match"]
        opponent = match.get("away_team") if match.get("home_team") == team_name else match.get("home_team")
        metrics: dict[str, dict[str, Any]] = {}
        for row in detail.get("stats_comparison", []):
            metrics.setdefault(str(row.get("metric")), row)
        is_home = match.get("home_team") == team_name
        return {
            **match,
            "opponent": opponent,
            "goals_for": match.get("home_score") if is_home else match.get("away_score"),
            "goals_against": match.get("away_score") if is_home else match.get("home_score"),
            "xg_for": (metrics.get("expected_goals") or {}).get(team_name),
            "xg_against": (metrics.get("expected_goals") or {}).get(opponent),
            "shots_for": (metrics.get("total_shots") or {}).get(team_name),
            "shots_against": (metrics.get("total_shots") or {}).get(opponent),
        }

    @staticmethod
    def _quantile(values: list[float], quantile: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        position = (len(ordered) - 1) * quantile
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        fraction = position - lower
        return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction

    @classmethod
    def _metric_benchmarks(
        cls,
        rows: list[dict[str, Any]],
        selected: dict[str, Any],
        metric_directions: dict[str, str],
        label: str,
    ) -> dict[str, Any]:
        metrics: dict[str, dict[str, Any]] = {}
        for metric, direction in metric_directions.items():
            values = [float(value) for row in rows if (value := number(row.get(metric))) is not None]
            selected_value = number(selected.get(metric))
            if not values or selected_value is None:
                continue
            average = sum(values) / len(values)
            better_or_equal = (
                sum(value >= float(selected_value) for value in values)
                if direction == "lower"
                else sum(value <= float(selected_value) for value in values)
            )
            metrics[metric] = {
                "selected_value": round(float(selected_value), 3),
                "average_value": round(average, 3),
                "median_value": round(float(cls._quantile(values, .5) or 0), 3),
                "percentile_25": round(float(cls._quantile(values, .25) or 0), 3),
                "percentile_75": round(float(cls._quantile(values, .75) or 0), 3),
                "percentile_90": round(float(cls._quantile(values, .9) or 0), 3),
                "delta": round(float(selected_value) - average, 3),
                "percentile": round(better_or_equal / len(values) * 100),
                "sample_size": len(values),
                "direction": direction,
            }
        return {"label": label, "sample_size": len(rows), "metrics": metrics}

    @staticmethod
    def _position_benchmark_label(macroposition: str) -> str:
        labels = {
            "Goleiro": "Média dos goleiros",
            "Lateral": "Média dos laterais",
            "Zagueiro": "Média dos zagueiros",
            "Meia ofensivo/Ponta": "Média dos meias ofensivos e pontas",
            "Volante/Meio-campista": "Média dos volantes e meio-campistas",
            "Centroavante": "Média dos centroavantes",
        }
        return labels.get(macroposition, f"Média da função {macroposition}")

    @staticmethod
    def _radar_leader(peers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Best value actually achieved by any peer in the same comparison population, per radar
        axis — a third reference point beyond "selected vs average" showing the distance to the
        absolute top, computed from the same per-peer radar scores already used for benchmarking."""
        by_axis: dict[str, float] = {}
        for peer in peers:
            for axis in peer.get("radar") or []:
                value = number(axis.get("value"))
                name = axis.get("axis")
                if value is None or not name:
                    continue
                if name not in by_axis or value > by_axis[name]:
                    by_axis[name] = value
        return [{"axis": axis, "value": value} for axis, value in by_axis.items()]

    @staticmethod
    def _nearest_by_radar(
        summary: dict[str, Any],
        peers: list[dict[str, Any]],
        *,
        id_key: str,
        name_key: str,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        """Suggest comparable entities by Euclidean distance between radar axis scores — a
        derived reading of the same aggregation already used for benchmarking, no new data."""
        own_axes = {axis.get("axis"): number(axis.get("value")) for axis in summary.get("radar") or [] if number(axis.get("value")) is not None}
        if len(own_axes) < 3:
            return []
        candidates = []
        for peer in peers:
            if peer.get(id_key) == summary.get(id_key):
                continue
            peer_axes = {axis.get("axis"): number(axis.get("value")) for axis in peer.get("radar") or [] if number(axis.get("value")) is not None}
            shared = [axis for axis in own_axes if axis in peer_axes]
            if len(shared) < 3:
                continue
            distance = sum((own_axes[axis] - peer_axes[axis]) ** 2 for axis in shared) ** 0.5
            candidates.append({
                "id": peer.get(id_key),
                "name": peer.get(name_key),
                "team_name": peer.get("team_name"),
                "distance": round(distance, 1),
            })
        candidates.sort(key=lambda item: item["distance"])
        return candidates[:limit]

    @staticmethod
    def _team_profile_radar(benchmarks: dict[str, Any]) -> list[dict[str, Any]]:
        metrics = benchmarks.get("metrics", {})
        axes = {
            "Ataque": (("xg_per_game", "xG por jogo"), ("goals_per_game", "gols por jogo")),
            "Finalização": (("shots_per_game", "finalizações por jogo"), ("conversion", "conversão")),
            "Defesa": (("xga_per_game", "xG cedido por jogo"), ("shots_against_per_game", "finalizações sofridas por jogo")),
            # "Controle" covers both possession/recovery control and passing precision — the
            # metric block of the same name mirrors exactly this set, so the axis and the block
            # share one name instead of the axis being called "Passe" while the block below it
            # is called "Controle".
            "Controle": (("average_possession", "posse média"), ("recoveries_per_game", "recuperações por jogo"), ("pass_accuracy", "precisão de passe")),
            "Eficiência": (("goals_minus_xg", "gols acima do xG"), ("xg_difference", "saldo de xG")),
        }
        radar = []
        for axis, definitions in axes.items():
            available = [(key, label) for key, label in definitions if key in metrics]
            values = [float(metrics[key]["percentile"]) for key, _ in available]
            if values:
                radar.append(
                    {
                        "axis": axis,
                        "value": round(sum(values) / len(values), 1),
                        "available_metrics": [label for _, label in available],
                    }
                )
        return radar

    @staticmethod
    def _shot_profile_benchmark(
        shots: list[dict[str, Any]],
        peer_ids: set[Any],
        selected_id: Any,
        *,
        entity_key: str = "player_id",
    ) -> dict[str, Any]:
        peers = {peer_id: [] for peer_id in peer_ids}
        for shot in shots:
            entity_id = shot.get(entity_key)
            if entity_id in peers:
                peers[entity_id].append(shot)
        peer_rows = list(peers.values())
        totals = {
            "shots": round(sum(len(rows) for rows in peer_rows) / len(peer_rows), 2) if peer_rows else None,
            "xg": round(sum(sum(float(shot.get("xg") or 0) for shot in rows) for rows in peer_rows) / len(peer_rows), 2) if peer_rows else None,
        }
        reference_shots = [shot for entity_id, rows in peers.items() if entity_id != selected_id for shot in rows]
        reference_peer_rows = [rows for entity_id, rows in peers.items() if entity_id != selected_id]
        distributions: dict[str, list[dict[str, Any]]] = {}
        for column in ("body_part", "shot_type"):
            counts = Counter(str(shot.get(column) or "Não informado") for shot in reference_shots)
            total = sum(counts.values())
            distributions[column] = [
                {"label": label, "percentage": round(count / total * 100, 1)}
                for label, count in counts.most_common()
            ] if total else []
        ranges = (
            (0, 15, "0–15"), (16, 30, "16–30"), (31, 45, "31–45+"),
            (46, 60, "46–60"), (61, 75, "61–75"), (76, 90, "76–90"),
            (91, float("inf"), "90+"),
        )
        minute_bins = []
        for start, end, label in ranges:
            counts = [
                sum(start <= float(shot.get("minute") or 0) <= end for shot in rows)
                for rows in reference_peer_rows
            ]
            minute_bins.append(
                {
                    "label": label,
                    "average_shots": round(sum(counts) / len(counts), 2) if counts else None,
                }
            )
        return {
            "totals": totals,
            "distributions": distributions,
            "minute_bins": minute_bins,
            "sample_size": len(peer_rows),
        }

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
    def _player_shot_breakdowns(shots: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = {}
        for column in ("body_part", "shot_type"):
            totals = Counter(str(shot.get(column) or "Não informado") for shot in shots)
            goals = Counter(
                str(shot.get(column) or "Não informado")
                for shot in shots
                if shot.get("is_goal")
            )
            result[column] = [
                {"label": label, "shots": total, "goals": goals.get(label, 0)}
                for label, total in totals.most_common()
            ]
        return result

    @staticmethod
    def _event_breakdown(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"label": label, "value": value} for label, value in Counter(str(event.get("type") or "unknown") for event in events).most_common()]

    @staticmethod
    def player_leaders(players: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        # Full rankings (no top-10 cap): the UI shows Top 5 and opens the whole list on demand.
        # Count-like metrics drop zero rows so the "complete ranking" ends where the stat ends;
        # signed/average metrics keep every measured player.
        metrics = ("goals", "xg", "shots", "shots_on_target", "xg_per_shot", "goals_minus_xg", "assists", "rating")
        keep_zero = {"goals_minus_xg", "rating"}
        played = [row for row in players if float(row.get("minutes_played") or 0) > 0]
        return {
            metric: sorted(
                [
                    row
                    for row in played
                    if row.get(metric) is not None
                    and (metric in keep_zero or float(row.get(metric) or 0) > 0)
                ],
                key=lambda row: row.get(metric) or 0,
                reverse=True,
            )
            for metric in metrics
        }

    @staticmethod
    def team_leaders(teams: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        metrics = ("xg", "xga", "xg_difference", "shots", "goals_for", "points")
        rankings = {}
        for metric in metrics:
            rankings[metric] = sorted(
                [row for row in teams if row.get(metric) is not None],
                key=lambda row: row.get(metric) or 0,
                reverse=True,
            )
        return rankings

    @staticmethod
    def match_rankings(matches: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        return {
            metric: sorted(
                [row for row in matches if row.get(metric) is not None],
                key=lambda row: row.get(metric) or 0,
                reverse=True,
            )
            for metric in ("xg_total", "shots")
        }

    @staticmethod
    def _total(rows: list[dict[str, Any]], metric: str) -> float | int:
        total = round(sum(float(row.get(metric) or 0) for row in rows), 2)
        return int(total) if float(total).is_integer() else total

    @staticmethod
    def _team_goals_per_match(rows: list[dict[str, Any]]) -> float | None:
        matches = sum(float(row.get("played") or 0) for row in rows) / 2
        goals = sum(float(row.get("goals_for") or 0) for row in rows)
        return round(goals / matches, 2) if matches else None

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
