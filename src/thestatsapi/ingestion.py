from __future__ import annotations

import json
import time
from collections import Counter
from typing import Any

from .client import ApiResponse, TheStatsApiClient, TransientApiError
from .config import ENDPOINTS, MATCH_BUNDLE_ENDPOINTS, WORLD_CUP_2026_EDITION
from .repository import IngestionRepository
from .storage import BronzeStore


class TheStatsApiIngestion:
    def __init__(
        self,
        *,
        client: Any | None = None,
        repository: IngestionRepository | None = None,
        store: BronzeStore | None = None,
    ) -> None:
        self.client = client or TheStatsApiClient()
        self.repository = repository or IngestionRepository()
        self.store = store or BronzeStore()

    def fetch_fixtures(self, *, force: bool = False) -> dict[str, int]:
        endpoint_name = "fixtures"
        fetch_stage = ENDPOINTS[endpoint_name].fetch_stage
        page_one_path = self.store.fixtures_page_path(1)
        if not force and self._job_success(
            endpoint_name=endpoint_name,
            fetch_stage=fetch_stage,
            request_fingerprint="page=1",
        ) and self.store.exists(page_one_path):
            return {"skipped": 1, "fixtures": 0, "success": 0}

        responses = self.client.fetch_paginated(endpoint_name)
        counters: Counter[str] = Counter()
        for index, response in enumerate(responses, start=1):
            payload = response.payload if isinstance(response.payload, dict) else {}
            meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
            page = int(meta.get("page") or index)
            raw_path = self.store.fixtures_page_path(page)
            status = "unavailable" if self._unavailable(response) else "success"
            written = self.store.write(
                raw_path=raw_path,
                response=response,
                fetch_stage=fetch_stage,
                fetch_status=status,
                extra_metadata={"page": page},
            )
            self.repository.record_job(
                endpoint_name=endpoint_name,
                fetch_stage=fetch_stage,
                status=status,
                request_fingerprint=f"page={page}",
                request_url=response.request_url,
                http_status=response.http_status,
                response_hash=written.response_hash,
                raw_path=str(written.raw_path),
                metadata_path=str(written.metadata_path),
            )
            self.repository.log_api_usage(
                endpoint_name=endpoint_name,
                fetch_stage=fetch_stage,
                status=status,
                request_url=response.request_url,
                http_status=response.http_status,
                response_hash=written.response_hash,
            )
            fixtures = self._records(response.payload)
            for match in fixtures:
                self.repository.upsert_match_control(
                    match,
                    raw_path=str(written.raw_path),
                    metadata_path=str(written.metadata_path),
                )
            counters[status] += 1
            counters["fixtures"] += len(fixtures)
        return dict(counters)

    def fetch_standings(self, *, force: bool = False) -> dict[str, int]:
        endpoint_name = "standings"
        fetch_stage = ENDPOINTS[endpoint_name].fetch_stage
        raw_path = self.store.standings_path()
        request_fingerprint = "world_cup_2026"
        if not force and (
            (
                self._job_success(
                    endpoint_name=endpoint_name,
                    fetch_stage=fetch_stage,
                    request_fingerprint=request_fingerprint,
                )
                and self.store.exists(raw_path)
            )
            or self._raw_blocks_fetch(endpoint_name, raw_path)
        ):
            return {"skipped": 1, "standings": 0}

        try:
            response = self.client.fetch_endpoint(endpoint_name)
            status = "unavailable" if self._unavailable(response) else "success"
            error = None
        except TransientApiError as exc:
            response = ApiResponse(
                endpoint_name=endpoint_name,
                request_url=exc.request_url,
                http_status=exc.http_status or 0,
                payload={"error": str(exc), "http_status": exc.http_status},
            )
            status = "failed"
            error = str(exc)

        written = self.store.write(
            raw_path=raw_path,
            response=response,
            fetch_stage=fetch_stage,
            fetch_status=status,
        )
        self.repository.record_job(
            endpoint_name=endpoint_name,
            fetch_stage=fetch_stage,
            status=status,
            request_fingerprint=request_fingerprint,
            request_url=response.request_url,
            http_status=response.http_status,
            response_hash=written.response_hash,
            raw_path=str(written.raw_path),
            metadata_path=str(written.metadata_path),
            last_error=error,
        )
        self.repository.log_api_usage(
            endpoint_name=endpoint_name,
            fetch_stage=fetch_stage,
            status=status,
            request_url=response.request_url,
            http_status=response.http_status,
            response_hash=written.response_hash,
        )
        data = response.payload.get("data") if isinstance(response.payload, dict) else response.payload
        standings_count = len(data) if isinstance(data, list) else int(bool(data))
        return {status: 1, "standings": standings_count}

    def fetch_core(self, *, force: bool = False) -> dict[str, int]:
        counters: Counter[str] = Counter()
        counters.update(self.fetch_fixtures(force=force))
        counters.update(self.fetch_standings(force=force))
        return dict(counters)

    def fetch_match_bundle(
        self,
        match_id: str,
        *,
        force: bool = False,
        endpoints: tuple[str, ...] = MATCH_BUNDLE_ENDPOINTS,
    ) -> dict[str, int]:
        counters: Counter[str] = Counter()
        for endpoint_name in endpoints:
            fetch_stage = ENDPOINTS[endpoint_name].fetch_stage
            raw_path = self.store.match_endpoint_path(match_id, endpoint_name)
            request_fingerprint = f"match_id={match_id}"
            if (
                not force
                and self._job_success(
                    endpoint_name=endpoint_name,
                    fetch_stage=fetch_stage,
                    match_id=match_id,
                    request_fingerprint=request_fingerprint,
                )
                and self.store.exists(raw_path)
            ):
                counters["skipped"] += 1
                continue
            if not force and self._raw_blocks_fetch(endpoint_name, raw_path):
                counters["skipped"] += 1
                continue

            try:
                response = self.client.fetch_endpoint(
                    endpoint_name,
                    match_id=match_id,
                )
                status = (
                    "unavailable"
                    if self._unavailable(response)
                    or self._endpoint_unavailable(endpoint_name, response)
                    else "success"
                )
                error = None
            except TransientApiError as exc:
                response = ApiResponse(
                    endpoint_name=endpoint_name,
                    request_url=exc.request_url,
                    http_status=exc.http_status or 0,
                    payload={"error": str(exc), "http_status": exc.http_status},
                )
                status = "failed"
                error = str(exc)

            written = self.store.write(
                raw_path=raw_path,
                response=response,
                fetch_stage=fetch_stage,
                fetch_status=status,
                extra_metadata={"match_id": match_id},
            )
            self.repository.record_job(
                endpoint_name=endpoint_name,
                fetch_stage=fetch_stage,
                status=status,
                match_id=match_id,
                request_fingerprint=request_fingerprint,
                request_url=response.request_url,
                http_status=response.http_status,
                response_hash=written.response_hash,
                raw_path=str(written.raw_path),
                metadata_path=str(written.metadata_path),
                last_error=error,
            )
            self.repository.log_api_usage(
                endpoint_name=endpoint_name,
                fetch_stage=fetch_stage,
                status=status,
                match_id=match_id,
                request_url=response.request_url,
                http_status=response.http_status,
                response_hash=written.response_hash,
            )
            counters[status] += 1
        return dict(counters)

    def fetch_club_teams(self, *, force: bool = False, pause_seconds: float = 5.0) -> dict[str, int]:
        """Resolve club names for every club_team_id seen in ingested player-stats.

        The provider tags each player_stats row with the club they were affiliated
        with at fetch time (club_team_id), independent of team_id (the World Cup
        squad). This backfills /football/teams/{team_id} once per distinct club,
        idempotent and cacheable (a club shows up for many players/matches).
        pause_seconds paces actual requests against the account's ~12 req/min limit;
        skipped (already-cached) clubs don't count against it.
        """
        endpoint_name = "club_team_detail"
        fetch_stage = ENDPOINTS[endpoint_name].fetch_stage
        counters: Counter[str] = Counter()
        for index, team_id in enumerate(sorted(self._distinct_club_team_ids())):
            raw_path = self.store.club_team_path(team_id)
            request_fingerprint = f"team_id={team_id}"
            if (
                not force
                and self._job_success(
                    endpoint_name=endpoint_name,
                    fetch_stage=fetch_stage,
                    match_id=team_id,
                    request_fingerprint=request_fingerprint,
                )
                and self.store.exists(raw_path)
            ):
                counters["skipped"] += 1
                continue
            if not force and self._raw_blocks_fetch(endpoint_name, raw_path):
                counters["skipped"] += 1
                continue
            if index and pause_seconds > 0:
                time.sleep(pause_seconds)

            try:
                response = self.client.fetch_endpoint(endpoint_name, team_id=team_id)
                status = "unavailable" if self._unavailable(response) else "success"
                error = None
            except TransientApiError as exc:
                response = ApiResponse(
                    endpoint_name=endpoint_name,
                    request_url=exc.request_url,
                    http_status=exc.http_status or 0,
                    payload={"error": str(exc), "http_status": exc.http_status},
                )
                status = "failed"
                error = str(exc)

            written = self.store.write(
                raw_path=raw_path,
                response=response,
                fetch_stage=fetch_stage,
                fetch_status=status,
                extra_metadata={"team_id": team_id},
            )
            self.repository.record_job(
                endpoint_name=endpoint_name,
                fetch_stage=fetch_stage,
                status=status,
                match_id=team_id,
                request_fingerprint=request_fingerprint,
                request_url=response.request_url,
                http_status=response.http_status,
                response_hash=written.response_hash,
                raw_path=str(written.raw_path),
                metadata_path=str(written.metadata_path),
                last_error=error,
            )
            self.repository.log_api_usage(
                endpoint_name=endpoint_name,
                fetch_stage=fetch_stage,
                status=status,
                match_id=team_id,
                request_url=response.request_url,
                http_status=response.http_status,
                response_hash=written.response_hash,
            )
            counters[status] += 1
        return dict(counters)

    def _distinct_club_team_ids(self) -> set[str]:
        ids: set[str] = set()
        for player_stats_path in self.store.matches_root().glob("match_id=*/player_stats/response.json"):
            try:
                payload = json.loads(player_stats_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            records = payload.get("data") if isinstance(payload, dict) else payload
            if not isinstance(records, list):
                continue
            for record in records:
                if isinstance(record, dict) and record.get("club_team_id"):
                    ids.add(str(record["club_team_id"]))
        return ids

    def _job_success(
        self,
        *,
        endpoint_name: str,
        fetch_stage: str,
        match_id: str | None = None,
        request_fingerprint: str = "",
    ) -> bool:
        job = self.repository.get_job(
            endpoint_name=endpoint_name,
            fetch_stage=fetch_stage,
            match_id=match_id,
            request_fingerprint=request_fingerprint,
        )
        return bool(job and job.get("status") == "success")

    def _raw_blocks_fetch(self, endpoint_name: str, raw_path: Any) -> bool:
        if not self.store.exists(raw_path):
            return False
        metadata = self.store.metadata(raw_path)
        if metadata.get("fetch_status") == "success":
            return True
        spec = ENDPOINTS.get(endpoint_name)
        if spec and spec.fallback_paths:
            request_url = str(metadata.get("request_url") or "")
            if not any(path.strip("/").split("/")[-1] in request_url for path in spec.fallback_paths):
                return False
        return True

    @staticmethod
    def _records(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            return [item for item in payload["data"] if isinstance(item, dict)]
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []

    @staticmethod
    def _unavailable(response: ApiResponse) -> bool:
        if response.http_status in (204, 404):
            return True
        payload = response.payload
        if payload is None:
            return True
        if isinstance(payload, dict) and payload.get("data") in (None, [], {}):
            return True
        if payload == []:
            return True
        return False

    @staticmethod
    def _endpoint_unavailable(endpoint_name: str, response: ApiResponse) -> bool:
        if endpoint_name != "match_referee":
            return False
        data = response.payload.get("data") if isinstance(response.payload, dict) else None
        if not isinstance(data, dict):
            return True
        official_fields = (
            "referee",
            "main_referee",
            "officials",
            "assistant_referees",
            "fourth_official",
            "var",
            "avar",
        )
        return not any(data.get(field) for field in official_fields)


def default_ingestion() -> TheStatsApiIngestion:
    return TheStatsApiIngestion(store=BronzeStore(edition_year=WORLD_CUP_2026_EDITION))
