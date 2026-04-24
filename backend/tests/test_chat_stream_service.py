"""Unit tests for Gemini chat streaming service helpers."""

from google.genai import types

from app.services import chat_stream


def test_to_sdk_contents_supports_multimodal_attachments() -> None:
    contents = chat_stream._to_sdk_contents(
        [
            {
                "role": "user",
                "text": "Analyze these inputs",
                "attachments": [
                    {
                        "file_name": "sample.png",
                        "content_type": "image/png",
                        "data_base64": "aGVsbG8=",
                    },
                    {
                        "file_name": "sample.wav",
                        "content_type": "audio/wav",
                        "data_base64": "aGVsbG8=",
                    },
                    {
                        "file_name": "sample.pdf",
                        "content_type": "application/pdf",
                        "data_base64": "aGVsbG8=",
                    },
                    {
                        "file_name": "sample.mp4",
                        "content_type": "video/mp4",
                        "uri": "gs://example-bucket/sample.mp4",
                    },
                ],
            }
        ],
        media_resolution=chat_stream._map_media_resolution("high"),
    )

    assert len(contents) == 1
    parts = contents[0].parts
    assert parts is not None

    inline_mime_types = {
        part.inline_data.mime_type
        for part in parts
        if part.inline_data is not None and part.inline_data.mime_type is not None
    }
    file_mime_types = {
        part.file_data.mime_type
        for part in parts
        if part.file_data is not None and part.file_data.mime_type is not None
    }

    assert "image/png" in inline_mime_types
    assert "audio/wav" in inline_mime_types
    assert "application/pdf" in inline_mime_types
    assert "video/mp4" in file_mime_types


def test_stream_chat_text_emits_tool_calls_and_maps_advanced_config(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeModels:
        def generate_content_stream(self, *, model, contents, config):
            captured["model"] = model
            captured["contents"] = contents
            captured["config"] = config

            yield types.GenerateContentResponse(
                candidates=[
                    types.Candidate(
                        content=types.Content(
                            role="model",
                            parts=[
                                types.Part.from_function_call(
                                    name="lookup_weather",
                                    args={"city": "Ha Noi"},
                                )
                            ],
                        )
                    )
                ]
            )
            yield types.GenerateContentResponse(
                candidates=[
                    types.Candidate(
                        content=types.Content(role="model", parts=[types.Part(text="sunny")])
                    )
                ]
            )

    class _FakeClient:
        def __init__(self):
            self.models = _FakeModels()

    monkeypatch.setattr(chat_stream, "get_client", lambda: _FakeClient())

    cfg = {
        "model": "gemma-4-31b-it",
        "system_prompt": "system",
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 32,
        "max_output_tokens": 4096,
        "candidate_count": 2,
        "stop_sequences": ["<END>"],
        "seed": 123,
        "presence_penalty": 0.1,
        "frequency_penalty": 0.2,
        "response_mime_type": "application/json",
        "response_json_schema": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
        },
        "tools": [
            {
                "name": "lookup_weather",
                "description": "Get weather by city",
                "parameters_json_schema": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                },
            }
        ],
        "function_calling_mode": "any",
        "allowed_function_names": ["lookup_weather"],
        "stream_function_call_arguments": True,
        "include_server_side_tool_invocations": True,
        "include_thoughts": True,
        "thinking_budget_tokens": 1024,
        "thinking_level": "medium",
        "media_resolution": "high",
        "safety_settings": [{"category": "harassment", "threshold": "block_medium_and_above"}],
    }

    events = list(chat_stream.stream_chat_text(messages=[{"role": "user", "text": "Hi"}], cfg=cfg))

    assert len(events) == 2
    assert isinstance(events[0], dict)
    assert events[0]["type"] == "tool_call"
    assert events[0]["name"] == "lookup_weather"
    assert events[0]["args"]["city"] == "Ha Noi"
    assert events[1] == "sunny"

    assert captured["model"] == "gemma-4-31b-it"
    config = captured["config"]
    assert isinstance(config, types.GenerateContentConfig)
    assert config.candidate_count == 2
    assert config.stop_sequences == ["<END>"]
    assert config.seed == 123
    assert config.presence_penalty == 0.1
    assert config.frequency_penalty == 0.2
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema is not None
    assert config.tools is not None
    assert config.tools[0].function_declarations is not None
    assert config.tools[0].function_declarations[0].name == "lookup_weather"
    assert config.tool_config is not None
    assert config.tool_config.function_calling_config is not None
    assert config.tool_config.function_calling_config.mode == types.FunctionCallingConfigMode.ANY
    assert config.tool_config.function_calling_config.allowed_function_names == ["lookup_weather"]
    assert config.tool_config.include_server_side_tool_invocations is True
    assert config.thinking_config is not None
    assert config.thinking_config.include_thoughts is True
    assert config.thinking_config.thinking_budget == 1024
    assert config.thinking_config.thinking_level == types.ThinkingLevel.MEDIUM
    assert config.media_resolution == types.MediaResolution.MEDIA_RESOLUTION_HIGH
    assert config.safety_settings is not None
    assert config.safety_settings[0].category == types.HarmCategory.HARM_CATEGORY_HARASSMENT
    assert config.safety_settings[0].threshold == types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
