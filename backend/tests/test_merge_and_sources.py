from __future__ import annotations

import asyncio
import json
import math
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
import respx
from pydantic import SecretStr

from passcheck.corridors import P, segment_key
from passcheck.domain import ChainLevel, LiveObservation, LiveSourceName, RawHour, RouteId
from passcheck.merge import derive_hours, map_live
from passcheck.sources import caltrans, ndot, openmeteo, wu
from passcheck.sources.base import ForecastResult, HintResult, LiveResult, UpstreamError
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


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "NaN", "-Infinity"])
def test_caltrans_drops_non_finite_coordinates(bad: float | str) -> None:
    doc = load_json("caltrans_cc_d10.json")
    item = next(i for i in doc["data"] if i["cc"]["location"]["route"] == "SR-88")
    assert caltrans.parse_cc({"data": [item]}, NOW)  # sanity: valid item is kept
    item["cc"]["location"]["latitude"] = bad
    assert caltrans.parse_cc({"data": [item]}, NOW) == []


def test_caltrans_missing_timestamp_falls_back_to_now() -> None:
    doc = load_json("caltrans_cc_d10.json")
    item = next(i for i in doc["data"] if i["cc"]["location"]["route"] == "SR-88")
    item["cc"]["statusData"]["statusTimestamp"] = None
    assert caltrans.parse_cc({"data": [item]}, NOW)[0].observed_at == NOW


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


def test_openmeteo_keeps_zero_values() -> None:
    doc = load_json("openmeteo.json")[0]
    for key in (
        "freezing_level_height",
        "precipitation",
        "precipitation_probability",
        "snow_depth",
        "weather_code",
    ):
        doc["hourly"][key][0] = 0
    first = openmeteo.parse_location(doc)[0]
    assert first.freezing_level_ft == 0.0  # not the 99,999 ft "missing" default
    assert (first.precip_in, first.precip_prob_pct, first.snow_depth_in) == (0.0, 0, 0.0)
    assert first.weather_code == 0


def test_openmeteo_missing_optional_uses_default() -> None:
    doc = load_json("openmeteo.json")[0]
    doc["hourly"]["freezing_level_height"][0] = None
    assert openmeteo.parse_location(doc)[0].freezing_level_ft >= 99999.0  # "very high"


@pytest.mark.parametrize(
    "key",
    [
        "temperature_2m",
        "dew_point_2m",
        "snowfall",
        "precipitation",
        "precipitation_probability",
        "weather_code",
        "freezing_level_height",
        "snow_depth",
    ],
)
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_openmeteo_drops_non_finite_hours(key: str, bad: float) -> None:
    doc = load_json("openmeteo.json")[0]
    doc["hourly"][key][3] = bad
    hours = openmeteo.parse_location(doc)
    assert len(hours) == 47  # dropped -> "No forecast data" (CAUTION), never GO
    assert all(math.isfinite(h.temp_f) and math.isfinite(h.snow_in) for h in hours)


def test_openmeteo_nan_in_raw_json_is_dropped() -> None:
    # json.loads accepts bare NaN/Infinity tokens; they must not survive parsing.
    doc = load_json("openmeteo.json")
    many = [doc[0]] * len(openmeteo.POINT_IDS)
    raw_text = json.dumps(many)
    first_temp = json.dumps(doc[0]["hourly"]["temperature_2m"][0])
    raw_text = raw_text.replace(f'"temperature_2m": [{first_temp},', '"temperature_2m": [NaN,')
    result = openmeteo.OpenMeteoForecast().parse(raw_text.encode(), NOW)
    assert isinstance(result, ForecastResult)
    assert all(len(v) == 47 for v in result.series.values())


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


CLEAR = (ChainLevel.R0, False, False)
CAUTION = (ChainLevel.R0, False, True)
CLOSED = (ChainLevel.R0, True, False)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # positives
        ("Chains Required, All Vehicles except 4WD", (ChainLevel.R2, False, False)),
        ("Chain controls / traction devices", (ChainLevel.R1, False, False)),
        ("R-2 in effect", (ChainLevel.R2, False, False)),
        ("Snow tires required", (ChainLevel.R1, False, False)),
        ("Road Closed", CLOSED),
        ("Holding Traffic", CAUTION),
        ("Icy spots", CAUTION),
        # negations -> clear
        ("No Chain Controls", CLEAR),
        ("No chains required", CLEAR),
        ("Chain Controls Lifted", CLEAR),
        ("Chain controls have been lifted", CLEAR),
        ("Chain controls not in effect", CLEAR),
        ("Reopened, previously closed", CLEAR),
        ("Road reopened", CLEAR),
        ("Restrictions lifted", CLEAR),
        ("Open", CLEAR),
        # plain all-clear
        ("", CLEAR),
        ("   ", CLEAR),
        ("Dry", CLEAR),
        ("Clear", CLEAR),
        ("Normal", CLEAR),
        # word boundaries: "device" is not "ice", "closedown"-style tokens don't match
        ("Message device out of service", CAUTION),
        ("Traffic device installed", CAUTION),
        # a negation does not hide a real hazard elsewhere in the text
        ("Reopened; chains required", (ChainLevel.R2, False, False)),
        ("No delays, holding traffic at summit", CAUTION),
        # unknown -> caution (Caltrans policy)
        ("Something new", CAUTION),
        ("Wet", CAUTION),
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


