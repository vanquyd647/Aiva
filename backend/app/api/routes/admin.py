"""Admin governance routes for audit, sessions, and usage overview."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.user_session import UserSession
from app.schemas.governance import (
    AuditLogListOut,
    AuditLogOut,
    UsageOverviewOut,
    UserSessionListOut,
    UserSessionOut,
)
from app.services.governance import (
    parse_details,
    revoke_session_by_sid,
    revoke_user_sessions,
    usage_overview,
    write_audit_log,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit", response_model=AuditLogListOut)
def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    target_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
):
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action.strip())
    if status_filter:
        query = query.filter(AuditLog.status == status_filter.strip())
    if target_type:
        query = query.filter(AuditLog.target_type == target_type.strip())

    total = query.count()
    rows = (
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    actor_ids = {row.actor_user_id for row in rows if row.actor_user_id is not None}
    actor_map: dict[int, str] = {}
    if actor_ids:
        users = db.query(User).filter(User.id.in_(actor_ids)).all()
        actor_map = {item.id: item.email for item in users}

    items = [
        AuditLogOut(
            id=row.id,
            actor_user_id=row.actor_user_id,
            actor_email=actor_map.get(row.actor_user_id) if row.actor_user_id else None,
            action=row.action,
            target_type=row.target_type,
            target_id=row.target_id,
            status=row.status,
            severity=row.severity,
            details=parse_details(row.details_json),
            created_at=row.created_at,
        )
        for row in rows
    ]

    write_audit_log(
        db,
        actor_user_id=current_admin.id,
        action="admin.audit.view",
        target_type="audit_logs",
        status="success",
        severity="info",
        details={"page": page, "page_size": page_size, "total": total},
    )

    return AuditLogListOut(items=items, total=total, page=page, page_size=page_size)


@router.get("/sessions", response_model=UserSessionListOut)
def list_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    include_revoked: bool = Query(default=False),
    user_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
):
    query = db.query(UserSession).join(User, User.id == UserSession.user_id)
    if not include_revoked:
        query = query.filter(UserSession.revoked_at.is_(None))
    if user_id is not None:
        query = query.filter(UserSession.user_id == user_id)

    total = query.count()
    rows = (
        query.order_by(UserSession.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    user_ids = {row.user_id for row in rows}
    email_map: dict[int, str] = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        email_map = {item.id: item.email for item in users}

    items = [
        UserSessionOut(
            session_id=row.session_id,
            user_id=row.user_id,
            user_email=email_map.get(row.user_id, "unknown"),
            ip_address=row.ip_address,
            user_agent=row.user_agent,
            created_at=row.created_at,
            last_seen_at=row.last_seen_at,
            revoked_at=row.revoked_at,
        )
        for row in rows
    ]

    write_audit_log(
        db,
        actor_user_id=current_admin.id,
        action="admin.sessions.view",
        target_type="user_sessions",
        status="success",
        severity="info",
        details={
            "page": page,
            "page_size": page_size,
            "include_revoked": include_revoked,
            "user_id": user_id,
            "total": total,
        },
    )

    return UserSessionListOut(items=items, total=total, page=page, page_size=page_size)


@router.post("/sessions/{session_id}/revoke")
def revoke_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
):
    ok = revoke_session_by_sid(db, session_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    write_audit_log(
        db,
        actor_user_id=current_admin.id,
        action="admin.sessions.revoke",
        target_type="user_session",
        target_id=session_id,
        status="success",
        severity="warning",
    )
    return {"status": "ok", "session_id": session_id}


@router.post("/sessions/revoke-user/{user_id}")
def revoke_all_sessions_for_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
):
    revoked = revoke_user_sessions(db, user_id)
    write_audit_log(
        db,
        actor_user_id=current_admin.id,
        action="admin.sessions.revoke_user",
        target_type="user",
        target_id=str(user_id),
        status="success",
        severity="warning",
        details={"revoked_sessions": revoked},
    )
    return {"status": "ok", "revoked_sessions": revoked, "user_id": user_id}


@router.get("/usage", response_model=UsageOverviewOut)
def admin_usage_overview(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
):
    payload = usage_overview(db, page=page, page_size=page_size)

    write_audit_log(
        db,
        actor_user_id=current_admin.id,
        action="admin.usage.view",
        target_type="usage",
        status="success",
        severity="info",
        details={"page": page, "page_size": page_size},
    )

    return UsageOverviewOut(**payload)
