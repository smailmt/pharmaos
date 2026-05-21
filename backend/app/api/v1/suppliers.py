"""Router : Fournisseurs, catalogue, BC, BL, factures, paiements, retours."""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_pharmacy_id, get_current_user
from app.models.user import User
from app.models.supplier import (
    Supplier, SupplierProduct,
    PurchaseOrder, DeliveryNote,
    SupplierInvoice, SupplierPayment, SupplierReturn,
)
from app.schemas.supplier import (
    SupplierCreate, SupplierUpdate, SupplierOut, SupplierDetailOut,
    SupplierProductCreate, SupplierProductOut,
    PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderOut,
    DeliveryNoteCreate, DeliveryNoteOut,
    SupplierInvoiceCreate, SupplierInvoiceOut,
    SupplierPaymentCreate, SupplierPaymentOut,
    SupplierReturnCreate, SupplierReturnOut,
)
from app.services.supplier_service import SupplierService

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


# ---------- Suppliers CRUD ----------
@router.post("", response_model=SupplierOut, status_code=201)
async def create_supplier(
    payload: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    supplier = Supplier(pharmacy_id=pharmacy_id, **payload.model_dump())
    db.add(supplier)
    await db.flush()
    return supplier


@router.get("", response_model=list[SupplierOut])
async def list_suppliers(
    q: str | None = Query(None),
    type_filter: str | None = Query(None, alias="type"),
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    stmt = select(Supplier).where(Supplier.pharmacy_id == pharmacy_id, Supplier.is_active == True)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Supplier.name.ilike(like)) | (Supplier.code.ilike(like)))
    if type_filter:
        stmt = stmt.where(Supplier.type == type_filter)
    stmt = stmt.order_by(Supplier.name).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.patch("/{supplier_id}", response_model=SupplierOut)
async def update_supplier(
    supplier_id: uuid.UUID,
    payload: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    supplier = await db.get(Supplier, supplier_id)
    if not supplier or supplier.pharmacy_id != pharmacy_id:
        raise HTTPException(404, "Fournisseur introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(supplier, k, v)
    await db.flush()
    return supplier


# ---------- Catalogue ----------
@router.post("/catalog", response_model=SupplierProductOut, status_code=201)
async def add_to_catalog(
    payload: SupplierProductCreate,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    item = SupplierProduct(pharmacy_id=pharmacy_id, **payload.model_dump())
    db.add(item)
    await db.flush()
    return item


# ---------- Purchase Orders ----------
@router.post("/orders", response_model=PurchaseOrderOut, status_code=201)
async def create_purchase_order(
    payload: PurchaseOrderCreate,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    svc = SupplierService(db, pharmacy_id)
    po = await svc.create_purchase_order(
        supplier_id=payload.supplier_id,
        items=[i.model_dump() for i in payload.items],
        order_date=payload.order_date,
        expected_delivery_date=payload.expected_delivery_date,
        notes=payload.notes,
    )
    # Recharger avec items
    result = await db.execute(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.items))
        .where(PurchaseOrder.id == po.id)
    )
    return result.scalar_one()


@router.post("/orders/{order_id}/send", response_model=PurchaseOrderOut)
async def send_purchase_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    po = await db.get(PurchaseOrder, order_id)
    if not po or po.pharmacy_id != pharmacy_id:
        raise HTTPException(404, "BC introuvable")
    svc = SupplierService(db, pharmacy_id)
    await svc.send_purchase_order(order_id)
    result = await db.execute(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.items))
        .where(PurchaseOrder.id == order_id)
    )
    return result.scalar_one()


@router.get("/orders", response_model=list[PurchaseOrderOut])
async def list_purchase_orders(
    supplier_id: uuid.UUID | None = None,
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    stmt = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.items))
        .where(PurchaseOrder.pharmacy_id == pharmacy_id)
    )
    if supplier_id:
        stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
    if status_filter:
        stmt = stmt.where(PurchaseOrder.status == status_filter)
    stmt = stmt.order_by(PurchaseOrder.order_date.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/orders/{order_id}", response_model=PurchaseOrderOut)
async def get_purchase_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    result = await db.execute(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.items))
        .where(PurchaseOrder.id == order_id)
    )
    po = result.scalar_one_or_none()
    if not po or po.pharmacy_id != pharmacy_id:
        raise HTTPException(404, "BC introuvable")
    return po


