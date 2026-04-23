"""Authentication route smoke tests."""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_admin_login_and_user_access() -> None:
    with TestClient(app) as client:
        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": settings.INITIAL_ADMIN_EMAIL,
                "password": settings.INITIAL_ADMIN_PASSWORD,
            },
        )
        assert login_response.status_code == 200

        token = login_response.json()["access_token"]
        users_response = client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert users_response.status_code == 200
