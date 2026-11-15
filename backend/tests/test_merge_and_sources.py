from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import SecretStr

from passcheck.corridors import P, segment_key
from passcheck.domain import ChainLevel, LiveObservation, LiveSourceName, RawHour, RouteId
from passcheck.merge import derive_hours, map_live
from passcheck.sources import caltrans, ndot, openmeteo, wu
from passcheck.sources.base import ForecastResult, HintResult, LiveResult
from tests.conftest import NOW, load_fixture, load_json

DEFAULT = caltrans.CaltransChainControls()


def raw(t: datetime, **kw: float) -> RawHour:
    base = {
        "temp_f": 40.0,
        "dewpoint_f": 20.0,
        "snow_in": 0.0,
        "precip_in": 0.0,
        "precip_prob_pct": 0,
        "weather_code": 0,
        "freezing_level_ft": 12000.0,
        "snow_depth_in": 0.0,
    }
    base.update(kw)
    return RawHour(time=t, **base)  # type: ignore[arg-type]


# --- merge --------------------------------------------------------------------------------


def test_snow_probability_only_counts_when_snowy() -> None:
    from passcheck.domain import DEFAULT_THRESHOLDS as T

    hours = derive_hours(
        "donner",
        [
            raw(NOW, precip_prob_pct=60, temp_f=50.0),  # warm rain
            raw(NOW + timedelta(hours=1), precip_prob_pct=60, temp_f=35.0),  # near freezing
            raw(
                NOW + timedelta(hours=2), precip_prob_pct=60, temp_f=50.0, freezing_level_ft=7500.0
            ),
        ],
        T,
    )
    assert [h.snow_prob_pct for h in hours] == [0, 60, 60]


def test_prev_12h_window() -> None:
    from passcheck.domain import DEFAULT_THRESHOLDS as T

    rows = [
        raw(
            NOW + timedelta(hours=k),
            precip_in=0.1 if k == 0 else 0.0,
            temp_f=50.0 if k == 0 else 30.0,
        )
        for k in range(14)
    ]
    hours = derive_hours("truckee", rows, T)
    assert hours[1].precip_prev_12h_in == pytest.approx(0.1)
    assert hours[1].temp_max_prev_12h_f == 50.0
    assert hours[13].precip_prev_12h_in == 0.0  # 0.1 fell 13 h earlier
    assert hours[0].local_hour == 7


def test_live_maps_to_nearest_segment_and_worst_wins() -> None:
    k = P["kingvale"]
    obs = [
        LiveObservation(
            LiveSourceName.CALTRANS,
            RouteId.I80,
            k.lat,
            k.lon,
            ChainLevel.R1,
            False,
            False,
            "",
            "A",
            NOW,
        ),
        LiveObservation(
            LiveSourceName.CALTRANS,
            RouteId.I80,
            k.lat,
            k.lon,
            ChainLevel.R2,
            False,
            False,
            "",
            "B",
            NOW,
        ),
        LiveObservation(
            LiveSourceName.CALTRANS,
            RouteId.I80,
            34.0,
            -118.0,
            ChainLevel.R3,
            False,
            False,
            "",
            "LA",
            NOW,
        ),
    ]
    mapped = map_live(obs)
    assert len(mapped) == 1  # far-away LA point is dropped
    status = next(iter(mapped.values()))
    assert status.chain is ChainLevel.R2
    assert next(iter(mapped)) in {
        segment_key("donner", "kingvale"),
        segment_key("kingvale", "yuba_gap"),
    }


# --- Caltrans -----------------------------------------------------------------------------


def test_caltrans_parses_real_fixtures() -> None:
    raw_bytes = (
        b"["
        + load_fixture("caltrans_cc_d03.json")
        + b","
        + load_fixture("caltrans_cc_d10.json")
        + b"]"
    )
    result = DEFAULT.parse(raw_bytes, NOW)
    assert isinstance(result, LiveResult)
    routes = {o.route for o in result.observations}
    assert routes == {RouteId.I80, RouteId.US50, RouteId.SR88}  # SR-89 / SR-4 filtered out
    assert all(o.chain is ChainLevel.R0 and not o.closed for o in result.observations)
    assert all(o.observed_at.tzinfo is not None for o in result.observations)


@pytest.mark.parametrize(
    ("status", "chain", "closed", "caution"),
    [
        ("R-2", ChainLevel.R2, False, False),
        ("R3", ChainLevel.R3, False, False),
        ("ROAD CLOSED", ChainLevel.R0, True, False),
        ("SOMETHING NEW", ChainLevel.R0, False, True),
    ],
    ids=["R-2", "R3", "closed", "unknown-is-caution"],
)
def test_caltrans_status_mapping(
    status: str, chain: ChainLevel, closed: bool, caution: bool
) -> None:
    doc = load_json("caltrans_cc_d10.json")
    item = next(i for i in doc["data"] if i["cc"]["location"]["route"] == "SR-88")
    item["cc"]["statusData"]["status"] = status
    item["cc"]["statusData"]["statusDescription"] = "Desc\x00with\x1bcontrol\nchars " + "x" * 400
    obs = caltrans.parse_cc({"data": [item]}, NOW)[0]
    assert (obs.chain, obs.closed, obs.caution) == (chain, closed, caution)
    assert "\x00" not in obs.description
    assert "\x1b" not in obs.description
    assert len(obs.description) <= 200


