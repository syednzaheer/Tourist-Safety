"""
SOS dispatch. Every press writes a real timestamped alert row to the DB
(no localStorage involved this time). SMS via Twilio is optional - set
the TWILIO_* env vars in sms.py's environment or it just logs
"simulated" instead of pretending to send a text it didn't actually
send.
"""
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException

from database import get_conn
from models import SOSRequest
from sms import send_sms

router = APIRouter(prefix="/api", tags=["sos"])

DISPATCH_TO = os.environ.get("DISPATCH_TO_NUMBER")


@router.post("/sos")
def trigger_sos(payload: SOSRequest):
    with get_conn() as conn:
        tourist = conn.execute(
            "SELECT name FROM tourists WHERE id = ?", (payload.tourist_id,)
        ).fetchone()
        if tourist is None:
            raise HTTPException(404, "Unknown tourist_id")

        now = datetime.utcnow().isoformat()
        conn.execute(
            """INSERT INTO alerts (tourist_id, alert_type, reason, lat, lng, created_at)
               VALUES (?, 'sos', ?, ?, ?, ?)""",
            (
                payload.tourist_id,
                f"SOS: {payload.service} requested by {tourist['name']}",
                payload.lat,
                payload.lng,
                now,
            ),
        )

    sms_status = send_sms(
        DISPATCH_TO,
        f"SOS ({payload.service}) from {tourist['name']} at "
        f"{payload.lat:.5f},{payload.lng:.5f}",
    )

    return {"status": "logged", "sms_status": sms_status}
