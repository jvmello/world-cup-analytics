from __future__ import annotations

import json
import os
from typing import Any


def database_url_from_env() -> str | None:
    explicit = os.getenv("THESTATSAPI_DATABASE_URL") or os.getenv(
        "SERVING_DATABASE_URL"
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
    return None


class GoldPayloadRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or database_url_from_env()
        self._unavailable = not bool(
            self.database_url and self.database_url.startswith("postgres")
        )
        self._pool: Any | None = None

    def _connection_pool(self) -> Any | None:
        if self._unavailable:
            return None
        if self._pool is not None:
            return self._pool
        try:
            import psycopg2.pool
        except ImportError:
            self._unavailable = True
            return None
        try:
            maxconn = int(os.getenv("THESTATSAPI_GOLD_POOL_MAX", "5"))
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                1,
                max(1, maxconn),
                self.database_url,
                # An unreachable database must fail fast so every request falls back to
                # the bronze/file path instead of hanging on the OS default connect timeout.
                connect_timeout=2,
            )
        except Exception:
            self._unavailable = True
            return None
        return self._pool

    def get_payload(
        self,
        year: int,
        endpoint: str,
        *,
        entity_id: str | None = None,
        scope: str | None = None,
    ) -> dict[str, Any] | None:
        payload = self.get_payload_text(
            year,
            endpoint,
            entity_id=entity_id,
            scope=scope,
        )
        if payload is None:
            return None
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def get_payload_text(
        self,
        year: int,
        endpoint: str,
        *,
        entity_id: str | None = None,
        scope: str | None = None,
    ) -> str | None:
        pool = self._connection_pool()
        if pool is None:
            return None
        try:
            import psycopg2.extras
        except ImportError:
            self._unavailable = True
            return None

        conn = None
        try:
            conn = pool.getconn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT payload::text AS payload
                    FROM gold.api_payloads
                    WHERE edition_year = %s
                      AND endpoint = %s
                      AND entity_id = %s
                      AND scope = %s
                    """,
                    (year, endpoint, entity_id or "", scope or ""),
                )
                row = cur.fetchone()
        except Exception:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return None
        finally:
            if conn is not None:
                pool.putconn(conn)
        if not row:
            return None
        payload = row.get("payload")
        return payload if isinstance(payload, str) else None
