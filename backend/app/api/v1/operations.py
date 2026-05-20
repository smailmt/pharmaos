"""
Router /operations — modules métier Jour 8 :
- Clôture journée
- Ordonnancier
- Échanges confrères
- Charges
- Inventaires
"""
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db, get_current_user, get_current_pharmacy_id, require_permission,
)
from app.models.user import User
from app.models.product import Product
from app.models.operations import (
    DayClosing, PrescriptionLog, PharmacyExchange, Expense,
    InventorySession, InventoryLine,
)
from app.services.day_closing_service import DayClosingService
from app.schemas.operations import (
    DayClosingCreate, DayClosingOut,
    PrescriptionLogOut,
    PharmacyExchangeCreate, PharmacyExchangeOut, PartnerBalance,
    ExpenseCreate, ExpenseOut, ExpenseSummary,
    InventorySessionCreate, InventorySessionOut,
    InventoryLineCreate, InventoryLineOut,
)


router = APIRouter(prefix="/operations", tags=["operations"])


# ============ Clôture journée ============
@router.post("/day-closings", response_model=DayClosingOut, status_code=201)
async def close_day(
    payload: DayClosingCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("sales:close_day")),
):
    """Clôture la journée. Une fois faite, les ventes ne peuvent plus être modifiées."""
    svc = DayClosingService(db, user.pharmacy_id)
    target = payload.closing_date or date.today()
    try:
        closing = await svc.close_day(
            closing_date=target,
            closed_by_user_id=user.id,
            cash_counted=payload.cash_counted,
            notes=payload.notes,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    return closing


@router.get("/day-closings/preview", response_model=dict)
async def preview_day_totals(
    target_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    """Pré-visualise les totaux du jour avant clôture (Z-report en lecture seule)."""
    svc = DayClosingService(db, pharmacy_id)
    target = target_date or date.today()
    if await svc.is_closed(target):
        existing = await svc.get_closing(target)
        return {
            "already_closed": True,
            "closing_id": str(existing.id),
            "closing_date": target.isoformat(),
        }
    totals = await svc.compute_day_totals(target)
    return {
        "already_closed": False,
        "closing_date": target.isoformat(),
        **{k: str(v) if isinstance(v, Decimal) else v for k, v in totals.items()},
    }


@router.get("/day-closings", response_model=list[DayClosingOut])
async def list_day_closings(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    svc = DayClosingService(db, pharmacy_id)
    return await svc.list_closings(limit=limit)


# ============ Ordonnancier ============
@router.get("/prescription-log", response_model=list[PrescriptionLogOut])
async def list_prescriptions(
    days: int = Query(30, ge=1, le=365),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    """Liste l'ordonnancier (registre légal des ordonnances dispensées)."""
    start = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(PrescriptionLog)
        .where(
            PrescriptionLog.pharmacy_id == pharmacy_id,
            PrescriptionLog.created_at >= start,
        )
        .order_by(PrescriptionLog.sequential_number.desc())
        .limit(500)
    )
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            (PrescriptionLog.patient_name.ilike(like))
            | (PrescriptionLog.prescriber_name.ilike(like))
            | (PrescriptionLog.prescription_number.ilike(like))
        )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ============ Échanges confrères ============
@router.post("/exchanges", response_model=PharmacyExchangeOut, status_code=201)
async def create_exchange(
    payload: PharmacyExchangeCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("exchanges:write")),
):
    """Enregistre un échange entrée/sortie avec une pharmacie confrère."""
    if payload.direction not in ("in", "out"):
        raise HTTPException(400, "direction doit être 'in' ou 'out'")

    total = payload.unit_value * Decimal(payload.quantity)
    exchange = PharmacyExchange(
        pharmacy_id=user.pharmacy_id,
        exchange_date=payload.exchange_date or date.today(),
        direction=payload.direction,
        partner_name=payload.partner_name,
        partner_phone=payload.partner_phone,
        product_id=payload.product_id,
        product_name=payload.product_name,
        quantity=payload.quantity,
        unit_value=payload.unit_value,
        total_value=total,
        notes=payload.notes,
        status="pending",
    )
    db.add(exchange)
    await db.flush()
    return exchange


@router.get("/exchanges", response_model=list[PharmacyExchangeOut])
async def list_exchanges(
    partner: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    stmt = select(PharmacyExchange).where(PharmacyExchange.pharmacy_id == pharmacy_id)
    if partner:
        stmt = stmt.where(PharmacyExchange.partner_name.ilike(f"%{partner}%"))
    if status_filter:
        stmt = stmt.where(PharmacyExchange.status == status_filter)
    stmt = stmt.order_by(PharmacyExchange.exchange_date.desc()).limit(200)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/exchanges/balances", response_model=list[PartnerBalance])
async def partner_balances(
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    """Solde des échanges par pharmacie confrère (qui doit quoi à qui)."""
    result = await db.execute(
        select(
            PharmacyExchange.partner_name,
            PharmacyExchange.direction,
            func.count(PharmacyExchange.id).label("count"),
            func.coalesce(func.sum(PharmacyExchange.total_value), 0).label("total"),
        )
        .where(
            PharmacyExchange.pharmacy_id == pharmacy_id,
            PharmacyExchange.status == "pending",
        )
        .group_by(PharmacyExchange.partner_name, PharmacyExchange.direction)
    )

    balances: dict[str, dict] = {}
    for row in result:
        b = balances.setdefault(row.partner_name, {
            "partner_name": row.partner_name,
            "in_count": 0, "in_value": Decimal("0"),
            "out_count": 0, "out_value": Decimal("0"),
        })
        if row.direction == "in":
            b["in_count"] = int(row.count)
            b["in_value"] = Decimal(str(row.total))
        else:
            b["out_count"] = int(row.count)
            b["out_value"] = Decimal(str(row.total))

    return [
        PartnerBalance(
            partner_name=b["partner_name"],
            in_count=b["in_count"], in_value=b["in_value"],
            out_count=b["out_count"], out_value=b["out_value"],
            # in (on a reçu) = on doit, out (on a donné) = ils nous doivent
            net_balance=b["out_value"] - b["in_value"],
        )
        for b in balances.values()
    ]


@router.post("/exchanges/{exchange_id}/settle", response_model=PharmacyExchangeOut)
async def settle_exchange(
    exchange_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("exchanges:write")),
):
    """Marque un échange comme réglé (le confrère a rendu / on a rendu)."""
    exchange = await db.get(PharmacyExchange, exchange_id)
    if not exchange or exchange.pharmacy_id != user.pharmacy_id:
        raise HTTPException(404, "Échange introuvable")
    exchange.status = "settled"
    exchange.settled_at = datetime.utcnow()
    await db.flush()
    return exchange


# ============ Charges ============
@router.post("/expenses", response_model=ExpenseOut, status_code=201)
async def create_expense(
    payload: ExpenseCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("expenses:write")),
):
    expense = Expense(
        pharmacy_id=user.pharmacy_id,
        expense_date=payload.expense_date or date.today(),
        category=payload.category,
        amount=payload.amount,
        description=payload.description,
        receipt_reference=payload.receipt_reference,
        payment_method=payload.payment_method,
        is_recurring=payload.is_recurring,
        created_by_user_id=user.id,
    )
    db.add(expense)
    await db.flush()
    return expense


@router.get("/expenses", response_model=list[ExpenseOut])
async def list_expenses(
    days: int = Query(30, ge=1, le=365),
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("expenses:read")),
):
    start = date.today() - timedelta(days=days)
    stmt = (
        select(Expense)
        .where(
            Expense.pharmacy_id == user.pharmacy_id,
            Expense.expense_date >= start,
        )
    )
    if category:
        stmt = stmt.where(Expense.category == category)
    stmt = stmt.order_by(Expense.expense_date.desc()).limit(500)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/expenses/summary", response_model=list[ExpenseSummary])
