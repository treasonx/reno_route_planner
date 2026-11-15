"""HTTP API: /api/plan, /api/status, /api/health."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response

from passcheck.domain import Direction, LiveSourceName, floor_hour, to_pacific
from passcheck.planner import DAYS_AHEAD, PlanContext, build_plan
from passcheck.schemas import (
    HealthResponse,
    PlanResponse,
    SourceOut,
    StatusResponse,
    plan_response,
    source_out,
)
from passcheck.store import Store

router = APIRouter(prefix="/api")


def _store(request: Request) -> Store:
    store: Store = request.app.state.store
    return store


def _now(request: Request) -> datetime:
    clock: Callable[[], datetime] = request.app.state.clock
    return clock()


def _sources(store: Store, now: datetime) -> dict[str, SourceOut]:
    return {name: source_out(st, st.fresh(now)) for name, st in store.states.items()}


def etag_matches(if_none_match: str | None, etag: str) -> bool:
    """RFC 9110 weak comparison: ``*``, comma-separated lists and ``W/`` prefixes."""
    if not if_none_match:
        return False
    if if_none_match.strip() == "*":
        return True
    opaque = etag.removeprefix("W/")
    return any(tag.strip().removeprefix("W/") == opaque for tag in if_none_match.split(","))


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness only: a dead upstream must never restart-loop the container."""
    return HealthResponse(ok=True)


@router.get("/status", response_model=StatusResponse)
async def status(request: Request) -> StatusResponse:
    store, now = _store(request), _now(request)
    cond = store.conditions
    return StatusResponse(
        ok=cond is not None,
        snapshot_version=cond.version if cond else None,
        sources=_sources(store, now),
    )


@router.get(
    "/plan",
    response_model=PlanResponse,
    responses={304: {"description": "Not modified"}, 503: {"description": "No data yet"}},
)
async def plan(
    request: Request,
    direction: Annotated[Direction, Query()] = Direction.RENO_SAC,
    day: Annotated[date | None, Query(alias="date")] = None,
    if_none_match: Annotated[str | None, Header()] = None,
) -> Response:
    # ``async def``: runs on the event-loop thread, the same thread that rebuilds the store,
    # so the plan caches are never touched from two threads. Building a plan is ~30 ms.
    store, now = _store(request), _now(request)
    today = to_pacific(now).date()
    if day is not None and not (today <= day <= today + timedelta(days=DAYS_AHEAD)):
        raise HTTPException(
            status_code=422, detail=f"date must be within the next {DAYS_AHEAD} days"
        )
    if day == today:
        day = None

    cond = store.conditions
    if cond is None:
        return Response(
            content=b'{"status":"unavailable"}',
            status_code=503,
            media_type="application/json",
            headers={"Cache-Control": "no-store", "Retry-After": "30"},
        )

    floor = store.live_floor(now)
    forecast_stale = store.forecast_stale(now)
    stale = forecast_stale or any(floor.values())
    # Everything the plan depends on besides ``day``; the planner only uses floor_hour(now).
    basis = (cond.version, direction, floor_hour(now), tuple(sorted(floor.items())), forecast_stale)
    key = (*basis, day)
    hit = store.cached(key)
    if hit is None:
        ctx = PlanContext(cond, now, floor, forecast_stale)
        built = build_plan(ctx, direction, day, store.cached_days(basis))
        store.put_days(basis, built.days)
        notes: list[str] = []
        ndot = store.states.get(LiveSourceName.NDOT.value)
        if ndot is None or not ndot.configured:
            notes.append("Nevada stretches are forecast-only (no live NDOT data).")
        if floor.get(LiveSourceName.CALTRANS):
            notes.append("Caltrans data is delayed. Check QuickMap before you leave.")
        body = (
            plan_response(built, now, cond.version, _sources(store, now), stale, notes)
            .model_dump_json()
            .encode()
        )
        etag = '"' + hashlib.sha256(body).hexdigest()[:20] + '"'
        hit = (body, etag)
        store.put(key, hit)

    body, etag = hit
    headers = {"ETag": etag, "Cache-Control": "no-cache"}
    if etag_matches(if_none_match, etag):
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)


@router.api_route(
    "/{rest:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"], include_in_schema=False
)
def api_not_found(rest: str) -> Response:
    raise HTTPException(status_code=404, detail="Not found")
