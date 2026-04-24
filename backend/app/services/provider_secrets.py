"""Provider secret rotation and encryption helpers."""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime

from cryptography.fernet import Fernet
from google import genai
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.provider_secret import ProviderSecret

GEMINI_PROVIDER = "gemini"
ACTIVE_STATUS = "active"


def _get_encryption_key_material() -> str:
    value = (settings.GEMINI_SECRET_ENCRYPTION_KEY or settings.SECRET_KEY or "").strip()
    if not value:
        raise ValueError("Encryption key is not configured")
    return value


def _build_fernet() -> Fernet:
    digest = hashlib.sha256(_get_encryption_key_material().encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def compute_secret_fingerprint(secret_value: str) -> str:
    return hashlib.sha256(secret_value.encode("utf-8")).hexdigest()


def format_fingerprint(fingerprint: str | None) -> str | None:
    if not fingerprint:
        return None
    if len(fingerprint) <= 12:
        return fingerprint
    return f"{fingerprint[:6]}...{fingerprint[-6:]}"


def encrypt_secret(secret_value: str) -> str:
    fernet = _build_fernet()
    token = fernet.encrypt(secret_value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    fernet = _build_fernet()
    clear = fernet.decrypt(ciphertext.encode("utf-8"))
    return clear.decode("utf-8")


def get_active_provider_secret(
    db: Session, provider: str = GEMINI_PROVIDER
) -> ProviderSecret | None:
    return (
        db.query(ProviderSecret)
        .filter(
            ProviderSecret.provider == provider,
            ProviderSecret.status == ACTIVE_STATUS,
        )
        .order_by(ProviderSecret.rotated_at.desc(), ProviderSecret.id.desc())
        .first()
    )


def get_active_provider_secret_value(
    db: Session, provider: str = GEMINI_PROVIDER
) -> tuple[str, str] | None:
    row = get_active_provider_secret(db, provider=provider)
    if row is None:
        return None
    return decrypt_secret(row.secret_ciphertext), row.secret_fingerprint


def rotate_provider_secret(
    db: Session,
    *,
    provider: str,
    raw_secret: str,
    rotated_by_user_id: int | None,
    reason: str | None,
) -> tuple[ProviderSecret, bool]:
    normalized = raw_secret.strip()
    if not normalized:
        raise ValueError("Provider secret cannot be empty")

    fingerprint = compute_secret_fingerprint(normalized)
    active = get_active_provider_secret(db, provider=provider)

    if active and active.secret_fingerprint == fingerprint:
        return active, False

    version = 1
    now = datetime.now(UTC)
    if active:
        version = active.key_version + 1
        active.status = "rotated"
        active.updated_at = now

    row = ProviderSecret(
        provider=provider,
        secret_ciphertext=encrypt_secret(normalized),
        secret_fingerprint=fingerprint,
        key_version=version,
        status=ACTIVE_STATUS,
        rotated_reason=(reason or "").strip()[:255] or None,
        rotated_by_user_id=rotated_by_user_id,
        rotated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, True


def validate_gemini_api_key(
    api_key: str,
    *,
    model: str,
) -> tuple[bool, str | None]:
    """Validate a Gemini key by issuing a tiny request to the model endpoint."""
    try:
        client = genai.Client(api_key=api_key)
        client.models.generate_content(
            model=model,
            contents="ping",
        )
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    return True, None
