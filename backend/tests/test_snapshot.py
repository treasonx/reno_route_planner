from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from passcheck.config import Settings
from passcheck.domain import Level, LiveSourceName
from passcheck.main import create_app
from passcheck.scheduler import WARMUP_RETRY_S, next_delay, refresh_once, restore_snapshots
from passcheck.snapshot import MAX_RESTORE_AGE, SnapshotDir
from passcheck.sources.caltrans import URLS as CALTRANS_URLS
from passcheck.sources.caltrans import CaltransChainControls
from passcheck.sources.openmeteo import POINT_IDS, OpenMeteoForecast
from passcheck.sources.openmeteo import URL as OPENMETEO_URL
from passcheck.store import Store
from tests.conftest import NOW, load_fixture, load_json


def openmeteo_bytes() -> bytes:
    """A valid multi-location response covering every sample point, around NOW."""
    loc = load_json("openmeteo.json")[0]
    hourly = loc["hourly"]
    n = 72
    start = NOW.replace(tzinfo=None) - timedelta(hours=24)
    hourly["time"] = [(start + timedelta(hours=k)).strftime("%Y-%m-%dT%H:%M") for k in range(n)]
    for key, values in hourly.items():
        if key != "time":
            hourly[key] = [values[k % len(values)] for k in range(n)]
    return json.dumps([loc] * len(POINT_IDS)).encode()


def caltrans_bytes() -> bytes:
    return (
        b"["
        + load_fixture("caltrans_cc_d03.json")
        + b","
        + load_fixture("caltrans_cc_d10.json")
        + b"]"
    )


# --- SnapshotDir -----------------------------------------------------------------------------


def test_round_trip_and_atomic_overwrite(tmp_path: Path) -> None:
    snaps = SnapshotDir(tmp_path)
    snaps.save("openmeteo", b"first", NOW - timedelta(hours=1))
    snaps.save("openmeteo", b"second", NOW)
    snap = snaps.load("openmeteo", NOW)
    assert snap is not None
    assert snap.raw == b"second"
    assert snap.fetched_at == NOW
    assert sorted(p.name for p in tmp_path.iterdir()) == ["openmeteo.bin", "openmeteo.json"]


@pytest.mark.parametrize(
    ("age", "usable"),
    [
        (timedelta(0), True),
        (MAX_RESTORE_AGE, True),
        (MAX_RESTORE_AGE + timedelta(seconds=1), False),
        (timedelta(minutes=-5), False),
    ],
    ids=["fresh", "at-limit", "too-old", "from-the-future"],
)
def test_age_limits(tmp_path: Path, age: timedelta, usable: bool) -> None:
    snaps = SnapshotDir(tmp_path)
    snaps.save("caltrans", b"x", NOW - age)
    assert (snaps.load("caltrans", NOW) is not None) is usable


@pytest.mark.parametrize(
    "corrupt",
    ["bad-json", "size-mismatch", "wrong-schema", "missing-data"],
)
def test_corrupt_snapshots_are_ignored(tmp_path: Path, corrupt: str) -> None:
    snaps = SnapshotDir(tmp_path)
    snaps.save("caltrans", b"payload", NOW)
    meta, data = tmp_path / "caltrans.json", tmp_path / "caltrans.bin"
    if corrupt == "bad-json":
        meta.write_text("{nope")
    elif corrupt == "size-mismatch":
        data.write_bytes(b"truncated")
    elif corrupt == "wrong-schema":
        meta.write_text(json.dumps({**json.loads(meta.read_text()), "schema": 99}))
    else:
        data.unlink()
    assert snaps.load("caltrans", NOW) is None


