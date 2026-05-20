"""Ventes (caisse) — intègre clients, crédits et tiers payants."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    String, Boolean, Numeric, Date, ForeignKey, Text, Integer, DateTime
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class Sale(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Vente au comptoir.

    Modes de paiement :
    - cash, card, check, transfer (encaissement immédiat)
    - credit (vente à crédit — génère CreditEntry)
    - third_party (tiers payant — génère ThirdPartyClaim pour la part payeur)
    - mixed (combinaison : ex 70% tiers payant + 30% crédit client)
    """
    __tablename__ = "sales"

    sale_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sale_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    cashier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"), index=True,
    )

    # Ordonnance
    has_prescription: Mapped[bool] = mapped_column(Boolean, default=False)
    prescription_number: Mapped[str | None] = mapped_column(String(100))
    prescriber_name: Mapped[str | None] = mapped_column(String(200))
    prescriber_inpe: Mapped[str | None] = mapped_column(String(50))

    # Tiers payant
    third_party_payer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("third_party_payers.id", ondelete="SET NULL"),
    )
    third_party_coverage_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    # Totaux
    subtotal_ht: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_vat: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_ttc: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    # Répartition du paiement
    payer_share: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)  # tiers payant
    client_share: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)  # à charge client
    paid_cash: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    paid_card: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    paid_check: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    paid_credit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)  # part en crédit client

    payment_method: Mapped[str] = mapped_column(String(50), default="cash")
    status: Mapped[str] = mapped_column(String(30), default="completed", index=True)  # completed / cancelled / refunded

    loyalty_points_earned: Mapped[int] = mapped_column(Integer, default=0)
    loyalty_points_used: Mapped[int] = mapped_column(Integer, default=0)

    notes: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items = relationship(
        "SaleItem",
        back_populates="sale",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class SaleItem(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "sale_items"

    sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    lot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_lots.id", ondelete="SET NULL"),
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_ht: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit_price_ttc: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.07"))
    line_total_ttc: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    is_reimbursable: Mapped[bool] = mapped_column(Boolean, default=True)

    sale = relationship("Sale", back_populates="items")