async def expenses_summary(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("expenses:read")),
):
    """Résumé par catégorie sur N jours."""
    start = date.today() - timedelta(days=days)
    result = await db.execute(
        select(
            Expense.category,
            func.coalesce(func.sum(Expense.amount), 0).label("total"),
            func.count(Expense.id).label("count"),
        )
        .where(
            Expense.pharmacy_id == user.pharmacy_id,
            Expense.expense_date >= start,
        )
        .group_by(Expense.category)
        .order_by(func.sum(Expense.amount).desc())
    )
    return [
        ExpenseSummary(
            category=row.category,
            total_amount=Decimal(str(row.total)),
            count=int(row.count),
        )
        for row in result
    ]


@router.delete("/expenses/{expense_id}", status_code=204)
async def delete_expense(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("expenses:write")),
):
    expense = await db.get(Expense, expense_id)
    if not expense or expense.pharmacy_id != user.pharmacy_id:
        raise HTTPException(404, "Charge introuvable")
    await db.delete(expense)


# ============ Inventaires ============
@router.post("/inventory-sessions", response_model=InventorySessionOut, status_code=201)
async def create_inventory_session(
    payload: InventorySessionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("stock:inventory")),
):
    """Démarre une nouvelle session d'inventaire."""
    session = InventorySession(
        pharmacy_id=user.pharmacy_id,
        started_by_user_id=user.id,
        name=payload.name,
        scope=payload.scope,
        notes=payload.notes,
    )
    db.add(session)
    await db.flush()
    return session


