"""Standalone admin desktop app for user management."""

from __future__ import annotations

import threading
import tkinter.messagebox as msgbox

import customtkinter as ctk
import requests

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


class ApiClient:
    def __init__(self) -> None:
        self.base_url = "http://127.0.0.1:8080"
        self.token: str | None = None

    def configure(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def login(self, email: str, password: str) -> dict:
        resp = requests.post(
            f"{self.base_url}/api/v1/auth/login",
            data={"username": email, "password": password},
            timeout=20,
        )
        if resp.status_code >= 400:
            raise ValueError(resp.text)
        payload = resp.json()
        self.token = payload["access_token"]
        return payload

    def list_users(self, page: int, page_size: int, search: str) -> dict:
        resp = requests.get(
            f"{self.base_url}/api/v1/users",
            params={"page": page, "page_size": page_size, "search": search},
            headers=self._headers(),
            timeout=20,
        )
        if resp.status_code >= 400:
            raise ValueError(resp.text)
        return resp.json()

    def create_user(self, payload: dict) -> dict:
        resp = requests.post(
            f"{self.base_url}/api/v1/users",
            json=payload,
            headers=self._headers(),
            timeout=20,
        )
        if resp.status_code >= 400:
            raise ValueError(resp.text)
        return resp.json()

    def update_status(self, user_id: int, is_active: bool) -> dict:
        resp = requests.patch(
            f"{self.base_url}/api/v1/users/{user_id}/status",
            json={"is_active": is_active},
            headers=self._headers(),
            timeout=20,
        )
        if resp.status_code >= 400:
            raise ValueError(resp.text)
        return resp.json()

    def delete_user(self, user_id: int) -> None:
        resp = requests.delete(
            f"{self.base_url}/api/v1/users/{user_id}",
            headers=self._headers(),
            timeout=20,
        )
        if resp.status_code >= 400:
            raise ValueError(resp.text)


class AdminApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AI Assist Admin")
        self.geometry("1150x760")
        self.minsize(980, 620)

        self.client = ApiClient()
        self.page = 1
        self.page_size = 15
        self._protected_widgets: list[object] = []

        self._build_ui()
        self._set_logged_in(False)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self, corner_radius=12)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(14, 8))

        self.backend_url_var = ctk.StringVar(value="http://127.0.0.1:8080")
        self.email_var = ctk.StringVar(value="admin@aiassist.app")
        self.password_var = ctk.StringVar(value="")

        ctk.CTkLabel(top, text="Backend URL").grid(row=0, column=0, padx=8, pady=8, sticky="w")
        ctk.CTkEntry(top, textvariable=self.backend_url_var, width=240).grid(row=0, column=1, padx=8, pady=8)

        ctk.CTkLabel(top, text="Admin Email").grid(row=0, column=2, padx=8, pady=8, sticky="w")
        ctk.CTkEntry(top, textvariable=self.email_var, width=230).grid(row=0, column=3, padx=8, pady=8)

        ctk.CTkLabel(top, text="Password").grid(row=0, column=4, padx=8, pady=8, sticky="w")
        ctk.CTkEntry(top, textvariable=self.password_var, width=180, show="*").grid(row=0, column=5, padx=8, pady=8)

        self.login_btn = ctk.CTkButton(top, text="Login", width=100, command=self._login)
        self.login_btn.grid(row=0, column=6, padx=8, pady=8)

        self.status_lbl = ctk.CTkLabel(top, text="Not authenticated", text_color="orange")
        self.status_lbl.grid(row=0, column=7, padx=8, pady=8, sticky="w")

        left = ctk.CTkFrame(self, corner_radius=12)
        left.grid(row=1, column=0, sticky="nsew", padx=(14, 7), pady=(8, 14))
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(left, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))

        self.search_var = ctk.StringVar(value="")
        self.search_entry = ctk.CTkEntry(toolbar, textvariable=self.search_var, placeholder_text="Search email/full name", width=260)
        self.search_entry.pack(side="left", padx=(0, 8))
        self.search_btn = ctk.CTkButton(toolbar, text="Search", width=85, command=lambda: self._load_users(reset_page=True))
        self.search_btn.pack(side="left", padx=(0, 6))
        self.refresh_btn = ctk.CTkButton(toolbar, text="Refresh", width=85, command=lambda: self._load_users(reset_page=False))
        self.refresh_btn.pack(side="left", padx=(0, 6))
        self.prev_btn = ctk.CTkButton(toolbar, text="Prev", width=65, command=self._prev_page)
        self.prev_btn.pack(side="right", padx=(6, 0))
        self.next_btn = ctk.CTkButton(toolbar, text="Next", width=65, command=self._next_page)
        self.next_btn.pack(side="right")

        self.page_lbl = ctk.CTkLabel(left, text="Page 1")
        self.page_lbl.grid(row=1, column=0, sticky="w", padx=12)

        self.user_box = ctk.CTkTextbox(left, wrap="none")
        self.user_box.grid(row=2, column=0, sticky="nsew", padx=10, pady=(4, 10))
        self.user_box.insert("1.0", "Login to load users.\n")
        self.user_box.configure(state="disabled")

        right = ctk.CTkFrame(self, corner_radius=12)
        right.grid(row=1, column=1, sticky="nsew", padx=(7, 14), pady=(8, 14))
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="Create User", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 8)
        )

        self.new_email = ctk.StringVar()
        self.new_name = ctk.StringVar()
        self.new_password = ctk.StringVar()
        self.new_role = ctk.StringVar(value="user")

        ctk.CTkLabel(right, text="Email").grid(row=1, column=0, sticky="w", padx=12)
        self.new_email_entry = ctk.CTkEntry(right, textvariable=self.new_email)
        self.new_email_entry.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(right, text="Full name").grid(row=3, column=0, sticky="w", padx=12)
        self.new_name_entry = ctk.CTkEntry(right, textvariable=self.new_name)
        self.new_name_entry.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(right, text="Password").grid(row=5, column=0, sticky="w", padx=12)
        self.new_password_entry = ctk.CTkEntry(right, textvariable=self.new_password, show="*")
        self.new_password_entry.grid(row=6, column=0, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(right, text="Role").grid(row=7, column=0, sticky="w", padx=12)
        self.role_menu = ctk.CTkOptionMenu(right, variable=self.new_role, values=["user", "admin"])
        self.role_menu.grid(row=8, column=0, sticky="ew", padx=12, pady=(0, 12))

        self.create_user_btn = ctk.CTkButton(right, text="Create User", command=self._create_user)
        self.create_user_btn.grid(row=9, column=0, sticky="ew", padx=12)

        ctk.CTkLabel(right, text="Quick Actions", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=10, column=0, sticky="w", padx=12, pady=(20, 8)
        )

        self.target_user_id = ctk.StringVar()
        self.target_user_entry = ctk.CTkEntry(
            right,
            textvariable=self.target_user_id,
            placeholder_text="Target User ID",
        )
        self.target_user_entry.grid(row=11, column=0, sticky="ew", padx=12, pady=(0, 8))

        self.activate_btn = ctk.CTkButton(right, text="Activate", command=lambda: self._change_status(True))
        self.activate_btn.grid(row=12, column=0, sticky="ew", padx=12, pady=(0, 6))
        self.deactivate_btn = ctk.CTkButton(right, text="Deactivate", command=lambda: self._change_status(False))
        self.deactivate_btn.grid(row=13, column=0, sticky="ew", padx=12, pady=(0, 6))
        self.delete_btn = ctk.CTkButton(
            right,
            text="Delete User",
            fg_color="#8B0000",
            hover_color="#A40000",
            command=self._delete_user,
        )
        self.delete_btn.grid(row=14, column=0, sticky="ew", padx=12, pady=(0, 10))

        self._protected_widgets = [
            self.search_entry,
            self.search_btn,
            self.refresh_btn,
            self.prev_btn,
            self.next_btn,
            self.new_email_entry,
            self.new_name_entry,
            self.new_password_entry,
            self.role_menu,
            self.create_user_btn,
            self.target_user_entry,
            self.activate_btn,
            self.deactivate_btn,
            self.delete_btn,
        ]

    def _set_logged_in(self, logged_in: bool) -> None:
        state = "normal" if logged_in else "disabled"
        for widget in self._protected_widgets:
            widget.configure(state=state)

        self.user_box.configure(state="normal")
        if not logged_in:
            self.user_box.delete("1.0", "end")
            self.user_box.insert("1.0", "Login to load users.\n")
            self.page_lbl.configure(text="Page 1")
        self.user_box.configure(state="disabled")

        for var in (
            self.new_email,
            self.new_name,
            self.new_password,
            self.target_user_id,
        ):
            if not logged_in:
                var.set("")

        self.login_btn.configure(text="Relogin" if logged_in else "Login")

    def _run_bg(self, fn, on_success=None, on_error=None) -> None:
        def runner():
            try:
                result = fn()
                if on_success:
                    self.after(0, lambda: on_success(result))
            except Exception as exc:
                if on_error:
                    self.after(0, lambda: on_error(exc))
                else:
                    self.after(0, lambda: msgbox.showerror("Error", str(exc)))

        threading.Thread(target=runner, daemon=True).start()

    def _login(self) -> None:
        url = self.backend_url_var.get().strip()
        email = self.email_var.get().strip()
        password = self.password_var.get()

        if not url or not email or not password:
            msgbox.showwarning("Validation", "Backend URL, email and password are required")
            return

        def job():
            self.client.configure(url)
            return self.client.login(email, password)

        def success(payload: dict) -> None:
            self.status_lbl.configure(text=f"Authenticated: {payload['user']['email']}", text_color="#33cc99")
            self._set_logged_in(True)
            self._load_users(reset_page=True)

        self._run_bg(job, on_success=success)

    def _render_users(self, payload: dict) -> None:
        self.user_box.configure(state="normal")
        self.user_box.delete("1.0", "end")

        header = f"ID   EMAIL                          ROLE    ACTIVE   FULL NAME\n"
        header += "-" * 90 + "\n"
        self.user_box.insert("1.0", header)

        for item in payload.get("items", []):
            line = (
                f"{item['id']:<4}"
                f"{item['email'][:30]:<31}"
                f"{item['role']:<8}"
                f"{str(item['is_active']):<9}"
                f"{item['full_name']}\n"
            )
            self.user_box.insert("end", line)

        self.user_box.configure(state="disabled")
        self.page_lbl.configure(
            text=(
                f"Page {payload.get('page', self.page)} | "
                f"Total users: {payload.get('total', 0)} | "
                f"Page size: {payload.get('page_size', self.page_size)}"
            )
        )

    def _load_users(self, reset_page: bool) -> None:
        if reset_page:
            self.page = 1

        search = self.search_var.get().strip()

        def job():
            return self.client.list_users(self.page, self.page_size, search)

        self._run_bg(job, on_success=self._render_users)

    def _next_page(self) -> None:
        self.page += 1
        self._load_users(reset_page=False)

    def _prev_page(self) -> None:
        self.page = max(1, self.page - 1)
        self._load_users(reset_page=False)

    def _create_user(self) -> None:
        payload = {
            "email": self.new_email.get().strip(),
            "full_name": self.new_name.get().strip(),
            "password": self.new_password.get(),
            "role": self.new_role.get(),
            "is_active": True,
        }
        if not payload["email"] or not payload["full_name"] or not payload["password"]:
            msgbox.showwarning("Validation", "Email, full name and password are required")
            return

        def job():
            return self.client.create_user(payload)

        def success(_):
            msgbox.showinfo("Success", "User created")
            self.new_email.set("")
            self.new_name.set("")
            self.new_password.set("")
            self._load_users(reset_page=False)

        self._run_bg(job, on_success=success)

    def _change_status(self, is_active: bool) -> None:
        raw_id = self.target_user_id.get().strip()
        if not raw_id.isdigit():
            msgbox.showwarning("Validation", "Valid user ID is required")
            return

        user_id = int(raw_id)

        def job():
            return self.client.update_status(user_id, is_active)

        def success(_):
            msgbox.showinfo("Success", "Status updated")
            self._load_users(reset_page=False)

        self._run_bg(job, on_success=success)

    def _delete_user(self) -> None:
        raw_id = self.target_user_id.get().strip()
        if not raw_id.isdigit():
            msgbox.showwarning("Validation", "Valid user ID is required")
            return

        if not msgbox.askyesno("Confirm", "Delete selected user?"):
            return

        user_id = int(raw_id)

        def job():
            self.client.delete_user(user_id)
            return True

        def success(_):
            msgbox.showinfo("Success", "User deleted")
            self._load_users(reset_page=False)

        self._run_bg(job, on_success=success)


if __name__ == "__main__":
    app = AdminApp()
    app.mainloop()
