"""
Trợ Lý AI - Desktop App
GUI chính: Sidebar hội thoại + Khung chat + Settings
"""

import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as msgbox
import tkinter.simpledialog as simpledialog
import base64
import mimetypes
import threading
from pathlib import Path
import customtkinter as ctk
import requests

import core.config as cfg_module
import core.history as history
import core.i18n as i18n
import core.backend_chat as backend_chat
import core.gemini as gemini

# ─── Cấu hình giao diện mặc định ─────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

APP_TITLE = "AI Assist Studio"
APP_SUBTITLE = "Gemma Workspace"
APP_W, APP_H = 1200, 760
SIDEBAR_W = 250
LANGUAGES = ["vi", "en"]
ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024
ATTACHMENT_PREVIEW_CHARS = 1600
LOCAL_TEXT_ATTACHMENT_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".xml",
    ".yml",
    ".yaml",
    ".log",
    ".py",
    ".js",
    ".ts",
    ".html",
    ".css",
}


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, cfg: dict, on_save, tr):
        super().__init__(parent)
        self.tr = tr
        self.title(self.tr("settings_dialog_title"))
        self.geometry("520x560")
        self.resizable(False, False)
        self.grab_set()

        self.cfg = dict(cfg)
        self.on_save = on_save
        self._build()

    def _build(self):
        pad = {"padx": 20, "pady": 6}

        ctk.CTkLabel(self, text=self.tr("settings_model"), anchor="w").pack(fill="x", **pad)
        self.model_var = ctk.StringVar(value=self.cfg["model"])
        ctk.CTkOptionMenu(
            self,
            variable=self.model_var,
            values=self.cfg.get("available_models", [self.cfg["model"]]),
        ).pack(fill="x", **pad)

        ctk.CTkLabel(self, text=self.tr("settings_temperature"), anchor="w").pack(fill="x", **pad)
        self.temp_var = ctk.DoubleVar(value=self.cfg["temperature"])
        ctk.CTkSlider(self, from_=0, to=2, variable=self.temp_var, number_of_steps=20).pack(
            fill="x", **pad
        )

        ctk.CTkLabel(self, text=self.tr("settings_system_prompt"), anchor="w").pack(fill="x", **pad)
        self.prompt_box = ctk.CTkTextbox(self, height=140)
        self.prompt_box.pack(fill="x", **pad)
        self.prompt_box.insert("end", self.cfg.get("system_prompt", ""))

        ctk.CTkLabel(self, text=self.tr("settings_theme"), anchor="w").pack(fill="x", **pad)
        self.theme_var = ctk.StringVar(value=self.cfg["theme"])
        ctk.CTkOptionMenu(self, variable=self.theme_var, values=["dark", "light", "system"]).pack(
            fill="x", **pad
        )

        ctk.CTkLabel(self, text=self.tr("settings_language"), anchor="w").pack(fill="x", **pad)
        self.language_var = ctk.StringVar(value=self.cfg.get("language", "vi"))
        ctk.CTkOptionMenu(self, variable=self.language_var, values=LANGUAGES).pack(fill="x", **pad)

        ctk.CTkLabel(self, text=self.tr("settings_backend_stream"), anchor="w").pack(
            fill="x", **pad
        )
        self.backend_stream_var = tk.BooleanVar(
            value=bool(self.cfg.get("use_backend_stream", False))
        )
        ctk.CTkSwitch(
            self, text="", variable=self.backend_stream_var, onvalue=True, offvalue=False
        ).pack(anchor="w", **pad)

        ctk.CTkLabel(self, text=self.tr("settings_web_citations"), anchor="w").pack(fill="x", **pad)
        self.web_citations_var = tk.BooleanVar(value=bool(self.cfg.get("use_web_citations", True)))
        ctk.CTkSwitch(
            self, text="", variable=self.web_citations_var, onvalue=True, offvalue=False
        ).pack(anchor="w", **pad)

        ctk.CTkLabel(self, text=self.tr("settings_web_citation_limit"), anchor="w").pack(
            fill="x", **pad
        )
        self.web_citation_limit_var = ctk.StringVar(
            value=str(int(self.cfg.get("web_citation_max_results", 3) or 3))
        )
        ctk.CTkOptionMenu(
            self,
            variable=self.web_citation_limit_var,
            values=["2", "3", "4", "5", "6", "8", "10"],
        ).pack(fill="x", **pad)

        ctk.CTkLabel(self, text=self.tr("settings_backend_url"), anchor="w").pack(fill="x", **pad)
        self.backend_url_var = ctk.StringVar(value=self.cfg.get("backend_api_url", ""))
        ctk.CTkEntry(self, textvariable=self.backend_url_var).pack(fill="x", **pad)

        ctk.CTkLabel(self, text=self.tr("settings_backend_token"), anchor="w").pack(fill="x", **pad)
        self.backend_token_var = ctk.StringVar(value=self.cfg.get("backend_access_token", ""))
        ctk.CTkEntry(self, textvariable=self.backend_token_var, show="*").pack(fill="x", **pad)

        # Nút lưu
        ctk.CTkButton(self, text=self.tr("settings_save"), command=self._save).pack(pady=16)

    def _save(self):
        self.cfg["model"] = self.model_var.get()
        self.cfg["temperature"] = round(self.temp_var.get(), 2)
        self.cfg["system_prompt"] = self.prompt_box.get("1.0", "end").strip()
        self.cfg["theme"] = self.theme_var.get()
        self.cfg["language"] = self.language_var.get()
        self.cfg["use_backend_stream"] = bool(self.backend_stream_var.get())
        self.cfg["use_web_citations"] = bool(self.web_citations_var.get())
        try:
            self.cfg["web_citation_max_results"] = int(self.web_citation_limit_var.get())
        except Exception:
            self.cfg["web_citation_max_results"] = 3
        self.cfg["backend_api_url"] = self.backend_url_var.get().strip()
        self.cfg["backend_access_token"] = self.backend_token_var.get().strip()
        self.on_save(self.cfg)
        ctk.set_appearance_mode(self.cfg["theme"])
        self.destroy()


