"""Pharmacy = tenant root. Chaque tenant a ses utilisateurs, produits, clients, etc."""
import uuid
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, UUIDMixin, TimestampMixin


class Pharmacy(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pharmacies"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(200))
    ice: Mapped[str | None] = mapped_column(String(50), index=True)  # Identifiant Commun Entreprise (Maroc)
    if_number: Mapped[str | None] = mapped_column(String(50))  # Identifiant Fiscal
    rc_number: Mapped[str | None] = mapped_column(String(50))  # Registre Commerce
    cnss_number: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(200))
    pharmacist_in_charge: Mapped[str | None] = mapped_column(String(200))
    inpe_number: Mapped[str | None] = mapped_column(String(50))  # N° d'inscription à l'Ordre

    plan: Mapped[str] = mapped_column(String(50), default="trial")  # trial / starter / pro / enterprise
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    users = relationship("User", back_populates="pharmacy", cascade="all, delete-orphan")
