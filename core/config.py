"""Quản lý cấu hình ứng dụng - lưu vào config.json"""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.json"

DEFAULTS = {
    "model": "gemma-4-31b-it",
    "temperature": 1.0,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "theme": "dark",
    "language": "vi",
    "use_backend_stream": False,
    "backend_api_url": "http://127.0.0.1:8080",
    "backend_access_token": "",
    "use_web_citations": True,
    "web_citation_max_results": 3,
    "system_prompt": (
        "Bạn là trợ lý AI thông minh, thân thiện. "
        "Luôn trả lời bằng Tiếng Việt, giải thích rõ ràng, xưng hô bạn/tôi. "
        "Thừa nhận khi không biết thay vì đoán mò."
    ),
    "available_models": [
        "gemma-4-31b-it",
        "gemma-4-26b-a4b-it",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ],
}


def load() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Merge với defaults để không thiếu key mới
            return {**DEFAULTS, **data}
        except Exception:
            pass
    return dict(DEFAULTS)


def save(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
