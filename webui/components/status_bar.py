from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from translate import _

if TYPE_CHECKING:
    from webui.app import WebUIManager


class StatusBar:
    """Status bar component displaying the current application status."""

    def __init__(self, manager: WebUIManager):
        self._manager = manager
        self._label = ft.Text(value="", size=14)
        self._container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(_("gui", "status", "name"), weight=ft.FontWeight.BOLD, size=12),
                    self._label,
                ],
                spacing=2,
            ),
            padding=ft.padding.all(8),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=4,
        )

    def update(self, text: str) -> None:
        """Update the status bar text."""
        self._label.value = text
        if self._manager._page:
            self._manager._page.update()

    def clear(self) -> None:
        """Clear the status bar text."""
        self._label.value = ""
        if self._manager._page:
            self._manager._page.update()

    def build(self) -> ft.Container:
        """Build and return the status bar control."""
        return self._container

    def apply_theme(self, colors: dict) -> None:
        """Apply theme colors to the status bar."""
        self._container.bgcolor = colors["surface"]
        self._container.border = ft.border.all(1, colors["border"])
        self._label.color = colors["fg"]
        # Update the title label color too
        if self._container.content and isinstance(self._container.content, ft.Column):
            for control in self._container.content.controls:
                if isinstance(control, ft.Text):
                    control.color = colors["fg"]
