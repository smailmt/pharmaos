"""Webhooks sortants : abonnement à des événements + livraisons."""
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class WebhookEndpoint(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """
    Endpoint webhook : URL HTTPS qui reçoit les événements d'une pharmacie.
    Chaque payload est signé HMAC-SHA256 avec le `secret`.
    """
    __tablename__ = "webhook_endpoints"

    url: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))

    # Secret pour signature HMAC (montré une fois à la création)
    # On stocke : (1) le hash sha256 pour vérification, (2) le secret chiffré Fernet
    # pour pouvoir resigner les payloads à l'envoi.
    secret_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    secret_encrypted: Mapped[str] = mapped_column(String(500), nullable=False)
    secret_prefix: Mapped[str] = mapped_column(String(20), nullable=False)  # 8 premiers chars du secret

    # Events souscrits (ex: ["sale.created", "product.low_stock"])
    events: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    # État
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Stats
    last_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class WebhookDelivery(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Enregistre chaque tentative de livraison d'un événement."""
    __tablename__ = "webhook_deliveries"

    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(100), nullable=False)  # idempotency key

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Résultat de la dernière tentative
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # pending / delivered / failed / retrying

    http_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