def test_caltrans_invalid_json_fails_whole_source() -> None:
    with pytest.raises(json.JSONDecodeError):
        DEFAULT.parse(b'[{"data": [}]', NOW)


# --- Open-Meteo ---------------------------------------------------------------------------


def test_openmeteo_parses_real_multi_location_fixture() -> None:
    doc = load_json("openmeteo.json")
    series = openmeteo.parse_forecast(doc, ("donner", "echo"))
    donner = series["donner"]
    assert len(donner) == 48
    assert donner[0].time == datetime(2026, 11, 14, 0, 0, tzinfo=UTC)
    assert donner[0].snow_in == pytest.approx(0.882)
    assert donner[0].snow_depth_in == pytest.approx(0.295 * 12)  # ft -> in
    assert donner[0].freezing_level_ft == pytest.approx(6430.447)


def test_openmeteo_location_count_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="unexpected number"):
        openmeteo.parse_forecast(load_json("openmeteo.json"), ("donner",))


def test_openmeteo_skips_null_hours() -> None:
    doc = load_json("openmeteo.json")[0]
    doc["hourly"]["temperature_2m"][3] = None
    assert len(openmeteo.parse_location(doc)) == 47


def test_openmeteo_params_cover_every_point() -> None:
    p = openmeteo.params()
    assert len(p["latitude"].split(",")) == len(P) == len(p["elevation"].split(","))
    assert p["forecast_days"] == "12"


def test_openmeteo_source_parse() -> None:
    doc = load_json("openmeteo.json")
    many = [doc[0]] * len(openmeteo.POINT_IDS)
    result = openmeteo.OpenMeteoForecast().parse(json.dumps(many).encode(), NOW)
    assert isinstance(result, ForecastResult)
    assert set(result.series) == set(P)


# --- NDOT ---------------------------------------------------------------------------------


def _encode(coords: list[tuple[float, float]]) -> str:
    out, plat, plon = [], 0, 0
    for lat, lon in coords:
        for v, prev in ((round(lat * 1e5), plat), (round(lon * 1e5), plon)):
            d = v - prev
            d = ~(d << 1) if d < 0 else d << 1
            while d >= 0x20:
                out.append(chr((0x20 | (d & 0x1F)) + 63))
                d >>= 5
            out.append(chr(d + 63))
        plat, plon = round(lat * 1e5), round(lon * 1e5)
    return "".join(out)


def test_polyline_roundtrip() -> None:
    pts = [(39.10357, -119.89641), (39.1, -119.9)]
    decoded = ndot.decode_polyline(_encode(pts))
    assert [c for p in decoded for c in p] == pytest.approx([c for p in pts for c in p])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Chains Required, All Vehicles except 4WD", (ChainLevel.R2, False, False)),
        ("Chain controls / traction devices", (ChainLevel.R1, False, False)),
        ("Road Closed", (ChainLevel.R0, True, False)),
        ("Holding Traffic", (ChainLevel.R0, False, True)),
        ("Dry", (ChainLevel.R0, False, False)),
    ],
)
def test_ndot_classify(text: str, expected: tuple[ChainLevel, bool, bool]) -> None:
    assert ndot.classify(text) == expected


def test_ndot_parse_filters_routes() -> None:
    sp = P["spooner"]
    items = [
        {
            "RoadwayName": "US-50",
            "Overall Status": "Chains Required",
            "EncodedPolyline": _encode([(sp.lat, sp.lon)]),
            "LastUpdated": 1794740000,
            "LocationDescription": "Spooner Summit",
        },
        {
            "RoadwayName": "SR-431",
            "Overall Status": "Road Closed",
            "EncodedPolyline": _encode([(39.3, -119.9)]),
        },
        {"RoadwayName": "I 80", "Overall Status": "Dry", "EncodedPolyline": ""},
    ]
    src = ndot.NdotRoadConditions(SecretStr("k"))
    result = src.parse(json.dumps(items).encode(), NOW)
    assert isinstance(result, LiveResult)
    assert [(o.route, o.chain, o.place) for o in result.observations] == [
        (RouteId.US50, ChainLevel.R2, "Spooner Summit")
    ]


def test_ndot_and_wu_unconfigured_without_key() -> None:
    assert not ndot.NdotRoadConditions(None).configured
    assert not ndot.NdotRoadConditions(SecretStr("")).configured
    assert not wu.WuDailyForecast(None).configured
    assert wu.WuDailyForecast(SecretStr("abc")).configured


# --- WU -----------------------------------------------------------------------------------


def test_wu_parse_daily() -> None:
    docs = {
        "donner": {
            "validTimeLocal": ["2026-11-15T07:00:00-0800", "2026-11-16T07:00:00-0800"],
            "qpfSnow": [0.0, 6.5],
        },
        "nowhere": {"validTimeLocal": [], "qpfSnow": []},
    }
    result = wu.WuDailyForecast(SecretStr("k")).parse(json.dumps(docs).encode(), NOW)
    assert isinstance(result, HintResult)
    assert [(h.point_id, h.day, h.snow_in) for h in result.hints] == [
        ("donner", date(2026, 11, 15), 0.0),
        ("donner", date(2026, 11, 16), 6.5),
    ]
