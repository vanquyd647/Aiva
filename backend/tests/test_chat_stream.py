"""Chat streaming API tests."""

import json

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User


def _admin_headers() -> dict[str, str]:
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == settings.INITIAL_ADMIN_EMAIL).first()
        assert admin is not None
        token = create_access_token(subject=str(admin.id), role=admin.role)
    finally:
        db.close()

    return {"Authorization": f"Bearer {token}"}


def _collect_events(response) -> list[tuple[str | None, dict]]:
    events: list[tuple[str | None, dict]] = []
    current_event: str | None = None
    for raw_line in response.iter_lines():
        line = raw_line.decode() if isinstance(raw_line, bytes) else raw_line
        if line is None:
            continue
        line = line.strip()
        if not line:
            continue
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
            continue
        if line.startswith("data:"):
            payload = json.loads(line.split(":", 1)[1].strip())
            events.append((current_event, payload))
    return events


def _admin_user_id() -> int:
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == settings.INITIAL_ADMIN_EMAIL).first()
        assert admin is not None
        return admin.id
    finally:
        db.close()


def test_chat_stream_success(monkeypatch) -> None:
    def fake_stream_chat_text(messages, cfg):
        assert messages[-1]["text"] == "Xin chao"
        assert cfg["model"] == "gemma-4-31b-it"
        yield "Xin "
        yield "chao"

    monkeypatch.setattr("app.api.routes.chat.stream_chat_text", fake_stream_chat_text)

    with TestClient(app) as client:
        headers = _admin_headers()
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            headers=headers,
            json={
                "messages": [{"role": "user", "text": "Xin chao"}],
                "model": "gemma-4-31b-it",
            },
        ) as response:
            assert response.status_code == 200
            events = _collect_events(response)

    meta_payloads = [payload for event, payload in events if event == "meta"]
    assert meta_payloads
    conversation_id = meta_payloads[-1].get("conversation_id")
    assert isinstance(conversation_id, int)

    chunks = [payload.get("text", "") for event, payload in events if event == "chunk"]
    assert "".join(chunks) == "Xin chao"
    done_payloads = [payload for event, payload in events if event == "done"]
    assert done_payloads and done_payloads[-1]["text"] == "Xin chao"
    assert done_payloads[-1].get("conversation_id") == conversation_id

    db = SessionLocal()
    try:
        admin_id = _admin_user_id()
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        assert conversation is not None
        assert conversation.user_id == admin_id

        persisted = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .all()
        )
        assert len(persisted) >= 2
        assert persisted[-2].role == "user"
        assert persisted[-2].content == "Xin chao"
        assert persisted[-1].role == "assistant"
        assert persisted[-1].content == "Xin chao"
    finally:
        db.close()


def test_chat_stream_reuses_conversation(monkeypatch) -> None:
    def fake_stream_chat_text(messages, cfg):
        yield "ok"

    monkeypatch.setattr("app.api.routes.chat.stream_chat_text", fake_stream_chat_text)

    with TestClient(app) as client:
        headers = _admin_headers()
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            headers=headers,
            json={"messages": [{"role": "user", "text": "Turn 1"}]},
        ) as first_response:
            assert first_response.status_code == 200
            first_events = _collect_events(first_response)

        first_meta = [payload for event, payload in first_events if event == "meta"][-1]
        conversation_id = first_meta["conversation_id"]

        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            headers=headers,
            json={
                "conversation_id": conversation_id,
                "messages": [{"role": "user", "text": "Turn 2"}],
            },
        ) as second_response:
            assert second_response.status_code == 200
            second_events = _collect_events(second_response)

    second_meta = [payload for event, payload in second_events if event == "meta"][-1]
    assert second_meta["conversation_id"] == conversation_id

    db = SessionLocal()
    try:
        persisted = db.query(Message).filter(Message.conversation_id == conversation_id).all()
        assert len(persisted) >= 4
    finally:
        db.close()


