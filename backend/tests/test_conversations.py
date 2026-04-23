"""Conversation and message API tests."""

import uuid

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from app.db.session import SessionLocal


def _admin_headers(client: TestClient) -> dict[str, str]:
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == settings.INITIAL_ADMIN_EMAIL).first()
        assert admin is not None
        token = create_access_token(subject=str(admin.id), role=admin.role)
    finally:
        db.close()

    return {"Authorization": f"Bearer {token}"}


def _user_headers(client: TestClient, prefix: str = "member") -> dict[str, str]:
    admin_headers = _admin_headers(client)

    unique = uuid.uuid4().hex[:8]
    email = f"{prefix}_{unique}@example.com"
    password = "Passw0rd!234"

    create_response = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": email,
            "full_name": f"{prefix.title()} User",
            "password": password,
            "role": "user",
            "is_active": True,
        },
    )
    assert create_response.status_code == 201

    created_user = create_response.json()
    token = create_access_token(subject=str(created_user["id"]), role=created_user["role"])
    return {"Authorization": f"Bearer {token}"}


def test_conversation_and_message_lifecycle() -> None:
    with TestClient(app) as client:
        headers = _user_headers(client)

        create_conversation = client.post(
            "/api/v1/conversations",
            headers=headers,
            json={"title": "Sprint Planning"},
        )
        assert create_conversation.status_code == 201
        conversation = create_conversation.json()

        list_conversations = client.get("/api/v1/conversations", headers=headers)
        assert list_conversations.status_code == 200
        assert any(item["id"] == conversation["id"] for item in list_conversations.json()["items"])

        create_message = client.post(
            "/api/v1/messages",
            headers=headers,
            json={
                "conversation_id": conversation["id"],
                "role": "user",
                "content": "Hello from test",
                "status": "final",
            },
        )
        assert create_message.status_code == 201
        message = create_message.json()

        list_messages = client.get(
            "/api/v1/messages",
            params={"conversation_id": conversation["id"]},
            headers=headers,
        )
        assert list_messages.status_code == 200
        assert any(item["id"] == message["id"] for item in list_messages.json()["items"])

        update_message = client.patch(
            f"/api/v1/messages/{message['id']}",
            headers=headers,
            json={"content": "Hello updated"},
        )
        assert update_message.status_code == 200
        assert update_message.json()["content"] == "Hello updated"

        update_conversation = client.patch(
            f"/api/v1/conversations/{conversation['id']}",
            headers=headers,
            json={"title": "Sprint Planning Updated"},
        )
        assert update_conversation.status_code == 200
        assert update_conversation.json()["title"] == "Sprint Planning Updated"

        delete_conversation = client.delete(
            f"/api/v1/conversations/{conversation['id']}",
            headers=headers,
        )
        assert delete_conversation.status_code == 204

        missing_messages = client.get(
            "/api/v1/messages",
            params={"conversation_id": conversation["id"]},
            headers=headers,
        )
        assert missing_messages.status_code == 404


def test_conversation_access_is_isolated_per_user() -> None:
    with TestClient(app) as client:
        owner_headers = _user_headers(client, prefix="owner")
        other_headers = _user_headers(client, prefix="other")

        create_conversation = client.post(
            "/api/v1/conversations",
            headers=owner_headers,
            json={"title": "Private Thread"},
        )
        assert create_conversation.status_code == 201
        conversation_id = create_conversation.json()["id"]

        get_other_conversation = client.get(
            f"/api/v1/conversations/{conversation_id}",
            headers=other_headers,
        )
        assert get_other_conversation.status_code == 404

        post_other_message = client.post(
            "/api/v1/messages",
            headers=other_headers,
            json={
                "conversation_id": conversation_id,
                "role": "user",
                "content": "Should not be allowed",
                "status": "final",
            },
        )
        assert post_other_message.status_code == 404


def test_branch_conversation_clones_messages_until_cutoff() -> None:
    with TestClient(app) as client:
        headers = _user_headers(client, prefix="branch")

        create_conversation = client.post(
            "/api/v1/conversations",
            headers=headers,
            json={"title": "Branch Source"},
        )
        assert create_conversation.status_code == 201
        source_id = create_conversation.json()["id"]

        first_message = client.post(
            "/api/v1/messages",
            headers=headers,
            json={
                "conversation_id": source_id,
                "role": "user",
                "content": "Message 1",
                "status": "final",
            },
        )
        assert first_message.status_code == 201

        second_message = client.post(
            "/api/v1/messages",
            headers=headers,
            json={
                "conversation_id": source_id,
                "role": "assistant",
                "content": "Message 2",
                "status": "final",
            },
        )
        assert second_message.status_code == 201
        second_message_id = second_message.json()["id"]

        third_message = client.post(
            "/api/v1/messages",
            headers=headers,
            json={
                "conversation_id": source_id,
                "role": "user",
                "content": "Message 3",
                "status": "final",
            },
        )
        assert third_message.status_code == 201

        branch_response = client.post(
            f"/api/v1/conversations/{source_id}/branch",
            headers=headers,
            params={"from_message_id": second_message_id},
        )
        assert branch_response.status_code == 201
        branch_payload = branch_response.json()
        assert branch_payload["id"] != source_id
        assert branch_payload["title"].endswith("(branch)")

        source_messages = client.get(
            "/api/v1/messages",
            headers=headers,
            params={"conversation_id": source_id},
        )
        assert source_messages.status_code == 200
        assert len(source_messages.json()["items"]) == 3

        branch_messages = client.get(
            "/api/v1/messages",
            headers=headers,
            params={"conversation_id": branch_payload["id"]},
        )
        assert branch_messages.status_code == 200
        items = branch_messages.json()["items"]
        assert len(items) == 2
        assert [item["content"] for item in items] == ["Message 1", "Message 2"]


def test_branch_conversation_is_isolated_per_user() -> None:
    with TestClient(app) as client:
        owner_headers = _user_headers(client, prefix="branch_owner")
        other_headers = _user_headers(client, prefix="branch_other")

        create_conversation = client.post(
            "/api/v1/conversations",
            headers=owner_headers,
            json={"title": "Owner Conversation"},
        )
        assert create_conversation.status_code == 201
        conversation_id = create_conversation.json()["id"]

        create_message = client.post(
            "/api/v1/messages",
            headers=owner_headers,
            json={
                "conversation_id": conversation_id,
                "role": "user",
                "content": "Owner only",
                "status": "final",
            },
        )
        assert create_message.status_code == 201
        message_id = create_message.json()["id"]

        branch_response = client.post(
            f"/api/v1/conversations/{conversation_id}/branch",
            headers=other_headers,
            params={"from_message_id": message_id},
        )
        assert branch_response.status_code == 404
