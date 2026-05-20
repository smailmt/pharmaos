"""add developer tables (api_keys, webhooks)

Revision ID: 0003_developer
Revises: 0002_create_all
Create Date: 2026-05-19 09:00:00.000000

Ajoute les tables api_keys, webhook_endpoints, webhook_deliveries.
S'appuie sur Base.metadata.create_all (idempotent).
"""
from typing import Sequence, Union
from alembic import op
from app.models import Base
from app.models.api_key import ApiKey  # noqa: F401
from app.models.webhook import WebhookEndpoint, WebhookDelivery  # noqa: F401

revision: str = "0003_developer"
down_revision: Union[str, None] = "0002_create_all"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # Crée uniquement les tables qui n'existent pas (idempotent)
    Base.metadata.create_all(bind=bind, tables=[
        ApiKey.__table__,
        WebhookEndpoint.__table__,
        WebhookDelivery.__table__,
    ])


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, tables=[
        WebhookDelivery.__table__,
        WebhookEndpoint.__table__,
        ApiKey.__table__,
    ])
