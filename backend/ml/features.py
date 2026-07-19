"""
Turns a tourist's recent location history into the fixed-length feature
vector the anomaly model actually looks at. Used by both train_model.py
(on synthetic data) and anomaly_model.py (on real pings from the DB), so
training and inference can't quietly drift apart from each other.

Feature order matters - it has to match training exactly:
  [avg_speed_kmh, max_speed_kmh, gap_minutes, path_std_km, zone_entries_24h]
"""
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime

FEATURE_NAMES = [
    "avg_speed_kmh",
    "max_speed_kmh",
    "gap_minutes",
    "path_std_km",
    "zone_entries_24h",
]


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371.0
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lng2 - lng1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def build_features(points: list[dict], now: datetime, zone_entries_24h: int) -> list[float]:
    """
    points: list of {lat, lng, recorded_at (datetime)}, most recent last,
            at least 1 point. Works with as few as 1-2 points (early trip),
            just less informative.
    """
    if not points:
        return [0.0, 0.0, 0.0, 0.0, float(zone_entries_24h)]

    speeds = []
    for i in range(1, len(points)):
        p1, p2 = points[i - 1], points[i]
        seconds = (p2["recorded_at"] - p1["recorded_at"]).total_seconds()
        if seconds < 30:
            continue  # too close together, speed estimate is noise
        dist_km = haversine_km(p1["lat"], p1["lng"], p2["lat"], p2["lng"])
        speeds.append(dist_km / (seconds / 3600))

    avg_speed = sum(speeds) / len(speeds) if speeds else 0.0
    max_speed = max(speeds) if speeds else 0.0

    gap_minutes = (now - points[-1]["recorded_at"]).total_seconds() / 60

    if len(points) >= 2:
        centroid_lat = sum(p["lat"] for p in points) / len(points)
        centroid_lng = sum(p["lng"] for p in points) / len(points)
        dists = [haversine_km(p["lat"], p["lng"], centroid_lat, centroid_lng) for p in points]
        mean_dist = sum(dists) / len(dists)
        path_std = (sum((d - mean_dist) ** 2 for d in dists) / len(dists)) ** 0.5
    else:
        path_std = 0.0

    return [avg_speed, max_speed, gap_minutes, path_std, float(zone_entries_24h)]
