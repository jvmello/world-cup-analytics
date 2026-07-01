from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .catalog import DEFAULT_EDITION
from .data_service import DataService


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: dict[str, Any]):  # type: ignore[override]
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        return response


def create_app(
    data_root: Path | str = Path("data"),
    static_dir: Path | str | None = Path(__file__).parent / "static",
) -> FastAPI:
    app = FastAPI(title="World Cup Analytics API", version="1.0.0")
    service = DataService(data_root)

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

    def edition_route(
        handler: Callable[[int], dict[str, Any]]
    ) -> Callable[[int], dict[str, Any]]:
        def endpoint(year: int) -> dict[str, Any]:
            require_year(year)
            return handler(year)

        return endpoint

    app.get("/api/health")(lambda: {"status": "ok", "default_year": DEFAULT_EDITION})
    app.get("/api/editions")(service.catalog)
    app.get("/api/editions/{year}/overview")(edition_route(service.overview))
    app.get("/api/editions/{year}/competition")(edition_route(service.competition))

    def team_detail(year: int, team_id: str) -> dict[str, Any]:
        require_year(year)
        return service.team_detail(year, team_id)

    def player_detail(
        year: int,
        player_id: str,
        scope: str = "all",
        match_id: str | None = None,
    ) -> dict[str, Any]:
        require_year(year)
        return service.player_detail(year, player_id, scope=scope, match_id=match_id)

    def match_detail(year: int, match_id: str) -> dict[str, Any]:
        require_year(year)
        return service.match_detail(year, match_id)

    app.get("/api/editions/{year}/teams/{team_id}")(team_detail)
    app.get("/api/editions/{year}/players/{player_id}")(player_detail)
    app.get("/api/editions/{year}/matches/{match_id}")(match_detail)
    app.get("/api/editions/{year}/teams")(edition_route(service.teams))
    app.get("/api/editions/{year}/players")(edition_route(service.players))
    app.get("/api/editions/{year}/matches")(edition_route(service.matches))
    app.get("/api/editions/{year}/shots")(edition_route(service.shots))
    app.get("/api/editions/{year}/thestatsapi-match")(
        edition_route(service.thestatsapi_match)
    )
    app.get("/api/editions/{year}/official-metrics")(
        edition_route(service.official_metrics)
    )
    app.get("/api/editions/{year}/availability")(
        edition_route(service.availability)
    )
    app.get("/api/history")(service.history)

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

                @app.get("/{full_path:path}", include_in_schema=False)
                def spa_fallback(full_path: str) -> FileResponse:
                    first_segment = full_path.strip("/").split("/", 1)[0]
                    if first_segment == "history" or first_segment.isdigit():
                        return spa_index()
                    raise HTTPException(status_code=404, detail="Not Found")

    return app


app = create_app()
