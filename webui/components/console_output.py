from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import flet as ft

from translate import _

if TYPE_CHECKING:
    from webui.app import WebUIManager


class ConsoleOutput:
    """Console output component displaying timestamped log messages."""

    MAX_LINES = 500  # Maximum number of lines to keep

    def __init__(self, manager: WebUIManager):
        self._manager = manager
        self._messages: list[ft.Text] = []

        self._list_view = ft.ListView(
            controls=[],
            spacing=2,
            auto_scroll=True,
            expand=True,
        )

        self._container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(_("gui", "output"), weight=ft.FontWeight.BOLD, size=12),
                    ft.Container(
                        content=self._list_view,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=4,
                        padding=4,
                        expand=True,
                        height=200,
                    ),
                ],
                spacing=4,
                expand=True,
            ),
            padding=ft.padding.all(8),
            expand=True,
        )

        self._colors = {
            "bg": "#252525",
            "fg": "#e6e6e6",
        }

    def print(self, message: str) -> None:
        """Print a message to the console output with timestamp."""
        stamp = datetime.now().strftime("%X")
        if '\n' in message:
            message = message.replace('\n', f"\n{stamp}: ")

        text = ft.Text(
            f"{stamp}: {message}",
            size=12,
            font_family="Courier New",
            selectable=True,
            color=self._colors["fg"],
        )
        self._messages.append(text)
        self._list_view.controls.append(text)

        # Limit the number of messages
        while len(self._messages) > self.MAX_LINES:
            removed = self._messages.pop(0)
            if removed in self._list_view.controls:
                self._list_view.controls.remove(removed)

        if self._manager._page:
            self._manager._page.update()

    def configure_theme(self, *, bg: str, fg: str, sel_bg: str, sel_fg: str) -> None:
        """Configure theme colors."""
        self._colors["bg"] = bg
        self._colors["fg"] = fg

        # Update existing messages
        for text in self._messages:
            text.color = fg

        # Update container background
        if self._container.content and isinstance(self._container.content, ft.Column):
            for control in self._container.content.controls:
                if isinstance(control, ft.Container):
                    control.bgcolor = bg

        if self._manager._page:
            self._manager._page.update()

    def build(self) -> ft.Container:
        """Build and return the console output control."""
        return self._container

    def apply_theme(self, colors: dict) -> None:
        """Apply theme colors to the console output."""
        self.configure_theme(
            bg=colors["surface"],
            fg=colors["fg"],
            sel_bg=colors["sel_bg"],
            sel_fg=colors["sel_fg"],
        )

        # Update title color
        if self._container.content and isinstance(self._container.content, ft.Column):
            first_control = self._container.content.controls[0]
            if isinstance(first_control, ft.Text):
                first_control.color = colors["fg"]
