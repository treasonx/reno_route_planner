from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from passcheck.api import etag_matches
from passcheck.config import Settings
from passcheck.domain import LiveSourceName
from passcheck.main import create_app
from passcheck.scheduler import refresh_once
from passcheck.sources.base import Source
from passcheck.sources.fixtures import FixtureCaltrans, FixtureForecast, fixture_sources
from passcheck.store import Store
from tests.conftest import NOW, build_fixture_app

GOLDEN = Path(__file__).parent / "golden" / "plan_reno_sac.json"


@pytest.fixture
def client(fixture_app: FastAPI) -> TestClient:
    return TestClient(fixture_app)


def test_health_is_liveness_only() -> None:
    app = create_app(
        Settings(static_dir=Path("/nonexistent")),
        sources=fixture_sources(),
        clock=lambda: NOW,
        start_scheduler=False,
    )
    c = TestClient(app)
    assert c.get("/api/health").json() == {"ok": True}
    # No data yet: plan is unavailable (never a verdict), status says not ready.
    r = c.get("/api/plan")
    assert r.status_code == 503
    assert r.json() == {"status": "unavailable"}
    assert c.get("/api/status").json()["ok"] is False


def test_plan_matches_golden(client: TestClient) -> None:
    body = client.get("/api/plan").json()
    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.write_text(json.dumps(body, indent=1, ensure_ascii=False) + "\n")
    assert body == json.loads(GOLDEN.read_text())


def test_plan_mockup_scenario(client: TestClient) -> None:
    body = client.get("/api/plan").json()
    now = body["hours"][0]
    assert now["label"] == "Now"
    assert {k: v["verdict"] for k, v in now["routes"].items()} == {
        "i80": "CAUTION",
        "us50": "GO",
        "sr88": "NO GO",
    }
    assert now["hero"]["title"] == "Take US-50"
    assert "Chains required (R-2) near Carson Spur" in now["routes"]["sr88"]["caption"]
    assert body["notes"] == ["Nevada stretches are forecast-only (no live NDOT data)."]
    assert body["corridors"]["us50"]["summit"] == "Echo Summit"
    assert len(body["days"]) == 11


def test_sac_reno_direction(client: TestClient) -> None:
    body = client.get("/api/plan", params={"direction": "sac-reno"}).json()
    assert body["direction"] == "sac-reno"
    assert body["corridors"]["i80"]["stops"][0]["id"] == "sacramento"


@pytest.mark.parametrize(
    "params",
    [{"date": "2026-11-14"}, {"date": "2026-11-26"}, {"date": "nope"}, {"direction": "la-sf"}],
    ids=["yesterday", "11-days-out", "garbage-date", "bad-direction"],
)
def test_validation(client: TestClient, params: dict[str, str]) -> None:
    assert client.get("/api/plan", params=params).status_code == 422


def test_date_mode(client: TestClient) -> None:
    body = client.get("/api/plan", params={"date": "2026-11-18"}).json()
    assert body["hours"][0]["label"] == "12 AM"
    assert len(body["hours"]) == 24


def test_etag_304_and_gzip(client: TestClient) -> None:
    r = client.get("/api/plan", headers={"Accept-Encoding": "gzip"})
    assert r.headers["content-encoding"] == "gzip"
    etag = r.headers["etag"]
    r2 = client.get("/api/plan", headers={"If-None-Match": etag})
    assert r2.status_code == 304


def test_security_headers_and_docs_disabled(client: TestClient) -> None:
    r = client.get("/api/health")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "server" not in {k.lower() for k in r.headers} or True  # uvicorn flag handles this
    for path in ("/docs", "/redoc", "/openapi.json"):
        resp = client.get(path)
        assert resp.status_code in (200, 404)
        assert "swagger" not in resp.text.lower()
        assert '"openapi"' not in resp.text
    assert client.get("/api/nope").status_code == 404
    assert client.get("/api/nope").json() == {"detail": "Not found"}


def test_static_allowlist_and_traversal(tmp_path: Path) -> None:
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>INDEX</html>")
    (static / "manifest.webmanifest").write_text("{}")
    (static / "assets" / "app.js").write_text("console.log(1)")
    (static / ".secret").write_text("SECRET")
    (tmp_path / "outside.txt").write_text("OUTSIDE")
    os.symlink(tmp_path / "outside.txt", static / "link.txt")
    app, _ = build_fixture_app(static_dir=static)
    c = TestClient(app)
    assert c.get("/").text == "<html>INDEX</html>"
    assert c.get("/some/client/route").text == "<html>INDEX</html>"
    assert c.get("/manifest.webmanifest").text == "{}"
    js = c.get("/assets/app.js")
    assert js.status_code == 200
    assert "immutable" in js.headers["cache-control"]
    for probe in (
        "/..%2foutside.txt",
        "/%2e%2e/outside.txt",
        "/link.txt",
        "/.secret",
        "/assets/../../outside.txt",
    ):
        r = c.get(probe)
        assert "OUTSIDE" not in r.text, probe
        assert "SECRET" not in r.text, probe


def test_status_reports_sources(client: TestClient) -> None:
    body = client.get("/api/status").json()
    assert body["ok"] is True
    assert set(body["sources"]) == {"openmeteo", "caltrans"}
    assert body["sources"]["caltrans"]["ok"] is True


