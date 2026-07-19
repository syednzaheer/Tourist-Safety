import hashlib
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from auth import issue_token, make_qr_base64, verify_token
from database import get_conn
from models import TouristRegister, TouristOut
from blockchain import web3_client

router = APIRouter(prefix="/api", tags=["tourist-id"])


def _data_hash(tourist_id: str, payload: TouristRegister) -> str:
    """keccak-style content hash of the record, stored locally and
    (optionally) on-chain. sha256 here rather than actual keccak256
    since this is just for tying the DB row to the chain entry, not
    something Solidity needs to recompute - the contract only ever
    receives this as an opaque bytes32, never recomputes it itself."""
    raw = f"{tourist_id}|{payload.name}|{payload.phone}|{payload.trip_start}|{payload.trip_end}"
    return hashlib.sha256(raw.encode()).hexdigest()


@router.post("/register", response_model=TouristOut)
def register_tourist(payload: TouristRegister):
    if payload.trip_end <= payload.trip_start:
        raise HTTPException(400, "trip_end must be after trip_start")

    tourist_id = str(uuid.uuid4())
    token = issue_token(tourist_id, payload.trip_start, payload.trip_end)
    qr_b64 = make_qr_base64(token)
    data_hash = _data_hash(tourist_id, payload)

    # On-chain issuance is best-effort: if it's not configured, or the
    # RPC call fails (network hiccup, out of testnet gas, whatever), the
    # tourist still gets a valid JWT-backed ID. A chain outage shouldn't
    # be able to block someone from registering.
    onchain_tx_hash = None
    if web3_client.is_configured():
        try:
            onchain_tx_hash = web3_client.issue_onchain(
                tourist_id,
                int(payload.trip_start.timestamp()),
                int(payload.trip_end.timestamp()),
                data_hash,
            )
        except Exception as e:
            print(f"[blockchain] on-chain issuance failed, continuing with JWT-only: {e}")

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO tourists (id, name, phone, nationality, itinerary,
                                      emergency_contact_name, emergency_contact_phone,
                                      trip_start, trip_end, created_at, onchain_tx_hash, data_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tourist_id,
                payload.name,
                payload.phone,
                payload.nationality,
                payload.itinerary,
                payload.emergency_contact_name,
                payload.emergency_contact_phone,
                payload.trip_start.isoformat(),
                payload.trip_end.isoformat(),
                datetime.utcnow().isoformat(),
                onchain_tx_hash,
                data_hash,
            ),
        )

    return TouristOut(
        id=tourist_id,
        name=payload.name,
        phone=payload.phone,
        nationality=payload.nationality,
        itinerary=payload.itinerary,
        trip_start=payload.trip_start,
        trip_end=payload.trip_end,
        token=token,
        qr_code_base64=qr_b64,
        onchain_tx_hash=onchain_tx_hash,
    )


@router.get("/verify/{token}")
def verify_id(token: str):
    """Used by the police dashboard to validate a scanned QR / ID token.

    The JWT check is the fast path and always runs. If blockchain is
    configured, this also cross-checks the chain - the two should agree,
    but the chain is what a checkpoint in a different state would trust
    if it didn't want to rely on this specific backend being up.
    """
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(401, "Invalid or expired ID")

    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM tourists WHERE id = ?", (payload["sub"],)
        ).fetchone()

    if row is None:
        raise HTTPException(404, "Tourist not found")

    result = dict(row)

    onchain_status = None  # None = blockchain not configured, not "unverified"
    if web3_client.is_configured():
        try:
            onchain_status = web3_client.is_valid_onchain(payload["sub"])
        except Exception as e:
            print(f"[blockchain] on-chain verification check failed: {e}")

    result["onchain_verified"] = onchain_status
    return result
