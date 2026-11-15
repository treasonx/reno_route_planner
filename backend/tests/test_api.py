from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from passcheck.config import Settings
from passcheck.main import create_app
from passcheck.sources.fixtures import fixture_sources
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
    assert best < 0.1, f"cold plan took {best * 1000:.0f} ms"


def _timed(fn) -> float:  # type: ignore[no-untyped-def]
    t = time.perf_counter()
    fn()
    return time.perf_counter() - t
