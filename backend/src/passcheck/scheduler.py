"""Background refresh: one loop per source, each fully isolated from the others."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from datetime import datetime

import httpx

from passcheck.snapshot import SnapshotDir
from passcheck.sources.base import ForecastResult, HintResult, LiveResult, Source
from passcheck.store import Store, describe_error

log = logging.getLogger("passcheck.scheduler")

Clock = Callable[[], datetime]
RETRY_DELAY_S = 60
# While there is no data to serve at all (fresh start, no usable snapshot), retry quickly.
WARMUP_RETRY_S = 10
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
    source: Source,
    store: Store,
    client: httpx.AsyncClient,
    clock: Clock,
    snapshots: SnapshotDir | None = None,
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
    fetched_at = clock()
    store.record_success(source.name, result, fetched_at)
    if snapshots is not None and snapshots.enabled:
        await asyncio.to_thread(snapshots.save, source.name, raw, fetched_at)
    log.info(
        "fetch source=%s ok=true items=%d ms=%d",
        source.name,
        _count(result),
        int((time.monotonic() - started) * 1000),
    )
    return True


def next_delay(ok: bool, interval_s: int, has_data: bool) -> float:
    if ok:
        return interval_s
    return min(WARMUP_RETRY_S if not has_data else RETRY_DELAY_S, interval_s)


async def run_source(
    source: Source,
    store: Store,
    client: httpx.AsyncClient,
    clock: Clock,
    delay_s: float,
    snapshots: SnapshotDir | None = None,
) -> None:
    await asyncio.sleep(delay_s)
    while True:
        ok = await refresh_once(source, store, client, clock, snapshots)
        await asyncio.sleep(next_delay(ok, source.interval_s, store.conditions is not None))


def restore_snapshots(
    sources: Sequence[Source], store: Store, snapshots: SnapshotDir, clock: Clock
) -> list[str]:
    """Re-parse each source's last snapshot and load it with its original fetch time."""
    restored: list[str] = []
    for s in sources:
        if not s.configured:
            continue
        now = clock()
        snap = snapshots.load(s.name, now)
        if snap is None:
            continue
        try:
            result = s.parse(snap.raw, snap.fetched_at)
        except Exception as exc:
            log.warning("snapshot parse failed source=%s error=%s", s.name, type(exc).__name__)
            continue
        store.restore(s.name, result, snap.fetched_at, now)
        restored.append(s.name)
    return restored


def first_delay(source: Source, store: Store, now: datetime, stagger_s: float) -> float:
    """When to fetch first: if a restored snapshot is still within its refresh interval, wait
    out the rest of that interval instead of refetching on every restart."""
    last = store.states[source.name].last_success
    if last is None:
        return stagger_s
    remaining = source.interval_s - (now - last).total_seconds()
    return max(stagger_s, remaining)


def start(
    sources: Sequence[Source],
    store: Store,
    client: httpx.AsyncClient,
    clock: Clock,
    snapshots: SnapshotDir | None = None,
) -> list[asyncio.Task[None]]:
    # Forecasts first and immediately: nothing can be served until one has arrived.
    ordered = sorted((s for s in sources if s.configured), key=lambda s: s.kind != "forecast")
    now = clock()
    return [
        asyncio.create_task(
            run_source(
                s, store, client, clock, first_delay(s, store, now, i * 2), snapshots=snapshots
            ),
            name=f"src-{s.name}",
        )
        for i, s in enumerate(ordered)
    ]
