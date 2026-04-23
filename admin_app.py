"""Standalone admin desktop app for user management."""

from __future__ import annotations

import csv
import json
import re
import threading
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as msgbox

import customtkinter as ctk
import requests

import core.config as cfg_module
import core.i18n as i18n

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ApiClient:
    def __init__(self) -> None:
        self.base_url = "http://127.0.0.1:8080"
        self.token: str | None = None

    def configure(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @staticmethod
    def _error_text(resp: requests.Response) -> str:
        try:
            payload = resp.json()
        except json.JSONDecodeError:
            return resp.text or f"HTTP {resp.status_code}"

        detail = payload.get("detail") if isinstance(payload, dict) else None
        if isinstance(detail, list):
            return "; ".join(
                str(item.get("msg", item)) if isinstance(item, dict) else str(item)
                for item in detail
            )
        if detail:
            return str(detail)
        return resp.text or f"HTTP {resp.status_code}"

    def login(self, email: str, password: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/api/v1/auth/login",
            data={"username": email, "password": password},
            timeout=20,
        )
        if resp.status_code >= 400:
            raise ValueError(self._error_text(resp))
        payload = resp.json()
        self.token = payload["access_token"]
        return payload

    def check_health(self) -> dict:
        resp = requests.get(f"{self.base_url}/api/v1/health/ready", timeout=20)
        if resp.status_code >= 400:
            raise ValueError(self._error_text(resp))
        return resp.json()

    def get_stats(self) -> dict:
        resp = requests.get(
            f"{self.base_url}/api/v1/users/stats",
            headers=self._headers(),
            timeout=20,
        )
        if resp.status_code >= 400:
            raise ValueError(self._error_text(resp))
        return resp.json()

    def list_users(self, page: int, page_size: int, search: str) -> dict:
        resp = requests.get(
            f"{self.base_url}/api/v1/users",
            params={"page": page, "page_size": page_size, "search": search},
            headers=self._headers(),
            timeout=20,
        )
        if resp.status_code >= 400:
            raise ValueError(self._error_text(resp))
        return resp.json()

    def create_user(self, payload: dict) -> dict:
        resp = requests.post(
            f"{self.base_url}/api/v1/users",
            json=payload,
            headers=self._headers(),
            timeout=20,
        )
        if resp.status_code >= 400:
            raise ValueError(self._error_text(resp))
        return resp.json()

    def update_user(self, user_id: int, payload: dict) -> dict:
        resp = requests.patch(
            f"{self.base_url}/api/v1/users/{user_id}",
            json=payload,
            headers=self._headers(),
            timeout=20,
        )
        if resp.status_code >= 400:
            raise ValueError(self._error_text(resp))
        return resp.json()

    def reset_password(self, user_id: int, new_password: str) -> dict:
        resp = requests.patch(
            f"{self.base_url}/api/v1/users/{user_id}/password",
            json={"new_password": new_password},
            headers=self._headers(),
            timeout=20,
        )
        if resp.status_code >= 400:
            raise ValueError(self._error_text(resp))
        return resp.json()

    def update_status(self, user_id: int, is_active: bool) -> dict:
        resp = requests.patch(
            f"{self.base_url}/api/v1/users/{user_id}/status",
            json={"is_active": is_active},
            headers=self._headers(),
            timeout=20,
        )
        if resp.status_code >= 400:
            raise ValueError(self._error_text(resp))
        return resp.json()

    def delete_user(self, user_id: int) -> None:
        resp = requests.delete(
            f"{self.base_url}/api/v1/users/{user_id}",
            headers=self._headers(),
            timeout=20,
        )
        if resp.status_code >= 400:
            raise ValueError(self._error_text(resp))


class AdminApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.cfg = cfg_module.load()
        self.i18n = i18n.Translator(self.cfg.get("language", "vi"))

        self.title(self.tr("admin_title"))
        self.geometry("1320x820")
        self.minsize(1080, 680)

        self.client = ApiClient()
        self.page = 1
        self.page_size = 15
        self._total_users = 0
        self._total_pages = 1
        self._busy = False
        self._logged_in = False
        self._users_by_id: dict[int, dict] = {}
        self._protected_widgets: list[object] = []

        self._build_ui()
        self._set_logged_in(False)
        self._set_feedback(self.tr("admin_noop_when_logged_out"), "info")
        self._bind_shortcuts()

    def tr(self, key: str, **kwargs) -> str:
        return self.i18n.t(key, **kwargs)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self, corner_radius=14)
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        top.grid_columnconfigure(0, weight=1)

        title_wrap = ctk.CTkFrame(top, fg_color="transparent")
        title_wrap.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))
        ctk.CTkLabel(
            title_wrap,
            text=self.tr("admin_header_title"),
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_wrap,
            text=self.tr("admin_header_subtitle"),
            text_color=("gray30", "gray70"),
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w")

        auth = ctk.CTkFrame(top, fg_color="transparent")
        auth.grid(row=1, column=0, sticky="ew", padx=12, pady=(4, 12))

        self.backend_url_var = ctk.StringVar(value="http://127.0.0.1:8080")
        self.email_var = ctk.StringVar(value="admin@aiassist.app")
        self.password_var = ctk.StringVar(value="")

        ctk.CTkLabel(auth, text=self.tr("admin_backend_url")).pack(side="left", padx=(0, 6))
        self.backend_entry = ctk.CTkEntry(auth, textvariable=self.backend_url_var, width=220)
        self.backend_entry.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(auth, text=self.tr("admin_email")).pack(side="left", padx=(0, 6))
        self.email_entry = ctk.CTkEntry(auth, textvariable=self.email_var, width=220)
        self.email_entry.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(auth, text=self.tr("admin_password")).pack(side="left", padx=(0, 6))
        self.password_entry = ctk.CTkEntry(auth, textvariable=self.password_var, width=180, show="*")
        self.password_entry.pack(side="left", padx=(0, 10))
        self.password_entry.bind("<Return>", lambda _: self._login())

        self.login_btn = ctk.CTkButton(auth, text=self.tr("admin_sign_in"), width=100, command=self._login)
        self.login_btn.pack(side="left", padx=(0, 10))

        self.logout_btn = ctk.CTkButton(auth, text=self.tr("admin_logout"), width=90, command=self._logout)
        self.logout_btn.pack(side="left", padx=(0, 8))

        self.export_btn = ctk.CTkButton(auth, text=self.tr("admin_export_csv"), width=110, command=self._export_users_csv)
        self.export_btn.pack(side="left", padx=(0, 10))

        self.auth_status_lbl = ctk.CTkLabel(
            auth,
            text=self.tr("admin_not_authenticated"),
            fg_color=("#fff1d6", "#4a3520"),
            text_color=("#8a5a00", "#ffd18c"),
            corner_radius=8,
            padx=10,
            pady=4,
        )
        self.auth_status_lbl.pack(side="left", padx=(0, 8))

        self.health_status_lbl = ctk.CTkLabel(
            auth,
            text=self.tr("admin_backend_unknown"),
            fg_color=("#ececec", "#2f2f2f"),
            text_color=("#444444", "#d8d8d8"),
            corner_radius=8,
            padx=10,
            pady=4,
        )
        self.health_status_lbl.pack(side="left")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 8))
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, corner_radius=14)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(2, weight=1)

        stat_row = ctk.CTkFrame(left, fg_color="transparent")
        stat_row.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        for col in range(4):
            stat_row.grid_columnconfigure(col, weight=1)

        self.stat_values: dict[str, ctk.CTkLabel] = {}
        self._build_stat_card(stat_row, 0, self.tr("admin_stat_total"), "total")
        self._build_stat_card(stat_row, 1, self.tr("admin_stat_active"), "active")
        self._build_stat_card(stat_row, 2, self.tr("admin_stat_inactive"), "inactive")
        self._build_stat_card(stat_row, 3, self.tr("admin_stat_admins"), "admins")

        toolbar = ctk.CTkFrame(left, fg_color="transparent")
        toolbar.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 6))

        self.search_var = ctk.StringVar(value="")
        self.search_entry = ctk.CTkEntry(
            toolbar,
            textvariable=self.search_var,
            width=280,
            placeholder_text=self.tr("admin_search_placeholder"),
        )
        self.search_entry.pack(side="left", padx=(0, 6))
        self.search_entry.bind("<Return>", lambda _: self._refresh_dashboard(reset_page=True))

        self.search_btn = ctk.CTkButton(
            toolbar,
            text=self.tr("admin_search"),
            width=80,
            command=lambda: self._refresh_dashboard(reset_page=True),
        )
        self.search_btn.pack(side="left", padx=(0, 6))

        self.refresh_btn = ctk.CTkButton(
            toolbar,
            text=self.tr("admin_refresh"),
            width=80,
            command=lambda: self._refresh_dashboard(reset_page=False),
        )
        self.refresh_btn.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(toolbar, text=self.tr("admin_page_size")).pack(side="left", padx=(0, 4))
        self.page_size_var = ctk.StringVar(value="15")
        self.page_size_menu = ctk.CTkOptionMenu(
            toolbar,
            variable=self.page_size_var,
            values=["10", "15", "20", "50"],
            width=70,
            command=self._on_page_size_change,
        )
        self.page_size_menu.pack(side="left", padx=(0, 10))

        self.prev_btn = ctk.CTkButton(toolbar, text=self.tr("admin_prev"), width=70, command=self._prev_page)
        self.prev_btn.pack(side="right", padx=(6, 0))
        self.next_btn = ctk.CTkButton(toolbar, text=self.tr("admin_next"), width=70, command=self._next_page)
        self.next_btn.pack(side="right")

        self.page_lbl = ctk.CTkLabel(left, text=self.tr("admin_page", page=1, total_pages=1, total=0, page_size=self.page_size))
        self.page_lbl.grid(row=3, column=0, sticky="w", padx=12, pady=(0, 8))

        self.user_box = ctk.CTkTextbox(left, wrap="none", corner_radius=10)
        self.user_box.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 6))
        self.user_box.insert("1.0", self.tr("admin_noop_when_logged_out") + "\n")
        self.user_box.configure(state="disabled")
        self.user_box.bind("<ButtonRelease-1>", self._on_user_click)

        right = ctk.CTkFrame(body, corner_radius=14)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1)

        tabs = ctk.CTkTabview(right)
        tabs.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        create_tab = tabs.add(self.tr("admin_tab_create"))
        update_tab = tabs.add(self.tr("admin_tab_update"))
        security_tab = tabs.add(self.tr("admin_tab_security"))
        actions_tab = tabs.add(self.tr("admin_tab_actions"))

        for tab in (create_tab, update_tab, security_tab, actions_tab):
            tab.grid_columnconfigure(0, weight=1)

        self._build_create_tab(create_tab)
        self._build_update_tab(update_tab)
        self._build_security_tab(security_tab)
        self._build_actions_tab(actions_tab)

        bottom = ctk.CTkFrame(self, corner_radius=10)
        bottom.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))

        self.feedback_lbl = ctk.CTkLabel(
            bottom,
            text=self.tr("admin_feedback_ready"),
            anchor="w",
            padx=12,
            pady=8,
        )
        self.feedback_lbl.pack(fill="x")

        self._protected_widgets = [
            self.logout_btn,
            self.export_btn,
            self.search_entry,
            self.search_btn,
            self.refresh_btn,
            self.page_size_menu,
            self.prev_btn,
            self.next_btn,
            self.create_email_entry,
            self.create_name_entry,
            self.create_password_entry,
            self.create_role_menu,
            self.create_active_switch,
            self.create_btn,
            self.update_id_entry,
            self.update_email_entry,
            self.update_name_entry,
            self.update_role_menu,
            self.update_active_switch,
            self.update_btn,
            self.reset_id_entry,
            self.reset_password_entry,
            self.reset_btn,
            self.action_id_entry,
            self.activate_btn,
            self.deactivate_btn,
            self.delete_btn,
        ]

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-r>", self._shortcut_refresh)

    def _shortcut_refresh(self, _event=None):
        self._refresh_dashboard(reset_page=False)
        return "break"

    def _build_stat_card(self, parent: ctk.CTkFrame, col: int, label: str, key: str) -> None:
        card = ctk.CTkFrame(parent, corner_radius=10)
        card.grid(row=0, column=col, sticky="ew", padx=4)
        ctk.CTkLabel(card, text=label, text_color=("gray35", "gray70"), font=ctk.CTkFont(size=12)).pack(
            anchor="w",
            padx=10,
            pady=(8, 2),
        )
        value = ctk.CTkLabel(card, text="0", font=ctk.CTkFont(size=22, weight="bold"))
        value.pack(anchor="w", padx=10, pady=(0, 8))
        self.stat_values[key] = value

    def _build_create_tab(self, parent: ctk.CTkFrame) -> None:
        self.create_email_var = ctk.StringVar()
        self.create_name_var = ctk.StringVar()
        self.create_password_var = ctk.StringVar()
        self.create_role_var = ctk.StringVar(value="user")
        self.create_active_var = tk.BooleanVar(value=True)

        ctk.CTkLabel(parent, text=self.tr("admin_create_title"), font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0,
            column=0,
            sticky="w",
            padx=12,
            pady=(12, 10),
        )

        ctk.CTkLabel(parent, text=self.tr("admin_field_email")).grid(row=1, column=0, sticky="w", padx=12)
        self.create_email_entry = ctk.CTkEntry(parent, textvariable=self.create_email_var)
        self.create_email_entry.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(parent, text=self.tr("admin_field_full_name")).grid(row=3, column=0, sticky="w", padx=12)
        self.create_name_entry = ctk.CTkEntry(parent, textvariable=self.create_name_var)
        self.create_name_entry.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(parent, text=self.tr("admin_field_password")).grid(row=5, column=0, sticky="w", padx=12)
        self.create_password_entry = ctk.CTkEntry(parent, textvariable=self.create_password_var, show="*")
        self.create_password_entry.grid(row=6, column=0, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(parent, text=self.tr("admin_field_role")).grid(row=7, column=0, sticky="w", padx=12)
        self.create_role_menu = ctk.CTkOptionMenu(parent, variable=self.create_role_var, values=["user", "admin"])
        self.create_role_menu.grid(row=8, column=0, sticky="ew", padx=12, pady=(0, 8))

        self.create_active_switch = ctk.CTkSwitch(
            parent,
            text=self.tr("admin_field_active_account"),
            variable=self.create_active_var,
            onvalue=True,
            offvalue=False,
        )
        self.create_active_switch.grid(row=9, column=0, sticky="w", padx=12, pady=(2, 12))

        self.create_btn = ctk.CTkButton(parent, text=self.tr("admin_create_button"), command=self._create_user)
        self.create_btn.grid(row=10, column=0, sticky="ew", padx=12, pady=(0, 12))

    def _build_update_tab(self, parent: ctk.CTkFrame) -> None:
        self.update_id_var = ctk.StringVar()
        self.update_email_var = ctk.StringVar()
        self.update_name_var = ctk.StringVar()
        self.update_role_var = ctk.StringVar(value="user")
        self.update_active_var = tk.BooleanVar(value=True)

        ctk.CTkLabel(parent, text=self.tr("admin_update_title"), font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0,
            column=0,
            sticky="w",
            padx=12,
            pady=(12, 10),
        )

        ctk.CTkLabel(parent, text=self.tr("admin_field_user_id")).grid(row=1, column=0, sticky="w", padx=12)
        self.update_id_entry = ctk.CTkEntry(
            parent,
            textvariable=self.update_id_var,
            placeholder_text=self.tr("admin_placeholder_user_id"),
        )
        self.update_id_entry.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(parent, text=self.tr("admin_field_email")).grid(row=3, column=0, sticky="w", padx=12)
        self.update_email_entry = ctk.CTkEntry(parent, textvariable=self.update_email_var)
        self.update_email_entry.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(parent, text=self.tr("admin_field_full_name")).grid(row=5, column=0, sticky="w", padx=12)
        self.update_name_entry = ctk.CTkEntry(parent, textvariable=self.update_name_var)
        self.update_name_entry.grid(row=6, column=0, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(parent, text=self.tr("admin_field_role")).grid(row=7, column=0, sticky="w", padx=12)
        self.update_role_menu = ctk.CTkOptionMenu(parent, variable=self.update_role_var, values=["user", "admin"])
        self.update_role_menu.grid(row=8, column=0, sticky="ew", padx=12, pady=(0, 8))

        self.update_active_switch = ctk.CTkSwitch(
            parent,
            text=self.tr("admin_field_active_account"),
            variable=self.update_active_var,
            onvalue=True,
            offvalue=False,
        )
        self.update_active_switch.grid(row=9, column=0, sticky="w", padx=12, pady=(2, 12))

        self.update_btn = ctk.CTkButton(parent, text=self.tr("admin_update_button"), command=self._update_user)
        self.update_btn.grid(row=10, column=0, sticky="ew", padx=12, pady=(0, 12))

    def _build_security_tab(self, parent: ctk.CTkFrame) -> None:
        self.reset_id_var = ctk.StringVar()
        self.reset_password_var = ctk.StringVar()

        ctk.CTkLabel(parent, text=self.tr("admin_reset_title"), font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0,
            column=0,
            sticky="w",
            padx=12,
            pady=(12, 10),
        )

        ctk.CTkLabel(parent, text=self.tr("admin_field_user_id")).grid(row=1, column=0, sticky="w", padx=12)
        self.reset_id_entry = ctk.CTkEntry(parent, textvariable=self.reset_id_var)
        self.reset_id_entry.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(parent, text=self.tr("admin_field_new_password")).grid(row=3, column=0, sticky="w", padx=12)
        self.reset_password_entry = ctk.CTkEntry(parent, textvariable=self.reset_password_var, show="*")
        self.reset_password_entry.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 12))

        self.reset_btn = ctk.CTkButton(parent, text=self.tr("admin_reset_button"), command=self._reset_password)
        self.reset_btn.grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 12))

    def _build_actions_tab(self, parent: ctk.CTkFrame) -> None:
        self.action_id_var = ctk.StringVar()

        ctk.CTkLabel(parent, text=self.tr("admin_actions_title"), font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0,
            column=0,
            sticky="w",
            padx=12,
            pady=(12, 10),
        )

        ctk.CTkLabel(parent, text=self.tr("admin_field_user_id")).grid(row=1, column=0, sticky="w", padx=12)
        self.action_id_entry = ctk.CTkEntry(parent, textvariable=self.action_id_var)
        self.action_id_entry.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))

        self.activate_btn = ctk.CTkButton(parent, text=self.tr("admin_activate"), command=lambda: self._change_status(True))
        self.activate_btn.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 6))

        self.deactivate_btn = ctk.CTkButton(parent, text=self.tr("admin_deactivate"), command=lambda: self._change_status(False))
        self.deactivate_btn.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 6))

        self.delete_btn = ctk.CTkButton(
            parent,
            text=self.tr("admin_delete"),
            fg_color="#8B0000",
            hover_color="#A40000",
            command=self._delete_user,
        )
        self.delete_btn.grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 12))

    def _set_feedback(self, message: str, tone: str) -> None:
        palette = {
            "info": (("#ececec", "#2f2f2f"), ("#444444", "#d8d8d8")),
            "busy": (("#fff1d6", "#4a3520"), ("#8a5a00", "#ffd18c")),
            "success": (("#d9f7e8", "#1e3b2f"), ("#115a35", "#93f0c3")),
            "error": (("#ffdcdc", "#4f2424"), ("#8a1d1d", "#ff9b9b")),
        }
        fg_color, text_color = palette.get(tone, palette["info"])
        self.feedback_lbl.configure(text=message, fg_color=fg_color, text_color=text_color)

    def _set_logged_in(self, logged_in: bool) -> None:
        self._logged_in = logged_in
        if not logged_in:
            self.client.token = None
            self.page = 1
            self._total_users = 0
            self._total_pages = 1
            self._users_by_id.clear()
            self.password_var.set("")
            self._render_users({"items": [], "total": 0, "page": 1, "page_size": self.page_size})
            self._render_stats({"total": 0, "active": 0, "inactive": 0, "admins": 0})
            self.auth_status_lbl.configure(
                text=self.tr("admin_not_authenticated"),
                fg_color=("#fff1d6", "#4a3520"),
                text_color=("#8a5a00", "#ffd18c"),
            )
            self.health_status_lbl.configure(
                text=self.tr("admin_backend_unknown"),
                fg_color=("#ececec", "#2f2f2f"),
                text_color=("#444444", "#d8d8d8"),
            )
        self._apply_control_state()
        self.login_btn.configure(text=self.tr("admin_relogin") if logged_in else self.tr("admin_sign_in"))

    def _apply_control_state(self) -> None:
        if self._logged_in and not self._busy:
            state = "normal"
        else:
            state = "disabled"

        for widget in self._protected_widgets:
            widget.configure(state=state)

        self.login_btn.configure(state="disabled" if self._busy else "normal")
        self.backend_entry.configure(state="disabled" if self._busy else "normal")
        self.email_entry.configure(state="disabled" if self._busy else "normal")
        self.password_entry.configure(state="disabled" if self._busy else "normal")
        self._sync_paging_controls()

    def _sync_paging_controls(self) -> None:
        if not self._logged_in or self._busy:
            self.prev_btn.configure(state="disabled")
            self.next_btn.configure(state="disabled")
            return

        self.prev_btn.configure(state="normal" if self.page > 1 else "disabled")
        self.next_btn.configure(state="normal" if self.page < self._total_pages else "disabled")

    def _run_bg(
        self,
        fn,
        on_success=None,
        success_message: str | None = None,
        busy_message: str | None = None,
    ) -> None:
        self._busy = True
        self._apply_control_state()
        self._set_feedback(busy_message or self.tr("admin_feedback_refreshing"), "busy")

        def done_success(result) -> None:
            self._busy = False
            self._apply_control_state()
            if on_success:
                on_success(result)
            if success_message:
                self._set_feedback(success_message, "success")

        def done_error(exc: Exception) -> None:
            self._busy = False
            self._apply_control_state()
            self._set_feedback(str(exc), "error")
            msgbox.showerror(self.tr("admin_error_title"), str(exc))

        def runner() -> None:
            try:
                result = fn()
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda: done_error(exc))
                return
            self.after(0, lambda: done_success(result))

        threading.Thread(target=runner, daemon=True).start()

    @staticmethod
    def _validate_email(value: str) -> bool:
        return bool(EMAIL_RE.match(value))

    def _resolve_user_id(self, raw: str) -> int | None:
        value = raw.strip()
        if not value.isdigit():
            return None
        return int(value)

    def _update_health_badge(self, health_payload: dict) -> None:
        status = health_payload.get("status", "unknown")
        cache_mode = health_payload.get("cache_mode", "-")
        if status == "ok":
            self.health_status_lbl.configure(
                text=self.tr("admin_health_ready", status=status, cache_mode=cache_mode),
                fg_color=("#d9f7e8", "#1e3b2f"),
                text_color=("#115a35", "#93f0c3"),
            )
        else:
            self.health_status_lbl.configure(
                text=self.tr("admin_health_bad", status=status),
                fg_color=("#ffdcdc", "#4f2424"),
                text_color=("#8a1d1d", "#ff9b9b"),
            )

    def _render_stats(self, payload: dict) -> None:
        self.stat_values["total"].configure(text=str(payload.get("total", 0)))
        self.stat_values["active"].configure(text=str(payload.get("active", 0)))
        self.stat_values["inactive"].configure(text=str(payload.get("inactive", 0)))
        self.stat_values["admins"].configure(text=str(payload.get("admins", 0)))

    def _render_users(self, payload: dict) -> None:
        self._total_users = max(0, int(payload.get("total", 0) or 0))
        self.page = max(1, int(payload.get("page", self.page) or 1))

        payload_page_size = int(payload.get("page_size", self.page_size) or self.page_size)
        self.page_size = payload_page_size if payload_page_size > 0 else self.page_size
        self.page_size_var.set(str(self.page_size))

        self._total_pages = max(1, (self._total_users + self.page_size - 1) // self.page_size)

        self.user_box.configure(state="normal")
        self.user_box.delete("1.0", "end")

        header = self.tr("admin_table_header")
        header += "-" * 92 + "\n"
        self.user_box.insert("1.0", header)

        self._users_by_id = {}
        for item in payload.get("items", []):
            self._users_by_id[item["id"]] = item
            line = (
                f"{item['id']:<4}"
                f"{item['email'][:32]:<34}"
                f"{item['role']:<8}"
                f"{(self.tr('admin_yes') if item['is_active'] else self.tr('admin_no')):<9}"
                f"{item['full_name']}\n"
            )
            self.user_box.insert("end", line)

        if not payload.get("items"):
            self.user_box.insert("end", self.tr("admin_users_empty") + "\n")

        self.user_box.configure(state="disabled")
        self.page_lbl.configure(
            text=self.tr(
                "admin_page",
                page=self.page,
                total_pages=self._total_pages,
                total=self._total_users,
                page_size=self.page_size,
            )
        )
        self._sync_paging_controls()

    def _populate_selected_user(self, user: dict) -> None:
        user_id = str(user["id"])
        self.update_id_var.set(user_id)
        self.update_email_var.set(user["email"])
        self.update_name_var.set(user["full_name"])
        self.update_role_var.set(user["role"])
        self.update_active_var.set(bool(user["is_active"]))

        self.reset_id_var.set(user_id)
        self.action_id_var.set(user_id)
        self._set_feedback(self.tr("admin_feedback_selected_user", user_id=user_id), "info")

    def _on_user_click(self, _: object) -> None:
        line = self.user_box.get("insert linestart", "insert lineend").strip()
        if not line or not line[0].isdigit():
            return

        parts = line.split()
        if not parts:
            return

        user_id = self._resolve_user_id(parts[0])
        if user_id is None:
            return

        user = self._users_by_id.get(user_id)
        if user:
            self._populate_selected_user(user)

    def _on_page_size_change(self, value: str) -> None:
        try:
            self.page_size = int(value)
        except ValueError:
            self.page_size = 15
            self.page_size_var.set("15")
        self._refresh_dashboard(reset_page=True)

    def _logout(self) -> None:
        if not self._logged_in:
            return
        self.search_var.set("")
        self._set_logged_in(False)
        self._set_feedback(self.tr("admin_feedback_signed_out"), "info")

    def _export_users_csv(self) -> None:
        if not self._logged_in:
            msgbox.showwarning(self.tr("admin_export_title"), self.tr("admin_export_login_first"))
            return
        if not self._users_by_id:
            msgbox.showinfo(self.tr("admin_export_title"), self.tr("admin_export_no_rows"))
            return

        file_path = filedialog.asksaveasfilename(
            title=self.tr("admin_export_dialog_title"),
            defaultextension=".csv",
            initialfile=f"users_page_{self.page}.csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if not file_path:
            return

        fieldnames = ["id", "email", "full_name", "role", "is_active", "created_at", "updated_at"]
        with open(file_path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for user_id in sorted(self._users_by_id):
                writer.writerow(self._users_by_id[user_id])

        self._set_feedback(self.tr("admin_export_done", path=file_path), "success")

    def _login(self) -> None:
        url = self.backend_url_var.get().strip()
        email = self.email_var.get().strip().lower()
        password = self.password_var.get()

        if not url or not email or not password:
            msgbox.showwarning(self.tr("admin_warning_title"), self.tr("admin_validation_login_required"))
            return
        if not self._validate_email(email):
            msgbox.showwarning(self.tr("admin_warning_title"), self.tr("admin_validation_invalid_admin_email"))
            return

        def job():
            self.client.configure(url)
            auth_payload = self.client.login(email, password)
            health_payload = self.client.check_health()
            users_payload = self.client.list_users(self.page, self.page_size, "")
            stats_payload = self.client.get_stats()
            return {
                "auth": auth_payload,
                "health": health_payload,
                "users": users_payload,
                "stats": stats_payload,
            }

        def success(payload: dict) -> None:
            admin_email = payload["auth"]["user"]["email"]
            self.auth_status_lbl.configure(
                text=self.tr("admin_authenticated_as", email=admin_email),
                fg_color=("#d9f7e8", "#1e3b2f"),
                text_color=("#115a35", "#93f0c3"),
            )
            self._set_logged_in(True)
            self._update_health_badge(payload["health"])
            self._render_users(payload["users"])
            self._render_stats(payload["stats"])

        self.page = 1
        self.search_var.set("")
        self._run_bg(
            fn=job,
            on_success=success,
            success_message=self.tr("admin_feedback_signed_in"),
            busy_message=self.tr("admin_feedback_signing_in"),
        )

    def _refresh_dashboard(self, reset_page: bool) -> None:
        if not self._logged_in:
            return
        if reset_page:
            self.page = 1

        search = self.search_var.get().strip()

        def job():
            users_payload = self.client.list_users(self.page, self.page_size, search)
            stats_payload = self.client.get_stats()
            health_payload = self.client.check_health()
            return {
                "users": users_payload,
                "stats": stats_payload,
                "health": health_payload,
            }

        def success(payload: dict) -> None:
            self._render_users(payload["users"])
            self._render_stats(payload["stats"])
            self._update_health_badge(payload["health"])

        self._run_bg(
            fn=job,
            on_success=success,
            success_message=self.tr("admin_feedback_dashboard_updated"),
            busy_message=self.tr("admin_feedback_refreshing"),
        )

    def _next_page(self) -> None:
        if self.page >= self._total_pages:
            self._set_feedback(self.tr("admin_feedback_last_page"), "info")
            return
        self.page += 1
        self._refresh_dashboard(reset_page=False)

    def _prev_page(self) -> None:
        if self.page <= 1:
            self._set_feedback(self.tr("admin_feedback_first_page"), "info")
            return
        self.page = max(1, self.page - 1)
        self._refresh_dashboard(reset_page=False)

    def _create_user(self) -> None:
        email = self.create_email_var.get().strip().lower()
        full_name = self.create_name_var.get().strip()
        password = self.create_password_var.get()

        if not email or not full_name or not password:
            msgbox.showwarning(self.tr("admin_warning_title"), self.tr("admin_validation_email_name_password_required"))
            return
        if not self._validate_email(email):
            msgbox.showwarning(self.tr("admin_warning_title"), self.tr("admin_validation_invalid_email"))
            return
        if len(password) < 8:
            msgbox.showwarning(self.tr("admin_warning_title"), self.tr("admin_validation_password_length"))
            return

        payload = {
            "email": email,
            "full_name": full_name,
            "password": password,
            "role": self.create_role_var.get(),
            "is_active": bool(self.create_active_var.get()),
        }

        def job():
            created = self.client.create_user(payload)
            users_payload = self.client.list_users(self.page, self.page_size, self.search_var.get().strip())
            stats_payload = self.client.get_stats()
            return {
                "created": created,
                "users": users_payload,
                "stats": stats_payload,
            }

        def success(payload: dict) -> None:
            created = payload["created"]
            self.create_email_var.set("")
            self.create_name_var.set("")
            self.create_password_var.set("")
            self.create_role_var.set("user")
            self.create_active_var.set(True)
            self._render_users(payload["users"])
            self._render_stats(payload["stats"])
            self._populate_selected_user(created)

        self._run_bg(
            fn=job,
            on_success=success,
            success_message=self.tr("admin_feedback_created"),
            busy_message=self.tr("admin_feedback_creating"),
        )

    def _update_user(self) -> None:
        user_id = self._resolve_user_id(self.update_id_var.get())
        if user_id is None:
            msgbox.showwarning(self.tr("admin_warning_title"), self.tr("admin_validation_user_id_required"))
            return

        email = self.update_email_var.get().strip().lower()
        full_name = self.update_name_var.get().strip()

        if not email or not full_name:
            msgbox.showwarning(self.tr("admin_warning_title"), self.tr("admin_validation_email_name_required"))
            return
        if not self._validate_email(email):
            msgbox.showwarning(self.tr("admin_warning_title"), self.tr("admin_validation_invalid_email"))
            return

        payload = {
            "email": email,
            "full_name": full_name,
            "role": self.update_role_var.get(),
            "is_active": bool(self.update_active_var.get()),
        }

        def job():
            updated = self.client.update_user(user_id, payload)
            users_payload = self.client.list_users(self.page, self.page_size, self.search_var.get().strip())
            stats_payload = self.client.get_stats()
            return {
                "updated": updated,
                "users": users_payload,
                "stats": stats_payload,
            }

        def success(payload: dict) -> None:
            self._render_users(payload["users"])
            self._render_stats(payload["stats"])
            self._populate_selected_user(payload["updated"])

        self._run_bg(
            fn=job,
            on_success=success,
            success_message=self.tr("admin_feedback_updated"),
            busy_message=self.tr("admin_feedback_updating"),
        )

    def _reset_password(self) -> None:
        user_id = self._resolve_user_id(self.reset_id_var.get())
        if user_id is None:
            msgbox.showwarning(self.tr("admin_warning_title"), self.tr("admin_validation_user_id_required"))
            return

        new_password = self.reset_password_var.get()
        if len(new_password) < 8:
            msgbox.showwarning(self.tr("admin_warning_title"), self.tr("admin_validation_password_length"))
            return

        def job():
            return self.client.reset_password(user_id, new_password)

        def success(_: dict) -> None:
            self.reset_password_var.set("")

        self._run_bg(
            fn=job,
            on_success=success,
            success_message=self.tr("admin_feedback_password_reset"),
            busy_message=self.tr("admin_feedback_resetting"),
        )

    def _change_status(self, is_active: bool) -> None:
        user_id = self._resolve_user_id(self.action_id_var.get())
        if user_id is None:
            msgbox.showwarning(self.tr("admin_warning_title"), self.tr("admin_validation_user_id_required"))
            return

        def job():
            updated = self.client.update_status(user_id, is_active)
            users_payload = self.client.list_users(self.page, self.page_size, self.search_var.get().strip())
            stats_payload = self.client.get_stats()
            return {
                "updated": updated,
                "users": users_payload,
                "stats": stats_payload,
            }

        def success(payload: dict) -> None:
            self._render_users(payload["users"])
            self._render_stats(payload["stats"])
            self._populate_selected_user(payload["updated"])

        action_name = self.tr("admin_feedback_activating") if is_active else self.tr("admin_feedback_deactivating")
        self._run_bg(
            fn=job,
            on_success=success,
            success_message=self.tr("admin_feedback_status"),
            busy_message=action_name,
        )

    def _delete_user(self) -> None:
        user_id = self._resolve_user_id(self.action_id_var.get())
        if user_id is None:
            msgbox.showwarning(self.tr("admin_warning_title"), self.tr("admin_validation_user_id_required"))
            return

        if not msgbox.askyesno(self.tr("admin_confirm_title"), self.tr("admin_delete_confirm", user_id=user_id)):
            return

        def job():
            self.client.delete_user(user_id)
            users_payload = self.client.list_users(self.page, self.page_size, self.search_var.get().strip())
            stats_payload = self.client.get_stats()
            return {
                "users": users_payload,
                "stats": stats_payload,
            }

        def success(payload: dict) -> None:
            self._render_users(payload["users"])
            self._render_stats(payload["stats"])
            if self.action_id_var.get().strip() == str(user_id):
                self.action_id_var.set("")
                self.update_id_var.set("")
                self.reset_id_var.set("")

        self._run_bg(
            fn=job,
            on_success=success,
            success_message=self.tr("admin_feedback_deleted"),
            busy_message=self.tr("admin_feedback_deleting"),
        )


if __name__ == "__main__":
    app = AdminApp()
    app.mainloop()
