"""Schemas auth, pharmacy, user."""
import uuid
from datetime import datetime
from pydantic import EmailStr, Field
from app.schemas.common import APIModel


# ---------- Pharmacy ----------
class PharmacyCreate(APIModel):
    name: str
    legal_name: str | None = None
    ice: str | None = None
    if_number: str | None = None
    rc_number: str | None = None
    cnss_number: str | None = None
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    email: str | None = None
    pharmacist_in_charge: str | None = None
    inpe_number: str | None = None


class PharmacyOut(APIModel):
    id: uuid.UUID
    name: str
    legal_name: str | None = None
    ice: str | None = None
    if_number: str | None = None
    rc_number: str | None = None
    cnss_number: str | None = None
    inpe_number: str | None = None
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    email: str | None = None
    pharmacist_in_charge: str | None = None
    plan: str
    is_active: bool
    created_at: datetime


# ---------- User ----------
class UserOut(APIModel):
    id: uuid.UUID
    pharmacy_id: uuid.UUID
    email: EmailStr
    full_name: str
    role: str
    is_active: bool


# ---------- Auth ----------
class RegisterRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    pharmacy: PharmacyCreate
    plan: str | None = None  # trial / starter / pro / enterprise


class LoginRequest(APIModel):
    email: EmailStr
    password: str


class TokenResponse(APIModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
    pharmacy: PharmacyOut


class RefreshRequest(APIModel):
    refresh_token: str
