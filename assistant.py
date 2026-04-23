"""
Trợ lý AI Gemma 4 - Phase 1 MVP
Sử dụng Gemini API (Cloud) + SDK google-genai mới nhất.
"""

import os
import sys
from dotenv import load_dotenv

# ─── Load API key từ .env ────────────────────────────────────────────────────
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    print("❌ Lỗi: Không tìm thấy GEMINI_API_KEY trong file .env")
    print("   Tạo file .env với nội dung: GEMINI_API_KEY=your_key_here")
    sys.exit(1)

from google import genai
from google.genai import types

# ─── Cấu hình ────────────────────────────────────────────────────────────────
# Tên model trên Gemini API - kiểm tra tên mới nhất tại: https://aistudio.google.com
MODEL_NAME = "gemma-4-31b-it"

# Gemma 4 hỗ trợ system_instruction chính thức qua GenerateContentConfig
SYSTEM_PROMPT = (
    "Bạn là trợ lý AI thông minh, thân thiện, nói Tiếng Việt. "
    "Luôn trả lời bằng Tiếng Việt, giải thích rõ ràng, xưng hô bạn/tôi. "
    "Thừa nhận khi không biết thay vì đoán mò."
)

# Tham số lấy mẫu theo khuyến nghị chính thức Google DeepMind
GENERATE_CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    temperature=1.0,
    top_p=0.95,
    top_k=64,
    max_output_tokens=8192,
)

# ─── Khởi tạo ────────────────────────────────────────────────────────────────
def init_client():
    return genai.Client(api_key=API_KEY)


def health_check(client) -> bool:
    """Kiểm tra kết nối API trước khi bắt đầu chat."""
    try:
        resp = client.models.generate_content(
            model=MODEL_NAME,
            contents="Xin chào! Trả lời ngắn gọn trong 1 câu bằng Tiếng Việt.",
            config=GENERATE_CONFIG,
        )
        return bool(resp.text)
    except Exception as e:
        print(f"❌ Không kết nối được API: {e}")
        return False


# ─── Chat loop ───────────────────────────────────────────────────────────────
def run_chat(client):
    # SDK chat API: tự động quản lý history
    chat = client.chats.create(
        model=MODEL_NAME,
        config=GENERATE_CONFIG,
    )

    print("\n" + "═" * 55)
    print(f"  🤖  Trợ Lý AI  |  {MODEL_NAME}")
    print("═" * 55)
    print("  Lệnh:  quit / exit  → thoát")
    print("         clear        → xoá lịch sử hội thoại")
    print("═" * 55 + "\n")

    while True:
        try:
            user_input = input("Bạn: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 Tạm biệt!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("👋 Tạm biệt!")
            break

        if user_input.lower() == "clear":
            chat = client.chats.create(
                model=MODEL_NAME,
                config=GENERATE_CONFIG,
            )
            print("🗑️  Đã xoá lịch sử hội thoại.\n")
            continue

        try:
            print("AI: ", end="", flush=True)
            response = chat.send_message(user_input)
            print(response.text)
            print()
        except Exception as e:
            print(f"\n❌ Lỗi khi gọi API: {e}\n")


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("⏳ Đang kết nối Gemini API...", end=" ", flush=True)
    client = init_client()

    if not health_check(client):
        sys.exit(1)

    print("✅ Sẵn sàng!")
    run_chat(client)
