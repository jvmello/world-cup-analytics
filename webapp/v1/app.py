from __future__ import annotations

import re
from typing import Any, Callable

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

from ..api_keys import ApiKeyRepository
from ..data_service import DataService
from ..rate_limit import RateLimiter

# Same shape as webapp/main.py's require_safe_id — entity ids end up in filesystem
# paths on the bronze fallback (data/bronze/.../match_id=<id>), so both public
# entry points validate identically before any use.
_SAFE_ENTITY_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

KEYLESS_DAILY_LIMIT = 100
KEYED_DAILY_LIMIT = 2000
KEY_CREATION_DAILY_LIMIT_PER_IP = 5


class ApiKeyRequest(BaseModel):
    owner_identifier: str


def create_v1_app(
    service: DataService,
    *,
    api_keys: ApiKeyRepository | None = None,
    rate_limiter: RateLimiter | None = None,
) -> FastAPI:
    """The versioned, documented, rate-limited public API for third-party
    consumers — parallel to (not a replacement for) the SPA's own unversioned
    /api/* contract, which stays exactly as-is. Mounted at /v1 by webapp/main.py.
    Deliberately always documents itself (docs_url/openapi_url are not gated by
    EXPOSE_API_DOCS like the legacy app — the whole point of this surface is to
    be a documented public product) and, being its own FastAPI instance, its
    OpenAPI schema structurally cannot include /api/* or /ops/metrics routes.
    """
    api_keys = api_keys or ApiKeyRepository()
    rate_limiter = rate_limiter or RateLimiter()

    v1 = FastAPI(
        title="World Cup Analytics API",
        version="1",
        description=(
            "Dados de leitura da Copa do Mundo 2026 (e do acervo histórico). "
            "Sem chave: 100 requisições/dia por IP. Com uma chave gerada em "
            "POST /v1/keys: 2000 requisições/dia (header X-API-Key). Chaves são "
            "permanentes até revogação manual — não há endpoint de revogação "
            "nesta fase. Pensada para consumo servidor-a-servidor: não use "
            "X-API-Key em código de navegador, a chave fica pública no momento "
            "em que é enviada ao cliente."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    def _client_ip(request: Request) -> str:
        return request.client.host if request.client else "unknown"

    def enforce_rate_limit(request: Request) -> None:
        raw_key = request.headers.get("X-API-Key")
        record = api_keys.authenticate(raw_key) if raw_key else None
        if record:
            api_keys.touch(record.id)
            bucket, limit = f"key:{record.id}", KEYED_DAILY_LIMIT
        else:
            bucket, limit = f"ip:{_client_ip(request)}", KEYLESS_DAILY_LIMIT
        if not rate_limiter.increment_and_check(bucket, limit=limit):
            raise HTTPException(
                status_code=429,
                detail="Limite diário de requisições excedido.",
            )

    def enforce_key_creation_limit(request: Request) -> None:
        bucket = f"keygen_ip:{_client_ip(request)}"
        if not rate_limiter.increment_and_check(
            bucket, limit=KEY_CREATION_DAILY_LIMIT_PER_IP
        ):
            raise HTTPException(
                status_code=429,
                detail="Limite diário de criação de chaves excedido.",
            )

    def require_year(year: int) -> None:
        if year not in service.years():
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Edição não materializada.",
                    "year": year,
                    "available_years": service.years(),
                },
            )

    def require_safe_id(value: str | None) -> None:
        if value is not None and not _SAFE_ENTITY_ID.fullmatch(value):
            raise HTTPException(status_code=404, detail="Not Found")

    rate_limited = [Depends(enforce_rate_limit)]

    def read_route(handler: Callable[[int], dict[str, Any]]) -> Callable[[int], Any]:
        def endpoint(year: int) -> Any:
            require_year(year)
            return handler(year)

        return endpoint

    v1.get("/editions", dependencies=rate_limited)(lambda: service.catalog())
    v1.get("/editions/{year}/overview", dependencies=rate_limited)(read_route(service.overview))
    v1.get("/editions/{year}/competition", dependencies=rate_limited)(read_route(service.competition))
    v1.get("/editions/{year}/teams", dependencies=rate_limited)(read_route(service.teams))
    v1.get("/editions/{year}/players", dependencies=rate_limited)(read_route(service.players))
    v1.get("/editions/{year}/profiles", dependencies=rate_limited)(read_route(service.profiles))
    v1.get("/editions/{year}/matches", dependencies=rate_limited)(read_route(service.matches))
    v1.get("/editions/{year}/shots", dependencies=rate_limited)(read_route(service.shots))
    v1.get("/history", dependencies=rate_limited)(lambda: service.history())

    @v1.get("/editions/{year}/teams/{team_id}", dependencies=rate_limited)
    def team_detail(year: int, team_id: str) -> Any:
        require_year(year)
        require_safe_id(team_id)
        return service.team_detail(year, team_id)

    @v1.get("/editions/{year}/players/{player_id}", dependencies=rate_limited)
    def player_detail(year: int, player_id: str) -> Any:
        require_year(year)
        require_safe_id(player_id)
        return service.player_detail(year, player_id)

    @v1.get("/editions/{year}/matches/{match_id}", dependencies=rate_limited)
    def match_detail(year: int, match_id: str) -> Any:
        require_year(year)
        require_safe_id(match_id)
        return service.match_detail(year, match_id)

    @v1.post("/keys", dependencies=[Depends(enforce_key_creation_limit)])
    def create_key(payload: ApiKeyRequest) -> Any:
        owner_identifier = payload.owner_identifier.strip()
        if not owner_identifier:
            raise HTTPException(status_code=422, detail="owner_identifier é obrigatório.")
        key = api_keys.create(owner_identifier)
        if key is None:
            raise HTTPException(
                status_code=503,
                detail="Serviço de chaves indisponível no momento — tente novamente em instantes.",
            )
        return {
            "key": key,
            "notice": "Guarde esta chave agora — ela não será exibida novamente. "
            "Envie-a no header X-API-Key.",
        }

    return v1
