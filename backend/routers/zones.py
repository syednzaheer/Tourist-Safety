"""
Risk zone management. Reading the zone list is public - the tourist-facing
map needs it to draw the same zones the backend enforces, and there's
nothing sensitive in a zone's coordinates. Creating or deleting a zone
is officer-only.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from database import get_conn
from deps import get_current_officer
from models import RiskZoneIn
from zones import all_zones

router = APIRouter(prefix="/api/zones", tags=["zones"])


@router.get("")
def list_zones():
    return [
        {
            "id": z.id,
            "name": z.name,
            "lat": z.lat,
            "lng": z.lng,
            "radius_m": z.radius_m,
            "risk_level": z.risk_level,
        }
        for z in all_zones()
    ]


@router.post("", dependencies=[Depends(get_current_officer)])
def create_zone(payload: RiskZoneIn):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO risk_zones (name, lat, lng, radius_m, risk_level, sms_guidance, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                payload.name, payload.lat, payload.lng, payload.radius_m,
                payload.risk_level, payload.sms_guidance, datetime.utcnow().isoformat(),
            ),
        )
    return {"id": cur.lastrowid, "status": "created"}


@router.delete("/{zone_id}", dependencies=[Depends(get_current_officer)])
def delete_zone(zone_id: int):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM risk_zones WHERE id = ?", (zone_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "Zone not found")
    return {"status": "deleted"}
