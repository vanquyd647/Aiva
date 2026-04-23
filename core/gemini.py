"""Gemini API wrapper - hỗ trợ streaming và multi-turn chat"""

import os
import threading
from typing import Callable

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY chưa được cài đặt trong file .env")
        _client = genai.Client(api_key=api_key)
    return _client


def reset_client() -> None:
    """Gọi khi người dùng thay đổi API key."""
    global _client
    _client = None


def _to_sdk_contents(messages: list[dict]) -> list[types.Content]:
    """
    Chuyển list messages JSON thành Contents cho API.
    messages: [{"role": "user"|"assistant", "text": "..."}]
    """
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(
            types.Content(role=role, parts=[types.Part(text=msg["text"])])
        )
    return contents


def send_message(
    messages: list[dict],
    cfg: dict,
    on_chunk: Callable[[str], None],
    on_done: Callable[[str], None],
    on_error: Callable[[str], None],
) -> None:
    """
    Gửi tin nhắn với streaming, chạy trong thread riêng để không block UI.
    - on_chunk(text): gọi mỗi khi có chunk mới
    - on_done(full_text): gọi khi hoàn thành
    - on_error(message): gọi nếu lỗi
    """
    def _run():
        try:
            client = get_client()
            # system_instruction được hỗ trợ chính thức trên Gemma 4 API
            gen_config = types.GenerateContentConfig(
                system_instruction=cfg.get("system_prompt", ""),
                temperature=cfg.get("temperature", 1.0),
                top_p=cfg.get("top_p", 0.95),
                top_k=cfg.get("top_k", 64),
                max_output_tokens=cfg.get("max_output_tokens", 8192),
            )
            contents = _to_sdk_contents(messages)
            full_text = ""
            for chunk in client.models.generate_content_stream(
                model=cfg.get("model", "gemma-4-31b-it"),
                contents=contents,
                config=gen_config,
            ):
                if chunk.text:
                    full_text += chunk.text
                    on_chunk(chunk.text)
            on_done(full_text)
        except Exception as e:
            on_error(str(e))

    threading.Thread(target=_run, daemon=True).start()


def test_connection(cfg: dict) -> tuple[bool, str]:
    """Kiểm tra kết nối API. Trả về (success, message)."""
    try:
        client = get_client()
        resp = client.models.generate_content(
            model=cfg.get("model", "gemma-4-31b-it"),
            contents="Xin chào! Trả lời 1 câu ngắn bằng Tiếng Việt.",
            config=types.GenerateContentConfig(max_output_tokens=50),
        )
        return True, resp.text.strip()
    except Exception as e:
        return False, str(e)
