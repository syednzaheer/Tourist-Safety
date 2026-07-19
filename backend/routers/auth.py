from fastapi import APIRouter, HTTPException

from auth import issue_officer_token, verify_password
from database import get_conn
from models import OfficerLogin

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def officer_login(payload: OfficerLogin):
    with get_conn() as conn:
        officer = conn.execute(
            "SELECT * FROM officers WHERE badge_id = ?", (payload.badge_id,)
        ).fetchone()

    if officer is None or not verify_password(payload.password, officer["password_hash"]):
        # Same message either way - don't tell a caller whether the badge_id
        # exists, that's a free enumeration of valid officer IDs otherwise.
        raise HTTPException(401, "Invalid badge ID or password")

    token = issue_officer_token(officer["badge_id"], officer["name"])
    return {"token": token, "name": officer["name"], "badge_id": officer["badge_id"]}
