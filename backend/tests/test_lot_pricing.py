"""Tests prix au lot (PPV par lot) + vente FEFO au bon prix.

Besoin métier : le PPV est imprimé sur la boîte et peut varier d'un lot à
l'autre. À la vente, on prend le lot qui périme le plus tôt (FEFO) et SON prix.
"""
import pytest


async def _product(client, auth_headers, code="LOTP1", ppv_ref="50"):
    r = await client.post(
        "/api/v1/products",
        json={"code": code, "name": "Produit Lot", "purchase_price_ht": "30",
              "sale_price_ttc": ppv_ref, "vat_rate": "0.07"},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _add_lot(client, auth_headers, product_id, lot, qty, exp, ppv=None):
    payload = {
        "product_id": product_id, "lot_number": lot, "quantity": qty,
        "expiration_date": exp,
    }
    if ppv is not None:
        payload["sale_price_ttc"] = ppv
    r = await client.post("/api/v1/products/lots", json=payload, headers=auth_headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_lot_carries_its_own_ppv(client, auth_headers):
    product = await _product(client, auth_headers)
    lot = await _add_lot(client, auth_headers, product["id"], "L1", 10, "2027-01-31", ppv="45.00")
    assert float(lot["sale_price_ttc"]) == 45.0

    # L'endpoint lots renvoie le PPV
    r = await client.get(f"/api/v1/products/{product['id']}/lots", headers=auth_headers)
    assert r.status_code == 200
    lots = r.json()
    assert float(lots[0]["sale_price_ttc"]) == 45.0


async def test_sale_uses_fefo_lot_price(client, auth_headers):
    """
    Deux lots, prix différents. Le lot qui périme en PREMIER a un PPV de 40.
    Une vente sans prix explicite doit appliquer 40 (FEFO), pas le prix de référence (50).
    """
    product = await _product(client, auth_headers, code="FEFO1", ppv_ref="50")
    # Lot A : périme tôt (2026-06), PPV 40
    await _add_lot(client, auth_headers, product["id"], "A", 5, "2026-06-30", ppv="40.00")
    # Lot B : périme tard (2027-06), PPV 55
    await _add_lot(client, auth_headers, product["id"], "B", 5, "2027-06-30", ppv="55.00")

    # Vente SANS prix explicite → doit prendre le lot A (FEFO) et son PPV 40
    r = await client.post(
        "/api/v1/sales",
        json={"items": [{"product_id": product["id"], "quantity": 1}], "paid_cash": "40"},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    sale = r.json()
    # Le prix unitaire TTC appliqué doit être 40 (PPV du lot FEFO), pas 50
    assert sale["items"][0]["unit_price_ttc"] == "40.0000"


async def test_sale_explicit_price_overrides_lot(client, auth_headers):
    """Si un prix explicite est fourni, il prime sur le PPV du lot."""
    product = await _product(client, auth_headers, code="OVR1", ppv_ref="50")
    await _add_lot(client, auth_headers, product["id"], "A", 5, "2026-06-30", ppv="40.00")

    r = await client.post(
        "/api/v1/sales",
        json={"items": [{"product_id": product["id"], "quantity": 1, "unit_price_ttc": "48.00"}],
              "paid_cash": "48"},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["items"][0]["unit_price_ttc"] == "48.0000"


async def test_sale_falls_back_to_product_price_when_lot_has_no_ppv(client, auth_headers):
    """Si le lot FEFO n'a pas de PPV, on utilise le prix de référence du produit."""
    product = await _product(client, auth_headers, code="FALL1", ppv_ref="50")
    await _add_lot(client, auth_headers, product["id"], "A", 5, "2026-06-30", ppv=None)

    r = await client.post(
        "/api/v1/sales",
        json={"items": [{"product_id": product["id"], "quantity": 1}], "paid_cash": "50"},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["items"][0]["unit_price_ttc"] == "50.0000"


async def test_delivery_sets_lot_ppv_from_item(client, auth_headers):
    """Réception BL avec PPV saisi → le lot créé porte ce PPV."""
    product = await _product(client, auth_headers, code="DELP1")
    supplier = await client.post(
        "/api/v1/suppliers",
        json={"code": "G1", "name": "Gros", "type": "wholesaler"},
        headers=auth_headers,
    )
    sid = supplier.json()["id"]

    r = await client.post(
        "/api/v1/suppliers/deliveries",
        json={
            "supplier_id": sid,
            "delivery_number": "BL-PPV-1",
            "items": [{
                "product_id": product["id"],
                "quantity_ordered": 10, "quantity_received": 10,
                "unit_price_ht": "30.0000", "discount_rate": "0", "vat_rate": "0.07",
                "lot_number": "LOT-PPV", "expiration_date": "2027-12-31",
                "sale_price_ttc": "52.50",
            }],
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text

    # Le lot créé doit avoir le PPV 52.50
    lots = await client.get(f"/api/v1/products/{product['id']}/lots", headers=auth_headers)
    lot = next((l for l in lots.json() if l["lot_number"] == "LOT-PPV"), None)
    assert lot is not None
    assert lot["sale_price_ttc"] == "52.5000"
