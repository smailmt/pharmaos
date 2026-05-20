"""init extensions

Revision ID: 0001_init_extensions
Revises: 
Create Date: 2026-05-18 13:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0001_init_extensions"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp";')