def test_chat_stream_requires_auth() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat/stream",
            json={"messages": [{"role": "user", "text": "hello"}]},
        )

    assert response.status_code == 401


def test_chat_stream_returns_error_event(monkeypatch) -> None:
    def boom_stream_chat_text(messages, cfg):
        raise RuntimeError("upstream unavailable")
        yield ""

    monkeypatch.setattr("app.api.routes.chat.stream_chat_text", boom_stream_chat_text)

    with TestClient(app) as client:
        headers = _admin_headers()
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            headers=headers,
            json={"messages": [{"role": "user", "text": "hello"}]},
        ) as response:
            assert response.status_code == 200
            events = _collect_events(response)

    error_payloads = [payload for event, payload in events if event == "error"]
    assert error_payloads
    assert "upstream unavailable" in error_payloads[-1]["message"]


def test_chat_stream_forwards_inline_image_attachments(monkeypatch) -> None:
    def fake_stream_chat_text(messages, cfg):
        attachments = messages[-1].get("attachments", [])
        assert len(attachments) == 1
        assert attachments[0]["content_type"] == "image/png"
        assert attachments[0]["data_base64"] == "aGVsbG8="
        yield "ok"

    monkeypatch.setattr("app.api.routes.chat.stream_chat_text", fake_stream_chat_text)

    with TestClient(app) as client:
        headers = _admin_headers()
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            headers=headers,
            json={
                "messages": [
                    {
                        "role": "user",
                        "text": "Analyze this image",
                        "attachments": [
                            {
                                "file_name": "sample.png",
                                "content_type": "image/png",
                                "data_base64": "aGVsbG8=",
                            }
                        ],
                    }
                ]
            },
        ) as response:
            assert response.status_code == 200
            events = _collect_events(response)

    done_payloads = [payload for event, payload in events if event == "done"]
    assert done_payloads
    assert done_payloads[-1]["text"] == "ok"


def test_chat_stream_done_event_includes_web_citations(monkeypatch) -> None:
    def fake_stream_chat_text(messages, cfg):
        has_system_context = any(
            item.get("role") == "system" and "Web references below" in item.get("text", "")
            for item in messages
        )
        assert has_system_context
        yield "grounded answer"

    def fake_search_web(query: str, limit: int = 5, timeout_seconds: int = 12):
        assert query == "latest ai news"
        assert limit == 2
        return [
            {
                "title": "Example Source",
                "url": "https://example.com/news",
                "snippet": "A concise source snippet",
                "source": "example.com",
            }
        ]

    monkeypatch.setattr("app.api.routes.chat.stream_chat_text", fake_stream_chat_text)
    monkeypatch.setattr("app.api.routes.chat.search_web", fake_search_web)

    with TestClient(app) as client:
        headers = _admin_headers()
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            headers=headers,
            json={
                "messages": [{"role": "user", "text": "latest ai news"}],
                "enable_web_search": True,
                "web_search_max_results": 2,
            },
        ) as response:
            assert response.status_code == 200
            events = _collect_events(response)

    done_payloads = [payload for event, payload in events if event == "done"]
    assert done_payloads
    done_payload = done_payloads[-1]
    assert done_payload["text"] == "grounded answer"
    assert isinstance(done_payload.get("citations"), list)
    assert done_payload["citations"]
    assert done_payload["citations"][0]["url"] == "https://example.com/news"


