"""Schemas tiers payants."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from app.schemas.common import APIModel


# ---------- ThirdPartyPayer ----------
class ThirdPartyPayerBase(APIModel):
    code: str
    name: str
    type: str = "public"
    legal_name: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    contact_person: str | None = None
    default_coverage_rate: Decimal = Decimal("0.70")
    max_coverage_per_claim: Decimal | None = None
    requires_prescription: bool = True
    requires_authorization: bool = False
    payment_terms_days: int = 60
    bordereau_frequency: str = "monthly"
    rules: dict = {}


class ThirdPartyPayerCreate(ThirdPartyPayerBase):
    pass


class ThirdPartyPayerUpdate(APIModel):
    name: str | None = None
    default_coverage_rate: Decimal | None = None
    payment_terms_days: int | None = None
    is_active: bool | None = None
    rules: dict | None = None


class ThirdPartyPayerOut(ThirdPartyPayerBase):
    id: uuid.UUID
    pharmacy_id: uuid.UUID
    is_active: bool
    created_at: datetime


# ---------- Claims ----------
class ThirdPartyClaimOut(APIModel):
    id: uuid.UUID
    payer_id: uuid.UUID
    client_id: uuid.UUID | None = None
    sale_id: uuid.UUID
    bordereau_id: uuid.UUID | None = None
    claim_date: date
    prescription_number: str | None = None
    total_amount: Decimal
    coverage_rate: Decimal
    payer_share: Decimal
    client_share: Decimal
    amount_paid: Decimal
    status: str
    rejection_reason: str | None = None


# ---------- Bordereaux ----------
class BordereauCreate(APIModel):
    payer_id: uuid.UUID
    period_start: date
    period_end: date
    claim_ids: list[uuid.UUID] | None = None  # si vide → toutes les claims pending de la période


class BordereauOut(APIModel):
    id: uuid.UUID
    payer_id: uuid.UUID
    bordereau_number: str
    period_start: date
    period_end: date
    submitted_at: datetime | None = None
    total_amount: Decimal
    amount_paid: Decimal
    status: str
    notes: str | None = None
    created_at: datetime


class BordereauDetailOut(BordereauOut):
    claims: list[ThirdPartyClaimOut]


# ---------- Payments ----------
class ThirdPartyPaymentCreate(APIModel):
    bordereau_id: uuid.UUID
    payment_date: date | None = None  # défaut: aujourd'hui (côté serveur)
    amount: Decimal
    payment_method: str = "transfer"
    reference: str | None = None
    notes: str | None = None
    rejected_claim_ids: list[uuid.UUID] | None = None  # claims refusées par l'organisme
    rejection_reasons: dict | None = None  # {claim_id: motif}


class ThirdPartyPaymentOut(APIModel):
    id: uuid.UUID
    bordereau_id: uuid.UUID
    payment_date: date
    amount: Decimal
    payment_method: str
    reference: str | None = None
    created_at: datetime
