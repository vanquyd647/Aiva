"""Health check endpoints for orchestration and monitoring."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.cache import cache

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def ready(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    await cache.set_json("health:last-ready", {"status": "ok"}, ttl_seconds=20)
    return {
        "status": "ok",
        "db": "ready",
        "cache_mode": cache.mode,
    }
