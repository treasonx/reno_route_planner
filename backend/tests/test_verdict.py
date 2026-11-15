from __future__ import annotations

from datetime import timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from passcheck.domain import ChainLevel, Level, LiveStatus, Reason, Verdict, worst
from passcheck.verdict import black_ice_risk, point_verdict, segment_verdict
from tests.conftest import NOW, make_hour


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, Level.GO),
        ({"snow_in": 0.5, "temp_f": 34.0}, Level.NO_GO),
        ({"snow_in": 0.49, "temp_f": 34.0}, Level.CAUTION),
        ({"snow_in": 0.5, "temp_f": 34.1}, Level.CAUTION),  # wet snow above 34°F
        ({"snow_in": 0.9, "temp_f": 35.0, "snow_prob_pct": 10}, Level.CAUTION),  # todo 010
        ({"snow_in": 0.01, "temp_f": 45.0, "snow_prob_pct": 0}, Level.CAUTION),  # trace snow
        ({"snow_in": 0.3, "temp_f": 30.0, "snow_prob_pct": 0}, Level.CAUTION),
        ({"snow_prob_pct": 19}, Level.GO),
        ({"snow_prob_pct": 20}, Level.CAUTION),
        ({"snow_prob_pct": 40}, Level.CAUTION),
        ({"snow_prob_pct": 80}, Level.CAUTION),  # >40% without accumulation is CAUTION
        ({"freezing_rain": True}, Level.CAUTION),
    ],
    ids=[
        "clear",
        "half-inch-at-34F-no-go",
        "just-under-half-inch-caution",
        "half-inch-above-34F-caution",
        "wet-heavy-snow-35F-low-prob-caution",
        "trace-snow-warm-caution",
        "light-snow-zero-prob-caution",
        "19pct-go",
        "20pct-caution",
        "40pct-caution",
        "80pct-no-accumulation-caution",
        "freezing-rain",
    ],
)
def test_point_verdict_thresholds(overrides: dict[str, object], expected: Level) -> None:
    assert point_verdict(make_hour(**overrides)).level is expected


def test_missing_data_is_caution_never_go() -> None:
    v = point_verdict(None)
    assert v.level is Level.CAUTION
    assert v.texts == ("No forecast data",)


@pytest.mark.parametrize(
    ("overrides", "risk"),
    [
        ({"local_hour": 6, "temp_f": 30.0, "precip_prev_12h_in": 0.1}, True),
        ({"local_hour": 6, "temp_f": 30.0, "dewpoint_f": 28.0}, True),
        (
            {"local_hour": 6, "temp_f": 30.0, "snow_depth_in": 10.0, "temp_max_prev_12h_f": 40.0},
            True,
        ),
        ({"local_hour": 6, "temp_f": 30.0}, False),  # dry air, no melt
        ({"local_hour": 13, "temp_f": 30.0, "precip_prev_12h_in": 0.1}, False),  # midday
        ({"local_hour": 22, "temp_f": 35.0, "precip_prev_12h_in": 0.1}, False),  # above 34°F
        ({"local_hour": 18, "temp_f": 34.0, "precip_prev_12h_in": 0.1}, True),  # window start
        ({"local_hour": 10, "temp_f": 30.0, "precip_prev_12h_in": 0.1}, False),  # window end
    ],
    ids=["wet-night", "humid-night", "melt-refreeze", "dry", "midday", "warm", "6pm", "10am"],
)
def test_black_ice(overrides: dict[str, object], risk: bool) -> None:
    assert black_ice_risk(make_hour(**overrides)) is risk
    if risk:
        assert "Black ice risk" in point_verdict(make_hour(**overrides)).texts


def _live(
    chain: ChainLevel = ChainLevel.R0, closed: bool = False, caution: bool = False
) -> LiveStatus:
    return LiveStatus(chain, closed, caution, "desc", "Kingvale")


GO = Verdict(Level.GO)
NOGO = Verdict(Level.NO_GO, (Reason("Snow"),))


@pytest.mark.parametrize("chain", [ChainLevel.R1, ChainLevel.R2, ChainLevel.R3])
def test_live_chains_force_no_go_near_term(chain: ChainLevel) -> None:
    v = segment_verdict(GO, GO, _live(chain), False, NOW + timedelta(hours=1), NOW)
    assert v.level is Level.NO_GO
    assert f"Chains required ({chain.label}) near Kingvale" in v.texts


def test_closure_wording_differs_from_chains() -> None:
    v = segment_verdict(GO, GO, _live(closed=True), False, NOW, NOW)
    assert v.texts == ("Closed near Kingvale",)


def test_live_ignored_beyond_override_window() -> None:
    # The window is 3 h from the *start of the current hour* plus that whole hour.
    v = segment_verdict(
        GO, GO, _live(ChainLevel.R2), False, NOW + timedelta(hours=4, minutes=1), NOW
    )
    assert v.level is Level.GO


