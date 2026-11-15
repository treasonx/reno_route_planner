"""Pydantic models for the API boundary only (also the source of the frontend's types)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from passcheck.corridors import CORRIDORS, Corridor
from passcheck.domain import Direction, RouteId, to_pacific
from passcheck.planner import DayPlan, HourPlan, Plan, RouteEval, hour_label
from passcheck.store import SourceState

VerdictLevel = Literal["GO", "CAUTION", "NO GO"]
RouteKey = Literal["i80", "us50", "sr88"]
DirectionKey = Literal["reno-sac", "sac-reno"]


class Model(BaseModel):
    model_config = ConfigDict(frozen=True)


class HeroOut(Model):
    title: str
    sub: str
    body: str


class RouteOut(Model):
    verdict: VerdictLevel
    caption: str
    summit_eta: datetime
    segments: list[VerdictLevel]
    go_until: str | None  # "12 PM" label of the last GO departure in this run; None unless GO


class RoutesOut(Model):
    i80: RouteOut
    us50: RouteOut
    sr88: RouteOut


class BestOut(Model):
    route: RouteKey
    verdict: VerdictLevel


class HourOut(Model):
    depart: datetime
    label: str
    best: BestOut
    hero: HeroOut
    routes: RoutesOut


class DayRoutesOut(Model):
    """Best verdict each highway can achieve that day."""

    i80: VerdictLevel
    us50: VerdictLevel
    sr88: VerdictLevel


class DayOut(Model):
    date: date
    dow: str
    day: int
    verdict: VerdictLevel
    best_route: RouteKey
    reasons: list[str]
    low_confidence: bool
    routes: DayRoutesOut


class StopOut(Model):
    id: str
    name: str
    x: float
    y: float
    elevation_ft: int
    peak_label: str


class CorridorOut(Model):
    name: str
    summit: str
    stops: list[StopOut]
    towns: list[str]


class CorridorsOut(Model):
    i80: CorridorOut
    us50: CorridorOut
    sr88: CorridorOut


class SourceOut(Model):
    configured: bool
    ok: bool
    last_success: datetime | None
    consecutive_failures: int
    last_error: str | None


class PlanResponse(Model):
    generated_at: datetime
    snapshot_version: int
    direction: DirectionKey
    corridors: CorridorsOut
    hours: list[HourOut]
    days: list[DayOut]
    sources: dict[str, SourceOut]
    stale: bool
    notes: list[str]


class StatusResponse(Model):
    ok: bool
    snapshot_version: int | None
    sources: dict[str, SourceOut]


class HealthResponse(Model):
    ok: bool


# --- converters -------------------------------------------------------------------------


def _route_out(e: RouteEval, go_until: datetime | None) -> RouteOut:
    return RouteOut(
        verdict=e.verdict.level.value,
        caption=e.caption,
        summit_eta=to_pacific(e.summit_eta),
        segments=[lvl.value for lvl in e.segments],
        go_until=hour_label(go_until) if go_until is not None else None,
    )


def _hour_out(h: HourPlan) -> HourOut:
    return HourOut(
        depart=to_pacific(h.depart),
        label=h.label,
        best=BestOut(route=h.best_route.value, verdict=h.best_level.value),
        hero=HeroOut(title=h.hero.title, sub=h.hero.sub, body=h.hero.body),
        routes=RoutesOut(
            i80=_route_out(h.routes[RouteId.I80], h.go_until[RouteId.I80]),
            us50=_route_out(h.routes[RouteId.US50], h.go_until[RouteId.US50]),
            sr88=_route_out(h.routes[RouteId.SR88], h.go_until[RouteId.SR88]),
        ),
    )


def _day_out(d: DayPlan) -> DayOut:
    return DayOut(
        date=d.day,
        dow=d.dow,
        day=d.day.day,
        verdict=d.level.value,
        best_route=d.best_route.value,
        reasons=list(d.reasons),
        low_confidence=d.low_confidence,
        routes=DayRoutesOut(
            i80=d.route_levels[RouteId.I80].value,
            us50=d.route_levels[RouteId.US50].value,
            sr88=d.route_levels[RouteId.SR88].value,
        ),
    )


def _corridor_out(c: Corridor) -> CorridorOut:
    return CorridorOut(
        name=c.name,
        summit=c.summit.point.name,
        stops=[
            StopOut(
                id=s.point.id,
                name=s.point.name,
                x=s.x,
                y=s.y,
                elevation_ft=s.point.elevation_ft,
                peak_label=s.point.peak_label,
            )
            for s in c.stops
        ],
        towns=list(c.towns),
    )


def corridors_out(direction: Direction) -> CorridorsOut:
    cs = CORRIDORS[direction]
    return CorridorsOut(
        i80=_corridor_out(cs[RouteId.I80]),
        us50=_corridor_out(cs[RouteId.US50]),
        sr88=_corridor_out(cs[RouteId.SR88]),
    )


def source_out(st: SourceState, ok: bool) -> SourceOut:
    return SourceOut(
        configured=st.configured,
        ok=ok,
        last_success=to_pacific(st.last_success) if st.last_success else None,
        consecutive_failures=st.consecutive_failures,
        last_error=st.last_error,
    )


def plan_response(
    plan: Plan,
    generated_at: datetime,
    version: int,
    sources: dict[str, SourceOut],
    stale: bool,
    notes: list[str],
) -> PlanResponse:
    return PlanResponse(
        generated_at=to_pacific(generated_at),
        snapshot_version=version,
        direction=plan.direction.value,
        corridors=corridors_out(plan.direction),
        hours=[_hour_out(h) for h in plan.hours],
        days=[_day_out(d) for d in plan.days],
        sources=sources,
        stale=stale,
        notes=notes,
    )
