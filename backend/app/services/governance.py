"""Governance helpers for audit, sessions, usage metering, and quota checks."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.usage_event import UsageEvent
from app.models.user import User
from app.models.user_session import UserSession

SENSITIVE_KEYS = {
    "password",
    "new_password",
    "access_token",
    "token",
    "authorization",
    "hashed_password",
    "secret",
    "data_base64",
}


def _sanitize_for_audit(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            lowered = key.lower()
            if lowered in SENSITIVE_KEYS:
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = _sanitize_for_audit(item)
        return sanitized

    if isinstance(value, list):
        return [_sanitize_for_audit(item) for item in value]

    if isinstance(value, str) and len(value) > 400:
        return value[:400] + "...[truncated]"

    return value


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def parse_details(details_json: str | None) -> dict[str, Any] | None:
    if not details_json:
        return None
    try:
        payload = json.loads(details_json)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def write_audit_log(
    db: Session,
    *,
    actor_user_id: int | None,
    action: str,
    target_type: str,
    target_id: str | None = None,
    status: str = "success",
    severity: str = "info",
    details: dict[str, Any] | None = None,
) -> AuditLog:
    serialized: str | None = None
    if details:
        safe_details = _sanitize_for_audit(details)
        serialized = json.dumps(safe_details, ensure_ascii=False)

    row = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        status=status,
        severity=severity,
        details_json=serialized,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_user_session(
    db: Session,
    *,
    user_id: int,
    session_id: str,
    token: str,
    ip_address: str | None,
    user_agent: str | None,
) -> UserSession:
    row = UserSession(
        user_id=user_id,
        session_id=session_id,
        token_hash=hash_token(token),
        ip_address=(ip_address or "").strip()[:64] or None,
        user_agent=(user_agent or "").strip()[:255] or None,
        last_seen_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def revoke_session_by_sid(db: Session, session_id: str) -> bool:
    row = db.query(UserSession).filter(UserSession.session_id == session_id).first()
    if not row:
        return False
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        db.commit()
    return True


def revoke_user_sessions(db: Session, user_id: int) -> int:
    rows = (
        db.query(UserSession)
        .filter(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .all()
    )
    if not rows:
        return 0

    now = datetime.now(UTC)
    for row in rows:
        row.revoked_at = now
    db.commit()
    return len(rows)


def touch_session_last_seen(db: Session, session_id: str) -> None:
    row = (
        db.query(UserSession)
        .filter(UserSession.session_id == session_id, UserSession.revoked_at.is_(None))
        .first()
    )
    if not row:
        return

    now = datetime.now(UTC)
    if row.last_seen_at and (now - row.last_seen_at).total_seconds() < 60:
        return

    row.last_seen_at = now
    db.commit()


def record_usage_event(
    db: Session,
    *,
    user_id: int,
    metric: str,
    quantity: int,
    source: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    if quantity <= 0:
        return

    meta_json = None
    if metadata:
        meta_json = json.dumps(_sanitize_for_audit(metadata), ensure_ascii=False)

    db.add(
        UsageEvent(
            user_id=user_id,
            metric=metric,
            quantity=quantity,
            source=source,
            meta_json=meta_json,
        )
    )
    db.commit()


def usage_window_start() -> datetime:
    return datetime.now(UTC) - timedelta(days=settings.USAGE_WINDOW_DAYS)


def estimate_tokens(text: str) -> int:
    raw = len((text or "").strip())
    if raw <= 0:
        return 0
    return max(1, raw // 4)


def _limits_for_role(role: str) -> tuple[int, int]:
    if role == "admin":
        return settings.QUOTA_ADMIN_MESSAGE_LIMIT, settings.QUOTA_ADMIN_TOKEN_LIMIT
    return settings.QUOTA_USER_MESSAGE_LIMIT, settings.QUOTA_USER_TOKEN_LIMIT


def _ratio(used: int, limit: int) -> float:
    if limit <= 0:
        return 0.0
    return round(used / limit, 4)


def _alert_level(message_ratio: float, token_ratio: float) -> str:
    highest = max(message_ratio, token_ratio)
    if highest >= 1.0:
        return "exceeded"
    if highest >= settings.QUOTA_ALERT_THRESHOLD_RATIO:
        return "warning"
    return "ok"


def user_usage_summary(db: Session, *, user_id: int, role: str) -> dict[str, Any]:
    start_at = usage_window_start()

    rows = (
        db.query(UsageEvent.metric, func.coalesce(func.sum(UsageEvent.quantity), 0))
        .filter(UsageEvent.user_id == user_id, UsageEvent.created_at >= start_at)
        .group_by(UsageEvent.metric)
        .all()
    )
    totals = {metric: int(total or 0) for metric, total in rows}

    messages_used = totals.get("chat_messages", 0)
    tokens_used = totals.get("chat_tokens", 0)
    message_limit, token_limit = _limits_for_role(role)

    message_ratio = _ratio(messages_used, message_limit)
    token_ratio = _ratio(tokens_used, token_limit)

    return {
        "window_days": settings.USAGE_WINDOW_DAYS,
        "messages_used": messages_used,
        "message_limit": message_limit,
        "message_ratio": message_ratio,
        "tokens_used": tokens_used,
        "token_limit": token_limit,
        "token_ratio": token_ratio,
        "alert_threshold_ratio": settings.QUOTA_ALERT_THRESHOLD_RATIO,
        "alert_level": _alert_level(message_ratio, token_ratio),
    }


def usage_overview(db: Session, *, page: int, page_size: int) -> dict[str, Any]:
    start_at = usage_window_start()

    system_rows = (
        db.query(UsageEvent.metric, func.coalesce(func.sum(UsageEvent.quantity), 0))
        .filter(UsageEvent.created_at >= start_at)
        .group_by(UsageEvent.metric)
        .all()
    )
    system_totals = {metric: int(total or 0) for metric, total in system_rows}

    user_rows = (
        db.query(
            User.id,
            User.email,
            User.full_name,
            User.role,
            UsageEvent.metric,
            func.coalesce(func.sum(UsageEvent.quantity), 0),
        )
        .join(UsageEvent, UsageEvent.user_id == User.id)
        .filter(UsageEvent.created_at >= start_at)
        .group_by(User.id, User.email, User.full_name, User.role, UsageEvent.metric)
        .all()
    )

    by_user: dict[int, dict[str, Any]] = {}
    for user_id, email, full_name, role, metric, total in user_rows:
        if user_id not in by_user:
            by_user[user_id] = {
                "user_id": int(user_id),
                "email": email,
                "full_name": full_name,
                "role": role,
                "messages_used": 0,
                "tokens_used": 0,
                "alert_level": "ok",
            }

        if metric == "chat_messages":
            by_user[user_id]["messages_used"] = int(total or 0)
        elif metric == "chat_tokens":
            by_user[user_id]["tokens_used"] = int(total or 0)

    for payload in by_user.values():
        message_limit, token_limit = _limits_for_role(payload["role"])
        message_ratio = _ratio(payload["messages_used"], message_limit)
        token_ratio = _ratio(payload["tokens_used"], token_limit)
        payload["alert_level"] = _alert_level(message_ratio, token_ratio)

    ranked = sorted(
        by_user.values(),
        key=lambda item: (item["alert_level"], item["messages_used"], item["tokens_used"]),
        reverse=True,
    )

    start_idx = max(0, (page - 1) * page_size)
    end_idx = start_idx + page_size
    paged = ranked[start_idx:end_idx]

    users_over_warning = sum(1 for item in by_user.values() if item["alert_level"] == "warning")
    users_exceeded = sum(1 for item in by_user.values() if item["alert_level"] == "exceeded")

    return {
        "window_days": settings.USAGE_WINDOW_DAYS,
        "total_messages": system_totals.get("chat_messages", 0),
        "total_tokens": system_totals.get("chat_tokens", 0),
        "users_over_warning": users_over_warning,
        "users_exceeded": users_exceeded,
        "top_users": paged,
    }


def will_exceed_quota(summary: dict[str, Any]) -> bool:
    return str(summary.get("alert_level", "ok")) == "exceeded"
