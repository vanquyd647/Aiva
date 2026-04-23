"""File upload schema models."""

from pydantic import BaseModel, Field


class FileUploadOut(BaseModel):
    file_id: str = Field(min_length=1)
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(ge=0)
    preview_text: str | None = None
