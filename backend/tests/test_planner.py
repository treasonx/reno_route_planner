from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest

from passcheck.corridors import CORRIDORS, P
from passcheck.domain import (
    ChainLevel,
    DayHint,
    Direction,
    Level,
    LiveObservation,
    LiveSourceName,
    RawHour,
    Reason,
    RouteId,
    Verdict,
)
from passcheck.merge import merge
from passcheck.planner import (
    PlanContext,
    Planner,
    build_plan,
    caption_for,
    hour_label,
)

NOW = datetime(2026, 11, 15, 15, 0, tzinfo=UTC)  # 7 AM PST Sunday
NO_FLOOR = {LiveSourceName.CALTRANS: False, LiveSourceName.NDOT: False}

Weather = Callable[[str, datetime], RawHour]


def clear(pid: str, t: datetime) -> RawHour:
    return RawHour(t, 50.0, 20.0, 0.0, 0.0, 0, 0, 12000.0, 0.0)


def snowy(pid: str, t: datetime) -> RawHour:
    return RawHour(t, 25.0, 24.0, 1.0, 0.1, 90, 75, 3000.0, 10.0)


def series(
    weather: Weather, start: datetime = NOW - timedelta(days=1), hours: int = 24 * 13
) -> dict[str, list[RawHour]]:
    return {pid: [weather(pid, start + timedelta(hours=k)) for k in range(hours)] for pid in P}


def ctx(
    weather: Weather = clear,
    live: list[LiveObservation] | None = None,
    now: datetime = NOW,
    floor: dict[LiveSourceName, bool] | None = None,
    hints: list[DayHint] | None = None,
    start: datetime | None = None,
    forecast_stale: bool = False,
) -> PlanContext:
    cond = merge(1, now, series(weather, start or now - timedelta(days=1)), live or [], hints or [])
    return PlanContext(cond, now, floor or NO_FLOOR, forecast_stale)


def test_all_clear_prefers_shortest_ties_by_route_order() -> None:
    plan = build_plan(ctx(), Direction.RENO_SAC, None)
    first = plan.hours[0]
    assert first.label == "Now"
    assert first.best_route is RouteId.I80
    assert first.best_level is Level.GO
    assert first.hero.title == "Take I-80"
    assert first.routes[RouteId.US50].caption == "Clear the whole way."
    assert len(plan.hours) == 24
    assert len(plan.days) == 11


def test_segment_counts_match_corridors() -> None:
    plan = build_plan(ctx(), Direction.RENO_SAC, None)
    counts = {r: len(e.segments) for r, e in plan.hours[0].routes.items()}
    assert counts == {RouteId.I80: 6, RouteId.US50: 9, RouteId.SR88: 7}


def test_arrival_time_not_departure_time_is_used() -> None:
    # Snow only at Donner between 8:00 and 9:00 PST. Leaving Reno 7:00 reaches Donner 7:50,
    # so both the 7:00 and 8:00 forecast hours are checked -> NO GO.
    def weather(pid: str, t: datetime) -> RawHour:
        if pid == "donner" and t == datetime(2026, 11, 15, 16, 0, tzinfo=UTC):
            return snowy(pid, t)
        return clear(pid, t)

    planner = Planner(ctx(weather), Direction.RENO_SAC)
    assert planner.level(RouteId.I80, NOW).severity == Level.NO_GO.severity
    # Leaving at 5:00 reaches Donner at 5:50 -> hours 5 and 6 -> clear.
    assert planner.level(RouteId.I80, NOW - timedelta(hours=2)) is Level.GO
    # Leaving at 8:00 reaches Donner at 8:50 -> checks 8:00 and 9:00 -> NO GO.
    assert planner.level(RouteId.I80, NOW + timedelta(hours=1)) is Level.NO_GO


def test_reverse_direction_offsets() -> None:
    sac = CORRIDORS[Direction.SAC_RENO][RouteId.I80]
    assert sac.stops[0].point.id == "sacramento"
    assert sac.summit.minutes == 135 - 50
    assert [s.minutes for s in sac.stops] == sorted(s.minutes for s in sac.stops)


def test_live_chains_escalate_and_caption_names_place() -> None:
    spur = P["carson_spur"]
    live = [
        LiveObservation(
            LiveSourceName.CALTRANS,
            RouteId.SR88,
            spur.lat,
            spur.lon,
            ChainLevel.R2,
            False,
            False,
            "Chains",
            "Carson Spur",
            NOW,
        )
    ]
    planner = Planner(ctx(live=live), Direction.RENO_SAC)
    ev = planner.route_eval(RouteId.SR88, NOW)
    assert ev.verdict.level is Level.NO_GO
    assert "Chains required (R-2) near Carson Spur" in ev.caption
    # The live window runs 3 h past the end of the current hour (Spur reached ~1h46 after
    # departure): a 9 AM departure is inside it, 10 AM is beyond, so the forecast rules alone.
    assert planner.level(RouteId.SR88, NOW + timedelta(hours=2)) is Level.NO_GO
    assert planner.level(RouteId.SR88, NOW + timedelta(hours=3)) is Level.GO


