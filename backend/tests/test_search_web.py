"""Web search API tests."""

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


def test_search_web_returns_results(monkeypatch) -> None:
    def fake_search_web(query: str, limit: int = 5, timeout_seconds: int = 12):
        assert query == "ai governance"
        assert limit == 3
        return [
            {
                "title": "Governance Guide",
                "url": "https://example.org/guide",
                "snippet": "Policy and governance summary",
                "source": "example.org",
            }
        ]

    monkeypatch.setattr("app.api.routes.search.search_web", fake_search_web)

    with TestClient(app) as client:
        headers = _admin_headers()
        response = client.get(
            "/api/v1/search/web",
            headers=headers,
            params={"q": "ai governance", "limit": 3},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "ai governance"
    assert payload["provider"] == "duckduckgo"
    assert payload["results"]
    assert payload["results"][0]["url"] == "https://example.org/guide"


def test_search_web_requires_auth() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/search/web", params={"q": "test"})

    assert response.status_code == 401
