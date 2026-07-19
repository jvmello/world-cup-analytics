from __future__ import annotations

from webapp.rate_limit import RateLimiter


def test_rate_limiter_fails_open_without_a_database(monkeypatch) -> None:
    """A transient/unconfigured rate-limit store must never take down the public API —
    increment_and_check() fails open (allows the request) rather than raising or
    silently blocking everyone."""
    monkeypatch.delenv("PUBLIC_WRITER_DATABASE_URL", raising=False)
    monkeypatch.delenv("THESTATSAPI_DATABASE_URL", raising=False)
    monkeypatch.delenv("SERVING_DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_DB", raising=False)
    limiter = RateLimiter(database_url=None)

    assert limiter.increment_and_check("ip:203.0.113.5", limit=1) is True
