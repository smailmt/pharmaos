"""Fournisseurs — grossistes, laboratoires, confrères.

Flux métier complet :
1. Supplier (fiche fournisseur, conditions)
2. SupplierProduct (catalogue : prix, remise, code fournisseur, par produit/fournisseur)
3. PurchaseOrder (bon de commande, statuts : draft / sent / partial / received / cancelled)
4. DeliveryNote (BL réceptionné, génère mouvement stock)
5. SupplierInvoice (facture fournisseur, déclenche dette)
6. SupplierPayment (paiement émis, solde la dette)
7. SupplierReturn (retour fournisseur — produits périmés, non-conformes)
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    String, Boolean, Numeric, Date, ForeignKey, Text, Integer, DateTime
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class Supplier(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Fournisseur : grossiste, laboratoire, confrère."""
    __tablename__ = "suppliers"

    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), default="wholesaler")  # wholesaler / laboratory / colleague

    legal_name: Mapped[str | None] = mapped_column(String(200))
    ice: Mapped[str | None] = mapped_column(String(50), index=True)
    if_number: Mapped[str | None] = mapped_column(String(50))
    rc_number: Mapped[str | None] = mapped_column(String(50))

    address: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(200))
    website: Mapped[str | None] = mapped_column(String(200))
    contact_person: Mapped[str | None] = mapped_column(String(200))

    # Conditions commerciales par défaut
    default_discount_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)  # plafond consenti par le fournisseur
    delivery_lead_time_days: Mapped[int] = mapped_column(Integer, default=1)
    min_order_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    # Informations bancaires
    bank_name: Mapped[str | None] = mapped_column(String(200))
    bank_rib: Mapped[str | None] = mapped_column(String(50))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

    products = relationship("SupplierProduct", back_populates="supplier", cascade="all, delete-orphan")
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier", cascade="all, delete-orphan")
    invoices = relationship("SupplierInvoice", back_populates="supplier", cascade="all, delete-orphan")


class SupplierProduct(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Catalogue : association produit ↔ fournisseur, avec conditions spécifiques.

    Un produit peut avoir plusieurs fournisseurs.
    Un fournisseur peut être le "préféré" pour un produit.
    """
    __tablename__ = "supplier_products"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    supplier_code: Mapped[str | None] = mapped_column(String(100))  # code chez le fournisseur
    purchase_price_ht: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    # PPV indiqué par le fournisseur (sert à pré-remplir le prix du lot à la réception)
    ppv: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0)
    min_order_quantity: Mapped[int] = mapped_column(Integer, default=1)
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False)
    last_purchase_date: Mapped[date | None] = mapped_column(Date)

    supplier = relationship("Supplier", back_populates="products")


class PurchaseOrder(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Bon de commande fournisseur.

    Statuts : draft / sent / partially_received / received / cancelled
    """
    __tablename__ = "purchase_orders"

    order_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    order_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Totaux calculés
    total_ht: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_vat: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_ttc: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    supplier = relationship("Supplier", back_populates="purchase_orders")
    items = relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan", lazy="selectin")
    delivery_notes = relationship("DeliveryNote", back_populates="purchase_order")


class PurchaseOrderItem(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "purchase_order_items"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, default=0)
    unit_price_ht: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.07"))
    line_total_ht: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    line_total_ttc: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    purchase_order = relationship("PurchaseOrder", back_populates="items")


class DeliveryNote(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Bon de Livraison reçu — déclenche l'entrée en stock."""
    __tablename__ = "delivery_notes"

    delivery_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="SET NULL"),
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    delivery_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    received_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
    )

    total_ht: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_ttc: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    has_discrepancies: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30), default="received")  # received / validated / invoiced
    notes: Mapped[str | None] = mapped_column(Text)

    purchase_order = relationship("PurchaseOrder", back_populates="delivery_notes")
    items = relationship("DeliveryNoteItem", back_populates="delivery_note", cascade="all, delete-orphan", lazy="selectin")


class DeliveryNoteItem(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "delivery_note_items"

    delivery_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("delivery_notes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    lot_number: Mapped[str | None] = mapped_column(String(100))
    expiration_date: Mapped[date | None] = mapped_column(Date)
    quantity_ordered: Mapped[int] = mapped_column(Integer, default=0)
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_ht: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.07"))
    line_total_ttc: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    discrepancy_note: Mapped[str | None] = mapped_column(Text)

    delivery_note = relationship("DeliveryNote", back_populates="items")


class SupplierInvoice(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Facture reçue d'un fournisseur — crée la dette en compta auxiliaire.

    Statuts : pending / partially_paid / paid / overdue / disputed / cancelled
    """
    __tablename__ = "supplier_invoices"

    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    received_date: Mapped[date] = mapped_column(Date, default=date.today)

    total_ht: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_vat: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_ttc: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    # Liens vers les BL couverts par cette facture (JSON souple)
    delivery_note_ids: Mapped[list] = mapped_column(JSONB, default=list)
    notes: Mapped[str | None] = mapped_column(Text)

    supplier = relationship("Supplier", back_populates="invoices")
    payments = relationship("SupplierPayment", back_populates="invoice", cascade="all, delete-orphan")

    @property
    def amount_remaining(self) -> Decimal:
        return self.total_ttc - self.amount_paid

    @property
    def is_overdue(self) -> bool:
        return self.status in ("pending", "partially_paid") and self.due_date < date.today()


class SupplierPayment(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Paiement émis vers un fournisseur."""
    __tablename__ = "supplier_payments"

    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("supplier_invoices.id", ondelete="SET NULL"),
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    payment_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), default="transfer")  # cash / check / transfer / card
    reference: Mapped[str | None] = mapped_column(String(200))  # n° chèque, n° virement
    bank_name: Mapped[str | None] = mapped_column(String(200))
    check_due_date: Mapped[date | None] = mapped_column(Date)  # pour chèques différés
    notes: Mapped[str | None] = mapped_column(Text)

    invoice = relationship("SupplierInvoice", back_populates="payments")


class SupplierReturn(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Retour fournisseur (périmé, non-conforme, surplus)."""
    __tablename__ = "supplier_returns"

    return_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    return_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    reason: Mapped[str] = mapped_column(String(100), default="expired")  # expired / damaged / wrong / surplus
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    credit_note_received: Mapped[bool] = mapped_column(Boolean, default=False)
    credit_note_number: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    notes: Mapped[str | None] = mapped_column(Text)

    items = relationship("SupplierReturnItem", back_populates="supplier_return", cascade="all, delete-orphan")


class SupplierReturnItem(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "supplier_return_items"

    return_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("supplier_returns.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    lot_number: Mapped[str | None] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_ht: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    supplier_return = relationship("SupplierReturn", back_populates="items")
