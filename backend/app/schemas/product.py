"""Schemas Product / Lot."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from app.schemas.common import APIModel


class ProductBase(APIModel):
    code: str | None = None
    barcode: str | None = None
    name: str
    dci: str | None = None
    laboratory: str | None = None
    form: str | None = None
    dosage: str | None = None
    category: str | None = None
    purchase_price_ht: Decimal = Decimal("0")
    sale_price_ttc: Decimal = Decimal("0")
    vat_rate: Decimal = Decimal("0.07")
    stock_min: int = 0
    stock_max: int = 0
    is_prescription_required: bool = False
    is_psychotropic: bool = False
    is_reimbursable: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(APIModel):
    name: str | None = None
    barcode: str | None = None
    dci: str | None = None
    laboratory: str | None = None
    purchase_price_ht: Decimal | None = None
    sale_price_ttc: Decimal | None = None
    stock_min: int | None = None
    is_active: bool | None = None


class ProductOut(ProductBase):
    id: uuid.UUID
    pharmacy_id: uuid.UUID
    stock_quantity: int
    is_active: bool
    created_at: datetime


class ProductLotCreate(APIModel):
    product_id: uuid.UUID
    lot_number: str
    quantity: int
    expiration_date: date | None = None
    purchase_price_ht: Decimal | None = None
    sale_price_ttc: Decimal | None = None


class ProductLotOut(APIModel):
    id: uuid.UUID
    product_id: uuid.UUID
    lot_number: str
    quantity: int
    expiration_date: date | None = None
    purchase_price_ht: Decimal | None = None
    sale_price_ttc: Decimal | None = None