class Sidebar(ctk.CTkFrame):
    def __init__(self, parent, on_select, on_new, on_delete, on_search, tr):
        super().__init__(parent, width=SIDEBAR_W, corner_radius=0)
        self.on_select = on_select
        self.on_new = on_new
        self.on_delete = on_delete
        self.on_search = on_search
        self.tr = tr
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._active_id: str | None = None
        self._build()

    def _build(self):
        self.pack_propagate(False)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(12, 6))
        ctk.CTkLabel(
            header,
            text=self.tr("sidebar_conversations"),
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left")
        ctk.CTkButton(
            header,
            text=self.tr("sidebar_new"),
            width=64,
            height=28,
            command=self.on_new,
        ).pack(side="right")

        self.search_var = ctk.StringVar(value="")
        self.search_entry = ctk.CTkEntry(
            self,
            textvariable=self.search_var,
            placeholder_text=self.tr("sidebar_search_placeholder"),
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
            cid = conv["id"]
            title = conv["title"]
            count = conv["message_count"]
            label = f"{title}\n{self.tr('sidebar_message_count', count=count)}"

            row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)

            btn = ctk.CTkButton(
                row,
                text=label,
                anchor="w",
                height=48,
                corner_radius=8,
                font=ctk.CTkFont(size=12),
                fg_color=("gray75", "gray25") if cid == active_id else "transparent",
                text_color=("black", "white"),
                hover_color=("gray70", "gray30"),
                command=lambda c=cid: self.on_select(c),
            )
            btn.pack(side="left", fill="x", expand=True)

            del_btn = ctk.CTkButton(
                row,
                text="🗑",
                width=28,
                height=28,
                corner_radius=6,
                fg_color="transparent",
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

    def __init__(
        self,
        parent,
        on_send,
        on_message_action,
        on_input_change,
        on_pick_attachment,
        on_clear_attachments,
        tr,
    ):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        self.on_send = on_send
        self.on_message_action = on_message_action
        self.on_input_change = on_input_change
        self.on_pick_attachment = on_pick_attachment
        self.on_clear_attachments = on_clear_attachments
        self.tr = tr
        self._has_pending_attachments = False
        self._build()
        self._thinking_id: str | None = None

    def _build(self):
        # ── Vùng chat hiển thị ──
        self.display = ctk.CTkScrollableFrame(self, corner_radius=8)
        self.display.pack(fill="both", expand=True, padx=12, pady=(12, 6))

        quick_row = ctk.CTkFrame(self, fg_color="transparent")
        quick_row.pack(fill="x", padx=12, pady=(0, 6))
        presets = [
            self.tr("quick_prompt_summary"),
            self.tr("quick_prompt_plan"),
            self.tr("quick_prompt_explain"),
            self.tr("quick_prompt_translate"),
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

        self.attach_btn = ctk.CTkButton(
            input_row,
            text=self.tr("chat_attach"),
            width=56,
            height=72,
            corner_radius=10,
            command=self.on_pick_attachment,
        )
        self.attach_btn.pack(side="left", padx=(0, 8))

        self.input_box = ctk.CTkTextbox(input_row, height=72, corner_radius=10, wrap="word")
        self.input_box.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.input_box.bind("<Return>", self._on_enter)
        self.input_box.bind("<Shift-Return>", lambda e: None)
        self.input_box.bind("<KeyRelease>", self._on_input_changed)

        self.send_btn = ctk.CTkButton(
            input_row,
            text=self.tr("chat_send"),
            width=80,
            height=72,
            corner_radius=10,
            command=self._submit,
        )
        self.send_btn.pack(side="right")

        self.attachments_row = ctk.CTkFrame(self, fg_color="transparent")
        self.attachments_row.pack(fill="x", padx=12, pady=(0, 10))

        self.attachments_lbl = ctk.CTkLabel(
            self.attachments_row,
            text=self.tr("chat_attachments_empty"),
            anchor="w",
            font=ctk.CTkFont(size=11),
            text_color=("gray35", "gray65"),
        )
        self.attachments_lbl.pack(side="left", fill="x", expand=True)

        self.clear_attachments_btn = ctk.CTkButton(
            self.attachments_row,
            text=self.tr("chat_attachments_clear"),
            width=96,
            height=24,
            state="disabled",
            command=self.on_clear_attachments,
        )
        self.clear_attachments_btn.pack(side="right")

    def _on_enter(self, event):
        # Shift+Enter = xuống dòng; Enter = gửi
        if not event.state & 0x1:  # không giữ Shift
            self._submit()
            return "break"

    def _submit(self):
        text = self.input_box.get("1.0", "end").strip()
        self.input_box.delete("1.0", "end")
        self._emit_input_change()
        self.on_send(text)

    def _insert_prompt(self, text: str) -> None:
        self.input_box.delete("1.0", "end")
        self.input_box.insert("1.0", text)
        self._emit_input_change()
        self.input_box.focus_set()

    # ── Thêm bubble ──
    def add_message(self, role: str, text: str, message_index: int | None = None) -> ctk.CTkLabel:
        is_user = role == "user"
        bg_color = self.BUBBLE_USER if is_user else self.BUBBLE_AI
        anchor = "e" if is_user else "w"
        prefix = "🧑  " if is_user else "🤖  "

        wrapper = ctk.CTkFrame(self.display, fg_color="transparent")
        wrapper.pack(fill="x", pady=4)

        bubble = ctk.CTkLabel(
            wrapper,
            text=prefix + text,
            wraplength=600,
            justify="left",
            fg_color=bg_color,
            corner_radius=12,
            padx=12,
            pady=8,
            font=ctk.CTkFont(size=13),
            anchor="w",
        )
        bubble.pack(anchor=anchor, padx=8)
        if message_index is not None:
            self._bind_message_menu(bubble, role, message_index)
        self._scroll_bottom()
        return bubble

    def _bind_message_menu(
        self,
        bubble: ctk.CTkLabel,
        role: str,
        message_index: int,
    ) -> None:
        bubble.bind(
            "<Button-3>",
            lambda event, r=role, i=message_index: self._open_message_menu(event, r, i),
        )

    def _open_message_menu(self, event, role: str, message_index: int) -> None:
        if not callable(self.on_message_action):
            return

        menu = tk.Menu(self, tearoff=0)
        if role == "user":
            menu.add_command(
                label=self.tr("chat_action_edit"),
                command=lambda: self._dispatch_message_action("edit", message_index),
            )
        menu.add_command(
            label=self.tr("chat_action_regenerate"),
            command=lambda: self._dispatch_message_action("regenerate", message_index),
        )
        menu.add_command(
            label=self.tr("chat_action_branch"),
            command=lambda: self._dispatch_message_action("branch", message_index),
        )

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _dispatch_message_action(self, action: str, message_index: int) -> None:
        if callable(self.on_message_action):
            self.on_message_action(action, message_index)

    def _on_input_changed(self, _event=None) -> None:
        self._emit_input_change()

    def _emit_input_change(self) -> None:
        if callable(self.on_input_change):
            self.on_input_change(self.get_input_text())

    def get_input_text(self) -> str:
        return self.input_box.get("1.0", "end").strip()

    def set_input_text(self, text: str, notify: bool = False) -> None:
        was_disabled = str(self.input_box.cget("state")) == "disabled"
        if was_disabled:
            self.input_box.configure(state="normal")

        self.input_box.delete("1.0", "end")
        if text:
            self.input_box.insert("1.0", text)

        if was_disabled:
            self.input_box.configure(state="disabled")

        if notify:
            self._emit_input_change()

    def show_thinking(self):
        """Hiển thị '...' khi đang chờ AI trả lời."""
        self._thinking_lbl = self.add_message("assistant", self.tr("chat_thinking"))

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
        self._streaming_lbl = self.add_message("assistant", "")

    def finalize_streaming_message(self, message_index: int) -> None:
        if hasattr(self, "_streaming_lbl"):
            self._bind_message_menu(self._streaming_lbl, "assistant", message_index)

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
        self.attach_btn.configure(state=state)

        clear_state = "disabled"
        if enabled and self._has_pending_attachments:
            clear_state = "normal"
        self.clear_attachments_btn.configure(state=clear_state)

    def set_pending_attachments(self, attachments: list[dict]) -> None:
        self._has_pending_attachments = bool(attachments)
        if not attachments:
            self.attachments_lbl.configure(text=self.tr("chat_attachments_empty"))
            self.clear_attachments_btn.configure(state="disabled")
            return

        names = [item.get("file_name", "file") for item in attachments]
        short_names = ", ".join(names[:3])
        if len(names) > 3:
            short_names += f" +{len(names) - 3}"

        self.attachments_lbl.configure(
            text=self.tr(
                "chat_attachments_selected",
                count=len(attachments),
                names=short_names,
            )
        )
        if str(self.input_box.cget("state")) != "disabled":
            self.clear_attachments_btn.configure(state="normal")

    def _scroll_bottom(self):
        self.display.after(50, lambda: self.display._parent_canvas.yview_moveto(1.0))


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.cfg = cfg_module.load()
        self.i18n = i18n.Translator(self.cfg.get("language", "vi"))

        self.title(self.tr("app_title"))
        self.geometry(f"{APP_W}x{APP_H}")
        self.minsize(800, 500)

        self.conv = history.new_conversation()
        self.conv["title"] = self.tr("conversation_new")
        self._is_busy = False
        self._conversation_query = ""
        self._draft_save_job: str | None = None
        self._pending_attachments: list[dict] = []
        self._last_usage_summary: dict = {}

        self._build_layout()
        self._refresh_sidebar()
        self._update_meta()
        self._bind_shortcuts()
        self._refresh_usage_summary_async(silent=True)

    def tr(self, key: str, **kwargs) -> str:
        return self.i18n.t(key, **kwargs)

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
            tr=self.tr,
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

        self.title_lbl = ctk.CTkLabel(
            title_wrap, text=self.tr("app_title"), font=ctk.CTkFont(size=18, weight="bold")
        )
        self.title_lbl.pack(anchor="w")
        ctk.CTkLabel(
            title_wrap,
            text=self.tr("app_subtitle"),
            font=ctk.CTkFont(size=12),
            text_color=("gray35", "gray65"),
        ).pack(anchor="w")
        self.meta_lbl = ctk.CTkLabel(
            title_wrap,
            text=self.tr("meta_messages", count=0),
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray60"),
        )
        self.meta_lbl.pack(anchor="w")

        ctk.CTkButton(
            topbar,
            text=self.tr("top_export"),
            width=78,
            height=30,
            command=self._export_current_conversation,
        ).pack(side="right", padx=(0, 8))

        self.retry_btn = ctk.CTkButton(
            topbar,
            text=self.tr("top_retry"),
            width=78,
            height=30,
            state="disabled",
            command=self._retry_last_response,
        )
        self.retry_btn.pack(side="right", padx=(0, 8))

        ctk.CTkButton(
            topbar,
            text=self.tr("top_clear"),
            width=70,
            height=30,
            command=self._clear_current_messages,
        ).pack(side="right", padx=(0, 8))

        self.status_lbl = ctk.CTkLabel(
            topbar,
            text=self.tr("status_ready"),
            fg_color=("#d9f7e8", "#1e3b2f"),
            text_color=("#115a35", "#93f0c3"),
            corner_radius=8,
            padx=10,
            pady=5,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.status_lbl.pack(side="right", padx=(0, 10))

        self.usage_lbl = ctk.CTkLabel(
            topbar,
            text=self.tr("usage_badge_offline"),
            fg_color=("#ececec", "#2f2f2f"),
            text_color=("#444444", "#d8d8d8"),
            corner_radius=8,
            padx=8,
            pady=4,
            font=ctk.CTkFont(size=11),
        )
        self.usage_lbl.pack(side="right", padx=(0, 8))

        self.usage_progress = ctk.CTkProgressBar(topbar, width=90, height=8)
        self.usage_progress.pack(side="right", padx=(0, 8))
        self.usage_progress.set(0)

        ctk.CTkButton(
            topbar,
            text=self.tr("top_settings"),
            width=110,
            height=30,
            command=self._open_settings,
        ).pack(side="right", padx=(0, 10))

        # Chat area
        self.chat = ChatArea(
            right,
            on_send=self._on_user_send,
            on_message_action=self._on_message_action,
            on_input_change=self._on_draft_input_change,
            on_pick_attachment=self._pick_attachments,
            on_clear_attachments=self._clear_pending_attachments,
            tr=self.tr,
        )
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
        self.status_lbl.configure(
            text=text, fg_color=style["fg_color"], text_color=style["text_color"]
        )

    def _refresh_usage_summary_async(self, silent: bool = True) -> None:
        if not self.cfg.get("use_backend_stream"):
            self.usage_lbl.configure(
                text=self.tr("usage_badge_local_mode"),
                fg_color=("#ececec", "#2f2f2f"),
                text_color=("#444444", "#d8d8d8"),
            )
            self.usage_progress.set(0)
            return

        backend_url = str(self.cfg.get("backend_api_url", "")).strip().rstrip("/")
        token = str(self.cfg.get("backend_access_token", "")).strip()
        if not backend_url or not token:
            self.usage_lbl.configure(
                text=self.tr("usage_badge_offline"),
                fg_color=("#ececec", "#2f2f2f"),
                text_color=("#444444", "#d8d8d8"),
            )
            self.usage_progress.set(0)
            return

        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        def worker() -> None:
            try:
                response = requests.get(
                    f"{backend_url}/api/v1/usage/me",
                    headers=headers,
                    timeout=15,
                )
                if response.status_code >= 400:
                    raise RuntimeError(response.text.strip() or f"HTTP {response.status_code}")
                payload = response.json()
            except Exception as exc:  # noqa: BLE001
                error_text = str(exc)
                if not silent:
                    self.after(
                        0,
                        lambda message=error_text: self._set_status(
                            f"{self.tr('status_error')}: {message}",
                            "error",
                        ),
                    )
                return

            self.after(0, lambda: self._apply_usage_summary(payload))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_usage_summary(self, payload: dict) -> None:
        self._last_usage_summary = dict(payload)

        ratio = float(payload.get("message_ratio", 0.0) or 0.0)
        used = int(payload.get("messages_used", 0) or 0)
        limit = int(payload.get("message_limit", 0) or 0)
        percent = round(ratio * 100, 1)
        alert_level = str(payload.get("alert_level", "ok"))

        self.usage_progress.set(max(0.0, min(1.0, ratio)))
        self.usage_lbl.configure(
            text=self.tr("usage_badge_fmt", used=used, limit=limit, percent=percent),
        )

        if alert_level == "exceeded":
            self.usage_lbl.configure(
                fg_color=("#ffdcdc", "#4f2424"),
                text_color=("#8a1d1d", "#ff9b9b"),
            )
            self._set_status(self.tr("usage_badge_exceeded"), "error")
        elif alert_level == "warning":
            self.usage_lbl.configure(
                fg_color=("#ffe7cc", "#4f3720"),
                text_color=("#8a4d00", "#ffbf75"),
            )
            self._set_status(self.tr("usage_badge_warning"), "busy")
        else:
            self.usage_lbl.configure(
                fg_color=("#d9f7e8", "#1e3b2f"),
                text_color=("#115a35", "#93f0c3"),
            )

    # ─── Sidebar actions ─────────────────────────────────────────────────────
    def _refresh_sidebar(self):
        convos = history.list_conversations()
        if self._conversation_query:
            needle = self._conversation_query.lower()
            convos = [c for c in convos if needle in c.get("title", "").lower()]
        self.sidebar.refresh(convos, active_id=self.conv.get("id"))

    def _on_sidebar_search(self, query: str):
        self._conversation_query = query
        self._refresh_sidebar()

    def _new_conversation(self):
        self.conv = history.new_conversation()
        self.conv["title"] = self.tr("conversation_new")
        self._clear_pending_attachments(set_status=False)
        self._render_conversation()
        self._restore_current_draft()
        self.title_lbl.configure(text=self.tr("app_title"))
        self._set_status(self.tr("status_ready"), "ready")
        self._update_meta()
        self._refresh_sidebar()
        self._sync_retry_button_state()

    def _load_conversation(self, conv_id: str):
        self.conv = history.load_conversation(conv_id)
        self._clear_pending_attachments(set_status=False)
        self._render_conversation()
        self._restore_current_draft()
        self.title_lbl.configure(text=self.conv.get("title", self.tr("app_title")))
        self._update_meta()
        self._refresh_sidebar()
        self._sync_retry_button_state()

    def _render_conversation(self) -> None:
        self.chat.clear()
        for index, msg in enumerate(self.conv.get("messages", [])):
            self.chat.add_message(msg["role"], msg["text"], message_index=index)

    def _delete_conversation(self, conv_id: str):
        if not msgbox.askyesno(
            self.tr("dialog_confirm_title"), self.tr("dialog_delete_conversation")
        ):
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
        if not text.strip() and not self._pending_attachments:
            return

        attached_items = [dict(item) for item in self._pending_attachments]
        user_text = self._compose_user_text_with_attachments(text, attached_items)
        if not user_text:
            return

        # Hiển thị tin nhắn người dùng
        self.conv["draft"] = ""
        self._clear_pending_attachments(set_status=False)
        self.chat.add_message("user", user_text, message_index=len(self.conv["messages"]))
        self.conv["messages"].append({"role": "user", "text": user_text})
        runtime_messages = self._build_runtime_messages(last_turn_attachments=attached_items)
        self._update_meta()

        # Cập nhật tiêu đề nếu là tin đầu
        if len(self.conv["messages"]) == 1:
            title_seed = text.strip()
            if not title_seed and attached_items:
                title_seed = attached_items[0].get("file_name", self.tr("conversation_new"))
            title = history.generate_title(title_seed)
            self.conv["title"] = title
            self.title_lbl.configure(text=title)

        history.save_conversation(self.conv)
        self._refresh_sidebar()

        self._request_assistant_reply(
            status_key="status_generating",
            runtime_messages=runtime_messages,
        )

    def _compose_user_text_with_attachments(self, text: str, attachments: list[dict]) -> str:
        clean_text = text.strip()
        if not clean_text and not attachments:
            return ""

        base_text = clean_text or self.tr("chat_attachment_only_message")
        if not attachments:
            return base_text

        lines = [base_text, "", self.tr("chat_attachment_context_header")]
        for index, item in enumerate(attachments, start=1):
            file_name = item.get("file_name", "file")
            content_type = item.get("content_type", "application/octet-stream")
            size_bytes = int(item.get("size_bytes", 0) or 0)
            lines.append(
                self.tr(
                    "chat_attachment_context_item",
                    index=index,
                    name=file_name,
                    content_type=content_type,
                    size=size_bytes,
                )
            )
            preview_text = str(item.get("preview_text", "")).strip()
            if preview_text:
                lines.append(self.tr("chat_attachment_context_preview"))
                lines.append(preview_text)

        return "\n".join(lines).strip()

    def _build_runtime_messages(self, last_turn_attachments: list[dict] | None = None) -> list[dict]:
        payload = [
            {
                "role": item.get("role", "user"),
                "text": item.get("text", ""),
            }
            for item in self.conv.get("messages", [])
        ]

        if not last_turn_attachments or not payload:
            return payload

        if payload[-1].get("role") != "user":
            return payload

        runtime_attachments = []
        for attachment in last_turn_attachments:
            serialized = self._to_runtime_attachment_payload(attachment)
            if serialized is not None:
                runtime_attachments.append(serialized)

        if runtime_attachments:
            payload[-1]["attachments"] = runtime_attachments

        return payload

    def _to_runtime_attachment_payload(self, attachment: dict) -> dict | None:
        content_type = str(attachment.get("content_type", "")).strip().lower()
        image_base64 = str(attachment.get("image_base64", "")).strip()
        if not content_type.startswith("image/"):
            return None
        if not image_base64:
            return None

        return {
            "file_name": str(attachment.get("file_name", "image")),
            "content_type": content_type,
            "data_base64": image_base64,
        }

    def _request_assistant_reply(
        self,
        status_key: str = "status_generating",
        runtime_messages: list[dict] | None = None,
    ) -> None:
        if self._is_busy:
            return

        self._is_busy = True
        self.chat.set_input_enabled(False)
        self._set_status(self.tr(status_key), "busy")
        self._sync_retry_button_state()

        messages_payload = runtime_messages or self._build_runtime_messages()

        # Bắt đầu bubble streaming
        self.chat.start_streaming_bubble()

        if self.cfg.get("use_backend_stream"):
            runtime_cfg = dict(self.cfg)
            runtime_cfg["_backend_conversation_id"] = self.conv.get("server_conversation_id")
            runtime_cfg["_backend_conversation_title"] = self.conv.get(
                "title", self.tr("conversation_new")
            )

            backend_chat.send_message(
                messages=messages_payload,
                cfg=runtime_cfg,
                on_chunk=self._on_chunk,
                on_done=lambda text: self._on_done_backend(text, runtime_cfg),
                on_error=self._on_error,
            )
            return

        gemini.send_message(
            messages=messages_payload,
            cfg=self.cfg,
            on_chunk=self._on_chunk,
            on_done=self._on_done,
            on_error=self._on_error,
        )

    def _on_done_backend(self, full_text: str, runtime_cfg: dict):
        server_conversation_id = runtime_cfg.get("_backend_last_conversation_id")
        if server_conversation_id is not None:
            self.conv["server_conversation_id"] = server_conversation_id

        user_message_id = runtime_cfg.get("_backend_last_user_message_id")
        if user_message_id is not None:
            user_index = self._find_last_role_index("user")
            if user_index is not None:
                self.conv["messages"][user_index]["server_message_id"] = user_message_id

        citations = runtime_cfg.get("_backend_last_citations")
        if isinstance(citations, list) and citations:
            full_text = self._append_citations_to_response(full_text, citations)

        assistant_message_id = runtime_cfg.get("_backend_last_assistant_message_id")
        self._on_done(full_text, assistant_message_id=assistant_message_id)

    def _append_citations_to_response(self, full_text: str, citations: list[dict]) -> str:
        lines = [full_text.strip(), "", self.tr("chat_citations_header")]
        for index, item in enumerate(citations, start=1):
            title = str(item.get("title", "")).strip() or self.tr("chat_citation_untitled")
            url = str(item.get("url", "")).strip() or "-"
            snippet = str(item.get("snippet", "")).strip()
            lines.append(self.tr("chat_citation_line", index=index, title=title, url=url))
            if snippet:
                lines.append(self.tr("chat_citation_snippet", snippet=snippet))
        return "\n".join(lines).strip()

    def _on_chunk(self, chunk: str):
        self.after(0, lambda: self.chat.append_stream(chunk))

    def _on_done(self, full_text: str, assistant_message_id: int | None = None):
        assistant_message = {"role": "assistant", "text": full_text}
        if assistant_message_id is not None:
            assistant_message["server_message_id"] = assistant_message_id

        self.conv["messages"].append(assistant_message)
        self.chat.finalize_streaming_message(len(self.conv["messages"]) - 1)
        history.save_conversation(self.conv)
        self._update_meta()
        self.after(0, self._after_response)

    def _on_error(self, err: str):
        def _show():
            self.chat.append_stream(f"\n❌ {self.tr('chat_error_prefix')}: {err}")
            self._set_status(self.tr("status_error"), "error")
            self._after_response()

        self.after(0, _show)

    def _after_response(self):
        self._is_busy = False
        self.chat.set_input_enabled(True)
        if self.status_lbl.cget("text") != self.tr("status_error"):
            self._set_status(self.tr("status_ready"), "ready")
        self._refresh_sidebar()
        self._sync_retry_button_state()
        self._refresh_usage_summary_async(silent=True)

    def _sync_retry_button_state(self) -> None:
        can_retry = (not self._is_busy) and bool(self.conv.get("messages"))
        if can_retry:
            can_retry = self.conv["messages"][-1].get("role") == "user"
        self.retry_btn.configure(state="normal" if can_retry else "disabled")

    def _trim_and_regenerate(
        self,
        keep_until_index: int,
        rebase_cutoff_index: int,
        status_key: str,
    ) -> None:
        self.conv["messages"] = self.conv["messages"][: keep_until_index + 1]
        self._rebase_server_conversation(rebase_cutoff_index)
        self._render_conversation()
        self._update_meta()
        history.save_conversation(self.conv)
        self._request_assistant_reply(status_key=status_key)

    def _retry_last_response(self):
        if self._is_busy:
            return

        last_user_index = self._find_last_role_index("user")
        if last_user_index is None or last_user_index != len(self.conv.get("messages", [])) - 1:
            msgbox.showinfo(self.tr("dialog_notice_title"), self.tr("dialog_no_pending_retry"))
            return

        self._trim_and_regenerate(
            keep_until_index=last_user_index,
            rebase_cutoff_index=last_user_index - 1,
            status_key="status_retrying",
        )

    def _on_draft_input_change(self, text: str) -> None:
        if self._is_busy:
            return
        self.conv["draft"] = text
        self._schedule_draft_save()

    def _restore_current_draft(self) -> None:
        self.chat.set_input_text(self.conv.get("draft", ""), notify=False)

    def _schedule_draft_save(self) -> None:
        conversation_ref = self.conv
        if self._draft_save_job is not None:
            try:
                self.after_cancel(self._draft_save_job)
            except Exception:
                pass
        self._draft_save_job = self.after(
            350,
            lambda ref=conversation_ref: self._flush_draft_save(ref),
        )

    def _flush_draft_save(self, conversation_ref: dict) -> None:
        self._draft_save_job = None
        history.save_conversation(conversation_ref)
        if conversation_ref is self.conv:
            self._refresh_sidebar()

    def _pick_attachments(self) -> None:
        if self._is_busy:
            return

        selected_paths = filedialog.askopenfilenames(
            title=self.tr("dialog_pick_attachments_title"),
            filetypes=[
                (self.tr("dialog_supported_files"), "*.txt *.md *.json *.csv *.xml *.yml *.yaml *.log *.py *.js *.ts *.html *.css *.png *.jpg *.jpeg *.webp *.gif *.bmp *.pdf"),
                (self.tr("dialog_all_files"), "*.*"),
            ],
        )
        if not selected_paths:
            return

        added_count = 0
        for file_path in selected_paths:
            attachment = self._prepare_attachment(file_path)
            if attachment is None:
                continue
            self._pending_attachments.append(attachment)
            added_count += 1

        self.chat.set_pending_attachments(self._pending_attachments)
        if added_count:
            self._set_status(self.tr("status_attachments_added", count=added_count), "ready")

    def _prepare_attachment(self, file_path: str) -> dict | None:
        try:
            if self.cfg.get("use_backend_stream"):
                return self._upload_attachment_backend(file_path)
            return self._build_local_attachment(file_path)
        except Exception as exc:
            msgbox.showwarning(
                self.tr("dialog_notice_title"),
                self.tr("dialog_attachment_prepare_failed", path=file_path, error=str(exc)),
            )
            return None

    def _upload_attachment_backend(self, file_path: str) -> dict:
        backend_url = str(self.cfg.get("backend_api_url", "")).strip().rstrip("/")
        if not backend_url:
            raise RuntimeError(self.tr("dialog_backend_url_missing"))

        token = str(self.cfg.get("backend_access_token", "")).strip()
        if not token:
            raise RuntimeError(self.tr("dialog_backend_token_missing"))

        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise RuntimeError(self.tr("dialog_attachment_file_not_found"))

        guessed_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as file_obj:
            response = requests.post(
                f"{backend_url}/api/v1/files/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": (path.name, file_obj, guessed_type)},
                timeout=30,
            )

        if response.status_code >= 400:
            detail = response.text.strip() or f"HTTP {response.status_code}"
            raise RuntimeError(detail)

        payload = response.json()
        preview_text = str(payload.get("preview_text") or "").strip()
        if len(preview_text) > ATTACHMENT_PREVIEW_CHARS:
            preview_text = preview_text[:ATTACHMENT_PREVIEW_CHARS] + "\n...[truncated]"

        image_base64 = self._encode_inline_image_base64(path, guessed_type)

        return {
            "file_name": payload.get("file_name") or path.name,
            "content_type": payload.get("content_type") or guessed_type,
            "size_bytes": int(payload.get("size_bytes") or 0),
            "preview_text": preview_text,
            "image_base64": image_base64,
        }

    def _build_local_attachment(self, file_path: str) -> dict:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise RuntimeError(self.tr("dialog_attachment_file_not_found"))

        size_bytes = path.stat().st_size
        if size_bytes > ATTACHMENT_MAX_BYTES:
            raise RuntimeError(self.tr("dialog_attachment_too_large"))

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        preview_text = ""
        if self._is_text_attachment(content_type, path.suffix.lower()):
            preview_text = self._extract_local_preview(path)

        image_base64 = self._encode_inline_image_base64(path, content_type)

        return {
            "file_name": path.name,
            "content_type": content_type,
            "size_bytes": size_bytes,
            "preview_text": preview_text,
            "image_base64": image_base64,
        }

    def _encode_inline_image_base64(self, path: Path, content_type: str) -> str:
        if not content_type.startswith("image/"):
            return ""

        raw = path.read_bytes()
        if len(raw) > ATTACHMENT_MAX_BYTES:
            raise RuntimeError(self.tr("dialog_attachment_too_large"))

        return base64.b64encode(raw).decode("ascii")

    def _is_text_attachment(self, content_type: str, suffix: str) -> bool:
        if content_type.startswith("text/"):
            return True
        if content_type in {"application/json", "application/xml"}:
            return True
        return suffix in LOCAL_TEXT_ATTACHMENT_EXTENSIONS

    def _extract_local_preview(self, path: Path) -> str:
        with path.open("rb") as file_obj:
            raw = file_obj.read(ATTACHMENT_PREVIEW_CHARS * 3)
        text = raw.decode("utf-8", errors="replace").strip()
        if len(text) > ATTACHMENT_PREVIEW_CHARS:
            text = text[:ATTACHMENT_PREVIEW_CHARS] + "\n...[truncated]"
        return text

    def _clear_pending_attachments(self, set_status: bool = True) -> None:
        self._pending_attachments = []
        self.chat.set_pending_attachments([])
        if set_status:
            self._set_status(self.tr("status_attachments_cleared"), "ready")

    def _on_message_action(self, action: str, message_index: int) -> None:
        if self._is_busy:
            return
        if message_index < 0 or message_index >= len(self.conv.get("messages", [])):
            return

        if action == "edit":
            self._edit_message(message_index)
        elif action == "regenerate":
            self._regenerate_from_message(message_index)
        elif action == "branch":
            self._branch_from_message(message_index)

    def _find_last_role_index(self, role: str) -> int | None:
        for idx in range(len(self.conv.get("messages", [])) - 1, -1, -1):
            if self.conv["messages"][idx].get("role") == role:
                return idx
        return None

    def _find_previous_user_index(self, start_index: int) -> int | None:
        for idx in range(start_index, -1, -1):
            if self.conv["messages"][idx].get("role") == "user":
                return idx
        return None

    def _message_server_id(self, index: int) -> int | None:
        value = self.conv["messages"][index].get("server_message_id")
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _clear_server_message_ids(self) -> None:
        for msg in self.conv.get("messages", []):
            msg.pop("server_message_id", None)

    def _clone_current_messages_until(self, message_index: int) -> list[dict]:
        return [dict(item) for item in self.conv.get("messages", [])[: message_index + 1]]

    def _request_backend_branch(self, from_message_id: int | None) -> tuple[int | None, str | None]:
        if not self.cfg.get("use_backend_stream"):
            return None, None

        source_server_conversation_id = self.conv.get("server_conversation_id")
        backend_url = str(self.cfg.get("backend_api_url", "")).strip().rstrip("/")
        if source_server_conversation_id is None or not backend_url:
            return None, None

        headers = {"Accept": "application/json"}
        token = str(self.cfg.get("backend_access_token", "")).strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        params = {}
        if from_message_id is not None:
            params["from_message_id"] = from_message_id

        try:
            response = requests.post(
                f"{backend_url}/api/v1/conversations/{source_server_conversation_id}/branch",
                headers=headers,
                params=params,
                timeout=20,
            )
            if response.status_code >= 400:
                detail = response.text.strip() or f"HTTP {response.status_code}"
                raise RuntimeError(detail)

            payload = response.json()
            branch_id = int(payload["id"])
            branch_title = str(payload.get("title", "")).strip() or None
            return branch_id, branch_title
        except Exception as exc:
            msgbox.showwarning(
                self.tr("dialog_notice_title"),
                f"{self.tr('dialog_backend_branch_failed')}\n{exc}",
            )
            return None, None

    def _rebase_server_conversation(self, cutoff_index: int | None) -> None:
        if not self.cfg.get("use_backend_stream") or self.conv.get("server_conversation_id") is None:
            return

        from_message_id = None
        if cutoff_index is not None and cutoff_index >= 0:
            from_message_id = self._message_server_id(cutoff_index)
            if from_message_id is None:
                self.conv.pop("server_conversation_id", None)
                self._clear_server_message_ids()
                return

        new_server_conversation_id, _ = self._request_backend_branch(from_message_id)
        if new_server_conversation_id is not None:
            self.conv["server_conversation_id"] = new_server_conversation_id
        else:
            self.conv.pop("server_conversation_id", None)
        self._clear_server_message_ids()

    def _edit_message(self, message_index: int) -> None:
        message = self.conv["messages"][message_index]
        if message.get("role") != "user":
            return

        new_text = simpledialog.askstring(
            self.tr("dialog_edit_message_title"),
            self.tr("dialog_edit_message_prompt"),
            initialvalue=message.get("text", ""),
            parent=self,
        )
        if new_text is None:
            return

        new_text = new_text.strip()
        if not new_text:
            return
        if new_text == message.get("text", ""):
            return

        self.conv["messages"][message_index]["text"] = new_text
        self._trim_and_regenerate(
            keep_until_index=message_index,
            rebase_cutoff_index=message_index - 1,
            status_key="status_regenerating",
        )

    def _regenerate_from_message(self, message_index: int) -> None:
        user_index = self._find_previous_user_index(message_index)
        if user_index is None:
            msgbox.showinfo(self.tr("dialog_notice_title"), self.tr("dialog_no_user_message"))
            return

        # Rebase tới message trước user cuối để backend không lưu trùng user message.
        self._trim_and_regenerate(
            keep_until_index=user_index,
            rebase_cutoff_index=user_index - 1,
            status_key="status_regenerating",
        )

    def _branch_from_message(self, message_index: int) -> None:
        source_messages = self._clone_current_messages_until(message_index)
        if not source_messages:
            return

        branch_server_id = None
        branch_title = None
        selected_server_message_id = self._message_server_id(message_index)
        if self.cfg.get("use_backend_stream") and selected_server_message_id is not None:
            branch_server_id, branch_title = self._request_backend_branch(selected_server_message_id)

        local_branch = history.new_conversation()
        local_branch["title"] = branch_title or f"{self.conv.get('title', self.tr('conversation_new'))} (branch)"
        local_branch["messages"] = source_messages
        for item in local_branch["messages"]:
            item.pop("server_message_id", None)
        if branch_server_id is not None:
            local_branch["server_conversation_id"] = branch_server_id

        history.save_conversation(local_branch)
        self.conv = local_branch
        self._clear_pending_attachments(set_status=False)
        self.title_lbl.configure(text=self.conv.get("title", self.tr("app_title")))
        self._render_conversation()
        self._restore_current_draft()
        self._update_meta()
        self._refresh_sidebar()
        self._sync_retry_button_state()
        self._set_status(self.tr("status_branch_created"), "ready")

    def _update_meta(self):
        msg_count = len(self.conv.get("messages", []))
        updated_at = self.conv.get("updated_at") or self.conv.get("created_at") or ""
        if updated_at:
            self.meta_lbl.configure(
                text=self.tr(
                    "meta_messages_updated",
                    count=msg_count,
                    updated=updated_at[:16].replace("T", " "),
                )
            )
        else:
            self.meta_lbl.configure(text=self.tr("meta_messages", count=msg_count))

    def _clear_current_messages(self):
        if not self.conv.get("messages"):
            msgbox.showinfo(self.tr("dialog_notice_title"), self.tr("dialog_conversation_empty"))
            return
        if not msgbox.askyesno(
            self.tr("dialog_confirm_title"), self.tr("dialog_clear_conversation")
        ):
            return

        self.conv["messages"] = []
        self.conv["title"] = self.tr("conversation_new")
        self.conv.pop("server_conversation_id", None)
        self.conv["draft"] = ""
        self._clear_pending_attachments(set_status=False)
        self.chat.clear()
        self._restore_current_draft()
        self.title_lbl.configure(text=self.tr("app_title"))
        history.save_conversation(self.conv)
        self._update_meta()
        self._refresh_sidebar()
        self._sync_retry_button_state()
        self._set_status(self.tr("status_conversation_cleared"), "ready")

    def _safe_file_stem(self, value: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", " "} else "_" for ch in value)
        cleaned = " ".join(cleaned.split()).strip()
        return cleaned or self.tr("conversation_file_name")

    def _export_current_conversation(self):
        messages = self.conv.get("messages", [])
        if not messages:
            msgbox.showinfo(self.tr("dialog_notice_title"), self.tr("dialog_no_content_to_export"))
            return

        title = self.conv.get("title", self.tr("conversation_file_name"))
        default_name = f"{self._safe_file_stem(title)}.md"
        file_path = filedialog.asksaveasfilename(
            title=self.tr("export_dialog_title"),
            defaultextension=".md",
            initialfile=default_name,
            filetypes=[("Markdown", "*.md"), ("Text", "*.txt"), ("All files", "*.*")],
        )
        if not file_path:
            return

        lines = [
            f"# {title}",
            "",
            f"{self.tr('export_conversation_id')}: {self.conv.get('id', '-')}",
            "",
        ]
        for item in messages:
            role = (
                self.tr("export_role_user")
                if item.get("role") == "user"
                else self.tr("export_role_assistant")
            )
            lines.append(f"## {role}")
            lines.append(item.get("text", ""))
            lines.append("")

        output = "\n".join(lines).strip() + "\n"
        Path(file_path).write_text(output, encoding="utf-8")
        self._set_status(self.tr("status_conversation_exported"), "ready")
        msgbox.showinfo(
            self.tr("export_done_title"), self.tr("export_done_message", path=file_path)
        )

    def _bind_shortcuts(self):
        self.bind("<Control-n>", self._shortcut_new_conversation)
        self.bind("<Control-e>", self._shortcut_export)
        self.bind("<Control-k>", self._shortcut_focus_search)
        self.bind("<Control-r>", self._shortcut_retry)
        self.bind("<Control-o>", self._shortcut_attach)

    def _shortcut_new_conversation(self, _event=None):
        self._new_conversation()
        return "break"

    def _shortcut_export(self, _event=None):
        self._export_current_conversation()
        return "break"

    def _shortcut_focus_search(self, _event=None):
        self.sidebar.search_entry.focus_set()
        return "break"

    def _shortcut_retry(self, _event=None):
        self._retry_last_response()
        return "break"

    def _shortcut_attach(self, _event=None):
        self._pick_attachments()
        return "break"

    # ─── Settings ────────────────────────────────────────────────────────────
    def _open_settings(self):
        def _save(new_cfg):
            previous_lang = self.cfg.get("language", "vi")
            self.cfg = new_cfg
            cfg_module.save(new_cfg)
            gemini.reset_client()  # reset client khi model/key thay đổi
            self.i18n.set_language(self.cfg.get("language", "vi"))
            self._set_status(self.tr("status_model", model=self.cfg["model"]), "ready")
            self._refresh_usage_summary_async(silent=True)

            if previous_lang != self.cfg.get("language", "vi"):
                msgbox.showinfo(
                    self.tr("settings_dialog_title"), self.tr("settings_restart_required")
                )

        SettingsDialog(self, self.cfg, on_save=_save, tr=self.tr)


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
