"""Admin user-management API tests."""

import uuid

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User


def _admin_headers(_: TestClient) -> dict[str, str]:
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == settings.INITIAL_ADMIN_EMAIL).first()
        assert admin is not None
        token = create_access_token(subject=str(admin.id), role=admin.role)
    finally:
        db.close()

    return {"Authorization": f"Bearer {token}"}


def test_admin_stats_update_and_password_reset_flow() -> None:
    with TestClient(app) as client:
        headers = _admin_headers(client)

        unique = uuid.uuid4().hex[:8]
        email = f"member_{unique}@example.com"
        create_response = client.post(
            "/api/v1/users",
            headers=headers,
            json={
                "email": email,
                "full_name": "Member Initial",
                "password": "InitialPass123",
                "role": "user",
                "is_active": True,
            },
        )
        assert create_response.status_code == 201
        created_user = create_response.json()

        stats_response = client.get("/api/v1/users/stats", headers=headers)
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats["total"] >= 1
        assert stats["active"] >= 1
        assert stats["admins"] >= 1

        update_response = client.patch(
            f"/api/v1/users/{created_user['id']}",
            headers=headers,
            json={
                "full_name": "Member Updated",
                "is_active": True,
            },
        )
        assert update_response.status_code == 200
        updated_user = update_response.json()
        assert updated_user["full_name"] == "Member Updated"
        assert updated_user["email"] == email

        reset_password_response = client.patch(
            f"/api/v1/users/{created_user['id']}/password",
            headers=headers,
            json={"new_password": "NewPass456!"},
        )
        assert reset_password_response.status_code == 200

        user_login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": email,
                "password": "NewPass456!",
            },
        )
        assert user_login_response.status_code == 200


def test_admin_cannot_downgrade_self() -> None:
    with TestClient(app) as client:
        headers = _admin_headers(client)
        me_response = client.get("/api/v1/auth/me", headers=headers)
        assert me_response.status_code == 200
        admin_id = me_response.json()["id"]

        downgrade_response = client.patch(
            f"/api/v1/users/{admin_id}",
            headers=headers,
            json={"role": "user"},
        )
        assert downgrade_response.status_code == 400
        assert "cannot downgrade" in downgrade_response.json()["detail"].lower()
