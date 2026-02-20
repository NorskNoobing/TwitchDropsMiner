from __future__ import annotations

import asyncio
import logging
from typing import Any, TYPE_CHECKING
from collections import abc

import flet as ft

from translate import _
from exceptions import ExitRequest
from constants import WINDOW_TITLE, OUTPUT_FORMATTER
from webui.theme import get_theme, ThemeColors
from webui.components.status_bar import StatusBar
from webui.components.websocket_status import WebsocketStatus
from webui.components.login_form import LoginForm
from webui.components.campaign_progress import CampaignProgress
from webui.components.console_output import ConsoleOutput
from webui.components.channel_list import ChannelList
from webui.components.inventory import InventoryOverview
from webui.components.settings_panel import SettingsPanel
from webui.components.help_tab import HelpTab

if TYPE_CHECKING:
    from twitch import Twitch
    from inventory import TimedDrop
    from utils import Game, _T


logger = logging.getLogger("TwitchDrops")


class _WebOutputHandler(logging.Handler):
    """Logging handler that outputs to the WebUI console."""

    def __init__(self, output: WebUIManager):
        super().__init__()
        self._output = output

    def emit(self, record):
        self._output.print(self.format(record))


class TrayIcon:
    """Stub tray icon for web UI (no-op implementation)."""

    TITLE = "Twitch Drops Miner"

    def __init__(self, manager: WebUIManager):
        self._manager = manager
        self.icon = None
        self._icon_state: str = "pickaxe"

    def stop(self) -> None:
        pass

    def quit(self) -> None:
        self._manager.close()

    def minimize(self) -> None:
        pass

    def restore(self) -> None:
        pass

    def notify(
        self, message: str, title: str | None = None, duration: float = 10
    ) -> asyncio.Task[None] | None:
        # Web UI doesn't support system notifications
        return None

    def update_title(self, drop: TimedDrop | None) -> None:
        pass

    def change_icon(self, state: str) -> None:
        self._icon_state = state


class Tabs:
    """Tab management for the web UI."""

    def __init__(self, manager: WebUIManager):
        self._manager = manager
        self._current_tab = 0
        self._tab_changed_callbacks: list[abc.Callable[[int], Any]] = []

    def current_tab(self) -> int:
        return self._current_tab

    def set_current_tab(self, index: int) -> None:
        self._current_tab = index
        for callback in self._tab_changed_callbacks:
            callback(index)

    def add_view_event(self, callback: abc.Callable[[Any], Any]) -> None:
        self._tab_changed_callbacks.append(lambda idx: callback(None))


