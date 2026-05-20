"""add per-lot PPV and supplier catalog PPV

Revision ID: 0006_lot_ppv
Revises: 0005_operations
Create Date: 2026-05-20 11:00:00.000000

Besoin métier : au Maroc le PPV est imprimé sur la boîte et peut changer
entre arrivages. Chaque lot porte donc son propre prix de vente.
Le catalogue fournisseur peut indiquer un PPV pour pré-remplir le lot.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0006_lot_ppv"
down_revision: Union[str, None] = "0005_operations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists("product_lots", "sale_price_ttc"):
        op.add_column(
            "product_lots",
            sa.Column("sale_price_ttc", sa.Numeric(12, 4), nullable=True),
        )
    if not _column_exists("supplier_products", "ppv"):
        op.add_column(
            "supplier_products",
            sa.Column("ppv", sa.Numeric(12, 4), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("supplier_products", "ppv"):
        op.drop_column("supplier_products", "ppv")
    if _column_exists("product_lots", "sale_price_ttc"):
        op.drop_column("product_lots", "sale_price_ttc")
