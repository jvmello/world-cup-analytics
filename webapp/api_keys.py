from __future__ import annotations

import hashlib
import secrets
import string
from dataclasses import dataclass
from typing import Any

from .gold_payloads import writer_database_url_from_env

KEY_PREFIX = "wca_live_"
RANDOM_PART_LENGTH = 24
CHECKSUM_LENGTH = 4
_ALPHABET = string.ascii_letters + string.digits


def _checksum(random_part: str) -> str:
    # Not a security control (the SHA-256 hash below is) — just lets obviously
    # mistyped/truncated keys get rejected before ever touching Postgres.
    return hashlib.sha256(random_part.encode("utf-8")).hexdigest()[:CHECKSUM_LENGTH]


def generate_key() -> str:
    random_part = "".join(secrets.choice(_ALPHABET) for _ in range(RANDOM_PART_LENGTH))
    return f"{KEY_PREFIX}{random_part}{_checksum(random_part)}"


def is_well_formed(key: str) -> bool:
    if not key.startswith(KEY_PREFIX):
        return False
    body = key[len(KEY_PREFIX):]
    if len(body) != RANDOM_PART_LENGTH + CHECKSUM_LENGTH:
        return False
    random_part, checksum = body[:RANDOM_PART_LENGTH], body[RANDOM_PART_LENGTH:]
    return checksum == _checksum(random_part)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ApiKeyRecord:
    id: int
    owner_identifier: str
    tier: str
    created_at: Any
    revoked_at: Any
    last_used_at: Any
    request_count: int


class ApiKeyRepository:
    """Self-service API keys (analytics.api_keys). High-entropy random tokens are
    hashed with plain SHA-256 (not bcrypt/argon2) — that slow-hashing tradeoff exists
    to defend low-entropy human passwords against brute force, which doesn't apply to
    a 32-char random token; every major API-key provider (Stripe, GitHub) does the same."""

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

    def create(self, owner_identifier: str, *, tier: str = "default") -> str | None:
        """Returns the plaintext key (shown once) or None if storage is unavailable."""
        pool = self._connection_pool()
        if pool is None:
            return None
        key = generate_key()
        conn = None
        try:
            conn = pool.getconn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO analytics.api_keys (key_hash, owner_identifier, tier)
                    VALUES (%s, %s, %s)
                    """,
                    (hash_key(key), owner_identifier.strip()[:200], tier),
                )
            conn.commit()
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
        return key

    def authenticate(self, key: str) -> ApiKeyRecord | None:
        if not key or not is_well_formed(key):
            return None
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
                    SELECT id, owner_identifier, tier, created_at, revoked_at,
                           last_used_at, request_count
                    FROM analytics.api_keys
                    WHERE key_hash = %s AND revoked_at IS NULL
                    """,
                    (hash_key(key),),
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
        return ApiKeyRecord(**row) if row else None

    def touch(self, record_id: int) -> None:
        """Fire-and-forget: bump last_used_at/request_count. Never blocks the request
        on failure — auth already succeeded by the time this runs."""
        pool = self._connection_pool()
        if pool is None:
            return
        conn = None
        try:
            conn = pool.getconn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE analytics.api_keys
                    SET last_used_at = now(), request_count = request_count + 1
                    WHERE id = %s
                    """,
                    (record_id,),
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
