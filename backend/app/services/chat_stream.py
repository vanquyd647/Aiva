"""Gemini streaming service helpers for backend chat routes."""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Iterable

from google import genai
from google.genai import types

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.provider_secrets import (
    GEMINI_PROVIDER,
    compute_secret_fingerprint,
    get_active_provider_secret_value,
)

_client: genai.Client | None = None
_client_source: str | None = None
_client_fingerprint: str | None = None

_SUPPORTED_ATTACHMENT_PREFIXES = ("image/", "audio/", "video/")
_SUPPORTED_ATTACHMENT_TYPES = {"application/pdf"}

_MEDIA_RESOLUTION_MAP = {
    "MEDIA_RESOLUTION_LOW": types.MediaResolution.MEDIA_RESOLUTION_LOW,
    "MEDIA_RESOLUTION_MEDIUM": types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
    "MEDIA_RESOLUTION_HIGH": types.MediaResolution.MEDIA_RESOLUTION_HIGH,
}

_THINKING_LEVEL_MAP = {
    "MINIMAL": types.ThinkingLevel.MINIMAL,
    "LOW": types.ThinkingLevel.LOW,
    "MEDIUM": types.ThinkingLevel.MEDIUM,
    "HIGH": types.ThinkingLevel.HIGH,
}

_FUNCTION_MODE_MAP = {
    "AUTO": types.FunctionCallingConfigMode.AUTO,
    "ANY": types.FunctionCallingConfigMode.ANY,
    "NONE": types.FunctionCallingConfigMode.NONE,
    "VALIDATED": types.FunctionCallingConfigMode.VALIDATED,
}

_HARM_CATEGORY_MAP = {
    "HARM_CATEGORY_HARASSMENT": types.HarmCategory.HARM_CATEGORY_HARASSMENT,
    "HARM_CATEGORY_HATE_SPEECH": types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
    "HARM_CATEGORY_SEXUALLY_EXPLICIT": types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
    "HARM_CATEGORY_DANGEROUS_CONTENT": types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
    "HARM_CATEGORY_CIVIC_INTEGRITY": types.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY,
    "HARM_CATEGORY_IMAGE_HATE": types.HarmCategory.HARM_CATEGORY_IMAGE_HATE,
    "HARM_CATEGORY_IMAGE_DANGEROUS_CONTENT": types.HarmCategory.HARM_CATEGORY_IMAGE_DANGEROUS_CONTENT,
    "HARM_CATEGORY_IMAGE_HARASSMENT": types.HarmCategory.HARM_CATEGORY_IMAGE_HARASSMENT,
    "HARM_CATEGORY_IMAGE_SEXUALLY_EXPLICIT": types.HarmCategory.HARM_CATEGORY_IMAGE_SEXUALLY_EXPLICIT,
    "HARM_CATEGORY_JAILBREAK": types.HarmCategory.HARM_CATEGORY_JAILBREAK,
}

_HARM_THRESHOLD_MAP = {
    "BLOCK_LOW_AND_ABOVE": types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    "BLOCK_MEDIUM_AND_ABOVE": types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    "BLOCK_ONLY_HIGH": types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
    "BLOCK_NONE": types.HarmBlockThreshold.BLOCK_NONE,
    "OFF": types.HarmBlockThreshold.OFF,
}

_HARM_METHOD_MAP = {
    "SEVERITY": types.HarmBlockMethod.SEVERITY,
    "PROBABILITY": types.HarmBlockMethod.PROBABILITY,
}


def _resolve_api_key_from_sources() -> tuple[str, str, str]:
    db = SessionLocal()
    try:
        resolved = get_active_provider_secret_value(db, provider=GEMINI_PROVIDER)
    except Exception:
        resolved = None
    finally:
        db.close()

    if resolved is not None:
        api_key, fingerprint = resolved
        return api_key, fingerprint, "database"

    if settings.GEMINI_FALLBACK_ENV_API_KEY_ENABLED:
        env_key = os.getenv("GEMINI_API_KEY", "").strip()
        if env_key:
            return env_key, compute_secret_fingerprint(env_key), "env"

    raise ValueError("No active Gemini API key (database and env fallback are empty)")


