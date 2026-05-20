"""Tests E2E : API keys, auth duale, webhooks."""
import hmac
import hashlib
import json
import time


# ============ API Keys ============

async def test_create_api_key_returns_plaintext_once(client, auth_headers):
    response = await client.post(
        "/api/v1/developer/api-keys",
        json={"name": "Mon intégration", "env": "live"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["key"].startswith("pk_live_")
    assert data["key_prefix"].startswith("pk_live_")
    assert data["is_active"] is True

    # Lister : la clé en clair n'apparaît plus
    r2 = await client.get("/api/v1/developer/api-keys", headers=auth_headers)
    keys = r2.json()
    assert len(keys) == 1
    assert "key" not in keys[0]  # plaintext n'est PAS dans la liste
    assert keys[0]["key_prefix"] == data["key_prefix"]


async def test_create_api_key_test_env(client, auth_headers):
    r = await client.post(
        "/api/v1/developer/api-keys",
        json={"name": "Test env", "env": "test"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    assert r.json()["key"].startswith("pk_test_")


async def test_revoke_api_key(client, auth_headers):
    r = await client.post(
        "/api/v1/developer/api-keys",
        json={"name": "Temp"},
        headers=auth_headers,
    )
    key_id = r.json()["id"]

    # Révoquer
    r2 = await client.delete(f"/api/v1/developer/api-keys/{key_id}", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["is_active"] is False
    assert r2.json()["revoked_at"] is not None


async def test_revoke_nonexistent_key_returns_404(client, auth_headers):
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = await client.delete(f"/api/v1/developer/api-keys/{fake_id}", headers=auth_headers)
    assert r.status_code == 404


async def test_api_keys_isolated_per_tenant(client):
    """Un pharmacien A ne doit pas voir/révoquer les clés d'un pharmacien B."""
    # Pharmacy A
    rA = await client.post("/api/v1/auth/register", json={
        "email": "a@dev.com", "password": "passwordA123",
        "full_name": "A", "pharmacy": {"name": "PA"},
    })
    hA = {"Authorization": f"Bearer {rA.json()['access_token']}"}

    # Pharmacy B
    rB = await client.post("/api/v1/auth/register", json={
        "email": "b@dev.com", "password": "passwordB123",
        "full_name": "B", "pharmacy": {"name": "PB"},
    })
    hB = {"Authorization": f"Bearer {rB.json()['access_token']}"}

    # A crée une clé
    k = await client.post("/api/v1/developer/api-keys", json={"name": "secret-A"}, headers=hA)
    key_id = k.json()["id"]

    # B ne la voit pas
    listB = await client.get("/api/v1/developer/api-keys", headers=hB)
    assert listB.json() == []

    # B ne peut pas la révoquer
    rev = await client.delete(f"/api/v1/developer/api-keys/{key_id}", headers=hB)
    assert rev.status_code == 404


# ============ Events ============

async def test_list_supported_events(client, auth_headers):
    r = await client.get("/api/v1/developer/events", headers=auth_headers)
    assert r.status_code == 200
    events = r.json()
    types = [e["type"] for e in events]
    assert "sale.created" in types
    assert "product.low_stock" in types


# ============ Webhooks ============

async def test_create_webhook_endpoint(client, auth_headers):
    r = await client.post(
        "/api/v1/developer/webhooks",
        json={
            "url": "https://example.com/hook",
            "events": ["sale.created"],
            "description": "Mon hook test",
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["url"] == "https://example.com/hook"
    assert "sale.created" in data["events"]
    assert data["secret"].startswith("whsec_")
    assert data["secret_prefix"].startswith("whsec_")

    # Lister : secret en clair absent
    r2 = await client.get("/api/v1/developer/webhooks", headers=auth_headers)
    eps = r2.json()
    assert len(eps) == 1
    assert "secret" not in eps[0]


async def test_delete_webhook(client, auth_headers):
    r = await client.post(
        "/api/v1/developer/webhooks",
        json={"url": "https://example.com/x", "events": ["*"]},
        headers=auth_headers,
    )
    ep_id = r.json()["id"]
    r2 = await client.delete(f"/api/v1/developer/webhooks/{ep_id}", headers=auth_headers)
    assert r2.status_code == 204

    r3 = await client.get("/api/v1/developer/webhooks", headers=auth_headers)
    assert r3.json() == []


async def test_webhook_emit_creates_pending_delivery(client, auth_headers):
    """
    Quand on souscrit à sale.created et qu'on fait une vente, une WebhookDelivery
    pending doit apparaître.
    """
    # 1. Créer un webhook qui souscrit à sale.created
    wh = await client.post(
        "/api/v1/developer/webhooks",
        json={"url": "https://example.invalid/hook", "events": ["sale.created"]},
        headers=auth_headers,
    )
    endpoint_id = wh.json()["id"]

    # 2. Créer produit + lot
    p = await client.post(
        "/api/v1/products",
        json={"code": "P1", "name": "Test", "purchase_price_ht": "5", "sale_price_ttc": "10", "stock_min": 10},
        headers=auth_headers,
    )
    product_id = p.json()["id"]
    await client.post(
        "/api/v1/products/lots",
        json={"product_id": product_id, "lot_number": "L1", "quantity": 50, "expiration_date": "2027-12-31"},
        headers=auth_headers,
    )

    # 3. Faire une vente
    s = await client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": product_id, "quantity": 2, "unit_price_ttc": "10.00"}],
            "paid_cash": "20.00",
        },
        headers=auth_headers,
    )
    assert s.status_code == 201

    # 4. Vérifier qu'une delivery pending existe pour ce webhook
    deliveries = await client.get(
        f"/api/v1/developer/webhooks/{endpoint_id}/deliveries",
        headers=auth_headers,
    )
    assert deliveries.status_code == 200
    items = deliveries.json()
    # Au moins une delivery sale.created
    sale_created = [d for d in items if d["event_type"] == "sale.created"]
    assert len(sale_created) >= 1


async def test_low_stock_event_emitted(client, auth_headers):
    """
    Quand un produit passe sous son seuil après vente, product.low_stock doit être émis.
    """
    wh = await client.post(
        "/api/v1/developer/webhooks",
        json={"url": "https://example.invalid/hook", "events": ["*"]},
        headers=auth_headers,
    )
    endpoint_id = wh.json()["id"]

    # Produit avec stock_min=20, lot de 25 → vendre 10 = passe à 15 < 20
    p = await client.post(
        "/api/v1/products",
        json={"code": "LS1", "name": "LowStockTest", "purchase_price_ht": "1", "sale_price_ttc": "10", "stock_min": 20},
        headers=auth_headers,
    )
    pid = p.json()["id"]
    await client.post(
        "/api/v1/products/lots",
        json={"product_id": pid, "lot_number": "L", "quantity": 25, "expiration_date": "2027-12-31"},
        headers=auth_headers,
    )

    # Vendre 10 → reste 15 < stock_min 20
    await client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": pid, "quantity": 10, "unit_price_ttc": "10.00"}],
            "paid_cash": "100.00",
        },
        headers=auth_headers,
    )

    deliveries = await client.get(
        f"/api/v1/developer/webhooks/{endpoint_id}/deliveries",
        headers=auth_headers,
    )
    types = [d["event_type"] for d in deliveries.json()]
    assert "product.low_stock" in types


# ============ Signature HMAC ============

async def test_signature_verification():
    """Vérifie le helper de signature HMAC."""
    from app.services.webhook_service import sign_payload, verify_signature

    secret = "whsec_test123"
    body = b'{"id":"evt_x","type":"sale.created"}'
    sig = sign_payload(body, secret)

    # Signature valide
    assert verify_signature(body, secret, sig) is True
    # Signature invalide
    assert verify_signature(body, secret, "wrong") is False
    # Body altéré
    assert verify_signature(b'{"id":"evt_x","type":"hacked"}', secret, sig) is False
