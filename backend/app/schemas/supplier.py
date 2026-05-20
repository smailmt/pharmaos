"""Schemas Fournisseur, commandes, BL, factures, paiements, retours."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from app.schemas.common import APIModel


# ---------- Supplier ----------
class SupplierBase(APIModel):
    code: str
    name: str
    type: str = "wholesaler"
    legal_name: str | None = None
    ice: str | None = None
    if_number: str | None = None
    rc_number: str | None = None
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    contact_person: str | None = None
    default_discount_rate: Decimal = Decimal("0")
    payment_terms_days: int = 30
    credit_limit: Decimal = Decimal("0")
    delivery_lead_time_days: int = 1
    min_order_amount: Decimal = Decimal("0")
    bank_name: str | None = None
    bank_rib: str | None = None


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(APIModel):
    name: str | None = None
    phone: str | None = None
    contact_person: str | None = None
    default_discount_rate: Decimal | None = None
    payment_terms_days: int | None = None
    is_active: bool | None = None


class SupplierOut(SupplierBase):
    id: uuid.UUID
    pharmacy_id: uuid.UUID
    is_active: bool
    created_at: datetime


class SupplierDetailOut(SupplierOut):
    current_balance: Decimal  # dette envers le fournisseur
    overdue_amount: Decimal
    total_purchases_ytd: Decimal


# ---------- Catalogue ----------
class SupplierProductCreate(APIModel):
    supplier_id: uuid.UUID
    product_id: uuid.UUID
    supplier_code: str | None = None
    purchase_price_ht: Decimal
    ppv: Decimal | None = None
    discount_rate: Decimal = Decimal("0")
    min_order_quantity: int = 1
    is_preferred: bool = False


class SupplierProductOut(SupplierProductCreate):
    id: uuid.UUID
    last_purchase_date: date | None = None


# ---------- Purchase Order ----------
class PurchaseOrderItemCreate(APIModel):
    product_id: uuid.UUID
    quantity_ordered: int
    unit_price_ht: Decimal
    discount_rate: Decimal = Decimal("0")
    vat_rate: Decimal = Decimal("0.07")


class PurchaseOrderItemOut(APIModel):
    id: uuid.UUID
    product_id: uuid.UUID
    quantity_ordered: int
    quantity_received: int
    unit_price_ht: Decimal
    discount_rate: Decimal
    vat_rate: Decimal
    line_total_ht: Decimal
    line_total_ttc: Decimal


class PurchaseOrderCreate(APIModel):
    supplier_id: uuid.UUID
    order_date: date | None = None
    expected_delivery_date: date | None = None
    notes: str | None = None
    items: list[PurchaseOrderItemCreate]


class PurchaseOrderOut(APIModel):
    id: uuid.UUID
    order_number: str
    supplier_id: uuid.UUID
    order_date: date
    expected_delivery_date: date | None = None
    sent_at: datetime | None = None
    total_ht: Decimal
    total_vat: Decimal
    total_discount: Decimal
    total_ttc: Decimal
    status: str
    notes: str | None = None
    items: list[PurchaseOrderItemOut]
    created_at: datetime


# ---------- Delivery Note ----------
class DeliveryNoteItemCreate(APIModel):
    product_id: uuid.UUID
    lot_number: str | None = None
    expiration_date: date | None = None
    quantity_ordered: int = 0
    quantity_received: int
    unit_price_ht: Decimal
    sale_price_ttc: Decimal | None = None  # PPV imprimé sur la boîte de ce lot
    discount_rate: Decimal = Decimal("0")
    vat_rate: Decimal = Decimal("0.07")
    discrepancy_note: str | None = None


class DeliveryNoteCreate(APIModel):
    delivery_number: str
    purchase_order_id: uuid.UUID | None = None
    supplier_id: uuid.UUID
    delivery_date: date | None = None
    items: list[DeliveryNoteItemCreate]
    notes: str | None = None


class DeliveryNoteItemOut(APIModel):
    id: uuid.UUID
    product_id: uuid.UUID
    lot_number: str | None = None
    expiration_date: date | None = None
    quantity_ordered: int
    quantity_received: int
    unit_price_ht: Decimal
    line_total_ttc: Decimal
    discrepancy_note: str | None = None


class DeliveryNoteOut(APIModel):
    id: uuid.UUID
    delivery_number: str
    purchase_order_id: uuid.UUID | None = None
    supplier_id: uuid.UUID
    delivery_date: date
    total_ht: Decimal
    total_ttc: Decimal
    has_discrepancies: bool
    status: str
    items: list[DeliveryNoteItemOut]
    created_at: datetime


# ---------- Supplier Invoice ----------
class SupplierInvoiceCreate(APIModel):
    invoice_number: str
    supplier_id: uuid.UUID
    invoice_date: date
    due_date: date | None = None  # si None, calculé à partir des conditions
    total_ht: Decimal
    total_vat: Decimal
    total_ttc: Decimal
    delivery_note_ids: list[uuid.UUID] = []
    notes: str | None = None


class SupplierInvoiceOut(APIModel):
    id: uuid.UUID
    invoice_number: str
    supplier_id: uuid.UUID
    invoice_date: date
    due_date: date
    received_date: date
    total_ht: Decimal
    total_vat: Decimal
    total_ttc: Decimal
    amount_paid: Decimal
    amount_remaining: Decimal
    status: str
    is_overdue: bool
    delivery_note_ids: list = []
    created_at: datetime


# ---------- Supplier Payment ----------
class SupplierPaymentCreate(APIModel):
    invoice_id: uuid.UUID | None = None  # peut être un paiement anticipé/on-account
    supplier_id: uuid.UUID
    payment_date: date | None = None
    amount: Decimal
    payment_method: str = "transfer"
    reference: str | None = None
    bank_name: str | None = None
    check_due_date: date | None = None
    notes: str | None = None


class SupplierPaymentOut(APIModel):
    id: uuid.UUID
    invoice_id: uuid.UUID | None = None
    supplier_id: uuid.UUID
    payment_date: date
    amount: Decimal
    payment_method: str
    reference: str | None = None
    check_due_date: date | None = None
    created_at: datetime


# ---------- Returns ----------
class SupplierReturnItemCreate(APIModel):
    product_id: uuid.UUID
    lot_number: str | None = None
    quantity: int
    unit_price_ht: Decimal


class SupplierReturnCreate(APIModel):
    supplier_id: uuid.UUID
    return_date: date | None = None
    reason: str = "expired"
    notes: str | None = None
    items: list[SupplierReturnItemCreate]


class SupplierReturnOut(APIModel):
    id: uuid.UUID
    return_number: str
    supplier_id: uuid.UUID
    return_date: date
    reason: str
    total_amount: Decimal
    credit_note_received: bool
    credit_note_number: str | None = None
    status: str
    created_at: datetime
