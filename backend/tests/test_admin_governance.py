"""Governance and usage API tests."""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.provider_secret import ProviderSecret


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


def _clear_provider_secrets() -> None:
    db = SessionLocal()
    try:
        db.query(ProviderSecret).delete()
        db.commit()
    finally:
        db.close()


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


def test_backend_monitor_returns_runtime_snapshot() -> None:
    with TestClient(app) as client:
        auth_payload = _login_admin(client)
        headers = {"Authorization": f"Bearer {auth_payload['access_token']}"}

        response = client.get("/api/v1/admin/backend-monitor", headers=headers)
        assert response.status_code == 200

        payload = response.json()
        assert payload["status"] in {"ok", "degraded"}
        assert payload["db_status"] in {"ready", "error"}
        assert payload["cache_mode"] in {"memory", "redis"}
        assert payload["gemini_key_source"] in {"database", "env", "none"}
        assert payload["gemini_validation_model"] == settings.GEMINI_VALIDATION_MODEL
        assert isinstance(payload["total_users"], int)
        assert isinstance(payload["active_users"], int)
        assert isinstance(payload["active_sessions"], int)


def test_gemini_key_dry_run_does_not_persist(monkeypatch) -> None:
    old_fallback = settings.GEMINI_FALLBACK_ENV_API_KEY_ENABLED
    settings.GEMINI_FALLBACK_ENV_API_KEY_ENABLED = False
    _clear_provider_secrets()
    monkeypatch.setattr(
        "app.services.admin_gemini_keys.validate_gemini_api_key",
        lambda api_key, model: (True, None),
    )

    try:
        with TestClient(app) as client:
            auth_payload = _login_admin(client)
            headers = {"Authorization": f"Bearer {auth_payload['access_token']}"}

            response = client.post(
                "/api/v1/admin/gemini-key",
                headers=headers,
                json={
                    "api_key": "AIzaSyDryRunOnlyKey123456789012345678",
                    "reason": "dry run check",
                    "dry_run": True,
                    "validate_with_provider": True,
                },
            )
            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "dry-run"
            assert body["dry_run_validated"] is True

            status_response = client.get("/api/v1/admin/gemini-key", headers=headers)
            assert status_response.status_code == 200
            status_payload = status_response.json()
            assert status_payload["has_active_key"] is False
            assert status_payload["source"] == "none"
    finally:
        settings.GEMINI_FALLBACK_ENV_API_KEY_ENABLED = old_fallback


def test_gemini_key_rotation_persists_and_resets_client(monkeypatch) -> None:
    old_fallback = settings.GEMINI_FALLBACK_ENV_API_KEY_ENABLED
    settings.GEMINI_FALLBACK_ENV_API_KEY_ENABLED = False
    _clear_provider_secrets()

    reset_calls = {"count": 0}

    def _fake_reset_client() -> None:
        reset_calls["count"] += 1

    monkeypatch.setattr(
        "app.services.admin_gemini_keys.validate_gemini_api_key",
        lambda api_key, model: (True, None),
    )
    monkeypatch.setattr(
        "app.services.admin_gemini_keys.reset_chat_stream_client", _fake_reset_client
    )

    key_value = "AIzaSyRotationKey1234567890123456789012"

    try:
        with TestClient(app) as client:
            auth_payload = _login_admin(client)
            headers = {"Authorization": f"Bearer {auth_payload['access_token']}"}

            rotate_response = client.post(
                "/api/v1/admin/gemini-key",
                headers=headers,
                json={
                    "api_key": key_value,
                    "reason": "scheduled rotation",
                    "dry_run": False,
                    "validate_with_provider": False,
                },
            )
            assert rotate_response.status_code == 200
            rotate_payload = rotate_response.json()
            assert rotate_payload["status"] == "ok"
            assert rotate_payload["key_version"] >= 1
            assert reset_calls["count"] == 1

            status_response = client.get("/api/v1/admin/gemini-key", headers=headers)
            assert status_response.status_code == 200
            status_payload = status_response.json()
            assert status_payload["has_active_key"] is True
            assert status_payload["source"] == "database"
            assert status_payload["key_version"] == rotate_payload["key_version"]
            assert status_payload["fingerprint"] == rotate_payload["fingerprint"]

            audit_response = client.get(
                "/api/v1/admin/audit",
                headers=headers,
                params={"action": "admin.gemini_key.rotate", "page": 1, "page_size": 20},
            )
            assert audit_response.status_code == 200
            items = audit_response.json()["items"]
            assert items
            assert any(item["status"] == "success" for item in items)
            for item in items:
                details = json.dumps(item.get("details") or {})
                assert key_value not in details
    finally:
        settings.GEMINI_FALLBACK_ENV_API_KEY_ENABLED = old_fallback