class WebUIManager:
    """
    Web-based UI manager using Flet.
    Mirrors the interface of GUIManager for compatibility with the Twitch client.
    """

    def __init__(self, twitch: Twitch):
        self._twitch: Twitch = twitch
        self._poll_task: asyncio.Task[None] | None = None
        self._close_requested = asyncio.Event()
        self._page: ft.Page | None = None
        self._current_theme: ThemeColors = get_theme(twitch.settings.dark_mode)

        # Initialize components (they will be built when the page is ready)
        self.tabs = Tabs(self)
        self.tray = TrayIcon(self)
        self.status = StatusBar(self)
        self.websockets = WebsocketStatus(self)
        self.login = LoginForm(self)
        self.progress = CampaignProgress(self)
        self.output = ConsoleOutput(self)
        self.channels = ChannelList(self)
        self.inv = InventoryOverview(self)
        self.settings = SettingsPanel(self)
        self.help = HelpTab(self)

        # Register logging handler
        self._handler = _WebOutputHandler(self)
        self._handler.setFormatter(OUTPUT_FORMATTER)
        logger.addHandler(self._handler)
        if (logging_level := logger.getEffectiveLevel()) < logging.ERROR:
            self.print(f"Logging level: {logging.getLevelName(logging_level)}")

    @property
    def running(self) -> bool:
        """Check if the UI is running."""
        return self._poll_task is not None

    @property
    def close_requested(self) -> bool:
        """Check if close has been requested."""
        return self._close_requested.is_set()

    async def wait_until_closed(self) -> None:
        """Wait until the user closes the window."""
        await self._close_requested.wait()

    async def coro_unless_closed(self, coro: abc.Awaitable[_T]) -> _T:
        """Run a coroutine unless the window is closed."""
        tasks = [asyncio.ensure_future(coro), asyncio.ensure_future(self._close_requested.wait())]
        done: set[asyncio.Task[Any]]
        pending: set[asyncio.Task[Any]]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        if self._close_requested.is_set():
            raise ExitRequest()
        return await next(iter(done))

    def prevent_close(self) -> None:
        """Prevent the window from closing."""
        self._close_requested.clear()

    def start(self) -> None:
        """Start the UI event loop."""
        if self._poll_task is None:
            self._poll_task = asyncio.create_task(self._run_flet())

    def stop(self) -> None:
        """Stop the UI event loop."""
        self.progress.stop_timer()
        if self._poll_task is not None:
            self._poll_task.cancel()
            self._poll_task = None

    async def _run_flet(self) -> None:
        """Run the Flet app."""

        async def main(page: ft.Page) -> None:
            self._page = page
            page.title = WINDOW_TITLE
            page.window.width = 1100
            page.window.height = 800
            page.window.min_width = 900
            page.window.min_height = 600
            page.on_window_event = self._on_window_event

            # Build the UI
            self._build_ui(page)

            # Apply initial theme
            self.apply_theme(self._twitch.settings.dark_mode)

            # Wait for close
            await self._close_requested.wait()

        try:
            await ft.app_async(
                target=main,
                view=ft.AppView.WEB_BROWSER,
                port=8550,
            )
        except Exception as e:
            logger.error(f"Flet app error: {e}")
        finally:
            self._poll_task = None

    def _on_window_event(self, e: ft.WindowEvent) -> None:
        """Handle window events."""
        if e.data == "close":
            self.close()

    def _build_ui(self, page: ft.Page) -> None:
        """Build the main UI structure."""
        # Create tab content containers
        main_content = ft.Column(
            controls=[
                # Top row: Status bar
                self.status.build(),
                # Middle row: Websockets, Login, Channel list
                ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                self.websockets.build(),
                                self.login.build(),
                            ],
                            spacing=8,
                        ),
                        ft.Column(
                            controls=[self.progress.build()],
                            spacing=8,
                            expand=True,
                        ),
                        self.channels.build(),
                    ],
                    spacing=8,
                    expand=True,
                ),
                # Console output
                self.output.build(),
            ],
            spacing=8,
            expand=True,
        )

        self._tab_contents = [
            main_content,
            self.inv.build(),
            self.settings.build(),
            self.help.build(),
        ]
        self._current_tab = 0

        # Create tab buttons
        tab_names = [
            _("gui", "tabs", "main"),
            _("gui", "tabs", "inventory"),
            _("gui", "tabs", "settings"),
            _("gui", "tabs", "help"),
        ]

        self._tab_buttons = []
        for i, name in enumerate(tab_names):
            btn = ft.TextButton(content=ft.Text(name, weight=ft.FontWeight.BOLD if i == 0 else None))
            btn.data = i
            btn.on_click = self._on_tab_click
            self._tab_buttons.append(btn)

        tab_bar = ft.Row(
            controls=self._tab_buttons,
            spacing=4,
        )

        # Content area - starts with main tab content
        self._content_area = ft.Container(
            content=self._tab_contents[0],
            expand=True,
            padding=16,
        )

        # Main layout
        page.add(
            ft.Column(
                controls=[
                    ft.Container(
                        content=tab_bar,
                        padding=8,
                        border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.OUTLINE)),
                    ),
                    self._content_area,
                ],
                expand=True,
                spacing=0,
            )
        )

    def _on_tab_click(self, e: ft.ControlEvent) -> None:
        """Handle tab button click."""
        new_tab = e.control.data
        if new_tab == self._current_tab:
            return

        # Update button styles
        for i, btn in enumerate(self._tab_buttons):
            if btn.content and isinstance(btn.content, ft.Text):
                btn.content.weight = ft.FontWeight.BOLD if i == new_tab else None

        # Initialize settings when switching to settings tab
        if new_tab == 2:  # Settings tab
            self.settings.initialize()

        # Swap content
        self._content_area.content = self._tab_contents[new_tab]
        self._current_tab = new_tab
        self.tabs.set_current_tab(new_tab)

        if self._page:
            self._page.update()

    def close(self, *args) -> int:
        """Request the GUI application to close."""
        self._close_requested.set()
        # Notify client we're supposed to close
        self._twitch.close()
        return 0

    def close_window(self) -> None:
        """Close the window and clean up."""
        self.tray.stop()
        logger.removeHandler(self._handler)
        if self._page:
            self._page.window.close()

    def unfocus(self) -> None:
        """Unfocus the current selection."""
        self.channels.clear_selection()
        self.settings.clear_selection()

    def save(self, *, force: bool = False) -> None:
        """Save the application state."""
        # WebUI doesn't have image cache like GUI
        pass

    def grab_attention(self, *, sound: bool = True) -> None:
        """Grab the user's attention (no-op for web UI)."""
        # Web UI can't grab attention like desktop app
        pass

    def set_games(self, games: set[Game]) -> None:
        """Set available games for the settings panel."""
        self.settings.set_games(games)

    def display_drop(
        self, drop: TimedDrop, *, countdown: bool = True, subone: bool = False
    ) -> None:
        """Display drop progress."""
        self.progress.display(drop, countdown=countdown, subone=subone)
        self.tray.update_title(drop)

    def clear_drop(self) -> None:
        """Clear the drop display."""
        self.progress.display(None)
        self.tray.update_title(None)

    def print(self, message: str) -> None:
        """Print a message to the console output."""
        self.output.print(message)

    def apply_theme(self, dark: bool) -> None:
        """Apply dark/light theme to all components."""
        self._current_theme = get_theme(dark)
        colors = self._current_theme

        if self._page:
            # Set page theme
            self._page.bgcolor = colors["bg"]
            self._page.theme_mode = ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT

        # Apply theme to all components
        self.status.apply_theme(colors)
        self.websockets.apply_theme(colors)
        self.login.apply_theme(colors)
        self.progress.apply_theme(colors)
        self.output.apply_theme(colors)
        self.channels.apply_theme(colors)
        self.inv.apply_theme(colors)
        self.settings.apply_theme(colors)
        self.help.apply_theme(colors)

        if self._page:
            self._page.update()
