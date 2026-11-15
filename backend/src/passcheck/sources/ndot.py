"""Nevada DOT (nvroads 511) road conditions. Optional: needs NDOT_API_KEY.

Status is free text ("Chains Required…", "Holding Traffic", "Closed"), mapped
conservatively to chain levels.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import SecretStr

from passcheck.domain import ChainLevel, LiveObservation, LiveSourceName, RouteId, sanitize
from passcheck.sources.base import LiveResult, SourceKind, SourceResult, get_bytes

URL = "https://www.nvroads.com/api/v3/get/roadconditions"
ROUTE_PATTERNS: tuple[tuple[re.Pattern[str], RouteId], ...] = (
    (re.compile(r"\b(I|IR)[-\s]?80\b", re.I), RouteId.I80),
    (re.compile(r"\bUS[-\s]?50\b", re.I), RouteId.US50),
    (re.compile(r"\b(SR|NV)[-\s]?88\b", re.I), RouteId.SR88),
)


def decode_polyline(encoded: str) -> list[tuple[float, float]]:
    """Decode a Google encoded polyline into (lat, lon) pairs."""
    coords: list[tuple[float, float]] = []
    index = lat = lon = 0
    while index < len(encoded):
        deltas: list[int] = []
        for _ in range(2):
            shift = result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lon += deltas[1]
        coords.append((lat / 1e5, lon / 1e5))
    return coords


def classify(status: str) -> tuple[ChainLevel, bool, bool]:
    s = status.lower()
    if "closed" in s:
        return ChainLevel.R0, True, False
    if "chains required" in s:
        return ChainLevel.R2, False, False
    if "chain" in s or "traction" in s:
        return ChainLevel.R1, False, False
    if "holding" in s or "snow" in s or "ice" in s or "icy" in s:
        return ChainLevel.R0, False, True
    return ChainLevel.R0, False, False


def parse_conditions(items: list[dict[str, Any]], now: datetime) -> list[LiveObservation]:
    out: list[LiveObservation] = []
    for item in items:
        roadway = str(item.get("RoadwayName", ""))
        route = next((r for pat, r in ROUTE_PATTERNS if pat.search(roadway)), None)
        if route is None:
            continue
        try:
            pts = decode_polyline(str(item.get("EncodedPolyline", "")))
        except (IndexError, ValueError):
            pts = []
        if not pts:
            continue
        lat, lon = pts[len(pts) // 2]
        status = str(item.get("Overall Status", ""))
        chain, closed, caution = classify(status)
        try:
            observed = datetime.fromtimestamp(int(item["LastUpdated"]), tz=UTC)
        except (KeyError, TypeError, ValueError):
            observed = now
        out.append(
            LiveObservation(
                source=LiveSourceName.NDOT,
                route=route,
                lat=lat,
                lon=lon,
                chain=chain,
                closed=closed,
                caution=caution,
                description=sanitize(status) or "Road conditions reported",
                place=sanitize(str(item.get("LocationDescription", roadway)), 60),
                observed_at=observed,
            )
        )
    return out


@dataclass(frozen=True, slots=True)
class NdotRoadConditions:
    api_key: SecretStr | None
    name: str = LiveSourceName.NDOT.value
    kind: SourceKind = "live"
    interval_s: int = 300

    @property
    def configured(self) -> bool:
        return self.api_key is not None and bool(self.api_key.get_secret_value())

    async def fetch(self, client: httpx.AsyncClient) -> bytes:
        assert self.api_key is not None
        return await get_bytes(
            client, self.name, URL, {"key": self.api_key.get_secret_value(), "format": "json"}
        )

    def parse(self, raw: bytes, now: datetime) -> SourceResult:
        items: list[dict[str, Any]] = json.loads(raw)
        return LiveResult(LiveSourceName.NDOT, parse_conditions(items, now))
