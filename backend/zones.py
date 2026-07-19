"""
Geo-fence math, plus zone lookups against the DB (see database.py's
risk_zones table). Used to hardcode a list here and duplicate it in
map.html - moved to the DB so there's one place to add/edit a zone
instead of two that can drift apart.

Zones are circles (center + radius) rather than polygons - simpler to
define and enough for a demo. If this needs real polygon zones later,
check_zone() is the only place that has to change; haversine_m() stays
the same either way.
"""
from dataclasses import dataclass
from math import radians, sin, cos, sqrt, atan2

from database import get_conn


@dataclass
class RiskZone:
    id: int
    name: str
    lat: float
    lng: float
    radius_m: float
    risk_level: str  # "high" | "medium"
    sms_guidance: str


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points, in meters."""
    R = 6_371_000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lng2 - lng1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def all_zones() -> list[RiskZone]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, lat, lng, radius_m, risk_level, sms_guidance FROM risk_zones ORDER BY id"
        ).fetchall()
    return [RiskZone(**dict(r)) for r in rows]


def check_zone(lat: float, lng: float) -> RiskZone | None:
    """Return the first risk zone containing this point, or None."""
    for zone in all_zones():
        if haversine_m(lat, lng, zone.lat, zone.lng) <= zone.radius_m:
            return zone
    return None
