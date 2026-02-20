from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import flet as ft
from yarl import URL

from translate import _
from webui.utils import webopen

if TYPE_CHECKING:
    from webui.app import WebUIManager


@dataclass
class LoginData:
    username: str
    password: str
    token: str


class LoginForm:
    """Login form component for user authentication."""

    def __init__(self, manager: WebUIManager):
        self._manager = manager
        self._confirm = asyncio.Event()

        self._status_label = ft.Text(
            _("gui", "login", "logged_out"),
            size=12,
            text_align=ft.TextAlign.CENTER,
        )
        self._user_id_label = ft.Text(
            "-",
            size=12,
            text_align=ft.TextAlign.CENTER,
        )

        self._login_entry = ft.TextField(
            hint_text=_("gui", "login", "username"),
            width=200,
            height=40,
            text_size=14,
        )
        self._pass_entry = ft.TextField(
            hint_text=_("gui", "login", "password"),
            password=True,
            can_reveal_password=True,
            width=200,
            height=40,
            text_size=14,
        )
        self._token_entry = ft.TextField(
            hint_text=_("gui", "login", "twofa_code"),
            width=200,
            height=40,
            text_size=14,
        )

        self._button = ft.ElevatedButton(
            content=ft.Text(_("gui", "login", "button")),
            disabled=True,
        )
        self._button.on_click = self._on_button_click

        self._container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(_("gui", "login", "name"), weight=ft.FontWeight.BOLD, size=12),
                    ft.Row(
                        controls=[
                            ft.Text(_("gui", "login", "labels"), size=12),
                            ft.Column(
                                controls=[self._status_label, self._user_id_label],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=0,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    self._button,
                ],
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.all(8),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=4,
        )

    def _on_button_click(self, e: ft.ControlEvent) -> None:
        """Handle button click."""
        self._confirm.set()

    def clear(self, login: bool = False, password: bool = False, token: bool = False) -> None:
        """Clear specified entry fields."""
        clear_all = not login and not password and not token
        if login or clear_all:
            self._login_entry.value = ""
        if password or clear_all:
            self._pass_entry.value = ""
        if token or clear_all:
            self._token_entry.value = ""
        if self._manager._page:
            self._manager._page.update()

    async def wait_for_login_press(self) -> None:
        """Wait for the user to press the login button."""
        self._confirm.clear()
        try:
            self._button.disabled = False
            if self._manager._page:
                self._manager._page.update()
            await self._manager.coro_unless_closed(self._confirm.wait())
        finally:
            self._button.disabled = True
            if self._manager._page:
                self._manager._page.update()

    async def ask_login(self) -> LoginData:
        """Ask the user for login credentials."""
        self.update(_("gui", "login", "required"), None)
        # Ensure the window gets attention
        self._manager.grab_attention(sound=False)

        while True:
            self._manager.print(_("gui", "login", "request"))
            await self.wait_for_login_press()

            login_data = LoginData(
                self._login_entry.value.strip() if self._login_entry.value else "",
                self._pass_entry.value if self._pass_entry.value else "",
                self._token_entry.value.strip() if self._token_entry.value else "",
            )

            # Basic input data validation
            if not (3 <= len(login_data.username) <= 25):
                self.clear(login=True)
                continue
            if len(login_data.password) < 8:
                self.clear(password=True)
                continue
            if login_data.token and len(login_data.token) < 6:
                self.clear(token=True)
                continue
            return login_data

    async def ask_enter_code(self, page_url: URL, user_code: str) -> None:
        """Ask the user to enter an activation code."""
        self.update(_("gui", "login", "required"), None)
        # Ensure the window gets attention
        self._manager.grab_attention(sound=False)
        self._manager.print(_("gui", "login", "request"))
        await self.wait_for_login_press()
        self._manager.print(f"Enter this code on the Twitch's device activation page: {user_code}")
        await asyncio.sleep(4)
        webopen(page_url)

    def update(self, status: str, user_id: int | None) -> None:
        """Update the login status display."""
        self._status_label.value = status
        self._user_id_label.value = str(user_id) if user_id is not None else "-"
        if self._manager._page:
            self._manager._page.update()

    def build(self) -> ft.Container:
        """Build and return the login form control."""
        return self._container

    def apply_theme(self, colors: dict) -> None:
        """Apply theme colors to the login form."""
        self._container.bgcolor = colors["surface"]
        self._container.border = ft.border.all(1, colors["border"])
        self._status_label.color = colors["fg"]
        self._user_id_label.color = colors["fg"]

        # Update text fields
        for field in [self._login_entry, self._pass_entry, self._token_entry]:
            field.bgcolor = colors["fieldbg"]
            field.color = colors["fg"]
            field.border_color = colors["border"]

        # Update title color
        if self._container.content and isinstance(self._container.content, ft.Column):
            first_control = self._container.content.controls[0]
            if isinstance(first_control, ft.Text):
                first_control.color = colors["fg"]
