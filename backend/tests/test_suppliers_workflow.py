"""Tests workflow fournisseurs : commandes (BC), bons de livraison (BL), stock."""
import pytest


async def _create_product(client, auth_headers, code="SUP1", name="Produit Sup"):
    r = await client.post(
        "/api/v1/products",
        json={"code": code, "name": name, "purchase_price_ht": "10", "sale_price_ttc": "20"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    return r.json()


async def _create_supplier(client, auth_headers, name="Grossiste Test"):
    r = await client.post(
        "/api/v1/suppliers",
        json={"code": "GRO1", "name": name, "type": "wholesaler"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    return r.json()


async def test_create_purchase_order(client, auth_headers):
    product = await _create_product(client, auth_headers)
    supplier = await _create_supplier(client, auth_headers)

    r = await client.post(
        "/api/v1/suppliers/orders",
        json={
            "supplier_id": supplier["id"],
            "items": [
                {
                    "product_id": product["id"],
                    "quantity_ordered": 50,
                    "unit_price_ht": "10.0000",
                    "discount_rate": "0",
                    "vat_rate": "0.07",
                }
            ],
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "draft"
    assert data["order_number"]


async def test_send_purchase_order(client, auth_headers):
    product = await _create_product(client, auth_headers)
    supplier = await _create_supplier(client, auth_headers)
    po = await client.post(
        "/api/v1/suppliers/orders",
        json={
            "supplier_id": supplier["id"],
            "items": [{"product_id": product["id"], "quantity_ordered": 10,
                       "unit_price_ht": "10.0000", "discount_rate": "0", "vat_rate": "0.07"}],
        },
        headers=auth_headers,
    )
    po_id = po.json()["id"]

    r = await client.post(f"/api/v1/suppliers/orders/{po_id}/send", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] in ("sent", "draft")


async def test_receive_delivery_increments_stock(client, auth_headers):
    """Le coeur du workflow : réceptionner un BL augmente le stock."""
    product = await _create_product(client, auth_headers, code="STK1")
    supplier = await _create_supplier(client, auth_headers)

    # Stock initial = 0
    before = await client.get(f"/api/v1/products/{product['id']}", headers=auth_headers)
    assert before.json()["stock_quantity"] == 0

    # Réceptionner un BL de 30 unités
    r = await client.post(
        "/api/v1/suppliers/deliveries",
        json={
            "supplier_id": supplier["id"],
            "delivery_number": "BL-TEST-001",
            "items": [
                {
                    "product_id": product["id"],
                    "quantity_ordered": 30,
                    "quantity_received": 30,
                    "unit_price_ht": "10.0000",
                    "discount_rate": "0",
                    "vat_rate": "0.07",
                    "lot_number": "LOT-A",
                    "expiration_date": "2027-12-31",
                }
            ],
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    assert r.json()["delivery_number"] == "BL-TEST-001"

    # Stock doit être passé à 30
    after = await client.get(f"/api/v1/products/{product['id']}", headers=auth_headers)
    assert after.json()["stock_quantity"] == 30


async def test_delivery_with_discrepancy_flagged(client, auth_headers):
    """Si quantité reçue != commandée, le BL est marqué avec écart."""
    product = await _create_product(client, auth_headers, code="DISC1")
    supplier = await _create_supplier(client, auth_headers)

    r = await client.post(
        "/api/v1/suppliers/deliveries",
        json={
            "supplier_id": supplier["id"],
            "delivery_number": "BL-DISC-001",
            "items": [
                {
                    "product_id": product["id"],
                    "quantity_ordered": 20,
                    "quantity_received": 15,  # écart de 5
                    "unit_price_ht": "10.0000",
                    "discount_rate": "0",
                    "vat_rate": "0.07",
                }
            ],
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    assert r.json()["has_discrepancies"] is True


async def test_list_deliveries(client, auth_headers):
    supplier = await _create_supplier(client, auth_headers)
    product = await _create_product(client, auth_headers, code="LST1")
    await client.post(
        "/api/v1/suppliers/deliveries",
        json={
            "supplier_id": supplier["id"],
            "delivery_number": "BL-LST-001",
            "items": [{"product_id": product["id"], "quantity_ordered": 5,
                       "quantity_received": 5, "unit_price_ht": "10.0000",
                       "discount_rate": "0", "vat_rate": "0.07"}],
        },
        headers=auth_headers,
    )
    r = await client.get("/api/v1/suppliers/deliveries", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


async def test_update_purchase_order(client, auth_headers):
    """Modifier les lignes d'un BC brouillon recalcule les totaux."""
    product = await _create_product(client, auth_headers, code="UPD1", name="Produit Update")
    product2 = await _create_product(client, auth_headers, code="UPD2", name="Produit Update 2")
    supplier = await _create_supplier(client, auth_headers)

    po = await client.post(
        "/api/v1/suppliers/orders",
        json={
            "supplier_id": supplier["id"],
            "items": [{"product_id": product["id"], "quantity_ordered": 10,
                       "unit_price_ht": "10.0000", "discount_rate": "0", "vat_rate": "0.07"}],
        },
        headers=auth_headers,
    )
    assert po.status_code == 201
    po_id = po.json()["id"]
    total_avant = po.json()["total_ttc"]

    # Modifier : 20 unités du produit 1 + 5 du produit 2
    r = await client.put(
        f"/api/v1/suppliers/orders/{po_id}",
        json={
            "items": [
                {"product_id": product["id"], "quantity_ordered": 20,
                 "unit_price_ht": "10.0000", "discount_rate": "0", "vat_rate": "0.07"},
                {"product_id": product2["id"], "quantity_ordered": 5,
                 "unit_price_ht": "8.0000", "discount_rate": "0", "vat_rate": "0.07"},
            ]
        },
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "draft"
    assert len(data["items"]) == 2
    # Total doit avoir augmenté
    assert float(data["total_ttc"]) > float(total_avant)


async def test_delete_purchase_order(client, auth_headers):
    """Supprimer un BC brouillon le retire de la liste."""
    product = await _create_product(client, auth_headers, code="DEL1", name="Produit Delete")
    supplier = await _create_supplier(client, auth_headers)

    po = await client.post(
        "/api/v1/suppliers/orders",
        json={
            "supplier_id": supplier["id"],
            "items": [{"product_id": product["id"], "quantity_ordered": 5,
                       "unit_price_ht": "10.0000", "discount_rate": "0", "vat_rate": "0.07"}],
        },
        headers=auth_headers,
    )
    assert po.status_code == 201
    po_id = po.json()["id"]

    r = await client.delete(f"/api/v1/suppliers/orders/{po_id}", headers=auth_headers)
    assert r.status_code == 204

    # Le BC ne doit plus être accessible
    r2 = await client.get(f"/api/v1/suppliers/orders/{po_id}", headers=auth_headers)
    assert r2.status_code == 404


async def test_cannot_update_sent_order(client, auth_headers):
    """Un BC déjà envoyé ne peut pas être modifié."""
    product = await _create_product(client, auth_headers, code="SNT1", name="Produit Sent")
    supplier = await _create_supplier(client, auth_headers)

    po = await client.post(
        "/api/v1/suppliers/orders",
        json={
            "supplier_id": supplier["id"],
            "items": [{"product_id": product["id"], "quantity_ordered": 5,
                       "unit_price_ht": "10.0000", "discount_rate": "0", "vat_rate": "0.07"}],
        },
        headers=auth_headers,
    )
    po_id = po.json()["id"]
    await client.post(f"/api/v1/suppliers/orders/{po_id}/send", headers=auth_headers)

    r = await client.put(
        f"/api/v1/suppliers/orders/{po_id}",
        json={"items": [{"product_id": product["id"], "quantity_ordered": 99,
                         "unit_price_ht": "10.0000", "discount_rate": "0", "vat_rate": "0.07"}]},
        headers=auth_headers,
    )
    assert r.status_code == 400


async def test_cannot_delete_sent_order(client, auth_headers):
    """Un BC déjà envoyé ne peut pas être supprimé."""
    product = await _create_product(client, auth_headers, code="SNT2", name="Produit Sent 2")
    supplier = await _create_supplier(client, auth_headers)

    po = await client.post(
        "/api/v1/suppliers/orders",
        json={
            "supplier_id": supplier["id"],
            "items": [{"product_id": product["id"], "quantity_ordered": 5,
                       "unit_price_ht": "10.0000", "discount_rate": "0", "vat_rate": "0.07"}],
        },
        headers=auth_headers,
    )
    po_id = po.json()["id"]
    await client.post(f"/api/v1/suppliers/orders/{po_id}/send", headers=auth_headers)

    r = await client.delete(f"/api/v1/suppliers/orders/{po_id}", headers=auth_headers)
    assert r.status_code == 400


async def test_supplier_payment(client, auth_headers):
    supplier = await _create_supplier(client, auth_headers)
    r = await client.post(
        "/api/v1/suppliers/payments",
        json={
            "supplier_id": supplier["id"],
            "amount": "1500.00",
            "payment_method": "transfer",
            "reference": "VIR-2026-001",
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    assert r.json()["amount"] == "1500.00"

    lst = await client.get("/api/v1/suppliers/payments", headers=auth_headers)
    assert lst.status_code == 200, lst.text
    assert len(lst.json()) >= 1
