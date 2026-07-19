from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from webapp.v1 import create_v1_app


class FakeService:
    """Duck-typed stand-in for DataService — create_v1_app() only calls a handful of
    named methods, so a fake matching those names is enough to test route wiring,
    rate-limit enforcement, and OpenAPI isolation without any real data/DB."""

    def years(self) -> list[int]:
        return [2026]

    def catalog(self) -> dict[str, Any]:
        return {"editions": [{"year": 2026}]}

    def overview(self, year: int) -> dict[str, Any]:
        return {"year": year, "available": True}

    def competition(self, year: int) -> dict[str, Any]:
        return {"year": year}

    def teams(self, year: int) -> dict[str, Any]:
        return {"year": year}

    def players(self, year: int) -> dict[str, Any]:
        return {"year": year}

    def profiles(self, year: int) -> dict[str, Any]:
        return {"year": year}

    def matches(self, year: int) -> dict[str, Any]:
        return {"year": year}

    def shots(self, year: int) -> dict[str, Any]:
        return {"year": year}

    def history(self) -> dict[str, Any]:
        return {"available": True}

    def team_detail(self, year: int, team_id: str) -> dict[str, Any]:
        return {"year": year, "team_id": team_id}

    def player_detail(self, year: int, player_id: str) -> dict[str, Any]:
        return {"year": year, "player_id": player_id}

    def match_detail(self, year: int, match_id: str) -> dict[str, Any]:
        return {"year": year, "match_id": match_id}


class FakeApiKeyRecord:
    def __init__(self, id: int = 1) -> None:
        self.id = id


class FakeApiKeys:
    def __init__(self, *, valid_key: str | None = None, create_result: str | None = "wca_live_fake") -> None:
        self.valid_key = valid_key
        self.create_result = create_result
        self.touched: list[int] = []

    def authenticate(self, key: str):
        return FakeApiKeyRecord() if key and key == self.valid_key else None

    def touch(self, record_id: int) -> None:
        self.touched.append(record_id)

    def create(self, owner_identifier: str, *, tier: str = "default"):
        return self.create_result


class FakeRateLimiter:
    def __init__(self, *, allow: bool = True) -> None:
        self.allow = allow
        self.calls: list[tuple[str, int]] = []

    def increment_and_check(self, key_or_ip: str, *, limit: int) -> bool:
        self.calls.append((key_or_ip, limit))
        return self.allow


def _client(*, allow: bool = True, valid_key: str | None = None) -> TestClient:
    app = create_v1_app(
        FakeService(),
        api_keys=FakeApiKeys(valid_key=valid_key),
        rate_limiter=FakeRateLimiter(allow=allow),
    )
    return TestClient(app)


def test_v1_routes_wrap_the_same_service_methods_as_the_legacy_api() -> None:
    client = _client()
    assert client.get("/editions").json() == {"editions": [{"year": 2026}]}
    assert client.get("/editions/2026/overview").json() == {"year": 2026, "available": True}
    assert client.get("/editions/2026/teams/tm_1").json() == {"year": 2026, "team_id": "tm_1"}
    assert client.get("/history").json() == {"available": True}


def test_v1_unknown_year_returns_404_with_available_years() -> None:
    client = _client()
    response = client.get("/editions/1999/overview")
    assert response.status_code == 404
    assert response.json()["detail"]["available_years"] == [2026]


def test_v1_entity_id_is_format_validated() -> None:
    """Entity ids end up in filesystem paths on the bronze fallback
    (data/bronze/.../match_id=<id>) — anything outside [A-Za-z0-9_-] must 404
    before reaching the service layer, same rule as webapp/main.py's require_safe_id."""
    client = _client()
    response = client.get("/editions/2026/players/pl_1!malformed")
    assert response.status_code == 404


def test_v1_rate_limit_returns_429_when_exceeded() -> None:
    client = _client(allow=False)
    response = client.get("/editions/2026/overview")
    assert response.status_code == 429


def test_v1_key_creation_endpoint_returns_plaintext_key_once() -> None:
    client = _client()
    response = client.post("/keys", json={"owner_identifier": "dev@example.com"})
    assert response.status_code == 200
    body = response.json()
    assert body["key"] == "wca_live_fake"
    assert "notice" in body


def test_v1_key_creation_requires_owner_identifier() -> None:
    client = _client()
    response = client.post("/keys", json={"owner_identifier": "   "})
    assert response.status_code == 422


def test_v1_openapi_schema_only_exposes_v1_routes() -> None:
    client = _client()
    schema = client.get("/openapi.json").json()
    paths = set(schema["paths"].keys())
    assert "/editions" in paths
    assert "/keys" in paths
    assert not any(path.startswith("/api/") for path in paths)
    assert "/ops/metrics" not in paths


def test_v1_mounted_under_main_app_stays_isolated_from_legacy_api() -> None:
    from webapp.main import create_app

    app = create_app()
    client = TestClient(app)

    assert client.get("/v1/editions").status_code == 200
    # /api/* (the SPA's own contract) must be completely untouched by this work.
    assert client.get("/api/health").status_code == 200
