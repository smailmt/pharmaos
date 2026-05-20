"""Clés API pour intégrations externes."""
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class ApiKey(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """
    Clé API pour les intégrations tierces (compta, ERP, mobile native, scripts).

    Format de la clé montrée à l'utilisateur : `pk_live_xxxxxxxxxxxxxxxx`
    Seul le HASH sha256 est stocké. La clé en clair n'est montrée qu'une fois à la création.
    """
    __tablename__ = "api_keys"

    # Métadonnées visibles
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))

    # Préfixe visible pour identification (8 premiers caractères de la clé)
    key_prefix: Mapped[str] = mapped_column(String(20), index=True, nullable=False)

    # Hash sha256 de la clé complète (jamais la clé en clair)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)

    # Scopes (granularité fine, séparés par espace) : "products:read sales:write" etc.
    # Vide ou null = full access
    scopes: Mapped[str | None] = mapped_column(String(500))

    # Rate limit par minute (None = défaut global)
    rate_limit_per_min: Mapped[int | None] = mapped_column(Integer)

    # Utilisateur qui a créé la clé
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    # Stats
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # État
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
