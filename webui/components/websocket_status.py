from __future__ import annotations

from math import log10, ceil
from typing import TYPE_CHECKING, TypedDict

import flet as ft

from translate import _
from constants import MAX_WEBSOCKETS, WS_TOPICS_LIMIT

if TYPE_CHECKING:
    from webui.app import WebUIManager


DIGITS = ceil(log10(WS_TOPICS_LIMIT))


class _WSEntry(TypedDict):
    status: str
    topics: int


class WebsocketStatus:
    """Component displaying the status of websocket connections."""

    def __init__(self, manager: WebUIManager):
        self._manager = manager
        self._items: dict[int, _WSEntry | None] = {i: None for i in range(MAX_WEBSOCKETS)}

        # Create labels for each websocket
        self._ws_labels: list[ft.Text] = []
        self._status_labels: list[ft.Text] = []
        self._topics_labels: list[ft.Text] = []

        for i in range(MAX_WEBSOCKETS):
            self._ws_labels.append(
                ft.Text(
                    _("gui", "websocket", "websocket").format(id=i + 1),
                    size=12,
                    font_family="Courier New",
                )
            )
            self._status_labels.append(ft.Text("", size=12, font_family="Courier New", width=120))
            self._topics_labels.append(
                ft.Text("", size=12, font_family="Courier New", width=50, text_align=ft.TextAlign.RIGHT)
            )

        self._container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(_("gui", "websocket", "name"), weight=ft.FontWeight.BOLD, size=12),
                    ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    self._ws_labels[i],
                                    self._status_labels[i],
                                    self._topics_labels[i],
                                ],
                                spacing=8,
                            )
                            for i in range(MAX_WEBSOCKETS)
                        ],
                        spacing=2,
                    ),
                ],
                spacing=4,
            ),
            padding=ft.padding.all(8),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=4,
        )
        self._update_display()

    def update(self, idx: int, status: str | None = None, topics: int | None = None) -> None:
        """Update the status of a specific websocket."""
        if status is None and topics is None:
            raise TypeError("You need to provide at least one of: status, topics")

        entry = self._items.get(idx)
        if entry is None:
            entry = self._items[idx] = _WSEntry(
                status=_("gui", "websocket", "disconnected"), topics=0
            )
        if status is not None:
            entry["status"] = status
        if topics is not None:
            entry["topics"] = topics
        self._update_display()

    def remove(self, idx: int) -> None:
        """Remove a websocket entry."""
        if idx in self._items:
            self._items[idx] = None
            self._update_display()

    def _update_display(self) -> None:
        """Update the display of all websocket statuses."""
        for idx in range(MAX_WEBSOCKETS):
            item = self._items.get(idx)
            if item is None:
                self._status_labels[idx].value = ""
                self._topics_labels[idx].value = ""
            else:
                self._status_labels[idx].value = item["status"]
                self._topics_labels[idx].value = f"{item['topics']:>{DIGITS}}/{WS_TOPICS_LIMIT}"

        if self._manager._page:
            self._manager._page.update()

    def build(self) -> ft.Container:
        """Build and return the websocket status control."""
        return self._container

    def apply_theme(self, colors: dict) -> None:
        """Apply theme colors to the websocket status."""
        self._container.bgcolor = colors["surface"]
        self._container.border = ft.border.all(1, colors["border"])

        for i in range(MAX_WEBSOCKETS):
            self._ws_labels[i].color = colors["fg"]
            self._status_labels[i].color = colors["fg"]
            self._topics_labels[i].color = colors["fg"]

        # Update title color
        if self._container.content and isinstance(self._container.content, ft.Column):
            first_control = self._container.content.controls[0]
            if isinstance(first_control, ft.Text):
                first_control.color = colors["fg"]
