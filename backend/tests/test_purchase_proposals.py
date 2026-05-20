"""Tests proposition de commande : mode ventes + mode min/Max."""
import pytest


async def _product(client, h, code, stock=0, stock_min=0, stock_max=0, ppa="10", ppv="20"):
    r = await client.post("/api/v1/products", json={
        "code": code, "name": f"Prod {code}", "purchase_price_ht": ppa,
        "sale_price_ttc": ppv, "stock_min": stock_min, "stock_max": stock_max,
    }, headers=h)
    assert r.status_code == 201, r.text
    p = r.json()
    # Mettre du stock via lot si besoin
    if stock > 0:
        await client.post("/api/v1/products/lots", json={
            "product_id": p["id"], "lot_number": f"L-{code}", "quantity": stock,
            "expiration_date": "2027-12-31",
        }, headers=h)
    return p


async def _sell(client, h, product_id, qty, price="20"):
    r = await client.post("/api/v1/sales", json={
        "items": [{"product_id": product_id, "quantity": qty, "unit_price_ttc": price}],
        "paid_cash": str(float(price) * qty),
    }, headers=h)
    assert r.status_code == 201, r.text


async def test_proposal_by_sales(client, auth_headers):
    """Un produit vendu mais en rupture doit être proposé."""
    p = await _product(client, auth_headers, "PROP1", stock=10)
    await _sell(client, auth_headers, p["id"], 8)  # vend 8, reste 2

    r = await client.get("/api/v1/suppliers/purchase-proposals?mode=sales&days=30", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["mode"] == "sales"
    item = next((i for i in data["items"] if i["product_code"] == "PROP1"), None)
    assert item is not None
    assert item["qty_sold"] == 8
    assert item["current_stock"] == 2
    # Suggestion = vendu - stock = 8 - 2 = 6
    assert item["suggested_quantity"] == 6


async def test_proposal_by_minmax(client, auth_headers):
    """Un produit sous son stock_min doit être proposé pour remonter au max."""
    # stock 3, min 5, max 20 → sous le seuil
    p = await _product(client, auth_headers, "MM1", stock=3, stock_min=5, stock_max=20)

    r = await client.get("/api/v1/suppliers/purchase-proposals?mode=minmax", headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["mode"] == "minmax"
    item = next((i for i in data["items"] if i["product_code"] == "MM1"), None)
    assert item is not None
    assert item["current_stock"] == 3
    # Suggestion = max - stock = 20 - 3 = 17
    assert item["suggested_quantity"] == 17


async def test_proposal_minmax_ignores_well_stocked(client, auth_headers):
    """Un produit au-dessus de son min ne doit PAS être proposé."""
    await _product(client, auth_headers, "OK1", stock=50, stock_min=5, stock_max=20)
    r = await client.get("/api/v1/suppliers/purchase-proposals?mode=minmax", headers=auth_headers)
    item = next((i for i in r.json()["items"] if i["product_code"] == "OK1"), None)
    assert item is None


async def test_proposal_totals(client, auth_headers):
    """Les totaux PPH et PPV sont calculés."""
    p = await _product(client, auth_headers, "TOT1", stock=0, stock_min=10, stock_max=10, ppa="5", ppv="12")
    r = await client.get("/api/v1/suppliers/purchase-proposals?mode=minmax", headers=auth_headers)
    data = r.json()
    item = next((i for i in data["items"] if i["product_code"] == "TOT1"), None)
    assert item is not None
    assert item["suggested_quantity"] == 10
    # total au moins 10×5 = 50 PPH
    assert float(data["total_pph"]) >= 50


async def test_proposal_filtered_by_supplier(client, auth_headers):
    """Filtrer par fournisseur ne renvoie que les produits de son catalogue."""
    p1 = await _product(client, auth_headers, "CAT1", stock=0, stock_min=5, stock_max=10)
    p2 = await _product(client, auth_headers, "CAT2", stock=0, stock_min=5, stock_max=10)

    sup = await client.post("/api/v1/suppliers", json={"code": "S1", "name": "Sup", "type": "wholesaler"}, headers=auth_headers)
    sid = sup.json()["id"]
    # Ajouter seulement p1 au catalogue
    await client.post("/api/v1/suppliers/catalog", json={
        "supplier_id": sid, "product_id": p1["id"], "purchase_price_ht": "8", "ppv": "15",
    }, headers=auth_headers)

    r = await client.get(f"/api/v1/suppliers/purchase-proposals?mode=minmax&supplier_id={sid}", headers=auth_headers)
    codes = [i["product_code"] for i in r.json()["items"]]
    assert "CAT1" in codes
    assert "CAT2" not in codes
    # Le PPH doit venir du catalogue (8) pas du produit (10)
    cat1 = next(i for i in r.json()["items"] if i["product_code"] == "CAT1")
    assert float(cat1["pph"]) == 8
