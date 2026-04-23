"""File upload routes for authenticated users."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.file import FileUploadOut
from app.services.governance import record_usage_event

router = APIRouter(prefix="/files", tags=["files"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PREVIEW_CHARS = 3000
ALLOWED_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".xml",
    ".yml",
    ".yaml",
    ".log",
    ".py",
    ".js",
    ".ts",
    ".html",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".pdf",
}

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".xml",
    ".yml",
    ".yaml",
    ".log",
    ".py",
    ".js",
    ".ts",
    ".html",
    ".css",
}

BACKEND_ROOT = Path(__file__).resolve().parents[3]
UPLOAD_ROOT = BACKEND_ROOT / "storage" / "uploads"


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._")
    return cleaned[:180] or "upload.bin"


def _extract_preview(content: bytes) -> str | None:
    text = content.decode("utf-8", errors="replace").strip()
    if not text:
        return None
    if len(text) > MAX_PREVIEW_CHARS:
        return text[:MAX_PREVIEW_CHARS] + "\n...[truncated]"
    return text


@router.post("/upload", response_model=FileUploadOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    raw_name = (file.filename or "upload.bin").strip()
    suffix = Path(raw_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension: {suffix or '(none)'}",
        )

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 10MB limit",
        )

    safe_name = _sanitize_filename(Path(raw_name).name)
    file_id = uuid.uuid4().hex
    stored_name = f"{file_id}_{safe_name}"

    user_dir = UPLOAD_ROOT / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / stored_name).write_bytes(content)

    record_usage_event(
        db=db,
        user_id=current_user.id,
        metric="uploaded_bytes",
        quantity=len(content),
        source="files",
        metadata={"file_name": safe_name, "content_type": file.content_type or ""},
    )

    content_type = (file.content_type or "application/octet-stream").strip()
    preview_text = _extract_preview(content) if suffix in TEXT_EXTENSIONS else None

    return FileUploadOut(
        file_id=file_id,
        file_name=safe_name,
        content_type=content_type,
        size_bytes=len(content),
        preview_text=preview_text,
    )