def reset_client() -> None:
    """Drop cached Gemini client so the next call reloads fresh credentials."""
    global _client, _client_source, _client_fingerprint
    _client = None
    _client_source = None
    _client_fingerprint = None


def get_client() -> genai.Client:
    """Build a singleton Gemini client from secure key sources."""
    global _client, _client_source, _client_fingerprint
    api_key, fingerprint, source = _resolve_api_key_from_sources()
    if _client is None or fingerprint != _client_fingerprint or source != _client_source:
        _client = genai.Client(api_key=api_key)
        _client_source = source
        _client_fingerprint = fingerprint
    return _client


def _normalize_enum_token(value: Any) -> str:
    return str(value or "").strip().upper().replace("-", "_")


def _map_media_resolution(value: Any) -> types.MediaResolution | None:
    normalized = _normalize_enum_token(value)
    if not normalized:
        return None
    if not normalized.startswith("MEDIA_RESOLUTION_"):
        normalized = f"MEDIA_RESOLUTION_{normalized}"
    return _MEDIA_RESOLUTION_MAP.get(normalized)


def _map_thinking_level(value: Any) -> types.ThinkingLevel | None:
    normalized = _normalize_enum_token(value)
    if not normalized:
        return None
    if normalized.startswith("THINKING_LEVEL_"):
        normalized = normalized.replace("THINKING_LEVEL_", "", 1)
    return _THINKING_LEVEL_MAP.get(normalized)


def _is_supported_attachment(content_type: str) -> bool:
    return content_type.startswith(_SUPPORTED_ATTACHMENT_PREFIXES) or (
        content_type in _SUPPORTED_ATTACHMENT_TYPES
    )


def _attachment_media_resolution(
    content_type: str,
    media_resolution: types.MediaResolution | None,
) -> types.MediaResolution | None:
    if media_resolution is None:
        return None
    if content_type.startswith(("image/", "video/")):
        return media_resolution
    return None


def _attachment_to_part(
    attachment: dict,
    media_resolution: types.MediaResolution | None,
) -> types.Part | None:
    content_type = str(attachment.get("content_type", "")).strip().lower()
    if not content_type or not _is_supported_attachment(content_type):
        return None

    attachment_resolution = _attachment_media_resolution(content_type, media_resolution)
    data_base64 = str(attachment.get("data_base64") or "").strip()
    if data_base64:
        try:
            raw = base64.b64decode(data_base64, validate=True)
        except Exception:
            return None
        if not raw:
            return None
        return types.Part.from_bytes(
            data=raw,
            mime_type=content_type,
            media_resolution=attachment_resolution,
        )

    file_uri = str(attachment.get("uri") or "").strip()
    if file_uri:
        return types.Part.from_uri(
            file_uri=file_uri,
            mime_type=content_type,
            media_resolution=attachment_resolution,
        )
    return None


def _to_sdk_contents(
    messages: list[dict],
    media_resolution: types.MediaResolution | None = None,
) -> list[types.Content]:
    contents: list[types.Content] = []
    for msg in messages:
        role = msg.get("role", "user")
        sdk_role = "user" if role in {"user", "system"} else "model"

        text = str(msg.get("text", ""))
        parts: list[types.Part] = [types.Part(text=text)] if text else []
        for attachment in msg.get("attachments") or []:
            part = _attachment_to_part(attachment, media_resolution=media_resolution)
            if part is not None:
                parts.append(part)

        if not parts:
            parts.append(types.Part(text=" "))

        contents.append(types.Content(role=sdk_role, parts=parts))
    return contents