def test_nevada_floor_only_when_ndot_configured_and_stale() -> None:
    no_ndot = Planner(
        ctx(floor={LiveSourceName.CALTRANS: False, LiveSourceName.NDOT: False}), Direction.RENO_SAC
    )
    assert no_ndot.level(RouteId.US50, NOW) is Level.GO
    stale_ndot = Planner(
        ctx(floor={LiveSourceName.CALTRANS: False, LiveSourceName.NDOT: True}), Direction.RENO_SAC
    )
    ev = stale_ndot.route_eval(RouteId.US50, NOW)
    assert ev.verdict.level is Level.CAUTION
    assert "Live road data unavailable" in ev.caption


def test_missing_forecast_is_caution_not_go() -> None:
    cond = merge(1, NOW, {}, [])
    planner = Planner(PlanContext(cond, NOW, NO_FLOOR), Direction.RENO_SAC)
    assert planner.level(RouteId.I80, NOW) is Level.CAUTION


def test_all_no_go_for_ten_days_says_no_window() -> None:
    plan = build_plan(ctx(snowy), Direction.RENO_SAC, None)
    hero = plan.hours[0].hero
    assert hero.title == "Don’t cross"
    assert hero.body == "No clear window in the next 10 days."
    assert all(d.level is Level.NO_GO for d in plan.days)


def test_no_go_points_to_next_go() -> None:
    clear_from = NOW + timedelta(hours=30)

    def weather(pid: str, t: datetime) -> RawHour:
        return clear(pid, t) if t >= clear_from else snowy(pid, t)

    hero = build_plan(ctx(weather), Direction.RENO_SAC, None).hours[0].hero
    assert hero.title == "Don’t cross"
    assert hero.body.startswith("Next GO: Mon")


def test_go_until_reports_end_of_run() -> None:
    snow_from = NOW + timedelta(hours=5)  # noon PST

    def weather(pid: str, t: datetime) -> RawHour:
        return snowy(pid, t) if t >= snow_from else clear(pid, t)

    hero = build_plan(ctx(weather), Direction.RENO_SAC, None).hours[0].hero
    # I-80 takes 135 min: a 9 AM departure reaches Sacramento at 11:15 and checks the 11 AM
    # and noon hours (noon is snowy), so the last clean departure is 8 AM.
    assert hero.title == "Take I-80"
    assert hero.sub == "GO for departures until 8 AM"


def test_date_mode_spans_local_day() -> None:
    plan = build_plan(ctx(), Direction.RENO_SAC, date(2026, 11, 17))
    assert len(plan.hours) == 24
    assert plan.hours[0].label == "12 AM"
    assert plan.hours[6].label == "6 AM"


def test_today_date_mode_starts_at_current_hour() -> None:
    plan = build_plan(ctx(), Direction.RENO_SAC, date(2026, 11, 15))
    assert plan.hours[0].depart == NOW
    assert len(plan.hours) == 17  # 7 AM .. 11 PM


