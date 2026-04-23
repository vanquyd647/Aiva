"""Usage routes for per-user quota and metering insights."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.governance import UserUsageSummaryOut
from app.services.governance import user_usage_summary

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/me", response_model=UserUsageSummaryOut)
def my_usage(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    payload = user_usage_summary(db, user_id=current_user.id, role=current_user.role)
    return UserUsageSummaryOut(**payload)
