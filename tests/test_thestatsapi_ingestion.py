from __future__ import annotations

import json
from pathlib import Path

import httpx

from thestatsapi.client import ApiResponse, TransientApiError
from thestatsapi.client import TheStatsApiClient
from thestatsapi.config import ENDPOINTS
from thestatsapi.ingestion import TheStatsApiIngestion
from thestatsapi.opening_match_smoke import find_match_by_teams, match_id
from thestatsapi.repository import IngestionRepository
from thestatsapi.storage import BronzeStore


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int | None, dict[str, object]]] = []
        self.failures: dict[str, ApiResponse | Exception] = {}

    def fetch_endpoint(
        self,
        endpoint_name: str,
        *,
        match_id: str | None = None,
        params: dict[str, object] | None = None,
    ) -> ApiResponse:
        self.calls.append((endpoint_name, match_id, params or {}))
        failure = self.failures.get(endpoint_name)
        if isinstance(failure, Exception):
            raise failure
        if failure is not None:
            return failure
        data = {"endpoint": endpoint_name, "match_id": match_id}
        if endpoint_name == "match_referee":
            data["referee"] = {"id": "ref_1", "name": "Test Referee"}
        return ApiResponse(
            endpoint_name=endpoint_name,
            request_url=f"https://example.test/{endpoint_name}",
            http_status=200,
            payload={"data": data},
        )

    def fetch_paginated(
        self,
        endpoint_name: str,
        *,
        base_params: dict[str, object] | None = None,
    ) -> list[ApiResponse]:
        self.calls.append((endpoint_name, None, base_params or {}))
        return [
            ApiResponse(
                endpoint_name=endpoint_name,
                request_url="https://example.test/fixtures?page=1",
                http_status=200,
                payload={
                    "data": [
                        {
                            "match_id": "mt_1",
                            "status": "scheduled",
                            "kickoff_utc": "2026-06-11T19:00:00Z",
                            "home": {"team_id": "tm_a", "name": "Team A"},
                            "away": {"team_id": "tm_b", "name": "Team B"},
                        }
                    ],
                    "meta": {"page": 1, "total_pages": 1},
                },
            )
        ]


def _ingestion(tmp_path: Path) -> tuple[TheStatsApiIngestion, FakeClient]:
    client = FakeClient()
    repo = IngestionRepository(f"sqlite:///{tmp_path / 'ingestion.db'}")
    store = BronzeStore(tmp_path / "bronze")
    return TheStatsApiIngestion(client=client, repository=repo, store=store), client


def test_fixtures_are_saved_to_bronze_and_upsert_match_control(
    tmp_path: Path,
) -> None:
    ingestion, client = _ingestion(tmp_path)

    result = ingestion.fetch_fixtures()

    assert result["fixtures"] == 1
    assert len(client.calls) == 1
    raw_path = (
        tmp_path
        / "bronze/thestatsapi/world_cup/2026/fixtures/page=1/response.json"
    )
    metadata_path = raw_path.with_name("metadata.json")
    assert raw_path.exists()
    assert metadata_path.exists()
    assert json.loads(metadata_path.read_text())["response_hash"]

    rows = ingestion.repository.match_control_rows()
    assert rows[0]["source_match_id"] == "mt_1"
    assert rows[0]["home_team_name"] == "Team A"
    assert rows[0]["fetch_status"] == "scheduled"


def test_fixtures_skip_existing_success_job_without_force(tmp_path: Path) -> None:
    ingestion, client = _ingestion(tmp_path)

    ingestion.fetch_fixtures()
    second = ingestion.fetch_fixtures()

    assert second["skipped"] == 1
    assert len(client.calls) == 1


def test_registry_uses_documented_match_referee_detail_and_standings_paths() -> None:
    referee = ENDPOINTS["match_referee"]
    detail = ENDPOINTS["match_detail"]
    standings = ENDPOINTS["standings"]

    assert referee.resolve_paths(match_id="mt_1") == (
        "/football/matches/mt_1/referee",
    )
    assert referee.required is False
    assert detail.resolve_paths(match_id="mt_1") == (
        "/football/matches/mt_1",
    )
    assert detail.required is False
    assert standings.resolve_paths() == (
        "/football/competitions/comp_6107/seasons/sn_118868/standings",
    )
    assert standings.required is True


def test_standings_are_saved_with_core_metadata_and_are_idempotent(
    tmp_path: Path,
) -> None:
    ingestion, client = _ingestion(tmp_path)

    first = ingestion.fetch_standings()
    second = ingestion.fetch_standings()

    assert first == {"success": 1, "standings": 1}
    assert second == {"skipped": 1, "standings": 0}
    assert [call[0] for call in client.calls] == ["standings"]
    raw_path = (
        tmp_path
        / "bronze/thestatsapi/world_cup/2026/standings/response.json"
    )
    assert raw_path.exists()
    metadata = json.loads(raw_path.with_name("metadata.json").read_text())
    assert metadata["endpoint_name"] == "standings"
    assert metadata["fetch_stage"] == "core"


