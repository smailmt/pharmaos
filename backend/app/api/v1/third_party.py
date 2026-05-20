"""Router : Tiers payants (organismes, claims, bordereaux, paiements)."""
import uuid
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_pharmacy_id
from app.models.third_party import (
    ThirdPartyPayer, ThirdPartyClaim, ThirdPartyBordereau, ThirdPartyPayment,
)
from app.schemas.third_party import (
    ThirdPartyPayerCreate, ThirdPartyPayerUpdate, ThirdPartyPayerOut,
    ThirdPartyClaimOut,
    BordereauCreate, BordereauOut, BordereauDetailOut,
    ThirdPartyPaymentCreate, ThirdPartyPaymentOut,
)
from app.services.third_party_service import ThirdPartyService

router = APIRouter(prefix="/third-party", tags=["third-party"])


# ---------- Payers ----------
@router.post("/payers", response_model=ThirdPartyPayerOut, status_code=201)
async def create_payer(
    payload: ThirdPartyPayerCreate,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    payer = ThirdPartyPayer(pharmacy_id=pharmacy_id, **payload.model_dump())
    db.add(payer)
    await db.flush()
    return payer


@router.get("/payers", response_model=list[ThirdPartyPayerOut])
async def list_payers(
    type_filter: str | None = Query(None, alias="type"),
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    stmt = select(ThirdPartyPayer).where(
        ThirdPartyPayer.pharmacy_id == pharmacy_id,
        ThirdPartyPayer.is_active == True,
    )
    if type_filter:
        stmt = stmt.where(ThirdPartyPayer.type == type_filter)
    stmt = stmt.order_by(ThirdPartyPayer.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/payers/{payer_id}", response_model=ThirdPartyPayerOut)
async def get_payer(
    payer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    payer = await db.get(ThirdPartyPayer, payer_id)
    if not payer or payer.pharmacy_id != pharmacy_id:
        raise HTTPException(404, "Organisme introuvable")
    return payer


@router.patch("/payers/{payer_id}", response_model=ThirdPartyPayerOut)
async def update_payer(
    payer_id: uuid.UUID,
    payload: ThirdPartyPayerUpdate,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    payer = await db.get(ThirdPartyPayer, payer_id)
    if not payer or payer.pharmacy_id != pharmacy_id:
        raise HTTPException(404, "Organisme introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(payer, k, v)
    await db.flush()
    return payer


# ---------- Claims ----------
@router.get("/claims", response_model=list[ThirdPartyClaimOut])
async def list_claims(
    payer_id: uuid.UUID | None = None,
    status_filter: str | None = Query(None, alias="status"),
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    stmt = select(ThirdPartyClaim).where(ThirdPartyClaim.pharmacy_id == pharmacy_id)
    if payer_id:
        stmt = stmt.where(ThirdPartyClaim.payer_id == payer_id)
    if status_filter:
        stmt = stmt.where(ThirdPartyClaim.status == status_filter)
    if date_from:
        stmt = stmt.where(ThirdPartyClaim.claim_date >= date_from)
    if date_to:
        stmt = stmt.where(ThirdPartyClaim.claim_date <= date_to)
    stmt = stmt.order_by(ThirdPartyClaim.claim_date.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---------- Bordereaux ----------
@router.post("/bordereaux", response_model=BordereauOut, status_code=201)
async def create_bordereau(
    payload: BordereauCreate,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    svc = ThirdPartyService(db, pharmacy_id)
    return await svc.generate_bordereau(
        payer_id=payload.payer_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        claim_ids=payload.claim_ids,
    )


@router.post("/bordereaux/{bordereau_id}/submit", response_model=BordereauOut)
async def submit_bordereau(
    bordereau_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    bordereau = await db.get(ThirdPartyBordereau, bordereau_id)
    if not bordereau or bordereau.pharmacy_id != pharmacy_id:
        raise HTTPException(404, "Bordereau introuvable")
    svc = ThirdPartyService(db, pharmacy_id)
    return await svc.submit_bordereau(bordereau_id)


@router.get("/bordereaux", response_model=list[BordereauOut])
async def list_bordereaux(
    payer_id: uuid.UUID | None = None,
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    stmt = select(ThirdPartyBordereau).where(ThirdPartyBordereau.pharmacy_id == pharmacy_id)
    if payer_id:
        stmt = stmt.where(ThirdPartyBordereau.payer_id == payer_id)
    if status_filter:
        stmt = stmt.where(ThirdPartyBordereau.status == status_filter)
    stmt = stmt.order_by(ThirdPartyBordereau.period_end.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/bordereaux/{bordereau_id}", response_model=BordereauDetailOut)
async def get_bordereau(
    bordereau_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    bordereau = await db.get(ThirdPartyBordereau, bordereau_id)
    if not bordereau or bordereau.pharmacy_id != pharmacy_id:
        raise HTTPException(404, "Bordereau introuvable")
    result = await db.execute(
        select(ThirdPartyClaim).where(ThirdPartyClaim.bordereau_id == bordereau_id)
    )
    claims = list(result.scalars().all())
    return BordereauDetailOut(
        **{k: getattr(bordereau, k) for k in BordereauOut.model_fields.keys()},
        claims=claims,
    )


# ---------- Payments ----------
@router.post("/payments", response_model=ThirdPartyPaymentOut, status_code=201)
async def record_payment(
    payload: ThirdPartyPaymentCreate,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    svc = ThirdPartyService(db, pharmacy_id)
    return await svc.record_bordereau_payment(
        bordereau_id=payload.bordereau_id,
        amount=payload.amount,
        payment_date=payload.payment_date,
        payment_method=payload.payment_method,
        reference=payload.reference,
        rejected_claim_ids=payload.rejected_claim_ids,
        rejection_reasons=payload.rejection_reasons,
        notes=payload.notes,
    )


@router.get("/payments", response_model=list[ThirdPartyPaymentOut])
async def list_payments(
    bordereau_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
):
    stmt = select(ThirdPartyPayment).where(ThirdPartyPayment.pharmacy_id == pharmacy_id)
    if bordereau_id:
        stmt = stmt.where(ThirdPartyPayment.bordereau_id == bordereau_id)
    stmt = stmt.order_by(ThirdPartyPayment.payment_date.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())
