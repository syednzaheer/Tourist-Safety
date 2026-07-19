"""
FastAPI dependency that protects the police dashboard and zone-admin
routes. Split out from auth.py so routers can import just this without
pulling in JWT-signing internals they don't need.
"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth import verify_officer_token

_bearer = HTTPBearer(auto_error=False)


def get_current_officer(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if creds is None:
        raise HTTPException(401, "Missing Authorization header")

    payload = verify_officer_token(creds.credentials)
    if payload is None:
        raise HTTPException(401, "Invalid or expired officer session")

    return payload
