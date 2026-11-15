"""Source protocol: ``fetch`` does I/O, ``parse`` is pure and tested on fixture bytes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

import httpx

from passcheck.domain import DayHint, LiveObservation, LiveSourceName, RawHour

MAX_RESPONSE_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ForecastResult:
    series: dict[str, list[RawHour]]


@dataclass(frozen=True, slots=True)
class LiveResult:
    source: LiveSourceName
    observations: list[LiveObservation]


@dataclass(frozen=True, slots=True)
class HintResult:
    hints: list[DayHint]


type SourceResult = ForecastResult | LiveResult | HintResult
type SourceKind = Literal["live", "forecast", "hint"]


class Source(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def kind(self) -> SourceKind: ...
    @property
    def interval_s(self) -> int: ...
    @property
    def configured(self) -> bool: ...

    async def fetch(self, client: httpx.AsyncClient) -> bytes: ...

    def parse(self, raw: bytes, now: datetime) -> SourceResult: ...


class UpstreamError(Exception):
    """Raised for non-2xx or oversized upstream responses. Never carries the URL."""

    def __init__(self, source: str, status: int | None, reason: str) -> None:
        super().__init__(f"{source}: {reason} ({status})")
        self.source = source
        self.status = status
        self.reason = reason


async def get_bytes(
    client: httpx.AsyncClient, source: str, url: str, params: dict[str, str] | None = None
) -> bytes:
    """GET with a size cap. Errors are re-raised without the URL (it may contain a key)."""
    try:
        async with client.stream("GET", url, params=params) as resp:
            if resp.status_code != 200:
                raise UpstreamError(source, resp.status_code, "bad status")
            chunks: list[bytes] = []
            size = 0
            async for chunk in resp.aiter_bytes():
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise UpstreamError(source, resp.status_code, "response too large")
                chunks.append(chunk)
            return b"".join(chunks)
    except httpx.HTTPError as exc:
        raise UpstreamError(source, None, type(exc).__name__) from None
