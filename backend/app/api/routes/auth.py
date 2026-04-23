"""Authentication routes."""

from datetime import timedelta
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, oauth2_scheme
from app.core.config import settings
from app.core.security import (
    TokenDecodeError,
    create_access_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import TokenOut
from app.schemas.user import UserCreate, UserOut
from app.services.cache import cache
from app.services.governance import create_user_session, revoke_session_by_sid, write_audit_log

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"auth:login:{client_ip}"
    attempts = await cache.increment(rate_key, ttl_seconds=60)
    if attempts > settings.RATE_LIMIT_LOGIN_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts, retry in 60 seconds",
        )

    email = form_data.username.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        write_audit_log(
            db,
            actor_user_id=user.id if user else None,
            action="auth.login",
            target_type="user",
            target_id=str(user.id) if user else None,
            status="failed",
            severity="warning",
            details={"email": email, "ip_address": client_ip, "reason": "invalid_credentials"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        write_audit_log(
            db,
            actor_user_id=user.id,
            action="auth.login",
            target_type="user",
            target_id=str(user.id),
            status="failed",
            severity="warning",
            details={"email": email, "ip_address": client_ip, "reason": "inactive_user"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    session_id = uuid.uuid4().hex
    expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(
        subject=str(user.id),
        role=user.role,
        expires_delta=expires,
        session_id=session_id,
    )

    create_user_session(
        db,
        user_id=user.id,
        session_id=session_id,
        token=token,
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent"),
    )

    write_audit_log(
        db,
        actor_user_id=user.id,
        action="auth.login",
        target_type="user",
        target_id=str(user.id),
        status="success",
        severity="info",
        details={"email": email, "ip_address": client_ip, "session_id": session_id},
    )

    return TokenOut(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
        session_id=session_id,
    )


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.post("/logout")
def logout(
    request: Request,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    session_id = ""
    try:
        payload = decode_token(token)
        session_id = str(payload.get("sid") or "").strip()
    except TokenDecodeError:
        session_id = ""

    revoked = False
    if session_id:
        revoked = revoke_session_by_sid(db, session_id)

    write_audit_log(
        db,
        actor_user_id=current_user.id,
        action="auth.logout",
        target_type="user",
        target_id=str(current_user.id),
        status="success",
        severity="info",
        details={
            "session_id": session_id or None,
            "revoked": revoked,
            "ip_address": request.client.host if request.client else "unknown",
        },
    )
    return {"status": "ok", "revoked": revoked, "session_id": session_id or None}


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    if not settings.ALLOW_PUBLIC_REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled",
        )

    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role="user",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
