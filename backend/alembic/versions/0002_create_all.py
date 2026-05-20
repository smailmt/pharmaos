"""create all tables

Revision ID: 0002_create_all
Revises: 0001_init_extensions
Create Date: 2026-05-18 13:10:00.000000

Cette migration crée toutes les tables en utilisant les metadata SQLAlchemy.
Approche pragmatique pour bootstrap rapide. Les migrations suivantes peuvent
être générées avec `alembic revision --autogenerate`.
"""
from typing import Sequence, Union
from alembic import op
from app.models import Base

revision: str = "0002_create_all"
down_revision: Union[str, None] = "0001_init_extensions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