def test_chat_stream_forwards_advanced_gemma_options_and_tool_calls(monkeypatch) -> None:
    def fake_stream_chat_text(messages, cfg):
        assert messages[-1]["text"] == "Call weather"
        assert cfg["candidate_count"] == 2
        assert cfg["stop_sequences"] == ["<END>"]
        assert cfg["seed"] == 42
        assert cfg["presence_penalty"] == 0.1
        assert cfg["frequency_penalty"] == 0.2
        assert cfg["system_prompt"].startswith("<|think|>")
        assert cfg["response_mime_type"] == "application/json"
        assert cfg["response_json_schema"]["type"] == "object"
        assert cfg["tools"][0]["name"] == "lookup_weather"
        assert cfg["function_calling_mode"] == "any"
        assert cfg["allowed_function_names"] == ["lookup_weather"]
        assert cfg["stream_function_call_arguments"] is True
        assert cfg["include_server_side_tool_invocations"] is True
        assert cfg["include_thoughts"] is True
        assert cfg["thinking_budget_tokens"] == 2048
        assert cfg["thinking_level"] == "medium"
        assert cfg["media_resolution"] == "high"
        assert cfg["safety_settings"][0]["category"] == "harassment"

        yield {
            "type": "tool_call",
            "kind": "function",
            "id": "call-1",
            "name": "lookup_weather",
            "args": {"city": "Ha Noi"},
        }
        yield '{"status":"ok"}'

    monkeypatch.setattr("app.api.routes.chat.stream_chat_text", fake_stream_chat_text)

    with TestClient(app) as client:
        headers = _admin_headers()
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            headers=headers,
            json={
                "messages": [{"role": "user", "text": "Call weather"}],
                "candidate_count": 2,
                "stop_sequences": ["<END>"],
                "seed": 42,
                "presence_penalty": 0.1,
                "frequency_penalty": 0.2,
                "enable_thinking": True,
                "include_thoughts": True,
                "thinking_budget_tokens": 2048,
                "thinking_level": "medium",
                "response_mime_type": "application/json",
                "response_json_schema": {
                    "type": "object",
                    "properties": {"status": {"type": "string"}},
                },
                "tools": [
                    {
                        "name": "lookup_weather",
                        "description": "Get weather by city",
                        "parameters_json_schema": {
                            "type": "object",
                            "properties": {"city": {"type": "string"}},
                            "required": ["city"],
                        },
                    }
                ],
                "function_calling_mode": "any",
                "allowed_function_names": ["lookup_weather"],
                "stream_function_call_arguments": True,
                "include_server_side_tool_invocations": True,
                "media_resolution": "high",
                "safety_settings": [
                    {"category": "harassment", "threshold": "block_medium_and_above"}
                ],
            },
        ) as response:
            assert response.status_code == 200
            events = _collect_events(response)

    tool_call_payloads = [payload for event, payload in events if event == "tool_call"]
    assert tool_call_payloads
    assert tool_call_payloads[-1]["name"] == "lookup_weather"
    assert tool_call_payloads[-1]["args"]["city"] == "Ha Noi"

    done_payloads = [payload for event, payload in events if event == "done"]
    assert done_payloads
    done_payload = done_payloads[-1]
    assert done_payload["text"] == '{"status":"ok"}'
    assert done_payload["tool_calls"]
    assert done_payload["tool_calls"][-1]["name"] == "lookup_weather"


def test_chat_stream_accepts_attachment_only_user_message(monkeypatch) -> None:
    def fake_stream_chat_text(messages, cfg):
        assert messages[-1]["text"] == ""
        attachments = messages[-1].get("attachments", [])
        assert len(attachments) == 1
        assert attachments[0]["content_type"] == "audio/wav"
        yield "audio processed"

    monkeypatch.setattr("app.api.routes.chat.stream_chat_text", fake_stream_chat_text)

    with TestClient(app) as client:
        headers = _admin_headers()
        with client.stream(
            "POST",
            "/api/v1/chat/stream",
            headers=headers,
            json={
                "messages": [
                    {
                        "role": "user",
                        "attachments": [
                            {
                                "file_name": "sample.wav",
                                "content_type": "audio/wav",
                                "data_base64": "aGVsbG8=",
                            }
                        ],
                    }
                ]
            },
        ) as response:
            assert response.status_code == 200
            events = _collect_events(response)

    done_payloads = [payload for event, payload in events if event == "done"]
    assert done_payloads
    assert done_payloads[-1]["text"] == "audio processed"
