"""Pure verdict rules. See the brainstorm's threshold table.

NO GO    any live chain control or closure (near-term), or >= 0.5 in of snow at <= 34°F.
CAUTION  black ice risk, >= 20% chance of snow, light snow, freezing rain, live advisories,
         missing data, or a configured live source that is stale.
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
    Thresholds,
    Verdict,
    worst,
)


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
        return Verdict(Level.CAUTION, ("No forecast data",))
    if h.snow_in >= t.nogo_snow_in and h.temp_f <= t.freezing_f:
        return Verdict(Level.NO_GO, (f"Snow {h.snow_in:.1f} in/hr",))
    reasons: list[str] = []
    if h.freezing_rain:
        reasons.append("Freezing rain")
    if 0 < h.snow_in < t.nogo_snow_in and h.temp_f <= t.freezing_f:
        reasons.append("Light snow")
    elif h.snow_prob_pct >= t.caution_snow_prob_pct:
        reasons.append(f"{h.snow_prob_pct}% chance of snow")
    if black_ice_risk(h, t):
        reasons.append("Black ice risk")
    return Verdict(Level.CAUTION, tuple(reasons)) if reasons else GO


def live_verdict(live: LiveStatus) -> Verdict:
    if live.closed:
        return Verdict(Level.NO_GO, (f"Closed near {live.place}",))
    if live.chain >= ChainLevel.R1:
        return Verdict(Level.NO_GO, (f"Chains required ({live.chain.label}) near {live.place}",))
    if live.caution:
        return Verdict(Level.CAUTION, (f"{live.description} near {live.place}",))
    return GO


def segment_verdict(
    a: Verdict,
    b: Verdict,
    live: LiveStatus | None,
    live_floor: bool,
    arrival: datetime,
    now: datetime,
) -> Verdict:
    """Worst of the two endpoint verdicts plus near-term live data (escalate-only)."""
    parts = [a, b]
    near_term = arrival - now <= timedelta(hours=LIVE_OVERRIDE_HOURS)
    if near_term:
        if live is not None:
            parts.append(live_verdict(live))
        if live_floor:
            parts.append(Verdict(Level.CAUTION, ("Live road data unavailable",)))
    return worst(parts)
