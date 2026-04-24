"""Provider secret service tests."""

from app.db.base import Base
from app.db.session import SessionLocal
from app.db.session import engine
from app.models.provider_secret import ProviderSecret
from app.services.provider_secrets import (
    GEMINI_PROVIDER,
    decrypt_secret,
    encrypt_secret,
    get_active_provider_secret,
    rotate_provider_secret,
)


def _clear_provider_secrets() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(ProviderSecret).delete()
        db.commit()
    finally:
        db.close()


def test_encrypt_decrypt_secret_roundtrip() -> None:
    raw = "AIzaSySecretRoundTrip123456789"
    encrypted = encrypt_secret(raw)

    assert encrypted != raw
    assert raw not in encrypted
    assert decrypt_secret(encrypted) == raw


def test_rotate_provider_secret_increments_version_and_deactivates_previous() -> None:
    _clear_provider_secrets()
    db = SessionLocal()
    try:
        first, first_changed = rotate_provider_secret(
            db,
            provider=GEMINI_PROVIDER,
            raw_secret="AIzaSyRotateV1_1234567890123",
            rotated_by_user_id=None,
            reason="initial",
        )
        assert first_changed is True
        assert first.key_version == 1
        assert first.status == "active"

        second, second_changed = rotate_provider_secret(
            db,
            provider=GEMINI_PROVIDER,
            raw_secret="AIzaSyRotateV2_1234567890123",
            rotated_by_user_id=None,
            reason="second",
        )
        assert second_changed is True
        assert second.key_version == 2
        assert second.status == "active"

        db.refresh(first)
        assert first.status == "rotated"

        active = get_active_provider_secret(db, provider=GEMINI_PROVIDER)
        assert active is not None
        assert active.id == second.id
    finally:
        db.close()
