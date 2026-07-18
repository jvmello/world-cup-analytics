from __future__ import annotations

import time
from dataclasses import dataclass
from math import ceil
from typing import Any
from urllib.parse import urlencode

import httpx

from .config import ENDPOINTS, api_key_from_env, base_url_from_env


@dataclass(frozen=True)
class ApiResponse:
    endpoint_name: str
    request_url: str
    http_status: int
    payload: dict[str, Any] | list[Any] | None


class TransientApiError(RuntimeError):
    def __init__(
        self,
        *,
        endpoint_name: str,
        request_url: str,
        http_status: int | None,
        message: str,
    ) -> None:
        super().__init__(message)
        self.endpoint_name = endpoint_name
        self.request_url = request_url
        self.http_status = http_status


class TheStatsApiClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key or api_key_from_env()
        self.base_url = (base_url or base_url_from_env()).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self._client = client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def fetch_endpoint(
        self,
        endpoint_name: str,
        *,
        match_id: str | None = None,
        team_id: str | None = None,
        params: dict[str, object] | None = None,
    ) -> ApiResponse:
        spec = ENDPOINTS[endpoint_name]
        query = {**spec.default_params, **(params or {})}
        paths = spec.resolve_paths(match_id=match_id, team_id=team_id)
        last_response: ApiResponse | None = None
        for index, path in enumerate(paths):
            response = self._request(endpoint_name=endpoint_name, path=path, params=query)
            last_response = response
            if index < len(paths) - 1 and self._fallbackable(response):
                continue
            return response
        if last_response is None:
            raise AssertionError(f"No path configured for endpoint {endpoint_name}.")
        return last_response

    def fetch_paginated(
        self,
        endpoint_name: str,
        *,
        base_params: dict[str, object] | None = None,
    ) -> list[ApiResponse]:
        spec = ENDPOINTS[endpoint_name]
        if not spec.paginated:
            return [self.fetch_endpoint(endpoint_name, params=base_params)]

        responses: list[ApiResponse] = []
        page = 1
        while True:
            params = {**spec.default_params, **(base_params or {}), "page": page}
            response = self.fetch_endpoint(endpoint_name, params=params)
            responses.append(response)
            payload = response.payload if isinstance(response.payload, dict) else {}
            meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
            total_pages = self._total_pages(meta, page)
            if page >= total_pages:
                break
            page += 1
        return responses

    def _request(
        self,
        *,
        endpoint_name: str,
        path: str,
        params: dict[str, object],
    ) -> ApiResponse:
        url = f"{self.base_url}{path}"
        request_url = self._request_url(url, params)
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        attempts = self.max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                response = self._client.get(url, headers=headers, params=params)
            except httpx.HTTPError as exc:
                if attempt >= attempts:
                    raise TransientApiError(
                        endpoint_name=endpoint_name,
                        request_url=request_url,
                        http_status=None,
                        message=str(exc),
                    ) from exc
                self._sleep(attempt)
                continue

            if response.status_code == 429 and attempt < attempts:
                self._sleep(attempt, response=response)
                continue
            if 500 <= response.status_code <= 599 and attempt < attempts:
                self._sleep(attempt)
                continue

            payload = self._json_payload(response)
            if response.status_code in (404, 204):
                return ApiResponse(
                    endpoint_name=endpoint_name,
                    request_url=request_url,
                    http_status=response.status_code,
                    payload=payload,
                )
            if response.status_code >= 400:
                raise TransientApiError(
                    endpoint_name=endpoint_name,
                    request_url=request_url,
                    http_status=response.status_code,
                    message=f"TheStatsAPI returned HTTP {response.status_code}.",
                )
            return ApiResponse(
                endpoint_name=endpoint_name,
                request_url=request_url,
                http_status=response.status_code,
                payload=payload,
            )

        raise AssertionError("unreachable request loop exit")

    @staticmethod
    def _fallbackable(response: ApiResponse) -> bool:
        if response.http_status in (204, 404):
            return True
        payload = response.payload
        if payload is None or payload == []:
            return True
        if isinstance(payload, dict) and payload.get("data") in (None, [], {}):
            return True
        return False

    def _sleep(self, attempt: int, response: httpx.Response | None = None) -> None:
        retry_after = response.headers.get("Retry-After") if response else None
        if retry_after and retry_after.isdigit():
            seconds = float(retry_after)
        else:
            seconds = self.backoff_seconds * (2 ** (attempt - 1))
        time.sleep(seconds)

    @staticmethod
    def _json_payload(response: httpx.Response) -> dict[str, Any] | list[Any] | None:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return {"raw_text": response.text}

    @staticmethod
    def _request_url(url: str, params: dict[str, object]) -> str:
        clean = {key: value for key, value in params.items() if value is not None}
        if not clean:
            return url
        return f"{url}?{urlencode(clean)}"

    @staticmethod
    def _total_pages(meta: dict[str, Any], current_page: int) -> int:
        explicit = meta.get("total_pages") or meta.get("last_page")
        if explicit:
            return int(explicit)
        total = meta.get("total")
        per_page = meta.get("per_page")
        if total and per_page:
            return max(current_page, ceil(int(total) / int(per_page)))
        return current_page
