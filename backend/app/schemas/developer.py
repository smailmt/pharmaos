"""Schémas pour clés API et webhooks."""
import uuid
from datetime import datetime
from app.schemas.common import APIModel


# ---------- API Keys ----------
class ApiKeyCreate(APIModel):
    name: str
    description: str | None = None
    scopes: str | None = None  # ex: "products:read sales:read"
    rate_limit_per_min: int | None = None
    env: str = "live"  # "live" ou "test"


class ApiKeyOut(APIModel):
    id: uuid.UUID
    name: str
    description: str | None
    key_prefix: str
    scopes: str | None
    rate_limit_per_min: int | None
    last_used_at: datetime | None
    usage_count: int
    is_active: bool
    revoked_at: datetime | None
    expires_at: datetime | None
    created_at: datetime


class ApiKeyCreateResponse(ApiKeyOut):
    """Réponse spéciale à la création — contient la clé en clair UNE SEULE FOIS."""
    key: str  # pk_live_xxxxxxxxxxxx (à sauvegarder par l'utilisateur)


# ---------- Webhooks ----------
class WebhookEndpointCreate(APIModel):
    url: str
    events: list[str]  # ["sale.created", "product.low_stock", "*"]
    description: str | None = None


class WebhookEndpointOut(APIModel):
    id: uuid.UUID
    url: str
    description: str | None
    secret_prefix: str
    events: list[str]
    is_active: bool
    last_delivery_at: datetime | None
    last_success_at: datetime | None
    consecutive_failures: int
    created_at: datetime


class WebhookEndpointCreateResponse(WebhookEndpointOut):
    """À la création, on renvoie aussi le secret HMAC en clair UNE SEULE FOIS."""
    secret: str  # whsec_xxxxxxxx


class WebhookDeliveryOut(APIModel):
    id: uuid.UUID
    endpoint_id: uuid.UUID
    event_type: str
    event_id: str
    status: str
    http_status: int | None
    attempt_count: int
    error_message: str | None
    delivered_at: datetime | None
    created_at: datetime
