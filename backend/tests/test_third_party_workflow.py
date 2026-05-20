"""Tests workflow tiers payants : payeurs, claims, bordereaux, paiements."""
import pytest
from datetime import date


async def _create_payer(client, auth_headers, code="CNOPS"):
    r = await client.post(
        "/api/v1/third-party/payers",
        json={
            "code": code,
            "name": "Caisse Test",
            "type": "public",
            "default_coverage_rate": "0.80",
            "payment_terms_days": 60,
            "requires_prescription": True,
            "requires_authorization": False,
            "bordereau_frequency": "monthly",
            "rules": {},
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_payer(client, auth_headers):
    payer = await _create_payer(client, auth_headers)
    assert payer["code"] == "CNOPS"
    assert float(payer["default_coverage_rate"]) == 0.80


async def test_list_payers(client, auth_headers):
    await _create_payer(client, auth_headers, code="CNSS")
    r = await client.get("/api/v1/third-party/payers", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


async def test_get_payer_detail(client, auth_headers):
    payer = await _create_payer(client, auth_headers, code="MUT1")
    r = await client.get(f"/api/v1/third-party/payers/{payer['id']}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["code"] == "MUT1"


async def test_list_claims_empty(client, auth_headers):
    """Pas de claims tant qu'aucune vente tiers payant n'a eu lieu."""
    r = await client.get("/api/v1/third-party/claims", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_create_bordereau(client, auth_headers):
    """Générer un bordereau (même vide) pour une période."""
    payer = await _create_payer(client, auth_headers, code="BORD1")
    r = await client.post(
        "/api/v1/third-party/bordereaux",
        json={
            "payer_id": payer["id"],
            "period_start": "2026-05-01",
            "period_end": "2026-05-31",
            "claim_ids": None,
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["bordereau_number"]
    assert data["status"] in ("draft", "open", "pending")


async def test_submit_bordereau(client, auth_headers):
    payer = await _create_payer(client, auth_headers, code="BORD2")
    b = await client.post(
        "/api/v1/third-party/bordereaux",
        json={"payer_id": payer["id"], "period_start": "2026-05-01", "period_end": "2026-05-31", "claim_ids": None},
        headers=auth_headers,
    )
    bid = b.json()["id"]
    r = await client.post(f"/api/v1/third-party/bordereaux/{bid}/submit", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["submitted_at"] is not None


async def test_get_bordereau_detail_with_claims(client, auth_headers):
    payer = await _create_payer(client, auth_headers, code="BORD3")
    b = await client.post(
        "/api/v1/third-party/bordereaux",
        json={"payer_id": payer["id"], "period_start": "2026-05-01", "period_end": "2026-05-31", "claim_ids": None},
        headers=auth_headers,
    )
    bid = b.json()["id"]
    r = await client.get(f"/api/v1/third-party/bordereaux/{bid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert "claims" in r.json()


async def test_record_payment(client, auth_headers):
    """Enregistrer un paiement d'organisme sur un bordereau soumis."""
    payer = await _create_payer(client, auth_headers, code="PAY1")
    b = await client.post(
        "/api/v1/third-party/bordereaux",
        json={"payer_id": payer["id"], "period_start": "2026-05-01", "period_end": "2026-05-31", "claim_ids": None},
        headers=auth_headers,
    )
    bid = b.json()["id"]
    await client.post(f"/api/v1/third-party/bordereaux/{bid}/submit", headers=auth_headers)

    r = await client.post(
        "/api/v1/third-party/payments",
        json={
            "bordereau_id": bid,
            "amount": "0.00",
            "payment_method": "transfer",
            "reference": "VIR-TP-001",
            "rejected_claim_ids": None,
            "rejection_reasons": None,
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["reference"] == "VIR-TP-001"

    lst = await client.get("/api/v1/third-party/payments", headers=auth_headers)
    assert lst.status_code == 200, lst.text
    assert len(lst.json()) >= 1


async def test_payer_tenant_isolation(client):
    """Pharmacie B ne voit pas les payeurs de A."""
    rA = await client.post("/api/v1/auth/register", json={
        "email": "tp_a@x.com", "password": "passwordA123", "full_name": "A", "pharmacy": {"name": "PA"},
    })
    hA = {"Authorization": f"Bearer {rA.json()['access_token']}"}
    rB = await client.post("/api/v1/auth/register", json={
        "email": "tp_b@x.com", "password": "passwordB123", "full_name": "B", "pharmacy": {"name": "PB"},
    })
    hB = {"Authorization": f"Bearer {rB.json()['access_token']}"}

    await _create_payer(client, hA, code="ISOL")
    listB = await client.get("/api/v1/third-party/payers", headers=hB)
    assert listB.json() == []
