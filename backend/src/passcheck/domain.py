"""Core domain types. Pure data, no I/O, no framework imports."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import IntEnum, StrEnum
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")
LIVE_OVERRIDE_HOURS = 3
LIVE_STALE_MINUTES = 30
FORECAST_STALE_HOURS = 6
FREEZING_RAIN_CODES = frozenset({56, 57, 66, 67})


class Level(StrEnum):
    GO = "GO"
    CAUTION = "CAUTION"
    NO_GO = "NO GO"

    @property
    def severity(self) -> int:
        return _SEVERITY[self]


_SEVERITY: dict[Level, int] = {Level.GO: 0, Level.CAUTION: 1, Level.NO_GO: 2}


class ChainLevel(IntEnum):
    R0 = 0
    R1 = 1
    R2 = 2
    R3 = 3

    @property
    def label(self) -> str:
        return f"R-{self.value}"


class Direction(StrEnum):
    RENO_SAC = "reno-sac"
    SAC_RENO = "sac-reno"


class RouteId(StrEnum):
    I80 = "i80"
    US50 = "us50"
    SR88 = "sr88"


ROUTE_ORDER: tuple[RouteId, ...] = (RouteId.I80, RouteId.US50, RouteId.SR88)


class LiveSourceName(StrEnum):
    CALTRANS = "caltrans"
    NDOT = "ndot"


@dataclass(frozen=True, slots=True)
class Reason:
    """One human-readable cause. ``place`` is kept apart from ``text`` so captions can group
    reasons by place without ever parsing free text (live descriptions may contain " at ")."""

    text: str
    place: str = ""

    def __str__(self) -> str:
        return f"{self.text} at {self.place}" if self.place else self.text


@dataclass(frozen=True, slots=True)
class Verdict:
    level: Level
    reasons: tuple[Reason, ...] = ()

    @property
    def texts(self) -> tuple[str, ...]:
        return tuple(str(r) for r in self.reasons)


GO = Verdict(Level.GO)


def worst(verdicts: Iterable[Verdict]) -> Verdict:
    """Return the most severe level, carrying every reason at that level (escalate-only)."""
    items = list(verdicts)
    if not items:
        return GO
    top = max(v.level.severity for v in items)
    level = next(v.level for v in items if v.level.severity == top)
    reasons: list[Reason] = []
    for v in items:
        if v.level.severity == top:
            for r in v.reasons:
                if r not in reasons:
                    reasons.append(r)
    return Verdict(level, tuple(reasons))


@dataclass(frozen=True, slots=True)
class Thresholds:
    freezing_f: float = 34.0
    nogo_snow_in: float = 0.5
    caution_snow_prob_pct: int = 20
    snow_prob_temp_f: float = 36.0
    freezing_level_margin_ft: float = 1000.0
    black_ice_dew_spread_f: float = 3.0
    black_ice_start_hour: int = 18  # 6 PM local
    black_ice_end_hour: int = 10  # until 10 AM local


DEFAULT_THRESHOLDS = Thresholds()


@dataclass(frozen=True, slots=True)
class RawHour:
    """One forecast hour for one point, as reported by a forecast source (UTC)."""

    time: datetime
    temp_f: float
    dewpoint_f: float
    snow_in: float
    precip_in: float
    precip_prob_pct: int
    weather_code: int
    freezing_level_ft: float
    snow_depth_in: float


@dataclass(frozen=True, slots=True)
class HourlyPoint:
    """Merged, derived conditions for one point at one UTC hour."""

    point_id: str
    time: datetime
    local_hour: int
    temp_f: float
    dewpoint_f: float
    snow_in: float
    snow_prob_pct: int
    freezing_rain: bool
    precip_prev_12h_in: float
    temp_max_prev_12h_f: float
    snow_depth_in: float


@dataclass(frozen=True, slots=True)
class LiveObservation:
    """A live road-condition report from Caltrans or NDOT."""

    source: LiveSourceName
    route: RouteId
    lat: float
    lon: float
    chain: ChainLevel
    closed: bool
    caution: bool
    description: str
    place: str
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class LiveStatus:
    """Worst live status on one segment."""

    chain: ChainLevel
    closed: bool
    caution: bool
    description: str
    place: str


@dataclass(frozen=True, slots=True)
class DayHint:
    """Day-level snow signal (e.g. WU daily forecast) for one point."""

    point_id: str
    day: date
    snow_in: float


def to_pacific(t: datetime) -> datetime:
    return t.astimezone(PACIFIC)


def floor_hour(t: datetime) -> datetime:
    """Start of the UTC hour containing ``t`` (the plan cache's time bucket)."""
    return t.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def sanitize(text: str, limit: int = 200) -> str:
    """Strip control characters from untrusted upstream text and cap its length."""
    cleaned = "".join(ch for ch in text if ch.isprintable())
    return " ".join(cleaned.split())[:limit]
