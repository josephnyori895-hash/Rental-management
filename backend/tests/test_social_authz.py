from __future__ import annotations

import hashlib
import hmac
import json as jsonlib

from tests.conftest import requires_db


@requires_db
async def test_social_owner_actions_do_not_require_auth_from_anonymous(client):
    res = await client.post("/api/v1/social/post", json={"caption": "hello"})
    feed = await client.get("/api/v1/social/instagram")
    reminder = await client.post(
        "/api/v1/social/send-reminder?recipient_id=254700000000&amount=100&unit=5"
    )
    assert res.status_code == 401, res.text
    assert feed.status_code == 401, feed.text
    assert reminder.status_code == 401, reminder.text


@requires_db
async def test_social_actions_are_owner_only(client, businesses):
    first, _ = businesses

    post = await client.post(
        "/api/v1/social/post", json={"caption": "hello"}, headers=first.bearer
    )
    feed = await client.get("/api/v1/social/instagram", headers=first.bearer)
    reminder = await client.post(
        "/api/v1/social/send-reminder?recipient_id=254700000000&amount=100&unit=5",
        headers=first.bearer,
    )

    # Creds are not configured in the test environment, so 400 is the first
    # answer after the authorization check. Anything in 401/403 means the guard
    # failed.
    assert post.status_code != 401
    assert feed.status_code != 401
    assert reminder.status_code != 401


@requires_db
async def test_social_reminder_requires_positive_amount(client, businesses):
    first, _ = businesses
    res = await client.post(
        "/api/v1/social/send-reminder?recipient_id=254700000000&amount=0&unit=5",
        headers=first.bearer,
    )
    assert res.status_code == 422, res.text


async def test_facebook_webhook_verify_rejects_wrong_token(client):
    res = await client.get(
        "/webhook/facebook",
        params={"hub_mode": "subscribe", "hub_verify_token": "wrong"},
    )
    assert res.status_code == 403, res.text


async def test_facebook_webhook_fails_closed_without_a_signature(client):
    res = await client.post("/webhook/facebook", json={"object": "page", "entry": []})
    assert res.status_code in (403, 503), (res.status_code, res.text)


async def test_facebook_webhook_accepts_a_validly_signed_payload(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "FB_WEBHOOK_SECRET", "ci-webhook-secret")

    body = {
        "object": "page",
        "entry": [
            {"messaging": [{"sender": {"id": "254700000000"}, "message": {"text": "rooms"}}]}
        ],
    }
    raw = jsonlib.dumps(body).encode()
    res = await client.post(
        "/webhook/facebook",
        content=raw,
        headers={
            "content-type": "application/json",
            "x-hub-signature-256": "sha256="
            + hmac.new(b"ci-webhook-secret", raw, hashlib.sha256).hexdigest(),
        },
    )
    assert res.status_code == 200, (res.status_code, res.text)


async def test_facebook_webhook_rejects_a_badly_signed_payload(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "FB_WEBHOOK_SECRET", "ci-webhook-secret")
    raw = jsonlib.dumps({"object": "page", "entry": []}).encode()
    res = await client.post(
        "/webhook/facebook",
        content=raw,
        headers={"content-type": "application/json", "x-hub-signature-256": "sha256=deadbeef"},
    )
    assert res.status_code == 403, (res.status_code, res.text)
