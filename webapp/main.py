from __future__ import annotations

import os
import re
# import secrets  # ADMIN DESATIVADO: usado apenas pela comparação de chave administrativa
from pathlib import Path
from typing import Any, Callable

# ADMIN DESATIVADO: Body, Depends e Header eram usados apenas pelas rotas /api/admin/*.
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .catalog import DEFAULT_EDITION

# ADMIN DESATIVADO POR ORA (2026-07-09): a área administrativa não deve subir para
# produção nesta fase. Todo o código permanece no repositório (admin_service.py,
# curation_repository.py, static/admin.*) — para reativar, descomente os blocos
# marcados com "ADMIN DESATIVADO" neste arquivo e remova o skip em
# tests/test_admin_curation.py. As curadorias já gravadas seguem sendo APLICADAS
# na leitura (fotos/nomes/posições via DataService); apenas a edição fica fechada.
# from .admin_service import AdminService, CurationValidationError
from .data_service import DataService

ADMIN_STATIC_ASSETS = {"admin.html", "admin.js", "admin.css"}


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: dict[str, Any]):  # type: ignore[override]
        # ADMIN DESATIVADO: os assets do painel não são servidos enquanto a área
        # administrativa estiver desligada.
        if Path(path).name in ADMIN_STATIC_ASSETS:
            raise HTTPException(status_code=404, detail="Not Found")
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        return response


