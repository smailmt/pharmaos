"""Router : authentification + gestion pharmacy/user."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
)
from app.models.pharmacy import Pharmacy
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse, RefreshRequest,
    UserOut, PharmacyOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Inscription : crée la pharmacy + un user owner."""
    # Vérif unicité email
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(409, "Email déjà utilisé")

    pharmacy = Pharmacy(
        name=payload.pharmacy.name,
        legal_name=payload.pharmacy.legal_name,
        ice=payload.pharmacy.ice,
        if_number=payload.pharmacy.if_number,
        rc_number=payload.pharmacy.rc_number,
        cnss_number=payload.pharmacy.cnss_number,
        address=payload.pharmacy.address,
        city=payload.pharmacy.city,
        phone=payload.pharmacy.phone,
        email=payload.pharmacy.email,
        pharmacist_in_charge=payload.pharmacy.pharmacist_in_charge,
        inpe_number=payload.pharmacy.inpe_number,
        plan=payload.plan or "trial",
    )
    db.add(pharmacy)
    await db.flush()

    user = User(
        pharmacy_id=pharmacy.id,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role="owner",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    access = create_access_token(str(user.id), str(pharmacy.id), user.role)
    refresh = create_refresh_token(str(user.id), str(pharmacy.id))
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user=UserOut.model_validate(user),
        pharmacy=PharmacyOut.model_validate(pharmacy),
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(401, "Identifiants invalides")
    if not user.is_active:
        raise HTTPException(403, "Compte désactivé")

    pharmacy = await db.get(Pharmacy, user.pharmacy_id)
    if not pharmacy or not pharmacy.is_active:
        raise HTTPException(403, "Pharmacie désactivée")

    access = create_access_token(str(user.id), str(pharmacy.id), user.role)
    refresh = create_refresh_token(str(user.id), str(pharmacy.id))
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        user=UserOut.model_validate(user),
        pharmacy=PharmacyOut.model_validate(pharmacy),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        data = decode_token(payload.refresh_token)
        if data.get("type") != "refresh":
            raise HTTPException(401, "Type de token invalide")
    except ValueError as e:
        raise HTTPException(401, str(e))

    user = await db.get(User, uuid.UUID(data["sub"]))
    if not user or not user.is_active:
        raise HTTPException(401, "Utilisateur invalide")
    pharmacy = await db.get(Pharmacy, user.pharmacy_id)

    access = create_access_token(str(user.id), str(pharmacy.id), user.role)
    new_refresh = create_refresh_token(str(user.id), str(pharmacy.id))
    return TokenResponse(
        access_token=access,
        refresh_token=new_refresh,
        user=UserOut.model_validate(user),
        pharmacy=PharmacyOut.model_validate(pharmacy),
    )


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.get("/pharmacy", response_model=PharmacyOut)
async def get_my_pharmacy(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Infos de la pharmacie courante (header de tickets / factures)."""
    pharmacy = await db.get(Pharmacy, user.pharmacy_id)
    if not pharmacy:
        raise HTTPException(404, "Pharmacie introuvable")
    return pharmacy
