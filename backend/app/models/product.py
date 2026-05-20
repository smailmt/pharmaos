"""Produit : médicament, parapharmacie. Lots gérés à part pour péremption."""
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy import String, Boolean, Numeric, Integer, Date, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class Product(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_name_trgm", "name", postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}),
        Index("ix_products_dci_trgm", "dci", postgresql_using="gin", postgresql_ops={"dci": "gin_trgm_ops"}),
    )

    code: Mapped[str | None] = mapped_column(String(50), index=True)  # code interne pharmacie
    barcode: Mapped[str | None] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    dci: Mapped[str | None] = mapped_column(String(300))  # Dénomination Commune Internationale
    laboratory: Mapped[str | None] = mapped_column(String(200))
    form: Mapped[str | None] = mapped_column(String(100))  # comprimé, sirop, etc.
    dosage: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(100))

    # Prix
    purchase_price_ht: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    sale_price_ttc: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)  # PPV au Maroc
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.07"))

    # Stock global (somme des lots)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    stock_min: Mapped[int] = mapped_column(Integer, default=0)
    stock_max: Mapped[int] = mapped_column(Integer, default=0)

    is_prescription_required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_psychotropic: Mapped[bool] = mapped_column(Boolean, default=False)
    is_reimbursable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    notes: Mapped[str | None] = mapped_column(Text)

    lots = relationship("ProductLot", back_populates="product", cascade="all, delete-orphan")


class ProductLot(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Lot d'un produit : quantité + date de péremption."""
    __tablename__ = "product_lots"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lot_number: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    expiration_date: Mapped[date | None] = mapped_column(Date)
    purchase_price_ht: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    # PPV imprimé sur la boîte de CE lot. Peut différer d'un lot à l'autre
    # (le prix réglementaire change entre arrivages). NULL = utiliser le prix du produit.
    sale_price_ttc: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))

    product = relationship("Product", back_populates="lots")
