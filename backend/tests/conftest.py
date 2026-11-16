from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from passcheck.config import Settings
from passcheck.domain import HourlyPoint
from passcheck.main import create_app
from passcheck.scheduler import refresh_once
from passcheck.sources.fixtures import fixture_sources

FIXTURES = Path(__file__).parent / "fixtures"
# Sunday 2026-11-15 07:00 PST
NOW = datetime(2026, 11, 15, 15, 0, tzinfo=UTC)


def load_fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def load_json(name: str) -> Any:
    return json.loads(load_fixture(name))


def make_hour(**overrides: Any) -> HourlyPoint:
    """A benign GO hour; each test overrides only what it varies."""
    base: dict[str, Any] = {
        "point_id": "donner",
        "time": NOW,
        "local_hour": 12,
        "temp_f": 45.0,
        "dewpoint_f": 25.0,
        "snow_in": 0.0,
        "snow_prob_pct": 0,
        "freezing_rain": False,
        "precip_prev_12h_in": 0.0,
        "temp_max_prev_12h_f": 45.0,
        "snow_depth_in": 0.0,
        "freezing_level_ft": 9000.0,
    }
    base.update(overrides)
    return HourlyPoint(**base)


def build_fixture_app(
    now: datetime = NOW, static_dir: Path | None = None
) -> tuple[FastAPI, Callable[[], datetime]]:
    def clock() -> datetime:
        return now

    srcs = fixture_sources()
    settings = Settings(passcheck_sources="fixtures", static_dir=static_dir or Path("/nonexistent"))
    app = create_app(settings, sources=srcs, clock=clock, start_scheduler=False)

    async def load() -> None:
        async with httpx.AsyncClient() as client:
            for s in srcs:
                await refresh_once(s, app.state.store, client, clock)

    asyncio.run(load())
    return app, clock


@pytest.fixture
def fixture_app() -> FastAPI:
    app, _ = build_fixture_app()
    return app
