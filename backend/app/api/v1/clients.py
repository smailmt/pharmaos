"""Router : Clients, crédits, échéances, relances, balance âgée."""
import uuid
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_pharmacy_id
from app.models.client import Client, CreditEntry, CreditDueDate, CreditReminder
from app.models.sale import Sale
from app.schemas.client import (
    ClientCreate, ClientUpdate, ClientOut, ClientDetailOut,
    CreditEntryCreate, CreditEntryOut,
    CreditPaymentRequest,
    CreditDueDateCreate, CreditDueDateOut,
    CreditReminderCreate, CreditReminderOut,
    AgingReport,
)
from app.services.credit_service import CreditService

router = APIRouter(prefix="/clients", tags=["clients"])


# ---------- Clients CRUD ----------
@router.post("", response_model=ClientOut, status_code=201)
async def create_client(
    payload: ClientCreate,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    client = Client(pharmacy_id=pharmacy_id, **payload.model_dump())
    db.add(client)
    await db.flush()
    return client


@router.get("", response_model=list[ClientOut])
async def list_clients(
    q: str | None = Query(None),
    credit_enabled: bool | None = None,
    has_overdue: bool | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    stmt = select(Client).where(Client.pharmacy_id == pharmacy_id, Client.is_active == True)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            (Client.full_name.ilike(like)) | (Client.phone.ilike(like)) | (Client.cin.ilike(like))
        )
    if credit_enabled is not None:
        stmt = stmt.where(Client.credit_enabled == credit_enabled)
    if has_overdue:
        sub = select(CreditDueDate.client_id).where(
            CreditDueDate.pharmacy_id == pharmacy_id,
            CreditDueDate.due_date < date.today(),
            CreditDueDate.status.in_(["pending", "partial"]),
        )
        stmt = stmt.where(Client.id.in_(sub))

    stmt = stmt.order_by(Client.full_name).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{client_id}", response_model=ClientDetailOut)
async def get_client_detail(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    client = await db.get(Client, client_id)
    if not client or client.pharmacy_id != pharmacy_id:
        raise HTTPException(404, "Client introuvable")

    svc = CreditService(db, pharmacy_id)
    balance = await svc.get_balance(client_id)
    overdue = await svc.get_overdue_amount(client_id)

    # Stats
    result = await db.execute(
        select(
            func.coalesce(func.sum(Sale.total_ttc), 0),
            func.max(Sale.sale_date),
        ).where(
            Sale.pharmacy_id == pharmacy_id,
            Sale.client_id == client_id,
            Sale.status == "completed",
        )
    )
    row = result.one()
    total_purchases = Decimal(str(row[0] or 0))
    last_purchase = row[1].date() if row[1] else None

    available = client.credit_limit - balance if client.credit_limit > 0 else Decimal("0")
    if available < 0:
        available = Decimal("0")

    return ClientDetailOut(
        **{k: getattr(client, k) for k in ClientOut.model_fields.keys()},
        current_balance=balance,
        overdue_amount=overdue,
        total_purchases=total_purchases,
        last_purchase_date=last_purchase,
        available_credit=available,
    )


@router.patch("/{client_id}", response_model=ClientOut)
async def update_client(
    client_id: uuid.UUID,
    payload: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    client = await db.get(Client, client_id)
    if not client or client.pharmacy_id != pharmacy_id:
        raise HTTPException(404, "Client introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(client, k, v)
    await db.flush()
    return client


# ---------- Crédit : entries (mouvements bruts) ----------
@router.get("/{client_id}/credit/entries", response_model=list[CreditEntryOut])
async def list_credit_entries(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    result = await db.execute(
        select(CreditEntry)
        .where(
            CreditEntry.pharmacy_id == pharmacy_id,
            CreditEntry.client_id == client_id,
        )
        .order_by(CreditEntry.entry_date.desc(), CreditEntry.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/{client_id}/credit/entries", response_model=CreditEntryOut, status_code=201)
async def create_credit_entry(
    client_id: uuid.UUID,
    payload: CreditEntryCreate,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    """Crée une entry manuelle (ajustement, write-off)."""
    if payload.client_id != client_id:
        raise HTTPException(400, "Incohérence client_id")
    entry = CreditEntry(
        pharmacy_id=pharmacy_id,
        client_id=client_id,
        entry_type=payload.entry_type,
        amount=payload.amount,
        entry_date=payload.entry_date or date.today(),
        payment_method=payload.payment_method,
        reference=payload.reference,
        notes=payload.notes,
    )
    db.add(entry)
    await db.flush()
    return entry


# ---------- Crédit : paiement avec allocation FIFO ----------
@router.post("/credit/payments", response_model=CreditEntryOut, status_code=201)
async def record_payment(
    payload: CreditPaymentRequest,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    """Enregistre un paiement client et alloue automatiquement sur les échéances ouvertes (FIFO)."""
    svc = CreditService(db, pharmacy_id)
    entry, _ = await svc.record_payment(
        client_id=payload.client_id,
        amount=payload.amount,
        payment_method=payload.payment_method,
        payment_date=payload.payment_date,
        reference=payload.reference,
        notes=payload.notes,
    )
    await svc.update_risk_score(payload.client_id)
    return entry


# ---------- Échéances ----------
@router.get("/{client_id}/credit/due-dates", response_model=list[CreditDueDateOut])
async def list_due_dates(
    client_id: uuid.UUID,
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    stmt = select(CreditDueDate).where(
        CreditDueDate.pharmacy_id == pharmacy_id,
        CreditDueDate.client_id == client_id,
    )
    if status_filter:
        stmt = stmt.where(CreditDueDate.status == status_filter)
    stmt = stmt.order_by(CreditDueDate.due_date.asc())
    result = await db.execute(stmt)
    items = list(result.scalars().all())
    return [
        CreditDueDateOut(
            id=d.id, client_id=d.client_id, sale_id=d.sale_id,
            due_date=d.due_date, amount_due=d.amount_due, amount_paid=d.amount_paid,
            amount_remaining=d.amount_remaining, status=d.status,
            is_overdue=d.is_overdue, paid_at=d.paid_at,
        )
        for d in items
    ]


# ---------- Relances ----------
@router.get("/credit/overdue", response_model=list[CreditDueDateOut])
async def list_overdue(
    days_overdue: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    """Toutes les échéances en retard de la pharmacie."""
    svc = CreditService(db, pharmacy_id)
    items = await svc.get_overdue_due_dates(days_overdue=days_overdue)
    return [
        CreditDueDateOut(
            id=d.id, client_id=d.client_id, sale_id=d.sale_id,
            due_date=d.due_date, amount_due=d.amount_due, amount_paid=d.amount_paid,
            amount_remaining=d.amount_remaining, status=d.status,
            is_overdue=True, paid_at=d.paid_at,
        )
        for d in items
    ]


@router.get("/credit/due-soon", response_model=list[CreditDueDateOut])
async def list_due_soon(
    days_ahead: int = Query(3, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    """Échéances arrivant à terme (pour pré-relance)."""
    svc = CreditService(db, pharmacy_id)
    items = await svc.get_due_soon(days_ahead=days_ahead)
    return [
        CreditDueDateOut(
            id=d.id, client_id=d.client_id, sale_id=d.sale_id,
            due_date=d.due_date, amount_due=d.amount_due, amount_paid=d.amount_paid,
            amount_remaining=d.amount_remaining, status=d.status,
            is_overdue=d.is_overdue, paid_at=d.paid_at,
        )
        for d in items
    ]


@router.post("/{client_id}/credit/reminders", response_model=CreditReminderOut, status_code=201)
async def create_reminder(
    client_id: uuid.UUID,
    payload: CreditReminderCreate,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    """
    Créer une relance crédit. Si channel = `whatsapp` ou `sms` et que Twilio est configuré,
    envoie effectivement le message. Sinon (mode preview), enregistre juste la relance.
    """
    svc = CreditService(db, pharmacy_id)
    reminder = await svc.create_reminder(
        client_id=client_id,
        due_date_id=payload.due_date_id,
        channel=payload.channel,
        message=payload.message,
    )

    # Envoi effectif via Twilio si applicable
    if payload.channel in ("whatsapp", "sms"):
        from app.services.notification_service import NotificationService, build_credit_reminder_message
        from app.models.client import Client as ClientModel
        from app.models.pharmacy import Pharmacy

        client = await db.get(ClientModel, client_id)
        pharmacy = await db.get(Pharmacy, pharmacy_id)

        if client and client.phone:
            svc_credit = CreditService(db, pharmacy_id)
            balance = await svc_credit.get_balance(client_id)
            body = payload.message or build_credit_reminder_message(
                pharmacy_name=pharmacy.name if pharmacy else "Votre pharmacie",
                client_name=client.full_name,
                amount_due=str(balance),
            )
            notif = NotificationService()
            result = await notif.send(to=client.phone, body=body, channel=payload.channel)
            # Annote la relance avec le résultat (mais ne bloque pas)
            reminder.message = body[:500] if not reminder.message else reminder.message
            # Note : on pourrait avoir un champ status sur CreditReminder pour stocker le résultat

    return reminder


@router.get("/{client_id}/credit/reminders", response_model=list[CreditReminderOut])
async def list_reminders(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    result = await db.execute(
        select(CreditReminder)
        .where(
            CreditReminder.pharmacy_id == pharmacy_id,
            CreditReminder.client_id == client_id,
        )
        .order_by(CreditReminder.sent_at.desc())
    )
    return list(result.scalars().all())


# ---------- Balance âgée ----------
@router.get("/credit/aging-report", response_model=AgingReport)
async def aging_report(
    as_of: date | None = None,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    """Balance âgée des créances clients."""
    svc = CreditService(db, pharmacy_id)
    return await svc.aging_report(as_of=as_of)
