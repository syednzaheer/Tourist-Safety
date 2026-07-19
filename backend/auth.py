"""
Digital ID signing, plus officer login for the police dashboard.

Issues a JWT-signed, time-bound tourist ID. The signature makes it
tamper-evident (edit the payload and verification fails), and it expires
on its own once trip_end passes. That covers the "tamper-proof" part of
the problem statement, but it's not a blockchain - no ledger, no
consensus, no chain of blocks. Worth being upfront about that instead of
letting the README oversell it.
"""
import base64
import hashlib
import hmac
import io
import os
import secrets
from datetime import datetime, timedelta

import qrcode
from jose import JWTError, jwt

# Falls back to a dev-only default so the app still runs out of the box,
# but SECRET_KEY should always be set via env var for anything beyond
# a local demo - swap this before deploying anywhere real.
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-only-secret-do-not-use-in-prod")
ALGORITHM = "HS256"
OFFICER_TOKEN_HOURS = 12


def issue_token(tourist_id: str, trip_start: datetime, trip_end: datetime) -> str:
    payload = {
        "sub": tourist_id,
        "typ": "tourist",
        "trip_start": trip_start.isoformat(),
        "trip_end": trip_end.isoformat(),
        "iat": int(datetime.utcnow().timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

    if payload.get("typ") != "tourist":
        return None  # e.g. someone trying to use an officer token as a tourist ID

    trip_end = datetime.fromisoformat(payload["trip_end"])
    if datetime.utcnow() > trip_end:
        return None  # ID is only valid for the trip duration

    return payload


def make_qr_base64(data: str) -> str:
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ---- Officer login (police dashboard access) ----
#
# Not using bcrypt/passlib here to keep the dependency list short -
# PBKDF2-HMAC-SHA256 with a random salt and 200k iterations is still a
# solid choice and it's stdlib-only (hashlib). Format stored in the DB:
# "<salt_hex>$<hash_hex>".

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt, _, expected_hex = stored.partition("$")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000)
    return hmac.compare_digest(digest.hex(), expected_hex)


def issue_officer_token(badge_id: str, name: str) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": badge_id,
        "typ": "officer",
        "name": name,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=OFFICER_TOKEN_HOURS)).timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_officer_token(token: str) -> dict | None:
    try:
        # jose checks "exp" automatically when present
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

    if payload.get("typ") != "officer":
        return None  # e.g. someone trying to use a tourist ID token on the dashboard

    return payload
