"""Fixture sources reproducing the approved mockup scenario relative to ``now``.

Used by tests, local UI development and browser screenshots via
``PASSCHECK_SOURCES=fixtures``. They go through the exact same Source seam as live
sources, so there are no test-only code paths in the app.

Scenario (Pacific time, day 0 = today):
- Day 0 before 9 AM: black ice on I-80 (Truckee to Yuba Gap).
- Day 0 before noon: snow above 7,500 ft (SR-88 summits); Caltrans R-2 at Carson Spur.
- Day 0 1-3 PM: 30% chance of snow near Donner and Echo summits.
- Day 0 4 PM through day 2: storm above 5,000 ft (1.5 in/hr).
- Day 3: icy morning. Days 4-6: clear (overnight refreeze). Day 7: 30% snow chance.
- Days 8-9: storm. Day 10: clear.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from passcheck.corridors import P
from passcheck.domain import (
    ChainLevel,
    LiveObservation,
    LiveSourceName,
    RawHour,
    RouteId,
    to_pacific,
)
from passcheck.sources.base import ForecastResult, LiveResult, SourceKind, SourceResult

HIGH_FT = 5000
VERY_HIGH_FT = 7500
I80_ICE = {"truckee", "donner", "kingvale", "yuba_gap"}
AFTERNOON_CHANCE = {"donner", "echo", "meyers", "twin_bridges"}


def _base_temp(elev: int, local_hour: int) -> float:
    hi = 70 - elev * 0.004
    lo = hi - 14
    return (hi + lo) / 2 + (hi - lo) / 2 * math.cos((local_hour - 15) / 24 * 2 * math.pi)


def scenario_hour(point_id: str, t: datetime, today_ordinal: int) -> RawHour:
    elev = P[point_id].elevation_ft
    local = to_pacific(t)
    day, h = local.date().toordinal() - today_ordinal, local.hour
    temp = _base_temp(elev, h)
    dew = temp - 15
    snow = precip = 0.0
    prob = code = 0
    freezing_ft = 9000.0
    depth = 0.0
    high, very_high = elev >= HIGH_FT, elev >= VERY_HIGH_FT
    storm = (day == 0 and h >= 16) or day in (1, 2, 8, 9)
    if high and (day >= 1 or (day == 0 and h >= 16)):
        depth = 24.0
    if storm:
        prob, precip = 90, 0.15
        if high:
            snow, temp, dew, code, freezing_ft = 1.5, 27.0, 26.0, 75, 4500.0
        else:
            temp, dew, code, freezing_ft = 42.0, 40.0, 63, 5500.0
    elif day == 0 and h < 9 and point_id in I80_ICE:
        temp, dew = 29.0, 27.0
    elif day == 0 and h < 12 and very_high:
        snow, temp, dew, prob, precip, code = 0.7, 27.0, 26.0, 80, 0.07, 73
    elif day == 0 and 13 <= h <= 15 and point_id in AFTERNOON_CHANCE:
        temp, prob = 34.0, 30
    elif day == 3 and h < 10 and high:
        temp, dew = 25.0, 23.0
    elif day in (4, 5, 6) and high:
        temp = 24.0 if (h < 9 or h >= 19) else 40.0
    elif day == 7 and high:
        temp, prob = 33.0, 30
    return RawHour(
        time=t,
        temp_f=round(temp, 1),
        dewpoint_f=round(dew, 1),
        snow_in=snow,
        precip_in=precip,
        precip_prob_pct=prob,
        weather_code=code,
        freezing_level_ft=freezing_ft,
        snow_depth_in=depth,
    )


@dataclass(frozen=True, slots=True)
class FixtureForecast:
    name: str = "openmeteo"
    kind: SourceKind = "forecast"
    interval_s: int = 3600
    configured: bool = True

    async def fetch(self, client: httpx.AsyncClient) -> bytes:
        return b""

    def parse(self, raw: bytes, now: datetime) -> SourceResult:
        start = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=24)
        today = to_pacific(now).date().toordinal()
        hours = [start + timedelta(hours=k) for k in range(24 * 13)]
        return ForecastResult({pid: [scenario_hour(pid, t, today) for t in hours] for pid in P})


@dataclass(frozen=True, slots=True)
class FixtureCaltrans:
    name: str = "caltrans"
    kind: SourceKind = "live"
    interval_s: int = 300
    configured: bool = True

    async def fetch(self, client: httpx.AsyncClient) -> bytes:
        return b""

    def parse(self, raw: bytes, now: datetime) -> SourceResult:
        spur, donner = P["carson_spur"], P["donner"]
        return LiveResult(
            LiveSourceName.CALTRANS,
            [
                LiveObservation(
                    LiveSourceName.CALTRANS,
                    RouteId.SR88,
                    spur.lat,
                    spur.lon,
                    ChainLevel.R2,
                    False,
                    False,
                    "Chains required",
                    "Carson Spur",
                    now,
                ),
                LiveObservation(
                    LiveSourceName.CALTRANS,
                    RouteId.I80,
                    donner.lat,
                    donner.lon,
                    ChainLevel.R0,
                    False,
                    False,
                    "No chain controls",
                    "Donner Summit",
                    now,
                ),
            ],
        )


def fixture_sources() -> list[FixtureForecast | FixtureCaltrans]:
    return [FixtureForecast(), FixtureCaltrans()]
