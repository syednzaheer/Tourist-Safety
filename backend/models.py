"""Pydantic schemas for request/response validation."""
from datetime import datetime
from pydantic import BaseModel, Field


class TouristRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=8, max_length=15)
    nationality: str | None = None
    itinerary: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    trip_start: datetime
    trip_end: datetime


class TouristOut(BaseModel):
    id: str
    name: str
    phone: str
    nationality: str | None = None
    itinerary: str | None = None
    trip_start: datetime
    trip_end: datetime
    token: str
    qr_code_base64: str
    onchain_tx_hash: str | None = None  # None if blockchain wasn't configured, not an error


class LocationPing(BaseModel):
    tourist_id: str
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class GeofenceResult(BaseModel):
    inside_risk_zone: bool
    zone_name: str | None = None
    risk_level: str | None = None
    alert_created: bool = False
    sms_guidance: str | None = None
    sms_status: str | None = None  # 'sent' | 'simulated' | 'failed: ...' | None (not in a zone)


class AlertOut(BaseModel):
    id: int
    tourist_id: str
    alert_type: str
    reason: str
    lat: float | None
    lng: float | None
    created_at: str
    resolved: bool


class SOSRequest(BaseModel):
    tourist_id: str
    service: str = Field(..., pattern="^(police|ambulance|fire|helpline)$")
    lat: float
    lng: float


class OfficerLogin(BaseModel):
    badge_id: str
    password: str


class RiskZoneIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    radius_m: float = Field(..., gt=0, le=50_000)
    risk_level: str = Field(..., pattern="^(high|medium)$")
    sms_guidance: str = Field(..., min_length=10, max_length=500)


class IncidentReportIn(BaseModel):
    tourist_id: str | None = None
    reporter_name: str | None = None
    reporter_phone: str | None = None
    category: str = Field(..., pattern="^(theft|harassment|medical|scam|other)$")
    description: str = Field(..., min_length=5, max_length=2000)
    lat: float | None = None
    lng: float | None = None
