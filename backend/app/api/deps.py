"""Dépendances FastAPI : DB session, current_user, current_pharmacy_id."""
import uuid
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.services.api_key_service import ApiKeyService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token manquant")
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Type de token invalide")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token sans sujet")
    except ValueError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e))

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Utilisateur inconnu ou inactif")
    return user


async def get_current_pharmacy_id(user: User = Depends(get_current_user)) -> uuid.UUID:
    return user.pharmacy_id


def require_role(*roles: str):
    """Décorateur pour les endpoints réservés à certains rôles."""
    async def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Rôle requis : {', '.join(roles)} (vous : {user.role})",
            )
        return user
    return checker


def require_permission(permission: str):
    """Décorateur pour les endpoints filtrés par permission atomique."""
    from app.core.permissions import has_permission
    async def checker(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user.role, permission):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Permission requise : {permission}",
            )
        return user
    return checker


async def get_pharmacy_id_dual(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    api_key: str | None = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    """
    Auth duale : accepte un JWT (header Authorization) OU une clé API (header X-API-Key).
    Stocke aussi `auth_method` et `api_key_id` sur la requête pour le rate-limiting / logs.
    """
    # JWT prioritaire si présent
    if token:
        try:
            payload = decode_token(token)
            if payload.get("type") == "access":
                user_id = payload.get("sub")
                if user_id:
                    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
                    user = result.scalar_one_or_none()
                    if user and user.is_active:
                        request.state.auth_method = "jwt"
                        request.state.user_id = user.id
                        return user.pharmacy_id
        except ValueError:
            pass

    # Sinon, essayer la clé API
    if api_key:
        # On a besoin du pharmacy_id pour le ApiKeyService.verify, mais la clé l'identifie
        # On cherche directement par hash
        from app.services.api_key_service import hash_key
        from app.services.rate_limit_service import check_rate_limit, DEFAULT_RATE_LIMIT_PER_MIN
        from app.models.api_key import ApiKey
        from datetime import datetime, timezone

        key_hash = hash_key(api_key)
        result = await db.execute(
            select(ApiKey).where(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active == True,
            )
        )
        api_key_obj = result.scalar_one_or_none()
        if api_key_obj:
            if api_key_obj.expires_at and api_key_obj.expires_at < datetime.now(timezone.utc):
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Clé API expirée")

            # Rate limit check
            limit = api_key_obj.rate_limit_per_min or DEFAULT_RATE_LIMIT_PER_MIN
            allowed, current, max_lim = await check_rate_limit(
                key=f"ratelimit:apikey:{api_key_obj.id}",
                limit_per_minute=limit,
            )
            if not allowed:
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    f"Rate limit dépassé ({current}/{max_lim} requêtes par minute)",
                    headers={"Retry-After": "60"},
                )

            # Update stats
            api_key_obj.last_used_at = datetime.now(timezone.utc)
            api_key_obj.usage_count = (api_key_obj.usage_count or 0) + 1
            request.state.auth_method = "api_key"
            request.state.api_key_id = api_key_obj.id
            return api_key_obj.pharmacy_id

    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Authentification requise (Authorization: Bearer <jwt> ou X-API-Key: <key>)",
    )
