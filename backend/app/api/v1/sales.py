"""Router : Ventes (caisse)."""
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_current_user, get_current_pharmacy_id
from app.models.user import User
from app.models.sale import Sale, SaleItem
from app.models.product import Product, ProductLot
from app.schemas.sale import SaleCreate, SaleOut
from app.services.sale_service import SaleService

router = APIRouter(prefix="/sales", tags=["sales"])


@router.post("", response_model=SaleOut, status_code=201)
async def create_sale(
    payload: SaleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Bloquer si la journée du jour est déjà clôturée
    from app.services.day_closing_service import DayClosingService
    from datetime import date as _date
    closing_svc = DayClosingService(db, user.pharmacy_id)
    if await closing_svc.is_closed(_date.today()):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La journée est déjà clôturée — impossible de créer une vente.",
        )

    svc = SaleService(db, user.pharmacy_id, cashier_id=user.id)
    sale = await svc.create_sale(payload.model_dump())
    # Recharger pour items
    result = await db.execute(
        select(Sale).options(selectinload(Sale.items)).where(Sale.id == sale.id)
    )
    sale_loaded = result.scalar_one()

    # === Logger l'ordonnance si présente ===
    if sale_loaded.has_prescription:
        from app.models.operations import PrescriptionLog
        from app.models.client import Client as ClientModel
        from sqlalchemy import func as _func

        # Numéro séquentiel par pharmacie par année
        year_start = datetime(datetime.utcnow().year, 1, 1)
        seq_result = await db.execute(
            select(_func.coalesce(_func.max(PrescriptionLog.sequential_number), 0))
            .where(
                PrescriptionLog.pharmacy_id == user.pharmacy_id,
                PrescriptionLog.created_at >= year_start,
            )
        )
        next_seq = (seq_result.scalar() or 0) + 1

        # Patient depuis le client si lié
        patient_name = None
        if sale_loaded.client_id:
            client = await db.get(ClientModel, sale_loaded.client_id)
            if client:
                patient_name = client.full_name

        dispensed = [
            {
                "product_id": str(item.product_id),
                "name": item.product_name_snapshot if hasattr(item, "product_name_snapshot") else None,
                "quantity": item.quantity,
            }
            for item in sale_loaded.items
        ]

        log_entry = PrescriptionLog(
            pharmacy_id=user.pharmacy_id,
            sale_id=sale_loaded.id,
            sequential_number=next_seq,
            prescription_number=sale_loaded.prescription_number,
            patient_name=patient_name,
            dispensed_items=dispensed,
        )
        db.add(log_entry)

    # === Webhooks ===
    from app.services.webhook_service import WebhookService
    wh = WebhookService(db, user.pharmacy_id)
    # sale.created
    await wh.emit("sale.created", {
        "id": str(sale_loaded.id),
        "sale_number": sale_loaded.sale_number,
        "sale_date": sale_loaded.sale_date.isoformat() if sale_loaded.sale_date else None,
        "client_id": str(sale_loaded.client_id) if sale_loaded.client_id else None,
        "total_ttc": str(sale_loaded.total_ttc),
        "items_count": len(sale_loaded.items),
        "payment_method": sale_loaded.payment_method,
    })
    # Détecter passages sous seuil pour chaque produit vendu
    for item in sale_loaded.items:
        product = await db.get(Product, item.product_id)
        if product and product.stock_quantity <= product.stock_min:
            await wh.emit("product.low_stock", {
                "id": str(product.id),
                "code": product.code,
                "name": product.name,
                "stock_quantity": product.stock_quantity,
                "stock_min": product.stock_min,
            })

    return sale_loaded


@router.get("", response_model=list[SaleOut])
async def list_sales(
    date_from: date | None = None,
    date_to: date | None = None,
    client_id: uuid.UUID | None = None,
    status_filter: str | None = Query(None, alias="status"),
    payment_method: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    stmt = select(Sale).where(Sale.pharmacy_id == pharmacy_id)
    if date_from:
        stmt = stmt.where(Sale.sale_date >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        stmt = stmt.where(Sale.sale_date <= datetime.combine(date_to, datetime.max.time()))
    if client_id:
        stmt = stmt.where(Sale.client_id == client_id)
    if status_filter:
        stmt = stmt.where(Sale.status == status_filter)
    if payment_method:
        stmt = stmt.where(Sale.payment_method == payment_method)
    stmt = stmt.order_by(Sale.sale_date.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/stats/today")
async def stats_today(
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    today = date.today()
    start = datetime.combine(today, datetime.min.time())
    end = datetime.combine(today, datetime.max.time())
    result = await db.execute(
        select(
            func.count(Sale.id),
            func.coalesce(func.sum(Sale.total_ttc), 0),
            func.coalesce(func.sum(Sale.paid_cash), 0),
            func.coalesce(func.sum(Sale.paid_card), 0),
            func.coalesce(func.sum(Sale.paid_credit), 0),
            func.coalesce(func.sum(Sale.payer_share), 0),
        ).where(
            Sale.pharmacy_id == pharmacy_id,
            Sale.sale_date >= start,
            Sale.sale_date <= end,
            Sale.status == "completed",
        )
    )
    row = result.one()
    return {
        "date": today,
        "sales_count": row[0],
        "total_ttc": float(row[1] or 0),
        "cash": float(row[2] or 0),
        "card": float(row[3] or 0),
        "credit": float(row[4] or 0),
        "third_party": float(row[5] or 0),
    }


@router.get("/{sale_id}", response_model=SaleOut)
async def get_sale(
    sale_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    sale = await db.get(Sale, sale_id)
    if not sale or sale.pharmacy_id != pharmacy_id:
        raise HTTPException(404, "Vente introuvable")
    return sale


@router.post("/{sale_id}/cancel", response_model=SaleOut)
async def cancel_sale(
    sale_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    """Annule une vente et restitue le stock."""
    sale = await db.get(Sale, sale_id)
    if not sale or sale.pharmacy_id != pharmacy_id:
        raise HTTPException(404, "Vente introuvable")
    if sale.status == "cancelled":
        raise HTTPException(400, "Vente déjà annulée")

    # Restituer le stock
    result = await db.execute(select(SaleItem).where(SaleItem.sale_id == sale_id))
    for item in result.scalars().all():
        await db.execute(
            update(Product)
            .where(Product.id == item.product_id)
            .values(stock_quantity=Product.stock_quantity + item.quantity)
        )
        if item.lot_id:
            lot = await db.get(ProductLot, item.lot_id)
            if lot:
                lot.quantity += item.quantity

    sale.status = "cancelled"
    sale.cancelled_at = datetime.utcnow()
    await db.flush()
    return sale
