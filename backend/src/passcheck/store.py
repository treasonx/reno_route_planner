"""In-memory state: last-good result per source, the current ``Conditions`` snapshot,
and an LRU of serialized plan responses.

Single process, single worker, and every access happens on the event-loop thread (the API
handlers are ``async def``). ``Conditions`` is rebuilt and swapped atomically after every
successful source update; nothing is mutated in place. (Raw responses are snapshotted to
disk by the scheduler, see ``snapshot.py``.) The forecast-derived matrix is reused when only
live or hint sources changed.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from passcheck.domain import (
    FORECAST_STALE_HOURS,
    LIVE_STALE_MINUTES,
    DayHint,
    LiveObservation,
    LiveSourceName,
    RawHour,
)
from passcheck.merge import Conditions, ForecastMatrix, assemble, derive_forecast
from passcheck.planner import DayPlan
from passcheck.sources.base import (
    ForecastResult,
    HintResult,
    LiveResult,
    Source,
    SourceKind,
    SourceResult,
    UpstreamError,
)

CACHE_SIZE = 24
# The single definitions of the staleness windows (status, floors and live expiry use these).
LIVE_MAX_AGE = timedelta(minutes=LIVE_STALE_MINUTES)
FORECAST_MAX_AGE = timedelta(hours=FORECAST_STALE_HOURS)


def max_age(kind: SourceKind) -> timedelta:
    """Hints are day-level forecasts and share the forecast window."""
    return LIVE_MAX_AGE if kind == "live" else FORECAST_MAX_AGE


@dataclass(slots=True)
class SourceState:
    name: str
    kind: SourceKind
    configured: bool
    last_success: datetime | None = None
    consecutive_failures: int = 0
    last_error: str | None = None
    result: SourceResult | None = None

    def ok(self, now: datetime, max_age: timedelta) -> bool:
        return (
            self.configured and self.last_success is not None and now - self.last_success <= max_age
        )

    def fresh(self, now: datetime) -> bool:
        return self.ok(now, max_age(self.kind))


def describe_error(exc: BaseException) -> str:
    """Redacted error text: type and status only, never the message or URL."""
    if isinstance(exc, UpstreamError):
        return f"{exc.reason} ({exc.status})" if exc.status else exc.reason
    return type(exc).__name__


class Store:
    def __init__(self, sources: Sequence[Source]) -> None:
        self.states: dict[str, SourceState] = {
            s.name: SourceState(s.name, s.kind, s.configured) for s in sources
        }
        self.conditions: Conditions | None = None
        self._version = 0
        self._cache: OrderedDict[Hashable, tuple[bytes, str]] = OrderedDict()
        self._days: OrderedDict[Hashable, tuple[DayPlan, ...]] = OrderedDict()
        self._matrix: ForecastMatrix | None = None
        self._matrix_inputs: tuple[ForecastResult, ...] = ()

    # --- updates ------------------------------------------------------------------------

    def record_success(self, name: str, result: SourceResult, now: datetime) -> None:
        st = self.states[name]
        st.result, st.last_success = result, now
        st.consecutive_failures, st.last_error = 0, None
        self._rebuild(now)

    def restore(self, name: str, result: SourceResult, fetched_at: datetime, now: datetime) -> None:
        """Load a snapshot result *as of when it was fetched*: staleness is measured from
        ``fetched_at``, so restored data is treated exactly like data we fetched back then."""
        st = self.states[name]
        st.result, st.last_success = result, fetched_at
        self._rebuild(now)

    def record_failure(self, name: str, exc: BaseException) -> None:
        st = self.states[name]
        st.consecutive_failures += 1
        st.last_error = describe_error(exc)

    def _forecast_matrix(self) -> ForecastMatrix | None:
        """Re-derive forecast hours/verdicts only when a forecast result object changed."""
        inputs = tuple(
            st.result for st in self.states.values() if isinstance(st.result, ForecastResult)
        )
        same = len(inputs) == len(self._matrix_inputs) and all(
            a is b for a, b in zip(inputs, self._matrix_inputs, strict=True)
        )
        if self._matrix is None or not same:
            series: dict[str, list[RawHour]] = {}
            for r in inputs:
                for pid, rows in r.series.items():
                    series.setdefault(pid, []).extend(rows)
            if not series:
                return None  # no forecast yet: keep serving "unavailable"
            self._matrix, self._matrix_inputs = derive_forecast(series), inputs
        return self._matrix

    def _rebuild(self, now: datetime) -> None:
        matrix = self._forecast_matrix()
        if matrix is None:
            return
        live: list[LiveObservation] = []
        hints: list[DayHint] = []
        for st in self.states.values():
            match st.result:
                case LiveResult(observations=obs):
                    # A live result we fetched longer ago than the live window no longer
                    # escalates anything: the CAUTION floor covers "unknown" instead. Age is
                    # our fetch time, not the upstream ``observed_at`` (an R-2 set hours ago
                    # and still in force carries an old status timestamp).
                    if st.ok(now, LIVE_MAX_AGE):
                        live.extend(obs)
                case HintResult(hints=h):
                    hints.extend(h)
                case _:
                    pass
        self._version += 1
        self.conditions = assemble(self._version, now, matrix, live, hints)
        self._cache.clear()
        self._days.clear()

    # --- derived status -----------------------------------------------------------------

    def live_floor(self, now: datetime) -> dict[LiveSourceName, bool]:
        """A configured live source that is stale or down floors its stretches at CAUTION."""
        out: dict[LiveSourceName, bool] = {}
        for name in LiveSourceName:
            st = self.states.get(name.value)
            if st is None or not st.configured:
                out[name] = False
            else:
                out[name] = not st.ok(now, LIVE_MAX_AGE)
        return out

    def forecast_stale(self, now: datetime) -> bool:
        forecasts = [s for s in self.states.values() if s.kind == "forecast" and s.configured]
        return not any(s.ok(now, FORECAST_MAX_AGE) for s in forecasts)

    # --- response cache -----------------------------------------------------------------

    def cached(self, key: Hashable) -> tuple[bytes, str] | None:
        hit = self._cache.get(key)
        if hit is not None:
            self._cache.move_to_end(key)
        return hit

    def put(self, key: Hashable, value: tuple[bytes, str]) -> None:
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)

    def cached_days(self, key: Hashable) -> tuple[DayPlan, ...] | None:
        """Day plans don't depend on the requested date; share them across date requests."""
        hit = self._days.get(key)
        if hit is not None:
            self._days.move_to_end(key)
        return hit

    def put_days(self, key: Hashable, days: tuple[DayPlan, ...]) -> None:
        self._days[key] = days
        self._days.move_to_end(key)
        while len(self._days) > CACHE_SIZE:
            self._days.popitem(last=False)
