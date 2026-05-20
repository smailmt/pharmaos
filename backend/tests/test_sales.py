"""Tests E2E pour le module Ventes (workflow critique caisse)."""
import pytest


@pytest.fixture
async def product_with_stock(client, auth_headers):
    """Crée un produit avec stock (via lot)."""
    r = await client.post(
        "/api/v1/products",
        json={
            "code": "TEST1",
            "name": "Produit test",
            "purchase_price_ht": "5.00",
            "sale_price_ttc": "10.00",
            "vat_rate": "0.07",
            "stock_min": 10,
        },
        headers=auth_headers,
    )
    product = r.json()
    # Ajouter un lot pour disposer de stock
    await client.post(
        "/api/v1/products/lots",
        json={
            "product_id": product["id"],
            "lot_number": "LOT-TEST",
            "quantity": 100,
            "expiration_date": "2027-12-31",
        },
        headers=auth_headers,
    )
    # Rafraîchir
    r2 = await client.get(f"/api/v1/products/{product['id']}", headers=auth_headers)
    return r2.json()


@pytest.fixture
async def client_with_credit(client, auth_headers):
    """Crée un client avec crédit autorisé."""
    r = await client.post(
        "/api/v1/clients",
        json={
            "full_name": "Mohammed Test",
            "phone": "0600000000",
            "credit_enabled": True,
            "credit_limit": "1000.00",
        },
        headers=auth_headers,
    )
    return r.json()


async def test_create_cash_sale(client, auth_headers, product_with_stock):
    response = await client.post(
        "/api/v1/sales",
        json={
            "items": [
                {
                    "product_id": product_with_stock["id"],
                    "quantity": 2,
                    "unit_price_ttc": "10.00",
                }
            ],
            "paid_cash": "20.00",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    sale = response.json()
    assert sale["sale_number"].startswith("V-")
    assert float(sale["total_ttc"]) == 20.0
    assert len(sale["items"]) == 1
    assert sale["status"] == "completed"


async def test_sale_decrements_stock(client, auth_headers, product_with_stock):
    pid = product_with_stock["id"]
    initial_stock = product_with_stock["stock_quantity"]

    await client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": pid, "quantity": 3, "unit_price_ttc": "10.00"}],
            "paid_cash": "30.00",
        },
        headers=auth_headers,
    )

    r = await client.get(f"/api/v1/products/{pid}", headers=auth_headers)
    new_stock = r.json()["stock_quantity"]
    assert new_stock == initial_stock - 3


async def test_sale_with_credit(client, auth_headers, product_with_stock, client_with_credit):
    """Vente à crédit : génère une CreditEntry + échéancier."""
    response = await client.post(
        "/api/v1/sales",
        json={
            "client_id": client_with_credit["id"],
            "items": [{"product_id": product_with_stock["id"], "quantity": 5, "unit_price_ttc": "10.00"}],
            "paid_credit": "50.00",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201

    # Vérifier balance client
    r = await client.get(f"/api/v1/clients/{client_with_credit['id']}", headers=auth_headers)
    detail = r.json()
    assert float(detail["current_balance"]) == 50.0


async def test_sale_credit_exceeds_limit_fails(client, auth_headers, product_with_stock):
    """Vente à crédit > plafond doit échouer."""
    r = await client.post(
        "/api/v1/clients",
        json={
            "full_name": "Low Credit",
            "credit_enabled": True,
            "credit_limit": "30.00",  # Plafond bas
        },
        headers=auth_headers,
    )
    client_id = r.json()["id"]

    response = await client.post(
        "/api/v1/sales",
        json={
            "client_id": client_id,
            "items": [{"product_id": product_with_stock["id"], "quantity": 10, "unit_price_ttc": "10.00"}],
            "paid_credit": "100.00",
        },
        headers=auth_headers,
    )
    assert response.status_code == 400


async def test_sale_loyalty_points(client, auth_headers, product_with_stock, client_with_credit):
    """1 point fidélité par tranche de 10 MAD."""
    r = await client.post(
        "/api/v1/sales",
        json={
            "client_id": client_with_credit["id"],
            "items": [{"product_id": product_with_stock["id"], "quantity": 5, "unit_price_ttc": "10.00"}],
            "paid_cash": "50.00",
        },
        headers=auth_headers,
    )
    sale = r.json()
    assert sale["loyalty_points_earned"] == 5  # 50/10


async def test_credit_payment_reduces_balance(client, auth_headers, product_with_stock, client_with_credit):
    """Paiement crédit doit réduire la balance."""
    client_id = client_with_credit["id"]
    # Vente à crédit 100
    await client.post(
        "/api/v1/sales",
        json={
            "client_id": client_id,
            "items": [{"product_id": product_with_stock["id"], "quantity": 10, "unit_price_ttc": "10.00"}],
            "paid_credit": "100.00",
        },
        headers=auth_headers,
    )
    # Paiement 40
    r = await client.post(
        "/api/v1/clients/credit/payments",
        json={"client_id": client_id, "amount": "40.00", "payment_method": "cash"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    # Balance attendue : 60
    r2 = await client.get(f"/api/v1/clients/{client_id}", headers=auth_headers)
    assert float(r2.json()["current_balance"]) == 60.0


async def test_get_sale_with_items(client, auth_headers, product_with_stock):
    r = await client.post(
        "/api/v1/sales",
        json={
            "items": [{"product_id": product_with_stock["id"], "quantity": 2, "unit_price_ttc": "10.00"}],
            "paid_cash": "20.00",
        },
        headers=auth_headers,
    )
    sale_id = r.json()["id"]
    r2 = await client.get(f"/api/v1/sales/{sale_id}", headers=auth_headers)
    assert r2.status_code == 200
    assert len(r2.json()["items"]) == 1
