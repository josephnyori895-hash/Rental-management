"""End-to-end tests for the public owner registration and authentication flow."""

from __future__ import annotations


async def test_owner_can_register_sign_in_and_fetch_profile(client):
    registration = {
        "business_name": "CI Auth Flow Rentals",
        "owner_full_name": "CI Test Owner",
        "email": "rental-auth-ci@example.com",
        "password": "ci-safe-test-password-2026",
        "phone": "+254700000001",
    }

    created = await client.post("/api/v1/auth/register", json=registration)
    assert created.status_code == 201, created.text
    business = created.json()
    assert business["name"] == registration["business_name"]
    assert business["slug"]

    duplicate = await client.post("/api/v1/auth/register", json=registration)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Email already registered"

    invalid_login = await client.post(
        "/api/v1/auth/login",
        json={"email": registration["email"], "password": "incorrect-password"},
    )
    assert invalid_login.status_code == 401

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": registration["email"], "password": registration["password"]},
    )
    assert login.status_code == 200, login.text
    tokens = login.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["token_type"] == "bearer"

    profile = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert profile.status_code == 200, profile.text
    user = profile.json()
    assert user["email"] == registration["email"]
    assert user["full_name"] == registration["owner_full_name"]
    assert user["role"] == "owner"
    assert user["is_active"] is True
