from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import httpx
import pytest
import respx
from pydantic import SecretStr

from passcheck.domain import LiveSourceName
from passcheck.scheduler import refresh_once
from passcheck.security import RedactingFilter, configure_logging, redact
from passcheck.sources.fixtures import FixtureCaltrans, FixtureForecast
from passcheck.sources.ndot import NdotRoadConditions
from passcheck.sources.wu import WuDailyForecast
from passcheck.store import Store
from tests.conftest import NOW

SENTINEL = "SENTINEL-KEY-8f3a9c"


def run(coro):  # type: ignore[no-untyped-def]
    return asyncio.run(coro)


def test_failure_is_isolated_and_redacted() -> None:
    src = NdotRoadConditions(SecretStr(SENTINEL))
    store = Store([FixtureForecast(), src])

    async def go() -> bool:
        with respx.mock:
            respx.get(url__startswith="https://www.nvroads.com/").mock(
                return_value=httpx.Response(500)
            )
            async with httpx.AsyncClient() as client:
                await refresh_once(FixtureForecast(), store, client, lambda: NOW)
                return await refresh_once(src, store, client, lambda: NOW)

    assert run(go()) is False
    st = store.states["ndot"]
    assert st.consecutive_failures == 1
    assert st.last_error == "bad status (500)"
    assert SENTINEL not in (st.last_error or "")
    assert store.conditions is not None  # forecast still served


def test_network_error_message_has_no_url() -> None:
    src = WuDailyForecast(SecretStr(SENTINEL))
    store = Store([src])

    async def go() -> None:
        with respx.mock:
            respx.get(url__startswith="https://api.weather.com/").mock(
                side_effect=httpx.ConnectError("boom")
            )
            async with httpx.AsyncClient() as client:
                await refresh_once(src, store, client, lambda: NOW)

    run(go())
    assert store.states["wu"].last_error == "ConnectError"


def test_sentinel_key_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    configure_logging("DEBUG")
    caplog.handler.addFilter(RedactingFilter())
    src = WuDailyForecast(SecretStr(SENTINEL))
    store = Store([src])

    async def go() -> None:
        with respx.mock:
            respx.get(url__startswith="https://api.weather.com/").mock(
                return_value=httpx.Response(401)
            )
            async with httpx.AsyncClient() as client:
                await refresh_once(src, store, client, lambda: NOW)

    with caplog.at_level(logging.DEBUG):
        run(go())
        logging.getLogger("x").info("GET https://api.weather.com/x?geocode=1,2&apiKey=%s", SENTINEL)
    assert SENTINEL not in caplog.text
    assert "apiKey=REDACTED" in caplog.text
    assert SENTINEL not in repr(src)


def test_redact() -> None:
    assert redact("a?key=abc&b=1 apiKey=xyz") == "a?key=REDACTED&b=1 apiKey=REDACTED"


def test_live_floor_and_forecast_staleness() -> None:
    store = Store([FixtureForecast(), FixtureCaltrans(), NdotRoadConditions(None)])
    assert store.live_floor(NOW) == {LiveSourceName.CALTRANS: True, LiveSourceName.NDOT: False}
    assert store.forecast_stale(NOW)

    async def go() -> None:
        async with httpx.AsyncClient() as client:
            for s in (FixtureForecast(), FixtureCaltrans()):
                await refresh_once(s, store, client, lambda: NOW)

    run(go())
    assert store.live_floor(NOW) == {LiveSourceName.CALTRANS: False, LiveSourceName.NDOT: False}
    later = NOW + timedelta(minutes=31)
    assert store.live_floor(later)[LiveSourceName.CALTRANS] is True
    assert not store.forecast_stale(NOW + timedelta(hours=5))
    assert store.forecast_stale(NOW + timedelta(hours=7))


def test_snapshot_version_increments_and_clears_cache() -> None:
    store = Store([FixtureForecast()])

    async def go() -> None:
        async with httpx.AsyncClient() as client:
            await refresh_once(FixtureForecast(), store, client, lambda: NOW)
            store.put("k", (b"x", "e"))
            await refresh_once(FixtureForecast(), store, client, lambda: NOW)

    run(go())
    assert store.conditions is not None
    assert store.conditions.version == 2
    assert store.cached("k") is None