@pytest.mark.parametrize("stamp", [float("nan"), float("inf"), 10**30, "x"])
def test_ndot_bad_timestamp_falls_back_to_now(stamp: float | str) -> None:
    sp = P["spooner"]
    items = [
        {
            "RoadwayName": "US-50",
            "Overall Status": "Dry",
            "EncodedPolyline": _encode([(sp.lat, sp.lon)]),
            "LastUpdated": stamp,
        }
    ]
    obs = ndot.parse_conditions(items, NOW)
    assert [o.observed_at for o in obs] == [NOW]


def test_ndot_and_wu_fetch_without_key_raise_upstream_error() -> None:
    async def go() -> None:
        async with httpx.AsyncClient() as client:
            for src in (ndot.NdotRoadConditions(None), wu.WuDailyForecast(None)):
                with pytest.raises(UpstreamError, match="not configured"):
                    await src.fetch(client)

    asyncio.run(go())


def test_ndot_and_wu_unconfigured_without_key() -> None:
    assert not ndot.NdotRoadConditions(None).configured
    assert not ndot.NdotRoadConditions(SecretStr("")).configured
    assert not wu.WuDailyForecast(None).configured
    assert wu.WuDailyForecast(SecretStr("abc")).configured


# --- WU -----------------------------------------------------------------------------------


def _wu_envelope(docs: dict[str, str]) -> bytes:
    """Same shape ``WuDailyForecast.fetch`` produces: {point_id: raw body text}."""
    return json.dumps(docs).encode()


def test_wu_parse_daily() -> None:
    docs = {
        "donner": json.dumps(
            {
                "validTimeLocal": [
                    "2026-11-15T07:00:00-0800",
                    "2026-11-16T07:00:00-0800",
                    "2026-11-17T07:00:00-0800",
                ],
                "qpfSnow": [0.0, 6.5, None],
            }
        ),
        "nowhere": json.dumps({"validTimeLocal": [], "qpfSnow": []}),
    }
    result = wu.WuDailyForecast(SecretStr("k")).parse(_wu_envelope(docs), NOW)
    assert isinstance(result, HintResult)
    assert [(h.point_id, h.day, h.snow_in) for h in result.hints] == [
        ("donner", date(2026, 11, 15), 0.0),
        ("donner", date(2026, 11, 16), 6.5),
    ]


def test_wu_skips_non_finite_snow() -> None:
    body = (
        '{"validTimeLocal": ["2026-11-15T07:00:00-0800", "2026-11-16T07:00:00-0800"],'
        ' "qpfSnow": [NaN, 2.0]}'
    )
    result = wu.WuDailyForecast(SecretStr("k")).parse(_wu_envelope({"donner": body}), NOW)
    assert isinstance(result, HintResult)
    assert [(h.day, h.snow_in) for h in result.hints] == [(date(2026, 11, 16), 2.0)]


def test_wu_invalid_body_fails_whole_source() -> None:
    with pytest.raises(json.JSONDecodeError):
        wu.WuDailyForecast(SecretStr("k")).parse(_wu_envelope({"donner": "<html>"}), NOW)


def test_wu_fetch_carries_raw_bodies() -> None:
    body = b'{"validTimeLocal": ["2026-11-15T07:00:00-0800"], "qpfSnow": [1.5]}'

    async def go() -> bytes:
        with respx.mock:
            respx.get(url__startswith="https://api.weather.com/").mock(
                return_value=httpx.Response(200, content=body)
            )
            async with httpx.AsyncClient() as client:
                return await wu.WuDailyForecast(SecretStr("k")).fetch(client)

    envelope = json.loads(asyncio.run(go()))
    assert set(envelope) == set(wu.SUMMITS)
    assert all(v == body.decode() for v in envelope.values())


# --- corridors ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pid", "elevation", "label"),
    [
        ("donner", 7056, "Donner Summit 7,056′"),
        ("spooner", 7146, "Spooner 7,146′"),
        ("echo", 7382, "Echo Summit 7,382′"),
        ("carson_pass", 8574, "Carson Pass 8,574′"),
    ],
)
def test_summit_label_matches_elevation(pid: str, elevation: int, label: str) -> None:
    assert P[pid].elevation_ft == elevation
    assert P[pid].peak_label == label


def test_only_summits_have_peak_labels() -> None:
    labelled = {pid for pid, p in P.items() if p.peak_label}
    assert labelled == {"donner", "spooner", "echo", "carson_pass"}
    for p in P.values():
        if p.peak_label:
            assert p.peak_label.endswith(f"{p.elevation_ft:,}′")
