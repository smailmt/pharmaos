"""add operations tables (day_closings, prescription_logs, exchanges, expenses, inventory)

Revision ID: 0005_operations
Revises: 0004_webhook_secret_encrypted
Create Date: 2026-05-20 09:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
from app.models import Base
from app.models.operations import (
    DayClosing, PrescriptionLog, PharmacyExchange, Expense,
    InventorySession, InventoryLine,
)

revision: str = "0005_operations"
down_revision: Union[str, None] = "0004_webhook_secret_encrypted"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, tables=[
        DayClosing.__table__,
        PrescriptionLog.__table__,
        PharmacyExchange.__table__,
        Expense.__table__,
        InventorySession.__table__,
        InventoryLine.__table__,
    ])


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, tables=[
        InventoryLine.__table__,
        InventorySession.__table__,
        Expense.__table__,
        PharmacyExchange.__table__,
        PrescriptionLog.__table__,
        DayClosing.__table__,
    ])
