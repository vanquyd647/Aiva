"""Schema models for admin governance and usage dashboards."""

from datetime import datetime
from typing import Any

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
