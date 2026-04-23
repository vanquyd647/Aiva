"""
Trợ Lý AI - Desktop App
GUI chính: Sidebar hội thoại + Khung chat + Settings
"""

import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as msgbox
from pathlib import Path
import customtkinter as ctk

import core.config as cfg_module
import core.history as history
import core.gemini as gemini

# ─── Cấu hình giao diện mặc định ─────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

APP_TITLE = "AI Assist Studio"
APP_SUBTITLE = "Gemma Workspace"
APP_W, APP_H = 1200, 760
SIDEBAR_W = 250


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, cfg: dict, on_save):
        super().__init__(parent)
        self.title("⚙️  Cài Đặt")
        self.geometry("520x560")
        self.resizable(False, False)
        self.grab_set()

        self.cfg = dict(cfg)
        self.on_save = on_save
        self._build()

    def _build(self):
        pad = {"padx": 20, "pady": 6}

        ctk.CTkLabel(self, text="Model", anchor="w").pack(fill="x", **pad)
        self.model_var = ctk.StringVar(value=self.cfg["model"])
        ctk.CTkOptionMenu(
            self,
            variable=self.model_var,
            values=self.cfg.get("available_models", [self.cfg["model"]]),
        ).pack(fill="x", **pad)

        ctk.CTkLabel(self, text="Temperature", anchor="w").pack(fill="x", **pad)
        self.temp_var = ctk.DoubleVar(value=self.cfg["temperature"])
        ctk.CTkSlider(self, from_=0, to=2, variable=self.temp_var, number_of_steps=20).pack(fill="x", **pad)

        ctk.CTkLabel(self, text="System Prompt", anchor="w").pack(fill="x", **pad)
        self.prompt_box = ctk.CTkTextbox(self, height=140)
        self.prompt_box.pack(fill="x", **pad)
        self.prompt_box.insert("end", self.cfg.get("system_prompt", ""))

        ctk.CTkLabel(self, text="Theme", anchor="w").pack(fill="x", **pad)
        self.theme_var = ctk.StringVar(value=self.cfg["theme"])
        ctk.CTkOptionMenu(self, variable=self.theme_var, values=["dark", "light", "system"]).pack(fill="x", **pad)

        # Nút lưu
        ctk.CTkButton(self, text="💾  Lưu cài đặt", command=self._save).pack(pady=16)

    def _save(self):
        self.cfg["model"]         = self.model_var.get()
        self.cfg["temperature"]   = round(self.temp_var.get(), 2)
        self.cfg["system_prompt"] = self.prompt_box.get("1.0", "end").strip()
        self.cfg["theme"]         = self.theme_var.get()
        self.on_save(self.cfg)
        ctk.set_appearance_mode(self.cfg["theme"])
        self.destroy()


class Sidebar(ctk.CTkFrame):
    def __init__(self, parent, on_select, on_new, on_delete, on_search):
        super().__init__(parent, width=SIDEBAR_W, corner_radius=0)
        self.on_select = on_select
        self.on_new    = on_new
        self.on_delete = on_delete
        self.on_search = on_search
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._active_id: str | None = None
        self._build()

    def _build(self):
        self.pack_propagate(False)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(12, 6))
        ctk.CTkLabel(
            header,
            text="Conversations",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left")
        ctk.CTkButton(
            header,
            text="New",
            width=64,
            height=28,
            command=self.on_new,
        ).pack(side="right")

        self.search_var = ctk.StringVar(value="")
        self.search_entry = ctk.CTkEntry(
            self,
            textvariable=self.search_var,
            placeholder_text="Search conversations",
            height=30,
        )
        self.search_entry.pack(fill="x", padx=12, pady=(0, 6))
        self.search_entry.bind("<KeyRelease>", self._emit_search)

        self.list_frame = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True, padx=4)

    def _emit_search(self, _event=None):
        self.on_search(self.search_var.get().strip())

    def refresh(self, conversations: list[dict], active_id: str | None = None):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self._buttons.clear()
        self._active_id = active_id

        for conv in conversations:
            cid   = conv["id"]
            title = conv["title"]
            count = conv["message_count"]
            label = f"{title}\n{count} tin nhắn"

            row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)

            btn = ctk.CTkButton(
                row, text=label, anchor="w",
                height=48, corner_radius=8,
                font=ctk.CTkFont(size=12),
                fg_color=("gray75", "gray25") if cid == active_id else "transparent",
                text_color=("black", "white"),
                hover_color=("gray70", "gray30"),
                command=lambda c=cid: self.on_select(c),
            )
            btn.pack(side="left", fill="x", expand=True)

            del_btn = ctk.CTkButton(
                row, text="🗑", width=28, height=28,
                corner_radius=6, fg_color="transparent",
                hover_color=("red", "#8B0000"),
                command=lambda c=cid: self.on_delete(c),
            )
            del_btn.pack(side="right", padx=(2, 0))
            self._buttons[cid] = btn