def _build_tools(cfg: dict) -> list[types.Tool] | None:
    functions: list[types.FunctionDeclaration] = []
    for item in cfg.get("tools") or []:
        name = str(item.get("name", "")).strip()
        if not name:
            continue

        declaration_kwargs: dict[str, Any] = {"name": name}
        description = str(item.get("description") or "").strip()
        if description:
            declaration_kwargs["description"] = description

        parameters_json_schema = item.get("parameters_json_schema")
        if isinstance(parameters_json_schema, dict) and parameters_json_schema:
            declaration_kwargs["parameters_json_schema"] = parameters_json_schema

        response_json_schema = item.get("response_json_schema")
        if isinstance(response_json_schema, dict) and response_json_schema:
            declaration_kwargs["response_json_schema"] = response_json_schema

        functions.append(types.FunctionDeclaration(**declaration_kwargs))

    if not functions:
        return None
    return [types.Tool(function_declarations=functions)]


def _supports_stream_function_call_arguments() -> bool:
    model_fields = getattr(types.FunctionCallingConfig, "model_fields", None)
    if isinstance(model_fields, dict):
        return "stream_function_call_arguments" in model_fields

    legacy_fields = getattr(types.FunctionCallingConfig, "__fields__", None)
    if isinstance(legacy_fields, dict):
        return "stream_function_call_arguments" in legacy_fields

    return False


def _build_tool_config(cfg: dict) -> types.ToolConfig | None:
    mode_token = _normalize_enum_token(cfg.get("function_calling_mode"))
    function_calling_mode = _FUNCTION_MODE_MAP.get(mode_token)

    allowed_function_names = [
        str(item).strip() for item in (cfg.get("allowed_function_names") or []) if str(item).strip()
    ]

    stream_args_enabled = bool(cfg.get("stream_function_call_arguments", False))

    function_cfg_kwargs: dict[str, Any] = {}
    if function_calling_mode is not None:
        function_cfg_kwargs["mode"] = function_calling_mode
    if allowed_function_names:
        function_cfg_kwargs["allowed_function_names"] = allowed_function_names
    if stream_args_enabled and _supports_stream_function_call_arguments():
        function_cfg_kwargs["stream_function_call_arguments"] = True

    include_server_calls = cfg.get("include_server_side_tool_invocations")
    has_include_server_calls = include_server_calls is not None

    if not function_cfg_kwargs and not has_include_server_calls:
        return None

    tool_config_kwargs: dict[str, Any] = {}
    if function_cfg_kwargs:
        tool_config_kwargs["function_calling_config"] = types.FunctionCallingConfig(
            **function_cfg_kwargs
        )
    if has_include_server_calls:
        tool_config_kwargs["include_server_side_tool_invocations"] = bool(include_server_calls)
    return types.ToolConfig(**tool_config_kwargs)


def _build_safety_settings(cfg: dict) -> list[types.SafetySetting] | None:
    settings_payload: list[types.SafetySetting] = []
    for item in cfg.get("safety_settings") or []:
        raw_category = _normalize_enum_token(item.get("category"))
        if raw_category and not raw_category.startswith("HARM_CATEGORY_"):
            raw_category = f"HARM_CATEGORY_{raw_category}"
        category = _HARM_CATEGORY_MAP.get(raw_category)
        if category is None:
            continue

        raw_threshold = _normalize_enum_token(item.get("threshold"))
        threshold = _HARM_THRESHOLD_MAP.get(raw_threshold)
        if threshold is None:
            continue

        raw_method = _normalize_enum_token(item.get("method"))
        method = _HARM_METHOD_MAP.get(raw_method) if raw_method else None

        safety_kwargs: dict[str, Any] = {"category": category, "threshold": threshold}
        if method is not None:
            safety_kwargs["method"] = method
        settings_payload.append(types.SafetySetting(**safety_kwargs))

    if not settings_payload:
        return None
    return settings_payload


def _build_thinking_config(cfg: dict) -> types.ThinkingConfig | None:
    include_thoughts = bool(cfg.get("include_thoughts", False))
    thinking_budget = cfg.get("thinking_budget_tokens")
    thinking_level = _map_thinking_level(cfg.get("thinking_level"))

    thinking_kwargs: dict[str, Any] = {}
    if include_thoughts:
        thinking_kwargs["include_thoughts"] = True
    if thinking_budget is not None:
        thinking_kwargs["thinking_budget"] = int(thinking_budget)
    if thinking_level is not None:
        thinking_kwargs["thinking_level"] = thinking_level

    if not thinking_kwargs:
        return None
    return types.ThinkingConfig(**thinking_kwargs)


