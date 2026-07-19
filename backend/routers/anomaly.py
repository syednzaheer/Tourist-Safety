"""
Anomaly detection: three explainable rules, plus an IsolationForest model
that scores overall movement patterns. Rules stay because "why did this
fire" needs a plain-English answer for whoever's on the dashboard - the
ML layer catches shapes-of-behavior the fixed thresholds miss (e.g. a
speed and a gap that are each individually fine but combine into
something odd), at the cost of a reason that's a model score rather than
a sentence.

Model is trained on synthetic data for now - see ml/train_model.py for
why, and swap in real movement logs there the moment there's enough of
them.

Meant to run periodically per active tourist (cron/scheduled job), or
just get called after each location ping for now.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException

from database import get_conn
from zones import haversine_m
from ml.anomaly_model import score as ml_score

router = APIRouter(prefix="/api", tags=["anomaly"])

INACTIVITY_THRESHOLD_MIN = 45
MAX_PLAUSIBLE_SPEED_KMH = 120  # anything faster between two pings looks like bad GPS or spoofing, not travel
RISK_ZONE_ENTRIES_FOR_PATTERN_FLAG = 3
ML_HISTORY_POINTS = 10  # how many recent pings feed the model


@router.post("/anomaly/check/{tourist_id}")
def run_anomaly_check(tourist_id: str):
    with get_conn() as conn:
        tourist = conn.execute(
            "SELECT id FROM tourists WHERE id = ?", (tourist_id,)
        ).fetchone()
        if tourist is None:
            raise HTTPException(404, "Unknown tourist_id")

        locations = conn.execute(
            """SELECT lat, lng, recorded_at FROM locations
               WHERE tourist_id = ? ORDER BY recorded_at DESC LIMIT ?""",
            (tourist_id, ML_HISTORY_POINTS),
        ).fetchall()

        findings = []
        now = datetime.utcnow()

        # Rule 1: inactivity — no ping for over the threshold
        if locations:
            last_seen = datetime.fromisoformat(locations[0]["recorded_at"])
            gap_min = (now - last_seen).total_seconds() / 60
            if gap_min > INACTIVITY_THRESHOLD_MIN:
                findings.append(
                    ("inactivity", f"No location update for {int(gap_min)} minutes")
                )

        # Rule 2: implausible speed between the last two pings.
        # Skip anything under 30s apart, the speed math gets noisy that close.
        if len(locations) >= 2:
            p1, p2 = locations[0], locations[1]
            t1 = datetime.fromisoformat(p1["recorded_at"])
            t2 = datetime.fromisoformat(p2["recorded_at"])
            seconds = (t1 - t2).total_seconds()
            if seconds >= 30:
                dist_m = haversine_m(p1["lat"], p1["lng"], p2["lat"], p2["lng"])
                speed_kmh = (dist_m / 1000) / (seconds / 3600)
                if speed_kmh > MAX_PLAUSIBLE_SPEED_KMH:
                    findings.append(
                        ("deviation", f"Implausible movement: {speed_kmh:.0f} km/h between pings")
                    )

        # Rule 3: repeated risk-zone entries in the last 24h
        since = (now - timedelta(hours=24)).isoformat()
        zone_hits = conn.execute(
            """SELECT COUNT(*) as c FROM alerts
               WHERE tourist_id = ? AND alert_type = 'geofence' AND created_at > ?""",
            (tourist_id, since),
        ).fetchone()["c"]
        if zone_hits >= RISK_ZONE_ENTRIES_FOR_PATTERN_FLAG:
            findings.append(
                ("deviation", f"{zone_hits} risk-zone entries in the last 24 hours")
            )

        # ML layer: score the recent movement shape as a whole. Only
        # bother once there's at least one ping to build features from.
        if locations:
            points = [
                {
                    "lat": row["lat"],
                    "lng": row["lng"],
                    "recorded_at": datetime.fromisoformat(row["recorded_at"]),
                }
                # locations came back most-recent-first; the model expects oldest-first
                for row in reversed(locations)
            ]
            is_anomaly, ml_raw_score, _ = ml_score(points, now, zone_hits)
            if is_anomaly:
                findings.append(
                    ("ml_pattern", f"Movement pattern flagged as unusual by anomaly model (score={ml_raw_score:.3f})")
                )

        for alert_type, reason in findings:
            conn.execute(
                """INSERT INTO alerts (tourist_id, alert_type, reason, created_at)
                   VALUES (?, ?, ?, ?)""",
                (tourist_id, alert_type, reason, now.isoformat()),
            )

    return {"tourist_id": tourist_id, "findings": [f[1] for f in findings]}
