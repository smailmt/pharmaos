"""add webhook secret_encrypted column

Revision ID: 0004_webhook_secret_encrypted
Revises: 0003_developer
Create Date: 2026-05-19 10:00:00.000000

Note : la migration 0002 crée la table via Base.metadata.create_all(...) qui
inclut déjà la colonne secret_encrypted. Cette migration est donc no-op
sur les bases créées à partir de 0002, mais on la garde pour les bases
historiques antérieures.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0004_webhook_secret_encrypted"
down_revision: Union[str, None] = "0003_developer"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # Idempotent : skip si la colonne existe déjà (cas standard depuis 0002)
    if _column_exists("webhook_endpoints", "secret_encrypted"):
        return

    op.add_column(
        "webhook_endpoints",
        sa.Column("secret_encrypted", sa.String(500), nullable=True),
    )
    op.execute(
        "UPDATE webhook_endpoints SET secret_encrypted = '' WHERE secret_encrypted IS NULL"
    )
    op.alter_column("webhook_endpoints", "secret_encrypted", nullable=False)


def downgrade() -> None:
    if _column_exists("webhook_endpoints", "secret_encrypted"):
        op.drop_column("webhook_endpoints", "secret_encrypted")
