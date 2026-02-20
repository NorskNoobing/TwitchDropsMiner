from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from translate import _
from constants import State

if TYPE_CHECKING:
    from webui.app import WebUIManager
    from channel import Channel


class ChannelList:
    """Channel list component displaying available channels in a data table."""

    def __init__(self, manager: WebUIManager):
        self._manager = manager
        self._channel_map: dict[str, Channel] = {}
        self._selected_iid: str | None = None
        self._watching_iid: str | None = None

        # Switch button
        self._switch_button = ft.ElevatedButton(
            content=ft.Text(_("gui", "channels", "switch")),
            disabled=True,
        )
        self._switch_button.on_click = self._on_switch_click

        # Data table columns
        self._columns = [
            ft.DataColumn(ft.Text(_("gui", "channels", "headings", "channel"))),
            ft.DataColumn(ft.Text(_("gui", "channels", "headings", "status"))),
            ft.DataColumn(ft.Text(_("gui", "channels", "headings", "game"))),
            ft.DataColumn(ft.Text("Drops")),
            ft.DataColumn(ft.Text(_("gui", "channels", "headings", "viewers")), numeric=True),
            ft.DataColumn(ft.Text("ACL")),
        ]

        self._data_table = ft.DataTable(
            columns=self._columns,
            rows=[],
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=4,
            vertical_lines=ft.BorderSide(1, ft.Colors.OUTLINE),
            horizontal_lines=ft.BorderSide(1, ft.Colors.OUTLINE),
            column_spacing=20,
            show_checkbox_column=False,
        )

        self._container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(_("gui", "channels", "name"), weight=ft.FontWeight.BOLD, size=12),
                    self._switch_button,
                    ft.Container(
                        content=ft.Column(
                            controls=[self._data_table],
                            scroll=ft.ScrollMode.AUTO,
                        ),
                        expand=True,
                        height=300,
                    ),
                ],
                spacing=8,
            ),
            padding=ft.padding.all(8),
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=4,
            expand=True,
        )

    def _on_switch_click(self, e: ft.ControlEvent) -> None:
        """Handle switch button click."""
        if self._manager._twitch:
            self._manager._twitch.state_change(State.CHANNEL_SWITCH)()

    def _on_row_select(self, e: ft.ControlEvent) -> None:
        """Handle row selection."""
        row = e.control
        if row.data:
            iid = row.data
            if self._selected_iid == iid:
                # Deselect
                self._selected_iid = None
                row.selected = False
            else:
                # Deselect previous
                for r in self._data_table.rows:
                    r.selected = False
                # Select new
                self._selected_iid = iid
                row.selected = True

            self._switch_button.disabled = self._selected_iid is None
            if self._manager._page:
                self._manager._page.update()

    def _create_row(self, channel: Channel, iid: str) -> ft.DataRow:
        """Create a data row for a channel."""
        # Status
        if channel.online:
            status = _("gui", "channels", "online")
        elif channel.pending_online:
            status = _("gui", "channels", "pending")
        else:
            status = _("gui", "channels", "offline")

        # Game
        game = str(channel.game or "")

        # Drops
        drops = "Yes" if channel.drops_enabled else "No"

        # Viewers
        viewers = str(channel.viewers) if channel.viewers is not None else ""

        # ACL-based
        acl_based = "Yes" if channel.acl_based else "No"

        is_watching = iid == self._watching_iid

        row = ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(channel.name)),
                ft.DataCell(ft.Text(status)),
                ft.DataCell(ft.Text(game)),
                ft.DataCell(ft.Text(drops)),
                ft.DataCell(ft.Text(viewers)),
                ft.DataCell(ft.Text(acl_based)),
            ],
            data=iid,
            selected=iid == self._selected_iid,
            on_select_changed=lambda e, r=None: self._on_row_select(e),
            color=ft.Colors.GREY_700 if is_watching else None,
        )
        return row

    def clear_watching(self) -> None:
        """Clear the watching indicator from all channels."""
        self._watching_iid = None
        for row in self._data_table.rows:
            row.color = None
        if self._manager._page:
            self._manager._page.update()

    def set_watching(self, channel: Channel) -> None:
        """Set a channel as currently being watched."""
        self.clear_watching()
        iid = str(channel.iid)
        self._watching_iid = iid
        for row in self._data_table.rows:
            if row.data == iid:
                row.color = ft.Colors.GREY_700
                break
        if self._manager._page:
            self._manager._page.update()

    def get_selection(self) -> Channel | None:
        """Get the currently selected channel."""
        if not self._channel_map or not self._selected_iid:
            return None
        return self._channel_map.get(self._selected_iid)

    def clear_selection(self) -> None:
        """Clear the current selection."""
        self._selected_iid = None
        for row in self._data_table.rows:
            row.selected = False
        self._switch_button.disabled = True
        if self._manager._page:
            self._manager._page.update()

    def clear(self) -> None:
        """Clear all channels from the list."""
        self._data_table.rows.clear()
        self._channel_map.clear()
        self._selected_iid = None
        self._watching_iid = None
        self._switch_button.disabled = True
        if self._manager._page:
            self._manager._page.update()

    def display(self, channel: Channel, *, add: bool = False) -> None:
        """Display or update a channel in the list."""
        iid = str(channel.iid)

        if not add and iid not in self._channel_map:
            # Channel isn't on the list and we're not supposed to add it
            return

        if iid in self._channel_map:
            # Update existing row
            for row in self._data_table.rows:
                if row.data == iid:
                    # Update the row
                    new_row = self._create_row(channel, iid)
                    idx = self._data_table.rows.index(row)
                    self._data_table.rows[idx] = new_row
                    break
        elif add:
            # Add new row
            self._channel_map[iid] = channel
            self._data_table.rows.append(self._create_row(channel, iid))

        if self._manager._page:
            self._manager._page.update()

    def remove(self, channel: Channel) -> None:
        """Remove a channel from the list."""
        iid = str(channel.iid)
        if iid in self._channel_map:
            del self._channel_map[iid]
            for row in self._data_table.rows:
                if row.data == iid:
                    self._data_table.rows.remove(row)
                    break
            if self._selected_iid == iid:
                self._selected_iid = None
                self._switch_button.disabled = True
            if self._manager._page:
                self._manager._page.update()

    def shrink(self) -> None:
        """Shrink the columns (no-op in Flet, columns auto-size)."""
        pass

    def build(self) -> ft.Container:
        """Build and return the channel list control."""
        return self._container

    def apply_theme(self, colors: dict) -> None:
        """Apply theme colors to the channel list."""
        self._container.bgcolor = colors["surface"]
        self._container.border = ft.border.all(1, colors["border"])
        self._data_table.border = ft.border.all(1, colors["border"])
        self._data_table.vertical_lines = ft.BorderSide(1, colors["border"])
        self._data_table.horizontal_lines = ft.BorderSide(1, colors["border"])

        # Update column headers
        for col in self._data_table.columns:
            if isinstance(col.label, ft.Text):
                col.label.color = colors["fg"]

        # Update row text colors
        for row in self._data_table.rows:
            for cell in row.cells:
                if isinstance(cell.content, ft.Text):
                    cell.content.color = colors["fg"]

        # Update title color
        if self._container.content and isinstance(self._container.content, ft.Column):
            first_control = self._container.content.controls[0]
            if isinstance(first_control, ft.Text):
                first_control.color = colors["fg"]
