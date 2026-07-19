from __future__ import annotations

import os
from typing import Any

from .gold_payloads import writer_database_url_from_env


class RequestMetricsRepository:
    """Fire-and-forget log of API calls into analytics.api_requests. Every method
    swallows its own errors — metrics must never break or slow down a real request."""

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
            maxconn = int(os.getenv("THESTATSAPI_METRICS_POOL_MAX", "3"))
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                1,
                max(1, maxconn),
                self.database_url,
                # A dashboard load or a fire-and-forget write must never hang on an
                # unreachable database — fail fast instead of the OS default (which can
                # be tens of seconds and, for record(), stalls the thread-pool worker).
                connect_timeout=2,
            )
        except Exception:
            self._unavailable = True
            return None
        return self._pool

    def record(
        self,
        method: str,
        path_template: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        pool = self._connection_pool()
        if pool is None:
            return
        conn = None
        try:
            conn = pool.getconn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO analytics.api_requests
                        (method, path_template, status_code, duration_ms)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (method, path_template, status_code, round(duration_ms, 2)),
                )
            conn.commit()
        except Exception:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
        finally:
            if conn is not None:
                pool.putconn(conn)

    def top_endpoints(self, days: int = 7, limit: int = 50) -> list[dict[str, Any]]:
        pool = self._connection_pool()
        if pool is None:
            return []
        try:
            import psycopg2.extras
        except ImportError:
            self._unavailable = True
            return []
        conn = None
        try:
            conn = pool.getconn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        method,
                        path_template,
                        count(*) AS calls,
                        round(avg(duration_ms)::numeric, 1) AS avg_ms,
                        round(
                            percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms)::numeric, 1
                        ) AS p95_ms,
                        round(
                            100.0 * count(*) FILTER (WHERE status_code >= 400) / count(*), 1
                        ) AS error_rate_pct,
                        max(ts) AS last_seen
                    FROM analytics.api_requests
                    WHERE ts >= now() - (%s || ' days')::interval
                    GROUP BY method, path_template
                    ORDER BY calls DESC
                    LIMIT %s
                    """,
                    (days, limit),
                )
                rows = cur.fetchall()
        except Exception:
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return []
        finally:
            if conn is not None:
                pool.putconn(conn)
        return [dict(row) for row in rows]
