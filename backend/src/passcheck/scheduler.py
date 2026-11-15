"""Background refresh: one loop per source, each fully isolated from the others."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from datetime import datetime

import httpx

from passcheck.sources.base import ForecastResult, HintResult, LiveResult, Source
from passcheck.store import Store, describe_error

log = logging.getLogger("passcheck.scheduler")

Clock = Callable[[], datetime]
RETRY_DELAY_S = 60
PARSE_IN_THREAD_BYTES = 200_000


def _count(result: ForecastResult | LiveResult | HintResult) -> int:
    match result:
        case ForecastResult(series=s):
            return sum(len(v) for v in s.values())
        case LiveResult(observations=o):
            return len(o)
        case HintResult(hints=h):
            return len(h)


async def refresh_once(
    source: Source, store: Store, client: httpx.AsyncClient, clock: Clock
) -> bool:
    started = time.monotonic()
    try:
        raw = await source.fetch(client)
        now = clock()
        if len(raw) > PARSE_IN_THREAD_BYTES:
            result = await asyncio.to_thread(source.parse, raw, now)
        else:
            result = source.parse(raw, now)
    except Exception as exc:
        store.record_failure(source.name, exc)
        log.warning("fetch source=%s ok=false error=%r", source.name, describe_error(exc))
        return False
    store.record_success(source.name, result, clock())
    log.info(
        "fetch source=%s ok=true items=%d ms=%d",
        source.name,
        _count(result),
        int((time.monotonic() - started) * 1000),
    )
    return True


async def run_source(
    source: Source, store: Store, client: httpx.AsyncClient, clock: Clock, delay_s: float
) -> None:
    await asyncio.sleep(delay_s)
    while True:
        ok = await refresh_once(source, store, client, clock)
        await asyncio.sleep(source.interval_s if ok else min(RETRY_DELAY_S, source.interval_s))


def start(
    sources: Sequence[Source], store: Store, client: httpx.AsyncClient, clock: Clock
) -> list[asyncio.Task[None]]:
    return [
        asyncio.create_task(
            run_source(s, store, client, clock, delay_s=i * 2), name=f"src-{s.name}"
        )
        for i, s in enumerate(sources)
        if s.configured
    ]
