"""
Fixtures pytest pour les tests E2E PharmaOS.

Setup :
- APP_ENV=test → app/db/session.py utilise NullPool (pas de conflit de loop)
- BDD dédiée `pharmaos_test`
- Schéma créé au premier test, puis chaque test truncate les tables
"""
import os
import sys
from pathlib import Path

# Variables d'env AVANT tout import app
# IMPORTANT : on force POSTGRES_DB=pharmaos_test (pas setdefault) pour ne jamais
# truncater la DB de production même si POSTGRES_DB est déjà défini dans l'env Docker.
os.environ["APP_ENV"] = "test"
os.environ["POSTGRES_DB"] = "pharmaos_test"
os.environ.setdefault("SECRET_KEY", "test-secret-key-min-32-chars-long-for-testing-only")
os.environ.setdefault("POSTGRES_USER", "pharmaos")
os.environ.setdefault("POSTGRES_PASSWORD", "pharmaos_dev")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest_asyncio  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402

from app.models import (  # noqa: E402, F401
    Pharmacy, User, Product, ProductLot,
    Client, CreditEntry, CreditDueDate, CreditReminder,
    ThirdPartyPayer, ThirdPartyClaim, ThirdPartyBordereau, ThirdPartyPayment,
    Supplier, SupplierProduct, PurchaseOrder, PurchaseOrderItem,
    DeliveryNote, DeliveryNoteItem, SupplierInvoice, SupplierPayment,
    SupplierReturn, SupplierReturnItem, Sale, SaleItem,
)


_schema_initialized = False


async def _ensure_clean_schema():
    """Crée le schéma la 1re fois, truncate ensuite. Engine de l'app."""
    global _schema_initialized
    async with engine.begin() as conn:
        if not _schema_initialized:
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pg_trgm"'))
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
            _schema_initialized = True
        else:
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))


@pytest_asyncio.fixture
async def client():
    """Client HTTP async pour les tests E2E (schéma propre)."""
    await _ensure_clean_schema()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def registered_user(client):
    payload = {
        "email": "test@example.com",
        "password": "testpass123",
        "full_name": "Test User",
        "pharmacy": {
            "name": "Pharmacie Test",
            "city": "Casablanca",
            "ice": "001234567000089",
        },
        "plan": "pro",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


@pytest_asyncio.fixture
async def auth_headers(registered_user):
    return {"Authorization": f"Bearer {registered_user['access_token']}"}
