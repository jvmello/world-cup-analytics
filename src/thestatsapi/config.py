from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


SOURCE_NAME = "thestatsapi"
DEFAULT_BASE_URL = "https://api.thestatsapi.com/api"
WORLD_CUP_2026_COMPETITION_ID = "comp_6107"
WORLD_CUP_2026_SEASON_ID = "sn_118868"
WORLD_CUP_2026_EDITION = 2026


@dataclass(frozen=True)
class EndpointSpec:
    name: str
    path: str
    fetch_stage: str
    default_params: dict[str, Any] = field(default_factory=dict)
    fallback_paths: tuple[str, ...] = ()
    paginated: bool = False
    required: bool = False

    def resolve_paths(self, *, match_id: str | None = None) -> tuple[str, ...]:
        paths = (self.path, *self.fallback_paths)
        return tuple(self._resolve_path(path, match_id=match_id) for path in paths)

    def _resolve_path(self, path: str, *, match_id: str | None = None) -> str:
        if "{match_id}" not in path:
            return path
        if not match_id:
            raise ValueError(f"Endpoint {self.name} requires match_id.")
        return path.format(match_id=match_id)


ENDPOINTS: dict[str, EndpointSpec] = {
    "fixtures": EndpointSpec(
        name="fixtures",
        path="/football/matches",
        fetch_stage="fixtures",
        default_params={
            "competition_id": WORLD_CUP_2026_COMPETITION_ID,
            "season_id": WORLD_CUP_2026_SEASON_ID,
            "per_page": 100,
        },
        paginated=True,
        required=True,
    ),
    "standings": EndpointSpec(
        name="standings",
        path=(
            f"/football/competitions/{WORLD_CUP_2026_COMPETITION_ID}"
            f"/seasons/{WORLD_CUP_2026_SEASON_ID}/standings"
        ),
        fetch_stage="core",
        required=True,
    ),
    "match_detail": EndpointSpec(
        name="match_detail",
        path="/football/matches/{match_id}",
        fetch_stage="match_bundle",
        required=False,
    ),
    "lineups": EndpointSpec(
        name="lineups",
        path="/football/matches/{match_id}/lineups",
        fetch_stage="match_bundle",
    ),
    "match_stats": EndpointSpec(
        name="match_stats",
        path="/football/matches/{match_id}/stats",
        fetch_stage="match_bundle",
    ),
    "player_stats": EndpointSpec(
        name="player_stats",
        path="/football/matches/{match_id}/player-stats",
        fetch_stage="match_bundle",
    ),
    "events": EndpointSpec(
        name="events",
        path="/football/matches/{match_id}/events",
        fetch_stage="match_bundle",
        fallback_paths=("/football/matches/{match_id}/timeline",),
    ),
    "shotmap": EndpointSpec(
        name="shotmap",
        path="/football/matches/{match_id}/shotmap",
        fetch_stage="match_bundle",
    ),
    "match_referee": EndpointSpec(
        name="match_referee",
        path="/football/matches/{match_id}/referee",
        fetch_stage="match_bundle",
        required=False,
    ),
}

CORE_ENDPOINTS = ("fixtures", "standings")

MATCH_BUNDLE_ENDPOINTS = (
    "match_detail",
    "lineups",
    "match_stats",
    "player_stats",
    "events",
    "shotmap",
    "match_referee",
)


def api_key_from_env() -> str:
    key = os.getenv("THESTATSAPI_API_KEY") or os.getenv("THESTATSAPI_KEY")
    if not key:
        raise RuntimeError(
            "THESTATSAPI_API_KEY is required. Add it to .env or export it."
        )
    return key


def base_url_from_env() -> str:
    return os.getenv("THESTATSAPI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def database_url_from_env() -> str:
    explicit = os.getenv("THESTATSAPI_DATABASE_URL") or os.getenv(
        "INGESTION_DATABASE_URL"
    )
    if explicit:
        return explicit

    postgres_db = os.getenv("POSTGRES_DB")
    postgres_user = os.getenv("POSTGRES_USER")
    postgres_password = os.getenv("POSTGRES_PASSWORD")
    if postgres_db and postgres_user and postgres_password:
        host = os.getenv("POSTGRES_HOST", "postgres")
        port = (
            os.getenv("POSTGRES_INTERNAL_PORT", "5432")
            if host == "postgres"
            else os.getenv("POSTGRES_PORT", "5432")
        )
        return (
            f"postgresql://{postgres_user}:{postgres_password}"
            f"@{host}:{port}/{postgres_db}"
        )

    return "sqlite:///data/ingestion/world_cup_ingestion.db"