@router.get("/inventory-sessions", response_model=list[InventorySessionOut])
async def list_inventory_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("stock:read")),
):
    result = await db.execute(
        select(InventorySession)
        .where(InventorySession.pharmacy_id == user.pharmacy_id)
        .order_by(InventorySession.created_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())


@router.post("/inventory-sessions/{session_id}/lines", response_model=InventoryLineOut, status_code=201)
async def add_inventory_line(
    session_id: uuid.UUID,
    payload: InventoryLineCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("stock:inventory")),
):
    """Compte un produit dans une session d'inventaire."""
    session = await db.get(InventorySession, session_id)
    if not session or session.pharmacy_id != user.pharmacy_id:
        raise HTTPException(404, "Session introuvable")
    if session.status != "in_progress":
        raise HTTPException(409, "Session non modifiable")

    product = await db.get(Product, payload.product_id)
    if not product or product.pharmacy_id != user.pharmacy_id:
        raise HTTPException(404, "Produit introuvable")

    theoretical = product.stock_quantity or 0
    diff = payload.quantity_counted - theoretical
    cost = product.purchase_price_ht or Decimal("0")
    value_diff = Decimal(diff) * cost

    line = InventoryLine(
        pharmacy_id=user.pharmacy_id,
        session_id=session_id,
        product_id=payload.product_id,
        quantity_theoretical=theoretical,
        quantity_counted=payload.quantity_counted,
        difference=diff,
        unit_cost=cost,
        value_difference=value_diff,
        notes=payload.notes,
        counted_by_user_id=user.id,
    )
    db.add(line)
    await db.flush()
    return line


@router.get("/inventory-sessions/{session_id}/lines", response_model=list[InventoryLineOut])
async def list_inventory_lines(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("stock:read")),
):
    session = await db.get(InventorySession, session_id)
    if not session or session.pharmacy_id != user.pharmacy_id:
        raise HTTPException(404, "Session introuvable")
    result = await db.execute(
        select(InventoryLine)
        .where(InventoryLine.session_id == session_id)
        .order_by(InventoryLine.created_at)
    )
    return list(result.scalars().all())


@router.post("/inventory-sessions/{session_id}/complete", response_model=InventorySessionOut)
async def complete_inventory_session(
    session_id: uuid.UUID,
    apply_adjustments: bool = True,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("stock:inventory")),
):
    """
    Clôture la session : calcule les totaux et applique les ajustements de stock
    si apply_adjustments=True (alignement stock théorique sur stock compté).
    """
    session = await db.get(InventorySession, session_id)
    if not session or session.pharmacy_id != user.pharmacy_id:
        raise HTTPException(404, "Session introuvable")
    if session.status != "in_progress":
        raise HTTPException(409, "Session déjà clôturée")

    # Calcul stats
    lines_result = await db.execute(
        select(InventoryLine).where(InventoryLine.session_id == session_id)
    )
    lines = list(lines_result.scalars().all())

    items_counted = len(lines)
    discrepancies = sum(1 for l in lines if l.difference != 0)
    total_diff = sum((l.value_difference for l in lines), Decimal("0"))

    # Ajustement stock physique si demandé
    if apply_adjustments:
        for line in lines:
            if line.difference == 0:
                continue
            product = await db.get(Product, line.product_id)
            if product:
                product.stock_quantity = line.quantity_counted

    session.status = "completed"
    session.completed_at = datetime.utcnow()
    session.items_counted = items_counted
    session.discrepancies_count = discrepancies
    session.total_value_difference = total_diff

    await db.flush()
    return session
