"""Gemini streaming service helpers for backend chat routes."""

from __future__ import annotations

import base64
import os
from typing import Iterable

from google import genai
from google.genai import types

_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Build a singleton Gemini client from environment variables."""
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("GEMINI_API_KEY is missing")
        _client = genai.Client(api_key=api_key)
    return _client


def _to_sdk_contents(messages: list[dict]) -> list[types.Content]:
    contents: list[types.Content] = []
    for msg in messages:
        role = msg.get("role", "user")
        sdk_role = "user" if role in {"user", "system"} else "model"

        parts: list[types.Part] = [types.Part(text=msg.get("text", ""))]
        for attachment in msg.get("attachments") or []:
            content_type = str(attachment.get("content_type", "")).strip().lower()
            if not content_type.startswith("image/"):
                continue

            data_base64 = str(attachment.get("data_base64", "")).strip()
            if not data_base64:
                continue

            try:
                raw = base64.b64decode(data_base64, validate=True)
            except Exception:
                continue

            if raw:
                parts.append(types.Part.from_bytes(data=raw, mime_type=content_type))

        contents.append(types.Content(role=sdk_role, parts=parts))
    return contents


def stream_chat_text(messages: list[dict], cfg: dict) -> Iterable[str]:
    """Yield text chunks from Gemini streaming API."""
    gen_config = types.GenerateContentConfig(
        system_instruction=cfg.get("system_prompt", ""),
        temperature=cfg.get("temperature", 1.0),
        top_p=cfg.get("top_p", 0.95),
        top_k=cfg.get("top_k", 64),
        max_output_tokens=cfg.get("max_output_tokens", 8192),
    )

    client = get_client()
    contents = _to_sdk_contents(messages)
    for chunk in client.models.generate_content_stream(
        model=cfg.get("model", "gemma-4-31b-it"),
        contents=contents,
        config=gen_config,
    ):
        if chunk.text:
            yield chunk.text
