"""Schemas Pydantic pour les modules opérationnels (J8)."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from app.schemas.common import APIModel


# ============ Clôture journée ============
class DayClosingCreate(APIModel):
    closing_date: date | None = None  # défaut: aujourd'hui
    cash_counted: Decimal = Decimal("0")
    notes: str | None = None


class DayClosingOut(APIModel):
    id: uuid.UUID
    closing_date: date
    closed_by_user_id: uuid.UUID
    sales_count: int
    cancelled_count: int
    total_revenue: Decimal
    total_cash: Decimal
    total_card: Decimal
    total_check: Decimal
    total_credit: Decimal
    total_third_party: Decimal
    cash_expected: Decimal
    cash_counted: Decimal
    cash_difference: Decimal
    notes: str | None
    created_at: datetime


# ============ Ordonnancier ============
class PrescriptionLogOut(APIModel):
    id: uuid.UUID
    sale_id: uuid.UUID | None
    sequential_number: int
    prescription_number: str | None
    prescription_date: date | None
    prescriber_name: str | None
    prescriber_inpe: str | None
    patient_name: str | None
    patient_cin: str | None
    patient_age: int | None
    dispensed_items: list[dict]
    created_at: datetime


# ============ Échanges confrères ============
class PharmacyExchangeCreate(APIModel):
    exchange_date: date | None = None
    direction: str  # "in" / "out"
    partner_name: str
    partner_phone: str | None = None
    product_id: uuid.UUID | None = None
    product_name: str
    quantity: int
    unit_value: Decimal = Decimal("0")
    notes: str | None = None


class PharmacyExchangeOut(APIModel):
    id: uuid.UUID
    exchange_date: date
    direction: str
    partner_name: str
    partner_phone: str | None
    product_id: uuid.UUID | None
    product_name: str
    quantity: int
    unit_value: Decimal
    total_value: Decimal
    status: str
    settled_at: datetime | None
    notes: str | None
    created_at: datetime


class PartnerBalance(APIModel):
    """Solde des échanges avec un partenaire (qui doit quoi à qui)."""
    partner_name: str
    in_count: int
    in_value: Decimal
    out_count: int
    out_value: Decimal
    net_balance: Decimal  # positif = ils nous doivent / négatif = on leur doit


# ============ Charges ============
class ExpenseCreate(APIModel):
    expense_date: date | None = None
    category: str
    amount: Decimal
    description: str
    receipt_reference: str | None = None
    payment_method: str = "cash"
    is_recurring: bool = False


class ExpenseOut(APIModel):
    id: uuid.UUID
    expense_date: date
    category: str
    amount: Decimal
    description: str
    receipt_reference: str | None
    payment_method: str
    is_recurring: bool
    created_at: datetime


class ExpenseSummary(APIModel):
    """Résumé par catégorie pour un range de dates."""
    category: str
    total_amount: Decimal
    count: int


# ============ Inventaires ============
class InventorySessionCreate(APIModel):
    name: str = "Inventaire"
    scope: str = "full"
    notes: str | None = None


class InventoryLineCreate(APIModel):
    product_id: uuid.UUID
    quantity_counted: int
    notes: str | None = None


class InventoryLineOut(APIModel):
    id: uuid.UUID
    product_id: uuid.UUID
    quantity_theoretical: int
    quantity_counted: int
    difference: int
    unit_cost: Decimal
    value_difference: Decimal
    notes: str | None


class InventorySessionOut(APIModel):
    id: uuid.UUID
    name: str
    status: str
    scope: str
    started_at: datetime
    completed_at: datetime | None
    items_counted: int
    discrepancies_count: int
    total_value_difference: Decimal
    notes: str | None
    created_at: datetime
