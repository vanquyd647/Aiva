"""Admin routes for user management."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserListOut,
    UserOut,
    UserPasswordReset,
    UserStatsOut,
    UserStatusUpdate,
    UserUpdate,
)
from app.services.cache import cache

router = APIRouter(prefix="/users", tags=["users"])


async def _invalidate_users_cache() -> None:
    await cache.delete_prefix("users:list:")
    await cache.delete_prefix("users:stats")


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/stats", response_model=UserStatsOut)
async def users_stats(
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    cache_key = "users:stats"
    cached = await cache.get_json(cache_key)
    if cached is not None:
        return UserStatsOut(**cached)

    total = db.query(User).count()
    active = db.query(User).filter(User.is_active.is_(True)).count()
    admins = db.query(User).filter(User.role == "admin").count()
    payload = {
        "total": total,
        "active": active,
        "inactive": max(0, total - active),
        "admins": admins,
    }
    await cache.set_json(cache_key, payload, 30)
    return UserStatsOut(**payload)


@router.get("", response_model=UserListOut)
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    normalized_search = (search or "").strip().lower()
    cache_key = f"users:list:{page}:{page_size}:{normalized_search}"
    cached = await cache.get_json(cache_key)
    if cached is not None:
        return UserListOut(**cached)

    query = db.query(User)
    if normalized_search:
        query = query.filter(
            or_(
                User.email.ilike(f"%{normalized_search}%"),
                User.full_name.ilike(f"%{normalized_search}%"),
            )
        )

    total = query.count()
    items = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    payload = {
        "items": [UserOut.model_validate(item).model_dump(mode="json") for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
    await cache.set_json(cache_key, payload, settings.USER_LIST_CACHE_TTL_SECONDS)
    return UserListOut(**payload)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
        is_active=payload.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    await _invalidate_users_cache()
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)
    update_data = payload.model_dump(exclude_unset=True, exclude_none=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field is required",
        )

    normalized_email = None
    if "email" in update_data:
        normalized_email = update_data["email"].strip().lower()
        existing = (
            db.query(User)
            .filter(User.email == normalized_email, User.id != user_id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    new_role = update_data.get("role")
    if user.id == current_admin.id and new_role == "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin cannot downgrade itself",
        )

    if user.id == current_admin.id and update_data.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin cannot deactivate itself",
        )

    if normalized_email is not None:
        user.email = normalized_email
    if "full_name" in update_data:
        user.full_name = update_data["full_name"]
    if "role" in update_data:
        user.role = update_data["role"]
    if "is_active" in update_data:
        user.is_active = update_data["is_active"]

    db.commit()
    db.refresh(user)
    await _invalidate_users_cache()
    return user


@router.patch("/{user_id}/password", response_model=UserOut)
async def reset_user_password(
    user_id: int,
    payload: UserPasswordReset,
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)
    user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    db.refresh(user)
    await _invalidate_users_cache()
    return user


@router.patch("/{user_id}/status", response_model=UserOut)
async def update_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)

    if user.id == current_admin.id and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin cannot deactivate itself",
        )

    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    await _invalidate_users_cache()
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)

    if user.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin cannot delete itself",
        )

    db.delete(user)
    db.commit()
    await _invalidate_users_cache()
    return None
