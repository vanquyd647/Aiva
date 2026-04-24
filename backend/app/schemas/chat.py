"""Chat streaming schema models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ChatAttachmentIn(BaseModel):
    file_name: str = Field(default="image", min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=255)
    data_base64: str | None = Field(default=None, min_length=1)
    uri: str | None = Field(default=None, min_length=1, max_length=2048)

    @model_validator(mode="after")
    def validate_attachment_source(self) -> "ChatAttachmentIn":
        if not self.data_base64 and not self.uri:
            raise ValueError("Attachment requires data_base64 or uri")
        return self


class ChatMessageIn(BaseModel):
    role: str = Field(pattern="^(system|user|assistant)$")
    text: str = Field(default="", max_length=12000)
    attachments: list[ChatAttachmentIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_message_content(self) -> "ChatMessageIn":
        if not self.text.strip() and not self.attachments:
            raise ValueError("Message must include text or attachments")
        return self


class ChatToolFunctionIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1024)
    parameters_json_schema: dict[str, Any] | None = None
    response_json_schema: dict[str, Any] | None = None


class ChatSafetySettingIn(BaseModel):
    category: str = Field(min_length=1, max_length=128)
    threshold: str = Field(min_length=1, max_length=128)
    method: str | None = Field(default=None, min_length=1, max_length=128)


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
    stop_sequences: list[str] = Field(default_factory=list, max_length=8)
    candidate_count: int = Field(default=1, ge=1, le=8)
    seed: int | None = Field(default=None, ge=0)
    presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    system_prompt: str = Field(default="", max_length=12000)

    enable_thinking: bool = False
    include_thoughts: bool = False
    thinking_budget_tokens: int | None = Field(default=None, ge=0, le=32768)
    thinking_level: Literal["minimal", "low", "medium", "high"] | None = None

    response_mime_type: str | None = Field(default=None, min_length=1, max_length=128)
    response_schema: dict[str, Any] | None = None
    response_json_schema: dict[str, Any] | None = None

    tools: list[ChatToolFunctionIn] = Field(default_factory=list)
    function_calling_mode: Literal["auto", "any", "none", "validated"] | None = None
    allowed_function_names: list[str] = Field(default_factory=list, max_length=64)
    stream_function_call_arguments: bool = False
    include_server_side_tool_invocations: bool = False

    media_resolution: Literal["low", "medium", "high"] | None = None
    safety_settings: list[ChatSafetySettingIn] = Field(default_factory=list)
