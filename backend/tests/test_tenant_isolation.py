"""Tests E2E multi-tenant : vérifie l'isolation entre pharmacies."""
import pytest


async def test_tenant_isolation(client):
    """Une pharmacie ne doit pas voir les données d'une autre."""
    # Pharmacy A
    rA = await client.post("/api/v1/auth/register", json={
        "email": "a@example.com",
        "password": "passwordA123",
        "full_name": "Owner A",
        "pharmacy": {"name": "Pharma A"},
    })
    tokenA = rA.json()["access_token"]
    headersA = {"Authorization": f"Bearer {tokenA}"}

    # Pharmacy B
    rB = await client.post("/api/v1/auth/register", json={
        "email": "b@example.com",
        "password": "passwordB123",
        "full_name": "Owner B",
        "pharmacy": {"name": "Pharma B"},
    })
    tokenB = rB.json()["access_token"]
    headersB = {"Authorization": f"Bearer {tokenB}"}

    # A crée un produit
    await client.post(
        "/api/v1/products",
        json={"code": "A1", "name": "Produit A", "purchase_price_ht": "1", "sale_price_ttc": "10"},
        headers=headersA,
    )

    # B crée un produit
    await client.post(
        "/api/v1/products",
        json={"code": "B1", "name": "Produit B", "purchase_price_ht": "1", "sale_price_ttc": "10"},
        headers=headersB,
    )

    # A ne voit que ses produits
    listA = await client.get("/api/v1/products", headers=headersA)
    codesA = [p["code"] for p in listA.json()]
    assert "A1" in codesA
    assert "B1" not in codesA

    # B ne voit que ses produits
    listB = await client.get("/api/v1/products", headers=headersB)
    codesB = [p["code"] for p in listB.json()]
    assert "B1" in codesB
    assert "A1" not in codesB


async def test_cannot_access_other_pharmacy_product_by_id(client):
    """Tenter d'accéder à un produit d'une autre pharmacie par son UUID = 404."""
    rA = await client.post("/api/v1/auth/register", json={
        "email": "a2@example.com", "password": "passwordA123",
        "full_name": "A", "pharmacy": {"name": "PA"},
    })
    headersA = {"Authorization": f"Bearer {rA.json()['access_token']}"}

    rB = await client.post("/api/v1/auth/register", json={
        "email": "b2@example.com", "password": "passwordB123",
        "full_name": "B", "pharmacy": {"name": "PB"},
    })
    headersB = {"Authorization": f"Bearer {rB.json()['access_token']}"}

    # A crée un produit
    rprod = await client.post(
        "/api/v1/products",
        json={"code": "SECRET", "name": "Confidentiel", "purchase_price_ht": "1", "sale_price_ttc": "10"},
        headers=headersA,
    )
    product_id = rprod.json()["id"]

    # B essaie d'y accéder par son UUID
    response = await client.get(f"/api/v1/products/{product_id}", headers=headersB)
    assert response.status_code == 404
