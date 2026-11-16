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
    Reason,
    RouteId,
    Verdict,
    floor_hour,
    to_pacific,
    worst,
)
from passcheck.merge import Conditions
from passcheck.verdict import point_verdict, segment_verdict

HOUR = timedelta(hours=1)
DAYS_AHEAD = 10  # the single definition of the day horizon (the API validates against it)
DAY_WINDOW = (6, 20)  # departures from 6 AM through 8 PM count toward a day's verdict
LOW_CONFIDENCE_FROM_DAY = 7


@dataclass(frozen=True, slots=True)
class StopWeather:
    """Forecast at one stop for the moment you pass it. ``None`` = no forecast for that time."""

    eta: datetime
    temp_f: float | None
    snow_depth_in: float | None
    snowfall_in_hr: float | None
    freezing_level_ft: float | None


@dataclass(frozen=True, slots=True)
class RouteEval:
    route: RouteId
    verdict: Verdict
    caption: str
    segments: tuple[Level, ...]
    summit_eta: datetime
    # One entry per corridor stop, in driving order (aligned with ``Corridor.stops``).
    weather: tuple[StopWeather, ...] = ()
    # Freezing level over the summit when you cross it.
    freezing_level_ft: float | None = None


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
    # Last departure of each route's GO run starting here (None unless that route is GO), so
    # the UI can say "GO for departures until X" for whichever highway is selected.
    go_until: Mapping[RouteId, datetime | None]


@dataclass(frozen=True, slots=True)
class DayPlan:
    day: date
    dow: str
    level: Level
    best_route: RouteId
    reasons: tuple[str, ...]
    low_confidence: bool
    # Best verdict each route can achieve that day (same departure window as ``level``).
    route_levels: Mapping[RouteId, Level]


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
    # Every forecast source is older than FORECAST_STALE_HOURS: nothing may read GO.
    forecast_stale: bool = False


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
    return Verdict(v.level, tuple(r if r.place else Reason(r.text, name) for r in v.reasons))


def _lerp(a: float, b: float, frac: float) -> float:
    return a + (b - a) * frac


def weather_at(conditions: Conditions, stop: Stop, arrival: datetime) -> StopWeather:
    """Conditions at ``stop`` when you pass it at ``arrival``.

    Temperature, snow depth and freezing level are interpolated between the two forecast hours
    around the arrival (or taken from the one that exists). Snowfall takes the larger of the two
    hours: Open-Meteo's ``snowfall`` at hour H is the total for the hour before H, so the hour
    after the arrival covers it, and ``max`` stays as conservative as the verdict. Unlike the
    verdict (which treats a missing hour as CAUTION) the tile shows nothing it doesn't have.
    """
    lo = floor_hour(arrival)
    a = conditions.hours.get((stop.point.id, lo))
    b = a if arrival == lo else conditions.hours.get((stop.point.id, lo + HOUR))
    if a is None and b is None:
        return StopWeather(arrival, None, None, None, None)
    if a is None or b is None:
        only = a if a is not None else b
        assert only is not None
        a = b = only
    frac = (arrival - lo) / HOUR
    return StopWeather(
        eta=arrival,
        temp_f=_lerp(a.temp_f, b.temp_f, frac),
        snow_depth_in=_lerp(a.snow_depth_in, b.snow_depth_in, frac),
        snowfall_in_hr=max(a.snow_in, b.snow_in),
        freezing_level_ft=_lerp(a.freezing_level_ft, b.freezing_level_ft, frac),
    )


def caption_for(v: Verdict) -> str:
    """Group (X, A), (X, B) into "X at A, B" using the structured place, never the text."""
    if not v.reasons:
        return "Clear the whole way."
    groups: dict[str, list[str]] = {}
    for r in v.reasons:
        places = groups.setdefault(r.text, [])
        if r.place and r.place not in places:
            places.append(r.place)
    parts = [f"{t} at {', '.join(ps)}" if ps else t for t, ps in groups.items()]
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
                    forecast_stale=self.ctx.forecast_stale,
                )
            )
        overall = worst(segs)
        weather = tuple(
            weather_at(self.ctx.conditions, s, t0 + timedelta(minutes=s.minutes))
            for s in corridor.stops
        )
        summit_index = corridor.stops.index(corridor.summit)
        result = RouteEval(
            route=route,
            verdict=overall,
            caption=caption_for(overall),
            segments=tuple(s.level for s in segs),
            summit_eta=t0 + timedelta(minutes=corridor.summit.minutes),
            weather=weather,
            freezing_level_ft=weather[summit_index].freezing_level_ft,
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
            lvl = self.level(r, t0)
            # Any GO highway is fine, so prefer the main route (I-80 first, by ROUTE_ORDER).
            # Below GO, prefer the highway whose current level holds the longest.
            run = 0.0 if lvl is Level.GO else (self._run_end(r, t0) - t0) / HOUR
            return (lvl.severity, -run, ROUTE_ORDER.index(r))

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
            go_until={
                r: self._run_end(r, t0) if self.level(r, t0) is Level.GO else None
                for r in ROUTE_ORDER
            },
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

    def _hinted(self, route: RouteId, d: date) -> list[str]:
        """Stops on ``route`` where the daily cross-check (WU) expects >= 0.5 in of snow."""
        return [
            s.point.name
            for s in self.corridors[route].stops
            if (hint := self.ctx.conditions.day_hints.get((s.point.id, d))) is not None
            and hint.snow_in >= 0.5
        ]

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
            hinted_by_route = {r: self._hinted(r, d) for r in ROUTE_ORDER}
            if lvl is Level.GO and hinted_by_route[route]:
                lvl = Level.CAUTION
                reasons = (
                    f"Weather Underground expects snow at {', '.join(hinted_by_route[route])}",
                )
            route_levels: dict[RouteId, Level] = {}
            for r in ROUTE_ORDER:
                r_lvl = min((self.level(r, t) for t in candidates), key=lambda x: x.severity)
                if r_lvl is Level.GO and hinted_by_route[r]:
                    r_lvl = Level.CAUTION
                route_levels[r] = r_lvl
            out.append(
                DayPlan(
                    day=d,
                    dow=d.strftime("%a"),
                    level=lvl,
                    best_route=route,
                    reasons=reasons,
                    low_confidence=i >= LOW_CONFIDENCE_FROM_DAY,
                    route_levels=route_levels,
                )
            )
        return out


def build_plan(
    ctx: PlanContext,
    direction: Direction,
    day: date | None,
    days: tuple[DayPlan, ...] | None = None,
) -> Plan:
    """Build the plan; ``days`` may be passed in when already computed for the same
    (conditions, direction, current hour, floors) since it does not depend on ``day``."""
    planner = Planner(ctx, direction)
    hours = tuple(planner.hour_plan(t, first_is_now=day is None) for t in planner.departures(day))
    if days is None:
        days = tuple(planner.day_plans())
    return Plan(direction=direction, hours=hours, days=days)
