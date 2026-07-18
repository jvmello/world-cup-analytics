from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .client import ApiResponse
from .config import SOURCE_NAME, WORLD_CUP_2026_EDITION


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def response_hash(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BronzeWrite:
    raw_path: Path
    metadata_path: Path
    response_hash: str


class BronzeStore:
    def __init__(
        self,
        root: Path | str = Path("data/bronze"),
        *,
        edition_year: int = WORLD_CUP_2026_EDITION,
    ) -> None:
        self.root = Path(root)
        self.edition_year = edition_year

    def fixtures_page_path(self, page: int) -> Path:
        return (
            self.root
            / SOURCE_NAME
            / "world_cup"
            / str(self.edition_year)
            / "fixtures"
            / f"page={page}"
            / "response.json"
        )

    def standings_path(self) -> Path:
        return (
            self.root
            / SOURCE_NAME
            / "world_cup"
            / str(self.edition_year)
            / "standings"
            / "response.json"
        )

    def match_endpoint_path(self, match_id: str, endpoint_name: str) -> Path:
        return (
            self.root
            / SOURCE_NAME
            / "world_cup"
            / str(self.edition_year)
            / "matches"
            / f"match_id={self._safe_part(match_id)}"
            / endpoint_name
            / "response.json"
        )

    def matches_root(self) -> Path:
        return self.root / SOURCE_NAME / "world_cup" / str(self.edition_year) / "matches"

    def club_team_path(self, team_id: str) -> Path:
        return (
            self.root
            / SOURCE_NAME
            / "world_cup"
            / str(self.edition_year)
            / "club_teams"
            / f"team_id={self._safe_part(team_id)}"
            / "response.json"
        )

    def exists(self, raw_path: Path) -> bool:
        metadata_path = raw_path.with_name("metadata.json")
        return raw_path.exists() and metadata_path.exists()

    def metadata(self, raw_path: Path) -> dict[str, Any]:
        metadata_path = raw_path.with_name("metadata.json")
        if not metadata_path.exists():
            return {}
        try:
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def write(
        self,
        *,
        raw_path: Path,
        response: ApiResponse,
        fetch_stage: str,
        fetch_status: str,
        fetched_at: str | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> BronzeWrite:
        fetched_at = fetched_at or utc_now_iso()
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        payload = response.payload
        raw_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        digest = response_hash(payload)
        metadata = {
            "source": SOURCE_NAME,
            "edition_year": self.edition_year,
            "endpoint_name": response.endpoint_name,
            "fetch_stage": fetch_stage,
            "fetch_status": fetch_status,
            "request_url": response.request_url,
            "fetched_at": fetched_at,
            "http_status": response.http_status,
            "response_hash": digest,
            **(extra_metadata or {}),
        }
        metadata_path = raw_path.with_name("metadata.json")
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return BronzeWrite(
            raw_path=raw_path,
            metadata_path=metadata_path,
            response_hash=digest,
        )

    @staticmethod
    def _safe_part(value: str) -> str:
        return "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in value)
