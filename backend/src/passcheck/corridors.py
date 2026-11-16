"""Route corridors: sample points, travel offsets and profile geometry.

Defined once for Reno -> Sacramento; Sacramento -> Reno is derived at import
(reversed points, ``total - offset`` travel minutes), so the planner never
branches on direction.
"""

from __future__ import annotations

from dataclasses import dataclass

from passcheck.domain import Direction, LiveSourceName, RouteId


@dataclass(frozen=True, slots=True)
class Point:
    id: str
    name: str
    lat: float
    lon: float
    elevation_ft: int
    state: str  # "CA" | "NV"
    live_source: LiveSourceName
    peak_name: str = ""  # short summit name; non-empty only for signed summits
    short_name: str = ""  # narrow-column label; empty means ``name`` is already short

    @property
    def short_label(self) -> str:
        return self.short_name or self.name

    @property
    def peak_label(self) -> str:
        """Profile label, derived from ``elevation_ft`` so the two can never disagree."""
        return f"{self.peak_name} {self.elevation_ft:,}′" if self.peak_name else ""


@dataclass(frozen=True, slots=True)
class Stop:
    point: Point
    minutes: int  # typical minutes from the origin
    x: float  # SVG profile coordinates (viewBox 0 0 358 150)
    y: float


@dataclass(frozen=True, slots=True)
class Corridor:
    route: RouteId
    name: str
    summit_id: str
    stops: tuple[Stop, ...]
    towns: tuple[str, ...]

    @property
    def summit(self) -> Stop:
        return next(s for s in self.stops if s.point.id == self.summit_id)

    @property
    def segments(self) -> tuple[tuple[Stop, Stop], ...]:
        return tuple(zip(self.stops, self.stops[1:], strict=False))


CT = LiveSourceName.CALTRANS
NV = LiveSourceName.NDOT

P: dict[str, Point] = {
    p.id: p
    for p in [
        Point("reno", "Reno", 39.5296, -119.8138, 4505, "NV", NV),
        Point("sacramento", "Sacramento", 38.5816, -121.4944, 30, "CA", CT, short_name="Sac"),
        # I-80
        Point("truckee", "Truckee", 39.3280, -120.1833, 5820, "CA", CT),
        # Summit elevations are the posted (signed) summit heights; they are what Open-Meteo
        # downscales to and what the profile label shows.
        Point(
            "donner",
            "Donner Summit",
            39.3392,
            -120.3481,
            7056,
            "CA",
            CT,
            "Donner Summit",
            short_name="Donner",
        ),
        Point("kingvale", "Kingvale", 39.3142, -120.4461, 6076, "CA", CT),
        Point("yuba_gap", "Yuba Gap", 39.3168, -120.6145, 5770, "CA", CT),
        Point("colfax", "Colfax", 39.0967, -120.9494, 2421, "CA", CT),
        # US-50
        Point(
            "carson_city", "Carson City", 39.1638, -119.7674, 4688, "NV", NV, short_name="Carson"
        ),
        Point(
            "spooner",
            "Spooner Summit",
            39.1036,
            -119.8964,
            7146,
            "NV",
            NV,
            "Spooner",
            short_name="Spooner",
        ),
        Point(
            "south_lake_tahoe",
            "South Lake Tahoe",
            38.9399,
            -119.9772,
            6270,
            "CA",
            CT,
            short_name="Tahoe",
        ),
        Point("meyers", "Meyers", 38.8495, -120.0255, 6341, "CA", CT),
        Point(
            "echo",
            "Echo Summit",
            38.8131,
            -120.0297,
            7382,
            "CA",
            CT,
            "Echo Summit",
            short_name="Echo",
        ),
        Point(
            "twin_bridges",
            "Twin Bridges",
            38.8114,
            -120.1228,
            6158,
            "CA",
            CT,
            short_name="Twin Br.",
        ),
        Point("kyburz", "Kyburz", 38.7741, -120.2963, 4075, "CA", CT),
        Point(
            "placerville", "Placerville", 38.7296, -120.7985, 1863, "CA", CT, short_name="Placer."
        ),
        # SR-88
        Point("minden", "Minden", 38.9541, -119.7655, 4727, "NV", NV),
        Point("woodfords", "Woodfords", 38.7799, -119.8187, 5535, "CA", CT, short_name="Woodf."),
        Point(
            "carson_pass",
            "Carson Pass",
            38.6946,
            -119.9890,
            8574,
            "CA",
            CT,
            "Carson Pass",
            short_name="Carson P.",
        ),
        Point("kirkwood", "Kirkwood", 38.7027, -120.0715, 7723, "CA", CT),
        Point("carson_spur", "Carson Spur", 38.7056, -120.1090, 7972, "CA", CT, short_name="Spur"),
        Point("jackson", "Jackson", 38.3488, -120.7741, 1223, "CA", CT),
    ]
}

# (route, display name, summit, [(point id, minutes from Reno)], profile towns)
_DEFS: list[tuple[RouteId, str, str, list[tuple[str, int]], tuple[str, ...]]] = [
    (
        RouteId.I80,
        "I-80",
        "donner",
        [
            ("reno", 0),
            ("truckee", 35),
            ("donner", 50),
            ("kingvale", 57),
            ("yuba_gap", 68),
            ("colfax", 92),
            ("sacramento", 135),
        ],
        ("Reno", "Truckee", "Colfax", "Sacramento"),
    ),
    (
        RouteId.US50,
        "US-50",
        "echo",
        [
            ("reno", 0),
            ("carson_city", 35),
            ("spooner", 50),
            ("south_lake_tahoe", 68),
            ("meyers", 78),
            ("echo", 85),
            ("twin_bridges", 92),
            ("kyburz", 105),
            ("placerville", 130),
            ("sacramento", 165),
        ],
        ("Reno", "Tahoe", "Placerville", "Sacramento"),
    ),
    (
        RouteId.SR88,
        "SR-88",
        "carson_pass",
        [
            ("reno", 0),
            ("minden", 50),
            ("woodfords", 70),
            ("carson_pass", 95),
            ("kirkwood", 102),
            ("carson_spur", 106),
            ("jackson", 150),
            ("sacramento", 195),
        ],
        ("Reno", "Minden", "Jackson", "Sacramento"),
    ),
]

# Profile scale matches the approved mockup: x spans 10..348, y = 132 - elevation * 0.0125.
X0, X1 = 10.0, 348.0
Y_BASE, Y_SCALE = 132.0, 0.0125


def _build(direction: Direction) -> dict[RouteId, Corridor]:
    out: dict[RouteId, Corridor] = {}
    for route, name, summit, stops, towns in _DEFS:
        total = stops[-1][1]
        seq = (
            stops
            if direction is Direction.RENO_SAC
            else [(p, total - m) for p, m in reversed(stops)]
        )
        built = tuple(
            Stop(
                point=P[pid],
                minutes=m,
                x=round(X0 + (X1 - X0) * m / total, 1),
                y=round(Y_BASE - P[pid].elevation_ft * Y_SCALE, 1),
            )
            for pid, m in seq
        )
        town_seq = towns if direction is Direction.RENO_SAC else tuple(reversed(towns))
        out[route] = Corridor(route, name, summit, built, town_seq)
    return out


CORRIDORS: dict[Direction, dict[RouteId, Corridor]] = {d: _build(d) for d in Direction}


def segment_key(a: str, b: str) -> frozenset[str]:
    """Direction-independent identity of a segment."""
    return frozenset((a, b))
