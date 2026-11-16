"""Pure merge: per-source results -> one immutable, versioned ``Conditions`` snapshot.

The point-verdict matrix is precomputed here once per snapshot so the planner only
does lookups.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from passcheck.corridors import CORRIDORS, P, segment_key
from passcheck.domain import (
    DEFAULT_THRESHOLDS,
    FREEZING_RAIN_CODES,
    ChainLevel,
    DayHint,
    Direction,
    HourlyPoint,
    LiveObservation,
    LiveStatus,
    RawHour,
    Thresholds,
    Verdict,
    to_pacific,
)
from passcheck.verdict import point_verdict

MAX_LIVE_DISTANCE_KM = 25.0


@dataclass(frozen=True, slots=True)
class Conditions:
    version: int
    built_at: datetime
    hours: Mapping[tuple[str, datetime], HourlyPoint]
    point_verdicts: Mapping[tuple[str, datetime], Verdict]
    live: Mapping[frozenset[str], LiveStatus]
    day_hints: Mapping[tuple[str, date], DayHint] = field(
        default_factory=dict[tuple[str, date], DayHint]
    )

    def verdict_at(self, point_id: str, hour: datetime) -> Verdict | None:
        return self.point_verdicts.get((point_id, hour))


def _snow_prob(raw: RawHour, elevation_ft: int, t: Thresholds) -> int:
    snowy = (
        raw.snow_in > 0
        or raw.temp_f <= t.snow_prob_temp_f
        or raw.freezing_level_ft <= elevation_ft + t.freezing_level_margin_ft
    )
    return raw.precip_prob_pct if snowy else 0


def derive_hours(point_id: str, series: Iterable[RawHour], t: Thresholds) -> list[HourlyPoint]:
    rows = sorted(series, key=lambda r: r.time)
    elevation = P[point_id].elevation_ft
    out: list[HourlyPoint] = []
    for i, r in enumerate(rows):
        window = [w for w in rows[max(0, i - 12) : i] if r.time - w.time <= timedelta(hours=12)]
        out.append(
            HourlyPoint(
                point_id=point_id,
                time=r.time,
                local_hour=to_pacific(r.time).hour,
                temp_f=r.temp_f,
                dewpoint_f=r.dewpoint_f,
                snow_in=r.snow_in,
                snow_prob_pct=_snow_prob(r, elevation, t),
                freezing_rain=r.weather_code in FREEZING_RAIN_CODES,
                precip_prev_12h_in=round(sum(w.precip_in for w in window), 3),
                temp_max_prev_12h_f=max((w.temp_f for w in window), default=r.temp_f),
                snow_depth_in=r.snow_depth_in,
                freezing_level_ft=r.freezing_level_ft,
            )
        )
    return out


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _rank(s: LiveStatus) -> tuple[int, int, int]:
    return (int(s.closed), int(s.chain), int(s.caution))


def map_live(observations: Iterable[LiveObservation]) -> dict[frozenset[str], LiveStatus]:
    """Assign each live observation to the nearest segment of its route; worst wins."""
    corridors = CORRIDORS[Direction.RENO_SAC]
    out: dict[frozenset[str], LiveStatus] = {}
    for obs in observations:
        corridor = corridors[obs.route]
        best: tuple[float, frozenset[str]] | None = None
        for a, b in corridor.segments:
            d = min(
                _haversine_km(obs.lat, obs.lon, a.point.lat, a.point.lon),
                _haversine_km(obs.lat, obs.lon, b.point.lat, b.point.lon),
                _haversine_km(
                    obs.lat,
                    obs.lon,
                    (a.point.lat + b.point.lat) / 2,
                    (a.point.lon + b.point.lon) / 2,
                ),
            )
            if best is None or d < best[0]:
                best = (d, segment_key(a.point.id, b.point.id))
        if best is None or best[0] > MAX_LIVE_DISTANCE_KM:
            continue
        status = LiveStatus(obs.chain, obs.closed, obs.caution, obs.description, obs.place)
        if obs.chain is ChainLevel.R0 and not obs.closed and not obs.caution:
            continue
        current = out.get(best[1])
        if current is None or _rank(status) > _rank(current):
            out[best[1]] = status
    return out


@dataclass(frozen=True, slots=True)
class ForecastMatrix:
    """The forecast-derived part of a snapshot. Depends only on the forecast results, so the
    store reuses it when only live or hint sources update."""

    hours: Mapping[tuple[str, datetime], HourlyPoint]
    point_verdicts: Mapping[tuple[str, datetime], Verdict]


def derive_forecast(
    forecast: Mapping[str, Iterable[RawHour]], t: Thresholds = DEFAULT_THRESHOLDS
) -> ForecastMatrix:
    hours: dict[tuple[str, datetime], HourlyPoint] = {}
    verdicts: dict[tuple[str, datetime], Verdict] = {}
    for point_id, series in forecast.items():
        if point_id not in P:
            continue
        for h in derive_hours(point_id, series, t):
            hours[(point_id, h.time)] = h
            verdicts[(point_id, h.time)] = point_verdict(h, t)
    return ForecastMatrix(hours, verdicts)


def assemble(
    version: int,
    built_at: datetime,
    matrix: ForecastMatrix,
    live: Iterable[LiveObservation],
    day_hints: Iterable[DayHint] = (),
) -> Conditions:
    return Conditions(
        version=version,
        built_at=built_at,
        hours=matrix.hours,
        point_verdicts=matrix.point_verdicts,
        live=map_live(live),
        day_hints={(d.point_id, d.day): d for d in day_hints},
    )


def merge(
    version: int,
    built_at: datetime,
    forecast: Mapping[str, Iterable[RawHour]],
    live: Iterable[LiveObservation],
    day_hints: Iterable[DayHint] = (),
    t: Thresholds = DEFAULT_THRESHOLDS,
) -> Conditions:
    return assemble(version, built_at, derive_forecast(forecast, t), live, day_hints)
