from __future__ import annotations

import re
from collections import defaultdict
from typing import Any
from urllib.parse import urlparse

from .curation_repository import CurationRepository
from .data_service import DataService
from .player_positions import (
    DOMINANT_FEET,
    POSITION_GROUPS,
    POSITION_SIDES,
    PUBLIC_POSITION_ROLES,
    REVIEW_STATUSES,
    position_group_for_role,
    role_side,
)


class CurationValidationError(ValueError):
    pass


class AdminService:
    def __init__(
        self,
        data_service: DataService,
        repository: CurationRepository,
        *,
        year: int = 2026,
    ) -> None:
        self.data_service = data_service
        self.repository = repository
        self.year = year

    def config(self) -> dict[str, Any]:
        return {
            "year": self.year,
            "position_roles": list(PUBLIC_POSITION_ROLES),
            "position_groups": list(POSITION_GROUPS),
            "sides": list(POSITION_SIDES),
            "review_statuses": list(REVIEW_STATUSES),
            "dominant_feet": list(DOMINANT_FEET),
        }

    def _profile_data(self) -> dict[str, Any]:
        return self.data_service.profiles(self.year)

    def _players(self) -> list[dict[str, Any]]:
        profile = self._profile_data()
        overrides = self.repository.player_overrides_map()
        return [
            self._admin_player(player, overrides.get(str(player.get("player_id"))))
            for player in profile.get("players", [])
            if player.get("player_id")
        ]

    @staticmethod
    def _admin_player(
        player: dict[str, Any],
        override: dict[str, Any] | None,
    ) -> dict[str, Any]:
        manual_role = (override or {}).get("manual_position_role")
        status = (override or {}).get("review_status") or player.get("review_status") or "auto_inferred"
        return {
            "player_id": player.get("player_id"),
            "team_id": player.get("team_id"),
            "player_name": player.get("player_name"),
            "api_player_name": player.get("api_player_name") or player.get("player_name"),
            "team_name": player.get("team_name"),
            "jersey_number": player.get("jersey_number"),
            "api_position_group": player.get("api_position_group"),
            "inferred_position_role": player.get("primary_inferred_role") or player.get("inferred_position_role"),
            "inferred_side": player.get("primary_inferred_side") or "Indefinido",
            "manual_position_role": manual_role,
            "manual_position_group": (override or {}).get("manual_position_group"),
            "manual_secondary_roles": (override or {}).get("manual_secondary_roles") or [],
            "manual_side": (override or {}).get("manual_side"),
            "secondary_side": (override or {}).get("secondary_side"),
            "resolved_position_role": player.get("resolved_position"),
            "resolved_side": player.get("resolved_side"),
            "position_source": "manual" if manual_role else player.get("position_resolution_source") or "api",
            "role_confidence": "high" if manual_role else player.get("role_confidence") or "low",
            "review_status": status,
            "review_notes": (override or {}).get("review_notes"),
            "dominant_foot": (override or {}).get("dominant_foot"),
            "photo_url": (override or {}).get("photo_url") or player.get("photo_url"),
            "photo_asset_path": (override or {}).get("photo_asset_path") or player.get("photo_asset_path"),
            "photo_credit": (override or {}).get("photo_credit") or player.get("photo_credit"),
            "photo_source_url": (override or {}).get("photo_source_url") or player.get("photo_source_url"),
            "photo_alt_text": (override or {}).get("photo_alt_text") or player.get("photo_alt_text"),
            "has_override": override is not None,
            "needs_review": status in {"pending", "needs_check"} or player.get("role_confidence") == "low",
            "minutes_played": player.get("minutes_played"),
            "games": player.get("games"),
            "updated_at": (override or {}).get("updated_at"),
            "updated_by": (override or {}).get("updated_by"),
        }

    def players(self) -> dict[str, Any]:
        items = self._players()
        return {
            "year": self.year,
            "summary": self._player_summary(items),
            "items": items,
            **self.config(),
        }

    def player(self, player_id: str) -> dict[str, Any] | None:
        return next(
            (player for player in self._players() if str(player.get("player_id")) == player_id),
            None,
        )

    def teams(self) -> dict[str, Any]:
        profile = self._profile_data()
        players = self._players()
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for player in players:
            if player.get("team_id"):
                grouped[str(player["team_id"])].append(player)
        team_rows = {
            str(team.get("team_id")): team
            for team in profile.get("teams", [])
            if team.get("team_id")
        }
        overrides = self.repository.team_overrides_map()
        items = []
        for team_id, roster in grouped.items():
            base = team_rows.get(team_id, {})
            override = overrides.get(team_id) or {}
            reviewed = sum(player["review_status"] == "reviewed" for player in roster)
            pending = sum(player["needs_review"] for player in roster)
            items.append(
                {
                    "team_id": team_id,
                    "team_name": override.get("display_name_override") or base.get("team_name") or roster[0].get("team_name"),
                    "api_team_name": base.get("api_team_name") or roster[0].get("team_name"),
                    "group_name": base.get("group_name"),
                    "players": len(roster),
                    "reviewed_players": reviewed,
                    "pending_players": pending,
                    "curation_status": "reviewed" if reviewed == len(roster) else "in_progress" if reviewed else "pending",
                    "review_status": override.get("review_status") or "pending",
                    "has_override": bool(override),
                    "flag_asset_path": override.get("flag_asset_path"),
                    "primary_color": override.get("primary_color"),
                    "secondary_color": override.get("secondary_color"),
                }
            )
        items.sort(key=lambda item: str(item.get("team_name") or ""))
        return {"year": self.year, "summary": {"teams": len(items), "players": len(players)}, "items": items}

    def team(self, team_id: str) -> dict[str, Any] | None:
        team = next((row for row in self.teams()["items"] if str(row.get("team_id")) == team_id), None)
        if team is None:
            return None
        roster = [player for player in self._players() if str(player.get("team_id")) == team_id]
        return {
            "team": team,
            "override": self.repository.get_team_override(team_id),
            "summary": self._player_summary(roster),
            "players": roster,
        }

    @staticmethod
    def _player_summary(players: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "players": len(players),
            "reviewed": sum(player["review_status"] == "reviewed" for player in players),
            "pending": sum(player["needs_review"] for player in players),
            "overrides": sum(player["has_override"] for player in players),
            "without_photo": sum(not (player.get("photo_url") or player.get("photo_asset_path")) for player in players),
        }

    def save_player_override(
        self,
        player_id: str,
        values: dict[str, Any],
        *,
        updated_by: str | None,
    ) -> dict[str, Any]:
        current = self.player(player_id)
        if current is None:
            raise KeyError(player_id)
        payload = self._validate_player(values)
        payload["team_id"] = current.get("team_id")
        self.repository.upsert_player_override(player_id, payload, updated_by=updated_by)
        return self.player(player_id) or {}

    def save_team_override(
        self,
        team_id: str,
        values: dict[str, Any],
        *,
        updated_by: str | None,
    ) -> dict[str, Any]:
        if self.team(team_id) is None:
            raise KeyError(team_id)
        payload = self._validate_team(values)
        self.repository.upsert_team_override(team_id, payload, updated_by=updated_by)
        return self.team(team_id) or {}

    @staticmethod
    def _valid_url(value: Any, field: str) -> str | None:
        if value in (None, ""):
            return None
        parsed = urlparse(str(value))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise CurationValidationError(f"{field} precisa ser uma URL HTTP ou HTTPS válida.")
        return str(value).strip()

    @classmethod
    def _validate_player(cls, values: dict[str, Any]) -> dict[str, Any]:
        role = values.get("manual_position_role") or None
        group = values.get("manual_position_group") or None
        secondary = values.get("manual_secondary_roles") or []
        side = values.get("manual_side") or None
        secondary_side = values.get("secondary_side") or None
        foot = values.get("dominant_foot") or None
        status = values.get("review_status") or "pending"
        if role and role not in PUBLIC_POSITION_ROLES:
            raise CurationValidationError("Posição principal fora da lista controlada.")
        if group and group not in POSITION_GROUPS:
            raise CurationValidationError("Grupo de posição inválido.")
        expected_group = position_group_for_role(str(role)) if role else None
        if group and expected_group and group != expected_group:
            raise CurationValidationError("Grupo e posição principal são incompatíveis.")
        if not isinstance(secondary, list) or any(item not in PUBLIC_POSITION_ROLES for item in secondary):
            raise CurationValidationError("Posições secundárias fora da lista controlada.")
        if role in secondary:
            raise CurationValidationError("A posição principal não pode ser repetida como secundária.")
        if side and side not in POSITION_SIDES:
            raise CurationValidationError("Lado principal inválido.")
        expected_side = role_side(str(role)) if role else "Indefinido"
        if side and expected_side != "Indefinido" and side != expected_side:
            raise CurationValidationError("Lado principal incompatível com a posição escolhida.")
        if secondary_side and secondary_side not in POSITION_SIDES:
            raise CurationValidationError("Lado secundário inválido.")
        if foot and foot not in DOMINANT_FEET:
            raise CurationValidationError("Pé dominante inválido.")
        if status not in REVIEW_STATUSES:
            raise CurationValidationError("Status de revisão inválido.")
        asset_path = str(values.get("photo_asset_path") or "").strip() or None
        if asset_path and (".." in asset_path or asset_path.startswith(("/", "\\"))):
            raise CurationValidationError("Caminho local da foto precisa ser relativo e seguro.")
        return {
            "team_id": values.get("team_id"),
            "display_name_override": str(values.get("display_name_override") or "").strip() or None,
            "manual_position_group": group,
            "manual_position_role": role,
            "manual_secondary_roles": list(dict.fromkeys(secondary)),
            "manual_side": side,
            "secondary_side": secondary_side,
            "dominant_foot": foot,
            "photo_url": cls._valid_url(values.get("photo_url"), "Foto"),
            "photo_asset_path": asset_path,
            "photo_credit": str(values.get("photo_credit") or "").strip() or None,
            "photo_source_url": cls._valid_url(values.get("photo_source_url"), "Fonte da foto"),
            "photo_alt_text": str(values.get("photo_alt_text") or "").strip() or None,
            "review_status": status,
            "review_notes": str(values.get("review_notes") or "").strip() or None,
        }

    @staticmethod
    def _validate_team(values: dict[str, Any]) -> dict[str, Any]:
        status = values.get("review_status") or "pending"
        if status not in REVIEW_STATUSES:
            raise CurationValidationError("Status de revisão inválido.")
        colors = {}
        for field in ("primary_color", "secondary_color"):
            value = str(values.get(field) or "").strip() or None
            if value and not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
                raise CurationValidationError("Cores precisam usar o formato hexadecimal #RRGGBB.")
            colors[field] = value
        flag_path = str(values.get("flag_asset_path") or "").strip() or None
        if flag_path and (".." in flag_path or flag_path.startswith(("/", "\\"))):
            raise CurationValidationError("Caminho da bandeira precisa ser relativo e seguro.")
        return {
            "display_name_override": str(values.get("display_name_override") or "").strip() or None,
            "short_name_override": str(values.get("short_name_override") or "").strip() or None,
            "flag_asset_path": flag_path,
            **colors,
            "status_notes": str(values.get("status_notes") or "").strip() or None,
            "review_status": status,
        }
