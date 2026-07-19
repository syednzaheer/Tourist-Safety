from datetime import datetime

from fastapi import APIRouter, HTTPException

from database import get_conn
from models import LocationPing, GeofenceResult
from zones import check_zone
from sms import send_sms

router = APIRouter(prefix="/api", tags=["geofence"])


@router.post("/location/ping", response_model=GeofenceResult)
def location_ping(payload: LocationPing):
    with get_conn() as conn:
        tourist = conn.execute(
            "SELECT id, phone FROM tourists WHERE id = ?", (payload.tourist_id,)
        ).fetchone()
        if tourist is None:
            raise HTTPException(404, "Unknown tourist_id")

        now = datetime.utcnow().isoformat()

        conn.execute(
            "INSERT INTO locations (tourist_id, lat, lng, recorded_at) VALUES (?, ?, ?, ?)",
            (payload.tourist_id, payload.lat, payload.lng, now),
        )

        zone = check_zone(payload.lat, payload.lng)
        alert_created = False
        sms_status = None

        if zone is not None:
            conn.execute(
                """INSERT INTO alerts (tourist_id, alert_type, reason, lat, lng, created_at)
                   VALUES (?, 'geofence', ?, ?, ?, ?)""",
                (
                    payload.tourist_id,
                    f"Entered {zone.risk_level}-risk zone: {zone.name}",
                    payload.lat,
                    payload.lng,
                    now,
                ),
            )
            alert_created = True

            # This is the "offline-capable" part the problem statement asks
            # for - an SMS gets through on plain cellular coverage even
            # with no data connection, unlike a push notification which
            # needs the app open and online.
            sms_status = send_sms(tourist["phone"], zone.sms_guidance)

    return GeofenceResult(
        inside_risk_zone=zone is not None,
        zone_name=zone.name if zone else None,
        risk_level=zone.risk_level if zone else None,
        alert_created=alert_created,
        sms_guidance=zone.sms_guidance if zone else None,
        sms_status=sms_status,
    )