def create_app(
    data_root: Path | str = Path("data"),
    static_dir: Path | str | None = Path(__file__).parent / "static",
    *,
    admin_enabled: bool | None = None,
    admin_api_key: str | None = None,
    admin_db_path: Path | str | None = None,
) -> FastAPI:
    # Docs desligadas por padrão (produção); para explorar a API localmente,
    # suba com EXPOSE_API_DOCS=true. Obs.: o parâmetro correto é docs_url —
    # passar `docs=None` cai silenciosamente em **extra e não desliga nada.
    expose_docs = os.getenv("EXPOSE_API_DOCS", "false").strip().lower() in {"1", "true", "yes", "on"}
    app = FastAPI(
        title="World Cup Analytics API",
        version="1.0.0",
        docs_url="/docs" if expose_docs else None,
        redoc_url="/redoc" if expose_docs else None,
        openapi_url="/openapi.json" if expose_docs else None,
    )
    # CORS: never "*" in production. Comma-separated list via ALLOWED_ORIGINS
    # (e.g. "https://worldcup.jvmello.dev,http://localhost:8010" for local dev).
    allowed_origins = [
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", "https://worldcup.jvmello.dev").split(",")
        if origin.strip()
    ]
    # Superfície pública é somente leitura; com o admin desativado não há motivo para
    # anunciar métodos de escrita nem headers administrativos no CORS.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    service = DataService(data_root, admin_db_path=admin_db_path)
    # ADMIN DESATIVADO POR ORA: independentemente de ENABLE_ADMIN_TOOLS/admin_enabled,
    # nenhuma rota administrativa é registrada. Os parâmetros da assinatura são
    # mantidos para não quebrar chamadas existentes.
    del admin_enabled, admin_api_key
    # enabled = admin_enabled if admin_enabled is not None else os.getenv("ENABLE_ADMIN_TOOLS", "false").strip().lower() in {"1", "true", "yes", "on"}
    # configured_key = admin_api_key if admin_api_key is not None else os.getenv("ADMIN_API_KEY", "").strip()
    # admin = AdminService(service, service.curation)
    #
    # def require_admin_enabled() -> None:
    #     if not enabled:
    #         raise HTTPException(status_code=404, detail="Not Found")
    #
    # def require_admin(
    #     x_admin_key: str | None = Header(default=None),
    # ) -> None:
    #     require_admin_enabled()
    #     if configured_key and (
    #         not x_admin_key or not secrets.compare_digest(x_admin_key, configured_key)
    #     ):
    #         raise HTTPException(status_code=401, detail="Chave administrativa inválida.")
    #
    # def admin_actor(x_admin_actor: str | None = Header(default=None)) -> str:
    #     return (x_admin_actor or "local-admin").strip()[:100] or "local-admin"
    #
    # def admin_not_found(entity: str) -> HTTPException:
    #     return HTTPException(status_code=404, detail=f"{entity} não encontrado.")
    #
    # def admin_validation(error: CurationValidationError) -> HTTPException:
    #     return HTTPException(status_code=422, detail=str(error))

    # IDs de entidade entram em caminhos de arquivo no fallback bronze
    # (data/bronze/.../match_id=<id>), então o formato é validado antes de qualquer uso:
    # starlette decodifica %2F depois do roteamento, o que permitiria segmentos "../".
    safe_entity_id = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

    def require_safe_id(value: str | None) -> None:
        if value is not None and not safe_entity_id.fullmatch(value):
            raise HTTPException(status_code=404, detail="Not Found")

    def require_year(year: int) -> None:
        if year not in service.years():
            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Edição não materializada.",
                    "year": year,
                    "available_years": service.years(),
                    "default_year": DEFAULT_EDITION,
                },
            )

    def raw_gold_response(
        year: int,
        endpoint: str,
        *,
        entity_id: str | None = None,
        scope: str | None = None,
    ) -> Response | None:
        payload = service.raw_gold_payload(
            year,
            endpoint,
            entity_id=entity_id,
            scope=scope,
        )
        if payload is None:
            return None
        return Response(content=payload, media_type="application/json")

    def edition_route(
        handler: Callable[[int], dict[str, Any]],
        *,
        gold_endpoint: str | None = None,
    ) -> Callable[[int], Any]:
        def endpoint(year: int) -> Any:
            require_year(year)
            if gold_endpoint:
                raw = raw_gold_response(year, gold_endpoint)
                if raw is not None:
                    return raw
            return handler(year)

        return endpoint

    app.get("/api/health")(lambda: {"status": "ok", "default_year": DEFAULT_EDITION})
    app.get("/api/editions")(service.catalog)
    app.get("/api/editions/{year}/overview")(edition_route(service.overview, gold_endpoint="overview"))
    app.get("/api/editions/{year}/competition")(edition_route(service.competition, gold_endpoint="competition"))

    def team_detail(year: int, team_id: str) -> Any:
        require_year(year)
        require_safe_id(team_id)
        raw = raw_gold_response(year, "team_detail", entity_id=team_id)
        if raw is not None:
            return raw
        return service.team_detail(year, team_id)

    def player_detail(
        year: int,
        player_id: str,
        scope: str = "all",
        match_id: str | None = None,
    ) -> Any:
        require_year(year)
        require_safe_id(player_id)
        require_safe_id(match_id)
        payload_scope = f"match:{match_id}" if scope == "match" and match_id else scope
        raw = raw_gold_response(
            year,
            "player_detail",
            entity_id=player_id,
            scope=payload_scope,
        )
        if raw is not None:
            return raw
        return service.player_detail(year, player_id, scope=scope, match_id=match_id)

    def match_detail(year: int, match_id: str) -> Any:
        require_year(year)
        require_safe_id(match_id)
        raw = raw_gold_response(year, "match_detail", entity_id=match_id)
        if raw is not None:
            return raw
        return service.match_detail(year, match_id)

    app.get("/api/editions/{year}/teams/{team_id}")(team_detail)
    app.get("/api/editions/{year}/players/{player_id}")(player_detail)
    app.get("/api/editions/{year}/matches/{match_id}")(match_detail)
    app.get("/api/editions/{year}/teams")(edition_route(service.teams, gold_endpoint="teams"))
    app.get("/api/editions/{year}/players")(edition_route(service.players, gold_endpoint="players"))
    app.get("/api/editions/{year}/profiles")(edition_route(service.profiles, gold_endpoint="profiles"))
    app.get("/api/editions/{year}/matches")(edition_route(service.matches, gold_endpoint="matches"))
    app.get("/api/editions/{year}/shots")(edition_route(service.shots, gold_endpoint="shots"))
    app.get("/api/editions/{year}/thestatsapi-match")(
        edition_route(service.thestatsapi_match, gold_endpoint="thestatsapi_match")
    )
    app.get("/api/editions/{year}/official-metrics")(
        edition_route(service.official_metrics, gold_endpoint="official_metrics")
    )
    app.get("/api/editions/{year}/availability")(
        edition_route(service.availability, gold_endpoint="availability")
    )
    app.get("/api/history")(service.history)

    # ADMIN DESATIVADO POR ORA — rotas /api/admin/* não são registradas.
    #
    # @app.get("/api/admin/config")
    # def admin_config() -> dict[str, Any]:
    #     require_admin_enabled()
    #     return {**admin.config(), "requires_key": bool(configured_key)}
    #
    # @app.get("/api/admin/teams", dependencies=[Depends(require_admin)])
    # def admin_teams() -> dict[str, Any]:
    #     return admin.teams()
    #
    # @app.get("/api/admin/teams/{team_id}", dependencies=[Depends(require_admin)])
    # def admin_team(team_id: str) -> dict[str, Any]:
    #     result = admin.team(team_id)
    #     if result is None:
    #         raise admin_not_found("Seleção")
    #     return result
    #
    # @app.get("/api/admin/teams/{team_id}/players", dependencies=[Depends(require_admin)])
    # def admin_team_players(team_id: str) -> dict[str, Any]:
    #     result = admin.team(team_id)
    #     if result is None:
    #         raise admin_not_found("Seleção")
    #     return {"team": result["team"], "summary": result["summary"], "items": result["players"]}
    #
    # @app.get("/api/admin/players", dependencies=[Depends(require_admin)])
    # def admin_players() -> dict[str, Any]:
    #     return admin.players()
    #
    # @app.get("/api/admin/players/{player_id}", dependencies=[Depends(require_admin)])
    # def admin_player(player_id: str) -> dict[str, Any]:
    #     result = admin.player(player_id)
    #     if result is None:
    #         raise admin_not_found("Jogador")
    #     return result
    #
    # @app.get("/api/admin/position-overrides", dependencies=[Depends(require_admin)])
    # def admin_position_overrides() -> dict[str, Any]:
    #     payload = admin.players()
    #     payload["items"] = [item for item in payload["items"] if item["has_override"]]
    #     return payload
    #
    # @app.put("/api/admin/players/{player_id}/overrides", dependencies=[Depends(require_admin)])
    # def save_admin_player(
    #     player_id: str,
    #     payload: dict[str, Any] = Body(default_factory=dict),
    #     x_admin_actor: str | None = Header(default=None),
    # ) -> dict[str, Any]:
    #     try:
    #         return admin.save_player_override(
    #             player_id,
    #             payload,
    #             updated_by=admin_actor(x_admin_actor),
    #         )
    #     except KeyError:
    #         raise admin_not_found("Jogador")
    #     except CurationValidationError as error:
    #         raise admin_validation(error)
    #
    # @app.delete("/api/admin/players/{player_id}/overrides", status_code=204, dependencies=[Depends(require_admin)])
    # def delete_admin_player(
    #     player_id: str,
    #     x_admin_actor: str | None = Header(default=None),
    # ) -> Response:
    #     if not service.curation.delete_player_override(
    #         player_id,
    #         updated_by=admin_actor(x_admin_actor),
    #     ):
    #         raise admin_not_found("Override do jogador")
    #     return Response(status_code=204)
    #
    # @app.put("/api/admin/teams/{team_id}/overrides", dependencies=[Depends(require_admin)])
    # def save_admin_team(
    #     team_id: str,
    #     payload: dict[str, Any] = Body(default_factory=dict),
    #     x_admin_actor: str | None = Header(default=None),
    # ) -> dict[str, Any]:
    #     try:
    #         return admin.save_team_override(
    #             team_id,
    #             payload,
    #             updated_by=admin_actor(x_admin_actor),
    #         )
    #     except KeyError:
    #         raise admin_not_found("Seleção")
    #     except CurationValidationError as error:
    #         raise admin_validation(error)

    if static_dir is not None:
        resolved_static = Path(static_dir)
        if resolved_static.is_dir():
            app.mount(
                "/static",
                NoCacheStaticFiles(directory=resolved_static),
                name="static",
            )
            index = resolved_static / "index.html"
            if index.exists():
                def spa_index() -> FileResponse:
                    return FileResponse(
                        index,
                        headers={"Cache-Control": "no-store"},
                    )

                app.get("/", include_in_schema=False)(
                    spa_index
                )

                # ADMIN DESATIVADO POR ORA — o painel /admin não é servido.
                # admin_index = resolved_static / "admin.html"
                # if enabled and admin_index.exists():
                #     @app.get("/admin", include_in_schema=False)
                #     @app.get("/admin/{admin_path:path}", include_in_schema=False)
                #     def admin_spa(admin_path: str = "") -> FileResponse:
                #         return FileResponse(
                #             admin_index,
                #             headers={"Cache-Control": "no-store"},
                #         )

                @app.get("/{full_path:path}", include_in_schema=False)
                def spa_fallback(full_path: str) -> FileResponse:
                    first_segment = full_path.strip("/").split("/", 1)[0]
                    if first_segment in ("history", "about") or first_segment.isdigit():
                        return spa_index()
                    raise HTTPException(status_code=404, detail="Not Found")

    return app


app = create_app()