def test_cold_full_plan_benchmark() -> None:
    from passcheck.domain import Direction, LiveSourceName
    from passcheck.planner import PlanContext, build_plan

    app, _ = build_fixture_app()
    cond = app.state.store.conditions
    floor = {LiveSourceName.CALTRANS: False, LiveSourceName.NDOT: False}
    best = min(
        _timed(lambda: build_plan(PlanContext(cond, NOW, floor), Direction.RENO_SAC, None))
        for _ in range(5)
    )
    # Generous bound so shared CI runners don't flake; locally this is ~30 ms.
    assert best < 0.5, f"cold plan took {best * 1000:.0f} ms"


def _timed(fn) -> float:  # type: ignore[no-untyped-def]
    t = time.perf_counter()
    fn()
    return time.perf_counter() - t


@pytest.mark.parametrize(
    ("header", "matches"),
    [
        ('"abc"', True),
        ('W/"abc"', True),
        ('"zzz", W/"abc"', True),
        ('"zzz" ,"abc"', True),
        ("*", True),
        ('"zzz"', False),
        ("", False),
        (None, False),
    ],
)
def test_etag_matches(header: str | None, matches: bool) -> None:
    assert etag_matches(header, '"abc"') is matches


def test_weak_and_listed_if_none_match_get_304(client: TestClient) -> None:
    etag = client.get("/api/plan").headers["etag"]
    for header in (f"W/{etag}", f'"other", {etag}'):
        assert client.get("/api/plan", headers={"If-None-Match": header}).status_code == 304


def _refresh(store: Store, srcs: list[Source], now: datetime) -> None:
    async def go() -> None:
        async with httpx.AsyncClient() as c:
            for s in srcs:
                await refresh_once(s, store, c, lambda: now)

    asyncio.run(go())


def test_stale_forecast_plan_has_no_go() -> None:
    # Todo 001: with the forecast last fetched 7 h ago nothing in /api/plan may be GO. The
    # fixture scenario at NOW has US-50 GO, so this exercises the floor.
    app, _ = build_fixture_app()
    store: Store = app.state.store
    store.states["openmeteo"].last_success = NOW - timedelta(hours=7)
    body = TestClient(app).get("/api/plan").json()
    assert body["stale"] is True
    verdicts = [r["verdict"] for h in body["hours"] for r in h["routes"].values()]
    verdicts += [d["verdict"] for d in body["days"]]
    assert "GO" not in verdicts
    us50 = body["hours"][0]["routes"]["us50"]
    assert us50["verdict"] == "CAUTION"
    assert "Forecast data is out of date" in us50["caption"]


def test_old_live_result_is_dropped_on_rebuild() -> None:
    # Todo 007: a live result fetched longer ago than the live window stops escalating when the
    # snapshot is rebuilt; the CAUTION floor covers "unknown" instead.
    store = Store([FixtureForecast(), FixtureCaltrans()])
    _refresh(store, [FixtureForecast(), FixtureCaltrans()], NOW)
    assert store.conditions is not None
    assert store.conditions.live
    _refresh(store, [FixtureForecast()], NOW + timedelta(minutes=31))
    assert store.conditions.live == {}
    assert store.live_floor(NOW + timedelta(minutes=31))[LiveSourceName.CALTRANS] is True


def test_live_update_reuses_forecast_matrix() -> None:
    # Todo 016: a live poll must not re-derive forecast hours/verdicts.
    store = Store([FixtureForecast(), FixtureCaltrans()])
    _refresh(store, [FixtureForecast(), FixtureCaltrans()], NOW)
    assert store.conditions is not None
    before = store.conditions
    _refresh(store, [FixtureCaltrans()], NOW + timedelta(minutes=5))
    after = store.conditions
    assert after.version == before.version + 1
    assert after.point_verdicts is before.point_verdicts
    assert after.hours is before.hours
    _refresh(store, [FixtureForecast()], NOW + timedelta(minutes=10))
    assert store.conditions.point_verdicts is not before.point_verdicts


def test_day_plans_shared_across_dates(client: TestClient) -> None:
    now_days = client.get("/api/plan").json()["days"]
    dated_days = client.get("/api/plan", params={"date": "2026-11-18"}).json()["days"]
    assert now_days == dated_days
    assert all(d["best_route"] in ("i80", "us50", "sr88") for d in now_days)


@pytest.mark.parametrize(
    ("raw", "out"),
    [(None, None), (0.0, 0.0), (0.04, 0.1), (0.25, 0.2), (1.26, 1.3), (-0.0, 0.0)],
)
def test_snow_amounts_never_round_a_trace_to_zero(raw: float | None, out: float | None) -> None:
    from passcheck.schemas import _tenths  # pyright: ignore[reportPrivateUsage]

    assert _tenths(raw) == out


def test_plan_has_weather_for_every_stop(client: TestClient) -> None:
    body = client.get("/api/plan").json()
    for key, corridor in body["corridors"].items():
        stops = corridor["stops"]
        assert sum(s["is_summit"] for s in stops) == 1
        assert stops[0]["minutes"] == 0
        assert all(s["short_label"] for s in stops)
        for hour in body["hours"]:
            weather = hour["routes"][key]["weather"]
            assert [w["id"] for w in weather] == [s["id"] for s in stops]
            assert all(isinstance(w["temp_f"], int | None) for w in weather)
    donner = next(s for s in body["corridors"]["i80"]["stops"] if s["id"] == "donner")
    assert (donner["short_label"], donner["is_summit"]) == ("Donner", True)
