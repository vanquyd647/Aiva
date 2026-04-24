"""Application service for admin Gemini key operations."""

from __future__ import annotations

import os

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.cache import cache
from app.services.chat_stream import reset_client as reset_chat_stream_client
from app.services.governance import record_usage_event, write_audit_log
from app.services.provider_secrets import (
    GEMINI_PROVIDER,
    compute_secret_fingerprint,
    format_fingerprint,
    get_active_provider_secret,
    rotate_provider_secret,
    validate_gemini_api_key,
)


class GeminiKeyServiceError(Exception):
    """Service-level error with HTTP-oriented status code and safe detail."""

    def __init__(self, detail: str, *, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


async def enforce_rotate_rate_limit(*, actor_user_id: int, client_ip: str) -> None:
    rate_key = f"admin:gemini_key_rotate:{actor_user_id}:{client_ip}"
    attempts = await cache.increment(rate_key, ttl_seconds=60)
    if attempts > settings.RATE_LIMIT_GEMINI_KEY_ROTATE_PER_MINUTE:
        raise GeminiKeyServiceError(
            "Too many key rotation attempts, retry in 60 seconds",
            status_code=429,
        )


def get_status_payload(*, db: Session, actor_user_id: int) -> dict:
    row = get_active_provider_secret(db, provider=GEMINI_PROVIDER)
    if row is not None:
        source = "database"
        has_active_key = True
        fingerprint = format_fingerprint(row.secret_fingerprint)
        key_version = row.key_version
        rotated_at = row.rotated_at
        updated_at = row.updated_at
    else:
        env_key = os.getenv("GEMINI_API_KEY", "").strip()
        has_env = bool(env_key) and settings.GEMINI_FALLBACK_ENV_API_KEY_ENABLED
        source = "env" if has_env else "none"
        has_active_key = has_env
        fingerprint = format_fingerprint(compute_secret_fingerprint(env_key)) if has_env else None
        key_version = None
        rotated_at = None
        updated_at = None

    write_audit_log(
        db,
        actor_user_id=actor_user_id,
        action="admin.gemini_key.view",
        target_type="provider_secret",
        status="success",
        severity="info",
        details={"provider": GEMINI_PROVIDER, "source": source, "has_active_key": has_active_key},
    )

    return {
        "provider": GEMINI_PROVIDER,
        "has_active_key": has_active_key,
        "source": source,
        "fingerprint": fingerprint,
        "key_version": key_version,
        "rotated_at": rotated_at,
        "updated_at": updated_at,
    }


def rotate_payload(
    *,
    db: Session,
    actor_user_id: int,
    api_key: str,
    reason: str | None,
    dry_run: bool,
    validate_with_provider: bool,
    test_model: str | None,
) -> dict:
    raw_key = api_key.strip()
    if len(raw_key) < 20:
        raise GeminiKeyServiceError("Invalid Gemini API key", status_code=400)

    validated = False
    if validate_with_provider:
        model = test_model or settings.GEMINI_VALIDATION_MODEL
        ok, error = validate_gemini_api_key(raw_key, model=model)
        if not ok:
            write_audit_log(
                db,
                actor_user_id=actor_user_id,
                action="admin.gemini_key.rotate",
                target_type="provider_secret",
                status="failed",
                severity="warning",
                details={
                    "provider": GEMINI_PROVIDER,
                    "dry_run": dry_run,
                    "validate_with_provider": True,
                    "reason": (error or "validation_failed")[:300],
                },
            )
            raise GeminiKeyServiceError(
                f"Gemini key validation failed: {error or 'unknown error'}",
                status_code=400,
            )
        validated = True

    if dry_run:
        fingerprint = format_fingerprint(compute_secret_fingerprint(raw_key)) or "hidden"
        write_audit_log(
            db,
            actor_user_id=actor_user_id,
            action="admin.gemini_key.dry_run",
            target_type="provider_secret",
            status="success",
            severity="info",
            details={
                "provider": GEMINI_PROVIDER,
                "validate_with_provider": validate_with_provider,
                "validated": validated,
            },
        )
        return {
            "status": "dry-run",
            "provider": GEMINI_PROVIDER,
            "fingerprint": fingerprint,
            "dry_run_validated": validated,
            "message": "Gemini key validation succeeded (dry-run)",
            "key_version": None,
            "rotated_at": None,
        }

    row, changed = rotate_provider_secret(
        db,
        provider=GEMINI_PROVIDER,
        raw_secret=raw_key,
        rotated_by_user_id=actor_user_id,
        reason=reason,
    )

    reset_chat_stream_client()

    record_usage_event(
        db,
        user_id=actor_user_id,
        metric="admin_actions",
        quantity=1,
        source="admin",
        metadata={
            "action": "gemini_key_rotate",
            "provider": GEMINI_PROVIDER,
            "changed": changed,
        },
    )

    write_audit_log(
        db,
        actor_user_id=actor_user_id,
        action="admin.gemini_key.rotate",
        target_type="provider_secret",
        target_id=str(row.id),
        status="success",
        severity="warning",
        details={
            "provider": GEMINI_PROVIDER,
            "changed": changed,
            "key_version": row.key_version,
            "validate_with_provider": validate_with_provider,
            "validated": validated,
        },
    )

    return {
        "status": "ok",
        "provider": GEMINI_PROVIDER,
        "fingerprint": format_fingerprint(row.secret_fingerprint) or "hidden",
        "key_version": row.key_version,
        "rotated_at": row.rotated_at,
        "dry_run_validated": validated,
        "message": "Gemini API key rotated successfully",
    }
