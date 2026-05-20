"""Schemas Client / Crédit."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from app.schemas.common import APIModel


# ---------- Client ----------
class ClientBase(APIModel):
    code: str | None = None
    full_name: str
    phone: str | None = None
    email: str | None = None
    cin: str | None = None
    birth_date: date | None = None
    address: str | None = None
    city: str | None = None
    credit_enabled: bool = False
    credit_limit: Decimal = Decimal("0")
    default_payment_terms_days: int = 30
    third_party_payer_id: uuid.UUID | None = None
    third_party_card_number: str | None = None
    third_party_coverage_rate: Decimal | None = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(APIModel):
    full_name: str | None = None
    phone: str | None = None
    credit_enabled: bool | None = None
    credit_limit: Decimal | None = None
    third_party_payer_id: uuid.UUID | None = None
    is_active: bool | None = None


class ClientOut(ClientBase):
    id: uuid.UUID
    pharmacy_id: uuid.UUID
    loyalty_points: int
    risk_score: int
    is_active: bool
    created_at: datetime


class ClientDetailOut(ClientOut):
    """Vue détaillée avec solde courant et stats."""
    current_balance: Decimal
    overdue_amount: Decimal
    total_purchases: Decimal
    last_purchase_date: date | None = None
    available_credit: Decimal


# ---------- Credit ----------
class CreditEntryCreate(APIModel):
    client_id: uuid.UUID
    entry_type: str  # sale / payment / adjustment / writeoff
    amount: Decimal
    entry_date: date | None = None
    payment_method: str | None = None
    reference: str | None = None
    notes: str | None = None


class CreditEntryOut(APIModel):
    id: uuid.UUID
    client_id: uuid.UUID
    entry_type: str
    amount: Decimal
    entry_date: date
    sale_id: uuid.UUID | None = None
    payment_method: str | None = None
    reference: str | None = None
    notes: str | None = None
    created_at: datetime


class CreditPaymentRequest(APIModel):
    """Enregistrer un paiement (allocation auto sur échéances ouvertes, FIFO)."""
    client_id: uuid.UUID
    amount: Decimal
    payment_method: str = "cash"
    payment_date: date | None = None
    reference: str | None = None
    notes: str | None = None


class CreditDueDateCreate(APIModel):
    client_id: uuid.UUID
    sale_id: uuid.UUID | None = None
    due_date: date
    amount_due: Decimal


class CreditDueDateOut(APIModel):
    id: uuid.UUID
    client_id: uuid.UUID
    sale_id: uuid.UUID | None = None
    due_date: date
    amount_due: Decimal
    amount_paid: Decimal
    amount_remaining: Decimal
    status: str
    is_overdue: bool
    paid_at: datetime | None = None


class CreditReminderCreate(APIModel):
    client_id: uuid.UUID
    due_date_id: uuid.UUID | None = None
    channel: str = "manual"
    message: str | None = None


class CreditReminderOut(APIModel):
    id: uuid.UUID
    client_id: uuid.UUID
    channel: str
    sent_at: datetime
    message: str | None = None
    success: bool


class AgingBucket(APIModel):
    """Une tranche de la balance âgée."""
    bucket: str  # "0-30", "31-60", "61-90", "90+"
    amount: Decimal
    clients_count: int


class AgingReport(APIModel):
    as_of_date: date
    total_outstanding: Decimal
    buckets: list[AgingBucket]
