"""Security unit tests."""

from app.core.security import (
    create_access_token,
    decode_token,
    get_password_hash,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    password = "Str0ngP@ssw0rd"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_contains_subject_and_role() -> None:
    token = create_access_token(subject="42", role="admin")
    payload = decode_token(token)

    assert payload["sub"] == "42"
    assert payload["role"] == "admin"
    assert "exp" in payload
    assert "iat" in payload
