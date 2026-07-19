from __future__ import annotations

from webapp.api_keys import (
    KEY_PREFIX,
    ApiKeyRepository,
    generate_key,
    hash_key,
    is_well_formed,
)


def test_generate_key_is_well_formed_and_unique() -> None:
    first, second = generate_key(), generate_key()
    assert first != second
    assert first.startswith(KEY_PREFIX)
    assert is_well_formed(first)
    assert is_well_formed(second)


def test_is_well_formed_rejects_tampered_or_malformed_keys() -> None:
    key = generate_key()
    tampered = key[:-1] + ("0" if key[-1] != "0" else "1")

    assert not is_well_formed(tampered)  # checksum no longer matches the random part
    assert not is_well_formed("not_a_key_at_all")
    assert not is_well_formed(KEY_PREFIX + "tooshort")
    assert not is_well_formed("")


def test_hash_key_is_deterministic_and_never_reversible_by_inspection() -> None:
    key = generate_key()
    assert hash_key(key) == hash_key(key)
    assert hash_key(key) != key
    assert len(hash_key(key)) == 64  # sha256 hex digest


def test_api_key_repository_degrades_gracefully_without_a_database(monkeypatch) -> None:
    """Regression-shaped guard: matches the established pattern in GoldPayloadRepository/
    RequestMetricsRepository — an unreachable/unconfigured Postgres must never raise,
    only return None (create) or None (authenticate), so a public request never 500s
    just because the key store is down."""
    monkeypatch.delenv("PUBLIC_WRITER_DATABASE_URL", raising=False)
    monkeypatch.delenv("THESTATSAPI_DATABASE_URL", raising=False)
    monkeypatch.delenv("SERVING_DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_DB", raising=False)
    repo = ApiKeyRepository(database_url=None)

    assert repo.create("someone@example.com") is None
    assert repo.authenticate(generate_key()) is None
    repo.touch(1)  # must not raise