def test_match_bundle_saves_each_endpoint_and_continues_on_404(
    tmp_path: Path,
) -> None:
    ingestion, client = _ingestion(tmp_path)
    client.failures["events"] = ApiResponse(
        endpoint_name="events",
        request_url="https://example.test/events",
        http_status=404,
        payload={"message": "not found"},
    )

    result = ingestion.fetch_match_bundle("mt_1")

    assert result["success"] == 6
    assert result["unavailable"] == 1
    assert {call[0] for call in client.calls} == {
        "lineups",
        "match_stats",
        "player_stats",
        "events",
        "shotmap",
        "match_referee",
        "match_detail",
    }
    base = tmp_path / "bronze/thestatsapi/world_cup/2026/matches/match_id=mt_1"
    assert (base / "lineups/response.json").exists()
    assert json.loads((base / "events/metadata.json").read_text())[
        "fetch_status"
    ] == "unavailable"


def test_match_bundle_skips_successful_endpoint_without_force(
    tmp_path: Path,
) -> None:
    ingestion, client = _ingestion(tmp_path)

    ingestion.fetch_match_bundle("mt_1")
    result = ingestion.fetch_match_bundle("mt_1")

    assert result["skipped"] == 7
    assert len(client.calls) == 7


def test_match_referee_is_optional_and_saved_separately(tmp_path: Path) -> None:
    ingestion, client = _ingestion(tmp_path)
    client.failures["match_referee"] = ApiResponse(
        endpoint_name="match_referee",
        request_url="https://example.test/football/matches/mt_1/referee",
        http_status=404,
        payload={"data": None},
    )

    result = ingestion.fetch_match_bundle("mt_1")

    assert result == {"success": 6, "unavailable": 1}
    raw_path = (
        tmp_path
        / "bronze/thestatsapi/world_cup/2026/matches/match_id=mt_1/"
        "match_referee/response.json"
    )
    assert raw_path.exists()
    metadata = json.loads(raw_path.with_name("metadata.json").read_text())
    assert metadata["endpoint_name"] == "match_referee"
    assert metadata["fetch_status"] == "unavailable"
    assert ENDPOINTS["match_referee"].required is False


def test_match_referee_null_payload_is_unavailable_without_failing_bundle(
    tmp_path: Path,
) -> None:
    ingestion, client = _ingestion(tmp_path)
    client.failures["match_referee"] = ApiResponse(
        endpoint_name="match_referee",
        request_url="https://example.test/football/matches/mt_1/referee",
        http_status=200,
        payload={"data": {"match_id": "mt_1", "referee": None}},
    )

    result = ingestion.fetch_match_bundle("mt_1")

    assert result == {"success": 6, "unavailable": 1}


def test_match_detail_is_optional_and_does_not_block_other_endpoints(
    tmp_path: Path,
) -> None:
    ingestion, client = _ingestion(tmp_path)
    client.failures["match_detail"] = ApiResponse(
        endpoint_name="match_detail",
        request_url="https://example.test/football/matches/mt_1",
        http_status=404,
        payload={"data": None},
    )

    result = ingestion.fetch_match_bundle("mt_1")

    assert result == {"unavailable": 1, "success": 6}
    raw_path = (
        tmp_path
        / "bronze/thestatsapi/world_cup/2026/matches/match_id=mt_1/"
        "match_detail/response.json"
    )
    assert raw_path.exists()
    metadata = json.loads(raw_path.with_name("metadata.json").read_text())
    assert metadata["fetch_status"] == "unavailable"


def test_match_bundle_records_failed_endpoint_after_retries_exhausted(
    tmp_path: Path,
) -> None:
    ingestion, client = _ingestion(tmp_path)
    client.failures["match_stats"] = TransientApiError(
        endpoint_name="match_stats",
        request_url="https://example.test/stats",
        http_status=500,
        message="server error",
    )

    result = ingestion.fetch_match_bundle("mt_1")

    assert result["failed"] == 1
    job = ingestion.repository.get_job(
        endpoint_name="match_stats",
        fetch_stage="match_bundle",
        match_id="mt_1",
    )
    assert job is not None
    assert job["status"] == "failed"


def test_opening_match_smoke_finds_mexico_south_africa_fixture() -> None:
    rows = [
        {
            "id": "mt_other",
            "home_team": {"name": "Canada"},
            "away_team": {"name": "Mexico"},
            "utc_date": "2026-06-12T00:00:00Z",
        },
        {
            "id": "mt_opening",
            "home_team": {"name": "Mexico"},
            "away_team": {"name": "South Africa"},
            "utc_date": "2026-06-11T19:00:00Z",
        },
    ]

    selected = find_match_by_teams(
        rows,
        home_team="México",
        away_team="Africa do Sul",
    )

    assert selected is not None
    assert match_id(selected) == "mt_opening"


def test_events_endpoint_falls_back_to_timeline_after_404() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path.endswith("/events"):
            return httpx.Response(404, json={"error": "not found"})
        if request.url.path.endswith("/timeline"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "match_id": "mt_opening",
                        "events": [{"minute": 9, "type": "goal"}],
                    }
                },
            )
        return httpx.Response(500, json={"error": "unexpected"})

    client = TheStatsApiClient(
        api_key="test",
        base_url="https://api.example.test/api",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    response = client.fetch_endpoint("events", match_id="mt_opening")

    assert response.http_status == 200
    assert response.request_url.endswith("/timeline")
    assert response.payload["data"]["events"][0]["type"] == "goal"
    assert [url.rsplit("/", 1)[-1] for url in calls] == ["events", "timeline"]
