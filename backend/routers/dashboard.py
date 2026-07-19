"""
Police dashboard API: alert feed, live tourist locations, and a
WebSocket endpoint so the map updates without the browser having to
poll. The WebSocket here pushes a fresh snapshot to each connected
client every few seconds server-side, rather than a full event-driven
broadcast-on-insert pub/sub - that would need a message queue (Redis or
similar) to do properly across multiple worker processes, which is more
infrastructure than a single-process demo deployment needs. This still
replaces client-side polling with a server push, which is the part that
actually matters for "real-time" here.
"""
import asyncio
import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from auth import verify_officer_token
from database import get_conn
from deps import get_current_officer

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

PUSH_INTERVAL_SECONDS = 3


def _fetch_snapshot(resolved: bool = False, limit: int = 50):
    with get_conn() as conn:
        alerts = conn.execute(
            """SELECT a.*, t.name as tourist_name, t.phone as tourist_phone
               FROM alerts a JOIN tourists t ON a.tourist_id = t.id
               WHERE a.resolved = ? ORDER BY a.created_at DESC LIMIT ?""",
            (int(resolved), limit),
        ).fetchall()
        locations = conn.execute(
            """SELECT l.tourist_id, t.name, l.lat, l.lng, l.recorded_at
               FROM locations l
               JOIN tourists t ON t.id = l.tourist_id
               WHERE l.id IN (
                   SELECT MAX(id) FROM locations GROUP BY tourist_id
               )"""
        ).fetchall()
    return {
        "alerts": [dict(r) for r in alerts],
        "live_locations": [dict(r) for r in locations],
    }


@router.get("/alerts", dependencies=[Depends(get_current_officer)])
def list_alerts(resolved: bool = False, limit: int = 50):
    return _fetch_snapshot(resolved, limit)["alerts"]


@router.post("/alerts/{alert_id}/resolve", dependencies=[Depends(get_current_officer)])
def resolve_alert(alert_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE alerts SET resolved = 1 WHERE id = ?", (alert_id,))
    return {"status": "resolved"}


@router.get("/live-locations", dependencies=[Depends(get_current_officer)])
def live_locations():
    """Latest known position for every tourist — feeds the police map."""
    return _fetch_snapshot()["live_locations"]


@router.websocket("/ws")
async def dashboard_ws(websocket: WebSocket, token: str):
    """Browsers can't attach an Authorization header to a WebSocket
    handshake, so the officer token comes through as a query param
    instead: /api/dashboard/ws?token=<jwt>."""
    payload = verify_officer_token(token)
    if payload is None:
        await websocket.close(code=4401)  # 4401: custom close code, "unauthorized"
        return

    await websocket.accept()
    try:
        while True:
            snapshot = _fetch_snapshot()
            await websocket.send_text(json.dumps(snapshot))
            await asyncio.sleep(PUSH_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        pass
