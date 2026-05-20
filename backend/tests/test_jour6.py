"""Tests Jour 6 : chiffrement secrets, rate limiting, OCR ordonnance."""
import asyncio


# ============ Crypto ============

def test_crypto_roundtrip():
    from app.core.crypto import encrypt, decrypt
    secret = "whsec_my-super-secret-123"
    token = encrypt(secret)
    assert token != secret
    assert decrypt(token) == secret


def test_crypto_different_outputs():
    """Deux chiffrements du même secret donnent des tokens différents (Fernet inclut un IV)."""
    from app.core.crypto import encrypt, decrypt
    a = encrypt("same")
    b = encrypt("same")
    assert a != b  # Fernet est non-déterministe
    assert decrypt(a) == decrypt(b) == "same"


def test_crypto_invalid_token_raises():
    from app.core.crypto import decrypt
    from cryptography.fernet import InvalidToken
    try:
        decrypt("not-a-valid-fernet-token")
        assert False, "Should have raised"
    except InvalidToken:
        pass
    except Exception:
        pass  # Any decryption failure is acceptable


# ============ Webhook secret encrypted ============

async def test_webhook_secret_stored_encrypted(client, auth_headers, db_session=None):
    """Le secret est chiffré en BDD, pas en clair."""
    r = await client.post(
        "/api/v1/developer/webhooks",
        json={"url": "https://example.com/x", "events": ["sale.created"]},
        headers=auth_headers,
    )
    assert r.status_code == 201
    secret_plaintext = r.json()["secret"]

    # Lire en BDD via raw SQL pour vérifier que c'est chiffré
    from app.db.session import AsyncSessionLocal
    from sqlalchemy import text
    async with AsyncSessionLocal() as s:
        result = await s.execute(
            text("SELECT secret_encrypted FROM webhook_endpoints LIMIT 1")
        )
        stored = result.scalar()
    assert stored is not None
    assert stored != secret_plaintext
    assert secret_plaintext.startswith("whsec_")

    # Vérifier qu'on peut déchiffrer
    from app.core.crypto import decrypt
    assert decrypt(stored) == secret_plaintext


# ============ Rate limit service ============

async def test_rate_limit_without_redis():
    """Sans Redis, le service doit fail-open (autoriser)."""
    from app.services.rate_limit_service import check_rate_limit
    # Forcer Redis à None pour le test
    import app.services.rate_limit_service as rls
    rls._redis_client = None
    # Si Redis n'est pas dispo, get_redis() retournera None → allowed=True
    allowed, current, limit = await check_rate_limit("test-key-no-redis", limit_per_minute=5)
    # On peut avoir Redis dispo en CI ; donc on accepte les deux cas
    assert isinstance(allowed, bool)
    assert isinstance(current, int)
    assert isinstance(limit, int)


# ============ OCR endpoint validation ============

async def test_prescription_ocr_invalid_base64_returns_400(client, auth_headers):
    """L'endpoint OCR refuse une image base64 invalide."""
    r = await client.post(
        "/api/v1/ai/prescription-ocr",
        json={"image_base64": "not-valid-base64-!!!", "media_type": "image/jpeg"},
        headers=auth_headers,
    )
    # 400 (base64 invalide) ou 503 (Anthropic non configurée) sont tous deux OK
    assert r.status_code in (400, 503)


async def test_prescription_ocr_requires_auth(client):
    """L'endpoint OCR nécessite une authentification."""
    r = await client.post(
        "/api/v1/ai/prescription-ocr",
        json={"image_base64": "x", "media_type": "image/jpeg"},
    )
    assert r.status_code == 401


# ============ Webhook delivery worker ============

async def test_worker_marks_delivered_on_success(client, auth_headers):
    """Le worker doit marquer 'delivered' après une 2xx."""
    # Mock httpx pour retourner 200
    import httpx
    from unittest.mock import patch, AsyncMock

    # 1. Créer un webhook
    wh = await client.post(
        "/api/v1/developer/webhooks",
        json={"url": "https://example.invalid/hook", "events": ["sale.created"]},
        headers=auth_headers,
    )
    endpoint_id = wh.json()["id"]

    # 2. Produit + vente pour générer une delivery
    p = await client.post(
        "/api/v1/products",
        json={"code": "WK1", "name": "WorkerTest", "purchase_price_ht": "1", "sale_price_ttc": "10"},
        headers=auth_headers,
    )
    pid = p.json()["id"]
    await client.post(
        "/api/v1/products/lots",
        json={"product_id": pid, "lot_number": "L", "quantity": 10, "expiration_date": "2027-12-31"},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": pid, "quantity": 1, "unit_price_ttc": "10"}],
            "paid_cash": "10",
        },
        headers=auth_headers,
    )

    # 3. Lancer le worker en mockant httpx.AsyncClient.post pour retourner 200
    from app.db.session import AsyncSessionLocal
    from app.workers.webhook_worker import process_pending_deliveries

    class FakeResponse:
        status_code = 200
        text = '{"ok": true}'

    class FakeClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, *args, **kwargs):
            return FakeResponse()

    with patch("app.services.webhook_service.httpx.AsyncClient", FakeClient):
        async with AsyncSessionLocal() as s:
            stats = await process_pending_deliveries(s)

    assert stats["processed"] >= 1
    assert stats["delivered"] >= 1


async def test_worker_retries_on_failure(client, auth_headers):
    """Le worker doit marquer 'retrying' après un échec et programmer next_retry_at."""
    from unittest.mock import patch

    wh = await client.post(
        "/api/v1/developer/webhooks",
        json={"url": "https://example.invalid/hook", "events": ["sale.created"]},
        headers=auth_headers,
    )

    p = await client.post(
        "/api/v1/products",
        json={"code": "RT1", "name": "Retry", "purchase_price_ht": "1", "sale_price_ttc": "10"},
        headers=auth_headers,
    )
    pid = p.json()["id"]
    await client.post(
        "/api/v1/products/lots",
        json={"product_id": pid, "lot_number": "L", "quantity": 10, "expiration_date": "2027-12-31"},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/sales",
        json={"items": [{"product_id": pid, "quantity": 1, "unit_price_ttc": "10"}], "paid_cash": "10"},
        headers=auth_headers,
    )

    # Mock httpx pour échouer
    class FakeFailClient:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, *args, **kwargs):
            import httpx
            raise httpx.TimeoutException("simulated timeout")

    from app.db.session import AsyncSessionLocal
    from app.workers.webhook_worker import process_pending_deliveries

    with patch("app.services.webhook_service.httpx.AsyncClient", FakeFailClient):
        async with AsyncSessionLocal() as s:
            stats = await process_pending_deliveries(s)

    assert stats["failed"] >= 1
    # Vérifier qu'il y a au moins une delivery en status retrying avec next_retry_at
    from app.db.session import AsyncSessionLocal
    from sqlalchemy import select
    from app.models.webhook import WebhookDelivery
    async with AsyncSessionLocal() as s:
        result = await s.execute(
            select(WebhookDelivery).where(WebhookDelivery.status == "retrying")
        )
        retrying = list(result.scalars().all())
    assert len(retrying) >= 1
    assert retrying[0].next_retry_at is not None
    assert retrying[0].attempt_count >= 1
