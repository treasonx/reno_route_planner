"""Application factory. Run with a single uvicorn worker (state is in-process)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from passcheck import scheduler
from passcheck.api import router
from passcheck.config import Settings
from passcheck.security import SecurityHeadersMiddleware, configure_logging
from passcheck.sources.base import Source
from passcheck.store import Store

log = logging.getLogger("passcheck")

USER_AGENT = "pass-check/0.1 (self-hosted; https://github.com/treasonx/reno_route_planner)"


def utc_now() -> datetime:
    return datetime.now(UTC)


def default_sources(settings: Settings) -> list[Source]:
    if settings.passcheck_sources == "fixtures":
        from passcheck.sources.fixtures import fixture_sources

        return list(fixture_sources())
    from passcheck.sources.caltrans import CaltransChainControls
    from passcheck.sources.ndot import NdotRoadConditions
    from passcheck.sources.openmeteo import OpenMeteoForecast
    from passcheck.sources.wu import WuDailyForecast

    return [
        CaltransChainControls(),
        OpenMeteoForecast(),
        NdotRoadConditions(settings.ndot_api_key),
        WuDailyForecast(settings.wu_api_key),
    ]


class ImmutableStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        resp = await super().get_response(path, scope)
        if resp.status_code == 200:
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp


def _mount_frontend(app: FastAPI, static_dir: Path) -> None:
    index = static_dir / "index.html"
    if (static_dir / "assets").is_dir():
        app.mount("/assets", ImmutableStaticFiles(directory=static_dir / "assets"), name="assets")
    # Exact-match allowlist of top-level files (manifest, icons…): no path joins on user input.
    allowlist: dict[str, Path] = (
        {
            p.name: p
            for p in static_dir.iterdir()
            if p.is_file() and not p.is_symlink() and not p.name.startswith(".")
        }
        if static_dir.is_dir()
        else {}
    )

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> Response:
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        f = allowlist.get(path)
        if f is not None and path != "index.html":
            return FileResponse(f, headers={"Cache-Control": "public, max-age=3600"})
        if index.is_file():
            return FileResponse(index, headers={"Cache-Control": "no-cache"})
        return Response("Frontend not built", status_code=404, media_type="text/plain")


def create_app(
    settings: Settings | None = None,
    sources: Sequence[Source] | None = None,
    clock: Callable[[], datetime] = utc_now,
    start_scheduler: bool = True,
) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)
    srcs = list(sources) if sources is not None else default_sources(settings)
    store = Store(srcs)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        enabled = [s.name for s in srcs if s.configured]
        disabled = [s.name for s in srcs if not s.configured]
        log.info("sources enabled=%s disabled=%s", enabled, disabled)
        if not start_scheduler:
            yield
            return
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            tasks = scheduler.start(srcs, store, client, clock)
            try:
                yield
            finally:
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(
        title="Pass Check",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.store = store
    app.state.clock = clock
    app.state.settings = settings
    app.include_router(router)
    _mount_frontend(app, settings.static_dir)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(SecurityHeadersMiddleware)
    return app


def app_factory() -> FastAPI:
    """Entry point for ``uvicorn --factory passcheck.main:app_factory``."""
    return create_app()
