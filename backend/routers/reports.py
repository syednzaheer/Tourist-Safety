from datetime import datetime

from fastapi import APIRouter, Depends

from database import get_conn
from deps import get_current_officer
from models import IncidentReportIn

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("")
def submit_report(payload: IncidentReportIn):
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO incident_reports
               (tourist_id, reporter_name, reporter_phone, category, description, lat, lng, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                payload.tourist_id, payload.reporter_name, payload.reporter_phone,
                payload.category, payload.description, payload.lat, payload.lng, now,
            ),
        )
    return {"id": cur.lastrowid, "status": "received"}


@router.get("", dependencies=[Depends(get_current_officer)])
def list_reports(status: str | None = None, limit: int = 50):
    query = "SELECT * FROM incident_reports"
    params: list = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]
