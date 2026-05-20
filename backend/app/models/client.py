"""Clients & crédits clients.

Conception métier :
- Un Client a un compte (Account) qui contient son solde.
- Chaque vente à crédit génère une CreditEntry (positif = créance pharmacie).
- Chaque paiement génère une CreditEntry négative.
- Les échéances (CreditDueDate) permettent de découper le remboursement.
- Les relances (CreditReminder) tracent les actions de recouvrement.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    String, Boolean, Numeric, Date, ForeignKey, Text, Integer, DateTime
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class Client(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Client de la pharmacie."""
    __tablename__ = "clients"

    code: Mapped[str | None] = mapped_column(String(50), index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(30), index=True)
    email: Mapped[str | None] = mapped_column(String(200))
    cin: Mapped[str | None] = mapped_column(String(30), index=True)  # Carte Identité Nationale
    birth_date: Mapped[date | None] = mapped_column(Date)
    address: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str | None] = mapped_column(String(100))

    # Crédit
    credit_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    default_payment_terms_days: Mapped[int] = mapped_column(Integer, default=30)

    # Tiers payant (rattachement)
    third_party_payer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("third_party_payers.id", ondelete="SET NULL"),
        index=True,
    )
    third_party_card_number: Mapped[str | None] = mapped_column(String(100))
    third_party_coverage_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    # Fidélité
    loyalty_points: Mapped[int] = mapped_column(Integer, default=0)

    # Scoring simple
    risk_score: Mapped[int] = mapped_column(Integer, default=0)  # 0-100, plus haut = plus risqué
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    credit_entries = relationship("CreditEntry", back_populates="client", cascade="all, delete-orphan")
    due_dates = relationship("CreditDueDate", back_populates="client", cascade="all, delete-orphan")
    third_party_payer = relationship("ThirdPartyPayer", back_populates="clients")


class CreditEntry(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Mouvement de crédit client : vente à crédit (+) ou paiement (-).

    Le solde courant = somme algébrique des entries.
    """
    __tablename__ = "credit_entries"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)  # sale / payment / adjustment / writeoff
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)  # signé : + débit client, - paiement
    entry_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)

    # Référence au document source
    sale_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales.id", ondelete="SET NULL"), index=True,
    )
    payment_method: Mapped[str | None] = mapped_column(String(50))  # cash / card / check / transfer
    reference: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)

    client = relationship("Client", back_populates="credit_entries")


class CreditDueDate(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Échéance de paiement.

    Permet de gérer un échéancier (paiement en plusieurs fois).
    Statuts : pending / partial / paid / overdue / cancelled
    """
    __tablename__ = "credit_due_dates"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    sale_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales.id", ondelete="SET NULL"), index=True,
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount_due: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    client = relationship("Client", back_populates="due_dates")

    @property
    def amount_remaining(self) -> Decimal:
        return self.amount_due - self.amount_paid

    @property
    def is_overdue(self) -> bool:
        return self.status in ("pending", "partial") and self.due_date < date.today()


class CreditReminder(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Trace des relances effectuées sur un client en retard."""
    __tablename__ = "credit_reminders"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    due_date_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("credit_due_dates.id", ondelete="SET NULL"),
    )
    channel: Mapped[str] = mapped_column(String(30), default="manual")  # manual / sms / email / call / whatsapp
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    message: Mapped[str | None] = mapped_column(Text)
    response: Mapped[str | None] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
