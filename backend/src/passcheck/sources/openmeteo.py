"""Open-Meteo hourly forecast for every sample point in one multi-location request.

Free for non-commercial use; data CC-BY 4.0 (attribution shown in the UI footer).
"""

from __future__ import annotations

import json
import math
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


REQUIRED = ("temperature_2m", "dew_point_2m", "snowfall")


def _num(row: dict[str, Any], key: str, default: float) -> float:
    """Value for ``key``; ``default`` only when absent/null (a real 0 is kept)."""
    value = row.get(key)
    return default if value is None else float(value)


def parse_location(loc: dict[str, Any]) -> list[RawHour]:
    hourly: dict[str, list[Any]] = loc["hourly"]
    units: dict[str, str] = loc.get("hourly_units", {})
    out: list[RawHour] = []
    for i, ts in enumerate(hourly["time"]):
        try:
            row = {k: hourly[k][i] for k in hourly}
            if any(row[k] is None for k in REQUIRED):
                continue  # missing hour -> planner treats as "No forecast data" (CAUTION)
            values = {
                "temp_f": float(row["temperature_2m"]),
                "dewpoint_f": float(row["dew_point_2m"]),
                "snow_in": float(row["snowfall"]),
                "precip_in": _num(row, "precipitation", 0.0),
                "precip_prob": _num(row, "precipitation_probability", 0.0),
                "weather_code": _num(row, "weather_code", 0.0),
                "freezing_level": _num(row, "freezing_level_height", 99999.0),
                "snow_depth": _num(row, "snow_depth", 0.0),
            }
            if not all(math.isfinite(v) for v in values.values()):
                # NaN/Infinity compare False against every threshold (fail-open), so the
                # hour is dropped and becomes "No forecast data" (CAUTION) instead.
                continue
            out.append(
                RawHour(
                    time=datetime.fromisoformat(ts).replace(tzinfo=UTC),
                    temp_f=values["temp_f"],
                    dewpoint_f=values["dewpoint_f"],
                    snow_in=values["snow_in"],
                    precip_in=values["precip_in"],
                    precip_prob_pct=int(values["precip_prob"]),
                    weather_code=int(values["weather_code"]),
                    freezing_level_ft=_to_feet(
                        values["freezing_level"], units.get("freezing_level_height", "m")
                    ),
                    snow_depth_in=_to_inches(values["snow_depth"], units.get("snow_depth", "m")),
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
