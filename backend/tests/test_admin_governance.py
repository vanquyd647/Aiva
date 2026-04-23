"""Governance and usage API tests."""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def _login_admin(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": settings.INITIAL_ADMIN_EMAIL,
            "password": settings.INITIAL_ADMIN_PASSWORD,
        },
    )
    assert response.status_code == 200
    return response.json()


def _collect_events(response) -> list[tuple[str | None, dict]]:
    events: list[tuple[str | None, dict]] = []
    current_event: str | None = None
    for raw_line in response.iter_lines():
        line = raw_line.decode() if isinstance(raw_line, bytes) else raw_line
        if line is None:
            continue
        line = line.strip()
        if not line:
            continue
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
            continue
        if line.startswith("data:"):
            payload = json.loads(line.split(":", 1)[1].strip())
            events.append((current_event, payload))
    return events


def test_admin_can_revoke_session_and_token_stops_working() -> None:
    with TestClient(app) as client:
        auth_payload = _login_admin(client)
        token = auth_payload["access_token"]
        session_id = auth_payload["session_id"]
        headers = {"Authorization": f"Bearer {token}"}

        sessions_response = client.get("/api/v1/admin/sessions", headers=headers)
        assert sessions_response.status_code == 200
        listed_ids = {item["session_id"] for item in sessions_response.json()["items"]}
        assert session_id in listed_ids

        revoke_response = client.post(
            f"/api/v1/admin/sessions/{session_id}/revoke", headers=headers
        )
        assert revoke_response.status_code == 200

        me_response = client.get("/api/v1/auth/me", headers=headers)
        assert me_response.status_code == 401


def test_chat_quota_enforced_when_limit_is_reached(monkeypatch) -> None:
    old_message_limit = settings.QUOTA_ADMIN_MESSAGE_LIMIT
    old_token_limit = settings.QUOTA_ADMIN_TOKEN_LIMIT
    old_threshold = settings.QUOTA_ALERT_THRESHOLD_RATIO
    settings.QUOTA_ALERT_THRESHOLD_RATIO = 0.8
    settings.QUOTA_ADMIN_TOKEN_LIMIT = 10_000_000

    def fake_stream_chat_text(messages, cfg):
        yield "ok"

    monkeypatch.setattr("app.api.routes.chat.stream_chat_text", fake_stream_chat_text)

    try:
        with TestClient(app) as client:
            auth_payload = _login_admin(client)
            headers = {"Authorization": f"Bearer {auth_payload['access_token']}"}

            pre_usage_response = client.get("/api/v1/usage/me", headers=headers)
            assert pre_usage_response.status_code == 200
            already_used = int(pre_usage_response.json().get("messages_used", 0) or 0)
            settings.QUOTA_ADMIN_MESSAGE_LIMIT = already_used + 1

            with client.stream(
                "POST",
                "/api/v1/chat/stream",
                headers=headers,
                json={"messages": [{"role": "user", "text": "turn1"}]},
            ) as first_response:
                assert first_response.status_code == 200
                first_events = _collect_events(first_response)
                done_payloads = [payload for event, payload in first_events if event == "done"]
                assert done_payloads and done_payloads[-1]["text"] == "ok"

            with client.stream(
                "POST",
                "/api/v1/chat/stream",
                headers=headers,
                json={"messages": [{"role": "user", "text": "turn2"}]},
            ) as second_response:
                assert second_response.status_code == 429

            usage_response = client.get("/api/v1/usage/me", headers=headers)
            assert usage_response.status_code == 200
            usage_payload = usage_response.json()
            assert usage_payload["messages_used"] >= 1
            assert usage_payload["alert_level"] == "exceeded"
    finally:
        settings.QUOTA_ADMIN_MESSAGE_LIMIT = old_message_limit
        settings.QUOTA_ADMIN_TOKEN_LIMIT = old_token_limit
        settings.QUOTA_ALERT_THRESHOLD_RATIO = old_threshold


def test_admin_actions_are_present_in_audit_log() -> None:
    with TestClient(app) as client:
        auth_payload = _login_admin(client)
        headers = {"Authorization": f"Bearer {auth_payload['access_token']}"}

        unique = uuid.uuid4().hex[:8]
        email = f"audit_{unique}@example.com"
        create_response = client.post(
            "/api/v1/users",
            headers=headers,
            json={
                "email": email,
                "full_name": "Audit Target",
                "password": "AuditPass123!",
                "role": "user",
                "is_active": True,
            },
        )
        assert create_response.status_code == 201

        audit_response = client.get(
            "/api/v1/admin/audit",
            headers=headers,
            params={"action": "users.create", "page": 1, "page_size": 50},
        )
        assert audit_response.status_code == 200
        items = audit_response.json()["items"]
        assert any(
            item["action"] == "users.create" and item["status"] == "success" for item in items
        )