@pytest.mark.parametrize("minutes_past", [0, 1, 40, 59])
def test_live_window_depends_only_on_current_hour(minutes_past: int) -> None:
    # Todo 011: the plan cache is keyed by floor_hour(now); the live window must be too.
    now = NOW + timedelta(minutes=minutes_past)
    for arrival in (NOW + timedelta(hours=3, minutes=35), NOW + timedelta(hours=4)):
        v = segment_verdict(GO, GO, _live(ChainLevel.R2), False, arrival, now)
        assert v.level is Level.NO_GO, (minutes_past, arrival)
    beyond = segment_verdict(
        GO, GO, _live(ChainLevel.R2), False, NOW + timedelta(hours=4, minutes=1), now
    )
    assert beyond.level is Level.GO


def test_stale_forecast_floors_every_hour_at_caution() -> None:
    far = NOW + timedelta(days=5)
    v = segment_verdict(GO, GO, None, False, far, NOW, forecast_stale=True)
    assert v.level is Level.CAUTION
    assert v.texts == ("Forecast data is out of date",)
    # A floor, never a downgrade.
    assert segment_verdict(NOGO, GO, None, False, far, NOW, forecast_stale=True) == NOGO


def test_live_clear_never_downgrades_forecast_no_go() -> None:
    v = segment_verdict(NOGO, GO, _live(ChainLevel.R0), False, NOW, NOW)
    assert v.level is Level.NO_GO


def test_stale_live_source_floors_at_caution_near_term_only() -> None:
    assert segment_verdict(GO, GO, None, True, NOW, NOW).level is Level.CAUTION
    far = segment_verdict(GO, GO, None, True, NOW + timedelta(hours=5), NOW)
    assert far.level is Level.GO


def test_worst_keeps_reasons_of_top_level_only() -> None:
    v = worst(
        [
            Verdict(Level.CAUTION, (Reason("a"),)),
            Verdict(Level.NO_GO, (Reason("b"),)),
            Verdict(Level.NO_GO, (Reason("b"), Reason("c"))),
        ]
    )
    assert v == Verdict(Level.NO_GO, (Reason("b"), Reason("c")))


# --- monotonicity: more snow / colder / worse live status never improves the verdict ------

temps = st.floats(min_value=-10, max_value=60, allow_nan=False)
snows = st.floats(min_value=0, max_value=5, allow_nan=False)


@given(temp=temps, snow=snows, extra=st.floats(min_value=0, max_value=3, allow_nan=False))
def test_more_snow_never_improves(temp: float, snow: float, extra: float) -> None:
    a = point_verdict(make_hour(temp_f=temp, snow_in=snow))
    b = point_verdict(make_hour(temp_f=temp, snow_in=snow + extra))
    assert b.level.severity >= a.level.severity


probs = st.integers(min_value=0, max_value=100)


@given(
    temp=temps,
    snow=st.floats(min_value=0.001, max_value=5, allow_nan=False),
    prob=probs,
)
def test_any_forecast_snow_is_never_go(temp: float, snow: float, prob: int) -> None:
    v = point_verdict(make_hour(temp_f=temp, snow_in=snow, snow_prob_pct=prob))
    assert v.level is not Level.GO
    if snow >= 0.5 and temp <= 34.0:
        assert v.level is Level.NO_GO


@given(temp=temps, snow=snows, prob=probs, extra=st.integers(min_value=0, max_value=100))
def test_higher_probability_never_improves(temp: float, snow: float, prob: int, extra: int) -> None:
    a = point_verdict(make_hour(temp_f=temp, snow_in=snow, snow_prob_pct=prob))
    b = point_verdict(make_hour(temp_f=temp, snow_in=snow, snow_prob_pct=min(100, prob + extra)))
    assert b.level.severity >= a.level.severity


@given(temp=temps, snow=snows, drop=st.floats(min_value=0, max_value=30, allow_nan=False))
def test_colder_never_improves(temp: float, snow: float, drop: float) -> None:
    # dewpoint tracks temperature so only the temperature axis varies
    a = point_verdict(make_hour(temp_f=temp, dewpoint_f=temp - 20, snow_in=snow, local_hour=12))
    b = point_verdict(
        make_hour(temp_f=temp - drop, dewpoint_f=temp - drop - 20, snow_in=snow, local_hour=12)
    )
    assert b.level.severity >= a.level.severity


@given(
    lo=st.sampled_from(list(ChainLevel)),
    hi=st.sampled_from(list(ChainLevel)),
    base=st.sampled_from([GO, Verdict(Level.CAUTION, (Reason("x"),)), NOGO]),
)
def test_worse_live_never_improves(lo: ChainLevel, hi: ChainLevel, base: Verdict) -> None:
    lo, hi = min(lo, hi), max(lo, hi)
    a = segment_verdict(base, GO, _live(lo), False, NOW, NOW)
    b = segment_verdict(base, GO, _live(hi), False, NOW, NOW)
    assert b.level.severity >= a.level.severity >= base.level.severity
