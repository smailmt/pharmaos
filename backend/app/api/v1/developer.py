"""Router /developer : gestion des clés API et webhooks par le pharmacien."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user, get_current_pharmacy_id
from app.models.user import User
from app.services.api_key_service import ApiKeyService
from app.services.webhook_service import WebhookService
from app.schemas.developer import (
    ApiKeyCreate, ApiKeyOut, ApiKeyCreateResponse,
    WebhookEndpointCreate, WebhookEndpointOut, WebhookEndpointCreateResponse,
    WebhookDeliveryOut,
)
from app.models.webhook import WebhookDelivery
from sqlalchemy import select

router = APIRouter(prefix="/developer", tags=["developer"])


# ============ API Keys ============
@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=201)
async def create_api_key(
    payload: ApiKeyCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Crée une nouvelle clé API.

    **⚠️ La clé en clair n'est retournée qu'une seule fois.**
    Stockez-la immédiatement, vous ne pourrez plus la récupérer ensuite.
    """
    svc = ApiKeyService(db, user.pharmacy_id)
    api_key, plaintext = await svc.create(
        name=payload.name,
        description=payload.description,
        scopes=payload.scopes,
        rate_limit_per_min=payload.rate_limit_per_min,
        created_by_user_id=user.id,
        env=payload.env,
    )
    return ApiKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        description=api_key.description,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes,
        rate_limit_per_min=api_key.rate_limit_per_min,
        last_used_at=api_key.last_used_at,
        usage_count=api_key.usage_count,
        is_active=api_key.is_active,
        revoked_at=api_key.revoked_at,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
        key=plaintext,
    )


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
    db: AsyncSession = Depends(get_db),
):
    svc = ApiKeyService(db, pharmacy_id)
    return await svc.list()


@router.delete("/api-keys/{api_key_id}", response_model=ApiKeyOut)
async def revoke_api_key(
    api_key_id: uuid.UUID,
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
    db: AsyncSession = Depends(get_db),
):
    """Révoque immédiatement une clé. Elle ne pourra plus être utilisée."""
    svc = ApiKeyService(db, pharmacy_id)
    api_key = await svc.revoke(api_key_id)
    if not api_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clé introuvable")
    return api_key


# ============ Webhooks ============
@router.post("/webhooks", response_model=WebhookEndpointCreateResponse, status_code=201)
async def create_webhook(
    payload: WebhookEndpointCreate,
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Souscrit un endpoint webhook.

    **⚠️ Le secret HMAC n'est retourné qu'une seule fois.**
    Utilisez-le pour vérifier la signature `X-PharmaOS-Signature` des requêtes entrantes.
    """
    svc = WebhookService(db, pharmacy_id)
    endpoint, secret = await svc.create_endpoint(
        url=payload.url, events=payload.events, description=payload.description
    )
    return WebhookEndpointCreateResponse(
        id=endpoint.id,
        url=endpoint.url,
        description=endpoint.description,
        secret_prefix=endpoint.secret_prefix,
        events=endpoint.events,
        is_active=endpoint.is_active,
        last_delivery_at=endpoint.last_delivery_at,
        last_success_at=endpoint.last_success_at,
        consecutive_failures=endpoint.consecutive_failures,
        created_at=endpoint.created_at,
        secret=secret,
    )


@router.get("/webhooks", response_model=list[WebhookEndpointOut])
async def list_webhooks(
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
    db: AsyncSession = Depends(get_db),
):
    svc = WebhookService(db, pharmacy_id)
    return await svc.list_endpoints()


@router.delete("/webhooks/{endpoint_id}", status_code=204)
async def delete_webhook(
    endpoint_id: uuid.UUID,
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
    db: AsyncSession = Depends(get_db),
):
    svc = WebhookService(db, pharmacy_id)
    deleted = await svc.delete_endpoint(endpoint_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook introuvable")
    return None


@router.get("/webhooks/{endpoint_id}/deliveries", response_model=list[WebhookDeliveryOut])
async def list_deliveries(
    endpoint_id: uuid.UUID,
    limit: int = 50,
    pharmacy_id: uuid.UUID = Depends(get_current_pharmacy_id),
    db: AsyncSession = Depends(get_db),
):
    """Historique des livraisons d'un webhook (succès et échecs)."""
    result = await db.execute(
        select(WebhookDelivery)
        .where(
            WebhookDelivery.pharmacy_id == pharmacy_id,
            WebhookDelivery.endpoint_id == endpoint_id,
        )
        .order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ============ Documentation des events ============
SUPPORTED_EVENTS = [
    {
        "type": "sale.created",
        "description": "Une vente vient d'être enregistrée à la caisse.",
        "example_data": {
            "id": "uuid",
            "sale_number": "V-202605-00001",
            "total_ttc": "150.00",
            "client_id": "uuid|null",
            "items_count": 3,
        },
    },
    {
        "type": "product.low_stock",
        "description": "Un produit est passé sous son seuil minimum de stock.",
        "example_data": {
            "id": "uuid",
            "code": "ASP500",
            "name": "Aspirine 500mg",
            "stock_quantity": 3,
            "stock_min": 10,
        },
    },
]


@router.get("/events", tags=["developer"])
async def list_supported_events(_user: User = Depends(get_current_user)):
    """
    Liste des types d'événements webhook disponibles.

    Vous pouvez vous abonner avec :
    - Le type exact (ex: `"sale.created"`)
    - `"*"` pour recevoir tous les événements
    """
    return SUPPORTED_EVENTS