class ChatArea(ctk.CTkFrame):
    """Vùng hiển thị và nhập chat."""

    BUBBLE_USER = ("#c9f2dd", "#14402c")
    BUBBLE_AI = ("#eef1f4", "#252d37")
    THINKING_CLR = ("gray60", "gray50")

    def __init__(self, parent, on_send):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self.on_send = on_send
        self._build()
        self._thinking_id: str | None = None

    def _build(self):
        # ── Vùng chat hiển thị ──
        self.display = ctk.CTkScrollableFrame(self, corner_radius=8)
        self.display.pack(fill="both", expand=True, padx=12, pady=(12, 6))

        quick_row = ctk.CTkFrame(self, fg_color="transparent")
        quick_row.pack(fill="x", padx=12, pady=(0, 6))
        presets = [
            "Tom tat nhanh noi dung nay",
            "Lap ke hoach hanh dong 5 buoc",
            "Giai thich de hieu nhu cho nguoi moi",
            "Dich sang Tieng Anh chuyen nghiep",
        ]
        for preset in presets:
            ctk.CTkButton(
                quick_row,
                text=preset,
                height=28,
                width=0,
                command=lambda p=preset: self._insert_prompt(p),
            ).pack(side="left", padx=(0, 6))

        # ── Thanh nhập ──
        input_row = ctk.CTkFrame(self, fg_color="transparent")
        input_row.pack(fill="x", padx=12, pady=(0, 12))

        self.input_box = ctk.CTkTextbox(input_row, height=72, corner_radius=10, wrap="word")
        self.input_box.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.input_box.bind("<Return>", self._on_enter)
        self.input_box.bind("<Shift-Return>", lambda e: None)

        self.send_btn = ctk.CTkButton(
            input_row, text="Gửi ▶", width=80, height=72,
            corner_radius=10, command=self._submit,
        )
        self.send_btn.pack(side="right")

    def _on_enter(self, event):
        # Shift+Enter = xuống dòng; Enter = gửi
        if not event.state & 0x1:  # không giữ Shift
            self._submit()
            return "break"

    def _submit(self):
        text = self.input_box.get("1.0", "end").strip()
        if text:
            self.input_box.delete("1.0", "end")
            self.on_send(text)

    def _insert_prompt(self, text: str) -> None:
        self.input_box.delete("1.0", "end")
        self.input_box.insert("1.0", text)
        self.input_box.focus_set()

    # ── Thêm bubble ──
    def add_message(self, role: str, text: str) -> ctk.CTkLabel:
        is_user  = role == "user"
        bg_color = self.BUBBLE_USER if is_user else self.BUBBLE_AI
        anchor   = "e" if is_user else "w"
        prefix   = "🧑  " if is_user else "🤖  "

        wrapper = ctk.CTkFrame(self.display, fg_color="transparent")
        wrapper.pack(fill="x", pady=4)

        bubble = ctk.CTkLabel(
            wrapper,
            text=prefix + text,
            wraplength=600,
            justify="left",
            fg_color=bg_color,
            corner_radius=12,
            padx=12, pady=8,
            font=ctk.CTkFont(size=13),
            anchor="w",
        )
        bubble.pack(anchor=anchor, padx=8)
        self._scroll_bottom()
        return bubble

    def show_thinking(self):
        """Hiển thị '...' khi đang chờ AI trả lời."""
        self._thinking_lbl = self.add_message("assistant", "⏳ Đang suy nghĩ…")

    def hide_thinking(self):
        if hasattr(self, "_thinking_lbl"):
            self._thinking_lbl.master.destroy()

    def update_last_ai(self, text: str):
        """Cập nhật text của bubble AI cuối cùng (streaming)."""
        if hasattr(self, "_streaming_lbl"):
            self._streaming_lbl.configure(text="🤖  " + text)
            self._scroll_bottom()

    def start_streaming_bubble(self) -> None:
        self._streaming_text = ""
        self._streaming_lbl  = self.add_message("assistant", "")

    def append_stream(self, chunk: str) -> None:
        self._streaming_text += chunk
        if hasattr(self, "_streaming_lbl"):
            self._streaming_lbl.configure(text="🤖  " + self._streaming_text)
            self._scroll_bottom()

    def clear(self):
        for w in self.display.winfo_children():
            w.destroy()

    def set_input_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.input_box.configure(state=state)
        self.send_btn.configure(state=state)

    def _scroll_bottom(self):
        self.display.after(50, lambda: self.display._parent_canvas.yview_moveto(1.0))


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(f"{APP_W}x{APP_H}")
        self.minsize(800, 500)

        self.cfg      = cfg_module.load()
        self.conv     = history.new_conversation()
        self._is_busy = False
        self._conversation_query = ""

        self._build_layout()
        self._refresh_sidebar()
        self._update_meta()
        self._bind_shortcuts()

    # ─── Layout ──────────────────────────────────────────────────────────────
    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = Sidebar(
            self,
            on_select=self._load_conversation,
            on_new=self._new_conversation,
            on_delete=self._delete_conversation,
            on_search=self._on_sidebar_search,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # Right panel
        right = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # Top bar
        topbar = ctk.CTkFrame(right, height=62, corner_radius=0)
        topbar.grid(row=0, column=0, sticky="ew")
        topbar.grid_propagate(False)

        title_wrap = ctk.CTkFrame(topbar, fg_color="transparent")
        title_wrap.pack(side="left", padx=16)

        self.title_lbl = ctk.CTkLabel(title_wrap, text=APP_TITLE, font=ctk.CTkFont(size=18, weight="bold"))
        self.title_lbl.pack(anchor="w")
        ctk.CTkLabel(
            title_wrap,
            text=APP_SUBTITLE,
            font=ctk.CTkFont(size=12),
            text_color=("gray35", "gray65"),
        ).pack(anchor="w")
        self.meta_lbl = ctk.CTkLabel(
            title_wrap,
            text="0 messages",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray60"),
        )
        self.meta_lbl.pack(anchor="w")

        ctk.CTkButton(
            topbar,
            text="Export",
            width=78,
            height=30,
            command=self._export_current_conversation,
        ).pack(side="right", padx=(0, 8))

        ctk.CTkButton(
            topbar,
            text="Clear",
            width=70,
            height=30,
            command=self._clear_current_messages,
        ).pack(side="right", padx=(0, 8))

        self.status_lbl = ctk.CTkLabel(
            topbar,
            text="Ready",
            fg_color=("#d9f7e8", "#1e3b2f"),
            text_color=("#115a35", "#93f0c3"),
            corner_radius=8,
            padx=10,
            pady=5,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.status_lbl.pack(side="right", padx=(0, 10))

        ctk.CTkButton(
            topbar, text="⚙️  Cài đặt", width=110, height=30,
            command=self._open_settings,
        ).pack(side="right", padx=(0, 10))

        # Chat area
        self.chat = ChatArea(right, on_send=self._on_user_send)
        self.chat.grid(row=1, column=0, sticky="nsew")

    def _set_status(self, text: str, kind: str = "ready"):
        styles = {
            "ready": {
                "fg_color": ("#d9f7e8", "#1e3b2f"),
                "text_color": ("#115a35", "#93f0c3"),
            },
            "busy": {
                "fg_color": ("#fff1d6", "#4a3520"),
                "text_color": ("#8a5a00", "#ffd18c"),
            },
            "error": {
                "fg_color": ("#ffdcdc", "#4f2424"),
                "text_color": ("#8a1d1d", "#ff9b9b"),
            },
        }
        style = styles.get(kind, styles["ready"])
        self.status_lbl.configure(text=text, fg_color=style["fg_color"], text_color=style["text_color"])

    # ─── Sidebar actions ─────────────────────────────────────────────────────
    def _refresh_sidebar(self):
        convos = history.list_conversations()
        if self._conversation_query:
            needle = self._conversation_query.lower()
            convos = [
                c for c in convos
                if needle in c.get("title", "").lower()
            ]
        self.sidebar.refresh(convos, active_id=self.conv.get("id"))

    def _on_sidebar_search(self, query: str):
        self._conversation_query = query
        self._refresh_sidebar()

    def _new_conversation(self):
        self.conv = history.new_conversation()
        self.chat.clear()
        self.title_lbl.configure(text=APP_TITLE)
        self._set_status("Ready", "ready")
        self._update_meta()
        self._refresh_sidebar()

    def _load_conversation(self, conv_id: str):
        self.conv = history.load_conversation(conv_id)
        self.chat.clear()
        for msg in self.conv.get("messages", []):
            self.chat.add_message(msg["role"], msg["text"])
        self.title_lbl.configure(text=self.conv.get("title", APP_TITLE))
        self._update_meta()
        self._refresh_sidebar()

    def _delete_conversation(self, conv_id: str):
        if not msgbox.askyesno("Xác nhận", "Xoá hội thoại này?"):
            return
        history.delete_conversation(conv_id)
        if self.conv.get("id") == conv_id:
            self._new_conversation()
        else:
            self._refresh_sidebar()

    # ─── Chat ────────────────────────────────────────────────────────────────
    def _on_user_send(self, text: str):
        if self._is_busy:
            return

        self._is_busy = True
        self.chat.set_input_enabled(False)
        self._set_status("Generating...", "busy")

        # Hiển thị tin nhắn người dùng
        self.chat.add_message("user", text)
        self.conv["messages"].append({"role": "user", "text": text})
        self._update_meta()

        # Cập nhật tiêu đề nếu là tin đầu
        if len(self.conv["messages"]) == 1:
            title = history.generate_title(text)
            self.conv["title"] = title
            self.title_lbl.configure(text=title)

        # Bắt đầu bubble streaming
        self.chat.start_streaming_bubble()

        gemini.send_message(
            messages=self.conv["messages"],
            cfg=self.cfg,
            on_chunk=self._on_chunk,
            on_done=self._on_done,
            on_error=self._on_error,
        )

    def _on_chunk(self, chunk: str):
        self.after(0, lambda: self.chat.append_stream(chunk))

    def _on_done(self, full_text: str):
        self.conv["messages"].append({"role": "assistant", "text": full_text})
        history.save_conversation(self.conv)
        self._update_meta()
        self.after(0, self._after_response)

    def _on_error(self, err: str):
        def _show():
            self.chat.append_stream(f"\n❌ Lỗi: {err}")
            self._set_status("Error", "error")
            self._after_response()
        self.after(0, _show)

    def _after_response(self):
        self._is_busy = False
        self.chat.set_input_enabled(True)
        if self.status_lbl.cget("text") != "Error":
            self._set_status("Ready", "ready")
        self._refresh_sidebar()

    def _update_meta(self):
        msg_count = len(self.conv.get("messages", []))
        updated_at = self.conv.get("updated_at") or self.conv.get("created_at") or ""
        if updated_at:
            self.meta_lbl.configure(text=f"{msg_count} messages • updated {updated_at[:16].replace('T', ' ')}")
        else:
            self.meta_lbl.configure(text=f"{msg_count} messages")

    def _clear_current_messages(self):
        if not self.conv.get("messages"):
            msgbox.showinfo("Thông báo", "Hội thoại hiện tại đang trống")
            return
        if not msgbox.askyesno("Xác nhận", "Xoá toàn bộ tin nhắn trong hội thoại hiện tại?"):
            return

        self.conv["messages"] = []
        self.conv["title"] = "Hội thoại mới"
        self.chat.clear()
        self.title_lbl.configure(text=APP_TITLE)
        history.save_conversation(self.conv)
        self._update_meta()
        self._refresh_sidebar()
        self._set_status("Conversation cleared", "ready")

    def _safe_file_stem(self, value: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", " "} else "_" for ch in value)
        cleaned = " ".join(cleaned.split()).strip()
        return cleaned or "conversation"

    def _export_current_conversation(self):
        messages = self.conv.get("messages", [])
        if not messages:
            msgbox.showinfo("Thông báo", "Không có nội dung để export")
            return

        title = self.conv.get("title", "conversation")
        default_name = f"{self._safe_file_stem(title)}.md"
        file_path = filedialog.asksaveasfilename(
            title="Export Conversation",
            defaultextension=".md",
            initialfile=default_name,
            filetypes=[("Markdown", "*.md"), ("Text", "*.txt"), ("All files", "*.*")],
        )
        if not file_path:
            return

        lines = [f"# {title}", "", f"Conversation ID: {self.conv.get('id', '-')}", ""]
        for item in messages:
            role = "User" if item.get("role") == "user" else "Assistant"
            lines.append(f"## {role}")
            lines.append(item.get("text", ""))
            lines.append("")

        output = "\n".join(lines).strip() + "\n"
        Path(file_path).write_text(output, encoding="utf-8")
        self._set_status("Conversation exported", "ready")
        msgbox.showinfo("Export", f"Đã lưu hội thoại: {file_path}")

    def _bind_shortcuts(self):
        self.bind("<Control-n>", self._shortcut_new_conversation)
        self.bind("<Control-e>", self._shortcut_export)
        self.bind("<Control-k>", self._shortcut_focus_search)

    def _shortcut_new_conversation(self, _event=None):
        self._new_conversation()
        return "break"

    def _shortcut_export(self, _event=None):
        self._export_current_conversation()
        return "break"

    def _shortcut_focus_search(self, _event=None):
        self.sidebar.search_entry.focus_set()
        return "break"

    # ─── Settings ────────────────────────────────────────────────────────────
    def _open_settings(self):
        def _save(new_cfg):
            self.cfg = new_cfg
            cfg_module.save(new_cfg)
            gemini.reset_client()   # reset client khi model/key thay đổi
            self._set_status(f"Model: {self.cfg['model']}", "ready")

        SettingsDialog(self, self.cfg, on_save=_save)


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