@pytest.mark.parametrize(
    ("day", "count", "labels"),
    [
        (date(2026, 3, 8), 23, None),  # spring forward: 2 AM skipped
        (date(2026, 11, 1), 25, ["1 AM PDT", "1 AM PST"]),  # fall back: two 1 AMs
    ],
    ids=["spring-forward", "fall-back"],
)
def test_dst_days(day: date, count: int, labels: list[str] | None) -> None:
    now = datetime.combine(day - timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    plan = build_plan(ctx(now=now), Direction.RENO_SAC, day)
    got = [h.label for h in plan.hours]
    assert len(got) == count
    assert "2 AM" not in got if count == 23 else True
    if labels:
        assert [lbl for lbl in got if lbl.startswith("1 AM")] == labels


def test_midnight_crossing_uses_next_day_forecast() -> None:
    # Snow everywhere only after local midnight (08:00 UTC Nov 16). A 11 PM departure reaches
    # Donner at 11:50 PM, checks 11 PM and 12 AM -> NO GO.
    snow_from = datetime(2026, 11, 16, 8, 0, tzinfo=UTC)

    def weather(pid: str, t: datetime) -> RawHour:
        return snowy(pid, t) if t >= snow_from else clear(pid, t)

    planner = Planner(ctx(weather), Direction.RENO_SAC)
    eleven_pm = datetime(2026, 11, 16, 7, 0, tzinfo=UTC)
    assert planner.level(RouteId.I80, eleven_pm) is Level.NO_GO
    # A 10 PM departure still reaches Sacramento after midnight (12:15 AM) -> NO GO.
    assert planner.level(RouteId.I80, eleven_pm - timedelta(hours=1)) is Level.NO_GO
    # 8 PM reaches Sacramento at 10:15 PM -> entirely before the snow.
    assert planner.level(RouteId.I80, eleven_pm - timedelta(hours=3)) is Level.GO


def test_wu_day_hint_turns_go_day_into_caution() -> None:
    hints = [
        DayHint("donner", date(2026, 11, 18), 2.0),
        DayHint("echo", date(2026, 11, 18), 2.0),
        DayHint("carson_pass", date(2026, 11, 18), 2.0),
    ]
    days = {d.day: d for d in build_plan(ctx(hints=hints), Direction.RENO_SAC, None).days}
    assert days[date(2026, 11, 18)].level is Level.CAUTION
    assert "Weather Underground expects snow" in days[date(2026, 11, 18)].reasons[0]
    assert days[date(2026, 11, 19)].level is Level.GO


def test_low_confidence_from_day_seven() -> None:
    days = build_plan(ctx(), Direction.RENO_SAC, None).days
    assert [d.low_confidence for d in days] == [False] * 7 + [True] * 4


def test_caption_groups_places() -> None:
    v = Verdict(
        Level.CAUTION,
        (
            Reason("Black ice risk", "Truckee"),
            Reason("Black ice risk", "Kingvale"),
            Reason("Light snow", "Kingvale"),
        ),
    )
    assert caption_for(v) == "Black ice risk at Truckee, Kingvale. Light snow at Kingvale."


def test_caption_never_splits_free_text() -> None:
    # Todo 015: live descriptions are upstream free text and may contain " at ".
    v = Verdict(
        Level.CAUTION,
        (
            Reason("No chain controls are in effect at this time near Kingvale"),
            Reason("Expect delays at the summit near Echo Summit"),
            Reason("Black ice risk", "Truckee"),
        ),
    )
    assert caption_for(v) == (
        "No chain controls are in effect at this time near Kingvale. "
        "Expect delays at the summit near Echo Summit. "
        "Black ice risk at Truckee."
    )


def _chains_at_spur(now: datetime) -> list[LiveObservation]:
    spur = P["carson_spur"]
    return [
        LiveObservation(
            LiveSourceName.CALTRANS,
            RouteId.SR88,
            spur.lat,
            spur.lon,
            ChainLevel.R2,
            False,
            False,
            "Chains",
            "Carson Spur",
            now,
        )
    ]


def test_stale_forecast_never_produces_go() -> None:
    # Todo 001: with every forecast source older than 6 h, nothing is GO, at any hour or day.
    plan = build_plan(ctx(forecast_stale=True), Direction.RENO_SAC, None)
    for h in plan.hours:
        assert h.best_level is not Level.GO
        for ev in h.routes.values():
            assert ev.verdict.level is not Level.GO
            assert Level.GO not in ev.segments
            assert "Forecast data is out of date" in ev.caption
    assert all(d.level is not Level.GO for d in plan.days)
    assert plan.hours[0].hero.title == "Careful on I-80"
    dated = build_plan(ctx(forecast_stale=True), Direction.RENO_SAC, date(2026, 11, 20))
    assert all(h.best_level is not Level.GO for h in dated.hours)


def test_live_window_uses_cache_hour_basis() -> None:
    # Todo 011: plans are cached per floor_hour(now). Built at NOW and NOW+40min with the same
    # live R-2 they must be identical, so a cached plan never misses a live chain control.
    start = NOW - timedelta(days=1)
    later = NOW + timedelta(minutes=40)
    a = build_plan(ctx(live=_chains_at_spur(NOW), start=start), Direction.RENO_SAC, None)
    b = build_plan(ctx(live=_chains_at_spur(NOW), now=later, start=start), Direction.RENO_SAC, None)
    assert a == b
    # The whole current hour is covered: a 9 AM departure reaches the Spur ~3h46 after NOW,
    # inside the window for both builds. With the old exact-``now`` rule the 7:00 build
    # ignored it, and that cached GO was still served at 7:40 when the arrival was < 3 h away.
    nogo = [h.depart for h in a.hours if h.routes[RouteId.SR88].verdict.level is Level.NO_GO]
    assert NOW + timedelta(hours=2) in nogo


def test_hour_label() -> None:
    assert hour_label(datetime(2026, 11, 15, 20, 0, tzinfo=UTC)) == "12 PM"
    assert hour_label(datetime(2026, 11, 16, 8, 0, tzinfo=UTC)) == "12 AM"
