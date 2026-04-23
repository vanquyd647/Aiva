"""File upload API tests."""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User


def _admin_headers() -> dict[str, str]:
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == settings.INITIAL_ADMIN_EMAIL).first()
        assert admin is not None
        token = create_access_token(subject=str(admin.id), role=admin.role)
    finally:
        db.close()

    return {"Authorization": f"Bearer {token}"}


def test_upload_file_success() -> None:
    with TestClient(app) as client:
        headers = _admin_headers()
        response = client.post(
            "/api/v1/files/upload",
            headers=headers,
            files={"file": ("notes.txt", b"Hello upload test", "text/plain")},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["file_id"]
    assert payload["file_name"] == "notes.txt"
    assert payload["content_type"] == "text/plain"
    assert payload["size_bytes"] == len(b"Hello upload test")
    assert "Hello upload test" in (payload.get("preview_text") or "")


def test_upload_file_requires_auth() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/files/upload",
            files={"file": ("notes.txt", b"Hello", "text/plain")},
        )

    assert response.status_code == 401


def test_upload_file_rejects_unsupported_extension() -> None:
    with TestClient(app) as client:
        headers = _admin_headers()
        response = client.post(
            "/api/v1/files/upload",
            headers=headers,
            files={"file": ("payload.exe", b"MZ", "application/octet-stream")},
        )

    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]
