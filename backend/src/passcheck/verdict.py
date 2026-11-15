"""Pure verdict rules. See the brainstorm's threshold table.

NO GO    any live chain control or closure (near-term), or >= 0.5 in of snow at <= 34°F.
CAUTION  any forecast snowfall (incl. wet snow above 34°F), black ice risk, >= 20% chance of
         snow, freezing rain, live advisories, missing data, a configured live source that is
         stale, or a forecast older than ``FORECAST_STALE_HOURS``.
GO       none of the above.

Live data only ever *adds* to ``worst()``, so it can escalate but never downgrade.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from passcheck.domain import (
    DEFAULT_THRESHOLDS,
    GO,
    LIVE_OVERRIDE_HOURS,
    ChainLevel,
    HourlyPoint,
    Level,
    LiveStatus,
    Reason,
    Thresholds,
    Verdict,
    floor_hour,
    worst,
)

# The plan cache is bucketed by ``floor_hour(now)``, so the live window is measured from the
# start of the current hour and includes that whole hour: a plan built at 10:00 and one built
# at 10:59 must apply live data to exactly the same arrivals (conservatively, up to 14:00).
LIVE_WINDOW = timedelta(hours=LIVE_OVERRIDE_HOURS + 1)

LIVE_UNAVAILABLE = Verdict(Level.CAUTION, (Reason("Live road data unavailable"),))
FORECAST_OUT_OF_DATE = Verdict(Level.CAUTION, (Reason("Forecast data is out of date"),))


def black_ice_risk(h: HourlyPoint, t: Thresholds = DEFAULT_THRESHOLDS) -> bool:
    in_window = h.local_hour >= t.black_ice_start_hour or h.local_hour < t.black_ice_end_hour
    if not in_window or h.temp_f > t.freezing_f:
        return False
    moisture = h.precip_prev_12h_in > 0 or (h.temp_f - h.dewpoint_f) <= t.black_ice_dew_spread_f
    melt_refreeze = h.snow_depth_in > 0 and h.temp_max_prev_12h_f > t.freezing_f
    return moisture or melt_refreeze


def point_verdict(h: HourlyPoint | None, t: Thresholds = DEFAULT_THRESHOLDS) -> Verdict:
    """Forecast-only verdict for one point at one hour (place names are added by the planner)."""
    if h is None:
        return Verdict(Level.CAUTION, (Reason("No forecast data"),))
    if h.snow_in >= t.nogo_snow_in and h.temp_f <= t.freezing_f:
        return Verdict(Level.NO_GO, (Reason(f"Snow {h.snow_in:.1f} in/hr"),))
    reasons: list[Reason] = []
    if h.freezing_rain:
        reasons.append(Reason("Freezing rain"))
    if h.snow_in >= t.nogo_snow_in:  # heavy but above freezing_f: wet snow, still not GO
        reasons.append(Reason(f"Wet snow {h.snow_in:.1f} in/hr"))
    elif h.snow_in > 0:  # any forecast snowfall is at least CAUTION, whatever the probability
        reasons.append(Reason("Light snow"))
    elif h.snow_prob_pct >= t.caution_snow_prob_pct:
        reasons.append(Reason(f"{h.snow_prob_pct}% chance of snow"))
    if black_ice_risk(h, t):
        reasons.append(Reason("Black ice risk"))
    return Verdict(Level.CAUTION, tuple(reasons)) if reasons else GO


def live_verdict(live: LiveStatus) -> Verdict:
    # Live text is free-form upstream text: it is never given a ``place`` to group on.
    if live.closed:
        return Verdict(Level.NO_GO, (Reason(f"Closed near {live.place}"),))
    if live.chain >= ChainLevel.R1:
        return Verdict(
            Level.NO_GO, (Reason(f"Chains required ({live.chain.label}) near {live.place}"),)
        )
    if live.caution:
        return Verdict(Level.CAUTION, (Reason(f"{live.description} near {live.place}"),))
    return GO


def in_live_window(arrival: datetime, now: datetime) -> bool:
    """True when live data applies to ``arrival``; depends only on ``floor_hour(now)``."""
    return arrival - floor_hour(now) <= LIVE_WINDOW


def segment_verdict(
    a: Verdict,
    b: Verdict,
    live: LiveStatus | None,
    live_floor: bool,
    arrival: datetime,
    now: datetime,
    *,
    forecast_stale: bool = False,
) -> Verdict:
    """Worst of the two endpoint verdicts plus near-term live data (escalate-only).

    A stale forecast floors every segment at CAUTION, at every hour: it can never be GO.
    """
    parts = [a, b]
    if in_live_window(arrival, now):
        if live is not None:
            parts.append(live_verdict(live))
        if live_floor:
            parts.append(LIVE_UNAVAILABLE)
    if forecast_stale:
        parts.append(FORECAST_OUT_OF_DATE)
    return worst(parts)