# ---------- Delivery Notes ----------
@router.post("/deliveries", response_model=DeliveryNoteOut, status_code=201)
async def receive_delivery(
    payload: DeliveryNoteCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    svc = SupplierService(db, user.pharmacy_id)
    dn = await svc.receive_delivery(
        supplier_id=payload.supplier_id,
        delivery_number=payload.delivery_number,
        items=[i.model_dump() for i in payload.items],
        purchase_order_id=payload.purchase_order_id,
        delivery_date=payload.delivery_date,
        received_by=user.id,
        notes=payload.notes,
    )
    # Recharger avec items pour la sérialisation
    result = await db.execute(
        select(DeliveryNote)
        .options(selectinload(DeliveryNote.items))
        .where(DeliveryNote.id == dn.id)
    )
    return result.scalar_one()


@router.get("/deliveries", response_model=list[DeliveryNoteOut])
async def list_deliveries(
    supplier_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    stmt = (
        select(DeliveryNote)
        .options(selectinload(DeliveryNote.items))
        .where(DeliveryNote.pharmacy_id == pharmacy_id)
    )
    if supplier_id:
        stmt = stmt.where(DeliveryNote.supplier_id == supplier_id)
    stmt = stmt.order_by(DeliveryNote.delivery_date.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---------- Invoices ----------
@router.post("/invoices", response_model=SupplierInvoiceOut, status_code=201)
async def register_invoice(
    payload: SupplierInvoiceCreate,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    svc = SupplierService(db, pharmacy_id)
    invoice = await svc.register_invoice(
        supplier_id=payload.supplier_id,
        invoice_number=payload.invoice_number,
        invoice_date=payload.invoice_date,
        total_ht=payload.total_ht,
        total_vat=payload.total_vat,
        total_ttc=payload.total_ttc,
        due_date=payload.due_date,
        delivery_note_ids=payload.delivery_note_ids,
        notes=payload.notes,
    )
    return _invoice_to_out(invoice)


@router.get("/invoices", response_model=list[SupplierInvoiceOut])
async def list_invoices(
    supplier_id: uuid.UUID | None = None,
    status_filter: str | None = Query(None, alias="status"),
    overdue_only: bool = False,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    stmt = select(SupplierInvoice).where(SupplierInvoice.pharmacy_id == pharmacy_id)
    if supplier_id:
        stmt = stmt.where(SupplierInvoice.supplier_id == supplier_id)
    if status_filter:
        stmt = stmt.where(SupplierInvoice.status == status_filter)
    if overdue_only:
        stmt = stmt.where(
            SupplierInvoice.due_date < date.today(),
            SupplierInvoice.status.in_(["pending", "partially_paid"]),
        )
    stmt = stmt.order_by(SupplierInvoice.due_date.asc())
    result = await db.execute(stmt)
    return [_invoice_to_out(inv) for inv in result.scalars().all()]


@router.get("/invoices/{invoice_id}", response_model=SupplierInvoiceOut)
async def get_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    invoice = await db.get(SupplierInvoice, invoice_id)
    if not invoice or invoice.pharmacy_id != pharmacy_id:
        raise HTTPException(404, "Facture introuvable")
    return _invoice_to_out(invoice)


# ---------- Payments ----------
@router.post("/payments", response_model=SupplierPaymentOut, status_code=201)
async def pay_invoice(
    payload: SupplierPaymentCreate,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    svc = SupplierService(db, pharmacy_id)
    return await svc.pay_invoice(
        invoice_id=payload.invoice_id,
        supplier_id=payload.supplier_id,
        amount=payload.amount,
        payment_method=payload.payment_method,
        payment_date=payload.payment_date,
        reference=payload.reference,
        bank_name=payload.bank_name,
        check_due_date=payload.check_due_date,
        notes=payload.notes,
    )


@router.get("/payments", response_model=list[SupplierPaymentOut])
async def list_payments(
    supplier_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    stmt = select(SupplierPayment).where(SupplierPayment.pharmacy_id == pharmacy_id)
    if supplier_id:
        stmt = stmt.where(SupplierPayment.supplier_id == supplier_id)
    stmt = stmt.order_by(SupplierPayment.payment_date.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---------- Returns ----------
@router.post("/returns", response_model=SupplierReturnOut, status_code=201)
async def create_return(
    payload: SupplierReturnCreate,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    svc = SupplierService(db, pharmacy_id)
    return await svc.create_return(
        supplier_id=payload.supplier_id,
        items=[i.model_dump() for i in payload.items],
        reason=payload.reason,
        return_date=payload.return_date,
        notes=payload.notes,
    )


@router.get("/returns", response_model=list[SupplierReturnOut])
async def list_returns(
    supplier_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    stmt = select(SupplierReturn).where(SupplierReturn.pharmacy_id == pharmacy_id)
    if supplier_id:
        stmt = stmt.where(SupplierReturn.supplier_id == supplier_id)
    stmt = stmt.order_by(SupplierReturn.return_date.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---------- Propositions de commande ----------
@router.get("/purchase-proposals")
async def purchase_proposals(
    mode: str = Query("sales", description="sales | minmax"),
    supplier_id: uuid.UUID | None = None,
    days: int = Query(30, ge=1, le=365),
    period_start: date | None = None,
    period_end: date | None = None,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    """
    Propose une liste de produits à commander.
    - mode=sales : basé sur les ventes (période = days en arrière, ou period_start/end)
    - mode=minmax : produits sous leur stock minimum
    """
    from app.services.purchase_proposal_service import PurchaseProposalService
    svc = PurchaseProposalService(db, pharmacy_id)

    if mode == "minmax":
        items = await svc.propose_by_minmax(supplier_id)
    else:
        end = period_end or date.today()
        start = period_start or (end - timedelta(days=days))
        items = await svc.propose_by_sales(supplier_id, start, end)

    total_pph = sum((Decimal(i["pph"]) * i["suggested_quantity"] for i in items), Decimal("0"))
    total_ppv = sum((Decimal(i["ppv"]) * i["suggested_quantity"] for i in items), Decimal("0"))
    return {
        "mode": mode,
        "count": len(items),
        "total_pph": str(total_pph.quantize(Decimal("0.01"))),
        "total_ppv": str(total_ppv.quantize(Decimal("0.01"))),
        "items": items,
    }


# ---------- Helpers ----------
def _invoice_to_out(invoice: SupplierInvoice) -> SupplierInvoiceOut:
    return SupplierInvoiceOut(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        supplier_id=invoice.supplier_id,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        received_date=invoice.received_date,
        total_ht=invoice.total_ht,
        total_vat=invoice.total_vat,
        total_ttc=invoice.total_ttc,
        amount_paid=invoice.amount_paid,
        amount_remaining=invoice.amount_remaining,
        status=invoice.status,
        is_overdue=invoice.is_overdue,
        delivery_note_ids=invoice.delivery_note_ids or [],
        created_at=invoice.created_at,
    )


@router.put("/orders/{order_id}", response_model=PurchaseOrderOut)
async def update_purchase_order(
    order_id: uuid.UUID,
    payload: PurchaseOrderUpdate,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    svc = SupplierService(db, pharmacy_id)
    try:
        await svc.update_purchase_order(
            po_id=order_id,
            expected_delivery_date=payload.expected_delivery_date,
            notes=payload.notes,
            items=[i.model_dump() for i in payload.items] if payload.items is not None else None,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    result = await db.execute(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.items))
        .where(PurchaseOrder.id == order_id)
    )
    return result.scalar_one()


@router.delete("/orders/{order_id}", status_code=204)
async def delete_purchase_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    svc = SupplierService(db, pharmacy_id)
    try:
        await svc.delete_purchase_order(order_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------- Routes paramétrées (DÉFINIES EN DERNIER) ----------
# IMPORTANT : ces routes /{supplier_id} doivent être déclarées APRÈS toutes
# les routes littérales (/orders, /deliveries, /invoices, /payments, /returns),
# sinon FastAPI matche "/payments" comme un supplier_id et renvoie 422.
@router.get("/{supplier_id}", response_model=SupplierDetailOut)
async def get_supplier_detail(
    supplier_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    supplier = await db.get(Supplier, supplier_id)
    if not supplier or supplier.pharmacy_id != pharmacy_id:
        raise HTTPException(404, "Fournisseur introuvable")

    svc = SupplierService(db, pharmacy_id)
    balance = await svc.get_supplier_balance(supplier_id)
    overdue = await svc.get_overdue_amount(supplier_id)

    year_start = date(date.today().year, 1, 1)
    result = await db.execute(
        select(func.coalesce(func.sum(SupplierInvoice.total_ttc), 0))
        .where(
            SupplierInvoice.pharmacy_id == pharmacy_id,
            SupplierInvoice.supplier_id == supplier_id,
            SupplierInvoice.invoice_date >= year_start,
        )
    )
    ytd = Decimal(str(result.scalar() or 0))

    return SupplierDetailOut(
        **{k: getattr(supplier, k) for k in SupplierOut.model_fields.keys()},
        current_balance=balance,
        overdue_amount=overdue,
        total_purchases_ytd=ytd,
    )


@router.get("/{supplier_id}/catalog", response_model=list[SupplierProductOut])
async def list_catalog(
    supplier_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    result = await db.execute(
        select(SupplierProduct).where(
            SupplierProduct.pharmacy_id == pharmacy_id,
            SupplierProduct.supplier_id == supplier_id,
        )
    )
    return list(result.scalars().all())
