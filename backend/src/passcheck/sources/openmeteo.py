"""Open-Meteo hourly forecast for every sample point in one multi-location request.

Free for non-commercial use; data CC-BY 4.0 (attribution shown in the UI footer).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from passcheck.corridors import P
from passcheck.domain import RawHour
from passcheck.sources.base import ForecastResult, SourceKind, SourceResult, get_bytes

URL = "https://api.open-meteo.com/v1/forecast"
HOURLY = (
    "temperature_2m,dew_point_2m,snowfall,precipitation,precipitation_probability,"
    "weather_code,freezing_level_height,snow_depth"
)
POINT_IDS: tuple[str, ...] = tuple(P)


def params() -> dict[str, str]:
    pts = [P[i] for i in POINT_IDS]
    return {
        "latitude": ",".join(f"{p.lat:.4f}" for p in pts),
        "longitude": ",".join(f"{p.lon:.4f}" for p in pts),
        "elevation": ",".join(f"{p.elevation_ft * 0.3048:.0f}" for p in pts),
        "hourly": HOURLY,
        "past_days": "1",
        "forecast_days": "12",
        "timezone": "UTC",
        "temperature_unit": "fahrenheit",
        "precipitation_unit": "inch",
    }


def _to_inches(value: float, unit: str) -> float:
    return {"ft": value * 12, "m": value * 39.3701, "cm": value / 2.54}.get(unit, value)


def _to_feet(value: float, unit: str) -> float:
    return value / 0.3048 if unit == "m" else value


def parse_location(loc: dict[str, Any]) -> list[RawHour]:
    hourly: dict[str, list[Any]] = loc["hourly"]
    units: dict[str, str] = loc.get("hourly_units", {})
    out: list[RawHour] = []
    for i, ts in enumerate(hourly["time"]):
        try:
            row = {k: hourly[k][i] for k in hourly}
            if any(row[k] is None for k in ("temperature_2m", "dew_point_2m", "snowfall")):
                continue  # missing hour -> planner treats as "No forecast data" (CAUTION)
            out.append(
                RawHour(
                    time=datetime.fromisoformat(ts).replace(tzinfo=UTC),
                    temp_f=float(row["temperature_2m"]),
                    dewpoint_f=float(row["dew_point_2m"]),
                    snow_in=float(row["snowfall"]),
                    precip_in=float(row.get("precipitation") or 0.0),
                    precip_prob_pct=int(row.get("precipitation_probability") or 0),
                    weather_code=int(row.get("weather_code") or 0),
                    freezing_level_ft=_to_feet(
                        float(row.get("freezing_level_height") or 99999.0),
                        units.get("freezing_level_height", "m"),
                    ),
                    snow_depth_in=_to_inches(
                        float(row.get("snow_depth") or 0.0), units.get("snow_depth", "m")
                    ),
                )
            )
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return out


def parse_forecast(
    doc: list[dict[str, Any]] | dict[str, Any], point_ids: tuple[str, ...]
) -> dict[str, list[RawHour]]:
    locations = doc if isinstance(doc, list) else [doc]
    if len(locations) != len(point_ids):
        raise ValueError("open-meteo returned an unexpected number of locations")
    return {pid: parse_location(loc) for pid, loc in zip(point_ids, locations, strict=True)}


@dataclass(frozen=True, slots=True)
class OpenMeteoForecast:
    name: str = "openmeteo"
    kind: SourceKind = "forecast"
    interval_s: int = 3600
    configured: bool = True

    async def fetch(self, client: httpx.AsyncClient) -> bytes:
        return await get_bytes(client, self.name, URL, params())

    def parse(self, raw: bytes, now: datetime) -> SourceResult:
        return ForecastResult(parse_forecast(json.loads(raw), POINT_IDS))
