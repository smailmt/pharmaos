"""
Modèles métier Jour 8 — parité avec Gebs/Sobrus.

- DayClosing : clôture caisse fin de journée (Z-report)
- PrescriptionLog : ordonnancier réglementaire (Maroc : médicaments listes I/II)
- PharmacyExchange : échanges entrée/sortie avec pharmacies confrères
- Expense : charges d'exploitation (loyer, salaires, électricité...)
- InventorySession + InventoryLine : sessions de comptage physique
"""
import uuid
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import (
    String, Boolean, DateTime, Integer, ForeignKey, Date, Text, Numeric,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin, TimestampMixin, TenantMixin


# ============ Clôture journée ============
class DayClosing(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """
    Clôture caisse de fin de journée (équivalent Z-report).
    Une fois clôturée, la journée ne peut plus être modifiée
    (les ventes sont verrouillées en lecture seule).
    """
    __tablename__ = "day_closings"

    closing_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    closed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Totaux figés au moment de la clôture
    sales_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cancelled_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    total_revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    total_cash: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    total_card: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    total_check: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    total_credit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    total_third_party: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    # Fond de caisse théorique vs déclaré (pour détecter écarts)
    cash_expected: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    cash_counted: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    cash_difference: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    notes: Mapped[str | None] = mapped_column(Text)


# ============ Ordonnancier ============
class PrescriptionLog(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """
    Ordonnancier réglementaire : trace toute dispensation de médicaments
    sur ordonnance (obligatoire au Maroc pour listes I et II).
    """
    __tablename__ = "prescription_logs"

    # Référence à la vente
    sale_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales.id", ondelete="SET NULL"), index=True
    )

    # Métadonnées ordonnance
    prescription_number: Mapped[str | None] = mapped_column(String(50), index=True)
    prescription_date: Mapped[date | None] = mapped_column(Date)
    prescriber_name: Mapped[str | None] = mapped_column(String(255))
    prescriber_inpe: Mapped[str | None] = mapped_column(String(50))  # Identifiant National Prof. Santé

    # Patient
    patient_name: Mapped[str | None] = mapped_column(String(255))
    patient_cin: Mapped[str | None] = mapped_column(String(20))  # CIN ou autre ID
    patient_age: Mapped[int | None] = mapped_column(Integer)

    # Détail de la dispensation (lignes médicaments)
    dispensed_items: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    # Ex: [{"product_id": "...", "name": "...", "quantity": 1, "list": "I"}, ...]

    # Numérotation séquentielle interne (par année)
    sequential_number: Mapped[int] = mapped_column(Integer, nullable=False)


# ============ Échanges confrères ============
class PharmacyExchange(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """
    Échange de produits avec une pharmacie confrère (très courant au Maroc).
    Direction "in" = on a reçu, "out" = on a donné.
    Le solde permet de suivre les dettes croisées.
    """
    __tablename__ = "pharmacy_exchanges"

    exchange_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # "in" / "out"

    # L'autre pharmacie (par nom + téléphone, pas dans nos users)
    partner_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    partner_phone: Mapped[str | None] = mapped_column(String(20))

    # Produit échangé
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL")
    )
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    total_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    # Statut du remboursement
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending / settled / cancelled
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    notes: Mapped[str | None] = mapped_column(Text)


# ============ Charges ============
class Expense(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """
    Charges d'exploitation : loyer, électricité, eau, salaires, abonnements...
    Utilisé pour le rapport de rentabilité (CA - achats - charges).
    """
    __tablename__ = "expenses"

    expense_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # rent / utilities / salaries / supplies / taxes / insurance / maintenance / marketing / other

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)

    # Justificatif (facture/reçu)
    receipt_reference: Mapped[str | None] = mapped_column(String(100))

    payment_method: Mapped[str] = mapped_column(String(20), default="cash")
    # cash / card / check / transfer

    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    # ex: loyer mensuel — pour template/copie automatique

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


# ============ Inventaires ============
class InventorySession(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """
    Session de comptage physique du stock (inventaire annuel ou tournant).
    Compare stock théorique vs compté, génère des ajustements.
    """
    __tablename__ = "inventory_sessions"

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    started_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), default="Inventaire")
    status: Mapped[str] = mapped_column(String(20), default="in_progress")  # in_progress / completed / cancelled

    # Périmètre : full / category / zone — pour l'instant on supporte juste full
    scope: Mapped[str] = mapped_column(String(50), default="full")

    # Stats agrégées calculées au close
    items_counted: Mapped[int] = mapped_column(Integer, default=0)
    discrepancies_count: Mapped[int] = mapped_column(Integer, default=0)
    total_value_difference: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    notes: Mapped[str | None] = mapped_column(Text)


class InventoryLine(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Ligne d'inventaire : un produit compté."""
    __tablename__ = "inventory_lines"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False
    )

    # Snapshot au moment du comptage
    quantity_theoretical: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_counted: Mapped[int] = mapped_column(Integer, nullable=False)
    difference: Mapped[int] = mapped_column(Integer, nullable=False)  # counted - theoretical

    # Valeur de l'écart (au PA pour la perte / valeur stock)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    value_difference: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    notes: Mapped[str | None] = mapped_column(Text)
    counted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
