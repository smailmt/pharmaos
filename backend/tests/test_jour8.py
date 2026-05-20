"""Tests Jour 8 : clôture journée, ordonnancier, échanges, charges, inventaires, permissions."""
import pytest
from datetime import date


# ============ Permissions ============

def test_permission_function():
    from app.core.permissions import has_permission
    assert has_permission("owner", "sales:close_day") is True
    assert has_permission("caissier", "sales:close_day") is False
    assert has_permission("caissier", "sales:create") is True
    assert has_permission("caissier", "expenses:read") is False
    assert has_permission("titulaire", "expenses:read") is True
    # Permission inconnue → False
    assert has_permission("owner", "fake:perm") is False


# ============ Clôture journée ============

async def test_preview_day_totals(client, auth_headers):
    r = await client.get("/api/v1/operations/day-closings/preview", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["already_closed"] is False
    assert "total_revenue" in data
    assert "total_cash" in data


async def test_close_day(client, auth_headers):
    r = await client.post(
        "/api/v1/operations/day-closings",
        json={"cash_counted": "0.00", "notes": "Test close"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["closing_date"] == date.today().isoformat()
    assert "cash_difference" in data


async def test_close_day_twice_fails(client, auth_headers):
    # 1ère clôture
    r1 = await client.post(
        "/api/v1/operations/day-closings",
        json={"cash_counted": "0.00"},
        headers=auth_headers,
    )
    assert r1.status_code == 201
    # 2ème → 409
    r2 = await client.post(
        "/api/v1/operations/day-closings",
        json={"cash_counted": "0.00"},
        headers=auth_headers,
    )
    assert r2.status_code == 409


async def test_sale_blocked_after_close_day(client, auth_headers):
    """Une vente est rejetée si la journée est clôturée."""
    # Créer produit + lot
    p = await client.post(
        "/api/v1/products",
        json={"code": "BLOCK1", "name": "Test", "purchase_price_ht": "1", "sale_price_ttc": "10"},
        headers=auth_headers,
    )
    pid = p.json()["id"]
    await client.post(
        "/api/v1/products/lots",
        json={"product_id": pid, "lot_number": "L", "quantity": 10, "expiration_date": "2027-12-31"},
        headers=auth_headers,
    )

    # Clôture
    await client.post(
        "/api/v1/operations/day-closings",
        json={"cash_counted": "0.00"},
        headers=auth_headers,
    )

    # Vente → 409
    r = await client.post(
        "/api/v1/sales",
        json={"items": [{"product_id": pid, "quantity": 1, "unit_price_ttc": "10"}], "paid_cash": "10"},
        headers=auth_headers,
    )
    assert r.status_code == 409
    assert "clôturée" in r.json()["detail"]


# ============ Ordonnancier ============

async def test_prescription_logged_on_sale(client, auth_headers):
    """Une vente avec ordonnance crée un PrescriptionLog avec numéro séquentiel."""
    p = await client.post(
        "/api/v1/products",
        json={"code": "RX1", "name": "Med Rx", "purchase_price_ht": "1", "sale_price_ttc": "20"},
        headers=auth_headers,
    )
    pid = p.json()["id"]
    await client.post(
        "/api/v1/products/lots",
        json={"product_id": pid, "lot_number": "L", "quantity": 10, "expiration_date": "2027-12-31"},
        headers=auth_headers,
    )

    # Vente avec ordonnance
    r = await client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": pid, "quantity": 1, "unit_price_ttc": "20"}],
            "paid_cash": "20",
            "has_prescription": True,
            "prescription_number": "ORD-2026-001",
        },
        headers=auth_headers,
    )
    assert r.status_code == 201

    # Vérifier dans l'ordonnancier
    r2 = await client.get("/api/v1/operations/prescription-log", headers=auth_headers)
    assert r2.status_code == 200
    logs = r2.json()
    assert len(logs) >= 1
    log = next((l for l in logs if l["prescription_number"] == "ORD-2026-001"), None)
    assert log is not None
    assert log["sequential_number"] >= 1
    assert len(log["dispensed_items"]) == 1


# ============ Échanges confrères ============

async def test_create_exchange(client, auth_headers):
    r = await client.post(
        "/api/v1/operations/exchanges",
        json={
            "direction": "in",
            "partner_name": "Pharmacie El Atlas",
            "partner_phone": "0612345678",
            "product_name": "Doliprane 500mg",
            "quantity": 5,
            "unit_value": "12.00",
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["direction"] == "in"
    assert data["total_value"] == "60.00"
    assert data["status"] == "pending"


async def test_exchange_balances(client, auth_headers):
    """Vérifier le solde par partenaire."""
    # 2 échanges in (on a reçu 100 MAD)
    for _ in range(2):
        await client.post(
            "/api/v1/operations/exchanges",
            json={
                "direction": "in", "partner_name": "Ph. Balance",
                "product_name": "X", "quantity": 1, "unit_value": "50",
            },
            headers=auth_headers,
        )
    # 1 échange out (on a donné 30 MAD)
    await client.post(
        "/api/v1/operations/exchanges",
        json={
            "direction": "out", "partner_name": "Ph. Balance",
            "product_name": "Y", "quantity": 1, "unit_value": "30",
        },
        headers=auth_headers,
    )

    r = await client.get("/api/v1/operations/exchanges/balances", headers=auth_headers)
    assert r.status_code == 200
    balances = r.json()
    b = next((b for b in balances if b["partner_name"] == "Ph. Balance"), None)
    assert b is not None
    assert b["in_count"] == 2 and float(b["in_value"]) == 100
    assert b["out_count"] == 1 and float(b["out_value"]) == 30
    # On a reçu 100, on a donné 30 → on leur doit 70 → net_balance = -70
    assert float(b["net_balance"]) == -70


async def test_settle_exchange(client, auth_headers):
    r1 = await client.post(
        "/api/v1/operations/exchanges",
        json={
            "direction": "in", "partner_name": "Ph. Settle",
            "product_name": "Z", "quantity": 1, "unit_value": "10",
        },
        headers=auth_headers,
    )
    ex_id = r1.json()["id"]
    r2 = await client.post(
        f"/api/v1/operations/exchanges/{ex_id}/settle",
        headers=auth_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "settled"
    assert r2.json()["settled_at"] is not None


# ============ Charges ============

async def test_create_expense(client, auth_headers):
    r = await client.post(
        "/api/v1/operations/expenses",
        json={
            "category": "rent",
            "amount": "5000",
            "description": "Loyer mensuel",
            "payment_method": "transfer",
            "is_recurring": True,
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    assert r.json()["category"] == "rent"


async def test_expense_summary(client, auth_headers):
    # Créer 2 charges rent + 1 utilities
    for amount in ("3000", "3000"):
        await client.post(
            "/api/v1/operations/expenses",
            json={"category": "rent", "amount": amount, "description": "Loyer"},
            headers=auth_headers,
        )
    await client.post(
        "/api/v1/operations/expenses",
        json={"category": "utilities", "amount": "500", "description": "Électricité"},
        headers=auth_headers,
    )

    r = await client.get("/api/v1/operations/expenses/summary", headers=auth_headers)
    assert r.status_code == 200
    summary = r.json()
    rent = next((s for s in summary if s["category"] == "rent"), None)
    assert rent is not None
    assert float(rent["total_amount"]) >= 6000
    assert rent["count"] >= 2


# ============ Inventaires ============

async def test_inventory_full_flow(client, auth_headers):
    """Création session → ajout lignes → clôture avec ajustement stock."""
    # Produit avec stock_quantity initial = 0 (pas de lot)
    p = await client.post(
        "/api/v1/products",
        json={"code": "INV1", "name": "Inv Test", "purchase_price_ht": "5", "sale_price_ttc": "10"},
        headers=auth_headers,
    )
    pid = p.json()["id"]

    # Démarrer session
    s = await client.post(
        "/api/v1/operations/inventory-sessions",
        json={"name": "Test inventaire", "scope": "full"},
        headers=auth_headers,
    )
    assert s.status_code == 201
    session_id = s.json()["id"]
    assert s.json()["status"] == "in_progress"

    # Compter 15 unités (théorique = 0)
    line = await client.post(
        f"/api/v1/operations/inventory-sessions/{session_id}/lines",
        json={"product_id": pid, "quantity_counted": 15},
        headers=auth_headers,
    )
    assert line.status_code == 201
    assert line.json()["difference"] == 15  # +15 vs théorique
    assert float(line.json()["value_difference"]) == 75  # 15 × 5 MAD

    # Lister lignes
    lines = await client.get(
        f"/api/v1/operations/inventory-sessions/{session_id}/lines",
        headers=auth_headers,
    )
    assert len(lines.json()) == 1

    # Clôturer avec ajustement
    close = await client.post(
        f"/api/v1/operations/inventory-sessions/{session_id}/complete?apply_adjustments=true",
        headers=auth_headers,
    )
    assert close.status_code == 200
    assert close.json()["status"] == "completed"
    assert close.json()["items_counted"] == 1
    assert close.json()["discrepancies_count"] == 1

    # Vérifier que le stock produit a été mis à jour
    prod = await client.get(f"/api/v1/products/{pid}", headers=auth_headers)
    assert prod.json()["stock_quantity"] == 15


async def test_inventory_session_isolated_per_tenant(client):
    """Pharmacie A ne voit pas les sessions d'inventaire de B."""
    rA = await client.post("/api/v1/auth/register", json={
        "email": "inv_a@x.com", "password": "passwordA123",
        "full_name": "A", "pharmacy": {"name": "PA"},
    })
    hA = {"Authorization": f"Bearer {rA.json()['access_token']}"}

    rB = await client.post("/api/v1/auth/register", json={
        "email": "inv_b@x.com", "password": "passwordB123",
        "full_name": "B", "pharmacy": {"name": "PB"},
    })
    hB = {"Authorization": f"Bearer {rB.json()['access_token']}"}

    await client.post(
        "/api/v1/operations/inventory-sessions",
        json={"name": "Session A"},
        headers=hA,
    )

    listB = await client.get("/api/v1/operations/inventory-sessions", headers=hB)
    assert listB.json() == []
