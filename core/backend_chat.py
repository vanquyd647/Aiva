"""Backend SSE chat adapter for desktop app."""

from __future__ import annotations

import json
import threading
from typing import Callable

import requests


def send_message(
    messages: list[dict],
    cfg: dict,
    on_chunk: Callable[[str], None],
    on_done: Callable[[str], None],
    on_error: Callable[[str], None],
) -> None:
    """Send chat request to backend SSE endpoint and stream chunks to callbacks."""

    def _run() -> None:
        backend_url = str(cfg.get("backend_api_url", "")).strip().rstrip("/")
        if not backend_url:
            on_error("Backend API URL is missing")
            return

        token = str(cfg.get("backend_access_token", "")).strip()
        headers = {
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        payload = {
            "messages": messages,
            "conversation_id": cfg.get("_backend_conversation_id"),
            "conversation_title": cfg.get("_backend_conversation_title"),
            "enable_web_search": bool(cfg.get("use_web_citations", False)),
            "web_search_max_results": int(cfg.get("web_citation_max_results", 3) or 3),
            "model": cfg.get("model", "gemma-4-31b-it"),
            "temperature": cfg.get("temperature", 1.0),
            "top_p": cfg.get("top_p", 0.95),
            "top_k": cfg.get("top_k", 64),
            "max_output_tokens": cfg.get("max_output_tokens", 8192),
            "system_prompt": cfg.get("system_prompt", ""),
        }

        try:
            with requests.post(
                f"{backend_url}/api/v1/chat/stream",
                headers=headers,
                json=payload,
                stream=True,
                timeout=(10, 600),
            ) as response:
                if response.status_code >= 400:
                    detail = response.text.strip() or f"HTTP {response.status_code}"
                    on_error(detail)
                    return

                current_event = "message"
                full_text = ""

                for raw_line in response.iter_lines(decode_unicode=True):
                    if raw_line is None:
                        continue
                    line = raw_line.strip()
                    if not line:
                        continue

                    if line.startswith("event:"):
                        current_event = line.split(":", 1)[1].strip()
                        continue

                    if not line.startswith("data:"):
                        continue

                    raw_payload = line.split(":", 1)[1].strip()
                    try:
                        event_data = json.loads(raw_payload)
                    except Exception:
                        event_data = {"message": raw_payload}

                    if current_event == "chunk":
                        chunk = str(event_data.get("text", ""))
                        if chunk:
                            full_text += chunk
                            on_chunk(chunk)
                    elif current_event == "meta":
                        if event_data.get("conversation_id") is not None:
                            cfg["_backend_last_conversation_id"] = event_data.get("conversation_id")
                        if event_data.get("user_message_id") is not None:
                            cfg["_backend_last_user_message_id"] = event_data.get("user_message_id")
                    elif current_event == "done":
                        if event_data.get("conversation_id") is not None:
                            cfg["_backend_last_conversation_id"] = event_data.get("conversation_id")
                        if event_data.get("assistant_message_id") is not None:
                            cfg["_backend_last_assistant_message_id"] = event_data.get(
                                "assistant_message_id"
                            )
                        citations = event_data.get("citations")
                        if isinstance(citations, list):
                            cfg["_backend_last_citations"] = citations
                        final_text = str(event_data.get("text", full_text))
                        on_done(final_text)
                        return
                    elif current_event == "error":
                        on_error(str(event_data.get("message", "Streaming failed")))
                        return

                if full_text:
                    on_done(full_text)
                else:
                    on_error("Streaming ended unexpectedly")
        except Exception as exc:
            on_error(str(exc))

    threading.Thread(target=_run, daemon=True).start()
