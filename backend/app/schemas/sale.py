"""Schemas Sale."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from app.schemas.common import APIModel


class SaleItemCreate(APIModel):
    product_id: uuid.UUID
    lot_id: uuid.UUID | None = None
    quantity: int
    unit_price_ttc: Decimal | None = None  # si None, prix du produit
    discount_rate: Decimal = Decimal("0")
    is_reimbursable: bool = True


class SaleCreate(APIModel):
    client_id: uuid.UUID | None = None
    has_prescription: bool = False
    prescription_number: str | None = None
    prescriber_name: str | None = None
    prescriber_inpe: str | None = None

    third_party_payer_id: uuid.UUID | None = None
    third_party_coverage_rate: Decimal | None = None

    items: list[SaleItemCreate]

    # Encaissements
    paid_cash: Decimal = Decimal("0")
    paid_card: Decimal = Decimal("0")
    paid_check: Decimal = Decimal("0")

    # Si crédit client, on peut préciser un échéancier
    due_dates: list[dict] | None = None  # [{"due_date": "2026-06-15", "amount_due": "150.00"}]

    loyalty_points_used: int = 0
    notes: str | None = None


class SaleItemOut(APIModel):
    id: uuid.UUID
    product_id: uuid.UUID
    lot_id: uuid.UUID | None = None
    quantity: int
    unit_price_ttc: Decimal
    discount_rate: Decimal
    line_total_ttc: Decimal
    is_reimbursable: bool


class SaleOut(APIModel):
    id: uuid.UUID
    sale_number: str
    sale_date: datetime
    client_id: uuid.UUID | None = None
    has_prescription: bool
    prescription_number: str | None = None
    third_party_payer_id: uuid.UUID | None = None
    third_party_coverage_rate: Decimal | None = None
    subtotal_ht: Decimal
    total_vat: Decimal
    total_discount: Decimal
    total_ttc: Decimal
    payer_share: Decimal
    client_share: Decimal
    paid_cash: Decimal
    paid_card: Decimal
    paid_check: Decimal
    paid_credit: Decimal
    payment_method: str
    status: str
    loyalty_points_earned: int
    loyalty_points_used: int
    items: list[SaleItemOut]
    created_at: datetime
