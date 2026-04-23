"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from app.api.routes import auth, health, users
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import User  # noqa: F401 - ensure model import for metadata
from app.models.user import User
from app.services.cache import cache


def _seed_admin_if_missing() -> None:
    db = SessionLocal()
    try:
        admin_email = settings.INITIAL_ADMIN_EMAIL.strip().lower()
        existing = db.query(User).filter(User.email == admin_email).first()
        if existing:
            return

        admin = User(
            email=admin_email,
            full_name=settings.INITIAL_ADMIN_NAME,
            hashed_password=get_password_hash(settings.INITIAL_ADMIN_PASSWORD),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
    except OperationalError as exc:
        raise RuntimeError(
            "Database schema is not ready. Run migrations: "
            "python -m alembic -c backend/alembic.ini upgrade head"
        ) from exc
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_runtime()
    if settings.AUTO_CREATE_DB_SCHEMA:
        Base.metadata.create_all(bind=engine)
    _seed_admin_if_missing()
    await cache.startup()
    yield
    await cache.shutdown()


_DOCS_URL = None if settings.is_production else "/docs"
_REDOC_URL = None if settings.is_production else "/redoc"
_OPENAPI_URL = None if settings.is_production else f"{settings.API_V1_PREFIX}/openapi.json"

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    docs_url=_DOCS_URL,
    redoc_url=_REDOC_URL,
    openapi_url=_OPENAPI_URL,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers_middleware(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def root() -> dict:
    return {
        "name": settings.APP_NAME,
        "env": settings.ENV,
        "version": "1.0.0",
        "docs": _DOCS_URL,
    }


app.include_router(health.router, prefix=settings.API_V1_PREFIX)
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)
