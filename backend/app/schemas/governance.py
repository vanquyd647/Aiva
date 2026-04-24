"""Schema models for admin governance and usage dashboards."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AuditLogOut(BaseModel):
    id: int
    actor_user_id: int | None = None
    actor_email: str | None = None
    action: str
    target_type: str
    target_id: str | None = None
    status: str
    severity: str
    details: dict[str, Any] | None = None
    created_at: datetime


class AuditLogListOut(BaseModel):
    items: list[AuditLogOut]
    total: int
    page: int
    page_size: int


class UserSessionOut(BaseModel):
    session_id: str
    user_id: int
    user_email: str
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime
    last_seen_at: datetime | None = None
    revoked_at: datetime | None = None


class UserSessionListOut(BaseModel):
    items: list[UserSessionOut]
    total: int
    page: int
    page_size: int


class UserUsageSummaryOut(BaseModel):
    window_days: int
    messages_used: int
    message_limit: int
    message_ratio: float
    tokens_used: int
    token_limit: int
    token_ratio: float
    alert_threshold_ratio: float
    alert_level: str = Field(pattern="^(ok|warning|exceeded)$")


class UsageTopUserOut(BaseModel):
    user_id: int
    email: str
    full_name: str
    role: str
    messages_used: int
    tokens_used: int
    alert_level: str = Field(pattern="^(ok|warning|exceeded)$")


class UsageOverviewOut(BaseModel):
    window_days: int
    total_messages: int
    total_tokens: int
    users_over_warning: int
    users_exceeded: int
    top_users: list[UsageTopUserOut]


class BackendMonitorOut(BaseModel):
    status: Literal["ok", "degraded"]
    generated_at: datetime
    app_name: str
    env: str
    db_status: Literal["ready", "error"]
    cache_mode: str

    total_users: int
    active_users: int
    active_sessions: int
    revoked_sessions: int

    audit_events_24h: int
    usage_events_24h: int

    gemini_key_source: Literal["database", "env", "none"]
    gemini_has_active_key: bool
    gemini_validation_model: str
    quota_alert_threshold_ratio: float


class GeminiKeyStatusOut(BaseModel):
    provider: str
    has_active_key: bool
    source: Literal["database", "env", "none"]
    fingerprint: str | None = None
    key_version: int | None = None
    rotated_at: datetime | None = None
    updated_at: datetime | None = None


class GeminiKeyRotateIn(BaseModel):
    api_key: str = Field(min_length=20, max_length=512)
    reason: str | None = Field(default=None, max_length=255)
    dry_run: bool = False
    validate_with_provider: bool = False
    test_model: str | None = Field(default=None, max_length=120)


class GeminiKeyRotateOut(BaseModel):
    status: Literal["ok", "dry-run"]
    provider: str
    fingerprint: str
    key_version: int | None = None
    rotated_at: datetime | None = None
    dry_run_validated: bool = False
    message: str
