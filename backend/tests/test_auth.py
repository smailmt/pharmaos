"""Tests E2E pour le module Auth."""
import pytest


async def test_register_creates_pharmacy_and_user(client):
    payload = {
        "email": "owner@example.com",
        "password": "password123",
        "full_name": "Dr. Karim",
        "pharmacy": {"name": "Pharma1", "city": "Rabat"},
        "plan": "starter",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["user"]["email"] == "owner@example.com"
    assert data["user"]["role"] == "owner"
    assert data["pharmacy"]["name"] == "Pharma1"
    assert data["pharmacy"]["plan"] == "starter"


async def test_register_duplicate_email_fails(client):
    payload = {
        "email": "dup@example.com",
        "password": "password123",
        "full_name": "User1",
        "pharmacy": {"name": "P"},
    }
    r1 = await client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409


async def test_register_short_password_fails(client):
    payload = {
        "email": "short@example.com",
        "password": "123",  # < 8 chars
        "full_name": "X",
        "pharmacy": {"name": "P"},
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


async def test_login_success(client, registered_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "testpass123"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_login_wrong_password(client, registered_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "wrongpass"},
    )
    assert response.status_code == 401


async def test_me_requires_auth(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_returns_user(client, auth_headers):
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


async def test_pharmacy_endpoint(client, auth_headers):
    response = await client.get("/api/v1/auth/pharmacy", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Pharmacie Test"
    assert data["city"] == "Casablanca"
    assert data["plan"] == "pro"
