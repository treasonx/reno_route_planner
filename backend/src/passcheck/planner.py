"""Pure planner: departure hour -> arrival at each stop -> route verdicts -> best route.

Never reads the clock; ``now`` is always passed in.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from passcheck.corridors import CORRIDORS, Stop, segment_key
from passcheck.domain import (
    PACIFIC,
    ROUTE_ORDER,
    Direction,
    Level,
    LiveSourceName,
    RouteId,
    Verdict,
    to_pacific,
    worst,
)
from passcheck.merge import Conditions
from passcheck.verdict import point_verdict, segment_verdict

HOUR = timedelta(hours=1)
DAYS_AHEAD = 10
DAY_WINDOW = (6, 20)  # departures from 6 AM through 8 PM count toward a day's verdict
LOW_CONFIDENCE_FROM_DAY = 7


@dataclass(frozen=True, slots=True)
class RouteEval:
    route: RouteId
    verdict: Verdict
    caption: str
    segments: tuple[Level, ...]
    summit_eta: datetime


@dataclass(frozen=True, slots=True)
class Hero:
    title: str
    sub: str
    body: str


@dataclass(frozen=True, slots=True)
class HourPlan:
    depart: datetime
    label: str
    best_route: RouteId
    best_level: Level
    hero: Hero
    routes: Mapping[RouteId, RouteEval]


@dataclass(frozen=True, slots=True)
class DayPlan:
    day: date
    dow: str
    level: Level
    best_route: RouteId | None
    reasons: tuple[str, ...]
    low_confidence: bool


@dataclass(frozen=True, slots=True)
class Plan:
    direction: Direction
    hours: tuple[HourPlan, ...]
    days: tuple[DayPlan, ...]


@dataclass(frozen=True, slots=True)
class PlanContext:
    conditions: Conditions
    now: datetime
    # A live source is "floored" when it is configured but stale/down.
    live_floor: Mapping[LiveSourceName, bool]


def floor_hour(t: datetime) -> datetime:
    t = t.astimezone(UTC)
    return t.replace(minute=0, second=0, microsecond=0)


def hour_label(t: datetime) -> str:
    local = to_pacific(t)
    h12 = local.hour % 12 or 12
    label = f"{h12} {'AM' if local.hour < 12 else 'PM'}"
    other = local.replace(fold=1 - local.fold)
    if other.utcoffset() != local.utcoffset():  # ambiguous wall time (fall-back day)
        label += f" {local.tzname()}"
    return label


def day_label(t: datetime) -> str:
    return to_pacific(t).strftime("%a")


def local_midnight(d: date) -> datetime:
    return datetime.combine(d, time(0), tzinfo=PACIFIC).astimezone(UTC)


def _place(v: Verdict, name: str) -> Verdict:
    return Verdict(v.level, tuple(f"{r} at {name}" for r in v.reasons))


def caption_for(v: Verdict) -> str:
    """Group "X at A", "X at B" into "X at A, B"."""
    if not v.reasons:
        return "Clear the whole way."
    groups: dict[str, list[str]] = {}
    for r in v.reasons:
        head, sep, place = r.rpartition(" at ")
        key, where = (head, place) if sep else (r, "")
        groups.setdefault(key, [])
        if where and where not in groups[key]:
            groups[key].append(where)
    parts = [f"{k} at {', '.join(w)}" if w else k for k, w in groups.items()]
    return ". ".join(parts) + "."


class Planner:
    def __init__(self, ctx: PlanContext, direction: Direction) -> None:
        self.ctx = ctx
        self.direction = direction
        self.corridors = CORRIDORS[direction]
        self.now_hour = floor_hour(ctx.now)
        today = to_pacific(ctx.now).date()
        self.horizon_end = local_midnight(today + timedelta(days=DAYS_AHEAD + 1))
        self._cache: dict[tuple[RouteId, datetime], RouteEval] = {}
        self._best: dict[datetime, tuple[RouteId, Level]] = {}
        self._points: dict[tuple[str, datetime, bool], Verdict] = {}

    # --- point / segment / route evaluation -------------------------------------------

    def _point_at(self, stop: Stop, arrival: datetime) -> Verdict:
        lo = floor_hour(arrival)
        exact = arrival == lo
        key = (stop.point.id, lo, exact)
        cached = self._points.get(key)
        if cached is not None:
            return cached
        hours = [lo] if exact else [lo, lo + HOUR]
        found = [self.ctx.conditions.verdict_at(stop.point.id, h) for h in hours]
        verdicts = [v if v is not None else point_verdict(None) for v in found]
        result = _place(worst(verdicts), stop.point.name)
        self._points[key] = result
        return result

    def _floored(self, stop: Stop) -> bool:
        return bool(self.ctx.live_floor.get(stop.point.live_source, False))

    def route_eval(self, route: RouteId, t0: datetime) -> RouteEval:
        key = (route, t0)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        corridor = self.corridors[route]
        segs: list[Verdict] = []
        for a, b in corridor.segments:
            ta, tb = t0 + timedelta(minutes=a.minutes), t0 + timedelta(minutes=b.minutes)
            live = self.ctx.conditions.live.get(segment_key(a.point.id, b.point.id))
            segs.append(
                segment_verdict(
                    self._point_at(a, ta),
                    self._point_at(b, tb),
                    live,
                    self._floored(a) or self._floored(b),
                    ta,
                    self.ctx.now,
                )
            )
        overall = worst(segs)
        result = RouteEval(
            route=route,
            verdict=overall,
            caption=caption_for(overall),
            segments=tuple(s.level for s in segs),
            summit_eta=t0 + timedelta(minutes=corridor.summit.minutes),
        )
        self._cache[key] = result
        return result

    def level(self, route: RouteId, t0: datetime) -> Level:
        return self.route_eval(route, t0).verdict.level

    def _run_end(self, route: RouteId, t0: datetime, limit: int = 24) -> datetime:
        lvl, t = self.level(route, t0), t0
        for _ in range(limit - 1):
            nxt = t + HOUR
            if nxt >= self.horizon_end or self.level(route, nxt) is not lvl:
                break
            t = nxt
        return t

    def best(self, t0: datetime) -> tuple[RouteId, Level]:
        cached = self._best.get(t0)
        if cached is not None:
            return cached

        def score(r: RouteId) -> tuple[int, float, int]:
            run = (self._run_end(r, t0) - t0) / HOUR
            return (self.level(r, t0).severity, -run, ROUTE_ORDER.index(r))

        route = min(ROUTE_ORDER, key=score)
        result = (route, self.level(route, t0))
        self._best[t0] = result
        return result

    def next_go(self, after: datetime) -> tuple[datetime, RouteId] | None:
        t = after + HOUR
        while t < self.horizon_end:
            route, lvl = self.best(t)
            if lvl is Level.GO:
                return t, route
            t += HOUR
        return None

    # --- presentation -----------------------------------------------------------------

    def hero(self, t0: datetime) -> Hero:
        route, lvl = self.best(t0)
        name = self.corridors[route].name
        caption = self.route_eval(route, t0).caption
        if lvl is Level.GO:
            until = self._run_end(route, t0)
            return Hero(f"Take {name}", f"GO for departures until {hour_label(until)}", caption)
        if lvl is Level.CAUTION:
            return Hero(f"Careful on {name}", "CAUTION: best option at this time", caption)
        nxt = self.next_go(t0)
        if nxt is None:
            body = "No clear window in the next 10 days."
        else:
            t, r = nxt
            body = f"Next GO: {day_label(t)} {hour_label(t)} on {self.corridors[r].name}."
        return Hero("Don’t cross", "NO GO on all three routes", body)

    def hour_plan(self, t0: datetime, first_is_now: bool) -> HourPlan:
        route, lvl = self.best(t0)
        return HourPlan(
            depart=t0,
            label="Now" if first_is_now and t0 == self.now_hour else hour_label(t0),
            best_route=route,
            best_level=lvl,
            hero=self.hero(t0),
            routes={r: self.route_eval(r, t0) for r in ROUTE_ORDER},
        )

    def departures(self, day: date | None) -> list[datetime]:
        if day is None:
            return [self.now_hour + k * HOUR for k in range(24)]
        start, end = local_midnight(day), local_midnight(day + timedelta(days=1))
        t = max(start, self.now_hour)
        out: list[datetime] = []
        while t < end:
            out.append(t)
            t += HOUR
        return out

    def day_plans(self) -> list[DayPlan]:
        today = to_pacific(self.ctx.now).date()
        out: list[DayPlan] = []
        for i in range(DAYS_AHEAD + 1):
            d = today + timedelta(days=i)
            deps = self.departures(d)
            window = [t for t in deps if DAY_WINDOW[0] <= to_pacific(t).hour <= DAY_WINDOW[1]]
            candidates = window or deps
            if not candidates:
                continue
            best_t = min(candidates, key=lambda t: (self.best(t)[1].severity, t))
            route, lvl = self.best(best_t)
            reasons: tuple[str, ...] = ()
            if lvl is Level.GO:
                hinted = [
                    s.point.name
                    for s in self.corridors[route].stops
                    if (hint := self.ctx.conditions.day_hints.get((s.point.id, d))) is not None
                    and hint.snow_in >= 0.5
                ]
                if hinted:
                    lvl = Level.CAUTION
                    reasons = (f"Weather Underground expects snow at {', '.join(hinted)}",)
            out.append(
                DayPlan(
                    day=d,
                    dow=d.strftime("%a"),
                    level=lvl,
                    best_route=route,
                    reasons=reasons,
                    low_confidence=i >= LOW_CONFIDENCE_FROM_DAY,
                )
            )
        return out


def build_plan(ctx: PlanContext, direction: Direction, day: date | None) -> Plan:
    planner = Planner(ctx, direction)
    hours = tuple(planner.hour_plan(t, first_is_now=day is None) for t in planner.departures(day))
    return Plan(direction=direction, hours=hours, days=tuple(planner.day_plans()))
