"""Weather Underground / The Weather Company daily 5-day forecast. Optional (WU_API_KEY).

A PWS-contributor key only grants the *daily* 5-day product, so this is used as a
day-level signal ("WU expects snow"), never spread across hourly snowfall.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx
from pydantic import SecretStr

from passcheck.corridors import P
from passcheck.domain import DayHint
from passcheck.sources.base import HintResult, SourceKind, SourceResult, get_bytes

URL = "https://api.weather.com/v3/wx/forecast/daily/5day"
SUMMITS: tuple[str, ...] = ("donner", "spooner", "echo", "carson_pass")


def parse_daily(point_id: str, doc: dict[str, Any]) -> list[DayHint]:
    out: list[DayHint] = []
    times: list[str] = doc.get("validTimeLocal", [])
    snows: list[float | None] = doc.get("qpfSnow", [])
    for ts, snow in zip(times, snows, strict=False):
        if snow is None:
            continue
        try:
            day = date.fromisoformat(ts[:10])
        except ValueError:
            continue
        out.append(DayHint(point_id, day, float(snow)))
    return out


@dataclass(frozen=True, slots=True)
class WuDailyForecast:
    api_key: SecretStr | None
    name: str = "wu"
    kind: SourceKind = "hint"
    interval_s: int = 3 * 3600

    @property
    def configured(self) -> bool:
        return self.api_key is not None and bool(self.api_key.get_secret_value())

    async def fetch(self, client: httpx.AsyncClient) -> bytes:
        assert self.api_key is not None
        docs: dict[str, Any] = {}
        for pid in SUMMITS:
            p = P[pid]
            raw = await get_bytes(
                client,
                self.name,
                URL,
                {
                    "geocode": f"{p.lat:.4f},{p.lon:.4f}",
                    "format": "json",
                    "units": "e",
                    "language": "en-US",
                    "apiKey": self.api_key.get_secret_value(),
                },
            )
            docs[pid] = json.loads(raw)
        return json.dumps(docs).encode()

    def parse(self, raw: bytes, now: datetime) -> SourceResult:
        docs: dict[str, dict[str, Any]] = json.loads(raw)
        return HintResult([h for pid, d in docs.items() if pid in P for h in parse_daily(pid, d)])
