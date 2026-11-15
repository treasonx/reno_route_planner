"""Nevada DOT (nvroads 511) road conditions. Optional: needs NDOT_API_KEY.

Status is free text ("Chains Required…", "Holding Traffic", "Closed"), mapped
conservatively to chain levels; unrecognised text is CAUTION, never clear.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import SecretStr

from passcheck.domain import ChainLevel, LiveObservation, LiveSourceName, RouteId, sanitize
from passcheck.sources.base import (
    LiveResult,
    SourceKind,
    SourceResult,
    UpstreamError,
    get_bytes,
)

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


# Negated / all-clear phrases are stripped *before* hazard matching so "No Chain Controls",
# "Chain controls lifted" or "Reopened, previously closed" never read as chains / closed.
_NEGATIONS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\bno\s+(?:chains?|chain\s+controls?|restrictions?|closures?|delays?)"
        r"(?:\s+(?:controls?|required|in\s+effect))*\b"
    ),
    re.compile(
        r"\b(?:chains?|traction)(?:\s+(?:controls?|restrictions?|requirements?|laws?))?"
        r"\s+(?:(?:have|has|are|is|were|was)\s+(?:been\s+)?)?"
        r"(?:lifted|removed|cancell?ed|not\s+(?:in\s+effect|required))\b"
    ),
    re.compile(r"\b(?:re-?opened|re-?opens?|re-?opening)\b"),
    re.compile(r"\bpreviously\s+closed\b"),
    re.compile(r"\b(?:lifted|not\s+in\s+effect)\b"),
)
_CLOSED = re.compile(r"\bclosed\b")
_CHAIN_CODE = re.compile(r"\br-?([1-3])\b")
_CHAINS_REQUIRED = re.compile(r"\bchains?\s+(?:are\s+)?required\b")
_CHAINS_OR_TRACTION = re.compile(r"\b(?:chains?|traction|snow\s+tires?)\b")
_HAZARD = re.compile(r"\b(?:holding|snow(?:y|ing)?|ice|icy|slick|slush(?:y)?|black\s+ice)\b")
_CLEAR = re.compile(r"\b(?:dry|clear|normal|open|good)\b")


def classify(status: str) -> tuple[ChainLevel, bool, bool]:
    """Map NDOT free text to ``(chain, closed, caution)``.

    Order: negations are removed first, then hazards are matched on word boundaries
    ("device" is not "ice"). Text that is neither a known hazard nor a known all-clear
    yields CAUTION -- the same never-treat-unknown-as-clear policy as Caltrans.
    """
    s = " ".join(status.lower().split())
    if not s:
        return ChainLevel.R0, False, False
    negated = False
    for pat in _NEGATIONS:
        s, n = pat.subn(" ", s)
        negated = negated or n > 0
    if _CLOSED.search(s):
        return ChainLevel.R0, True, False
    if m := _CHAIN_CODE.search(s):
        return ChainLevel(int(m.group(1))), False, False
    if _CHAINS_REQUIRED.search(s):
        return ChainLevel.R2, False, False
    if _CHAINS_OR_TRACTION.search(s):
        return ChainLevel.R1, False, False
    if _HAZARD.search(s):
        return ChainLevel.R0, False, True
    if negated or _CLEAR.search(s):
        return ChainLevel.R0, False, False
    return ChainLevel.R0, False, True  # unknown text: never treat as clear


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
        if not (math.isfinite(lat) and math.isfinite(lon)):
            continue
        status = str(item.get("Overall Status", ""))
        chain, closed, caution = classify(status)
        try:
            observed = datetime.fromtimestamp(int(item["LastUpdated"]), tz=UTC)
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
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
        if self.api_key is None:
            raise UpstreamError(self.name, None, "not configured")
        return await get_bytes(
            client, self.name, URL, {"key": self.api_key.get_secret_value(), "format": "json"}
        )

    def parse(self, raw: bytes, now: datetime) -> SourceResult:
        items: list[dict[str, Any]] = json.loads(raw)
        return LiveResult(LiveSourceName.NDOT, parse_conditions(items, now))