def test_unwritable_dir_disables_snapshots(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("not a directory")
    snaps = SnapshotDir(blocker / "data")
    assert not snaps.enabled
    snaps.save("caltrans", b"x", NOW)  # no-op, no exception
    assert snaps.load("caltrans", NOW) is None


def test_names_cannot_escape_the_directory(tmp_path: Path) -> None:
    snaps = SnapshotDir(tmp_path)
    snaps.save("../evil", b"x", NOW)
    assert not (tmp_path.parent / "evil.bin").exists()


# --- restore into the store ------------------------------------------------------------------


def test_restore_uses_original_fetch_time(tmp_path: Path) -> None:
    snaps = SnapshotDir(tmp_path)
    fetched = NOW - timedelta(minutes=10)
    snaps.save("openmeteo", openmeteo_bytes(), fetched)
    snaps.save("caltrans", caltrans_bytes(), fetched)
    srcs = [CaltransChainControls(), OpenMeteoForecast()]
    store = Store(srcs)

    assert restore_snapshots(srcs, store, snaps, lambda: NOW) == ["caltrans", "openmeteo"]
    assert store.conditions is not None
    assert store.states["openmeteo"].last_success == fetched
    assert store.live_floor(NOW)[LiveSourceName.CALTRANS] is False  # 10 min old: still fresh
    # Once the restored live data passes the live window, the CAUTION floor applies.
    assert store.live_floor(NOW + timedelta(minutes=25))[LiveSourceName.CALTRANS] is True


def test_restored_stale_forecast_is_never_go(tmp_path: Path) -> None:
    snaps = SnapshotDir(tmp_path)
    snaps.save("openmeteo", openmeteo_bytes(), NOW - timedelta(hours=7))
    srcs = [OpenMeteoForecast()]
    store = Store(srcs)
    restore_snapshots(srcs, store, snaps, lambda: NOW)
    assert store.forecast_stale(NOW)

    app = create_app(
        Settings(data_dir=tmp_path, static_dir=Path("/nonexistent")),
        sources=srcs,
        clock=lambda: NOW,
        start_scheduler=False,
    )
    with TestClient(app) as client:
        body = client.get("/api/plan").json()
    assert body["stale"] is True
    verdicts = {r["verdict"] for h in body["hours"] for r in h["routes"].values()}
    assert Level.GO.value not in verdicts


def test_app_serves_restored_data_immediately(tmp_path: Path) -> None:
    snaps = SnapshotDir(tmp_path)
    snaps.save("openmeteo", openmeteo_bytes(), NOW - timedelta(minutes=5))
    snaps.save("caltrans", caltrans_bytes(), NOW - timedelta(minutes=5))
    app = create_app(
        Settings(data_dir=tmp_path, static_dir=Path("/nonexistent")),
        sources=[CaltransChainControls(), OpenMeteoForecast()],
        clock=lambda: NOW,
        start_scheduler=False,
    )
    with TestClient(app) as client:  # runs lifespan -> restore
        r = client.get("/api/plan")
    assert r.status_code == 200
    assert r.json()["stale"] is False


def test_unparseable_snapshot_is_skipped(tmp_path: Path) -> None:
    snaps = SnapshotDir(tmp_path)
    snaps.save("openmeteo", b"not json", NOW)
    srcs = [OpenMeteoForecast()]
    store = Store(srcs)
    assert restore_snapshots(srcs, store, snaps, lambda: NOW) == []
    assert store.conditions is None


def test_successful_fetch_writes_a_snapshot(tmp_path: Path) -> None:
    snaps = SnapshotDir(tmp_path)
    src = CaltransChainControls()
    store = Store([src])

    async def go() -> bool:
        with respx.mock:
            for url, name in zip(
                CALTRANS_URLS, ("caltrans_cc_d03.json", "caltrans_cc_d10.json"), strict=True
            ):
                respx.get(url).mock(return_value=httpx.Response(200, content=load_fixture(name)))
            async with httpx.AsyncClient() as client:
                return await refresh_once(src, store, client, lambda: NOW, snaps)

    assert asyncio.run(go()) is True
    snap = snaps.load("caltrans", NOW)
    assert snap is not None
    assert snap.fetched_at == NOW


def test_failed_fetch_keeps_previous_snapshot(tmp_path: Path) -> None:
    snaps = SnapshotDir(tmp_path)
    snaps.save("openmeteo", b"previous", NOW - timedelta(minutes=30))
    src = OpenMeteoForecast()
    store = Store([src])

    async def go() -> bool:
        with respx.mock:
            respx.get(url__startswith=OPENMETEO_URL).mock(return_value=httpx.Response(500))
            async with httpx.AsyncClient() as client:
                return await refresh_once(src, store, client, lambda: NOW, snaps)

    assert asyncio.run(go()) is False
    snap = snaps.load("openmeteo", NOW)
    assert snap is not None
    assert snap.raw == b"previous"


# --- warm-up behaviour -----------------------------------------------------------------------


def test_retry_is_fast_only_while_there_is_no_data() -> None:
    assert next_delay(ok=False, interval_s=3600, has_data=False) == WARMUP_RETRY_S
    assert next_delay(ok=False, interval_s=3600, has_data=True) == 60
    assert next_delay(ok=True, interval_s=3600, has_data=False) == 3600


def test_restart_waits_out_the_interval_of_a_fresh_snapshot(tmp_path: Path) -> None:
    from passcheck.scheduler import first_delay

    src = OpenMeteoForecast()  # hourly
    store = Store([src])
    assert first_delay(src, store, NOW, stagger_s=0) == 0  # nothing restored: fetch now

    store.restore(src.name, src.parse(openmeteo_bytes(), NOW), NOW - timedelta(minutes=20), NOW)
    assert first_delay(src, store, NOW, stagger_s=0) == 40 * 60  # fetched 20 min ago

    store.restore(src.name, src.parse(openmeteo_bytes(), NOW), NOW - timedelta(hours=2), NOW)
    assert first_delay(src, store, NOW, stagger_s=0) == 0  # overdue: fetch now
