from __future__ import annotations

from typing import Any

from .gold_payloads import writer_database_url_from_env


class RateLimiter:
    """Postgres-backed daily counters (analytics.api_rate_limits) — chosen over an
    in-memory/per-process counter because that would be wrong under multiple uvicorn
    workers and would silently reset on every restart/redeploy. Volume here is low
    (at most a few thousand requests/key/day), so the extra round-trip is cheap."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or writer_database_url_from_env()
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
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                1, 3, self.database_url, connect_timeout=2,
            )
        except Exception:
            self._unavailable = True
            return None
        return self._pool

    def increment_and_check(self, key_or_ip: str, *, limit: int) -> bool:
        """Increments today's counter for key_or_ip and returns whether the request
        is still within `limit`. Fails OPEN (returns True) if the rate-limit store is
        unreachable — a transient DB hiccup must not take down the whole public API."""
        pool = self._connection_pool()
        if pool is None:
            return True
        conn = None
        try:
            conn = pool.getconn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO analytics.api_rate_limits (key_or_ip, day, request_count)
                    VALUES (%s, CURRENT_DATE, 1)
                    ON CONFLICT (key_or_ip, day)
                    DO UPDATE SET request_count = analytics.api_rate_limits.request_count + 1
                    RETURNING request_count
                    """,
                    (key_or_ip,),
                )
                row = cur.fetchone()
            conn.commit()
        except Exception:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return True
        finally:
            if conn is not None:
                pool.putconn(conn)
        count = row[0] if row else 1
        return count <= limit
