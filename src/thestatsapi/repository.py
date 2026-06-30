from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

from .config import (
    SOURCE_NAME,
    WORLD_CUP_2026_COMPETITION_ID,
    WORLD_CUP_2026_SEASON_ID,
    database_url_from_env,
)


SQLITE_DDL = (
    """
    CREATE TABLE IF NOT EXISTS ingestion_match_control (
        source_match_id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        edition_year INTEGER NOT NULL,
        competition_id TEXT NOT NULL,
        season_id TEXT NOT NULL,
        match_number TEXT,
        group_label TEXT,
        stage_name TEXT,
        status TEXT,
        fetch_status TEXT NOT NULL DEFAULT 'scheduled',
        kickoff_utc TEXT,
        venue_name TEXT,
        home_team_id TEXT,
        home_team_name TEXT,
        away_team_id TEXT,
        away_team_name TEXT,
        first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
        raw_path TEXT,
        metadata_path TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingestion_source_fetch_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        endpoint_name TEXT NOT NULL,
        fetch_stage TEXT NOT NULL,
        match_id TEXT NOT NULL DEFAULT '',
        request_fingerprint TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL,
        request_url TEXT,
        http_status INTEGER,
        response_hash TEXT,
        raw_path TEXT,
        metadata_path TEXT,
        attempts INTEGER NOT NULL DEFAULT 1,
        last_error TEXT,
        started_at TEXT DEFAULT CURRENT_TIMESTAMP,
        finished_at TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (source, endpoint_name, fetch_stage, match_id, request_fingerprint)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingestion_api_usage_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        endpoint_name TEXT NOT NULL,
        fetch_stage TEXT NOT NULL,
        match_id TEXT NOT NULL DEFAULT '',
        request_url TEXT,
        http_status INTEGER,
        response_hash TEXT,
        fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL
    )
    """,
)


POSTGRES_DDL = (
    "CREATE SCHEMA IF NOT EXISTS ingestion",
    """
    CREATE TABLE IF NOT EXISTS ingestion.match_control (
        source_match_id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        edition_year INTEGER NOT NULL,
        competition_id TEXT NOT NULL,
        season_id TEXT NOT NULL,
        match_number TEXT,
        group_label TEXT,
        stage_name TEXT,
        status TEXT,
        fetch_status TEXT NOT NULL DEFAULT 'scheduled',
        kickoff_utc TIMESTAMPTZ,
        venue_name TEXT,
        home_team_id TEXT,
        home_team_name TEXT,
        away_team_id TEXT,
        away_team_name TEXT,
        first_seen_at TIMESTAMPTZ DEFAULT now(),
        last_seen_at TIMESTAMPTZ DEFAULT now(),
        raw_path TEXT,
        metadata_path TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingestion.source_fetch_jobs (
        id BIGSERIAL PRIMARY KEY,
        source TEXT NOT NULL,
        endpoint_name TEXT NOT NULL,
        fetch_stage TEXT NOT NULL,
        match_id TEXT NOT NULL DEFAULT '',
        request_fingerprint TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL,
        request_url TEXT,
        http_status INTEGER,
        response_hash TEXT,
        raw_path TEXT,
        metadata_path TEXT,
        attempts INTEGER NOT NULL DEFAULT 1,
        last_error TEXT,
        started_at TIMESTAMPTZ DEFAULT now(),
        finished_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ DEFAULT now(),
        UNIQUE (source, endpoint_name, fetch_stage, match_id, request_fingerprint)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingestion.api_usage_log (
        id BIGSERIAL PRIMARY KEY,
        source TEXT NOT NULL,
        endpoint_name TEXT NOT NULL,
        fetch_stage TEXT NOT NULL,
        match_id TEXT NOT NULL DEFAULT '',
        request_url TEXT,
        http_status INTEGER,
        response_hash TEXT,
        fetched_at TIMESTAMPTZ DEFAULT now(),
        status TEXT NOT NULL
    )
    """,
)


class IngestionRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or database_url_from_env()
        self.backend = "postgres" if self.database_url.startswith("postgres") else "sqlite"
        self._ensure_schema()

    @contextmanager
    def connect(self) -> Iterator[Any]:
        if self.backend == "postgres":
            import psycopg2
            import psycopg2.extras

            conn = psycopg2.connect(
                self.database_url,
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()
            return

        path = self._sqlite_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self.connect() as conn:
            cur = conn.cursor()
            for statement in POSTGRES_DDL if self.backend == "postgres" else SQLITE_DDL:
                cur.execute(statement)

    def get_job(
        self,
        *,
        endpoint_name: str,
        fetch_stage: str,
        match_id: str | None = None,
        request_fingerprint: str = "",
    ) -> dict[str, Any] | None:
        sql = (
            f"SELECT * FROM {self._jobs_table} WHERE source = {self._ph} "
            f"AND endpoint_name = {self._ph} AND fetch_stage = {self._ph} "
            f"AND match_id = {self._ph} AND request_fingerprint = {self._ph}"
        )
        values = (
            SOURCE_NAME,
            endpoint_name,
            fetch_stage,
            self._match_id(match_id),
            self._fingerprint(match_id, request_fingerprint),
        )
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute(sql, values)
            row = cur.fetchone()
        return self._row_to_dict(row) if row else None

    def record_job(
        self,
        *,
        endpoint_name: str,
        fetch_stage: str,
        status: str,
        match_id: str | None = None,
        request_fingerprint: str = "",
        request_url: str | None = None,
        http_status: int | None = None,
        response_hash: str | None = None,
        raw_path: str | None = None,
        metadata_path: str | None = None,
        attempts: int = 1,
        last_error: str | None = None,
    ) -> None:
        table = self._jobs_table
        now_expr = "CURRENT_TIMESTAMP" if self.backend == "sqlite" else "now()"
        sql = f"""
            INSERT INTO {table} (
                source, endpoint_name, fetch_stage, match_id, request_fingerprint,
                status, request_url, http_status, response_hash, raw_path,
                metadata_path, attempts, last_error, finished_at, updated_at
            )
            VALUES (
                {self._ph}, {self._ph}, {self._ph}, {self._ph}, {self._ph},
                {self._ph}, {self._ph}, {self._ph}, {self._ph}, {self._ph},
                {self._ph}, {self._ph}, {self._ph}, {now_expr}, {now_expr}
            )
            ON CONFLICT (
                source, endpoint_name, fetch_stage, match_id, request_fingerprint
            )
            DO UPDATE SET
                status = excluded.status,
                request_url = excluded.request_url,
                http_status = excluded.http_status,
                response_hash = excluded.response_hash,
                raw_path = excluded.raw_path,
                metadata_path = excluded.metadata_path,
                attempts = excluded.attempts,
                last_error = excluded.last_error,
                finished_at = {now_expr},
                updated_at = {now_expr}
        """
        values = (
            SOURCE_NAME,
            endpoint_name,
            fetch_stage,
            self._match_id(match_id),
            self._fingerprint(match_id, request_fingerprint),
            status,
            request_url,
            http_status,
            response_hash,
            raw_path,
            metadata_path,
            attempts,
            last_error,
        )
        with self.connect() as conn:
            conn.cursor().execute(sql, values)

    def log_api_usage(
        self,
        *,
        endpoint_name: str,
        fetch_stage: str,
        status: str,
        match_id: str | None = None,
        request_url: str | None = None,
        http_status: int | None = None,
        response_hash: str | None = None,
    ) -> None:
        table = self._usage_table
        sql = f"""
            INSERT INTO {table} (
                source, endpoint_name, fetch_stage, match_id, request_url,
                http_status, response_hash, status
            )
            VALUES (
                {self._ph}, {self._ph}, {self._ph}, {self._ph},
                {self._ph}, {self._ph}, {self._ph}, {self._ph}
            )
        """
        values = (
            SOURCE_NAME,
            endpoint_name,
            fetch_stage,
            self._match_id(match_id),
            request_url,
            http_status,
            response_hash,
            status,
        )
        with self.connect() as conn:
            conn.cursor().execute(sql, values)

    def upsert_match_control(
        self,
        match: dict[str, Any],
        *,
        raw_path: str | None = None,
        metadata_path: str | None = None,
    ) -> None:
        row = self._match_row(match, raw_path=raw_path, metadata_path=metadata_path)
        table = self._match_table
        now_expr = "CURRENT_TIMESTAMP" if self.backend == "sqlite" else "now()"
        columns = list(row)
        placeholders = ", ".join([self._ph] * len(columns))
        updates = ", ".join(
            f"{column} = excluded.{column}"
            for column in columns
            if column not in {"source_match_id", "first_seen_at"}
        )
        sql = f"""
            INSERT INTO {table} ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT (source_match_id)
            DO UPDATE SET {updates}, last_seen_at = {now_expr}
        """
        with self.connect() as conn:
            conn.cursor().execute(sql, tuple(row.values()))

    def match_control_rows(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM {self._match_table} ORDER BY source_match_id")
            rows = cur.fetchall()
        return [self._row_to_dict(row) for row in rows]

    @property
    def _ph(self) -> str:
        return "%s" if self.backend == "postgres" else "?"

    @property
    def _match_table(self) -> str:
        return "ingestion.match_control" if self.backend == "postgres" else "ingestion_match_control"

    @property
    def _jobs_table(self) -> str:
        return "ingestion.source_fetch_jobs" if self.backend == "postgres" else "ingestion_source_fetch_jobs"

    @property
    def _usage_table(self) -> str:
        return "ingestion.api_usage_log" if self.backend == "postgres" else "ingestion_api_usage_log"

    def _sqlite_path(self) -> Path:
        parsed = urlparse(self.database_url)
        if parsed.scheme != "sqlite":
            raise ValueError(f"Unsupported database URL: {self.database_url}")
        if parsed.path in ("", "/:memory:"):
            return Path(":memory:")
        if parsed.path.startswith("//"):
            return Path(parsed.path[1:])
        if self.database_url.startswith("sqlite:///"):
            return Path(parsed.path.lstrip("/"))
        return Path(parsed.path)

    @staticmethod
    def _match_id(match_id: str | None) -> str:
        return str(match_id or "")

    @staticmethod
    def _fingerprint(match_id: str | None, request_fingerprint: str) -> str:
        if request_fingerprint:
            return request_fingerprint
        if match_id:
            return f"match_id={match_id}"
        return ""

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        if isinstance(row, sqlite3.Row):
            return dict(row)
        if isinstance(row, dict):
            return row
        columns = [item[0] for item in row.cursor_description]
        return dict(zip(columns, row))

    @staticmethod
    def _match_row(
        match: dict[str, Any],
        *,
        raw_path: str | None,
        metadata_path: str | None,
    ) -> dict[str, Any]:
        home = _object(match.get("home") or match.get("home_team"))
        away = _object(match.get("away") or match.get("away_team"))
        source_match_id = (
            match.get("match_id")
            or match.get("id")
            or match.get("fixture_id")
            or match.get("source_match_id")
        )
        if not source_match_id:
            raise ValueError(f"Fixture row does not include a match id: {match}")
        return {
            "source_match_id": str(source_match_id),
            "source": SOURCE_NAME,
            "edition_year": 2026,
            "competition_id": str(
                match.get("competition_id") or WORLD_CUP_2026_COMPETITION_ID
            ),
            "season_id": str(match.get("season_id") or WORLD_CUP_2026_SEASON_ID),
            "match_number": _string(
                match.get("match_number") or match.get("matchday") or match.get("number")
            ),
            "group_label": _string(match.get("group_label") or match.get("group")),
            "stage_name": _string(
                match.get("stage_name") or match.get("stage") or match.get("round")
            ),
            "status": _string(match.get("status")),
            "fetch_status": _string(match.get("status")) or "scheduled",
            "kickoff_utc": _string(
                match.get("kickoff_utc")
                or match.get("utc_date")
                or match.get("kickoff")
                or match.get("date")
            ),
            "venue_name": _string(match.get("venue")),
            "home_team_id": _string(home.get("team_id") or home.get("id")),
            "home_team_name": _string(home.get("name") or match.get("home_team")),
            "away_team_id": _string(away.get("team_id") or away.get("id")),
            "away_team_name": _string(away.get("name") or match.get("away_team")),
            "raw_path": raw_path,
            "metadata_path": metadata_path,
        }


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
