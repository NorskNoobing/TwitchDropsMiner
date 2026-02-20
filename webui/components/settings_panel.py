from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

import flet as ft
from yarl import URL

from translate import _
from constants import PriorityMode, State

if TYPE_CHECKING:
    from webui.app import WebUIManager
    from settings import Settings
    from utils import Game


class SettingsPanel:
    """Settings panel component with all configuration options."""

    @cached_property
    def PRIORITY_MODES(self) -> dict[PriorityMode, str]:
        """Priority mode options."""
        return {
            PriorityMode.PRIORITY_ONLY: _("gui", "settings", "priority_modes", "priority_only"),
            PriorityMode.ENDING_SOONEST: _("gui", "settings", "priority_modes", "ending_soonest"),
            PriorityMode.LOW_AVBL_FIRST: _("gui", "settings", "priority_modes", "low_availability"),
        }

    def __init__(self, manager: WebUIManager):
        self._manager = manager
        self._settings: Settings | None = None
        self._game_names: set[str] = set()

        # Initialize controls
        self._language_dropdown = ft.Dropdown(
            label="Language",
            width=200,
        )
        self._language_dropdown.on_change = self._on_language_change

        self._dark_mode_checkbox = ft.Checkbox(
            label=_("gui", "settings", "general", "dark_mode"),
            value=True,
        )
        self._dark_mode_checkbox.on_change = self._on_dark_mode_change

        self._tray_notifications_checkbox = ft.Checkbox(
            label=_("gui", "settings", "general", "tray_notifications"),
            value=True,
        )
        self._tray_notifications_checkbox.on_change = self._on_tray_notifications_change

        self._priority_mode_dropdown = ft.Dropdown(
            label=_("gui", "settings", "general", "priority_mode"),
            width=250,
        )
        self._priority_mode_dropdown.on_change = self._on_priority_mode_change

        self._proxy_field = ft.TextField(
            label=_("gui", "settings", "general", "proxy"),
            hint_text="http://username:password@address:port",
            width=350,
        )
        self._proxy_field.on_blur = self._on_proxy_change

        self._enable_badges_emotes_checkbox = ft.Checkbox(
            label=_("gui", "settings", "advanced", "enable_badges_emotes"),
            value=True,
        )
        self._enable_badges_emotes_checkbox.on_change = self._on_enable_badges_emotes_change

        self._available_drops_check_checkbox = ft.Checkbox(
            label=_("gui", "settings", "advanced", "available_drops_check"),
            value=True,
        )
        self._available_drops_check_checkbox.on_change = self._on_available_drops_check_change

        # Priority list
        self._priority_entry = ft.TextField(
            hint_text=_("gui", "settings", "game_name"),
            width=200,
        )
        self._priority_list = ft.ListView(
            controls=[],
            height=200,
            spacing=2,
        )
        self._priority_list_items: list[str] = []

        # Exclude list
        self._exclude_entry = ft.TextField(
            hint_text=_("gui", "settings", "game_name"),
            width=200,
        )
        self._exclude_list = ft.ListView(
            controls=[],
            height=200,
            spacing=2,
        )
        self._exclude_list_items: list[str] = []

        # Reload button
        self._reload_button = ft.ElevatedButton(
            content=ft.Text(_("gui", "settings", "reload")),
        )
        self._reload_button.on_click = self._on_reload_click

        self._container = self._build_layout()

    def _build_layout(self) -> ft.Container:
        """Build the settings panel layout."""
        # Priority add button
        priority_add_btn = ft.IconButton(icon=ft.Icons.ADD)
        priority_add_btn.on_click = self._priority_add

        # Priority move buttons
        priority_up_btn = ft.IconButton(icon=ft.Icons.ARROW_UPWARD, tooltip="Move up")
        priority_up_btn.on_click = lambda e: self._priority_move(1)

        priority_down_btn = ft.IconButton(icon=ft.Icons.ARROW_DOWNWARD, tooltip="Move down")
        priority_down_btn.on_click = lambda e: self._priority_move(-1)

        priority_top_btn = ft.IconButton(icon=ft.Icons.VERTICAL_ALIGN_TOP, tooltip="Move to top")
        priority_top_btn.on_click = lambda e: self._priority_move(1000)

        priority_bottom_btn = ft.IconButton(icon=ft.Icons.VERTICAL_ALIGN_BOTTOM, tooltip="Move to bottom")
        priority_bottom_btn.on_click = lambda e: self._priority_move(-1000)

        priority_delete_btn = ft.IconButton(icon=ft.Icons.DELETE, tooltip="Delete")
        priority_delete_btn.on_click = self._priority_delete

        # Exclude buttons
        exclude_add_btn = ft.IconButton(icon=ft.Icons.ADD)
        exclude_add_btn.on_click = self._exclude_add

        exclude_delete_btn = ft.IconButton(icon=ft.Icons.DELETE, tooltip="Delete")
        exclude_delete_btn.on_click = self._exclude_delete

        # General section
        general_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(_("gui", "settings", "general", "name"), weight=ft.FontWeight.BOLD, size=14),
                    ft.Row([ft.Text("Language:"), self._language_dropdown]),
                    self._dark_mode_checkbox,
                    self._tray_notifications_checkbox,
                    ft.Row([ft.Text(_("gui", "settings", "general", "priority_mode") + ":"), self._priority_mode_dropdown]),
                    self._proxy_field,
                ],
                spacing=8,
            ),
            padding=12,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=4,
        )

        # Advanced section
        advanced_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(_("gui", "settings", "advanced", "name"), weight=ft.FontWeight.BOLD, size=14),
                    ft.Text(_("gui", "settings", "advanced", "warning"), color="red", size=12),
                    ft.Text(_("gui", "settings", "advanced", "warning_text"), color="goldenrod", size=11),
                    self._enable_badges_emotes_checkbox,
                    self._available_drops_check_checkbox,
                ],
                spacing=8,
            ),
            padding=12,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=4,
        )

        # Priority section
        priority_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(_("gui", "settings", "priority"), weight=ft.FontWeight.BOLD, size=14),
                    ft.Row([
                        self._priority_entry,
                        priority_add_btn,
                    ]),
                    ft.Container(
                        content=self._priority_list,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=4,
                        padding=4,
                    ),
                    ft.Row([
                        priority_up_btn,
                        priority_down_btn,
                        priority_top_btn,
                        priority_bottom_btn,
                        priority_delete_btn,
                    ], alignment=ft.MainAxisAlignment.CENTER),
                ],
                spacing=8,
            ),
            padding=12,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=4,
            width=300,
        )

        # Exclude section
        exclude_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(_("gui", "settings", "exclude"), weight=ft.FontWeight.BOLD, size=14),
                    ft.Row([
                        self._exclude_entry,
                        exclude_add_btn,
                    ]),
                    ft.Container(
                        content=self._exclude_list,
                        border=ft.border.all(1, ft.Colors.OUTLINE),
                        border_radius=4,
                        padding=4,
                    ),
                    ft.Row([
                        exclude_delete_btn,
                    ], alignment=ft.MainAxisAlignment.CENTER),
                ],
                spacing=8,
            ),
            padding=12,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=4,
            width=300,
        )

        # Reload section
        reload_section = ft.Container(
            content=ft.Row([
                ft.Text(_("gui", "settings", "reload_text")),
                self._reload_button,
            ], alignment=ft.MainAxisAlignment.CENTER),
            padding=8,
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Column([general_section, advanced_section], spacing=8, expand=True),
                            priority_section,
                            exclude_section,
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                        wrap=True,
                    ),
                    reload_section,
                ],
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=16,
            expand=True,
        )

    def initialize(self) -> None:
        """Initialize the settings panel with current settings."""
        self._get_settings()

    def _get_settings(self) -> Settings | None:
        """Get settings from manager."""
        if self._settings is None and self._manager._twitch:
            self._settings = self._manager._twitch.settings
            self._init_from_settings()
        return self._settings

    def _init_from_settings(self) -> None:
        """Initialize controls from settings."""
        if self._settings is None:
            return

        # Language dropdown
        self._language_dropdown.options = [
            ft.dropdown.Option(lang) for lang in _.languages
        ]
        self._language_dropdown.value = _.current

        # Dark mode
        self._dark_mode_checkbox.value = self._settings.dark_mode

        # Tray notifications
        self._tray_notifications_checkbox.value = self._settings.tray_notifications

        # Priority mode
        self._priority_mode_dropdown.options = [
            ft.dropdown.Option(key=str(mode.value), text=text)
            for mode, text in self.PRIORITY_MODES.items()
        ]
        self._priority_mode_dropdown.value = str(self._settings.priority_mode.value)

        # Proxy
        self._proxy_field.value = str(self._settings.proxy) if self._settings.proxy.host else ""

        # Advanced settings
        self._enable_badges_emotes_checkbox.value = self._settings.enable_badges_emotes
        self._available_drops_check_checkbox.value = self._settings.available_drops_check

        # Priority list
        self._priority_list_items = list(self._settings.priority)
        self._update_priority_list_display()

        # Exclude list
        self._exclude_list_items = sorted(self._settings.exclude)
        self._update_exclude_list_display()

    def _on_language_change(self, e: ft.ControlEvent) -> None:
        """Handle language change."""
        settings = self._get_settings()
        if settings and e.control.value:
            settings.language = e.control.value

    def _on_dark_mode_change(self, e: ft.ControlEvent) -> None:
        """Handle dark mode change."""
        settings = self._get_settings()
        if settings:
            settings.dark_mode = e.control.value
            self._manager.apply_theme(settings.dark_mode)

    def _on_tray_notifications_change(self, e: ft.ControlEvent) -> None:
        """Handle tray notifications change."""
        settings = self._get_settings()
        if settings:
            settings.tray_notifications = e.control.value

    def _on_priority_mode_change(self, e: ft.ControlEvent) -> None:
        """Handle priority mode change."""
        settings = self._get_settings()
        if settings and e.control.value:
            for mode, text in self.PRIORITY_MODES.items():
                if str(mode.value) == e.control.value:
                    settings.priority_mode = mode
                    break

    def _on_proxy_change(self, e: ft.ControlEvent) -> None:
        """Handle proxy change."""
        settings = self._get_settings()
        if settings:
            raw_url = e.control.value.strip() if e.control.value else ""
            if raw_url:
                url = URL(raw_url)
                if url.host is not None and url.port is not None:
                    settings.proxy = url
                else:
                    e.control.value = ""
                    settings.proxy = URL()
            else:
                settings.proxy = URL()
            if self._manager._page:
                self._manager._page.update()

    def _on_enable_badges_emotes_change(self, e: ft.ControlEvent) -> None:
        """Handle enable badges/emotes change."""
        settings = self._get_settings()
        if settings:
            settings.enable_badges_emotes = e.control.value

    def _on_available_drops_check_change(self, e: ft.ControlEvent) -> None:
        """Handle available drops check change."""
        settings = self._get_settings()
        if settings:
            settings.available_drops_check = e.control.value

    def _on_reload_click(self, e: ft.ControlEvent) -> None:
        """Handle reload button click."""
        if self._manager._twitch:
            self._manager._twitch.state_change(State.INVENTORY_FETCH)()

    def _update_priority_list_display(self) -> None:
        """Update the priority list display."""
        self._priority_list.controls.clear()
        for i, item in enumerate(self._priority_list_items):
            container = ft.Container(
                content=ft.Text(item, size=12),
                padding=4,
                data=i,
            )
            container.on_click = lambda e, idx=i: self._select_priority_item(idx)
            self._priority_list.controls.append(container)
        if self._manager._page:
            self._manager._page.update()

    def _update_exclude_list_display(self) -> None:
        """Update the exclude list display."""
        self._exclude_list.controls.clear()
        for i, item in enumerate(self._exclude_list_items):
            container = ft.Container(
                content=ft.Text(item, size=12),
                padding=4,
                data=i,
            )
            container.on_click = lambda e, idx=i: self._select_exclude_item(idx)
            self._exclude_list.controls.append(container)
        if self._manager._page:
            self._manager._page.update()

    def _select_priority_item(self, idx: int) -> None:
        """Select a priority list item."""
        for i, control in enumerate(self._priority_list.controls):
            if isinstance(control, ft.Container):
                control.bgcolor = ft.Colors.BLUE_GREY_700 if i == idx else None
        if self._manager._page:
            self._manager._page.update()

    def _select_exclude_item(self, idx: int) -> None:
        """Select an exclude list item."""
        for i, control in enumerate(self._exclude_list.controls):
            if isinstance(control, ft.Container):
                control.bgcolor = ft.Colors.BLUE_GREY_700 if i == idx else None
        if self._manager._page:
            self._manager._page.update()

    def _get_selected_priority_idx(self) -> int | None:
        """Get the selected priority list item index."""
        for control in self._priority_list.controls:
            if isinstance(control, ft.Container) and control.bgcolor:
                return control.data
        return None

    def _get_selected_exclude_idx(self) -> int | None:
        """Get the selected exclude list item index."""
        for control in self._exclude_list.controls:
            if isinstance(control, ft.Container) and control.bgcolor:
                return control.data
        return None

    def _priority_add(self, e: ft.ControlEvent) -> None:
        """Add a game to the priority list."""
        settings = self._get_settings()
        if not settings:
            return

        game_name = self._priority_entry.value.strip() if self._priority_entry.value else ""
        if not game_name:
            return

        self._priority_entry.value = ""
        if game_name not in self._priority_list_items:
            self._priority_list_items.append(game_name)
            settings.priority.append(game_name)
            settings.alter()
            self._update_priority_list_display()

    def _priority_move(self, amount: int) -> None:
        """Move the selected priority item."""
        settings = self._get_settings()
        idx = self._get_selected_priority_idx()
        if settings is None or idx is None:
            return

        max_idx = len(self._priority_list_items) - 1
        if amount == 0 or (amount > 0 and idx == 0) or (amount < 0 and idx == max_idx):
            return

        insert_idx = idx - amount
        insert_idx = max(0, min(insert_idx, max_idx))

        item = self._priority_list_items.pop(idx)
        self._priority_list_items.insert(insert_idx, item)

        settings.priority.pop(idx)
        settings.priority.insert(insert_idx, item)
        settings.alter()

        self._update_priority_list_display()
        self._select_priority_item(insert_idx)

    def _priority_delete(self, e: ft.ControlEvent) -> None:
        """Delete the selected priority item."""
        settings = self._get_settings()
        idx = self._get_selected_priority_idx()
        if settings is None or idx is None:
            return

        self._priority_list_items.pop(idx)
        del settings.priority[idx]
        settings.alter()
        self._update_priority_list_display()

    def _exclude_add(self, e: ft.ControlEvent) -> None:
        """Add a game to the exclude list."""
        settings = self._get_settings()
        if not settings:
            return

        game_name = self._exclude_entry.value.strip() if self._exclude_entry.value else ""
        if not game_name:
            return

        self._exclude_entry.value = ""
        if game_name not in settings.exclude:
            settings.exclude.add(game_name)
            settings.alter()
            self._exclude_list_items = sorted(settings.exclude)
            self._update_exclude_list_display()

    def _exclude_delete(self, e: ft.ControlEvent) -> None:
        """Delete the selected exclude item."""
        settings = self._get_settings()
        idx = self._get_selected_exclude_idx()
        if settings is None or idx is None:
            return

        item = self._exclude_list_items[idx]
        settings.exclude.discard(item)
        settings.alter()
        self._exclude_list_items = sorted(settings.exclude)
        self._update_exclude_list_display()

    def clear_selection(self) -> None:
        """Clear all selections."""
        for control in self._priority_list.controls:
            if isinstance(control, ft.Container):
                control.bgcolor = None
        for control in self._exclude_list.controls:
            if isinstance(control, ft.Container):
                control.bgcolor = None
        if self._manager._page:
            self._manager._page.update()

    def set_games(self, games: set[Game]) -> None:
        """Set available games for autocomplete."""
        self._game_names.update(game.name for game in games)

    def build(self) -> ft.Container:
        """Build and return the settings panel control."""
        return self._container

    def apply_theme(self, colors: dict) -> None:
        """Apply theme colors to the settings panel."""
        self._container.bgcolor = colors["bg"]

        # Update text field colors
        for field in [self._proxy_field, self._priority_entry, self._exclude_entry]:
            field.bgcolor = colors["fieldbg"]
            field.color = colors["fg"]
            field.border_color = colors["border"]

        # Update dropdown colors
        for dropdown in [self._language_dropdown, self._priority_mode_dropdown]:
            dropdown.bgcolor = colors["fieldbg"]
            dropdown.color = colors["fg"]
            dropdown.border_color = colors["border"]

        # Update checkbox labels
        for checkbox in [
            self._dark_mode_checkbox,
            self._tray_notifications_checkbox,
            self._enable_badges_emotes_checkbox,
            self._available_drops_check_checkbox,
        ]:
            checkbox.label_style = ft.TextStyle(color=colors["fg"])
