"""Caltrans CWWP2 chain controls (no key). D3 covers I-80 and US-50; D10 covers SR-88."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from passcheck.domain import (
    PACIFIC,
    ChainLevel,
    LiveObservation,
    LiveSourceName,
    RouteId,
    sanitize,
)
from passcheck.sources.base import LiveResult, SourceKind, SourceResult, get_bytes

URLS = (
    "https://cwwp2.dot.ca.gov/data/d3/cc/ccStatusD03.json",
    "https://cwwp2.dot.ca.gov/data/d10/cc/ccStatusD10.json",
)
ROUTES = {"I-80": RouteId.I80, "US-50": RouteId.US50, "SR-88": RouteId.SR88}
CHAIN_RE = re.compile(r"^R-?([0-3])$")


def _timestamp(ts: dict[str, Any] | None, fallback: datetime) -> datetime:
    try:
        assert ts is not None
        local = datetime.fromisoformat(f"{ts['statusDate']}T{ts['statusTime']}")
        return local.replace(tzinfo=PACIFIC).astimezone(UTC)
    except (AssertionError, KeyError, TypeError, ValueError):
        return fallback


def parse_cc(doc: dict[str, Any], now: datetime) -> list[LiveObservation]:
    out: list[LiveObservation] = []
    for item in doc.get("data", []):
        cc = item.get("cc", {})
        loc = cc.get("location", {})
        route = ROUTES.get(str(loc.get("route", "")))
        if route is None or str(cc.get("inService", "true")).lower() != "true":
            continue
        status_data = cc.get("statusData", {})
        status = str(status_data.get("status", "")).strip().upper()
        chain, closed, caution = ChainLevel.R0, False, False
        if m := CHAIN_RE.match(status):
            chain = ChainLevel(int(m.group(1)))
        elif "CLOSED" in status:
            closed = True
        else:
            caution = True  # unknown status string: never treat as clear
        try:
            lat, lon = float(loc["latitude"]), float(loc["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        out.append(
            LiveObservation(
                source=LiveSourceName.CALTRANS,
                route=route,
                lat=lat,
                lon=lon,
                chain=chain,
                closed=closed,
                caution=caution,
                description=sanitize(str(status_data.get("statusDescription", status))),
                place=sanitize(str(loc.get("locationName", "")).title(), 60),
                observed_at=_timestamp(status_data.get("statusTimestamp"), now),
            )
        )
    return out


@dataclass(frozen=True, slots=True)
class CaltransChainControls:
    name: str = LiveSourceName.CALTRANS.value
    kind: SourceKind = "live"
    interval_s: int = 300
    configured: bool = True

    async def fetch(self, client: httpx.AsyncClient) -> bytes:
        docs = [await get_bytes(client, self.name, url) for url in URLS]
        return b"[" + b",".join(docs) + b"]"

    def parse(self, raw: bytes, now: datetime) -> SourceResult:
        # Any district failing to parse fails the whole source -> stale floor (conservative).
        docs: list[dict[str, Any]] = json.loads(raw)
        return LiveResult(LiveSourceName.CALTRANS, [o for d in docs for o in parse_cc(d, now)])
