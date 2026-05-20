"""Tests E2E pour le module Produits."""
import pytest


async def test_create_product(client, auth_headers):
    payload = {
        "code": "PARA500",
        "name": "Paracétamol 500mg",
        "dci": "Paracétamol",
        "laboratory": "Sanofi",
        "purchase_price_ht": "5.00",
        "sale_price_ttc": "10.00",
        "vat_rate": "0.07",
        "stock_min": 20,
    }
    response = await client.post("/api/v1/products", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["code"] == "PARA500"
    assert data["stock_quantity"] == 0  # Stock vient des lots ajoutés ensuite


async def test_list_products(client, auth_headers):
    # Créer 3 produits
    for i in range(3):
        await client.post(
            "/api/v1/products",
            json={
                "code": f"P{i}",
                "name": f"Produit {i}",
                "purchase_price_ht": "5",
                "sale_price_ttc": "10",
            },
            headers=auth_headers,
        )
    response = await client.get("/api/v1/products", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 3


async def test_search_product(client, auth_headers):
    await client.post(
        "/api/v1/products",
        json={"code": "ASP1", "name": "Aspirine 500", "dci": "Acide acetylsalicylique", "purchase_price_ht": "1", "sale_price_ttc": "10"},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/products",
        json={"code": "DOLI1", "name": "Doliprane", "dci": "Paracétamol", "purchase_price_ht": "1", "sale_price_ttc": "10"},
        headers=auth_headers,
    )
    response = await client.get("/api/v1/products?q=aspir", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["code"] == "ASP1"


async def test_low_stock_alert(client, auth_headers):
    """Stock du produit = somme des lots. On ajoute des lots pour contrôler."""
    # Sous seuil (peu de stock)
    r1 = await client.post(
        "/api/v1/products",
        json={
            "code": "LOW1",
            "name": "Stock bas",
            "purchase_price_ht": "1",
            "sale_price_ttc": "10",
            "stock_min": 20,
        },
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/products/lots",
        json={
            "product_id": r1.json()["id"],
            "lot_number": "L1",
            "quantity": 5,  # < stock_min=20
            "expiration_date": "2027-01-01",
        },
        headers=auth_headers,
    )
    # Au-dessus du seuil
    r2 = await client.post(
        "/api/v1/products",
        json={
            "code": "OK1",
            "name": "Stock OK",
            "purchase_price_ht": "1",
            "sale_price_ttc": "10",
            "stock_min": 20,
        },
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/products/lots",
        json={
            "product_id": r2.json()["id"],
            "lot_number": "L2",
            "quantity": 100,  # > stock_min
            "expiration_date": "2027-01-01",
        },
        headers=auth_headers,
    )
    response = await client.get("/api/v1/products/alerts/low-stock", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    codes = [p["code"] for p in data]
    assert "LOW1" in codes
    assert "OK1" not in codes


async def test_create_lot(client, auth_headers):
    # Créer produit
    r = await client.post(
        "/api/v1/products",
        json={"code": "LOT1", "name": "Test", "purchase_price_ht": "1", "sale_price_ttc": "10", "stock_quantity": 0},
        headers=auth_headers,
    )
    product_id = r.json()["id"]

    # Ajouter lot
    response = await client.post(
        "/api/v1/products/lots",
        json={
            "product_id": product_id,
            "lot_number": "LOT-2026-01",
            "quantity": 50,
            "expiration_date": "2027-12-31",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["quantity"] == 50

    # Vérifier que le stock du produit a augmenté (via lots)
    r_lots = await client.get(f"/api/v1/products/{product_id}/lots", headers=auth_headers)
    assert r_lots.status_code == 200
    assert len(r_lots.json()) == 1
