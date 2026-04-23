"""Message schema models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    conversation_id: int
    role: str = Field(pattern="^(system|user|assistant)$")
    content: str = Field(min_length=1)
    status: str = Field(default="final", min_length=1, max_length=32)


class MessageUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    status: str | None = Field(default=None, min_length=1, max_length=32)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    status: str
    created_at: datetime
    updated_at: datetime | None = None


class MessageListOut(BaseModel):
    items: list[MessageOut]
    total: int
    page: int
    page_size: int
