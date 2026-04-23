"""Lưu và tải lịch sử hội thoại dạng JSON"""

import json
import uuid
from datetime import datetime
from pathlib import Path

HISTORY_DIR = Path(__file__).parent.parent / "chat_history"
HISTORY_DIR.mkdir(exist_ok=True)


def list_conversations() -> list[dict]:
    """Trả về danh sách hội thoại, mới nhất trước."""
    convos = []
    for f in sorted(HISTORY_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            convos.append({
                "id": f.stem,
                "title": data.get("title", "Hội thoại mới"),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "message_count": len(data.get("messages", [])),
            })
        except Exception:
            continue
    return convos


def load_conversation(conv_id: str) -> dict:
    path = HISTORY_DIR / f"{conv_id}.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return new_conversation()


def new_conversation() -> dict:
    return {
        "id": str(uuid.uuid4()),
        "title": "Hội thoại mới",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "messages": [],  # list of {"role": "user"|"assistant", "text": "..."}
    }


def save_conversation(conv: dict) -> None:
    conv["updated_at"] = datetime.now().isoformat()
    path = HISTORY_DIR / f"{conv['id']}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(conv, f, ensure_ascii=False, indent=2)


def delete_conversation(conv_id: str) -> None:
    path = HISTORY_DIR / f"{conv_id}.json"
    if path.exists():
        path.unlink()


def generate_title(first_user_message: str) -> str:
    """Tạo tiêu đề ngắn từ tin nhắn đầu tiên."""
    title = first_user_message.strip().replace("\n", " ")
    return title[:50] + ("…" if len(title) > 50 else "")
