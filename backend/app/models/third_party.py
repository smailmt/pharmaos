"""Tiers payants — modèle 100% générique.

Conception :
- Le pharmacien crée un ThirdPartyPayer pour chaque organisme (CNSS, CNOPS, etc.).
- Chaque organisme a un taux par défaut et des règles configurables.
- Une vente avec tiers payant génère une ThirdPartyClaim (créance sur l'organisme).
- Les claims sont regroupées en Bordereaux envoyés à l'organisme.
- Le règlement de l'organisme apporte un Payment qui solde les claims du bordereau.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    String, Boolean, Numeric, Date, ForeignKey, Text, Integer, DateTime, JSON
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class ThirdPartyPayer(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Organisme de tiers payant : CNSS, CNOPS, RAMED, mutuelle, assurance privée…

    Modèle générique : tous les paramètres métier sont configurables.
    """
    __tablename__ = "third_party_payers"

    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(50), default="public")  # public / mutual / private

    # Coordonnées
    legal_name: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(500))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(200))
    contact_person: Mapped[str | None] = mapped_column(String(200))

    # Conditions par défaut
    default_coverage_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.70"))  # 70%
    max_coverage_per_claim: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    requires_prescription: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_authorization: Mapped[bool] = mapped_column(Boolean, default=False)

    # Conditions de paiement
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=60)
    bordereau_frequency: Mapped[str] = mapped_column(String(30), default="monthly")  # weekly / biweekly / monthly

    # Règles configurables (JSON souple)
    # Ex: {"excluded_categories": ["parapharmacie"], "min_amount": 50, "non_reimbursable_only": false}
    rules: Mapped[dict] = mapped_column(JSONB, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

    clients = relationship("Client", back_populates="third_party_payer")
    claims = relationship("ThirdPartyClaim", back_populates="payer", cascade="all, delete-orphan")
    bordereaux = relationship("ThirdPartyBordereau", back_populates="payer", cascade="all, delete-orphan")


class ThirdPartyClaim(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Créance unitaire sur un tiers payant, générée par une vente.

    Statuts :
    - pending : non encore inclus dans un bordereau
    - bordereau_pending : inclus dans un bordereau pas encore envoyé
    - submitted : bordereau envoyé à l'organisme
    - paid : payé
    - rejected : refusé par l'organisme (motif dans rejection_reason)
    - partially_paid : payé partiellement
    """
    __tablename__ = "third_party_claims"

    payer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("third_party_payers.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"), index=True,
    )
    sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    bordereau_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("third_party_bordereaux.id", ondelete="SET NULL"),
        index=True,
    )

    claim_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    prescription_number: Mapped[str | None] = mapped_column(String(100))
    prescriber_name: Mapped[str | None] = mapped_column(String(200))
    prescriber_inpe: Mapped[str | None] = mapped_column(String(50))

    # Montants
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    coverage_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    payer_share: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)  # ce que l'organisme doit
    client_share: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)  # ticket modérateur

    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    payer = relationship("ThirdPartyPayer", back_populates="claims")
    bordereau = relationship("ThirdPartyBordereau", back_populates="claims")


class ThirdPartyBordereau(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Bordereau de remboursement envoyé à un organisme.

    Statuts : draft / submitted / partially_paid / paid / cancelled
    """
    __tablename__ = "third_party_bordereaux"

    payer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("third_party_payers.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    bordereau_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    payer = relationship("ThirdPartyPayer", back_populates="bordereaux")
    claims = relationship("ThirdPartyClaim", back_populates="bordereau")
    payments = relationship("ThirdPartyPayment", back_populates="bordereau", cascade="all, delete-orphan")


class ThirdPartyPayment(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Règlement reçu d'un organisme."""
    __tablename__ = "third_party_payments"

    bordereau_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("third_party_bordereaux.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    payment_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), default="transfer")
    reference: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)

    bordereau = relationship("ThirdPartyBordereau", back_populates="payments")