def _build_generate_config(cfg: dict) -> types.GenerateContentConfig:
    config_kwargs: dict[str, Any] = {
        "system_instruction": cfg.get("system_prompt", ""),
        "temperature": cfg.get("temperature", 1.0),
        "top_p": cfg.get("top_p", 0.95),
        "top_k": cfg.get("top_k", 64),
        "max_output_tokens": cfg.get("max_output_tokens", 8192),
        "candidate_count": cfg.get("candidate_count", 1),
    }

    stop_sequences = [
        str(item).strip() for item in (cfg.get("stop_sequences") or []) if str(item).strip()
    ]
    if stop_sequences:
        config_kwargs["stop_sequences"] = stop_sequences

    for field in ("seed", "presence_penalty", "frequency_penalty", "response_mime_type"):
        value = cfg.get(field)
        if value is not None:
            config_kwargs[field] = value

    response_json_schema = cfg.get("response_json_schema")
    if isinstance(response_json_schema, dict) and response_json_schema:
        config_kwargs["response_json_schema"] = response_json_schema
    else:
        response_schema = cfg.get("response_schema")
        if isinstance(response_schema, dict) and response_schema:
            config_kwargs["response_schema"] = response_schema

    media_resolution = _map_media_resolution(cfg.get("media_resolution"))
    if media_resolution is not None:
        config_kwargs["media_resolution"] = media_resolution

    tools = _build_tools(cfg)
    if tools is not None:
        config_kwargs["tools"] = tools

    tool_config = _build_tool_config(cfg)
    if tool_config is not None:
        config_kwargs["tool_config"] = tool_config

    safety_settings = _build_safety_settings(cfg)
    if safety_settings is not None:
        config_kwargs["safety_settings"] = safety_settings

    thinking_config = _build_thinking_config(cfg)
    if thinking_config is not None:
        config_kwargs["thinking_config"] = thinking_config

    return types.GenerateContentConfig(**config_kwargs)


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if hasattr(value, "model_dump"):
        return _to_jsonable(value.model_dump())
    return str(value)


def _extract_tool_calls(chunk: Any) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for candidate in getattr(chunk, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            function_call = getattr(part, "function_call", None)
            if function_call is not None:
                events.append(
                    {
                        "type": "tool_call",
                        "kind": "function",
                        "id": getattr(function_call, "id", None),
                        "name": getattr(function_call, "name", None),
                        "args": _to_jsonable(getattr(function_call, "args", None) or {}),
                        "partial_args": _to_jsonable(getattr(function_call, "partial_args", None)),
                        "will_continue": bool(getattr(function_call, "will_continue", False)),
                    }
                )

            tool_call = getattr(part, "tool_call", None)
            if tool_call is not None:
                events.append(
                    {
                        "type": "tool_call",
                        "kind": "tool",
                        "id": getattr(tool_call, "id", None),
                        "tool_type": getattr(tool_call, "tool_type", None),
                        "args": _to_jsonable(getattr(tool_call, "args", None) or {}),
                    }
                )
    return events


def stream_chat_text(messages: list[dict], cfg: dict) -> Iterable[str | dict[str, Any]]:
    """Yield text and tool-call events from Gemini streaming API."""
    media_resolution = _map_media_resolution(cfg.get("media_resolution"))
    gen_config = _build_generate_config(cfg)

    client = get_client()
    contents = _to_sdk_contents(messages, media_resolution=media_resolution)
    seen_tool_call_events: set[str] = set()
    for chunk in client.models.generate_content_stream(
        model=cfg.get("model", "gemma-4-31b-it"),
        contents=contents,
        config=gen_config,
    ):
        for tool_call in _extract_tool_calls(chunk):
            dedupe_key = json.dumps(tool_call, ensure_ascii=False, sort_keys=True)
            if dedupe_key in seen_tool_call_events:
                continue
            seen_tool_call_events.add(dedupe_key)
            yield tool_call

        if chunk.text:
            yield chunk.text
