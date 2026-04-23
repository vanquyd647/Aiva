"""Chat streaming schema models."""

from pydantic import BaseModel, Field


class ChatAttachmentIn(BaseModel):
    file_name: str = Field(default="image", min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=255)
    data_base64: str = Field(min_length=1)


class ChatMessageIn(BaseModel):
    role: str = Field(pattern="^(system|user|assistant)$")
    text: str = Field(min_length=1)
    attachments: list[ChatAttachmentIn] = Field(default_factory=list)


class ChatStreamRequest(BaseModel):
    messages: list[ChatMessageIn] = Field(min_length=1)
    conversation_id: int | None = None
    conversation_title: str | None = Field(default=None, min_length=1, max_length=255)
    enable_web_search: bool = False
    web_search_max_results: int = Field(default=3, ge=1, le=10)
    model: str = Field(default="gemma-4-31b-it", min_length=1, max_length=128)
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    top_p: float = Field(default=0.95, gt=0.0, le=1.0)
    top_k: int = Field(default=64, ge=1, le=512)
    max_output_tokens: int = Field(default=8192, ge=1, le=32768)
    system_prompt: str = Field(default="", max_length=12000)
